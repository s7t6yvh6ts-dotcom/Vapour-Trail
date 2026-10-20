#!/usr/bin/env python3
"""Check products-shopify.csv against Shopify's product CSV rules and against the Chainline site itself.

Deliberately shares no code with build_shopify_csv.py: it reads the site's prices on its own, three ways (the bike
data, the bike cards in the HTML and the structured data), so a bug in the builder can't hide here.

  python3 validate_shopify_csv.py [CSV] [--site PATH] [--template SHOPIFY_SAMPLE.csv] [--launch]

--template  the sample CSV downloaded from Shopify admin (Products > Import > Download a sample CSV). Every column in
            our file must appear, spelt exactly, in its header row.
--launch    also fail while any [placeholder] is left in a description (fill them on the site first, run
            sync_bikes.py and build_shopify_csv.py, then validate again). Without it, they're reported as a NOTE.
Exit code 0 = all checks passed. Python 3 standard library only.
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))

# Shopify's current product CSV template, in template order: copied from launch/full-bars/validate_shopify_csv.py
# (typed by hand there from help.shopify.com; --template checks against a file Shopify itself produced).
CURRENT_TEMPLATE = [
    'Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
    'Published on online store', 'Status', 'SKU', 'Barcode',
    'Option1 name', 'Option1 value', 'Option1 LinkedTo', 'Option2 name', 'Option2 value', 'Option2 LinkedTo',
    'Option3 name', 'Option3 value', 'Option3 LinkedTo',
    'Price', 'Compare-at price', 'Cost per item', 'Charge tax', 'Tax code',
    'Unit price total measure', 'Unit price total measure unit', 'Unit price base measure', 'Unit price base measure unit',
    'Inventory tracker', 'Inventory quantity', 'Continue selling when out of stock',
    'Weight value (grams)', 'Weight unit for display', 'Requires shipping', 'Fulfillment service',
    'Product image URL', 'Image position', 'Image alt text', 'Variant image URL', 'Gift card',
    'SEO title', 'SEO description',
]
# The header launch/full-bars/products-shopify.csv uses: this file must use exactly the same one.
FULL_BARS_HEADER = ['Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
                    'Published on online store', 'Status', 'SKU', 'Option1 name', 'Option1 value', 'Option2 name',
                    'Option2 value', 'Option3 name', 'Option3 value', 'Price', 'Charge tax', 'Inventory tracker',
                    'Inventory quantity', 'Continue selling when out of stock', 'Weight value (grams)',
                    'Weight unit for display', 'Requires shipping', 'Fulfillment service', 'Product image URL',
                    'SEO title', 'SEO description']
MAX_BYTES = 15 * 1024 * 1024
# What every description must say (typed here as well as in the builder on purpose)
MUST_SAY = {
    'the warranty is on top of Consumer Rights Act 2015 rights': 'on top of your Consumer Rights Act 2015 rights, not instead of them',
    'the frame number was checked on BikeRegister (wording that does not overclaim)': 'Frame number checked on BikeRegister: not listed as stolen there when we checked',
    'the 14-day right to cancel': 'cancel for any reason within 14 days',
    'the drawings are illustrations, not photos': 'illustrations, not photos',
}
PLACEHOLDER = re.compile(r'\[[^\[\]<>"=]+\]')

results = []


def check(name, ok, detail=''):
    """ok: truthy = PASS, falsy = FAIL, None = NOTE (worth knowing; not a failure)."""
    results.append((name, None if ok is None else bool(ok), detail))


def find_site():
    for start in (HERE, os.getcwd()):
        d = start
        while os.path.dirname(d) != d:
            if os.path.isfile(os.path.join(d, 'sites', 'chainline', 'index.html')):
                return os.path.join(d, 'sites', 'chainline')
            d = os.path.dirname(d)
    sys.exit('Could not find sites/chainline/index.html; pass --site')


def site_truth(site):
    """Prices and ticket numbers straight from the page, three ways: {id: {...}}, plus the list of ids in the data."""
    src = open(os.path.join(site, 'index.html'), encoding='utf-8').read()
    data = json.loads(re.search(r'<script type="application/json" id="shop-data">(.*?)</script>', src, re.S).group(1))
    truth = {b['id']: {'price': b['price'], 'no': b['no'], 'make': b['make'], 'model': b['model'], 'type': b['type'],
                       'specs': b.get('specs', []), 'tag': b['tag']} for b in data['bikes']}
    cards = {}
    for cid, body in re.findall(r'<li class="card" id="bike-([a-z0-9-]+)">(.*?)</li>', src, re.S):
        m = re.search(r'<span class="price">£([\d,]+)</span>', body)
        cards[cid] = int(m.group(1).replace(',', '')) if m else None
    ld = json.loads(re.search(r'<script type="application/ld\+json" id="ld-bikes">(.*?)</script>', src, re.S).group(1))
    ld_prices = {}
    for it in ld.get('itemListElement', []):
        p = it.get('item', {})
        ld_prices[p.get('@id', '').replace('#bike-', '')] = Decimal(str(p.get('offers', {}).get('price', '0')))
    return truth, cards, ld_prices


def report(n='?'):
    width = max(len(name) for name, _, _ in results)
    for name, ok, d in results:
        label = 'NOTE' if ok is None else 'PASS' if ok else 'FAIL'
        print(f"{label}  {name.ljust(width)}  {d if (d and ok is not True) or name.startswith('prices') else ''}".rstrip())
    fails = sum(1 for _, ok, _ in results if ok is False)
    notes = sum(1 for _, ok, _ in results if ok is None)
    print(f'\n{len(results) - fails - notes}/{len(results) - notes} checks passed'
          + (f', {notes} {"note" if notes == 1 else "notes"}' if notes else '') + f'. {n} products.')
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('csv', nargs='?', default=os.path.join(HERE, 'products-shopify.csv'))
    ap.add_argument('--site')
    ap.add_argument('--template')
    ap.add_argument('--launch', action='store_true')
    a = ap.parse_args()
    truth, cards, ld_prices = site_truth(a.site or find_site())

    raw = open(a.csv, 'rb').read()
    check('file: UTF-8 without BOM', not raw.startswith(b'\xef\xbb\xbf'))
    try:
        raw.decode('utf-8')
        check('file: valid UTF-8', True)
    except UnicodeDecodeError as e:
        check('file: valid UTF-8', False, str(e))
        report()
    check('file: under Shopify 15 MB limit', len(raw) < MAX_BYTES, f'{len(raw)} bytes')
    with open(a.csv, encoding='utf-8', newline='') as f:
        table = list(csv.reader(f))
    if not table:
        check('file: has a header row', False)
        report()
    header, rows = table[0], [dict(zip(table[0], r)) for r in table[1:]]

    # ---------------- header
    check('header: the same columns, in the same order, as launch/full-bars/products-shopify.csv', header == FULL_BARS_HEADER,
          f'differs: {header}')
    check('header: no duplicate columns', len(header) == len(set(header)))
    unknown = [h for h in header if h not in CURRENT_TEMPLATE]
    check('header: every column is in the Shopify template list', not unknown, f'unknown: {unknown}')
    idx = [CURRENT_TEMPLATE.index(h) for h in header if h in CURRENT_TEMPLATE]
    check('header: columns in template order', idx == sorted(idx))
    check('rows: every row has the header’s column count', all(len(r) == len(header) for r in table[1:]))
    if a.template:
        with open(a.template, encoding='utf-8-sig', newline='') as f:
            tmpl = next(csv.reader(f))
        missing = [h for h in header if h not in tmpl]
        check('header: every column found verbatim in the downloaded Shopify sample', not missing, f'not in sample: {missing}')
    if header != FULL_BARS_HEADER or unknown:
        report()

    # ---------------- one product per bike
    handles = [r['URL handle'] for r in rows]
    check('products: one row per bike (each bike is its own single-variant product)', len(handles) == len(set(handles)),
          f'repeated: {sorted(h for h in set(handles) if handles.count(h) > 1)}')
    check('products: count matches the bikes in the site data', len(rows) == len(truth), f'{len(rows)} rows vs {len(truth)} bikes')
    check('products: count matches the bike cards in the HTML', len(rows) == len(cards), f'{len(cards)} cards')
    check('products: count matches the structured data', len(rows) == len(ld_prices), f'{len(ld_prices)} products in #ld-bikes')
    check('products: handles are exactly the site’s bike ids', set(handles) == set(truth),
          f'missing {sorted(set(truth) - set(handles))}, extra {sorted(set(handles) - set(truth))}')

    # ---------------- prices, row by row, against all three copies on the site
    bad = []
    for r in rows:
        h, p = r['URL handle'], r['Price']
        try:
            ok = bool(re.fullmatch(r'\d+\.\d{2}', p)) and Decimal(p) > 0
        except InvalidOperation:
            ok = False
        t = truth.get(h)
        want = [t and t['price'], cards.get(h), ld_prices.get(h)]
        if not ok or not t or any(w is None or Decimal(p) != Decimal(w) for w in want):
            bad.append(f'{h}: csv {p!r}, data {want[0]!r}, card {want[1]!r}, structured data {want[2]!r}')
    check('prices: every row equals the site’s data, its card and its structured data', not bad,
          f'{len(rows) - len(bad)}/{len(rows)} match' + ('; first bad: ' + bad[0] if bad else ''))

    # ---------------- fixed values
    def every(col, want):
        wrong = [r['URL handle'] for r in rows if r.get(col) != want]
        check(f'values: {col} = {want!r} on every row', not wrong, f'wrong on {wrong}')
    every('Status', 'draft')
    every('Published on online store', 'FALSE')
    every('Inventory tracker', 'shopify')
    every('Inventory quantity', '1')
    every('Continue selling when out of stock', 'deny')
    every('Requires shipping', 'TRUE')
    every('Fulfillment service', 'manual')
    every('Option1 name', 'Title')
    every('Option1 value', 'Default Title')
    every('Product image URL', '')
    for col in ('Option2 name', 'Option2 value', 'Option3 name', 'Option3 value'):
        every(col, '')
    check('values: Charge tax is TRUE or FALSE', all(r['Charge tax'] in ('TRUE', 'FALSE') for r in rows))
    # Shopify's rates are per order: GO-LIVE.md section 5 step 4 uses weight bands, one band per bike, so every bike must
    # carry the same shipping weight (1 kg, a counter), or two bikes could cost £39 on Shopify and £78 in the site's basket.
    weights = {r['Weight value (grams)'] for r in rows}
    check('values: every bike has the same shipping weight, 1000 g (the per-bike counter for the weight-based rates)',
          weights == {'1000'} and all(r['Weight unit for display'] == 'kg' for r in rows), f'found {sorted(weights)}')
    skus = [r['SKU'] for r in rows]
    check('values: SKU is CL- plus the workshop ticket number', all(r['SKU'] == 'CL-' + truth.get(r['URL handle'], {}).get('no', '?') for r in rows))
    check('values: SKUs unique', len(skus) == len(set(skus)))
    check('values: Vendor is the bike’s maker', all(r['Vendor'] == truth.get(r['URL handle'], {}).get('make') for r in rows))
    check('values: Type says refurbished bike or e-bike', all(
        r['Type'] == ('Refurbished e-bike' if truth.get(r['URL handle'], {}).get('type') == 'ebike' else 'Refurbished bike') for r in rows))
    check('values: e-bikes tagged for the specialist courier shipping profile', all(
        ('Specialist courier' in r['Tags']) == (truth.get(r['URL handle'], {}).get('type') == 'ebike') for r in rows))

    # ---------------- descriptions
    bodies = {r['URL handle']: r['Description'] for r in rows}
    for what, phrase in MUST_SAY.items():
        missing = [h for h, b in bodies.items() if phrase not in html.unescape(b)]
        check(f'description: says {what}', not missing, f'missing on {missing}')
    no_ticket = [h for h, b in bodies.items() if h in truth and f"Workshop ticket {truth[h]['no']}" not in b]
    check('description: names the workshop ticket and what was fitted or tested', not no_ticket and all(
        html.escape(truth[h]['tag'], quote=False) in b for h, b in bodies.items() if h in truth), f'{no_ticket}')
    no_cond = [h for h, b in bodies.items() if '<strong>Condition:</strong>' not in b]
    check('description: carries the bike’s condition', not no_cond, f'missing on {no_cond}')
    ebike_no_health = [h for h, b in bodies.items() if truth.get(h, {}).get('type') == 'ebike' and 'rated capacity' not in b]
    check('description: e-bikes explain battery health (share of rated capacity)', not ebike_no_health, f'{ebike_no_health}')
    check('description: no scripts or site-relative links', not any(re.search(r'<script|href="(?!https://)', b) for b in bodies.values()))
    check('description: no fake urgency or review wording', not any(
        re.search(r'(?i)only \d+ left|selling fast|best[- ]?seller|\breview|★|limited time|hurry', b) for b in bodies.values()))
    check('seo: titles ≤ 70 chars, descriptions ≤ 320', all(len(r['SEO title']) <= 70 and len(r['SEO description']) <= 320 for r in rows))

    found = sorted({p for r in rows for v in r.values() for p in PLACEHOLDER.findall(v)})
    if a.launch:
        check('launch: no [placeholders] left in any column', not found, ', '.join(found))
    else:
        check('placeholders still to fill on the site (fine in the preview; --launch fails on them)', None if found else True,
              ', '.join(found))
    report(len(rows))


if __name__ == '__main__':
    main()
