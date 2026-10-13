#!/usr/bin/env python3
"""Full Bars: check every phone price shown anywhere on the site against the single source of truth,
the data-prices JSON on each product page's #picker form (site.js renders the picker prices from it).

Run it after changing any price:  python3 launch/full-bars/check_site_prices.py [--site PATH]
It checks titles, meta and social tags, structured data, the static first-paint prices, every product
card and comparison-table row on every page, collection "N models . from" lines and tiles (and the phones each tile
lists in data-handles for site.js's stock note), the
Under-300 collection, pay.js keys and the trade-in model's Very Good sell prices in quote.js.
Prints FAIL lines (exit code 1) and lists any other price-like text for you to eyeball.
"""
import argparse
import html
import json
import os
import re
import sys


def _find_site():
    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        d = start
        while os.path.dirname(d) != d:
            if os.path.isfile(os.path.join(d, 'sites', 'full-bars', 'shop.html')):
                return os.path.join(d, 'sites', 'full-bars')
            d = os.path.dirname(d)
    sys.exit('Could not find sites/full-bars; pass --site')


_ap = argparse.ArgumentParser()
_ap.add_argument('--site')
_ap.add_argument('--quiet', action='store_true', help='do not list loose £ amounts')
_args = _ap.parse_args()
SITE = _args.site or _find_site()


def _attr(tag_html, name):
    m = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', tag_html)
    return html.unescape(m.group(1)) if m else None


def _text(fragment):
    """Visible text of an HTML fragment, entities decoded, whitespace collapsed."""
    t = re.sub(r'<[^>]+>', '', fragment)
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()


def product_files():
    d = os.path.join(SITE, 'products')
    return sorted(f for f in os.listdir(d) if f.endswith('.html'))


def read_product(fname):
    path = os.path.join(SITE, 'products', fname)
    src = open(path, encoding='utf-8').read()
    handle = fname[:-5]
    picker = re.search(r'<form class="picker" id="picker"[^>]*>', src).group(0)
    prices = json.loads(_attr(picker, 'data-prices'))
    grades_desc = json.loads(_attr(picker, 'data-grades'))
    model = _attr(picker, 'data-model')
    form = re.search(r'<form class="picker" id="picker".*?</form>', src, re.S).group(0)

    def radios(name):
        return [html.unescape(v) for v in re.findall(r'<input type="radio" name="' + name + r'" value="([^"]*)"', form)]

    storages, grades, colours = radios('storage'), radios('grade'), radios('colour')
    ld = None
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S):
        j = json.loads(block)
        if j.get('@type') == 'Product':
            ld = j
    specs = [( _text(dt), _text(dd)) for dt, dd in re.findall(r'<div><dt>(.*?)</dt><dd>(.*?)</dd></div>', src)]
    panels = {}
    for h2, ul in re.findall(r'<div class="panel[^"]*"[^>]*><h2[^>]*>(.*?)</h2><ul class="ticks">(.*?)</ul>', src, re.S):
        panels[_text(h2)] = [_text(li) for li in re.findall(r'<li>(.*?)</li>', ul, re.S)]
    return {
        'file': 'products/' + fname,
        'handle': handle,
        'model': model,
        'h1': _text(re.search(r'<h1>(.*?)</h1>', src, re.S).group(1)),
        'eyebrow': _text(re.search(r'<div class="eyebrow">(.*?)</div>', src, re.S).group(1)),
        'sub': _text(re.search(r'<p class="pd-sub">(.*?)</p>', src, re.S).group(1)),
        'title': _text(re.search(r'<title>(.*?)</title>', src, re.S).group(1)),
        'meta_desc': html.unescape(re.search(r'<meta name="description" content="([^"]*)"', src).group(1)),
        'brand': ld['brand']['name'],
        'ld': ld,
        'prices': prices,
        'grades_desc': grades_desc,
        'storages': storages,
        'grades': grades,
        'colours': colours,
        'specs': specs,
        'panels': panels,
        'promise_note': _text(re.search(r'<p class="promise-note">(.*?)</p>', src, re.S).group(1)),
        'buy_note': _text(re.search(r'<p class="buy-note" id="buyNote"[^>]*>(.*?)</p>', src, re.S).group(1)),
        'src': src,
    }


def all_products():
    return [read_product(f) for f in product_files()]


def shop_cards():
    """data-* attributes of each card on shop.html, keyed by product handle."""
    src = open(os.path.join(SITE, 'shop.html'), encoding='utf-8').read()
    out = {}
    for tag, href in re.findall(r'(<article class="card"[^>]*>)<a href="products/([^"]+)\.html"', src):
        out[href] = {k: _attr(tag, 'data-' + k) for k in ('series', 'type', 'from', 'usbc', 'order')}
    return out


def pay_keys():
    src = open(os.path.join(SITE, 'pay.js'), encoding='utf-8').read()
    body = src[src.index('window.FULLBARS_PAY'):]
    return re.findall(r'^\s*"([^"]+)":\s*"[^"]*",?\s*$', body, re.M)



fails, notes, checked = [], [], 0


def check(ok, msg):
    global checked
    checked += 1
    if not ok:
        fails.append(msg)


def pounds(s):
    return [int(x.replace(',', '')) for x in re.findall(r'(?:&pound;|£)\s?([0-9][0-9,]*)', s)]


products = {p['handle']: p for p in all_products()}
lo = {h: min(min(g.values()) for g in p['prices'].values()) for h, p in products.items()}
hi = {h: max(max(g.values()) for g in p['prices'].values()) for h, p in products.items()}
allp = {h: {v for g in p['prices'].values() for v in g.values()} for h, p in products.items()}

# ---- 1. each product page against its own picker data
for h, p in products.items():
    src, pr = p['src'], p['prices']
    check(list(pr.keys()) == p['storages'], f"{p['file']}: storage radios {p['storages']} != data-prices keys {list(pr)}")
    for st, g in pr.items():
        check(list(g.keys()) == p['grades'], f"{p['file']}: {st} grades {list(g)} != grade radios {p['grades']}")
        check(all(isinstance(v, int) and v > 0 for v in g.values()), f"{p['file']}: non-integer/zero price in {st}")
        # better grade must never cost less than a worse one, more storage never less than less storage
        vals = [g[x] for x in p['grades']]
        check(vals == sorted(vals, reverse=True), f"{p['file']}: {st} grade prices not descending {vals}")
    for gr in p['grades']:
        col = [pr[st][gr] for st in p['storages']]
        check(col == sorted(col), f"{p['file']}: {gr} prices not ascending with storage {col}")
    m = re.search(r'from (?:&pound;|£)(\d+)', p['title'].replace('£', '&pound;'))
    check(m and int(m.group(1)) == lo[h], f"{p['file']}: <title> 'from' {m and m.group(1)} != lowest {lo[h]}")
    for label, rx in (('meta description', r'<meta name="description" content="([^"]*)"'),
                      ('og:description', r'<meta property="og:description" content="([^"]*)"'),
                      ('og:title', r'<meta property="og:title" content="([^"]*)"')):
        mm = re.search(rx, src)
        nums = pounds(mm.group(1)) if mm else []
        check(nums and all(n == lo[h] for n in nums), f"{p['file']}: {label} prices {nums} != lowest {lo[h]}")
    off = p['ld']['offers']
    check(off.get('priceCurrency') == 'GBP', f"{p['file']}: JSON-LD currency {off.get('priceCurrency')}")
    check(off.get('lowPrice') == lo[h] and off.get('highPrice') == hi[h],
          f"{p['file']}: JSON-LD low/high {off.get('lowPrice')}/{off.get('highPrice')} != {lo[h]}/{hi[h]}")
    # static first paint (before site.js runs) must equal what site.js will render for the default selection
    st0 = re.search(r'name="storage" value="([^"]+)" checked', src).group(1)
    gr0 = re.search(r'name="grade" value="([^"]+)" checked', src).group(1)
    co0 = re.search(r'name="colour" value="([^"]+)" checked', src).group(1)
    pd = pounds(re.search(r'id="pdPrice"[^>]*>([^<]*)<', src).group(1))
    check(pd == [pr[st0][gr0]], f"{p['file']}: static #pdPrice {pd} != {pr[st0][gr0]} for {st0}/{gr0}")
    form = re.search(r'<form class="picker" id="picker".*?</form>', src, re.S).group(0)
    for st, small in re.findall(r'name="storage" value="([^"]+)"[^>]*><span>[^<]*<small>([^<]*)</small>', form):
        check(pounds(small) == [pr[st][gr0]], f"{p['file']}: static storage label {st} {small} != {pr[st][gr0]}")
    for gr, small in re.findall(r'name="grade" value="([^"]+)"[^>]*><span>[^<]*<small>([^<]*)</small>', form):
        check(pounds(small) == [pr[st0][gr]], f"{p['file']}: static grade label {gr} {small} != {pr[st0][gr]}")
    sel = html.unescape(re.search(r'id="selLine">(.*?)</p>', src, re.S).group(1))
    check(sel.startswith(f"Selected: {p['model']} {st0}, {gr0}, {co0}") and pounds(sel) == [pr[st0][gr0]],
          f"{p['file']}: static selected line '{sel}'")
    spec = dict(p['specs'])
    check(spec.get('Storage', '').split(', ') == p['storages'], f"{p['file']}: spec Storage '{spec.get('Storage')}' != {p['storages']}")
    check(spec.get('Colours', '').split(', ') == p['colours'], f"{p['file']}: spec Colours '{spec.get('Colours')}' != radios {p['colours']}")

# ---- 2. pay.js keys must be exactly every model+storage+grade the pickers offer
keys = pay_keys()
want = [f"{p['model']} {st} {gr}" for p in products.values() for st in p['storages'] for gr in p['grades']]
check(len(keys) == len(set(keys)), 'pay.js: duplicate keys')
check(set(keys) == set(want), f"pay.js: missing {sorted(set(want) - set(keys))} extra {sorted(set(keys) - set(want))}")

# ---- 2b. quote.js trade-in model: sellPrice is 'realistic selling price for a VERY GOOD unit' - must equal the shop price
qsrc = open(os.path.join(SITE, 'quote.js'), encoding='utf-8').read()
for qid, sp in re.findall(r"\{ id: '([a-z0-9-]+)',[^}]*sellPrice: \{([^}]*)\}", qsrc):
    for st, pence in re.findall(r"'([0-9]+(?:GB|TB))': (\d+)", sp):
        check(qid in products and int(pence) == products[qid]['prices'][st]['Very Good'] * 100,
              f"quote.js {qid} {st} sellPrice {pence}p != shop Very Good £{products.get(qid, {}).get('prices', {}).get(st, {}).get('Very Good')}")

# ---- 3. every card, table row and tile on every page
loose = []
handle_rx = re.compile(r'href="(?:\.\./)?products/([a-z0-9-]+)\.html')
for root, _, files in os.walk(SITE):
    for f in sorted(files):
        if not f.endswith('.html'):
            continue
        rel = os.path.relpath(os.path.join(root, f), SITE)
        src = open(os.path.join(root, f), encoding='utf-8').read()
        if rel.startswith('products/'):
            # the picker area is checked above; only scan the 'Similar phones' cards etc. below it
            src_scan = src[src.index('<div class="pd-more">'):]
        else:
            src_scan = src
        spans = []
        # cards
        for m in re.finditer(r'<article class="card"([^>]*)>(.*?)</article>', src_scan, re.S):
            spans.append(m.span())
            hs = set(handle_rx.findall(m.group(2)))
            df = re.search(r'data-from="(\d+)"', m.group(1))
            if len(hs) != 1:
                notes.append(f'{rel}: card links to {hs}')
                continue
            h = hs.pop()
            shown = pounds(re.search(r'class="card-price">(.*?)</div>', m.group(2), re.S).group(1))
            check(df and int(df.group(1)) == lo[h], f'{rel}: card {h} data-from {df and df.group(1)} != {lo[h]}')
            check(shown == [lo[h]], f'{rel}: card {h} shows {shown} != from {lo[h]}')
        # table rows
        for m in re.finditer(r'<tr>(.*?)</tr>', src_scan, re.S):
            hs = set(handle_rx.findall(m.group(1)))
            nums = pounds(m.group(1))
            if not nums:
                continue
            spans.append(m.span())
            if len(hs) != 1:
                notes.append(f'{rel}: priced table row without exactly one product link: {_text(m.group(1))[:90]}')
                continue
            h = hs.pop()
            check(nums == [lo[h]], f'{rel}: table row {h} shows {nums} != from {lo[h]}')
        # anything else with a £ amount: record for review
        masked = src_scan
        for a, b in sorted(spans, reverse=True):
            masked = masked[:a] + ' ' * (b - a) + masked[b:]
        for m in re.finditer(r'(?:&pound;|£)\s?[0-9][0-9,]*', masked):
            ctx = _text(masked[max(0, m.start() - 160):m.end() + 60])
            loose.append((rel, ctx[-170:]))

# ---- 4. collection pages: "N models · from £X" must match the cards on that page; tiles linking to them too
coll = {}
for f in sorted(os.listdir(os.path.join(SITE, 'collections'))):
    src = open(os.path.join(SITE, 'collections', f), encoding='utf-8').read()
    grid = src[src.index('<main'):]
    cards = re.findall(r'<article class="card"[^>]*>\s*<a href="\.\./products/([a-z0-9-]+)\.html"', grid)
    m = re.search(r'class="result-line"><span>(\d+) models? &middot; from &pound;(\d+)</span>', src)
    coll[f] = (len(cards), min(lo[c] for c in cards), cards)
    check(m and (int(m.group(1)), int(m.group(2))) == coll[f][:2],
          f'collections/{f}: result line {m and m.groups()} != {coll[f][:2]}')
under = {h for h in products if lo[h] < 300}
check(set(coll['under-300.html'][2]) == under, f"under-300: lists {sorted(coll['under-300.html'][2])}, should be {sorted(under)}")
for f in ['index.html', 'shop.html']:
    src = open(os.path.join(SITE, f), encoding='utf-8').read()
    for href, attrs, body in re.findall(r'<a class="tile[^"]*" href="collections/([^"]+)"([^>]*)>(.*?)</a>', src, re.S):
        t = _text(body)
        # data-handles: the phones site.js checks in stock.js for the tile's "None in stock right now" note
        dh = re.search(r'\bdata-handles="([^"]*)"', attrs)
        if dh and href in coll:
            check(sorted(dh.group(1).split()) == sorted(coll[href][2]),
                  f'{f}: tile {href} data-handles {sorted(dh.group(1).split())} != the phones on that page {sorted(coll[href][2])}')
        sp = re.search(r'<span>(.*?)</span>', body, re.S)
        n = re.search(r'^(\d+) models?', _text(sp.group(1))) if sp else None
        fr = pounds(body)
        if href in coll and fr and 'Under' not in t:
            check(fr == [coll[href][1]], f'{f}: tile {href} from {fr} != {coll[href][1]}')
            if n:
                check(int(n.group(1)) == coll[href][0], f'{f}: tile {href} says {n.group(1)} models, page has {coll[href][0]}')

print(f'products: {len(products)}  checks: {checked}  fails: {len(fails)}')
for x in fails:
    print('FAIL', x)
for x in notes:
    print('NOTE', x)
if _args.quiet:
    sys.exit(1 if fails else 0)
print(f'\nLoose £ amounts not inside a product card/row ({len(loose)}), unique contexts for review:')
seen = set()
for rel, ctx in loose:
    k = re.sub(r'\s+', ' ', ctx)
    if (rel.split('/')[0], k) in seen:
        continue
    seen.add((rel.split('/')[0], k))
    print(f'  {rel}: ...{k}')
sys.exit(1 if fails else 0)
