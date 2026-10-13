#!/usr/bin/env python3
"""Full Bars: change a phone price in one place and let this tool update every other page.

WHERE PRICES LIVE
  Each product page (sites/full-bars/products/<phone>.html) has an option picker,
  <form class="picker" id="picker" data-prices="...">. data-prices holds every price for that phone,
  by storage and condition. It is the single source of truth: site.js reads it, and so do
  build_shopify_csv.py and check_site_prices.py.

  Every other price on the site is worked out from it, and this tool rewrites all of them:
    - product pages: <title>, meta and og: descriptions and titles ("from £X"), structured data
      (lowPrice / highPrice), the price shown before site.js runs (#pdPrice), the "Price for 128GB in
      Very Good. From £X in Good." line (#pdFrom), the prices under each storage and condition button,
      and the "Selected: ... £X" line;
    - every product card on every page ("from £X" and its data-from, which the shop's price filter
      and sort use);
    - every comparison-table row's "From" column (collections and the buying guide);
    - each collection's "N models · from £X" line, and the home page tiles that repeat it.

HOW TO USE IT (from the repo root; put a model name with spaces in quotes)

  Check the site. Nothing is written:
      python3 launch/full-bars/set_prices.py --check
      python3 launch/full-bars/set_prices.py --check sites/full-bars

  Change one price and update every page that shows it:
      python3 launch/full-bars/set_prices.py --set "iPhone 13" 128GB Good 199 sites/full-bars
  See what that would change first, without writing anything:
      python3 launch/full-bars/set_prices.py --set "iPhone 13" 128GB Good 199 sites/full-bars --dry-run
  Several prices in one go (repeat --set, same folder each time). Do this when one change on its own
  would make a better condition cheaper than a worse one, e.g. lowering Very Good and Good together:
      python3 launch/full-bars/set_prices.py --set iphone-13 128GB "Very Good" 219 sites/full-bars \\
                                             --set iphone-13 128GB Good 199 sites/full-bars

  Edited data-prices by hand? Bring every other page into line with it:
      python3 launch/full-bars/set_prices.py --write sites/full-bars

  MODEL can be the name on the picker ("iPhone 13", "Galaxy S23", "Pixel 8"), the page name
  ("iphone-13"), or brand and model ("Samsung Galaxy S23"). STORAGE is as on the page (128GB, 1TB).
  GRADE is Excellent, "Very Good" or Good (or EX, VG, GD). PRICE is whole pounds, VAT included.

  After any change: rebuild the Shopify CSV (build_shopify_csv.py, then validate_shopify_csv.py).

  If a change needs a hand edit (below), --set and --write refuse and write nothing, so the site never
  goes out half-done (a £305 phone still on "Under £300", say, or a Buy now button whose Payment Link
  charges the old price). Make the hand edit first and run it again, or add --allow-hand-edits to write
  everything else now and do the hand edit straight after, before you publish.

WHAT IT WON'T DO (it tells you instead, under "NEEDS A HAND EDIT")
  - Change which phones are on the "Under £300" page. That page has hand-written cards, a table,
    a description and sentences naming the phones, so a phone crossing £300 needs a person.
  - Move the "Lowest price" badge when a different phone becomes the cheapest.
  - Touch pay.js (the static route's Stripe Payment Links, keyed "<model> <storage> <condition>", the
    way site.js looks them up). A Payment Link charges the price it was made with, and a Stripe price
    can't be changed, so when --set changes a price that has a link in pay.js, it lists it: deactivate
    that link in Stripe, make a new one at the new price with the same settings (payment limit), and
    paste it into pay.js. --check lists every link in pay.js with the site's price for it now, so you
    can compare them in Stripe; it can't see what Stripe charges. Change prices with --set, not by
    hand in data-prices: only --set knows the old price, so only it can name the link to replace.
    It reads pay.js only as it ships: one entry per line, "iPhone 13 128GB Good": "https://...",
    double quotes, nothing else on the line, one entry for every phone, storage and condition. site.js
    would use a link written any other way (a comment after it, single quotes, two on a line), but
    this tool might not see it, so --set and --write refuse (exit 2, nothing written) and --check
    fails until pay.js is back in that layout.
  - Touch quote.js (trade-in pricing). quote.js works out trade-in offers from the shop's Very Good
    price for the six phones it buys (iPhone 13, 13 Pro, 14, 14 Pro, Galaxy S23, Pixel 8, 128GB and
    256GB), and check_site_prices.py insists they match. Change one of those Very Good prices and the
    tool tells you the sellPrice to type into quote.js, or you put the price back.
  - Write outside the folder you give it, write through a symlink, or write anything at all when
    the input is wrong (unknown phone, a price that would make Good dearer than Very Good, broken
    data-prices).
  Under "REVIEW" it lists sentences that compare prices ("cheaper", "most affordable") when the order
  of phones by price changes, and notes a price crossing the £750 Special Delivery cover or the £450
  Buy now cap, so you can reread them.

--check is a little stricter than check_site_prices.py on its own: it also fails when any derived
price is out of date that the checker doesn't look at (the #pdFrom line) and when the "Lowest price"
badge sits on a phone that is no longer the cheapest. It also lists every Payment Link in pay.js
under "PAYMENT LINKS IN pay.js", each with the site's price for it now, for you to compare with what
Stripe shows. That list never fails the check: this tool can't see what Stripe charges.

EXIT CODES
  0  all good: prices consistent (and written, for --write/--set), check_site_prices.py passes.
  1  something needs you: stale prices (--check), a hand edit (nothing written, unless you passed
     --allow-hand-edits), or check_site_prices.py fails.
  2  bad command or bad input (including a pay.js it can't read in full): nothing was written.

Python 3 standard library only. It finds what to rewrite with the same patterns check_site_prices.py
uses, and runs that checker after every write, so the two can't silently disagree.
"""
import argparse
import bisect
import html
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, 'check_site_prices.py')
UNDER_FILE = 'collections/under-300.html'
UNDER_LIMIT = 300            # "Under £300" means a lowest price below 300 (same rule as check_site_prices.py)
LOWEST_BADGE = 'Lowest price'
SD_COVER = 750               # Royal Mail Special Delivery standard cover (GO-LIVE.md section 1, courier)
MAX_PRICE = 999_999          # a sanity limit on --set: anything bigger is a typo
GRADE_ALIASES = {'ex': 'Excellent', 'vg': 'Very Good', 'gd': 'Good'}
PAY_FILE = 'pay.js'          # the static route's Stripe Payment Links (GO-LIVE.md section 6, step 1)
# One pay.js entry per line, after window.FULLBARS_PAY: "iPhone 13 128GB Good": "https://buy.stripe.com/...",
# (the same pattern go_live.py and check_site_prices.py read it with). read_pay() refuses any other layout.
PAY_LINE_RX = re.compile(r'^\s*"([^"]+)":\s*"([^"]*)",?\s*$', re.M)
PAY_OPEN_RX = re.compile(r'^\s*window\.FULLBARS_PAY\s*=\s*\{\s*$')
PAY_CLOSE_RX = re.compile(r'^\s*\}\s*;?\s*$')

# A £ amount, as the site writes it (&pound;209 or £209, thousands with commas: £1,049).
NUM = r'(?:\d{1,3}(?:,\d{3})+(?!\d)|\d+)'
AMOUNT_RX = re.compile(r'(&pound;|£)(\s?)(' + NUM + r')')
HANDLE_RX = re.compile(r'href="(?:\.\./|/)?products/([a-z0-9-]+)\.html')
CARD_RX = re.compile(r'<article class="card"([^>]*)>(.*?)</article>', re.S)
ROW_RX = re.compile(r'<tr>(.*?)</tr>', re.S)
TILE_RX = re.compile(r'<a class="tile[^"]*" href="(?:\.\./|/)?collections/([^"]+)"[^>]*>(.*?)</a>', re.S)
COMPARE_RX = re.compile(r'cheapest|cheaper|costs? less|most affordable|lowest price we sell|price gap', re.I)


class SiteError(Exception):
    """Something about the site stops the tool before it writes anything."""


class InputError(Exception):
    """The command asked for something impossible (unknown phone, price breaks the order...)."""


class PartialWrite(Exception):
    """A disk error part-way through writing."""


def money(n):
    return f'{n:,}'


def amount(s):
    return int(s.replace(',', ''))


def text_of(fragment):
    t = re.sub(r'<[^>]+>', '', fragment)
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()


def norm(s):
    return re.sub(r'[\s_-]+', ' ', s.strip().lower())


def find_site():
    for start in (HERE, os.getcwd()):
        d = start
        while os.path.dirname(d) != d:
            if os.path.isfile(os.path.join(d, 'sites', 'full-bars', 'shop.html')):
                return os.path.join(d, 'sites', 'full-bars')
            d = os.path.dirname(d)
    raise SiteError('Could not find sites/full-bars from here. Give the folder: --check sites/full-bars')


# ----------------------------------------------------------------------------------------------- site files
class Site:
    def __init__(self, root):
        if not os.path.isdir(root):
            raise InputError(f'{root} is not a folder')
        self.root = os.path.realpath(root)
        if not (os.path.isfile(os.path.join(self.root, 'shop.html')) and os.path.isdir(os.path.join(self.root, 'products'))):
            raise InputError(f'{root} does not look like the Full Bars site (no shop.html and products/ folder)')
        self.overlay = {}

    def read(self, rel):
        if rel in self.overlay:
            return self.overlay[rel]
        with open(os.path.join(self.root, rel), encoding='utf-8', newline='') as f:
            return f.read()

    def exists(self, rel):
        return rel in self.overlay or os.path.isfile(os.path.join(self.root, rel))

    def html_files(self):
        out = []
        for d, dirs, files in os.walk(self.root):
            dirs.sort()
            for f in sorted(files):
                if f.endswith('.html'):
                    out.append(os.path.relpath(os.path.join(d, f), self.root).replace(os.sep, '/'))
        return out

    def product_files(self):
        d = os.path.join(self.root, 'products')
        return sorted('products/' + f for f in os.listdir(d) if f.endswith('.html'))

    def safe_target(self, rel):
        path = os.path.join(self.root, rel)
        if os.path.islink(path):
            raise SiteError(f'{rel} is a symlink; not writing through it')
        real = os.path.realpath(path)
        if not real.startswith(self.root + os.sep):
            raise SiteError(f'{rel} resolves outside {self.root}; not writing it')
        return real

    def write_all(self, new_files):
        """Write every file, each one atomically (temp file in the same folder, then rename)."""
        targets = {rel: self.safe_target(rel) for rel in new_files}   # check every target before writing any
        written = []
        for rel, text in new_files.items():
            path = targets[rel]
            tmp = None
            try:
                fd, tmp = tempfile.mkstemp(prefix='.set_prices-', suffix='.tmp', dir=os.path.dirname(path))
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                    f.write(text)
                os.chmod(tmp, os.stat(path).st_mode & 0o7777)
                os.replace(tmp, path)
                written.append(rel)
            except OSError as e:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
                raise PartialWrite(f'could not write {rel} ({e}). Already written: {", ".join(written) or "nothing"}. '
                                   f'Fix the cause and run --write on the folder again; it finishes the job.')


# ----------------------------------------------------------------------------------------------- products
def serialise_prices(prices):
    s = json.dumps(prices, separators=(',', ':'), ensure_ascii=False)
    return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def lowest(prices):
    """The lowest price and which storage/condition it is, picked exactly as site.js picks it
    (first strictly lowest, in the page's own order)."""
    best = None
    for st, row in prices.items():
        for gr, v in row.items():
            if best is None or v < best[0]:
                best = (v, st, gr)
    return best


def parse_product(rel, src):
    m = re.search(r'<form class="picker" id="picker"[^>]*>', src)
    if not m:
        raise SiteError(f'{rel}: no <form class="picker" id="picker"> found')
    tag, tag_start = m.group(0), m.start()
    am = re.search(r'\bdata-prices="([^"]*)"', tag)
    if not am:
        raise SiteError(f'{rel}: the picker has no data-prices')
    raw = am.group(1)
    try:
        prices = json.loads(html.unescape(raw))
    except ValueError as e:
        raise SiteError(f'{rel}: data-prices is not valid JSON ({e}). Fix the typo by hand first.')
    if not isinstance(prices, dict) or not prices or not all(isinstance(r, dict) and r for r in prices.values()):
        raise SiteError(f'{rel}: data-prices should look like {{"128GB": {{"Excellent": 249, ...}}, ...}}')
    for st, row in prices.items():
        for gr, v in row.items():
            if not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
                raise SiteError(f'{rel}: data-prices {st} {gr} is {v!r}; every price must be a whole number of pounds above 0')
    fm = re.search(r'<form class="picker" id="picker".*?</form>', src, re.S)
    form, form_start = fm.group(0), fm.start()

    def radios(name):
        return [html.unescape(v) for v in re.findall(r'<input type="radio" name="' + name + r'" value="([^"]*)"', form)]

    def checked(name):
        c = re.search(r'name="' + name + r'" value="([^"]+)" checked', form)
        return html.unescape(c.group(1)) if c else None

    storages, grades = radios('storage'), radios('grade')
    if list(prices) != storages:
        raise SiteError(f'{rel}: storage buttons {storages} don\'t match data-prices {list(prices)}')
    for st, row in prices.items():
        if list(row) != grades:
            raise SiteError(f'{rel}: data-prices {st} has conditions {list(row)}, the buttons are {grades}')
    st0, gr0, co0 = checked('storage'), checked('grade'), checked('colour')
    if not (st0 and gr0):
        raise SiteError(f'{rel}: no storage or condition is ticked by default, so the first-paint price is undefined')
    model = html.unescape(re.search(r'\bdata-model="([^"]*)"', tag).group(1)) if 'data-model=' in tag else rel
    brand = None
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S):
        try:
            j = json.loads(block)
        except ValueError:
            continue
        if isinstance(j, dict) and j.get('@type') == 'Product' and isinstance(j.get('brand'), dict):
            brand = j['brand'].get('name')
    return {
        'rel': rel, 'handle': rel[len('products/'):-len('.html')], 'model': model, 'brand': brand,
        'prices': prices, 'raw': raw, 'raw_span': (tag_start + am.start(1), tag_start + am.end(1)),
        'form_span': (form_start, form_start + len(form)),
        'storages': storages, 'grades': grades, 'st0': st0, 'gr0': gr0, 'co0': co0,
    }


def order_problems(p):
    """Better condition must never cost less than a worse one; more storage never less than less storage."""
    out, pr = [], p['prices']
    for st in p['storages']:
        vals = [pr[st][g] for g in p['grades']]
        if vals != sorted(vals, reverse=True):
            out.append(f"{p['model']} {st}: conditions {dict(zip(p['grades'], vals))} - a better condition costs less than a worse one")
    for g in p['grades']:
        col = [pr[st][g] for st in p['storages']]
        if col != sorted(col):
            out.append(f"{p['model']} {g}: storage prices {dict(zip(p['storages'], col))} - more storage costs less")
    return out


# ----------------------------------------------------------------------------------------------- edits
class Edits:
    """Edits to one file, all located in the original text, applied in one go."""

    def __init__(self, rel, text):
        self.rel, self.text, self.items = rel, text, []
        self.nl = [i for i, c in enumerate(text) if c == '\n']
        self.masked = []      # spans this tool manages, left out of the loose-amount review

    def line(self, pos):
        return bisect.bisect_left(self.nl, pos) + 1

    def add(self, start, end, new, what, old_show=None, new_show=None):
        old = self.text[start:end]
        if old == new:
            return False
        self.items.append((start, end, new, what,
                           old_show if old_show is not None else text_of(old),
                           new_show if new_show is not None else text_of(new)))
        return True

    def amounts(self, start, end, value, what):
        """Set every £ amount in text[start:end] to value. Returns (found_any, old_values)."""
        found, olds = False, []
        for m in AMOUNT_RX.finditer(self.text, start, end):
            found = True
            if self.add(m.start(3), m.end(3), money(value), what,
                        html.unescape(m.group(1)) + m.group(3), html.unescape(m.group(1)) + money(value)):
                olds.append(amount(m.group(3)))
        return found, olds

    def apply(self):
        items = sorted(self.items, key=lambda x: x[0])
        for a, b in zip(items, items[1:]):
            if a[1] > b[0]:
                raise RuntimeError(f'{self.rel}: overlapping edits at line {self.line(b[0])} ({a[3]} / {b[3]})')
        out, pos = [], 0
        for s, e, new, *_ in items:
            out.append(self.text[pos:s])
            out.append(new)
            pos = e
        out.append(self.text[pos:])
        return ''.join(out)


def pdfrom_text(p):
    """The #pdFrom line exactly as site.js writes it for the default options (with &pound; for the HTML)."""
    pr, st, gr = p['prices'], p['st0'], p['gr0']
    price = pr[st][gr]
    lo, lo_st, lo_gr = lowest(pr)
    esc = lambda s: html.escape(s, quote=False)
    if price == lo:
        return f'Price for {esc(st)} in {esc(gr)}: the lowest for this phone.'
    return (f'Price for {esc(st)} in {esc(gr)}. From &pound;{money(lo)}'
            + ('' if lo_st == st else f' for {esc(lo_st)}') + f' in {esc(lo_gr)}.')


# ----------------------------------------------------------------------------------------------- the plan
class Plan:
    def __init__(self):
        self.files = {}        # rel -> new text
        self.changes = []      # (rel, line, what, old, new)
        self.hand = []         # needs a person: the tool can't (or mustn't) do it
        self.review = []       # worth a look, not necessarily wrong
        self.products = {}
        self.old_values = {}   # amount that was replaced -> names of the phones it belonged to
        self.eds = []          # one Edits per page, for the reviews


def make_plan(site):
    plan = Plan()
    products = {}
    for rel in site.product_files():
        p = parse_product(rel, site.read(rel))
        products[p['handle']] = p
    plan.products = products
    lo = {h: lowest(p['prices'])[0] for h, p in products.items()}
    hi = {h: max(v for r in p['prices'].values() for v in r.values()) for h, p in products.items()}
    cheapest = min(lo.values())
    for p in products.values():
        for msg in order_problems(p):
            plan.hand.append(f"{p['rel']}: {msg}. Fix data-prices by hand.")

    def name(h):
        return products[h]['model'] if h in products else h

    # the from-prices as currently published (shop cards), for spotting a change in the price order
    published = {}
    if site.exists('shop.html'):
        for attrs, body in CARD_RX.findall(site.read('shop.html')):
            hs = set(HANDLE_RX.findall(body))
            df = re.search(r'\bdata-from="(\d+)"', attrs)
            if len(hs) == 1 and df:
                published[hs.pop()] = int(df.group(1))

    # collections: which phones each one lists (cards after <main>, as check_site_prices.py counts them)
    coll = {}
    for rel in site.html_files():
        if rel.startswith('collections/'):
            src = site.read(rel)
            i = src.find('<main')
            hs = []
            for _, body in CARD_RX.findall(src[i if i >= 0 else 0:]):
                found = set(HANDLE_RX.findall(body))
                if len(found) == 1:
                    hs.append(found.pop())
            known = [h for h in hs if h in lo]
            coll[rel[len('collections/'):]] = (len(hs), min((lo[h] for h in known), default=None), hs)

    badge_wrong = {}
    for rel in site.html_files():
        src = site.read(rel)
        ed = Edits(rel, src)
        masked = ed.masked
        scan_from = 0
        handle = rel[len('products/'):-len('.html')] if rel.startswith('products/') else None
        if handle in products:
            p = products[handle]
            product_page(ed, p, lo[handle], hi[handle], plan)
            i = src.find('<div class="pd-more">')
            scan_from = i if i >= 0 else p['form_span'][1]
            masked.append((0, scan_from))

        # product cards
        for m in CARD_RX.finditer(src, scan_from):
            masked.append(m.span())
            hs = set(HANDLE_RX.findall(m.group(2)))
            if len(hs) != 1:
                plan.review.append(f'{rel}:{ed.line(m.start())}: a card links to {len(hs)} phones {sorted(hs)}; its price was left alone')
                continue
            h = hs.pop()
            if h not in products:
                plan.hand.append(f'{rel}:{ed.line(m.start())}: a card links to products/{h}.html, which has no product page')
                continue
            df = re.search(r'\bdata-from="([^"]*)"', m.group(1))
            if df:
                s = m.start(1) + df.start(1)
                ed.add(s, s + len(df.group(1)), str(lo[h]), f'{name(h)} card: data-from (shop filter/sort)', df.group(1), str(lo[h]))
            else:
                plan.hand.append(f'{rel}:{ed.line(m.start())}: {name(h)} card has no data-from; add data-from="{lo[h]}"')
            cp = re.search(r'class="card-price">(.*?)</div>', m.group(2), re.S)
            if cp:
                found, olds = ed.amounts(m.start(2) + cp.start(1), m.start(2) + cp.end(1), lo[h], f'{name(h)} card: price')
                for o in olds:
                    plan.old_values.setdefault(o, set()).add(name(h))
            if not (cp and found):
                plan.hand.append(f'{rel}:{ed.line(m.start())}: {name(h)} card shows no "from £" price')
            if re.search(r'class="card-badge">\s*' + LOWEST_BADGE + r'\s*<', m.group(2), re.I) and lo[h] != cheapest:
                badge_wrong.setdefault(h, []).append(f'{rel}:{ed.line(m.start())}')

        # comparison-table rows: a priced row naming exactly one phone shows that phone's from-price
        for m in ROW_RX.finditer(src, scan_from):
            if not AMOUNT_RX.search(m.group(1)):
                continue
            masked.append(m.span())
            hs = set(HANDLE_RX.findall(m.group(1)))
            if len(hs) != 1:
                plan.review.append(f'{rel}:{ed.line(m.start())}: priced table row without exactly one phone link, left alone: {text_of(m.group(1))[:80]}')
                continue
            h = hs.pop()
            if h not in products:
                plan.hand.append(f'{rel}:{ed.line(m.start())}: a table row links to products/{h}.html, which has no product page')
                continue
            _, olds = ed.amounts(m.start(1), m.end(1), lo[h], f'{name(h)} table row: From')
            for o in olds:
                plan.old_values.setdefault(o, set()).add(name(h))

        # collection pages: "N models · from £X"
        if rel.startswith('collections/'):
            n, frm, hs = coll[rel[len('collections/'):]]
            rm = re.search(r'class="result-line"><span>(.*?)</span>', src, re.S)
            inner = rm and re.fullmatch(r'(\d+) models? &middot; from (&pound;|£)(' + NUM + ')', rm.group(1))
            if not inner:
                plan.hand.append(f'{rel}: no readable "N models · from £X" line')
            elif frm is not None:
                masked.append(rm.span())
                new = f"{n} model{'' if n == 1 else 's'} &middot; from {inner.group(2)}{money(frm)}"
                ed.add(rm.start(1), rm.end(1), new, '"N models · from" line')
            if rel == UNDER_FILE:
                under_flags(site, plan, ed, products, lo, hs)

        # tiles that repeat a collection's line (home page)
        for m in TILE_RX.finditer(src):
            cname, body = m.group(1), m.group(2)
            masked.append(m.span())
            if 'Under' in text_of(body) or not AMOUNT_RX.search(body):
                continue
            if cname not in coll or coll[cname][1] is None:
                plan.hand.append(f'{rel}:{ed.line(m.start())}: tile links to collections/{cname}, which has no phones or doesn\'t exist')
                continue
            n, frm, _ = coll[cname]
            ed.amounts(m.start(2), m.end(2), frm, f'tile for collections/{cname}: from')
            cm = re.search(r'<span>(\d+) models?\b', body)
            if cm:
                s = m.start(2) + cm.start(1)
                ed.add(s, m.start(2) + cm.end(0), f"{n} model{'' if n == 1 else 's'}", f'tile for collections/{cname}: count')

        if ed.items:
            plan.files[rel] = ed.apply()
            for s, e, new, what, old_show, new_show in sorted(ed.items, key=lambda x: x[0]):
                plan.changes.append((rel, ed.line(s), what, old_show, new_show))
        plan.eds.append(ed)

    for h, where in badge_wrong.items():
        low = sorted(name(k) for k in lo if lo[k] == cheapest)
        plan.hand.append(f'"{LOWEST_BADGE}" badge is on the {name(h)} card (from £{money(lo[h])}), but the cheapest phone is now '
                         f'{" / ".join(low)} at £{money(cheapest)}. Move or reword the badge by hand in: ' + ', '.join(where))

    quote_flags(site, plan, products)
    review_loose(plan)
    review_order(site, plan, products, published, lo)
    return plan


def product_page(ed, p, lo, hi, plan):
    src, pr, st0, gr0 = ed.text, p['prices'], p['st0'], p['gr0']
    price0 = pr[st0][gr0]

    def note(olds):
        for o in olds:
            plan.old_values.setdefault(o, set()).add(p['model'])

    m = re.search(r'<title>(.*?)</title>', src, re.S)
    hits = list(re.finditer(r'[Ff]rom\s+(&pound;|£)(\s?)(' + NUM + ')', m.group(1))) if m else []
    if not hits:
        plan.hand.append(f'{ed.rel}: <title> has no "from £X"; it should say "from £{money(lo)}"')
    for h in hits:
        s = m.start(1) + h.start(3)
        if ed.add(s, m.start(1) + h.end(3), money(lo), 'page title (from)', '£' + h.group(3), '£' + money(lo)):
            note([amount(h.group(3))])
    for label, rx, required in (('meta description', r'<meta name="description" content="([^"]*)"', True),
                                ('og:description', r'<meta property="og:description" content="([^"]*)"', True),
                                ('og:title', r'<meta property="og:title" content="([^"]*)"', True),
                                ('twitter:title', r'<meta name="twitter:title" content="([^"]*)"', False),
                                ('twitter:description', r'<meta name="twitter:description" content="([^"]*)"', False)):
        mm = re.search(rx, src)
        if not mm:
            continue
        found, olds = ed.amounts(mm.start(1), mm.end(1), lo, label + ' (from)')
        note(olds)
        if required and not found:
            plan.hand.append(f'{ed.rel}: {label} quotes no price; check_site_prices.py expects "From £{money(lo)}"')

    # structured data: AggregateOffer lowPrice/highPrice (or a single Offer's price)
    for bm in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', src, re.S):
        try:
            j = json.loads(bm.group(1))
        except ValueError:
            plan.hand.append(f'{ed.rel}:{ed.line(bm.start())}: a structured-data block is not valid JSON')
            continue
        if not (isinstance(j, dict) and j.get('@type') == 'Product'):
            continue
        off = j.get('offers')
        if not isinstance(off, dict):
            plan.hand.append(f'{ed.rel}: Product structured data has no single offers object; set prices there by hand')
            continue
        want = {'lowPrice': lo, 'highPrice': hi} if off.get('@type') == 'AggregateOffer' else {'price': lo}
        if off.get('@type') != 'AggregateOffer' and lo != hi:
            plan.hand.append(f'{ed.rel}: structured data uses a single Offer but prices run £{lo}-£{hi}; make it an AggregateOffer')
            continue
        for key, val in want.items():
            km = re.search(r'("' + key + r'"\s*:\s*)("?)(\d+(?:\.\d+)?)("?)', bm.group(1))
            if not km:
                plan.hand.append(f'{ed.rel}: structured data offers has no {key}; add "{key}":{val}')
                continue
            new = f'{val:.2f}' if '.' in km.group(3) else str(val)
            s = bm.start(1) + km.start(3)
            if ed.add(s, bm.start(1) + km.end(3), new, f'structured data {key}', km.group(3), new):
                note([int(float(km.group(3)))])

    # first paint, before site.js runs: must equal what site.js renders for the default options
    m = re.search(r'id="pdPrice"[^>]*>([^<]*)<', src)
    if m:
        found, olds = ed.amounts(m.start(1), m.end(1), price0, f'price shown before site.js (#pdPrice, {st0} {gr0})')
        note(olds)
        if not found:
            ed.add(m.start(1), m.end(1), f'&pound;{money(price0)}', f'price shown before site.js (#pdPrice, {st0} {gr0})')
    m = re.search(r'id="pdFrom"[^>]*>([^<]*)<', src)
    if m:
        ed.add(m.start(1), m.end(1), pdfrom_text(p), '"Price for ... From ..." line (#pdFrom)')
    f0, f1 = p['form_span']
    for name, fixed, label in (('storage', None, 'storage'), ('grade', None, 'condition')):
        for om in re.finditer(r'name="' + name + r'" value="([^"]+)"[^>]*><span>[^<]*<small>([^<]*)</small>', src[f0:f1]):
            opt = html.unescape(om.group(1))
            v = pr[opt][gr0] if name == 'storage' else pr[st0][opt]
            what = f'{label} button {opt} price'
            s, e = f0 + om.start(2), f0 + om.end(2)
            found, olds = ed.amounts(s, e, v, what)
            note(olds)
            if not found:
                ed.add(s, e, f'&pound;{money(v)}', what)
    m = re.search(r'id="selLine">(.*?)</p>', src, re.S)
    if m:
        found, olds = ed.amounts(m.start(1), m.end(1), price0, '"Selected: ..." line')
        note(olds)


def under_flags(site, plan, ed, products, lo, listed):
    want = {h for h in products if lo[h] < UNDER_LIMIT}
    have = set(listed)
    src = ed.text

    def lines_for(h):
        return sorted({ed.line(m.start()) for m in re.finditer(r'products/' + re.escape(h) + r'\.html', src)})

    def thead(s):
        m = re.search(r'<thead>(.*?)</thead>', s, re.S)
        return m and re.sub(r'\s+', '', m.group(1))

    def row_source(h):
        """A page whose comparison table has the same columns as this one and a row for h."""
        for rel in site.html_files():
            if rel == UNDER_FILE:
                continue
            s = site.read(rel)
            if thead(s) == thead(src) and re.search(r'<tr><td><a href="[^"]*products/' + re.escape(h) + r'\.html"', s):
                return rel
        return None

    def card_ids_clash(h):
        m = re.search(r'<article class="card"[^>]*><a href="products/' + re.escape(h) + r'\.html">.*?</article>', site.read('shop.html'), re.S)
        ids = set(re.findall(r"""\bid=['"]([^'"]+)['"]""", m.group(0))) if m else set()
        return sorted(ids & set(re.findall(r"""\bid=['"]([^'"]+)['"]""", src)))

    desc_lines = sorted({ed.line(m.start()) for m in re.finditer(r'<meta (?:name|property)="(?:og:)?description"', src)})
    for h in sorted(have - want, key=lambda k: lo.get(k, 0)):
        if h not in products:
            continue
        plan.hand.append(
            f'{UNDER_FILE}: {products[h]["model"]} now starts at £{money(lo[h])}, so it no longer belongs on "Under £300". '
            f'Remove its card, its "Side by side" table row and its structured-data list entry (renumber the positions), '
            f'and reword any sentence naming it: lines {", ".join(map(str, lines_for(h)))}; '
            f'also check the meta/og description (lines {", ".join(map(str, desc_lines))}).')
    for h in sorted(want - have, key=lambda k: lo[k]):
        src_row = row_source(h)
        clash = card_ids_clash(h)
        plan.hand.append(
            f'{UNDER_FILE}: {products[h]["model"]} now starts at £{money(lo[h])}, so it belongs on "Under £300" but isn\'t there. '
            f'Add its card (copy it from shop.html, changing products/ links to ../products/'
            + (f'; rename these SVG ids, which this page already uses: {", ".join(clash)}' if clash else '') + '), '
            + (f'a "Side by side" table row (copy it from {src_row}, which has the same columns), ' if src_row else
               'a "Side by side" table row (no page has one with the same columns: write it by hand), ')
            + f'a structured-data list entry, and consider the meta/og description (lines {", ".join(map(str, desc_lines))}) '
            f'and the prose. Then run this tool again to fill in its prices.')


def quote_flags(site, plan, products):
    if not os.path.isfile(os.path.join(site.root, 'quote.js')):
        return
    q = site.read('quote.js')
    for qid, sp in re.findall(r"\{ id: '([a-z0-9-]+)',[^}]*sellPrice: \{([^}]*)\}", q):
        for st, pence in re.findall(r"'([0-9]+(?:GB|TB))': (\d+)", sp):
            p = products.get(qid)
            vg = p and p['prices'].get(st, {}).get('Very Good')
            if vg is None:
                plan.hand.append(f'quote.js: trade-in model {qid} {st} has no matching shop price (Very Good) on products/{qid}.html')
            elif int(pence) != vg * 100:
                plan.hand.append(
                    f'quote.js: the trade-in quote for {p["model"]} {st} starts from a sell price of £{int(pence) / 100:g} '
                    f"(sellPrice '{st}': {pence}), but the shop's Very Good price is now £{money(vg)}. check_site_prices.py "
                    f'requires them to match, and this tool never edits quote.js, because changing it changes every trade-in '
                    f"offer for that phone. Either set '{st}': {vg * 100} in quote.js by hand (and in lib/pricing-config.ts in "
                    f'the phones-business repo, which it is copied from), or put the Very Good price back.')


def review_loose(plan):
    """A price this run changed that still appears somewhere this tool doesn't manage (prose, say)."""
    if not plan.old_values:
        return
    for ed in plan.eds:
        spans = ed.masked
        for m in AMOUNT_RX.finditer(ed.text):
            if any(a <= m.start() < b for a, b in spans):
                continue
            v = amount(m.group(3))
            if v in plan.old_values:
                plan.review.append(f'{ed.rel}:{ed.line(m.start())}: still says £{money(v)}, which was the price of '
                                   f'{" / ".join(sorted(plan.old_values[v]))} before this change: '
                                   f'"...{text_of(ed.text[max(0, m.start() - 80):m.end() + 30])[-110:]}"')


def review_order(site, plan, products, published, lo):
    """If the order of phones by from-price changed, list sentences that compare prices."""
    hs = [h for h in products if h in published]
    moved = set()
    sign = lambda x: (x > 0) - (x < 0)
    for i, a in enumerate(hs):
        for b in hs[i + 1:]:
            if sign(published[a] - published[b]) != sign(lo[a] - lo[b]):
                moved.update((a, b))
    if not moved:
        return
    names = {h: products[h]['model'] for h in moved}
    name_rx = re.compile('|'.join(r'\b' + re.escape(n) + r'\b(?!\s(?:mini|Pro|Plus|Max)\b)'
                                  for n in sorted(names.values(), key=len, reverse=True)))
    link_rx = re.compile(r'products/(' + '|'.join(map(re.escape, moved)) + r')\.html')
    plan.review.append('The order of phones by price changed for: ' + ', '.join(sorted(names.values()))
                       + '. Reread these sentences that compare prices:')
    for ed in plan.eds:
        own = ed.rel.startswith('products/') and ed.rel[len('products/'):-len('.html')] in moved
        for ln, line in enumerate(ed.text.split('\n'), 1):
            if not COMPARE_RX.search(line) or 'option value' in line or 'card-badge' in line:
                continue
            # one sentence at a time: it must compare prices and name a phone whose place in the order moved
            # (or sit on that phone's own page, where "it's cheaper" means that phone)
            for sentence in re.split(r'(?<=[.!?])\s+|(?<=>)(?=<(?:p|li|h\d|td|summary)\b)', line):
                plain = text_of(sentence)
                if not COMPARE_RX.search(plain) or plain.startswith('“From” is our lowest price'):
                    continue
                if own or link_rx.search(sentence) or name_rx.search(plain):
                    plan.review.append(f'    {ed.rel}:{ln}: "{plain[:170]}"')


# ----------------------------------------------------------------------------------------------- --set
def resolve(products, model, storage, grade, price):
    want = norm(model)
    hits = [p for p in products.values()
            if want in (norm(p['model']), norm(p['handle']), norm(f"{p['brand'] or ''} {p['model']}"))]
    if len(hits) != 1:
        names = ', '.join(f'"{p["model"]}"' for p in products.values())
        raise InputError(f'No phone called "{model}". Use one of: {names} (or the page name, e.g. iphone-13).')
    p = hits[0]
    st = next((s for s in p['storages'] if s.upper() == storage.replace(' ', '').upper()), None)
    if not st:
        raise InputError(f'{p["model"]} has no {storage} option. It has: {", ".join(p["storages"])}.')
    g = GRADE_ALIASES.get(norm(grade), grade)
    gr = next((x for x in p['grades'] if norm(x) == norm(g)), None)
    if not gr:
        raise InputError(f'{p["model"]} has no "{grade}" condition. It has: {", ".join(p["grades"])}.')
    ps = price.strip().lstrip('£').replace(',', '')
    if not re.fullmatch(r'\d+', ps):
        raise InputError(f'Price "{price}" must be a whole number of pounds, like 199 (no pence).')
    if int(ps) <= 0:
        raise InputError(f'Price "{price}" must be above £0.')
    if int(ps) > MAX_PRICE:
        raise InputError(f'Price "{price}" is more than £{money(MAX_PRICE)}, which no phone here costs. Check for a typo '
                         '(an extra 0, or pence typed without the point).')
    return p, st, gr, int(ps)


def apply_sets(site, sets):
    products = {}
    for rel in site.product_files():
        p = parse_product(rel, site.read(rel))
        products[p['handle']] = p
    done, touched, records, notes = [], {}, [], []
    cap = buy_now_cap(site)
    before = {h: {st: dict(row) for st, row in p['prices'].items()} for h, p in products.items()}
    for model, storage, grade, price in sets:
        p, st, gr, new = resolve(products, model, storage, grade, price)
        old = p['prices'][st][gr]
        p['prices'][st][gr] = new
        touched[p['handle']] = p
        done.append(f'{p["model"]} {st} {gr}: £{money(old)} -> £{money(new)}' + ('  (no change)' if old == new else ''))
        if old != new:
            records.append((p['rel'], f'data-prices {st} {gr} (the source)', f'£{money(old)}', f'£{money(new)}'))
        what = f'{p["model"]} {st} {gr} (£{money(new)})'
        if (old <= SD_COVER) != (new <= SD_COVER):
            notes.append(f'{what} is now {"above" if new > SD_COVER else "within"} Royal Mail Special Delivery\'s standard '
                         f'£{SD_COVER} cover: {"buy the higher cover band for it" if new > SD_COVER else "the standard cover is enough"} '
                         f'(GO-LIVE.md section 1, courier).')
        if cap and (old <= cap) != (new <= cap):
            notes.append(f'{what} is now {"above" if new > cap else "within"} the static site\'s Buy now cap '
                         f'(BUY_NOW_MAX £{cap} in site.js): {"it can only be ordered, not bought with a Payment Link" if new > cap else "a Payment Link for it would now be used"}.')
    problems = [m for p in touched.values() for m in order_problems(p)]
    if problems:
        raise InputError('Not changed, because the new prices would break the price order:\n  ' + '\n  '.join(problems)
                         + '\nChange the neighbouring price in the same command (repeat --set).')
    # A Payment Link in pay.js charges the price it was made with, whatever data-prices says now: every price this run
    # changes (old price before the first --set, new after the last) that has a link needs a new link, by hand.
    # A pay.js this tool can't read in full could hide a link from it, so that stops the run before anything is written.
    links, pay_problems = read_pay(site, products)
    if pay_problems:
        raise InputError(pay_unreadable(pay_problems, 'it can\'t tell whether a Payment Link charges a price this --set '
                                                      'changes'))
    hand = []
    for p in touched.values():
        for st, row in p['prices'].items():
            for gr, new in row.items():
                old = before[p['handle']][st][gr]
                if old != new and pay_key(p, st, gr) in links:
                    hand.append(pay_link_hand_edit(pay_key(p, st, gr), old, new, cap))
    for p in touched.values():
        src = site.read(p['rel'])
        a, b = p['raw_span']
        new_raw = serialise_prices(p['prices'])
        if serialise_prices(json.loads(html.unescape(p['raw']))) != p['raw']:
            done.append(f'(note: data-prices on {p["rel"]} was not in the usual compact form; it is rewritten compactly)')
        if new_raw != p['raw']:
            site.overlay[p['rel']] = src[:a] + new_raw + src[b:]
    line_of = {p['rel']: Edits(p['rel'], site.read(p['rel'])).line(p['raw_span'][0]) for p in touched.values()}
    return done, [(rel, line_of[rel], what, old, new) for rel, what, old, new in records], notes, hand


def buy_now_cap(site):
    try:
        m = re.search(r"BUY_NOW_MAX\s*=\s*Number\('(\d+)'\)", site.read('site.js'))
    except OSError:
        return None
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------------------------------------- pay.js
def pay_key(p, st, gr):
    """The pay.js key for one phone, storage and condition, built as site.js builds it:
    PAY[data-model + ' ' + storage + ' ' + condition], e.g. "iPhone 13 128GB Good"."""
    return f"{p['model']} {st} {gr}"


def pay_code_lines(src):
    """[(line number, line)] for every line of pay.js that isn't blank or wholly a comment (// ..., or inside or a whole
    /* ... */). A line with code and a comment on it counts as code, so it must match the layout read_pay() expects."""
    out, in_block = [], False
    for n, line in enumerate(src.split('\n'), 1):
        rest = line.strip()
        while rest or in_block:
            if in_block:
                j = rest.find('*/')
                if j < 0:
                    rest = ''
                    break
                rest, in_block = rest[j + 2:].strip(), False
            elif rest.startswith('//'):
                rest = ''
            elif rest.startswith('/*'):
                rest, in_block = rest[2:], True
            else:
                break
        if rest:
            out.append((n, line))
    return out


def read_pay(site, products):
    """({key: link} for every non-empty entry in pay.js, [problems]). This tool never writes pay.js.

    pay.js is JavaScript, and site.js uses any link it can read in it, however it is written. This tool only reads the
    layout pay.js ships with, so anything else is a problem rather than a link it might miss: outside comments, the
    file must be the line 'window.FULLBARS_PAY = {', then one entry per line ("<model> <storage> <condition>":
    "<link>", with nothing else on the line: no comment, no second entry, double quotes only), then '};'. And its keys
    must be exactly every model, storage and condition on the product pages, once each (check_site_prices.py's
    section 2). No pay.js at all: no links, no problem (site.js then has no Payment Links either)."""
    if not site.exists(PAY_FILE):
        return {}, []
    try:
        src = site.read(PAY_FILE)
    except (OSError, UnicodeDecodeError) as e:
        return {}, [f'{PAY_FILE} can\'t be read ({e})']
    links, keys, bad, stage = {}, [], [], 'before'
    for n, line in pay_code_lines(src):
        if stage == 'before' and PAY_OPEN_RX.match(line):
            stage = 'in'
            continue
        if stage == 'in':
            m = PAY_LINE_RX.match(line)
            if m:
                keys.append(m.group(1))
                if m.group(2).strip():
                    links[m.group(1)] = m.group(2).strip()
                continue
            if PAY_CLOSE_RX.match(line):
                stage = 'after'
                continue
        bad.append(f'line {n} can\'t be read: {line.strip()[:100]}')
    problems = [f'{PAY_FILE} ' + b for b in bad[:5]]
    if len(bad) > 5:
        problems.append(f'{PAY_FILE}: and {len(bad) - 5} more line(s) like that')
    if stage == 'before':
        problems.append(f'{PAY_FILE} has no line "window.FULLBARS_PAY = {{" on its own')
    elif stage == 'in':
        problems.append(f'{PAY_FILE} has no closing line "}};" after its entries')
    want = {pay_key(p, st, gr) for p in products.values() for st in p['storages'] for gr in p['grades']}
    dup = sorted({k for k in keys if keys.count(k) > 1})
    missing, extra = sorted(want - set(keys)), sorted(set(keys) - want)

    def few(xs):
        return ', '.join(xs[:5]) + (f' and {len(xs) - 5} more' if len(xs) > 5 else '')
    if dup:
        problems.append(f'{PAY_FILE} has the same key more than once (JavaScript uses the last): {few(dup)}')
    if missing and not bad:
        problems.append(f'{PAY_FILE} has no entry for {few(missing)}')
    if extra:
        problems.append(f'{PAY_FILE} has entries no product page offers: {few(extra)}')
    return links, problems


def pay_unreadable(problems, why):
    """The message for a pay.js read_pay() can't vouch for. Fails closed: a link it can't see is a link whose price
    it can't guard."""
    return (f'{PAY_FILE} isn\'t laid out the way this tool reads it, so {why}. Fix {PAY_FILE} first: one entry per line, '
            f'"iPhone 13 128GB Good": "https://buy.stripe.com/...", in double quotes, with no comment or second entry on '
            f'the line, and one entry for every phone, storage and condition on the product pages (as it ships).\n  '
            + '\n  '.join(problems))


def pay_link_hand_edit(key, old, new, cap):
    """NEEDS A HAND EDIT line for a price --set changed that has a Payment Link in pay.js. A Stripe price can't be
    changed after it's made, so the link still charges what it was made at: the site's old price, if Ash followed
    pay.js's rules. This tool can't see Stripe, so it says so rather than claiming to know."""
    head = (f'pay.js has a Payment Link for {key}; Stripe still charges £{money(old)} (the site\'s old price, which the '
            f'link was made at if made as pay.js says), not £{money(new)}: a Stripe price can\'t be changed. ')
    if cap and new > cap:
        return head + (f'At £{money(new)} it is above the £{money(cap)} Buy now cap (BUY_NOW_MAX in site.js), so the site '
                       f'no longer shows Buy now for it: deactivate the link in Stripe and clear it in pay.js.')
    return head + (f'Deactivate it in Stripe, make a new link at £{money(new)} with the same settings (payment limit 1, '
                   f'quantity fixed at 1), paste it into pay.js in place of the old one, then deploy and check its Buy now '
                   f'button opens Stripe at £{money(new)} (GO-LIVE.md section 6, step 1). This is listed whenever the entry '
                   f'isn\'t empty, so clear it first and paste the new link after this run (or add --allow-hand-edits).')


def pay_links_report(site, products, links, problems):
    """--check: every Payment Link in pay.js with the site's price for it now. Never a failure in itself: Stripe's price
    can't be read from here (Stripe's API refuses any request without an API key, which must never be in the repo).
    A pay.js read_pay() can't read in full is a failure, listed under NEEDS A HAND EDIT by main()."""
    caveat = ([f'\nPAYMENT LINKS IN {PAY_FILE}: can\'t all be listed, because this tool can\'t read {PAY_FILE} in full '
               '(see NEEDS A HAND EDIT). Only the entries it could read are below.'] if problems else [])
    if not links:
        return caveat or [f'\nPAYMENT LINKS IN {PAY_FILE}: none (every entry is empty).']
    cap = buy_now_cap(site)
    price = {pay_key(p, st, gr): v for p in products.values() for st, row in p['prices'].items() for gr, v in row.items()}
    out = caveat + [f'\nPAYMENT LINKS IN {PAY_FILE} ({len(links)}): this tool can\'t see what Stripe charges. Open each link and '
                    'check Stripe shows the site\'s price below, and in Stripe that the link has "Limit the number of '
                    'payments" set to 1 (one link per unit). A link at any other price: deactivate it in Stripe, make a '
                    'new one at the site\'s price with the same settings, and paste it in (GO-LIVE.md section 6, step 1).']
    for key, link in links.items():
        v = price.get(key)
        if v is None:
            out.append(f'  - {key}: no phone, storage and condition on the site has this name, so site.js never uses '
                       f'this link: deactivate it in Stripe and clear it ({link})')
        elif not link.startswith('https://'):
            out.append(f'  - {key}: site price £{money(v)}, but "{link}" is not an https:// link, so site.js ignores it')
        elif cap and v > cap:
            out.append(f'  - {key}: site price £{money(v)}, above the £{money(cap)} Buy now cap, so the site never shows '
                       f'this link: deactivate it in Stripe and clear it ({link})')
        else:
            out.append(f'  - {key}: site price £{money(v)}: {link}')
    return out


# ----------------------------------------------------------------------------------------------- checker
def run_checker(root):
    """Run check_site_prices.py on root. Returns (ok, summary_lines)."""
    if not os.path.isfile(CHECKER):
        return False, [f'check_site_prices.py not found next to this tool ({CHECKER}); could not run it']
    r = subprocess.run([sys.executable, CHECKER, '--site', root, '--quiet'], capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.startswith(('products:', 'FAIL', 'NOTE'))]
    if r.returncode not in (0, 1) or 'Traceback' in r.stderr:
        lines.append('check_site_prices.py crashed: ' + (r.stderr.strip().splitlines() or ['no output'])[-1])
        return False, lines
    return r.returncode == 0, lines


# ----------------------------------------------------------------------------------------------- report
def report(plan, wrote, dry):
    if plan.changes:
        files = sorted({c[0] for c in plan.changes})
        verb = 'Would change' if dry else ('Changed' if wrote else 'Out of date')
        print(f'\n{verb}: {len(plan.changes)} place(s) in {len(files)} file(s)')
        cur = None
        for rel, line, what, old, new in sorted(plan.changes, key=lambda c: (c[0], c[1])):
            if rel != cur:
                print(f'  {rel}')
                cur = rel
            print(f'    line {line:<4} {what}: {old}  ->  {new}')
    else:
        print('\nEvery derived price already matches data-prices.')
    if plan.hand:
        print(f'\nNEEDS A HAND EDIT ({len(plan.hand)}):')
        for m in plan.hand:
            print('  - ' + m)
    if plan.review:
        print(f'\nREVIEW (may be fine, worth reading):')
        for m in plan.review:
            print(m if m.startswith('    ') else '  - ' + m)


def rebuild_hint(root):
    """What to run next. For a folder other than sites/full-bars, the CSV commands name it with --site."""
    try:
        default = os.path.realpath(find_site())
    except SiteError:
        default = None
    if default == os.path.realpath(root):
        return ('Next: rebuild the Shopify CSV from the repo root:\n'
                '  python3 launch/full-bars/build_shopify_csv.py && python3 launch/full-bars/validate_shopify_csv.py')
    q = shlex.quote(root)
    return ('Next: rebuild the Shopify CSV from this folder (from the repo root):\n'
            f'  python3 launch/full-bars/build_shopify_csv.py --site {q} && '
            f'python3 launch/full-bars/validate_shopify_csv.py --site {q}\n'
            '  That replaces launch/full-bars/products-shopify.csv. If this folder is only a test copy, skip it and rebuild '
            'once the real site has the change.')


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='set_prices.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Full Bars prices: data-prices on each product page is the only place a price is typed; '
                    'this tool rewrites every other price on the site from it.',
        epilog='Examples (from the repo root):\n'
               '  python3 launch/full-bars/set_prices.py --check\n'
               '  python3 launch/full-bars/set_prices.py --set "iPhone 13" 128GB Good 199 sites/full-bars --dry-run\n'
               '  python3 launch/full-bars/set_prices.py --set "iPhone 13" 128GB Good 199 sites/full-bars\n'
               '  python3 launch/full-bars/set_prices.py --write sites/full-bars\n\n'
               'If a change needs a hand edit, --set and --write write nothing unless you add --allow-hand-edits.\n'
               'That includes a price --set changes that has a Stripe Payment Link in pay.js: the link keeps charging the\n'
               'price it was made with, so it needs a new link. --check lists every pay.js link with the site\'s price.\n'
               'pay.js must stay one entry per line, as it ships; otherwise --set and --write refuse (exit 2).\n'
               'Exit codes: 0 all good; 1 something needs you (stale prices, a hand edit, or check_site_prices.py '
               'fails); 2 bad command or input, nothing written.\n'
               'Then rebuild the Shopify CSV: build_shopify_csv.py and validate_shopify_csv.py.')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', nargs='?', const='', metavar='DIR',
                   help='check every derived price against data-prices and run check_site_prices.py; writes nothing '
                        '(DIR defaults to sites/full-bars)')
    g.add_argument('--write', metavar='DIR', help='rewrite every derived price in DIR from data-prices')
    g.add_argument('--set', nargs=5, action='append', metavar=('MODEL', 'STORAGE', 'GRADE', 'PRICE', 'DIR'),
                   help='change one price in data-prices, then do --write; repeat for several prices (same DIR)')
    ap.add_argument('--dry-run', action='store_true', help='with --write or --set: show what would change, write nothing')
    ap.add_argument('--allow-hand-edits', action='store_true',
                    help='with --write or --set: write even though something needs a hand edit (by default it refuses and '
                         'writes nothing, so the site never goes out half-done)')
    args = ap.parse_args(argv)
    if args.check is not None and (args.dry_run or args.allow_hand_edits):
        ap.error(f'{"--dry-run" if args.dry_run else "--allow-hand-edits"} does nothing with --check, which never writes')

    try:
        if args.check is not None:
            root = args.check or find_site()
        elif args.write:
            root = args.write
        else:
            dirs = {os.path.realpath(s[4]) for s in args.set}
            if len(dirs) != 1:
                raise InputError('Every --set must name the same folder')
            root = args.set[0][4]
        site = Site(root)
        print(f'Full Bars prices: {site.root}')
        done, set_changes, notes, set_hand = apply_sets(site, [s[:4] for s in args.set]) if args.set else ([], [], [], [])
        for d in done:
            print('Set ' + d)
        plan = make_plan(site)
        plan.review[:0] = notes
        plan.hand[:0] = set_hand
        links, pay_problems = read_pay(site, plan.products)
        if pay_problems and args.write:
            raise InputError(pay_unreadable(pay_problems, 'it can\'t tell whether a price you changed by hand in '
                                                          'data-prices has a Payment Link'))
        if pay_problems:            # --check: a failure to fix by hand (--set stopped in apply_sets)
            plan.hand.append(pay_unreadable(pay_problems, 'set_prices.py --set can\'t tell whether a Payment Link charges '
                                                          'a price it changes').replace('\n  ', ' ', 1).replace('\n  ', '; '))
        nlinks = len(links) if args.write else 0
        if nlinks:
            plan.review.append(f'{PAY_FILE} has {nlinks} Payment Link(s), and a Payment Link keeps charging '
                               'the price it was made with. If you changed a price by hand in data-prices, this tool can\'t '
                               'tell which: run --check to list every link with the site\'s price for it now, and replace '
                               'any whose price changed (GO-LIVE.md section 6, step 1). --set names them for you.')
        nprices = sum(len(r) for p in plan.products.values() for r in p['prices'].values())
        print(f'{len(plan.products)} phones, {nprices} prices.')
    except InputError as e:
        print(f'ERROR: {e}\nNothing was written.', file=sys.stderr)
        return 2
    except SiteError as e:
        print(f'ERROR: {e}\nNothing was written.', file=sys.stderr)
        return 1

    new_files = dict(plan.files)
    for rel, text in site.overlay.items():          # the product page(s) --set changed but nothing else did
        new_files.setdefault(rel, text)
    plan.changes.extend(set_changes)

    if args.check is not None:
        report(plan, wrote=False, dry=False)
        print('\n'.join(pay_links_report(site, plan.products, links, pay_problems)))
        ok, lines = run_checker(site.root)
        print('\ncheck_site_prices.py: ' + ('\n  '.join(lines) if lines else 'no output'))
        stale = bool(plan.files)
        if stale:
            me = os.path.relpath(os.path.abspath(__file__))
            me = me if not me.startswith('..') else os.path.abspath(__file__)
            print(f'\n{len(plan.changes)} derived price(s) out of date. Fix: python3 {me} --write {root}')
        good = ok and not stale and not plan.hand
        print('\nRESULT: ' + ('PASS' if good else 'FAIL'))
        return 0 if good else 1

    if args.dry_run:
        report(plan, wrote=False, dry=True)
        print('\nDry run: nothing written, check_site_prices.py not run.')
        if plan.hand:
            print('A real run would refuse and write nothing until the hand edit is done (or you add --allow-hand-edits).')
        print('RESULT: ' + ('would need a hand edit' if plan.hand else 'OK to write'))
        return 1 if plan.hand else 0

    if plan.hand and not args.allow_hand_edits:
        report(plan, wrote=False, dry=True)
        print('\nNothing written: the change above needs a hand edit, and writing the rest now would leave the site '
              'half-done (a wrong badge or "Under £300" page, say). Either make the hand edit first and run this again, '
              'or add --allow-hand-edits to write everything else now and then make the hand edit before you publish.')
        if any(m.startswith(f'{PAY_FILE} has a Payment Link') for m in plan.hand):
            print(f'For a Payment Link, the edit to make first is: deactivate it in Stripe and clear its entry in {PAY_FILE}. '
                  'Then run this again, make the new link at the new price, paste it in and deploy.')
        print('\nRESULT: NEEDS YOU (nothing written)')
        return 1

    try:
        site.write_all(new_files)
    except SiteError as e:
        print(f'ERROR: {e}\nNothing was written.', file=sys.stderr)
        return 1
    except PartialWrite as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1
    report(plan, wrote=True, dry=False)
    print(f'\nWrote {len(new_files)} file(s).' if new_files else '\nNo files needed changing.')
    ok, lines = run_checker(site.root)
    print('\ncheck_site_prices.py: ' + ('\n  '.join(lines) if lines else 'no output'))
    if new_files:
        print('\n' + rebuild_hint(site.root))
    good = ok and not plan.hand
    print('\nRESULT: ' + ('OK' if good else 'NEEDS YOU (see above)'))
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
