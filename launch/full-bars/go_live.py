#!/usr/bin/env python3
"""Full Bars launch-day switch: turns the preview site into the live site in one go.

What it does, in plain English (for Ash)
----------------------------------------
The site in sites/full-bars is a preview: search engines are blocked, every page has a "not trading yet"
banner, and the Order buttons, contact form and trade-in tool are switched off. Doing that by hand on launch
day means editing 56 pages. This script does the mechanical part for you, and refuses to run while anything
would make launching a mistake.

It switches, on every page that has them:
  - robots.txt: "Disallow: /" becomes "Allow: /" and the preview comments go
  - <meta name="robots" content="noindex"> becomes index,follow (404.html keeps noindex on purpose)
  - the yellow "Preview: Full Bars isn't trading yet" banner is removed
  - data-preview="1" is removed from the 19 product pickers and the contact form (and from the 7 trade-in
    quote tools if you pass --trade-ins open)
  - the dead "Opening soon" span on each product page becomes a real Order link: to the contact page with
    --checkout stripe (email order, or Buy now where pay.js has a Payment Link), or to the phone's Shopify product
    with --checkout shopify (reading "Choose and pay on the next page", with the note under it shown, unless there is
    a variant ID for the phone ticked in the page's HTML: without JavaScript that's the phone a visitor orders)
  - --checkout shopify --shop-url https://SHOP: each product picker gets data-shop="https://SHOP/products/<handle>",
    where <handle> is the page's name and must be a URL handle in products-shopify.csv. site.js then sends the
    Order button there and never builds an email order or a Payment Link, so one phone can't be sold twice
  - --checkout shopify --shop-variants FILE (from fetch_shopify_variants.py): each product picker gets data-variants,
    the Shopify variant ID of every storage, condition and colour, so site.js opens Shopify on exactly the phone chosen
    (?variant=ID). A choice with no ID reads "Choose and pay on the next page" instead of a price
  - the "Not trading yet" boxes on terms, privacy, cookies, warranty, delivery-returns and contact go
  - --checkout stripe: the contact form gets its "Order a phone" topic (site.js looks for it). --checkout shopify:
    it doesn't (and an existing one is removed), so there is no email-order route beside Shopify
  - --checkout stripe: data-stock-required="1" goes on each product picker and on each grid of product cards and row of
    range tiles. There site.js fails closed: if stock.js is missing, has a typo that stops browsers reading it, or has a
    missing or malformed entry for a phone, that phone shows as not in stock ("Not in stock — ask us", "None in stock
    right now"), never as orderable. --checkout shopify takes the mark off again (stock.js is optional there)
  - "Last updated ..." on the legal pages and every <lastmod> in sitemap.xml become the launch date. Only in
    the run that switches the site out of preview, or when you pass --launch-date: rerunning on a site that is
    already live leaves those dates alone, because nothing on those pages changed
  - every https://www.fullbars.co.uk link and hello@fullbars.co.uk address follows --domain
  - your --rewrites (below): the preview wording, in every place it appears

It will NOT run (exit code 1, nothing written) while any of these launch blockers remain:
  - a [placeholder] in square brackets on any page (the "leave these alone" ones in GO-LIVE.md section 3,
    such as the customer's [date] in the cancellation form, are allowed)
  - a price problem found by check_site_prices.py, or by set_prices.py --check (which also catches a stale
    "Price for ... From" line and a "Lowest price" badge on a phone that is no longer the cheapest)
  - a handset spec that disagrees with facts.json (check_site_facts.py)
  - checkout not chosen, or the site not matching it: --checkout stripe needs at least one https Payment
    Link in pay.js and no data-shop on any product page; --checkout shopify needs pay.js empty, --shop-url, and a
    Shopify product (a URL handle in products-shopify.csv) for every product page, or you'd sell the same phone
    twice or have an Order button with nowhere to go
  - stock that site.js can't use, in stock.js (the one place to keep it: {"<handle>": {"storage|condition": units}})
    or in a page's older data-stock attribute: not valid JSON, a count that isn't a whole number of 0 or more, a key
    that isn't one of that page's "storage|condition" pairs (colour is never part of the key), or a handle that isn't
    a product page; on both routes. stock.js is read as a browser reads it, so a stray comma, a missing brace or a stray
    character outside its comment, which make browsers ignore the whole file, is a blocker too. With --checkout stripe,
    also a product page with no stock data from either (the page would show that phone as not in stock), a phone whose
    stock is only in its page's data-stock (its cards would say "None in stock right now"), no stock.js at all, or a
    page with a picker, cards or range tiles that doesn't load stock.js. On the Shopify route stock data is
    optional: stock.js is then a snapshot written from Shopify by fetch_shopify_variants.py --write-stock (a hand-kept,
    partial or other-store one, or a stale one: more than 24 hours old, or with no time on it, is a warning). stock.js
    wins over data-stock. After launch, set_prices.py --check runs the same stock check on the route the site is on:
    run it after every edit to stock.js and before every deploy
  - --shop-variants with a key that isn't one of that page's storage, condition and colour options, or an ID that
    isn't a whole number
  - --trade-ins open while the sell pages have no quote-sending form
  - preview wording ("Preview prices: we're not taking orders yet", "When we open ...") that would still be
    on the live pages. It is future-tense, so it can't be switched mechanically: you write the new wording
    once in a --rewrites file and the script puts it on every page. Trade-in wording that stays true while
    trade-ins are closed is listed separately and doesn't block.
  - checkout wording that doesn't fit the checkout you chose: "our intended payment provider" (terms section 4) on
    either route; with --checkout shopify also every sentence about Stripe, Buy now, payment links or ordering by
    email (terms section 3 on how the contract is made, the FAQ's "How do I pay?" ...), any "ask when you order"
    promise (on Shopify, ordering is paying), and any claim that customers can't see their order on the website
    (Shopify shows it on its order status page). With --checkout stripe
    and a Payment Link in pay.js, also any promise to confirm or send something "before you pay", or to answer "when
    you order", that isn't limited to email orders: Buy now takes payment first. Rewrite them in the same --rewrites
    file. A sentence that is still true can be kept: give it its own text as the new wording. Not listed: your own new
    wording from --rewrites (your decision: it is shown in the report, never blocks), and on the Shopify route a
    sentence's email-order words when it says replaced-part phones are sold by email order (GO-LIVE.md section 4 keeps
    that true on Shopify; a "Buy now" in the same sentence is still listed).
  To switch anyway and fix the preview or checkout wording by hand afterwards, pass --allow-preview-wording: the
  run then ends "NOT READY TO GO LIVE" with exit code 3, and you must not deploy the site to your web host until the
  wording is done.

How to use it
-------------
Always run it on a copy of the site folder or on a git branch (GO-LIVE.md section 7 says how the switched
copy goes on your web host as the live site), never on your only copy.

  1. See what it would change and what is still blocking launch. Changes nothing:
       python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout stripe --dry-run \\
           --out ~/go-live-report.txt --rewrites-template ~/rewrites.json
     (Shopify instead: --checkout shopify --shop-url https://your-shop.example, your store's own address.)
  2. Just the blockers:
       python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout stripe --check-only
  3. Fill in ~/rewrites.json (below), fix the other blockers, dry-run again with --rewrites ~/rewrites.json
     until it says "No blockers", then do it for real (edits COPY in place):
       python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout stripe \\
           --rewrites ~/rewrites.json --out ~/go-live-report.txt
  4. Do the items listed under STILL TO DO BY HAND, deploy the switched folder to your web host (GO-LIVE.md section 7;
     the claude.ai artifact stays a preview copy), and put one real order through.

The --rewrites file:
  --rewrites-template FILE writes every preview or checkout sentence still on the pages, one per key, each null.
  Each key is one sentence as a customer reads it (&rsquo; and the like already turned into ’). Replace each
  null with your new wording in plain text, or "" to delete the sentence. Then pass the file with --rewrites:
  each sentence is replaced wherever it appears, in the page text, in meta descriptions and in the structured
  data (FAQ answers), with quotes and & made safe for each place. Plain text only: < and > are refused, so
  links and bold stay as they are on the page. A checkout sentence that is still true for your checkout can be
  kept by giving it its own text as the new wording (preview wording can't be kept). If one of your sentences sits inside a longer one of yours at
  the same place, the longer one wins there; two that partly overlap are refused, and every clash is listed.
  A sentence left null is skipped, and blocks the switch if it is preview wording.

Options: --launch-date YYYY-MM-DD (default today) sets the "Last updated" and sitemap dates.
--shop-url https://SHOP (with --checkout shopify only): your Shopify store's own address, not a /products/ page (the
script adds /products/<handle> itself); --shopify-csv FILE reads the
URL handles from FILE instead of products-shopify.csv in this folder.
--shop-variants FILE (with --checkout shopify only): Shopify variant IDs, as fetch_shopify_variants.py writes them.
--trade-ins closed (the default) keeps the trade-in quote tool in guide-price mode; --trade-ins open switches it on.
--no-www uses https://fullbars.co.uk/ instead of https://www.fullbars.co.uk/ for page addresses.

Exit codes: 0 = done and ready to deploy to your web host (with --dry-run or --check-only: no blockers);
1 = blockers, nothing written (or, after writing, a re-check failed: the report says so, don't deploy);
2 = bad arguments; 3 = switched (or would switch), but NOT READY TO GO LIVE: preview or checkout wording is still
on the pages because you passed --allow-preview-wording.
"Deploy" always means putting the switched folder on your own web host (GO-LIVE.md section 7). The claude.ai artifact
stays a preview copy: never publish the switched folder there.
The script writes only inside --site, plus the --out report and the --rewrites-template file you name (both
must be outside --site, so they never go up with the site). Python 3 standard library only.
"""
import argparse
import bisect
import collections
import csv
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_CHECKER = os.path.join(HERE, 'check_site_prices.py')
SET_PRICES = os.path.join(HERE, 'set_prices.py')
FACTS_CHECKER = os.path.join(HERE, 'check_site_facts.py')

TEXT_EXT = ('.html', '.js', '.css', '.txt', '.xml', '.json', '.svg', '.webmanifest')   # read, and domain-rewritten
SCAN_EXT = ('.html', '.js', '.css', '.txt', '.xml')                                       # scanned for preview wording

# GO-LIVE.md section 7's grep, plus preview phrasings it misses ("not taking payments yet", "until then" ...)
GOLIVE_GREP = r'preview|when we open|once we open|open soon|opening soon|not trading|trading yet'
_APOS = r"(?:&rsquo;|’|')"
SHOP_WORDS = re.compile(
    GOLIVE_GREP + r'|not taking (?:orders|payments|messages)'
    r'|not (?:buying|selling|sending|accepting)\b[^.<]{0,60}?\byet\b'
    r'|isn' + _APOS + r't (?:selling|sending)\b[^.<]{0,80}?\byet\b'
    r'|can' + _APOS + r't take orders|goes live when|until then', re.I)
# Trade-in wording that is true while trade-ins stay closed, and wrong once they open
TRADE_WORDS = re.compile(r'trade-ins open|trade-ins aren|guide price|guide figure|expect to pay', re.I)
# A sentence that is explicitly about trade-ins: on a sell page, preview wording like this stays true while trade-ins
# are closed. ("When we open, we'll quote ..." is not: once the shop is live, "when we open" reads as wrong.)
TRADE_CONTEXT = re.compile(r'\btrade-?ins?\b|buying phones|guide (?:price|figure)|expect to pay', re.I)

# Same pattern as GO-LIVE.md section 3's placeholder grep (no ] < > " = inside the brackets)
PLACEHOLDER = re.compile(r'\[[^\]<>"=\n]+\]')
# GO-LIVE.md section 3 "Leave these alone": (file, placeholder, the context it must sit in)
LEAVE_ALONE = (
    ('delivery-returns.html', '[phone, storage, grade, colour]', r'I hereby give notice.*?</div>'),
    ('delivery-returns.html', '[date]', r'I hereby give notice.*?</div>'),
    ('delivery-returns.html', '[your name]', r'I hereby give notice.*?</div>'),
    ('delivery-returns.html', '[your address]', r'I hereby give notice.*?</div>'),
    ('guides/remove-find-my-before-selling-iphone.html', '[your name]', r'Settings (?:&gt;|>) \[your name\]'),
)

# Script text that only ever runs while data-preview is on, so it never shows on the live site
PREVIEW_ONLY_JS = (
    ('site.js', 'Opening soon'),
    ('site.js', 'Full Bars isn’t trading yet, so questions can’t be sent'),
    ('site.js', 'Nothing has been sent. Full Bars isn’t trading yet'),
    ('quote-ui.js', 'Guide price only: trade-ins open soon.'),
)
# What quote-ui.js needs on a sell page before trade-in quotes can be sent
QT_SEND_IDS = ('qtSend', 'qtName', 'qtNotes', 'qtOwner', 'qtStatus')
PICKER_TAG = re.compile(r'<form class="picker" id="picker"[^>]*>')   # as in check_site_prices.py
NO_INDEX_KEEP = ('404.html',)   # an error page should never be indexed
# The static route's stock: one file, {handle: {"storage|condition": units}}, read by site.js as window.FULLBARS_STOCK
STOCK_JS = 'stock.js'
SCRIPT_SRC = re.compile(r'<script\b[^>]*\bsrc="(?:\.\./)*(stock|site)\.js"')

# --checkout shopify: where each product page's Order button goes. The URL handles come from the Shopify CSV
# (build_shopify_csv.py names each product after its page, so products/iphone-13.html is handle iphone-13).
SHOPIFY_CSV = os.path.join(HERE, 'products-shopify.csv')
# https, a host name, an optional port and path (Shopify Markets can add one, such as /en-gb); no query or fragment
SHOP_URL = re.compile(r'https://(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d{1,5})?(?:/[A-Za-z0-9._~%-]+)*')
# Wording about ordering and paying that has to match the checkout you chose. "Our intended payment provider" is
# wrong at launch on either route. On the Shopify route, every sentence about Stripe, Buy now, payment links or
# ordering by email has to be rewritten or confirmed (terms section 3 on how the contract is made, the FAQ's
# "How do I pay?" answer, the contact form's order prompt ...), plus any promise to do something "when you order"
# before payment (the FAQ's photos and battery answers: on Shopify, ordering and paying are one checkout step), and
# these sentences, which name none of them:
SHOPIFY_SENTENCES = (
    'In both cases the contract is made when we email to confirm your order has been accepted.',   # terms section 3
    'For orders: the phone, storage, grade and colour, your delivery address and a phone number for the courier.',
)
_CHECKOUT_BOTH = r'\bintended payment provider\b'
# A claim that customers can't see their order online: true for an email order or a Payment Link, but Shopify shows every
# order on its order status page (and in the customer's account), so on that route it is checkout wording
_NOT_ONLINE = r'\bcan(?:not|' + _APOS + r't) (?:view|see)\b[^.;<]{0,60}?\bon (?:our|this) (?:web)?site\b'
# A promise to confirm or send something before payment, or to answer "when you order": true for an email order (you
# order, we reply, then you pay) but not for a Buy now link or Shopify checkout, where ordering is paying. On the static
# route it is checkout wording as soon as pay.js has a Payment Link, unless the sentence limits it to email orders.
_PAY_FIRST = (r'\bconfirm(?:ed|s)?\b[^.;<]{0,60}?\bbefore you pay\b|\bsend\b[^.;<]{0,60}?\bbefore you pay\b'
              r'|\bask when you order\b')
EMAIL_ORDER_ONLY = re.compile(r'\bemail orders?\b|\border(?:s|ing)? (?:it )?by email\b|\bby email order\b', re.I)
# A sentence about phones with a replaced part. GO-LIVE.md section 4 keeps those units off Shopify (stock 0) and sells them
# by email order (a Shopify draft order sent as an invoice), so on the Shopify route "replaced-part phones are sold by
# email order" stays true, and only the email-order words in such a sentence are exempt (a "Buy now" beside them is not)
REPLACED_PART = re.compile(r'\breplaced parts?\b|\bparts? (?:has|have) been replaced\b', re.I)
# privacy.html's quote-tool sentence, which must end up saying what cookies.html says (answers kept for this tab only)
PRIVACY_QUOTE_TOOL = 'The quote tool works in your browser.'
CHECKOUT_WORDS = {
    'stripe': re.compile(_CHECKOUT_BOTH, re.I),
    # --checkout stripe with at least one Payment Link in pay.js (Buy now takes payment first)
    'stripe-buy-now': re.compile(_CHECKOUT_BOTH + '|' + _PAY_FIRST, re.I),
    'shopify': re.compile(_CHECKOUT_BOTH + r'|\bstripe\b|\bbuy now\b(?!,?\s*pay later)|\bpayment links?\b'
                          r'|\border(?:s|ing)? (?:it )?by email\b|\bemail orders?\b|\bsend us an order\b|'
                          + _PAY_FIRST + '|' + _NOT_ONLINE + '|' + '|'.join(re.escape(s) for s in SHOPIFY_SENTENCES), re.I),
}
# Script text that only runs when pay.js has a Payment Link, so never on a Shopify-route page
STRIPE_ONLY_JS = (('site.js', 'Buy now — '),)
# Shown only beside a Buy now link: hidden on every Shopify-route page
STRIPE_ONLY_HTML = re.compile(r'<p\b[^>]*\bid="buyNote"[^>]*>.*?</p>', re.S)


class Fail(Exception):
    """A problem that stops the run (bad input, unexpected site structure)."""


# ----------------------------------------------------------------------------------------------- reading
def load_site(root):
    """Every text file under root, as {relative/path: text}. Symlinks and dot-folders are skipped."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('.') and not os.path.islink(os.path.join(dirpath, d)))
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            if f.startswith('.') or os.path.islink(p) or not f.lower().endswith(TEXT_EXT):
                continue
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            try:
                with open(p, encoding='utf-8', newline='') as fh:
                    files[rel] = fh.read()
            except UnicodeDecodeError:
                raise Fail(f'{rel} is not UTF-8 text')
    return files


def attr(tag, name):
    m = re.search(r'(?<![\w-])' + re.escape(name) + r'="([^"]*)"', tag)
    return html.unescape(m.group(1)) if m else None


def line_of(src, pos):
    return src.count('\n', 0, pos) + 1


def element_end(src, start, tag='div'):
    """Index just past the </tag> closing the element whose start tag begins at start, or -1."""
    depth = 0
    for m in re.finditer(r'<(/?)' + tag + r'\b[^>]*>', src[start:], re.I):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start + m.end()
    return -1


def closing(rel, src, start):
    end = element_end(src, start)
    if end < 0:
        raise Fail(f'{rel}:{line_of(src, start)}: <div> with no closing </div>, so it can\'t be removed safely')
    return end


def widen_to_line(src, s, e):
    """If src[s:e] is alone on its line(s), widen it to take the whole line and its newline."""
    ls = src.rfind('\n', 0, s) + 1
    le = src.find('\n', e)
    le = len(src) if le < 0 else le
    if not src[ls:s].strip() and not src[e:le].strip():
        return ls, min(le + 1, len(src))
    return s, e


def pickers(files):
    """(rel, picker start tag, its position) for each product page's #picker form."""
    out = []
    for rel in sorted(files):
        if rel.startswith('products/') and rel.endswith('.html'):
            m = PICKER_TAG.search(files[rel])
            if m:
                out.append((rel, m.group(0), m.start()))
    return out


def robots_rules(text):
    """(line_start, line, field, value, agents) for each Allow/Disallow line of robots.txt, with the user-agents it applies to."""
    out, agents, in_rules, pos = [], [], False, 0
    for line in text.splitlines(True):
        body = line.split('#', 1)[0].strip()
        field, _, value = body.partition(':')
        field, value = field.strip().lower(), value.strip()
        if field == 'user-agent':
            if in_rules:
                agents, in_rules = [], False
            agents.append(value)
        elif field in ('allow', 'disallow'):
            in_rules = True
            out.append((pos, line, field, value, tuple(agents)))
        pos += len(line)
    return out


def robots_blocks_all(text):
    """True if robots.txt tells every crawler (User-agent: *) to keep out of the whole site."""
    return any(f == 'disallow' and v == '/' and '*' in a for _, _, f, v, a in robots_rules(text))


def pay_links(src):
    """[(key, link)] from pay.js, as check_site_prices.py reads its keys."""
    body = src[src.index('window.FULLBARS_PAY'):] if 'window.FULLBARS_PAY' in src else ''
    return re.findall(r'^\s*"([^"]+)":\s*"([^"]*)",?\s*$', body, re.M)


def pay_prices(files):
    """{pay.js key: the site's price} for every storage and condition on every product page's #picker, keyed as
    site.js looks a Payment Link up: data-model + ' ' + storage + ' ' + condition ("iPhone 13 128GB Good")."""
    prices = {}
    for rel, tag, _ in pickers(files):
        try:
            for st, g in json.loads(attr(tag, 'data-prices') or '{}').items():
                for gr, p in g.items():
                    prices[f'{attr(tag, "data-model")} {st} {gr}'] = p
        except (ValueError, AttributeError):
            pass   # check_site_prices.py reports this
    return prices


def gbp(v):
    return f'£{v:,}' if isinstance(v, int) and not isinstance(v, bool) else f'£{v}'


def page_handle(rel):
    """products/iphone-13.html -> iphone-13: the Shopify URL handle build_shopify_csv.py gives that page's product."""
    return rel.rsplit('/', 1)[-1][:-len('.html')]


def parse_shop_url(value):
    """--shop-url as https://host[/path], without a trailing slash; Fail if it isn't one."""
    v = value.strip().rstrip('/')
    m = re.match(r'(?i)(https://)([^/]+)(.*)$', v)
    if m:
        v = m.group(1).lower() + m.group(2).lower() + m.group(3)
    if not SHOP_URL.fullmatch(v):
        raise Fail(f'--shop-url {value!r} is not an https:// address like https://your-shop.example (your Shopify '
                   'store\'s own address, with no ? or #)')
    if any(seg.lower() in ('products', 'collections', 'cart', 'checkout', 'checkouts') for seg in m.group(3).split('/')):
        raise Fail(f'--shop-url {value!r} is a page inside your store, not its address. Give just the store\'s own address '
                   '(such as https://your-shop.example): this script adds /products/<handle> for each phone itself')
    return v


def csv_handles(path):
    """(set of URL handles in a Shopify product CSV, None) or (None, why it can't be read)."""
    try:
        with open(path, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.reader(fh))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        return None, f'can\'t read {path} ({e})'
    head = rows[0] if rows else []
    col = 'URL handle' if 'URL handle' in head else 'Handle' if 'Handle' in head else None
    if col is None:
        return None, f'{path} has no "URL handle" (or "Handle") column'
    i = head.index(col)
    return {r[i].strip() for r in rows[1:] if len(r) > i and r[i].strip()}, None


def shop_targets(files, opt):
    """--checkout shopify: ({product page: its Shopify product address}, blockers, warnings). Every product page needs
    a product with the same URL handle in the Shopify CSV, or its Order button would have nowhere to go."""
    if getattr(opt, 'checkout', None) != 'shopify' or not getattr(opt, 'shop_url', None):
        return {}, [], []
    handles, err = csv_handles(opt.shopify_csv)
    if err:
        return {}, [f'--checkout shopify: {err}, so the Order buttons can\'t be matched to Shopify products'], []
    targets, blockers = {}, []
    name = os.path.basename(opt.shopify_csv)
    for rel, _, _ in pickers(files):
        h = page_handle(rel)
        if h in handles:
            targets[rel] = f'{opt.shop_url}/products/{h}'
        else:
            blockers.append(f'{rel}: no product with URL handle "{h}" in {name}, so its Order button would have no '
                            'Shopify product to go to (data-shop). Rebuild the CSV with build_shopify_csv.py and import '
                            'it, or rename the page to match its Shopify handle')
    extra = sorted(handles - {page_handle(r) for r, _, _ in pickers(files)})
    warnings = [f'{name} has product(s) with no page on the site, so no Order button leads to them: {", ".join(extra)}'] if extra else []
    return targets, blockers, warnings


def whole_count(v):
    """True for a stock count site.js accepts: a whole number of 0 or more, written 2, 2.0 or 2e0 (JSON has one kind
    of number, so site.js reads them all as 2). Not true/false, not 1.5, not "1", not negative."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return v >= 0 and (isinstance(v, int) or v.is_integer())


def _no_constant(name):
    raise ValueError(f'{name} isn\'t allowed in JSON')


# JavaScript's whitespace (besides Unicode "space separator" characters) and line ends: browsers read stock.js as a script
JS_SPACE = '\t\v\f \u00a0\ufeff'
JS_LINE_END = '\n\r\u2028\u2029'


def _js_string_end(src, i):
    """Index just past the string literal that starts at src[i] (a quote), or at the line end that cuts it short."""
    q, j, n = src[i], i + 1, len(src)
    while j < n and src[j] != q and src[j] not in JS_LINE_END:
        j += 2 if src[j] == '\\' else 1
    return min(j + 1, n)


def js_code(src):
    """(code, None) or (None, line): src as a browser's JavaScript parser reads it, with each comment (/* */ or //, never
    one inside a string) and every character JavaScript counts as whitespace made a plain space, and each line end a
    newline (so line numbers still match the file). line is where a /* comment that is never closed starts."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in '"\'':
            j = _js_string_end(src, i)
            out.append(src[i:j])
            i = j
        elif src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0:
                return None, line_of(src, i)
            ends = len(re.findall('\r\n|[' + JS_LINE_END + ']', src[i:j]))   # a comment over several lines keeps them
            out.append('\n' * ends if ends else ' ')
            i = j + 2
        elif src.startswith('//', i):
            while i < n and src[i] not in JS_LINE_END:
                i += 1
        elif c == '\r':
            out.append('\n')
            i += 2 if src.startswith('\r\n', i) else 1
        elif c in JS_LINE_END:
            out.append('\n')
            i += 1
        elif c in JS_SPACE or unicodedata.category(c) == 'Zs':
            out.append(' ')
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out), None


def _drop_trailing_commas(code):
    """code with each trailing comma (one JavaScript allows just before } or ]) made a space, outside strings. Only a
    comma after a value or a closing bracket is a trailing comma: one straight after {, [ or another comma ({,} or
    1,,}) is a typo in an object, so it stays and the JSON read fails, as the browser's does. (In a list, [,] or [1,,]
    is a hole a browser accepts; it stays too and is refused: stock.js has no lists.)"""
    out, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if c in '"\'':
            j = _js_string_end(code, i)
            out.append(code[i:j])
            i = j
            continue
        if c == ',':
            k, p = i + 1, i - 1
            while k < n and code[k] in ' \n':
                k += 1
            while p >= 0 and code[p] in ' \n':
                p -= 1
            if k < n and code[k] in '}]' and p >= 0 and code[p] not in '{[,':
                c = ' '
        out.append(c)
        i += 1
    return ''.join(out)


# How stock.js may set the stock. The header's form is window.FULLBARS_STOCK = { ... }; a browser runs a few other
# spellings the same way in a classic script, so they are read too: window["FULLBARS_STOCK"] (or in single quotes),
# spaces around the dot, a top-level FULLBARS_STOCK = or var FULLBARS_STOCK =, and semicolons before it. let and const
# are not: they make a variable that isn't on window, so site.js would find no stock (read_stock_js says so).
STOCK_ASSIGN = re.compile(r'''(?:window\s*(?:\.\s*FULLBARS_STOCK|\[\s*(?:"FULLBARS_STOCK"|'FULLBARS_STOCK')\s*\])|(?:\bvar\s+)?\bFULLBARS_STOCK)'''
                          r'\s*=(?!=)\s*')


def read_stock_js(files):
    """(entries, problems) from stock.js, as site.js reads window.FULLBARS_STOCK: entries is {handle: {key: count}}, or
    None when the site has no stock.js. It is read as a browser reads it: comments (/* */ and //), trailing commas,
    semicolons and any whitespace are fine, as in JavaScript, and so are the other spellings of the assignment in
    STOCK_ASSIGN; then the file must be window.FULLBARS_STOCK = <JSON> and nothing else, because anything a browser
    can't run (a stray comma, {,}, a missing brace, a stray letter or */ outside a comment) makes it ignore the whole
    file, and the stock with it. Problems name the line.
    Deliberately refused although a browser would run them, so that what passes here is exactly what the pages read:
    anything JSON doesn't allow inside the list (single quotes, unquoted keys, a count written 0x2, 01 or 2_0, NaN,
    Infinity), an <!-- line, let or const, a second assignment or any other statement before or after it."""
    src = files.get(STOCK_JS)
    if src is None:
        return None, []
    lost = ('If a browser can\'t run the file (a stray comma, a missing brace or a stray character stops it), it ignores all '
            'of it: on the live static route every phone then shows as not in stock, and elsewhere every option as orderable')
    why = ('Write it as JSON, as the header of the file shows: each phone\'s handle and each "storage|condition" in double '
           'quotes, each count a whole number, a comma between entries, and outside the /* */ comment nothing but '
           'window.FULLBARS_STOCK = { ... }; (this check refuses anything else, even forms a browser would run such as '
           'single quotes or 0x2, so that what passes is exactly what the pages read)')
    code, open_line = js_code(src)
    if code is None:
        return {}, [f'{STOCK_JS} line {open_line}: a comment that is never closed ("/*" with no "*/"). {lost}. Close it with '
                    '*/, as the header does']
    m = STOCK_ASSIGN.search(code)
    if not m:
        return {}, [f'{STOCK_JS} doesn\'t set window.FULLBARS_STOCK, so site.js finds no stock in it. Put the counts after '
                    '"window.FULLBARS_STOCK = ", as the header of the file shows']
    before = code[:m.start()]
    bad = before.strip(' \n;')
    if bad:
        at = len(before) - len(before.lstrip(' \n;'))
        if bad in ('let', 'const'):
            return {}, [f'{STOCK_JS} line {line_of(code, at)}: "{show(bad, 40)} FULLBARS_STOCK" makes a variable browsers '
                        'don\'t put on window, so site.js finds no stock in it: on the live static route every phone then '
                        'shows as not in stock, and elsewhere every option as orderable. Write window.FULLBARS_STOCK = '
                        '{ ... }, as the header of the file shows']
        return {}, [f'{STOCK_JS} line {line_of(code, at)}: "{show(bad, 40)}" is outside the comment, before '
                    f'window.FULLBARS_STOCK. {lost}. Delete it. {why}']
    body = _drop_trailing_commas(code[m.end():])
    try:
        data, end = json.JSONDecoder(parse_constant=_no_constant).raw_decode(body)
    except ValueError as e:
        at = getattr(e, 'pos', 0) or 0
        near = show(body[max(0, at - 30):at + 30])
        prev = body[:at].rstrip(' \n')[-1:]
        comma = (' (a comma with no entry before it, as in {,} or 1,,: delete it)'
                 if body[at:at + 1] == ',' and prev and prev in '{,' else '')
        return {}, [f'{STOCK_JS} line {line_of(code, m.end() + at)} is not valid JSON ({getattr(e, "msg", e)}, near "{near}"){comma}, '
                    f'so its stock can\'t be checked. {why}. {lost}.']
    rest = body[end:]
    tail = rest.strip(' \n;')
    if tail:
        at = end + len(rest) - len(rest.lstrip(' \n;'))
        return {}, [f'{STOCK_JS} line {line_of(code, m.end() + at)} has something after the stock list '
                    f'("{show(tail, 40)}"). {lost}. {why}']
    if not isinstance(data, dict):
        return {}, [f'{STOCK_JS} must set window.FULLBARS_STOCK to a list of phones in braces {{ }}. {why}']
    return data, []


def stock_problems(label, stock, combos, place='on this page'):
    """Blockers for one stock list ({"128GB|Good": 2}) against the storage|condition pairs of its product page."""
    out = []
    bad = [f'"{k}": {json.dumps(v)}' for k, v in stock.items() if not whole_count(v)]
    if bad:
        out.append(f'{label} count(s) that aren\'t a whole number of units (0 or more): {", ".join(bad)}. '
                   'site.js treats them as not in stock. Write each as a plain number of units, such as 2')
    coloured = [k for k in stock if k.count('|') >= 2]
    if coloured:
        out.append(f'{label} key(s) with a colour in them: {", ".join(coloured)}. Colour isn\'t tracked: '
                   'the key is "storage|condition" (for example "128GB|Good"), counting every colour together')
    odd = [k for k in stock if combos and k not in combos and k not in coloured]
    if odd:
        out.append(f'{label} key(s) that aren\'t a storage and condition {place}: {", ".join(odd)}. '
                   f'Use one of: {", ".join(sorted(combos))}. A phone under a mistyped key shows as not in stock')
    return out


# The line fetch_shopify_variants.py --write-stock puts above the stock in stock.js (Shopify route). Its time is when
# Shopify sent the data (with --from-dump, when the saved copy was fetched), or "time unknown" when nobody knows
SNAPSHOT_LINE = re.compile(r'/\* Shopify stock snapshot: (?:(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC|time unknown) from (\S+) '
                           r'\((\d+) phones?\)')
SNAPSHOT_MAX_AGE = datetime.timedelta(hours=24)   # older than this, a snapshot (or a saved copy of Shopify's data) is stale
CLOCK_SLACK = datetime.timedelta(minutes=10)      # a time this far ahead of now is "in the future", not clock drift


# when: a timezone-aware UTC datetime, or None if the snapshot doesn't say when
Snapshot = collections.namedtuple('Snapshot', 'when shop phones')


def stock_snapshot(src):
    """The Snapshot (when, shop, phones) that stock.js holds, or None if it wasn't written by fetch_shopify_variants.py
    --write-stock (kept by hand, or empty). A time that isn't a real date and time reads as unknown (None)."""
    m = SNAPSHOT_LINE.search(src or '')
    if not m:
        return None
    when = None
    if m.group(1):
        try:
            when = datetime.datetime.strptime(f'{m.group(1)} {m.group(2)}', '%Y-%m-%d %H:%M').replace(
                tzinfo=datetime.timezone.utc)
        except ValueError:
            when = None
    return Snapshot(when, m.group(3), int(m.group(4)))


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def age_words(when, now=None):
    """How long before now (both aware datetimes) when was, in words: "less than an hour ago", "30 hours ago",
    "42 days ago", or "in the future"."""
    secs = ((now or utc_now()) - when).total_seconds()
    if secs < -CLOCK_SLACK.total_seconds():
        return 'in the future'
    if secs < 3600:
        return 'less than an hour ago'
    hours = int(secs // 3600)
    if hours < 48:
        return f'{hours} hour{"" if hours == 1 else "s"} ago'
    return f'{int(secs // 86400)} days ago'


def staleness(when, now=None):
    """None if Shopify data from when (aware UTC, or None for unknown) is fresh: at most 24 hours old. Otherwise
    'unknown', 'future' or 'old'."""
    now = now or utc_now()
    if when is None:
        return 'unknown'
    if when - now > CLOCK_SLACK:
        return 'future'
    return 'old' if now - when > SNAPSHOT_MAX_AGE else None


def snapshot_age_warning(snap, fetch_cmd, now=None):
    """The warning for a stock snapshot that is more than 24 hours old, in the future or of unknown age, else None."""
    state = staleness(snap.when, now)
    if state is None:
        return None
    again = (f'Fetch it again from the live store and deploy the site (at least daily): {fetch_cmd}. A saved copy '
             '(--from-dump) is stamped with the time it was fetched, so it can\'t freshen a snapshot (GO-LIVE.md section 5, '
             'step 13)')
    if state == 'unknown':
        return (f'{STOCK_JS} is a Shopify stock snapshot with no time on it (written from a saved copy that doesn\'t say when '
                f'Shopify sent it), so it counts as stale. {again}')
    t = f'{snap.when:%Y-%m-%d %H:%M} UTC'
    if state == 'future':
        return (f'{STOCK_JS} is a Shopify stock snapshot dated {t}, which is in the future: the file was edited or a '
                f'computer\'s clock is wrong, so its age can\'t be trusted. {again}')
    return (f'{STOCK_JS} is a Shopify stock snapshot from {t} ({age_words(snap.when, now)}), more than 24 hours old. Stock '
            f'has probably changed since. {again}')


def loads_stock_js(src):
    """True if a page loads stock.js before site.js (site.js reads window.FULLBARS_STOCK as it starts)."""
    order = [m.group(1) for m in SCRIPT_SRC.finditer(src)]
    return 'stock' in order and ('site' not in order or order.index('stock') < order.index('site'))


def picker_combos(tag):
    """{"storage|condition"} offered on a product page, from its picker's data-prices (empty if it can't be read)."""
    try:
        return {f'{st}|{gr}' for st, g in json.loads(attr(tag, 'data-prices') or '{}').items() for gr in g}
    except (ValueError, AttributeError):
        return set()   # check_site_prices.py reports a broken data-prices


# The live static route's fail-closed stock (site.js). --checkout stripe puts data-stock-required="1" on every product
# picker and on the element holding each group of product cards (the card grid) and range tiles (a tile with
# data-handles: the home page's row of tiles); inside them site.js treats stock data that is missing, unreadable or
# malformed as nothing held. --checkout shopify takes it off: on that route stock.js is optional.
STOCK_REQUIRED = 'data-stock-required'
CARD_TAG = re.compile(r'<article class="card"[^>]*>')
STOCK_TILE_TAG = re.compile(r'<a class="tile[^"]*"[^>]*\bdata-handles="[^"]*"[^>]*>')
STOCK_REQUIRED_ATTR = re.compile(r'\s' + STOCK_REQUIRED + r'(?:="[^"]*")?(?=[\s/>])')
DIV_TAG = re.compile(r'<(/?)div\b[^>]*>', re.I)


def stock_mark_tags(src):
    """[(what, match)] for each start tag on a page that takes data-stock-required on the static route, in page order:
    each product picker, and for product cards and range tiles the <div> holding them (a card grid, the row of tiles),
    or the card or tile itself when no <div> holds it."""
    found = [('product picker', m) for m in PICKER_TAG.finditer(src)]
    items = sorted([('card grid', m) for m in CARD_TAG.finditer(src)] + [('range tiles', m) for m in STOCK_TILE_TAG.finditer(src)],
                   key=lambda t: t[1].start())
    divs, stack, seen, d = list(DIV_TAG.finditer(src)), [], set(), 0
    for what, m in items:
        while d < len(divs) and divs[d].start() < m.start():   # the <div>s still open where the card or tile starts
            if divs[d].group(1):
                if stack:
                    stack.pop()
            else:
                stack.append(divs[d])
            d += 1
        holder = stack[-1] if stack else m
        if holder.start() not in seen:
            seen.add(holder.start())
            found.append((what if stack else ('product card' if what == 'card grid' else 'range tile'), holder))
    return sorted(found, key=lambda t: t[1].start())


def stock_marks(files):
    """(marked, unmarked): "page:line (what)" for each product picker, card grid and row of range tiles (stock_mark_tags)
    with and without data-stock-required (site.js goes by the attribute alone, whatever its value)."""
    marked, unmarked = [], []
    for rel in sorted(files):
        if rel.endswith('.html'):
            for what, m in stock_mark_tags(files[rel]):
                (marked if STOCK_REQUIRED_ATTR.search(m.group(0)) else unmarked).append(
                    f'{rel}:{line_of(files[rel], m.start())} ({what})')
    return marked, unmarked


def few(items, n=4):
    return ', '.join(items[:n]) + (f' and {len(items) - n} more' if len(items) > n else '')


def stock_mark_problems(files, checkout):
    """What is wrong with the data-stock-required marks of a switched site on this route: with --checkout stripe every
    picker, card grid and row of range tiles needs one (or a stock.js typo would make every phone there look orderable again); with
    --checkout shopify none may have one (stock.js is optional there, so a marked page would show nothing in stock)."""
    marked, unmarked = stock_marks(files)
    if checkout == 'stripe' and unmarked:
        return [f'{len(unmarked)} product picker(s), card grid(s) or row(s) of range tiles have no {STOCK_REQUIRED}="1": {few(unmarked)}. '
                'On the static route that mark makes site.js fail closed (nothing in stock) when stock.js is missing or '
                'broken; without it a typo in stock.js shows every option there as orderable. Run go_live.py --checkout '
                'stripe on the site again: it adds the mark']
    if checkout == 'shopify' and marked:
        return [f'{len(marked)} product picker(s), card grid(s) or row(s) of range tiles still have {STOCK_REQUIRED} on the Shopify route: '
                f'{few(marked)}. It is for the static route only: with no stock.js snapshot those pages show every phone as '
                'not in stock. Run go_live.py --checkout shopify on the site again: it takes the mark off']
    return []


def site_route(files):
    """The checkout route a site is on, as the pages show it: 'shopify' when a product picker has data-shop; 'stripe' when
    anything has data-stock-required, or when the pickers are live (no data-preview) and pay.js has a Payment Link; else
    None (the preview, or not switched yet)."""
    tags = [tag for _, tag, _ in pickers(files)]
    if any(attr(t, 'data-shop') is not None for t in tags):
        return 'shopify'
    if stock_marks(files)[0]:
        return 'stripe'
    live = tags and not any(attr(t, 'data-preview') is not None for t in tags)
    if live and any(v.strip() for _, v in pay_links(files.get('pay.js', ''))):
        return 'stripe'
    return None


def routine_stock_check(root):
    """For set_prices.py --check, the check to run after every edit and before every deploy: (route, blockers, warnings)
    for the site folder's stock data, exactly as go_live.py checks it (stock_check), on the route the site is on now
    (site_route), plus its data-stock-required marks on a switched site."""
    files = load_site(root)
    route = site_route(files)
    filled = [(k, v.strip()) for k, v in pay_links(files.get('pay.js', '')) if v.strip()]
    shop = next((attr(tag, 'data-shop') for _, tag, _ in pickers(files) if attr(tag, 'data-shop')), None)
    shop = re.sub(r'/products/[^/?#]+$', '', shop) if shop else None
    blockers, warnings = stock_check(files, route, shop, filled if route == 'stripe' else ())
    return route, blockers + stock_mark_problems(files, route), warnings


def pay_units(files):
    """{pay.js key: units held} from stock.js, or else a page's older data-stock, as site.js reads them, so the checklist
    can name a Payment Link for a storage and condition you hold none of. (Every link's payment limit is 1: one link per
    unit.) A phone with no stock data, or with stock data that can't be read, is left out."""
    sj, _ = read_stock_js(files)
    out = {}
    for rel, tag, _ in pickers(files):
        stock = sj.get(page_handle(rel)) if isinstance(sj, dict) else None
        if not isinstance(stock, dict):
            try:
                stock = json.loads(attr(tag, 'data-stock') or 'null', parse_constant=_no_constant)
            except ValueError:
                stock = None
        if not isinstance(stock, dict):
            continue
        for k in picker_combos(tag):
            v = stock.get(k)
            out[f'{attr(tag, "data-model") or ""} {k.replace("|", " ")}'] = int(v) if whole_count(v) else 0
    return out


def picker_form(src):
    m = re.search(r'<form class="picker" id="picker".*?</form>', src, re.S)
    return m.group(0) if m else ''


def picker_colours(src):
    """The colour options of a product page's picker, in page order."""
    return [html.unescape(v) for v in re.findall(r'<input\b[^>]*\bname="colour"[^>]*\bvalue="([^"]*)"', picker_form(src))]


def picker_default(src):
    """"storage|condition|colour" ticked in the page's HTML (what a visitor without JavaScript orders), or None."""
    form, got = picker_form(src), []
    for name in ('storage', 'grade', 'colour'):
        m = re.search(r'<input\b[^>]*\bname="' + name + r'"[^>]*\bvalue="([^"]*)"[^>]*\bchecked\b', form)
        if not m:
            return None
        got.append(html.unescape(m.group(1)))
    return '|'.join(got)


def variant_id(v):
    """A Shopify variant ID as digits (from a number or a string of digits), or None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int) and v > 0:
        return str(v)
    if isinstance(v, str) and re.fullmatch(r'[1-9][0-9]{0,19}', v.strip()):
        return v.strip()
    return None


def load_variants_file(path):
    """--shop-variants FILE: {handle: {"storage|condition|colour": variant ID}}, as fetch_shopify_variants.py writes it."""
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh, parse_constant=_no_constant)
    except (OSError, ValueError) as e:
        raise Fail(f'--shop-variants {path}: {e}')
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, dict) for k, v in data.items()):
        raise Fail(f'--shop-variants {path} must be a JSON object of {{"<handle>": {{"<storage>|<condition>|<colour>": '
                   '<variant ID>}}}}, as fetch_shopify_variants.py writes it')
    return data


def variant_maps(files, opt):
    """--checkout shopify: ({product page: {"storage|condition|colour": variant ID digits}}, blockers, warnings).
    With --shop-variants the file decides; without it, each page's existing data-variants (from an earlier run)."""
    if getattr(opt, 'checkout', None) != 'shopify':
        return {}, [], []
    given = getattr(opt, 'variants_data', None)
    maps, blockers, warnings, gaps = {}, [], [], []
    pages = {}
    for rel, tag, pos in pickers(files):
        pages[page_handle(rel)] = rel
        where = f'{rel}:{line_of(files[rel], pos)}'
        if given is not None:
            raw, label = given.get(page_handle(rel)), f'--shop-variants "{page_handle(rel)}"'
        else:
            text = attr(tag, 'data-variants')
            if text is None:
                continue
            label = f'{where}: data-variants'
            try:
                raw = json.loads(text, parse_constant=_no_constant)
            except ValueError as e:
                blockers.append(f'{label} is not valid JSON ({e}). Run go_live.py again with --shop-variants')
                continue
            if not isinstance(raw, dict):
                blockers.append(f'{label} is not a list of variant IDs in braces. Run go_live.py again with --shop-variants')
                continue
        if not raw:
            continue
        want = {f'{c}|{col}' for c in picker_combos(tag) for col in picker_colours(files[rel])}
        odd = sorted(k for k in raw if k not in want)
        if odd:
            blockers.append(f'{label}: variant(s) that aren\'t a storage, condition and colour on {rel}: {", ".join(odd[:8])}'
                            f'{" ..." if len(odd) > 8 else ""}. Each key must be one of the page\'s options, such as '
                            f'"{sorted(want)[0] if want else "128GB|Good|Blue"}", written as in products-shopify.csv')
        bad = [f'"{k}": {json.dumps(v)}' for k, v in raw.items() if variant_id(v) is None]
        if bad:
            blockers.append(f'{label}: variant ID(s) that aren\'t a Shopify variant ID (a whole number): {", ".join(bad[:8])}'
                            f'{" ..." if len(bad) > 8 else ""}')
        good = {k: variant_id(v) for k, v in raw.items() if k in want and variant_id(v) is not None}
        if good:
            maps[rel] = good
        missing = len(want - set(good))
        if missing:
            gaps.append(f'{rel} ({missing} of {len(want)})')
    if given is not None:
        no_ids = [rel for h, rel in sorted(pages.items()) if not given.get(h)]
        extra = sorted(h for h in given if h not in pages)
        if no_ids:
            warnings.append(f'--shop-variants has no variant IDs for {len(no_ids)} product page(s): {", ".join(no_ids)}. '
                            'Their Order buttons read "Choose and pay on the next page" and open Shopify on its first variant')
        if extra:
            warnings.append(f'--shop-variants has product(s) with no page on the site: {", ".join(extra)}')
    if gaps:
        warnings.append('phone choices with no Shopify variant ID, whose Order button reads "Choose and pay on the next page" '
                        '(the customer picks storage, condition and colour again on Shopify): ' + ', '.join(gaps))
    return maps, blockers, warnings


def page_variants(tag):
    """{"storage|condition|colour": variant ID digits} from a picker's data-variants ({} if none or unreadable)."""
    try:
        raw = json.loads(attr(tag, 'data-variants') or '{}')
    except ValueError:
        return {}
    return {k: variant_id(v) for k, v in raw.items() if variant_id(v)} if isinstance(raw, dict) else {}


def shop_href(shop, vmap, src):
    """The Order link's address without JavaScript: the Shopify product, opened on the variant ticked in the page's
    HTML when there is an ID for it."""
    vid = (vmap or {}).get(picker_default(src) or '')
    return f'{shop}?variant={vid}' if vid else shop


# The Order link's text on the Shopify route when there is no variant ID for the phone chosen: Shopify then opens on its
# own first variant, perhaps at another price, so the button never reads "Order" beside our price (site.js says the same)
HANDOFF_LABEL = 'Choose and pay on the next page'
HANDOFF_NOTE = re.compile(r'<p\b[^>]*\bid="handoffNote"[^>]*>')


def order_link_state(shop, vmap, src):
    """(href, text, handoff) of the Order link a visitor without JavaScript gets on the Shopify route: with a variant ID
    for the phone ticked in the HTML, "Order" to that variant; without one, the hand-off wording to the bare product
    (handoff True: the note under the button, "You'll pick storage, condition and colour again there ...", shows too)."""
    href = shop_href(shop, vmap, src)
    handoff = href == shop
    return href, (HANDOFF_LABEL if handoff else 'Order'), handoff


# ----------------------------------------------------------------------------------------------- edits
class Edit:
    """Replace src[start:end] of one file with new. prio 0 = switch, 1 = domain (dropped inside a switch)."""
    __slots__ = ('rel', 'start', 'end', 'new', 'what', 'prio', 'line')

    def __init__(self, rel, start, end, new, what, prio=0):
        self.rel, self.start, self.end, self.new, self.what, self.prio = rel, start, end, new, what, prio
        self.line = 0


def resolve(files, edits):
    """Drop domain edits that sit inside a block a switch replaces; refuse any other overlap."""
    by_file = {}
    for e in edits:
        by_file.setdefault(e.rel, []).append(e)
    kept = []
    for rel, es in by_file.items():
        es.sort(key=lambda e: (e.start, -e.end, e.prio))
        out = []
        for e in es:
            clash = [k for k in out if e.start < k.end and k.start < e.end or (e.start == e.end == k.start == k.end)]
            if not clash:
                out.append(e)
                continue
            if all(k.prio < e.prio and k.start <= e.start and e.end <= k.end for k in clash):
                continue   # e.g. a domain inside a removed banner: it goes with the banner
            raise Fail(f'{rel}: overlapping changes ({e.what} / {clash[0].what}) at line {line_of(files.get(rel, ""), e.start)}')
        kept.extend(out)
    for e in kept:
        e.line = line_of(files.get(e.rel, ''), e.start)
    return sorted(kept, key=lambda e: (e.rel, e.start))


def apply_edits(files, edits):
    out = dict(files)
    by_file = {}
    for e in edits:
        by_file.setdefault(e.rel, []).append(e)
    for rel, es in by_file.items():
        src = out.get(rel, '')
        for e in sorted(es, key=lambda e: e.start, reverse=True):
            src = src[:e.start] + e.new + src[e.end:]
        out[rel] = src
    return out


def show(text, limit=None):
    t = text.replace('\n', '⏎')
    return t if limit is None or len(t) <= limit else t[:limit] + '…'


def describe(files, e, ctx=40):
    src = files.get(e.rel, '')
    ls = src.rfind('\n', 0, e.start) + 1
    le = src.find('\n', e.end)
    le = len(src) if le < 0 else le
    old, new = src[e.start:e.end], e.new
    whole_line = old.endswith('\n') and not new and e.start == ls
    left = src[max(ls, e.start - ctx):e.start]
    right = '' if whole_line else src[e.end:min(le, e.end + ctx)]
    lpad = '…' if e.start - ctx > ls else ''
    rpad = '…' if not whole_line and e.end + ctx < le else ''
    lines = [f'  {e.rel}:{e.line}  {e.what}']
    lines.append(f'    before: {lpad}{show(left)}[-{show(old.rstrip(chr(10)) if whole_line else old)}-]{show(right)}{rpad}')
    lines.append('    after:  (line removed)' if whole_line else f'    after:  {lpad}{show(left)}{{+{show(new)}+}}{show(right)}{rpad}')
    return '\n'.join(lines)


# ----------------------------------------------------------------------------------------------- domain
def parse_domain(value, no_www):
    d = re.sub(r'^https?://', '', value.strip().lower()).rstrip('/').rstrip('.')
    bare = d[4:] if d.startswith('www.') else d
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', bare):
        raise Fail(f'--domain {value!r} is not a domain name like fullbars.co.uk')
    return bare, (bare if no_www else 'www.' + bare)


def current_host(files):
    m = re.search(r'<link\b[^>]*\brel="canonical"[^>]*\bhref="https?://([^/"]+)/', files.get('index.html', ''))
    if not m:
        raise Fail('index.html has no canonical link, so the current domain is unknown')
    return m.group(1).lower()


def domain_edits(files, old_host, new_bare, new_host):
    old_bare = old_host[4:] if old_host.startswith('www.') else old_host
    if old_bare == new_bare and old_host == new_host:
        return []
    dom = re.escape(old_bare) + r'(?![\w-]|\.\w)'
    rules = (
        (re.compile(r'https?://(?:www\.)?' + dom, re.I), 'https://' + new_host, 'web address'),
        (re.compile(r'(?<=@)' + dom, re.I), new_bare, 'email domain'),
        (re.compile(r'(?<![\w@/.-])www\.' + dom, re.I), new_host, 'web address'),
        (re.compile(r'(?<![\w@/.-])' + dom, re.I), new_bare, 'domain'),
    )
    edits = []
    for rel, src in files.items():
        taken = []
        for rx, new, what in rules:
            for m in rx.finditer(src):
                if any(a < m.end() and m.start() < b for a, b in taken):
                    continue
                taken.append(m.span())
                if m.group(0) != new:
                    edits.append(Edit(rel, m.start(), m.end(), new, f'{what}: {m.group(0)} -> {new}', prio=1))
    return edits


# ----------------------------------------------------------------------------------------------- switches
def plan_switches(files, opt):
    """The mechanical preview -> live edits, and notes about what was deliberately left."""
    edits, notes = [], []
    long_date = f'{opt.launch_date.day} {opt.launch_date:%B %Y}'
    for rel in sorted(files):
        src = files[rel]
        if not rel.endswith('.html'):
            continue
        # robots meta
        for m in re.finditer(r'<meta\b[^>]*\bname="robots"[^>]*>', src):
            content = attr(m.group(0), 'content') or ''
            if 'noindex' not in content.lower():
                continue
            if rel in NO_INDEX_KEEP:
                notes.append(f'{rel} keeps noindex on purpose: an error page should never be in search results.')
                continue
            new = re.sub(r'content="[^"]*"', 'content="index,follow"', m.group(0))
            edits.append(Edit(rel, m.start(), m.end(), new, 'search engines: noindex -> index,follow'))
        # preview banner
        for m in re.finditer(r'<div\b[^>]*\bclass="preview-bar\b[^"]*"[^>]*>', src):
            end = closing(rel, src, m.start())
            s, e = widen_to_line(src, m.start(), end)
            edits.append(Edit(rel, s, e, '', 'preview banner removed'))
        # data-preview attributes
        for m in re.finditer(r'<[a-zA-Z][^>]*?\sdata-preview(?:="[^"]*")?[^>]*>', src):
            tag = m.group(0)
            if opt.trade_ins == 'closed' and attr(tag, 'id') == 'qt':
                continue
            a = re.search(r'\sdata-preview(?:="[^"]*")?', tag)
            where = {'picker': 'product picker', 'contactForm': 'contact form', 'qt': 'trade-in quote tool'}.get(attr(tag, 'id'), 'element')
            edits.append(Edit(rel, m.start() + a.start(), m.start() + a.end(), '', f'{where}: data-preview removed (switches it on)'))
        # the static route's fail-closed stock: data-stock-required="1" on each product picker, card grid and row of range
        # tiles, so site.js shows nothing as held there if stock.js is missing or broken (stock.js is the only thing that
        # stops a sale on this route); off again on the Shopify route, where stock.js is optional
        for what, m in stock_mark_tags(src) if opt.checkout in ('stripe', 'shopify') else ():
            have = STOCK_REQUIRED_ATTR.search(m.group(0))
            if opt.checkout == 'stripe' and not have:
                at = m.end() - 1
                edits.append(Edit(rel, at, at, f' {STOCK_REQUIRED}="1"',
                                  f'{what}: {STOCK_REQUIRED} added (nothing shows as in stock if stock.js is missing or broken)'))
            elif opt.checkout == 'shopify' and have:
                edits.append(Edit(rel, m.start() + have.start(), m.start() + have.end(), '',
                                  f'{what}: {STOCK_REQUIRED} removed (Shopify route: stock.js is optional)'))
        # Shopify route: the picker's data-shop (site.js sends the Order button there)
        pk = PICKER_TAG.search(src)
        shop = opt.shop_targets.get(rel) if opt.checkout == 'shopify' else None
        if pk and shop:
            dm = re.search(r'\sdata-shop="([^"]*)"', pk.group(0))
            if not dm:
                at = pk.end() - 1
                edits.append(Edit(rel, at, at, f' data-shop="{html.escape(shop)}"', f'product picker: data-shop added ({shop})'))
            elif html.unescape(dm.group(1)) != shop:
                edits.append(Edit(rel, pk.start() + dm.start(1), pk.start() + dm.end(1), html.escape(shop),
                                  f'product picker: data-shop -> {shop}'))
        # Shopify route with --shop-variants: the picker's data-variants (site.js adds ?variant=<id> to the Order link)
        vmap = getattr(opt, 'variant_maps', {}).get(rel) if shop else None
        if pk and shop and getattr(opt, 'variants_data', None) is not None:
            want = html.escape(json.dumps(vmap, separators=(',', ':'), sort_keys=True), quote=True) if vmap else None
            vm = re.search(r'\sdata-variants="([^"]*)"', pk.group(0))
            if vm and want is None:
                edits.append(Edit(rel, pk.start() + vm.start(), pk.start() + vm.end(), '',
                                  'product picker: data-variants removed (no Shopify variant IDs for this phone)'))
            elif vm and vm.group(1) != want:
                edits.append(Edit(rel, pk.start() + vm.start(1), pk.start() + vm.end(1), want,
                                  f'product picker: data-variants -> {len(vmap)} Shopify variant ID(s)'))
            elif not vm and want:
                at = pk.start() + len('<form class="picker" id="picker"')
                edits.append(Edit(rel, at, at, f' data-variants="{want}"',
                                  f'product picker: data-variants added ({len(vmap)} Shopify variant ID(s))'))
        # the Order link when site.js doesn't run: the Shopify product (on the variant ticked in the HTML, when there is an
        # ID for it; without one it reads "Choose and pay on the next page", with the hand-off note shown under it), or the
        # contact page
        if shop:
            href, label, handoff = order_link_state(shop, vmap, src)
        else:
            href = (attr(pk.group(0), 'data-contact') if pk else None) or '../contact.html'
            label, handoff = 'Order', False
        described = ' aria-describedby="handoffNote"' if handoff else ''
        # dead Order span -> link
        for m in re.finditer(r'<span\b[^>]*\bid="orderBtn"[^>]*>.*?</span>', src, re.S):
            tag = m.group(0)[:m.group(0).index('>') + 1]
            cls = ' '.join(c for c in (attr(tag, 'class') or 'btn btn-hot btn-block').split() if c != 'btn-off')
            new = f'<a class="{html.escape(cls)}" id="orderBtn" href="{html.escape(href)}"{described}>{label}</a>'
            edits.append(Edit(rel, m.start(), m.end(), new, 'Order button: dead "Opening soon" span -> link'
                              + (' to the Shopify product' if shop else '')))
        # an Order link from an earlier run that points the other way (contact page vs Shopify, or another variant): follow
        # --checkout, and keep its no-JavaScript text and the hand-off note in step with where it goes
        if pk and opt.checkout in ('shopify', 'stripe') and (shop or opt.checkout == 'stripe'):
            for m in re.finditer(r'(<a\b[^>]*\bid="orderBtn"[^>]*>)(.*?)</a>', src, re.S):
                tag = m.group(1)
                cls = attr(tag, 'class') or 'btn btn-hot btn-block'
                new = f'<a class="{html.escape(cls)}" id="orderBtn" href="{html.escape(href)}"{described}>{label}</a>'
                hm = re.search(r'\shref="([^"]*)"', tag)
                old_href = html.unescape(hm.group(1)) if hm else None
                if (old_href != href or html.unescape(m.group(2)).strip() != label
                        or (attr(tag, 'aria-describedby') == 'handoffNote') != handoff):
                    what = f'Order button: link -> {href}' if old_href != href else f'Order button: text -> "{label}"'
                    edits.append(Edit(rel, m.start(), m.end(), new, what))
        # the hand-off note under the button: shown without JavaScript exactly when the link reads the hand-off wording
        # (site.js keeps it in step as the visitor changes storage, condition and colour)
        if pk and opt.checkout in ('shopify', 'stripe'):
            for m in HANDOFF_NOTE.finditer(src):
                hid = re.search(r'\shidden(?:="[^"]*")?(?=[\s>/])', m.group(0))
                if handoff and hid:
                    edits.append(Edit(rel, m.start() + hid.start(), m.start() + hid.end(), '',
                                      'hand-off note shown (no Shopify variant ID for the phone ticked in the HTML)'))
                elif not handoff and not hid:
                    at = m.end() - 1
                    edits.append(Edit(rel, at, at, ' hidden', 'hand-off note hidden'))
        # preview-only notes
        if opt.trade_ins == 'open':
            for m in re.finditer(r'<div\b[^>]*\bid="qtPreview"[^>]*>', src):
                end = closing(rel, src, m.start())
                s, e = widen_to_line(src, m.start(), end)
                edits.append(Edit(rel, s, e, '', 'trade-in "open soon" note removed'))
        for m in re.finditer(r'<div\b[^>]*\bclass="[^"]*\bpreview-note\b[^"]*"[^>]*>', src):
            end = closing(rel, src, m.start())
            s, e = widen_to_line(src, m.start(), end)
            edits.append(Edit(rel, s, e, '', '"Not trading yet" box removed'))
        for m in re.finditer(r'<div\b[^>]*>\s*<h[1-6][^>]*>\s*Not trading yet\.?\s*</h[1-6]>', src):
            end = closing(rel, src, m.start())
            s, e = widen_to_line(src, m.start(), end)
            edits.append(Edit(rel, s, e, '', '"Not trading yet" panel removed'))
        # contact form: the topic site.js picks for ?order= links. Static route only: on the Shopify route there is no
        # email order beside Shopify (site.js ignores ?order= without this topic), so it isn't added, or goes
        if 'id="contactForm"' in src:
            sm = re.search(r'<select\b[^>]*\bid="cTopic"[^>]*>(.*?)</select>', src, re.S)
            if sm and opt.checkout == 'shopify':
                for om in re.finditer(r'<option\b[^>]*>\s*Order a phone\s*</option>', sm.group(0)):
                    edits.append(Edit(rel, sm.start() + om.start(), sm.start() + om.end(), '',
                                      'contact form: "Order a phone" topic removed (Shopify takes the orders)'))
            elif sm and 'Order a phone' not in sm.group(1):
                first = src.find('</option>', sm.start(), sm.end())
                at = first + len('</option>') if first >= 0 else sm.start() + sm.group(0).index('>') + 1
                edits.append(Edit(rel, at, at, '<option>Order a phone</option>', 'contact form: "Order a phone" topic added'))
        # legal pages' date: only in the run that switches the site out of preview (or with --launch-date)
        for m in re.finditer(r'(<p\b[^>]*\bclass="legal-updated"[^>]*>)([^<]*)(</p>)', src) if opt.set_dates else ():
            want = f'Last updated {long_date}'
            if m.group(2).strip() != want:
                edits.append(Edit(rel, m.start(2), m.end(2), want, 'legal page date -> launch date'))
    # sitemap
    sm = files.get('sitemap.xml')
    if sm is None:
        notes.append('No sitemap.xml in the site folder: search engines will find pages by links only.')
    elif opt.set_dates:
        for m in re.finditer(r'<lastmod>([^<]*)</lastmod>', sm):
            if m.group(1).strip() != opt.launch_date.isoformat():
                edits.append(Edit('sitemap.xml', m.start(1), m.end(1), opt.launch_date.isoformat(), 'sitemap date -> launch date'))
    # robots.txt
    rb = files.get('robots.txt')
    if rb is None:
        new = f'User-agent: *\nAllow: /\n\nSitemap: https://{opt.host}/sitemap.xml\n'
        edits.append(Edit('robots.txt', 0, 0, new, 'robots.txt created (allows crawling)'))
    else:
        pos = 0
        for line in rb.splitlines(True):
            body = line.strip()
            if body.startswith('#') and (SHOP_WORDS.search(body) or re.search(r'at launch|placeholder', body, re.I)):
                edits.append(Edit('robots.txt', pos, pos + len(line), '', 'robots.txt: preview comment removed'))
            pos += len(line)
        # only the rule that shuts out every crawler; a Disallow you add for one named bot is left alone
        for at, line, field, value, agents in robots_rules(rb):
            if field == 'disallow' and value == '/' and '*' in agents:
                body = line.split('#', 1)[0].strip()
                s = at + line.index(body)
                edits.append(Edit('robots.txt', s, s + len(body), 'Allow: /', 'robots.txt: crawlers allowed'))
    return edits, notes


# ----------------------------------------------------------------------------------------------- blockers
def code_mask(src):
    """src with <style>, non-JSON-LD <script> and <!-- --> contents blanked (newlines kept)."""
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    src = re.sub(r'<!--.*?-->', blank, src, flags=re.S)
    src = re.sub(r'(<style\b[^>]*>)(.*?)(?=</style)', lambda m: m.group(1) + re.sub(r'[^\n]', ' ', m.group(2)), src, flags=re.S | re.I)

    def script(m):
        if 'application/ld+json' in m.group(1):
            return m.group(0)
        return m.group(1) + re.sub(r'[^\n]', ' ', m.group(2))
    return re.sub(r'(<script\b[^>]*>)(.*?)(?=</script)', script, src, flags=re.S | re.I)


def placeholders(files):
    """{placeholder: [rel:line, ...]} still on customer-facing pages."""
    found = {}
    for rel in sorted(files):
        if not rel.endswith('.html'):
            continue
        src = files[rel]
        masked = code_mask(src)
        allowed = []
        for f, text, ctx in LEAVE_ALONE:
            if f == rel:
                for m in re.finditer(ctx, src, re.S):
                    allowed.append((text, m.start(), m.end()))
        for m in PLACEHOLDER.finditer(masked):
            if any(t == m.group(0) and a <= m.start() and m.end() <= b for t, a, b in allowed):
                continue
            found.setdefault(m.group(0), []).append(f'{rel}:{line_of(src, m.start())}')
    return found


def _run(cmd):
    """Run one of the pack's checkers. Returns the CompletedProcess, or None if it took over 5 minutes."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None


def run_price_check(site):
    """[] if check_site_prices.py passes, else the reasons."""
    if not os.path.isfile(PRICE_CHECKER):
        return [f'check_site_prices.py is missing from {HERE}, so prices can\'t be checked']
    r = _run([sys.executable, PRICE_CHECKER, '--site', site, '--quiet'])
    if r is None:
        return ['check_site_prices.py took over 5 minutes and was stopped']
    if r.returncode == 0:
        return []
    fails = [ln[5:] for ln in r.stdout.splitlines() if ln.startswith('FAIL ')]
    if fails:
        return [f'price check: {f}' for f in fails]
    tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['no output'])[-1]
    return [f'check_site_prices.py stopped with an error, which usually means a mistyped data-prices on a product page '
            f'(GO-LIVE.md section 6, step 3): {tail}']


def run_set_prices_check(site, price_check_failed=False):
    """[] if set_prices.py --check passes, else its NEEDS A HAND EDIT items, stale derived prices and errors.
    It checks everything check_site_prices.py does, plus the #pdFrom line and the "Lowest price" badge."""
    if not os.path.isfile(SET_PRICES):
        return [f'set_prices.py is missing from {HERE}, so the "Lowest price" badge and "From" lines can\'t be checked']
    r = _run([sys.executable, SET_PRICES, '--check', site, '--no-stock-check'])   # stock: checked below (stock_check)
    if r is None:
        return ['set_prices.py --check took over 5 minutes and was stopped']
    if r.returncode == 0:
        return []
    out, section, stale = [], None, []
    for ln in r.stdout.splitlines():
        if not ln.strip():
            continue
        if not ln.startswith(' '):
            section = 'hand' if ln.startswith('NEEDS A HAND EDIT') else 'stale' if ln.startswith('Out of date') else None
            continue
        if section == 'hand' and ln.startswith('  - '):
            out.append(f'set_prices.py: needs a hand edit: {ln[4:]}')
        elif section == 'stale':
            if re.match(r'  \S', ln):
                page = ln.strip()
            elif re.match(r'\s+line \d+', ln):
                stale.append(f'{page}: {ln.strip()}')
    m = re.search(r'^(\d+) derived price\(s\) out of date', r.stdout, re.M)
    if m:
        out.append(f'set_prices.py: {m.group(1)} price(s) shown on the pages don\'t match data-prices '
                   f'({"; ".join(stale[:3])}{"; ..." if len(stale) > 3 else ""}). Fix them all with: '
                   f'python3 launch/full-bars/set_prices.py --write {site}')
    out += [f'set_prices.py: {ln[7:]}' for ln in r.stderr.splitlines() if ln.startswith('ERROR: ')]
    if not out and not price_check_failed:
        tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['no output'])[-1]
        out.append(f'set_prices.py --check failed (exit {r.returncode}): {tail}')
    return out


def run_facts_check(site):
    """[] if check_site_facts.py finds no spec that disagrees with facts.json, else the conflicts."""
    if not os.path.isfile(FACTS_CHECKER):
        return [f'check_site_facts.py is missing from {HERE}, so handset specs can\'t be checked']
    r = _run([sys.executable, FACTS_CHECKER, '--site', site, '--quiet'])
    if r is None:
        return ['check_site_facts.py took over 5 minutes and was stopped']
    if r.returncode == 0:
        return []
    fails = [ln[5:] for ln in r.stdout.splitlines() if ln.startswith('FAIL ')]
    if fails:
        return [f'facts check (facts.json): {f}' for f in fails]
    tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['no output'])[-1]
    return [f'check_site_facts.py stopped (exit {r.returncode}): {tail}']


def run_checks(site):
    """Every content check in this folder, run on site: prices, derived prices and badge, handset specs."""
    price = run_price_check(site)
    return price + run_set_prices_check(site, bool(price)) + run_facts_check(site)


def stock_check(files, checkout=None, shop_url=None, filled=()):
    """(blockers, warnings) for the site's stock data on a checkout route ('stripe', 'shopify', or None for the preview):
    stock.js (read as a browser reads it) and any page's older data-stock, checked against each product page's storage
    and condition pairs. go_live.py runs it before switching, and set_prices.py --check after every edit (on the route the
    site is on: site_route). filled: pay.js's Payment Links [(key, link)], for the static route's unheld-link warning."""
    blockers, warnings = [], []
    sj, sj_problems = read_stock_js(files)
    blockers.extend(sj_problems)
    entries = sj or {}
    handles = {page_handle(rel) for rel, _, _ in pickers(files)}
    for h in sorted(entries):
        if h not in handles:
            blockers.append(f'{STOCK_JS}: "{h}" is not a product page (there is no products/{h}.html), so its stock is never '
                            f'used. Use the page\'s name, one of: {", ".join(sorted(handles))}')
        elif not isinstance(entries[h], dict):
            blockers.append(f'{STOCK_JS}: "{h}" must be its storage and condition counts in braces, such as '
                            f'"{h}": {{"128GB|Good": 2}} ({{}} if you hold none of it), not {json.dumps(entries[h])}')
    missing, with_stock, both, no_include, held_by_key, with_attr = [], [], [], [], {}, []
    for rel, tag, pos in pickers(files):
        h = page_handle(rel)
        where = f'{rel}:{line_of(files[rel], pos)}'
        combos = picker_combos(tag)
        page_stock = None
        raw = attr(tag, 'data-stock')
        if raw is not None:
            with_attr.append(rel)
            try:
                page_stock = json.loads(raw, parse_constant=_no_constant)   # NaN/Infinity: browsers refuse the attribute
                if not isinstance(page_stock, dict):
                    raise ValueError('not an object')
            except ValueError as e:
                blockers.append(f'{where}: data-stock is not valid JSON ({e}), so site.js ignores it: on the live static route the '
                                'phone then shows as not in stock, elsewhere every option looks in stock')
                page_stock = None
            else:
                blockers.extend(stock_problems(f'{where}: data-stock', page_stock, combos))
        js_stock = entries.get(h) if isinstance(entries.get(h), dict) else None
        if js_stock is not None:
            blockers.extend(stock_problems(f'{STOCK_JS} "{h}"', js_stock, combos, place='on that phone\'s page'))
            if not loads_stock_js(files[rel]):
                no_include.append(rel)
            if raw is not None:
                both.append(rel)
        stock = js_stock if js_stock is not None else page_stock
        if js_stock is None and raw is None:
            missing.append(rel)
            continue
        with_stock.append(rel)
        if stock is None:
            continue   # a data-stock that isn't valid JSON: reported above
        model = attr(tag, 'data-model') or ''
        for k in combos | set(stock):
            v = stock.get(k)
            held_by_key[f'{model} {k.replace("|", " ")}'] = whole_count(v) and v > 0
    if no_include:
        blockers.append(f'{len(no_include)} product page(s) have stock in {STOCK_JS} but don\'t load it before site.js, so '
                        f'site.js never sees it: {", ".join(no_include)}. Add <script src="../{STOCK_JS}" defer></script> '
                        'just before the site.js script tag, as on the other pages')
    if both:
        warnings.append(f'{len(both)} product page(s) have data-stock as well as an entry in {STOCK_JS}: {", ".join(both)}. '
                        f'{STOCK_JS} wins and the page\'s data-stock is ignored. Remove data-stock from those pages, so '
                        f'{STOCK_JS} is the only place to change')
    if sj is None and checkout == 'stripe':
        blockers.append(f'the site folder has no {STOCK_JS}. On the live static route site.js fails closed without it: every '
                        'phone shows as not in stock and nothing can be ordered. Put it back with every phone you hold in it '
                        '(GO-LIVE.md section 6, step 2)')
    elif sj is None and any(loads_stock_js(src) for rel, src in files.items() if rel.endswith('.html')):
        warnings.append(f'the pages load {STOCK_JS}, but the site folder has none: browsers log a "not found" error for it. '
                        f'Put back {STOCK_JS} (on the Shopify route, write it with fetch_shopify_variants.py --write-stock, '
                        'or leave it empty)')
    if checkout == 'stripe':
        if missing and not sj_problems:   # an unreadable stock.js is reported above: fix that first
            blockers.append(f'no stock data for {len(missing)} of {len(missing) + len(with_stock)} product pages '
                            f'({", ".join(missing)}): neither {STOCK_JS} nor the page\'s data-stock says what you hold. On the '
                            'live static route site.js fails closed, so each of those phones shows as not in stock at all and '
                            'can\'t be ordered (without that safeguard, every option would look orderable with no phone '
                            f'behind it). Add each phone to {STOCK_JS}: "iphone-13": {{"128GB|Good": 2}} means 2 units of '
                            '128GB in Good, any colour; a missing key or 0 means not in stock; {} means none at all '
                            '(GO-LIVE.md section 6, step 2)')
        # every page with a picker, phone cards or range tiles must load stock.js: on the live static route site.js treats
        # stock it can't see as none (product pages with stock.js entries are listed above already)
        unloaded = [rel for rel in sorted(files) if rel.endswith('.html') and rel not in no_include
                    and stock_mark_tags(files[rel]) and not loads_stock_js(files[rel])]
        if unloaded and sj is not None:
            blockers.append(f'{len(unloaded)} page(s) with a product picker, phone cards or range tiles don\'t load {STOCK_JS} '
                            f'before site.js: {", ".join(unloaded)}. On the live static route site.js would then show every '
                            f'phone there as not in stock. Add <script src="{STOCK_JS}" defer></script> (../{STOCK_JS} in a '
                            'folder) just before the site.js script tag, as on the other pages')
        # a phone held only in a page's older data-stock: its product page sells it, but its cards and range tiles (which
        # read stock.js alone) would tell customers "None in stock right now". A blocker, not a warning: that is false
        attr_only = [rel for rel in with_attr if page_handle(rel) not in entries]
        if attr_only and not sj_problems:   # an unreadable stock.js is reported above: fix that first
            blockers.append(f'{len(attr_only)} phone(s) keep their stock only in the older data-stock attribute: '
                            f'{", ".join(attr_only)}. Their product pages use it, but their cards and range tiles can\'t read '
                            f'it, so on the live static route they would say "None in stock right now" while the page sells '
                            f'the phone. Copy each phone\'s data-stock list into {STOCK_JS} under its handle '
                            f'("{page_handle(attr_only[0])}": {{...}}) and remove data-stock from its #picker (GO-LIVE.md '
                            'section 6, step 2)')
    elif checkout == 'shopify':
        # Shopify's own stock decides what can be bought. Stock data here is optional and checked as above; it only turns
        # a page's button into "Not in stock — ask us" and puts "None in stock right now" on cards, so it must come from
        # Shopify (fetch_shopify_variants.py --write-stock) and be fresh
        snap = stock_snapshot(files.get(STOCK_JS))
        how = ('Write it from Shopify instead: python3 launch/full-bars/fetch_shopify_variants.py --shop-url '
               f'{shop_url or "<shop-url>"} --write-stock <this site folder>/{STOCK_JS} (GO-LIVE.md section 5, step 13)')
        if entries and not snap:
            warnings.append(f'{STOCK_JS} lists {len(entries)} phone(s) but wasn\'t written by fetch_shopify_variants.py '
                            '--write-stock, so it doesn\'t follow Shopify\'s stock: a phone Shopify has could show "Not in stock '
                            f'— ask us". {how}')
        if snap:
            # its age to the minute, in UTC as written: a snapshot more than 24 hours old (or of unknown age) is stale
            stale = snapshot_age_warning(snap, 'python3 launch/full-bars/fetch_shopify_variants.py --shop-url '
                                         f'{shop_url or "<shop-url>"} --write-stock <this site folder>/{STOCK_JS}')
            if stale:
                warnings.append(stale)
            if snap.shop.startswith('https://') and shop_url and snap.shop.rstrip('/') != shop_url:
                warnings.append(f'{STOCK_JS} is a stock snapshot from {snap.shop}, not from --shop-url {shop_url}. {how}')
        if entries and missing:
            warnings.append(f'{len(missing)} product page(s) have no stock data while {STOCK_JS} lists other phones: '
                            f'{", ".join(missing)}. They show every option as orderable (Shopify still refuses what it '
                            'doesn\'t have). fetch_shopify_variants.py --write-stock lists every phone it can read from Shopify')
        if with_attr:
            warnings.append(f'{len(with_attr)} product page(s) have the older data-stock attribute, kept by hand, which doesn\'t '
                            f'follow Shopify\'s stock: {", ".join(with_attr)}. Remove it from each #picker and use a {STOCK_JS} '
                            'snapshot from Shopify')
    if checkout == 'stripe':
        unheld = [k for k, v in filled if k in held_by_key and not held_by_key[k]]
        if unheld:
            warnings.append(f'pay.js has Payment Link(s) for phones your stock data says you don\'t hold, so the page shows '
                            f'"Not in stock" and never offers them: {", ".join(unheld)}. Deactivate them in Stripe and clear them')
    return blockers, warnings


def find_blockers(site, files, opt):
    blockers, warnings = [], []
    # 1. placeholders
    for ph, where in sorted(placeholders(files).items(), key=lambda kv: (-len(kv[1]), kv[0])):
        pages = len({w.rsplit(':', 1)[0] for w in where})
        blockers.append(f'placeholder {ph} still on {pages} page{"s" if pages != 1 else ""} ({len(where)}x): {", ".join(where)}')
    # 2. prices (check_site_prices.py and set_prices.py --check) and handset specs (check_site_facts.py)
    blockers.extend(run_checks(site))
    # 3. checkout
    links = pay_links(files.get('pay.js', ''))
    filled = [(k, v.strip()) for k, v in links if v.strip()]
    if opt.checkout is None:
        blockers.append('checkout not chosen: pass --checkout shopify or --checkout stripe (GO-LIVE.md section 1, decision 1)')
    elif opt.checkout == 'shopify':
        if filled:
            blockers.append(f'--checkout shopify, but pay.js has {len(filled)} Stripe Payment Link(s) ({", ".join(k for k, _ in filled)}). '
                            'Clear them: running both checkouts sells the same phone twice')
        if not opt.shop_url:
            blockers.append('--checkout shopify needs --shop-url https://... (your Shopify store\'s address): each product page\'s '
                            'Order button goes to <shop-url>/products/<handle>, and without it the pages would still take '
                            'email orders beside Shopify and sell the same phone twice')
        blockers.extend(opt.shop_blockers)
        warnings.extend(opt.shop_warnings)
    else:
        if 'pay.js' not in files:
            blockers.append('--checkout stripe, but the site has no pay.js')
        elif not filled:
            blockers.append('--checkout stripe, but every Payment Link in pay.js is empty, so nothing can be paid for. '
                            'Add a link for each phone you hold (rules at the top of pay.js), or choose --checkout shopify')
        shop_pages = [f'{rel}:{line_of(files[rel], pos)}' for rel, tag, pos in pickers(files) if attr(tag, 'data-shop') is not None]
        if shop_pages:
            blockers.append(f'--checkout stripe, but {len(shop_pages)} product page(s) have data-shop (an Order link to Shopify): '
                            f'{", ".join(shop_pages)}. site.js would send those Order buttons to Shopify while the rest of the '
                            'site takes email orders and Payment Links, selling the same phone twice. Remove data-shop from each '
                            '#picker, or use --checkout shopify')
        for k, v in filled:
            if not v.startswith('https://'):
                blockers.append(f'pay.js "{k}": "{v}" is not an https:// link, so site.js ignores it')
            elif not v.startswith('https://buy.stripe.com/'):
                warnings.append(f'pay.js "{k}" is not a buy.stripe.com link: fine only if it is your Stripe custom domain')
        cap = re.search(r"BUY_NOW_MAX\s*=\s*Number\('(\d+)'\)", files.get('site.js', ''))
        prices = pay_prices(files)
        if cap:
            over = [k for k, v in filled if isinstance(prices.get(k), (int, float)) and prices[k] > int(cap.group(1))]
            if over:
                warnings.append(f'pay.js has links for phones priced above the GBP {cap.group(1)} cap (BUY_NOW_MAX), which site.js '
                                f'never shows: {", ".join(over)}')
    # 4. stock: stock.js ({handle: {"128GB|Good": 2}}, the one place to keep it) or a page's older data-stock
    #    attribute ({"128GB|Good": 2}); units held per storage and condition (colour isn't tracked). stock.js wins.
    b, w = stock_check(files, opt.checkout, opt.shop_url, filled if opt.checkout == 'stripe' else ())
    blockers.extend(b)
    warnings.extend(w)
    # 4b. Shopify variant IDs (data-variants / --shop-variants)
    blockers.extend(getattr(opt, 'variant_blockers', []))
    warnings.extend(getattr(opt, 'variant_warnings', []))
    if opt.checkout == 'stripe':
        dv = [rel for rel, tag, _ in pickers(files) if attr(tag, 'data-variants') is not None]
        if dv:
            warnings.append(f'{len(dv)} product page(s) have data-variants (Shopify variant IDs), which only the Shopify route '
                            'uses: harmless here, but remove them if you no longer use Shopify')
    # 5. trade-ins
    if opt.trade_ins == 'open':
        for rel in sorted(files):
            src = files[rel]
            if rel.endswith('.html') and re.search(r'\bid="qt"', src):
                missing = [i for i in QT_SEND_IDS if f'id="{i}"' not in src]
                if missing:
                    blockers.append(f'--trade-ins open, but {rel} has no way to send a quote (missing #{", #".join(missing)}): '
                                    'quote-ui.js would give a quote nobody can accept. Add the send form, or use --trade-ins closed')
    return blockers, warnings


# ----------------------------------------------------------------------------------------------- leftover wording
TEXT, TAG, CODE, LDJSON = 0, 1, 2, 3
# Attributes customers read but scripts also use, so --rewrites never touches them: a person edits these
HAND_ATTRS = {'data-title', 'data-grades', 'data-copy', 'data-model', 'value', 'label'}
# Attributes whose value is only ever shown to people, so --rewrites may change them
TEXT_ATTRS = {'alt', 'title', 'aria-label', 'placeholder'}
# <meta name/property> whose content is wording (description, og:title, twitter:description, og:image:alt ...)
META_TEXT = re.compile(r'(?:^|:)(?:description|title|site_name|alt)$', re.I)


def html_marks(src):
    marks = bytearray(len(src))

    def put(a, b, k):
        marks[a:b] = bytes([k]) * (b - a)
    for m in re.finditer(r'<!--.*?-->|<(script|style)\b[^>]*>.*?</\1\s*>|<[^>]*>', src, re.S | re.I):
        s = m.group(0)
        if s.startswith('<!--'):
            put(m.start(), m.end(), CODE)
        elif m.group(1):
            o = s.index('>') + 1
            c = s.lower().rindex('</')
            put(m.start(), m.start() + o, TAG)
            put(m.start() + c, m.end(), TAG)
            put(m.start() + o, m.start() + c, LDJSON if 'application/ld+json' in s[:o] else CODE)
        else:
            put(m.start(), m.end(), TAG)
    return marks


def js_marks(src):
    """0 code, 1 comment, 2 string (contents) for a JavaScript file; rough but regex-literal aware."""
    marks = bytearray(len(src))
    i, n, last = 0, len(src), ''
    while i < n:
        c = src[i]
        if c == '/' and src.startswith('//', i):
            j = src.find('\n', i)
            j = n if j < 0 else j
            marks[i:j] = b'\x01' * (j - i)
            i = j
            continue
        if c == '/' and src.startswith('/*', i):
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            marks[i:j] = b'\x01' * (j - i)
            i = j
            continue
        if c in '"\'`':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            marks[i + 1:min(j, n)] = b'\x02' * (min(j, n) - i - 1)
            i, last = j + 1, c
            continue
        if c == '/' and (last == '' or last in '(,=:[!&|?{};+-*%<>~^' or re.search(r'\b(?:return|typeof|case)\s*$', src[max(0, i - 8):i])):
            j, cls = i + 1, False
            while j < n and src[j] != '\n':
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == '[':
                    cls = True
                elif src[j] == ']':
                    cls = False
                elif src[j] == '/' and not cls:
                    break
                j += 1
            i, last = j + 1, '/'
            continue
        if not c.isspace():
            last = c
        i += 1
    return marks


def js_literal_is_code(rel, lit):
    """A JS string that is never shown on the live site: preview-only text, or a selector / attribute name."""
    if any(rel.split('/')[-1] == f and lit.startswith(p) for f, p in PREVIEW_ONLY_JS + STRIPE_ONLY_JS):
        return True
    return bool(re.fullmatch(r'[#.\[]?[\w-]+(?:=["\']?[\w-]*["\']?)?\]?', lit))   # e.g. '#qtPreview', 'data-preview'


def classify(rel, src, marks, pos):
    """(kind, snippet_start, snippet_end) for a match at pos that is NOT inside a text segment (see segments()):
    kind is hook (a class, id or attribute name: never shown), hand (customer-facing, but where scripts read it
    too, so a person must edit it), or code (scripts, styles, comments, preview-only script text)."""
    if rel.endswith('.html'):
        k = marks[pos]
        if k == CODE:
            return 'code', pos, pos
        if k in (TEXT, LDJSON):
            a = max(src.rfind('>', 0, pos) + 1, src.rfind('\n', 0, pos) + 1)
            b = min(x for x in (src.find('<', pos), src.find('\n', pos), len(src)) if x >= 0)
            return 'hand', a, b
        ts = src.rfind('<', 0, pos)
        te = src.find('>', pos) + 1
        for am in re.finditer(r'([^\s=<>/"\']+)(?:\s*=\s*"([^"]*)")?', src[ts + 1:te]):
            ns, ne = ts + 1 + am.start(1), ts + 1 + am.end(1)
            if ns <= pos < ne:
                return 'hook', ns, ne
            if am.group(2) is not None:
                vs, ve = ts + 1 + am.start(2), ts + 1 + am.end(2)
                if vs <= pos < ve:
                    return ('hand' if am.group(1).lower() in HAND_ATTRS else 'hook'), vs, ve
        return 'hook', ts, te
    if rel.endswith('.js'):
        if marks[pos] == 2:
            a, b = pos, pos
            while a > 0 and marks[a - 1] == 2:
                a -= 1
            while b < len(src) and marks[b] == 2:
                b += 1
            return ('code' if js_literal_is_code(rel, src[a:b]) else 'hand'), a, b
        return 'code', pos, pos
    if rel.endswith('.css'):
        return 'code', pos, pos
    ls = src.rfind('\n', 0, pos) + 1
    le = src.find('\n', pos)
    le = len(src) if le < 0 else le
    return ('code' if src[ls:le].lstrip().startswith('#') else 'hand'), ls, le


# ----------------------------------------------------------------------------------------------- text segments
# A segment is one run of customer-facing text in one context: an HTML text node, a wording attribute (meta
# description, alt ...), a string in the structured data (JSON-LD), or a JavaScript string shown on the page.
# Its text is what a customer reads: entities (&rsquo;) and escapes (\u003e) decoded, whitespace collapsed.
# Each decoded character remembers where it came from in the file, so a sentence found in the text maps
# back to the exact characters to replace, and the new wording is escaped for that context.
ENTITY_RX = r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);'
TOKEN_RX = {
    'html': re.compile(ENTITY_RX),
    'attr': re.compile(ENTITY_RX),
    'json': re.compile(r'\\(?:u[0-9a-fA-F]{4}|.)', re.S),
    'js': re.compile(r'\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)', re.S),
    'jshtml': re.compile(r'\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)|' + ENTITY_RX, re.S),
}
JS_SIMPLE = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0', '\n': ''}
# Folded for matching only (same length): curly and straight quotes alike
FOLD = str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"'})
# A sentence ends at . ! or ? (plus any closing quote or bracket), then a space, then anything but lower case
SENT_BREAK = re.compile(r'(?<=[.!?])(["\'\u201d\u2019)\]]*)(\s+)(?=[^\sa-z])')
CTX_NAME = {'html': 'page text', 'attr': 'attribute', 'json': 'structured data', 'js': 'script text', 'jshtml': 'script text'}


def decode_token(tok):
    if tok.startswith('&'):
        return html.unescape(tok)
    c = tok[1]
    if c in 'ux' and len(tok) > 2:
        return chr(int(tok[2:], 16))
    return JS_SIMPLE.get(c, c)


class Segment:
    """One run of customer-facing text. text is what a customer reads; starts[i]/ends[i] are where character i of
    text came from in the file (built only when needed: most segments never match anything)."""
    __slots__ = ('rel', 'start', 'end', 'ctx', 'quote', 'text', 'fold', '_src', '_starts', '_ends')

    def __init__(self, rel, src, a, b, ctx, quote=''):
        self.rel, self.start, self.end, self.ctx, self.quote, self._src = rel, a, b, ctx, quote, src
        raw = src[a:b]
        dec = TOKEN_RX[ctx].sub(lambda m: decode_token(m.group(0)), raw) if ('&' in raw or '\\' in raw) else raw
        self.text = re.sub(r'\s+', ' ', dec)
        self.fold = self.text.translate(FOLD)
        self._starts = self._ends = None

    def _build(self):
        chars, starts, ends = [], [], []

        def put(ch, s, e):
            if ch.isspace():
                if chars and chars[-1] == ' ':
                    ends[-1] = e
                    return
                ch = ' '
            chars.append(ch)
            starts.append(s)
            ends.append(e)
        src, i = self._src, self.start
        for m in TOKEN_RX[self.ctx].finditer(src, self.start, self.end):
            for k in range(i, m.start()):
                put(src[k], k, k + 1)
            for ch in decode_token(m.group(0)):
                put(ch, m.start(), m.end())
            i = m.end()
        for k in range(i, self.end):
            put(src[k], k, k + 1)
        if ''.join(chars) != self.text:
            raise Fail(f'internal: {self.rel}:{line_of(src, self.start)}: text decoded two ways differs')
        self._starts, self._ends = starts, ends

    @property
    def starts(self):
        if self._starts is None:
            self._build()
        return self._starts

    @property
    def ends(self):
        if self._ends is None:
            self._build()
        return self._ends

    def index(self, pos):
        """Index in text of the character that raw position pos belongs to."""
        return max(0, bisect.bisect_right(self.starts, pos) - 1)


_SEGMENTS = {}


def segments(rel, src, marks=None):
    """Every customer-facing text segment of one file, in file order (cached: the same text gives the same list)."""
    key = (rel, src)
    if key not in _SEGMENTS:
        _SEGMENTS[key] = _segments(rel, src, marks)
    return _SEGMENTS[key]


def _segments(rel, src, marks=None):
    out = []
    if rel.endswith('.html'):
        marks = html_marks(src) if marks is None else marks
        flat = bytes(marks)
        for m in re.finditer(b'\x00+', flat):
            if src[m.start():m.end()].strip():
                out.append(Segment(rel, src, m.start(), m.end(), 'html'))
        for m in re.finditer(b'\x03+', flat):
            for sm in re.finditer(r'"((?:[^"\\]|\\.)*)"(\s*:)?', src[m.start():m.end()], re.S):
                if not sm.group(2) and sm.group(1).strip():
                    out.append(Segment(rel, src, m.start() + sm.start(1), m.start() + sm.end(1), 'json'))
        for m in re.finditer(r'<([a-zA-Z][\w:-]*)(\s[^>]*)?>', src):
            if marks[m.start()] != TAG or not m.group(2):
                continue
            tag, base = m.group(0), m.start(2)
            meta_text = m.group(1).lower() == 'meta' and META_TEXT.search(attr(tag, 'name') or attr(tag, 'property') or '')
            for am in re.finditer(r'([^\s=<>/"\']+)(?:\s*=\s*"([^"]*)")?', m.group(2)):
                name = am.group(1).lower()
                if am.group(2) and am.group(2).strip() and (name in TEXT_ATTRS or (name == 'content' and meta_text)):
                    out.append(Segment(rel, src, base + am.start(2), base + am.end(2), 'attr'))
    elif rel.endswith('.js'):
        marks = js_marks(src) if marks is None else marks
        for m in re.finditer(b'\x02+', bytes(marks)):
            a, b = m.start(), m.end()
            q = src[a - 1]
            lit = src[a:b]
            if q == '`' or js_literal_is_code(rel, lit) or not lit.strip():
                continue
            if re.search(r'<[a-zA-Z/]', lit):          # HTML in a string (innerHTML): the text between the tags
                for tm in re.finditer(r'[^<>]+', lit):
                    if tm.group(0).strip() and (tm.start() == 0 or lit[tm.start() - 1] != '<'):
                        out.append(Segment(rel, src, a + tm.start(), a + tm.end(), 'jshtml', q))
            else:
                out.append(Segment(rel, src, a, b, 'jshtml' if re.search(ENTITY_RX, lit) else 'js', q))
    out.sort(key=lambda s: s.start)
    return out


def sentence_bounds(text):
    """[(start, end)] of each sentence in text, without surrounding spaces."""
    spans, s = [], 0
    for m in SENT_BREAK.finditer(text):
        spans.append((s, m.end(1)))
        s = m.end(2)
    spans.append((s, len(text)))
    out = []
    for a, b in spans:
        while a < b and text[a] == ' ':
            a += 1
        while b > a and text[b - 1] == ' ':
            b -= 1
        if a < b:
            out.append((a, b))
    return out


def sentence_at(text, i):
    bounds = sentence_bounds(text)
    for a, b in bounds:
        if i < b:
            return a, b
    return bounds[-1] if bounds else (0, len(text))


def covering(segs, starts, pos):
    k = bisect.bisect_right(starts, pos) - 1
    if k >= 0 and segs[k].start <= pos < segs[k].end:
        return segs[k]
    return None


def element_spans(src, id_):
    out = []
    for m in re.finditer(r'<div\b[^>]*\bid="' + re.escape(id_) + r'"[^>]*>', src):
        e = element_end(src, m.start())
        out.append((m.start(), e if e > 0 else len(src)))
    return out


def is_sell_page(rel):
    return rel == 'sell.html' or (rel.startswith('sell/') and rel.endswith('.html'))


def leftovers(files, opt, keep=(), own=()):
    """Preview and checkout wording still in the site, as {category: {snippet: [rel:line, ...]}}.
    rewrite = customer-facing, needs new wording (one sentence per snippet, as a --rewrites key);
    hand = customer-facing, but in a place scripts read too, so a person edits it;
    checkout / checkout-hand = the same, for wording about ordering and paying that doesn't fit --checkout;
    checkout-kept = such wording that your --rewrites keeps as it is (keep: those sentences);
    checkout-own = such wording inside your own new text from --rewrites (own: your new wordings): your decision,
    so it is listed but never blocks;
    hidden = Buy now wording that only shows beside a Payment Link, so never on the Shopify route;
    later = trade-in wording that stays true until trade-ins open; kept = preview hooks deliberately left
    (class, id and attribute names); code = scripts/styles/comments that never show on the live site.
    Preview wording is checked in your new text too: "when we open" is wrong on a live site whoever wrote it."""
    items, seen_locs = {}, set()
    rank = {'rewrite': 0, 'hand': 0, 'checkout': 1, 'checkout-hand': 1, 'later': 2, 'checkout-kept': 3, 'checkout-own': 3,
            'hidden': 3, 'kept': 3, 'code': 4}
    checkout = getattr(opt, 'checkout', None)
    # static route with a Payment Link: Buy now takes payment first, so "before you pay" promises are checkout wording too
    buy_now = checkout == 'stripe' and any(v.strip() for _, v in pay_links(files.get('pay.js', '')))
    crx = CHECKOUT_WORDS['stripe-buy-now'] if buy_now else CHECKOUT_WORDS.get(checkout)
    keep_fold = {norm_text(k).translate(FOLD) for k in keep}
    own_fold = [norm_text(v).translate(FOLD) for v in own if v and norm_text(v)]
    for rel in sorted(files):
        if not rel.endswith(SCAN_EXT):
            continue
        src = files[rel]
        marks = html_marks(src) if rel.endswith('.html') else js_marks(src) if rel.endswith('.js') else None
        segs = segments(rel, src, marks) if rel.endswith(('.html', '.js')) else []
        seg_starts = [g.start for g in segs]
        boxes = element_spans(src, 'qtPreview') if rel.endswith('.html') else []
        sell = is_sell_page(rel)
        for rx, trade in ((SHOP_WORDS, False), (TRADE_WORDS, True)):
            for m in rx.finditer(src):
                pos = m.start()
                loc = f'{rel}:{line_of(src, pos)}'
                seg = covering(segs, seg_starts, pos)
                if seg is not None:
                    a, b = sentence_at(seg.text, seg.index(pos))
                    snippet, kind = seg.text[a:b], 'text'
                else:
                    kind, a, b = classify(rel, src, marks, pos)
                    snippet = src[a:b].strip()
                if kind == 'code':
                    ls = src.rfind('\n', 0, pos) + 1
                    le = src.find('\n', pos)
                    line = src[ls:(len(src) if le < 0 else le)]
                    o = pos - ls
                    snippet = line.strip() if len(line.strip()) <= 160 else '…' + line[max(0, o - 60):o + 100].strip() + '…'
                    cat = 'code'
                elif kind == 'hook':
                    cat = 'kept'
                else:
                    shop = not trade or bool(SHOP_WORDS.search(snippet))
                    in_box = any(x <= pos < y for x, y in boxes)
                    if opt.trade_ins == 'open':
                        cat = 'rewrite'
                    elif in_box or (sell and TRADE_CONTEXT.search(snippet)) or not shop:
                        cat = 'later'      # trade-in wording: still true while trade-ins are closed
                    else:
                        cat = 'rewrite'
                    if cat == 'rewrite' and kind == 'hand':
                        cat = 'hand'
                if cat == 'code' and loc in seen_locs:
                    continue   # one entry per line of code
                seen_locs.add(loc)
                key = (snippet, loc)
                if key not in items or rank[cat] < rank[items[key]]:
                    items[key] = cat
        # checkout wording: only what customers read (code, comments and hooks never show)
        if crx is None or not rel.endswith(('.html', '.js')):
            continue
        hidden = [(m.start(), m.end()) for m in STRIPE_ONLY_HTML.finditer(src)] if opt.checkout == 'shopify' else []
        for m in crx.finditer(src):
            pos = m.start()
            loc = f'{rel}:{line_of(src, pos)}'
            seg = covering(segs, seg_starts, pos)
            if seg is None:
                kind, a, b = classify(rel, src, marks, pos)
                if kind != 'hand':
                    continue
                snippet, cat = src[a:b].strip(), 'checkout-hand'
            else:
                a, b = sentence_at(seg.text, seg.index(pos))
                snippet = seg.text[a:b]
                sf = snippet.translate(FOLD)
                cat = ('hidden' if any(x <= pos < y for x, y in hidden)
                       else 'checkout-kept' if sf in keep_fold
                       else 'checkout-own' if any(sf in o for o in own_fold) else 'checkout')
            if buy_now and not re.search(_CHECKOUT_BOTH, m.group(0), re.I) and EMAIL_ORDER_ONLY.search(snippet):
                continue   # limited to email orders (you order, we reply, then you pay), so still true beside Buy now
            if checkout == 'shopify' and EMAIL_ORDER_ONLY.fullmatch(m.group(0)) and REPLACED_PART.search(snippet):
                continue   # "replaced-part phones are sold by email order": still true on Shopify (GO-LIVE.md section 4)
            key = (snippet, loc)
            if key not in items or rank[cat] < rank[items[key]]:
                items[key] = cat
    out = {}
    for (snippet, loc), cat in items.items():
        out.setdefault(cat, {}).setdefault(snippet, [])
        if loc not in out[cat][snippet]:
            out[cat][snippet].append(loc)
    return out


def wording_left(left):
    """(pieces, places) of preview wording that must change before the site can go live."""
    groups = list(left.get('rewrite', {}).values()) + list(left.get('hand', {}).values())
    return len(groups), sum(len(v) for v in groups)


def checkout_left(left):
    """(pieces, places) of checkout wording that doesn't fit --checkout and must change before going live."""
    groups = list(left.get('checkout', {}).values()) + list(left.get('checkout-hand', {}).values())
    return len(groups), sum(len(v) for v in groups)


# ----------------------------------------------------------------------------------------------- rewrites
def norm_text(s):
    """A --rewrites key or new wording as plain text: entities decoded, whitespace collapsed."""
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def load_rewrites(path):
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        raise Fail(f'--rewrites {path}: {e}')
    if not isinstance(data, dict) or not all(isinstance(k, str) and k and (v is None or isinstance(v, str)) for k, v in data.items()):
        raise Fail(f'--rewrites {path} must be a JSON object of "exact text": "new text" (or null to skip)')
    rewrites, skipped, bad = {}, [], []
    for k, v in data.items():
        if v is None:
            skipped.append(k)
            continue
        key, new = norm_text(k), norm_text(v)
        if not key:
            bad.append(f'"{show(k, 60)}": the text to find is empty')
            continue
        if '<' in new or '>' in new:
            bad.append(f'"{show(k, 60)}": the new wording has < or >. Rewrites are plain text, so tags can\'t go in them: '
                       'keep links and bold on the page as they are, and rewrite the text around them')
            continue
        if key in rewrites and rewrites[key] != new:
            bad.append(f'"{show(k, 60)}" is in the file twice with different new wording')
            continue
        rewrites[key] = new
    if bad:
        raise Fail(f'--rewrites {path}: {len(bad)} problem(s), nothing written:\n  - ' + '\n  - '.join(bad))
    return rewrites, sorted(skipped)


def encode(plain, seg):
    """plain text, made safe for the place it goes."""
    if seg.ctx == 'html':
        return plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if seg.ctx == 'attr':
        return plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    if seg.ctx == 'json':
        return json.dumps(plain, ensure_ascii=False)[1:-1].replace('<', '\\u003c').replace('>', '\\u003e')
    s = plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') if seg.ctx == 'jshtml' else plain
    s = s.replace('\\', '\\\\').replace(seg.quote, '\\' + seg.quote)
    return s.replace('\n', '\\n').replace('\r', '\\r').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def match_rewrites(files, keys):
    """Where each key would apply. Returns (hits, clashes, found): hits are (segment, start, end, key) in decoded
    text, with a key that sits inside a longer key at the same place dropped (the longer one wins); clashes are
    the places where two keys partly overlap; found is the set of keys found anywhere."""
    folded = {k: k.translate(FOLD) for k in keys}
    hits, clash_at, found = [], {}, set()
    for rel in sorted(files):
        if not rel.endswith(('.html', '.js')):
            continue
        src = files[rel]
        for seg in segments(rel, src):
            hs = []
            for key, fk in folded.items():
                i = seg.fold.find(fk)
                while i >= 0 and fk:
                    hs.append((seg, i, i + len(fk), key))
                    i = seg.fold.find(fk, i + len(fk))
            if not hs:
                continue
            hs.sort(key=lambda h: (h[1], -(h[2] - h[1])))
            kept = []
            for h in hs:
                found.add(h[3])
                if any(k[1] <= h[1] and h[2] <= k[2] for k in kept):
                    continue
                other = next((k for k in kept if h[1] < k[2] and k[1] < h[2]), None)
                if other:
                    clash_at.setdefault((other[3], h[3]), []).append(f'{rel}:{line_of(src, seg.starts[h[1]])}')
                    continue
                kept.append(h)
            hits.extend(kept)
    clashes = [f'two of your texts overlap: "{show(a, 70)}" and "{show(b, 70)}", at {", ".join(dict.fromkeys(locs))}. '
               'Use one or the other, or split them into separate sentences' for (a, b), locs in clash_at.items()]
    return hits, clashes, found


def found_whole(files, texts):
    """The texts that appear somewhere as a whole run of words (not inside a longer word): an earlier run's rewrite."""
    rx = {t: re.compile(r'(?<!\w)' + re.escape(t.translate(FOLD)) + r'(?!\w)') for t in texts if t}
    out = set()
    for rel in sorted(files):
        if rel.endswith(('.html', '.js')) and len(out) < len(rx):
            for seg in segments(rel, files[rel]):
                out.update(t for t, r in rx.items() if t not in out and r.search(seg.fold))
    return out


def follow_domain(t, bare, host, old_host):
    """t with the site's old web address and email domain moved to the new ones (--domain), as the switch moves them."""
    if old_host:
        ob = old_host[4:] if old_host.startswith('www.') else old_host
        t = re.sub(r'https?://(?:www\.)?' + re.escape(ob), 'https://' + host, t)
        t = re.sub(r'(?<=@)' + re.escape(ob), bare, t)
    return t


def rewrite_edits(files, rewrites, bare, host, old_host):
    """The edits for your --rewrites. Refuses (Fail, listing every problem) if a text is nowhere, two texts
    partly overlap, or new wording can't go where its text is."""
    rw = {}
    for k, v in rewrites.items():
        rw.setdefault(follow_domain(k, bare, host, old_host), follow_domain(v, bare, host, old_host))
    hits, problems, found = match_rewrites(files, list(rw))
    notes = []
    missing = [k for k in rw if k not in found]
    if missing:
        already = found_whole(files, [rw[k] for k in missing if rw[k]])
        # your new wording for another entry in the same file, also "kept as it is": nothing to keep until this run
        # puts it on the pages (and it is never flagged: wording you wrote is your decision)
        others = [v.translate(FOLD) for k2, v in rw.items() if v and v != k2]
        for k in missing:
            if rw[k] and rw[k] in already:
                notes.append(f'--rewrites: "{show(k, 80)}" is on no page, but your new wording is: taken as already done.')
            elif rw[k] == k and any(k.translate(FOLD) in o for o in others):
                notes.append(f'--rewrites: "{show(k, 80)}" is your new wording for another sentence in the same file, so it '
                             'isn\'t on the pages yet: nothing to keep. (You don\'t need it as a key: your own wording is never '
                             'listed as checkout wording.)')
            else:
                problems.append(f'not on any page (copy it exactly from the report or the template'
                                f'{"; if you deleted it in an earlier run, set it to null" if not rw[k] else ""}): "{show(k, 120)}"')
    edits, last_end = [], {}
    for seg, ds, de, key in sorted(hits, key=lambda h: (h[0].rel, h[0].start, h[1])):
        new, text = rw[key], seg.text
        if new == key:
            continue   # kept as it is (a checkout sentence that is still true): nothing to change
        prev = last_end.get(id(seg), 0)
        if not new:   # deleting a sentence: take one neighbouring space with it, but never the space next to a tag
            if ds > 1 and text[ds - 1] == ' ' and ds - 1 >= prev:
                ds -= 1
            elif de + 1 < len(text) and text[de] == ' ':
                de += 1
        last_end[id(seg)] = de
        if seg.ctx in ('js', 'jshtml') and seg.quote not in '\'"':
            problems.append(f'{seg.rel}:{line_of(files[seg.rel], seg.start)}: "{show(key, 80)}" is in a script string '
                            'this tool can\'t safely change; edit it by hand')
            continue
        edits.append(Edit(seg.rel, seg.starts[ds], seg.ends[de - 1], encode(new, seg),
                          f'your rewrite (--rewrites), {CTX_NAME[seg.ctx]}'))
    if problems:
        raise Fail(f'--rewrites: {len(problems)} problem(s), nothing written:\n  - ' + '\n  - '.join(problems))
    return edits, notes


def template_keys(files, left):
    """The --rewrites-template keys: every preview or checkout sentence still to rewrite, minus any that only ever
    sits inside a longer one (it could never apply), with notes for any two that partly overlap."""
    keys = sorted(set(left.get('rewrite', {})) | set(left.get('checkout', {})))
    hits, clashes, _ = match_rewrites(files, keys)
    used = {h[3] for h in hits}
    notes = [f'--rewrites-template: fill in only one of these: {c}' for c in clashes]
    return [k for k in keys if k in used], notes


# ----------------------------------------------------------------------------------------------- checks after
TAG_TOKEN = re.compile(r'<!--.*?-->|<(/?)([a-zA-Z][\w:-]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*)>', re.S)
ATTR_NAME = re.compile(r'([^\s=/"\'>]+)(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\'>]+))?')


def shape(rel, src):
    """The tags and attribute names of a page, or the code (strings left out) of a script, in order. A rewrite
    changes wording only, so it must never change this: a stray quote or tag would."""
    if rel.endswith('.html'):
        return [(m.group(1), m.group(2).lower(), tuple(a.group(1).lower() for a in ATTR_NAME.finditer(m.group(3))))
                for m in TAG_TOKEN.finditer(src) if m.group(2)]
    if rel.endswith('.js'):
        return ''.join(c for c, k in zip(src, js_marks(src)) if k != 2)
    return None


def rewrite_damage(before, after, rels):
    """Files where a rewrite changed the markup or script structure (a stray quote, a tag): [] when none."""
    bad = []
    for rel in sorted(rels):
        if shape(rel, before[rel]) != shape(rel, after[rel]):
            bad.append(f'{rel}: your rewrite changed the page\'s tags or script, not just its wording')
    return bad


LDJSON_BLOCK = re.compile(r'<script\b[^>]*\btype="application/ld\+json"[^>]*>(.*?)</script\s*>', re.S | re.I)


def verify(files, opt, new_host, old_host_changed):
    """What must be true of a switched site. [] when all good."""
    bad = []
    checkout, shop_url = getattr(opt, 'checkout', None), getattr(opt, 'shop_url', None)
    long_date = f'{opt.launch_date.day} {opt.launch_date:%B %Y}'
    for rel in sorted(files):
        src = files[rel]
        if not rel.endswith('.html'):
            continue
        for m in re.finditer(r'<meta\b[^>]*\bname="robots"[^>]*>', src):
            if 'noindex' in (attr(m.group(0), 'content') or '').lower() and rel not in NO_INDEX_KEEP:
                bad.append(f'{rel}: still noindex')
        if re.search(r'class="preview-bar\b', src):
            bad.append(f'{rel}: preview banner still there')
        for m in re.finditer(r'<[a-zA-Z][^>]*?\sdata-preview\b[^>]*>', src):
            if not (opt.trade_ins == 'closed' and attr(m.group(0), 'id') == 'qt'):
                bad.append(f'{rel}:{line_of(src, m.start())}: data-preview still on <{m.group(0)[1:].split()[0]} id="{attr(m.group(0), "id")}">')
        if re.search(r'class="[^"]*\bpreview-note\b', src):
            bad.append(f'{rel}: "Not trading yet" box still there')
        if opt.trade_ins == 'open' and 'id="qtPreview"' in src:
            bad.append(f'{rel}: trade-in "open soon" note still there')
        if rel.startswith('products/'):
            ob = re.search(r'<(\w+)\b[^>]*\bid="orderBtn"[^>]*>', src)
            if not ob or ob.group(1).lower() != 'a' or not attr(ob.group(0), 'href'):
                bad.append(f'{rel}: Order control is not a link with an href ({ob.group(0) if ob else "missing"})')
            pk = PICKER_TAG.search(src)
            shop = attr(pk.group(0), 'data-shop') if pk else None
            if checkout == 'shopify' and pk:
                want = f'{shop_url}/products/{page_handle(rel)}' if shop_url else None
                link = shop_href(shop, page_variants(pk.group(0)), src) if shop else None
                if not shop or not SHOP_URL.fullmatch(shop) or (want and shop != want):
                    bad.append(f'{rel}: data-shop is {shop!r}, not the page\'s Shopify product ({want or "an https:// address"})')
                elif ob and ob.group(1).lower() == 'a' and attr(ob.group(0), 'href') != link:
                    bad.append(f'{rel}: Order link goes to {attr(ob.group(0), "href")}, not the Shopify product {link}')
                elif ob and ob.group(1).lower() == 'a' and link == shop:
                    # no variant ID for the phone ticked in the HTML: Shopify opens on its own first variant, so the
                    # no-JavaScript link must say so rather than "Order" beside our price
                    tm = re.search(r'<a\b[^>]*\bid="orderBtn"[^>]*>(.*?)</a>', src, re.S)
                    text = html.unescape(re.sub(r'<[^>]+>', '', tm.group(1))).strip() if tm else ''
                    if text != HANDOFF_LABEL:
                        bad.append(f'{rel}: Order link opens Shopify on its own first variant but reads "{text}", '
                                   f'not "{HANDOFF_LABEL}"')
                if getattr(opt, 'variants_data', None) is not None:
                    expect = getattr(opt, 'variant_maps', {}).get(rel) or {}
                    if page_variants(pk.group(0)) != expect:
                        bad.append(f'{rel}: data-variants doesn\'t hold the {len(expect)} variant ID(s) from --shop-variants')
                if '?order=' in src:
                    bad.append(f'{rel}: has an email-order link (?order=) on the Shopify route')
            elif checkout == 'stripe' and shop is not None:
                bad.append(f'{rel}: data-shop is still on the page with --checkout stripe')
        if 'id="contactForm"' in src:
            topic = re.search(r'<option\b[^>]*>\s*Order a phone\s*</option>', src)
            if checkout == 'shopify' and topic:
                bad.append(f'{rel}: contact form still has the "Order a phone" topic on the Shopify route (email orders beside Shopify)')
            elif checkout != 'shopify' and not topic:
                bad.append(f'{rel}: contact form has no "Order a phone" topic')
        if opt.set_dates:
            for m in re.finditer(r'<p\b[^>]*\bclass="legal-updated"[^>]*>([^<]*)</p>', src):
                if m.group(1).strip() != f'Last updated {long_date}':
                    bad.append(f'{rel}: "{m.group(1).strip()}" is not the launch date')
        for m in re.finditer(r'<link\b[^>]*\brel="canonical"[^>]*>', src):
            if not (attr(m.group(0), 'href') or '').startswith(f'https://{new_host}/'):
                bad.append(f'{rel}: canonical {attr(m.group(0), "href")} is not on https://{new_host}/')
        for m in LDJSON_BLOCK.finditer(src):
            try:
                json.loads(m.group(1))
            except ValueError as e:
                bad.append(f'{rel}:{line_of(src, m.start(1))}: structured data (JSON-LD) is no longer valid JSON ({e})')
    bad.extend(stock_mark_problems(files, checkout))
    if 'robots.txt' not in files or robots_blocks_all(files['robots.txt']):
        bad.append('robots.txt does not allow crawling')
    sm = files.get('sitemap.xml')
    if sm is not None:
        for m in re.finditer(r'<lastmod>([^<]*)</lastmod>', sm) if opt.set_dates else ():
            if m.group(1).strip() != opt.launch_date.isoformat():
                bad.append(f'sitemap.xml: lastmod {m.group(1)} is not the launch date')
                break
        for m in re.finditer(r'<loc>([^<]*)</loc>', sm):
            if not m.group(1).startswith(f'https://{new_host}/'):
                bad.append(f'sitemap.xml: {m.group(1)} is not on https://{new_host}/')
    if old_host_changed:
        ob = old_host_changed[4:] if old_host_changed.startswith('www.') else old_host_changed
        nb = new_host[4:] if new_host.startswith('www.') else new_host
        # the old bare domain must be gone; if only www changed, every page address must be on the new host
        rx = (re.escape(ob) + r'(?![\w-]|\.\w)') if ob != nb else \
            (r'https?://(?!' + re.escape(new_host) + r'(?![\w-]|\.\w))(?:www\.)?' + re.escape(ob))
        left = [rel for rel, src in files.items() if re.search(rx, src, re.I)]
        if left:
            bad.append(f'old address {old_host_changed} still in: {", ".join(sorted(left))}')
    return bad


def in_preview(files):
    """True while any preview switch is still on: banner, noindex, data-preview on a picker or the contact
    form, or robots.txt shutting out every crawler. Then this run is the launch, and sets the dates."""
    for rel, src in files.items():
        if not rel.endswith('.html'):
            continue
        if re.search(r'class="preview-bar\b', src):
            return True
        if rel not in NO_INDEX_KEEP and any('noindex' in (attr(m.group(0), 'content') or '').lower()
                                            for m in re.finditer(r'<meta\b[^>]*\bname="robots"[^>]*>', src)):
            return True
        if re.search(r'<(?:form)\b[^>]*\bid="(?:picker|contactForm)"[^>]*\sdata-preview\b', src):
            return True
    return 'robots.txt' in files and robots_blocks_all(files['robots.txt'])


# ----------------------------------------------------------------------------------------------- report
def manual_items(opt, files):
    pages = sum(1 for r in files if r.startswith('products/') and r.endswith('.html'))
    items = []
    shop = getattr(opt, 'shop_url', None) or '<shop-url>'
    if opt.checkout == 'shopify':
        items.append(f'Shopify: set the products to Active and publish them (GO-LIVE.md section 5). Every product page\'s Order '
                     f'button now goes to {shop}/products/<handle> (data-shop), and there is no email-order route beside it '
                     '(no "Order a phone" topic, no ?order= links). Keep each Shopify URL handle exactly as products-shopify.csv '
                     'has it, or that Order button lands on a "page not found".')
        vm = getattr(opt, 'variant_maps', {})
        mapped = sum(len(v) for v in vm.values())
        if mapped:
            items.append(f'Shopify variants: {mapped} phone choice(s) on {len(vm)} page(s) open Shopify on exactly that variant '
                         '(?variant=<id>, "Order — £…"); any choice without an ID reads "Choose and pay on the next page". '
                         'Whenever you add, delete or re-import variants in Shopify, fetch the IDs again with '
                         'fetch_shopify_variants.py and rerun this with --shop-variants (GO-LIVE.md section 5, step 13). '
                         'Then deploy the site to your web host again.')
        else:
            items.append('Shopify variants: every Order button reads "Choose and pay on the next page" and opens Shopify on its '
                         'own first variant, so the customer picks storage, condition and colour again there. Once the products '
                         f'are active and published, run: python3 launch/full-bars/fetch_shopify_variants.py --shop-url {shop} '
                         '--out ~/shopify-variants.json, then rerun this with --shop-variants ~/shopify-variants.json, so each '
                         'button opens the phone chosen at the price shown, and deploy the site again (GO-LIVE.md section 5, '
                         'step 13).')
        items.append('Shopify prices: Shopify must charge exactly the site\'s prices. Before every deploy, and after every price '
                     f'change, run: python3 launch/full-bars/fetch_shopify_variants.py --shop-url {shop} --check-prices '
                     '--site <this site folder>. It must end "Price check: passed" (exit 0): it lists every variant whose '
                     'Shopify price differs from the site, with both prices. Before a deploy it must be a live fetch '
                     '(--shop-url), not --from-dump: a saved copy only shows what Shopify charged when it was fetched, and '
                     'never ends "Price check: passed". Change a price in Shopify admin (Products > Bulk '
                     'edit, Price column) in the same sitting as set_prices.py, never by importing the CSV again (that puts '
                     'every product back to draft, unpublished, with stock 0), then run the check and deploy (GO-LIVE.md '
                     'section 1, item 6).')
        snap = stock_snapshot(files.get(STOCK_JS))
        if snap:
            as_of = (f'as of {snap.when:%Y-%m-%d %H:%M} UTC ({age_words(snap.when)})' if snap.when else
                     'as of an unknown time (from a saved copy that doesn\'t say when it was fetched)')
            items.append(f'Stock snapshot: {STOCK_JS} holds Shopify\'s stock for {snap.phones} phone(s) {as_of}, so each page '
                         'shows "Not in stock — ask us" for a storage and condition Shopify can\'t sell, and "None in stock right '
                         'now" on the cards of a phone with nothing available. It is right only until stock changes: fetch it '
                         f'again from the live store (fetch_shopify_variants.py --shop-url {shop} --write-stock <this site '
                         f'folder>/{STOCK_JS}, not --from-dump, which only repeats an old copy) and deploy the site whenever '
                         'stock changes in Shopify, straight after you add stock and at least daily, and just before every '
                         'deploy. A stale snapshot never sells a phone Shopify doesn\'t have, but a phone sold since still shows '
                         'as in stock (its button opens a sold-out Shopify page) and a phone added since shows "Not in stock — '
                         'ask us" (GO-LIVE.md section 5, step 13).')
        else:
            items.append(f'Stock on the site (optional, recommended): {STOCK_JS} has no Shopify stock snapshot, so every storage '
                         'and condition shows as orderable and a sold-out choice lands on a sold-out Shopify page. To show '
                         'what Shopify has, run fetch_shopify_variants.py --shop-url '
                         f'{shop} --write-stock <this site folder>/{STOCK_JS}, deploy, and repeat whenever stock changes '
                         '(GO-LIVE.md section 5, step 13).')
        items.append('Shopify stock: add stock only for units with all original manufacturer parts. A unit with any replaced '
                     'part stays at 0 on Shopify and is sold by email order: the customer asks through the contact page, you '
                     'tell them which part was replaced, then send a Shopify draft order (a custom item whose title names the '
                     'replaced part) as an invoice for them to pay. Never a Payment Link: pay.js stays empty on this route '
                     '(GO-LIVE.md section 4).')
        items.append('Keep the static site live as the information front (warranty, grading standard, FAQ, delivery and returns '
                     'with the cancellation form, terms, privacy, cookies, sell pages and guides), or carry those pages into '
                     'Shopify before you retire it (GO-LIVE.md section 5, step 12).')
        items.append('Order confirmation: paste launch/full-bars/order-confirmation-email.html into Shopify\'s Settings > '
                     'Notifications > Order confirmation, and send the unit email in order-confirmation-email.md (exact phone, '
                     'battery %, parts) within 1 working day of each order. Decide the IMEI question at the top of both files '
                     'first. Place a test order and read the email before launch: the law wants the order confirmed, with the '
                     'cancellation rights and form, on a durable medium such as email (GO-LIVE.md section 5, step 11).')
    elif opt.checkout == 'stripe':
        filled = [k for k, v in pay_links(files.get('pay.js', '')) if v.strip()]
        items.append(f'Stripe: pay.js has {len(filled)} Payment Link(s). One link per unit: each must have "Limit the number of '
                     'payments" ticked (in the link\'s settings in Stripe) and set to 1, with the quantity fixed at 1, so Stripe '
                     'deactivates it once that payment has completed. Even so, the moment a phone sells, still clear its link '
                     'in pay.js and lower its count in stock.js (next item), then deploy: otherwise the page keeps a Buy now '
                     'button that opens Stripe\'s deactivated-link message. If you hold another unit of that storage and '
                     'condition, make a new link for it (same price and settings) and paste it in. Stripe\'s docs don\'t say '
                     'what happens to a second checkout already open when the first one completes, so check each Stripe '
                     'payment against stock.js before dispatch and refund any payment for a phone already sold '
                     '(GO-LIVE.md section 6, step 1).')
        items.append(f'Stock: change {STOCK_JS} (and only {STOCK_JS}) the moment a phone sells or arrives: units held per storage '
                     'and condition for each phone (GO-LIVE.md section 6, step 2). After every edit, and again just before every '
                     'deploy, run python3 launch/full-bars/set_prices.py --check <this site folder>: it reads stock.js as a '
                     'browser does and fails on a typo. Then deploy the site to your web host again. If a broken stock.js '
                     'goes up anyway, the pages fail closed (data-stock-required): every phone shows "Not in stock — ask '
                     'us" and "None in stock right now", with nothing to order, and the browser console names stock.js.')
        prices, units = pay_prices(files), pay_units(files)
        listed = ', '.join((f'{k} ({gbp(prices[k])}' + (', none held: deactivate and clear it)' if units.get(k) == 0 else ')'))
                           if k in prices else f'{k} (no such phone on the site)' for k in filled)
        items.append('Stripe prices: a Payment Link charges the price it was made with, and nothing here can read it (Stripe\'s '
                     'API refuses any request without your API key, which must never be in this repo). After every deploy, open every Buy now '
                     'button on the live site and check the Stripe page shows the same price as the button, and in Stripe '
                     'that the link has a payment limit of 1. Each link should charge the site\'s price: '
                     f'{listed or "none yet"}. A link at any other price: deactivate it, make a new one at the site\'s price '
                     'with the same settings and paste it into pay.js. Change prices only with set_prices.py --set, which '
                     'lists every changed price that has a link; set_prices.py --check lists them all (GO-LIVE.md section 6, '
                     'step 1, and section 7).')
        items.append('Order confirmation: send launch/full-bars/order-confirmation-email.md, filled in, as the confirmation '
                     'email for every order (Stripe\'s receipt doesn\'t carry the cancellation rights and form). Decide the '
                     'IMEI question at the top of that file first. Send one to yourself from a test order before launch '
                     '(GO-LIVE.md section 6, step 7).')
    items.append(f'Deploy the switched folder to your web host at https://{opt.host}/, with HTTPS on, and do the hosting '
                 'checks in GO-LIVE.md section 7: robots.txt, sitemap.xml and every page the sitemap lists must answer 200 '
                 'at that exact address (a product page at products/<handle>.html, not a redirect to an address without '
                 '.html, which some hosts do by default), a made-up address must show the 404 page with a 404 status, and '
                 'the links in the confirmation emails must open. The claude.ai artifact stays a preview copy: don\'t '
                 'publish the switched folder there. Then put one real order through end to end, and refund it.')
    if opt.checkout == 'shopify':
        items.append(f'Open all {pages} product pages on the live site. Each needs a clickable button that goes to its own '
                     f'product at {shop}: "Order — £…" for a choice with a Shopify variant ID (Shopify must open on that '
                     'storage, condition and colour, at that price), "Choose and pay on the next page" for one without ("Not in '
                     'stock — ask us" for a storage and condition the stock snapshot says Shopify can\'t sell), and the price '
                     'must change when you change storage, condition or colour. With a snapshot, a phone with nothing available '
                     'must show "None in stock right now" on its cards. "Opening soon" or greyed-out options mean site.js '
                     'didn\'t load or data-prices is wrong (GO-LIVE.md section 6, step 3).')
    else:
        items.append(f'Open all {pages} product pages on the live site. Each needs a clickable "Order — £…" button '
                     '("Buy now — £…" with a Payment Link, "Not in stock — ask us" for an option you don\'t hold) that '
                     'changes when you change storage, condition or colour, and a phone stock.js lists with no units must show '
                     '"None in stock right now" on its cards. "Opening soon" or greyed-out options mean site.js didn\'t '
                     'load or data-prices is wrong (GO-LIVE.md section 6, step 3). Every phone "Not in stock" when you hold '
                     'some means stock.js is broken or not deployed: the browser console says why ("Full Bars: stock.js ...").')
    items.append('Open sell.html: the quote questions must appear, not "The instant quote hasn\'t loaded".')
    if opt.trade_ins == 'closed':
        items.append('Trade-ins stay closed: the quote tool still gives guide prices only. To open them, add a quote-sending form '
                     f'(#{", #".join(QT_SEND_IDS)}, as quote-ui.js expects) to sell.html and the sell/*.html pages, confirm the '
                     'trade-in prices (GO-LIVE.md section 1, item 7), then run this again with --trade-ins open.')
    if any(PRIVACY_QUOTE_TOOL in g.text and 'this tab' not in g.text
           for g in segments('privacy.html', files.get('privacy.html', ''))):
        items.append(f'privacy.html still says "{PRIVACY_QUOTE_TOOL}" while cookies.html says the quote tool keeps your answers '
                     'in your browser for this tab only. Make them say the same thing: add that sentence to your --rewrites '
                     'file, for example "The quote tool works in your browser: it keeps your answers there for this tab only, '
                     'and they\'re never sent to us." (GO-LIVE.md section 7).')
    items.append('Check the sections it can\'t judge: VAT line in the footers, WEEE take-back wording, the privacy policy naming '
                 'your host and email provider (GO-LIVE.md sections 1 to 3).')
    return items


def group_lines(groups, indent='    '):
    out = []
    for snippet, locs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[1][0])):
        files_n = len({x.rsplit(':', 1)[0] for x in locs})
        out.append(f'{indent}- {files_n} file{"s" if files_n != 1 else ""}: {show(snippet)}')
        out.append(f'{indent}  at {", ".join(locs)}')
    return out


def build_report(mode, site, opt, edits, edited_from, notes, blockers, warnings, left, rewrite_skipped, result):
    L = []
    L.append(f'Full Bars go-live switch: {mode}')
    L.append(f'Site: {os.path.abspath(site)}')
    dates = (f'{opt.launch_date.day} {opt.launch_date:%B %Y}' if opt.set_dates else 'left as they are (site already live)')
    L.append(f'Domain: {opt.bare} (pages at https://{opt.host}/, email hello@{opt.bare})   Checkout: {opt.checkout or "NOT CHOSEN"}'
             + (f' ({opt.shop_url or "NO --shop-url"})' if opt.checkout == 'shopify' else '')
             + f'   Trade-ins: {opt.trade_ins}   Launch date: {dates}')
    if edits is not None:
        L.append('')
        changed_files = len({e.rel for e in edits})
        L.append(f'CHANGES ({len(edits)} in {changed_files} file{"s" if changed_files != 1 else ""}; '
                 f'{"none written: dry run" if mode.startswith("DRY") else "written" if mode.startswith(("DONE", "WRITTEN")) else "none written"})')
        L.append('  Line numbers are in the file as it was before the switch, except for your --rewrites, which are in the switched file.')
        for e in edits:
            L.append(describe(edited_from[e], e))
        kinds = {}
        for e in edits:
            # one summary line per kind of change: addresses that differ page by page are left out
            k = re.sub(r':.*', '', e.what) if e.prio else re.sub(r' \(https?://[^)]*\)$| -> (?:https?://|\.\./)\S+$', '', e.what)
            kinds[k] = kinds.get(k, 0) + 1
        L.append('  Summary:')
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            L.append(f'    {n:4d}  {k}')
    if left is not None:
        L.append('')
        rw, hand = left.get('rewrite', {}), left.get('hand', {})
        pieces, places = wording_left(left)
        L.append('STILL TO DO BY HAND')
        if pieces:
            L.append(f'  1. Rewrite the preview wording: {pieces} piece(s) of text in {places} place(s). It says the shop isn\'t '
                     'open, or talks about opening in the future, so it can\'t be switched mechanically, and a real run refuses '
                     'while any of it is left (unless you pass --allow-preview-wording: then don\'t deploy until it\'s done). '
                     'Each sentence is shown as a customer reads it, which is exactly the key to put in a --rewrites file '
                     '(--rewrites-template writes them all for you).')
            L.extend(group_lines(rw))
            if hand:
                L.append('    Edit these by hand: scripts read these attributes too, so --rewrites leaves them alone.')
                L.extend(group_lines(hand, '      '))
        else:
            L.append('  1. Preview wording: none left on the pages.')
        cw, cwh = left.get('checkout', {}), left.get('checkout-hand', {})
        cpieces, cplaces = checkout_left(left)
        if cpieces:
            why = ('your Order buttons go to Shopify, so anything about Stripe, Buy now buttons, payment links, ordering by '
                   'email or confirming before you pay must say how Shopify checkout works. That includes terms section 3 '
                   '(when the contract is made) and the FAQ\'s "How do I pay?" answer (GO-LIVE.md section 5, step 7)'
                   if opt.checkout == 'shopify' else
                   'it describes a payment provider you only intend to use, or (because pay.js has Payment Links) it '
                   'promises to confirm or send something before you pay, or to answer "when you order", which a Buy now '
                   'payment doesn\'t wait for. Limit such a promise to email orders ("On an email order we ...") or reword it')
            L.append(f'    Checkout wording that doesn\'t fit --checkout {opt.checkout}: {cpieces} piece(s) of text in {cplaces} '
                     f'place(s). Rewrite it in the same --rewrites file: {why}. A sentence that is still true can stay: give '
                     'it its own text as the new wording.')
            L.extend(group_lines(cw))
            if cwh:
                L.append('    Edit these by hand: scripts read these attributes too, so --rewrites leaves them alone.')
                L.extend(group_lines(cwh, '      '))
        elif opt.checkout:
            L.append(f'    Checkout wording: nothing left that contradicts --checkout {opt.checkout}.')
        if left.get('checkout-kept'):
            L.append('    Checkout wording you kept as it is (your --rewrites gives it its own text):')
            L.extend(group_lines(left['checkout-kept'], '      '))
        if left.get('checkout-own'):
            L.append('    Checkout words in your own new wording (from your --rewrites; your decision, so not blocking). Check '
                     f'each is true for --checkout {opt.checkout}:')
            L.extend(group_lines(left['checkout-own'], '      '))
        if rewrite_skipped:
            L.append(f'    ({len(rewrite_skipped)} entr{"y" if len(rewrite_skipped) == 1 else "ies"} in your --rewrites file still null, so skipped)')
        for i, item in enumerate(manual_items(opt, result), 2):
            L.append(f'  {i}. {item}')
        if left.get('later'):
            L.append('')
            L.append('LEFT FOR WHEN TRADE-INS OPEN (true while they are closed; rewrite these when you run with --trade-ins open)')
            L.extend(group_lines(left['later']))
        if left.get('hidden'):
            L.append('')
            L.append('SHOWN ONLY BESIDE A STRIPE BUY NOW LINK (hidden on every Shopify-route page: no action)')
            L.extend(group_lines(left['hidden']))
        if left.get('kept'):
            L.append('')
            L.append('PREVIEW HOOKS KEPT ON PURPOSE (trade-ins closed: the quote tool stays in guide-price mode)'
                     if opt.trade_ins == 'closed' else 'PREVIEW HOOKS LEFT (class, id and attribute names: never shown to customers)')
            L.extend(group_lines(left['kept']))
        if left.get('code'):
            L.append('')
            L.append('CODE THAT MENTIONS PREVIEW (no action: it only runs while data-preview is on, or it is a comment or a style)')
            L.extend(group_lines(left['code']))
    if notes:
        L.append('')
        L.append('NOTES')
        L.extend(f'  - {n}' for n in dict.fromkeys(notes))
    if warnings:
        L.append('')
        L.append(f'WARNINGS ({len(warnings)}: worth fixing, not blocking)')
        L.extend(f'  - {w}' for w in warnings)
    L.append('')
    if blockers:
        L.append(f'BLOCKERS ({len(blockers)}): fix these first, then run again')
        L.extend(f'  {i}. {b}' for i, b in enumerate(blockers, 1))
    else:
        L.append('BLOCKERS: none')
    return L


# ----------------------------------------------------------------------------------------------- main
def write_site(root, before, after):
    realroot = os.path.realpath(root)
    n = 0
    for rel, text in sorted(after.items()):
        if before.get(rel) == text:
            continue
        path = os.path.join(root, *rel.split('/'))
        real = os.path.realpath(path)
        if not real.startswith(realroot + os.sep) or os.path.islink(path):
            raise Fail(f'refusing to write {rel}: it is outside {root}')
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.go_live-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text)
            if os.path.exists(path):
                shutil.copymode(path, tmp)
            else:
                os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        n += 1
    return n


def outside(path, site):
    rp, rs = os.path.realpath(path), os.path.realpath(site)
    return rp != rs and not rp.startswith(rs + os.sep)


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog='go_live.py',
        description='Full Bars launch-day switch: turns the preview site live (robots, noindex, banner, data-preview, Order '
                    'buttons, preview notes, dates, domain, and your --rewrites of the preview wording), and refuses while '
                    'launch blockers remain. Do the real run on a copy or a git branch. Plain-English guide: the top of this file.',
        epilog='Example: python3 launch/full-bars/go_live.py --site ~/full-bars-copy --domain fullbars.co.uk --checkout stripe '
               '--dry-run --out ~/go-live-report.txt --rewrites-template ~/rewrites.json   (Shopify: --checkout shopify '
               '--shop-url https://your-shop.example)   (exit 0 = done and ready to deploy to your web host, '
               '1 = blockers or a failed check, 2 = bad arguments, 3 = switched but NOT READY TO GO LIVE: preview or checkout '
               'wording left)')
    ap.add_argument('--site', required=True, metavar='DIR', help='the site folder to switch (edited in place unless --dry-run)')
    ap.add_argument('--domain', required=True, help='the shop\'s domain, e.g. fullbars.co.uk (pages go on www.DOMAIN, email hello@DOMAIN)')
    ap.add_argument('--checkout', choices=('shopify', 'stripe'), help='GO-LIVE.md decision 1. Required before it will switch anything')
    ap.add_argument('--shop-url', dest='shop_url', metavar='https://SHOP',
                    help='with --checkout shopify (required there): your Shopify store\'s own address (not a /products/ page). Each product page\'s Order '
                         'button goes to SHOP/products/<handle>, the handle being the page\'s URL handle in products-shopify.csv')
    ap.add_argument('--shopify-csv', dest='shopify_csv', metavar='CSV', default=SHOPIFY_CSV,
                    help='the Shopify product CSV whose URL handles the Order links must match (default: products-shopify.csv '
                         'next to this script)')
    ap.add_argument('--shop-variants', dest='shop_variants', metavar='JSON',
                    help='with --checkout shopify: the file fetch_shopify_variants.py writes ({"<handle>": {"<storage>|<condition>|'
                         '<colour>": <variant ID>}}). Each product picker gets data-variants, so its Order button opens Shopify '
                         'on exactly the phone chosen (?variant=ID); a choice with no ID reads "Choose and pay on the next page"')
    ap.add_argument('--trade-ins', dest='trade_ins', choices=('closed', 'open'), default='closed',
                    help='closed (default): the quote tool keeps giving guide prices only. open: switch it on (needs a send form)')
    ap.add_argument('--dry-run', action='store_true', help='print exactly what would change (file, line, before, after); write nothing')
    ap.add_argument('--check-only', dest='check_only', action='store_true',
                    help='only list the launch blockers (exit 1 if there are any); writes nothing')
    ap.add_argument('--force-preview-check-only', dest='check_only', action='store_true', help=argparse.SUPPRESS)  # old name
    ap.add_argument('--allow-preview-wording', action='store_true',
                    help='switch even though preview wording ("When we open ...") or checkout wording that doesn\'t fit '
                         '--checkout is still on the pages; the run then ends NOT READY TO GO LIVE (exit 3) and you rewrite '
                         'it by hand before you deploy the site')
    ap.add_argument('--out', metavar='REPORT', help='also save the full report to this file (must be outside --site)')
    ap.add_argument('--launch-date', metavar='YYYY-MM-DD',
                    help='date for "Last updated" and the sitemap (default: today, and only in the run that switches the site '
                         'out of preview; on a site that is already live the dates change only if you pass this)')
    ap.add_argument('--rewrites', metavar='JSON', help='file of {"sentence as on the page": "new wording"} applied wherever the '
                    'sentence appears, escaped for each place (null = skip, "" = delete)')
    ap.add_argument('--rewrites-template', metavar='JSON', help='write a --rewrites file listing every sentence still to rewrite')
    ap.add_argument('--no-www', action='store_true', help='use https://DOMAIN/ rather than https://www.DOMAIN/ for page addresses')
    return ap.parse_args(argv)


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors='replace')
    except AttributeError:
        pass
    opt = parse_args(argv)
    try:
        return run(opt)
    except Fail as e:
        print(f'go_live.py: {e}', file=sys.stderr)
        return 1


def run(opt):
    site = opt.site
    if not os.path.isdir(site) or not os.path.isfile(os.path.join(site, 'index.html')) \
            or not os.path.isdir(os.path.join(site, 'products')):
        print(f'go_live.py: {site} is not the Full Bars site folder (no index.html and products/)', file=sys.stderr)
        return 2
    for flag, path in (('--out', opt.out), ('--rewrites-template', opt.rewrites_template)):
        if path and not outside(path, site):
            print(f'go_live.py: {flag} {path} is inside --site, so it would go up to your web host with the site. Put it '
                  'somewhere else.',
                  file=sys.stderr)
            return 2
        if path and os.path.isdir(path):
            print(f'go_live.py: {flag} {path} is a folder, not a file', file=sys.stderr)
            return 2
    if opt.rewrites_template and os.path.exists(opt.rewrites_template):
        print(f'go_live.py: {opt.rewrites_template} already exists; delete or move it first (it may hold your rewrites)', file=sys.stderr)
        return 2
    opt.launch_date_given = bool(opt.launch_date)
    try:
        opt.launch_date = datetime.date.fromisoformat(opt.launch_date) if opt.launch_date else datetime.date.today()
    except ValueError:
        print(f'go_live.py: --launch-date {opt.launch_date!r} is not YYYY-MM-DD', file=sys.stderr)
        return 2
    try:
        opt.bare, opt.host = parse_domain(opt.domain, opt.no_www)
        if opt.shop_url is not None:
            if opt.checkout != 'shopify':
                raise Fail('--shop-url is only for --checkout shopify (the Order buttons go to Shopify only on that route)')
            opt.shop_url = parse_shop_url(opt.shop_url)
            shop_host = re.match(r'https://([^/:]+)', opt.shop_url).group(1)
            if shop_host in (opt.host, opt.bare):
                raise Fail(f'--shop-url {opt.shop_url} is the static site\'s own address (--domain). The Shopify store needs '
                           'its own address, such as shop.' + opt.bare + ' or your-shop.myshopify.com')
        opt.variants_data = None
        if opt.shop_variants is not None:
            if opt.checkout != 'shopify':
                raise Fail('--shop-variants is only for --checkout shopify (Shopify variant IDs are used on that route only)')
            opt.variants_data = load_variants_file(opt.shop_variants)
    except Fail as e:
        print(f'go_live.py: {e}', file=sys.stderr)
        return 2

    files = load_site(site)
    opt.shop_targets, opt.shop_blockers, opt.shop_warnings = shop_targets(files, opt)
    opt.variant_maps, opt.variant_blockers, opt.variant_warnings = variant_maps(files, opt)
    blockers, warnings = find_blockers(site, files, opt)

    old_host = current_host(files)
    # Dates change only in the run that takes the site out of preview, or when asked: a rerun on a live site
    # (to apply more --rewrites, say) must not claim the legal pages were updated today.
    opt.set_dates = in_preview(files) or opt.launch_date_given
    mech, notes = plan_switches(files, opt)
    if not opt.set_dates:
        notes.append('The site is already out of preview, so the "Last updated" dates on the legal pages and the sitemap '
                     'dates were left as they are. Pass --launch-date YYYY-MM-DD if you do want to change them.')
    dom = domain_edits(files, old_host, opt.bare, opt.host)
    stage_a = resolve(files, mech + dom)
    if old_host != opt.host:
        for e in stage_a:
            if e.prio == 0 and old_host in e.new:
                raise Fail(f'internal: switch at {e.rel}:{e.line} would write the old domain')
    switched = apply_edits(files, stage_a)
    edited_from = {e: files for e in stage_a}
    edits = list(stage_a)
    skipped, rewritten, keep, own = [], set(), set(), set()
    if opt.rewrites:
        rewrites, skipped = load_rewrites(opt.rewrites)
        keep = {k for k, v in rewrites.items() if k == v}
        # your new wording, as it lands on the pages: never listed as checkout wording (it is your decision)
        follow_from = old_host if old_host != opt.host else None
        own = {follow_domain(v, opt.bare, opt.host, follow_from) for v in rewrites.values() if v}
        rw_edits, rw_notes = rewrite_edits(switched, rewrites, opt.bare, opt.host, old_host if old_host != opt.host else None)
        stage_b = resolve(switched, rw_edits)
        notes += rw_notes
        edited_from.update({e: switched for e in stage_b})
        edits += stage_b
        result = apply_edits(switched, stage_b)
        rewritten = {e.rel for e in stage_b}
    else:
        result = switched
    left = leftovers(result, opt, keep, own)
    changed_host = old_host if old_host != opt.host else None
    problems = verify(result, opt, opt.host, changed_host) + rewrite_damage(switched, result, rewritten)

    if opt.rewrites_template:
        keys, tnotes = template_keys(result, left)
        with open(opt.rewrites_template, 'w', encoding='utf-8') as fh:
            json.dump({k: None for k in keys}, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
        notes += tnotes
        notes.append(f'Wrote {opt.rewrites_template}: {len(keys)} sentence(s), each set to null. Replace each null with the new '
                     'wording in plain text ("" deletes the sentence), then run again with --rewrites.')
    if problems:
        blockers = blockers + [f'the switch would be incomplete: {p}' for p in problems]
    pieces, places = wording_left(left)
    if pieces and not opt.allow_preview_wording:
        blockers.append(wording_blocker(left, listing=opt.check_only))
    elif pieces:
        warnings.append(f'--allow-preview-wording: {pieces} piece(s) of preview wording in {places} place(s) would stay on the '
                        'pages, so the switched site is NOT READY TO GO LIVE until they are rewritten.')
    cpieces, cplaces = checkout_left(left)
    if cpieces and not opt.allow_preview_wording:
        blockers.append(checkout_blocker(left, opt, listing=opt.check_only))
    elif cpieces:
        warnings.append(f'--allow-preview-wording: {cpieces} piece(s) of checkout wording that doesn\'t fit --checkout '
                        f'{opt.checkout} in {cplaces} place(s) would stay on the pages, so the switched site is NOT READY TO '
                        'GO LIVE until they are rewritten.')
    pieces += cpieces

    if opt.check_only:
        report = build_report('BLOCKER CHECK ONLY (nothing written)', site, opt, None, None, notes if opt.rewrites_template else [],
                              blockers, warnings, None, [], files)
        if blockers:
            report.append(f'RESULT: {len(blockers)} blocker(s): not ready to launch.')
            return finish(report, opt, 1)
        if pieces:
            report.append(f'RESULT: no blockers, but NOT READY TO GO LIVE: the switch would leave {pieces} piece(s) of preview '
                          'or checkout wording on the pages (--allow-preview-wording).')
            return finish(report, opt, 3)
        report.append('RESULT: no blockers: ready to switch.')
        return finish(report, opt, 0)

    if opt.dry_run:
        report = build_report('DRY RUN (nothing written)', site, opt, edits, edited_from, notes, blockers, warnings, left, skipped, result)
        head = f'RESULT: dry run. {len(edits)} change(s) would be made. '
        if blockers:
            report.append(head + f'{len(blockers)} blocker(s): a real run would refuse.')
            return finish(report, opt, 1)
        if pieces:
            report.append(head + 'No blockers: a real run would go ahead, but end NOT READY TO GO LIVE, because preview '
                          'or checkout wording would still be on the pages (--allow-preview-wording).')
            return finish(report, opt, 3)
        report.append(head + 'No blockers: a real run would go ahead.')
        return finish(report, opt, 0)

    if blockers:
        report = build_report('REFUSED (nothing written)', site, opt, edits, edited_from, notes, blockers, warnings, left, skipped, result)
        report.append(f'RESULT: REFUSED. {len(blockers)} blocker(s) remain, so nothing was written. Fix them and run again.')
        return finish(report, opt, 1)

    n = write_site(site, files, result)
    after = load_site(site)
    problems = verify(after, opt, opt.host, changed_host) + run_checks(site)
    left_after = leftovers(after, opt, keep, own)
    pieces, places = (a + b for a, b in zip(wording_left(left_after), checkout_left(left_after)))
    mode = 'WRITTEN, BUT CHECKS FAILED' if problems else 'WRITTEN, NOT READY TO GO LIVE' if pieces else 'DONE'
    report = build_report(mode, site, opt, edits, edited_from, notes, [f'after writing: {p}' for p in problems], warnings,
                          left_after, skipped, after)
    if problems:
        report.append(f'RESULT: {len(edits)} change(s) written to {n} file(s), but the checks above failed. Don\'t deploy it to '
                      'your web host yet.')
        return finish(report, opt, 1)
    if pieces:
        report.append(f'RESULT: NOT READY TO GO LIVE. {len(edits)} change(s) written to {n} file(s) and the checks pass, but '
                      f'{pieces} piece(s) of preview or checkout wording in {places} place(s) are still on the pages (you passed '
                      '--allow-preview-wording). Rewrite them (STILL TO DO BY HAND, item 1), for example by running this again '
                      'with --rewrites, before you deploy the site to your web host.')
        return finish(report, opt, 3)
    report.append(f'RESULT: done. {len(edits)} change(s) written to {n} file(s); checks pass and no preview wording is left '
                  f'(nor checkout wording that doesn\'t fit --checkout {opt.checkout}). Now do the items under STILL TO DO BY '
                  'HAND, then deploy the switched folder to your web host (GO-LIVE.md section 7). The claude.ai artifact '
                  'stays a preview copy: don\'t publish this folder there.')
    return finish(report, opt, 0)


def wording_blocker(left, listing=False):
    pieces, places = wording_left(left)
    msg = (f'preview wording would still be on the live pages: {pieces} piece(s) of text in {places} place(s) '
           f'({"listed below" if listing else "STILL TO DO BY HAND, item 1"}). Put the new wording in a --rewrites file '
           '(--rewrites-template writes one for you), or pass --allow-preview-wording to switch anyway and rewrite it by '
           'hand before you deploy the site')
    if listing:
        groups = list(left.get('rewrite', {}).items()) + [(k + '  [edit by hand]', v) for k, v in left.get('hand', {}).items()]
        for k, locs in sorted(groups, key=lambda kv: (-len(kv[1]), kv[0])):
            msg += f'\n       - {show(k, 110)} ({len(locs)} place{"s" if len(locs) != 1 else ""})'
    return msg


def checkout_blocker(left, opt, listing=False):
    pieces, places = checkout_left(left)
    msg = (f'checkout wording that doesn\'t fit --checkout {opt.checkout}: {pieces} piece(s) of text in {places} place(s) '
           f'({"listed below" if listing else "STILL TO DO BY HAND, item 1"}). Put the new wording in the same --rewrites file '
           '(--rewrites-template lists it; a sentence that is still true can be kept by giving it its own text), or pass '
           '--allow-preview-wording to switch anyway and rewrite it by hand before you deploy the site')
    if listing:
        groups = list(left.get('checkout', {}).items()) + [(k + '  [edit by hand]', v) for k, v in left.get('checkout-hand', {}).items()]
        for k, locs in sorted(groups, key=lambda kv: (-len(kv[1]), kv[0])):
            msg += f'\n       - {show(k, 110)} ({len(locs)} place{"s" if len(locs) != 1 else ""})'
    return msg


def finish(report, opt, code):
    text = '\n'.join(report) + '\n'
    sys.stdout.write(text)
    if opt.out:
        with open(opt.out, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return code


if __name__ == '__main__':
    sys.exit(main())
