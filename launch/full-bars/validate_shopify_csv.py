#!/usr/bin/env python3
"""Check products-shopify.csv against Shopify's product CSV rules and against the Full Bars site itself.

Deliberately shares no code with build_shopify_csv.py: it reads the site's prices on its own, so a
bug in the builder can't hide here.

  python3 validate_shopify_csv.py [CSV] [--site PATH] [--template SHOPIFY_SAMPLE.csv] [--export EXPORT.csv]
                                  [--legacy LEGACY.csv]

--template: the sample CSV downloaded from Shopify admin (Products > Import > Download a sample CSV).
            Every column in our file must appear, spelt exactly, in its header row.
--export:   an export from your own store of ONE test product made by hand, set up as GO-LIVE.md step 5.3 says.
            Checks the header as --template does, then checks that the values we write (draft, deny, TRUE,
            shopify, manual, g, the category) are spelt exactly as your store writes them.
Exit code 0 = all checks passed.
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

# Shopify's current product CSV template (help.shopify.com/en/manual/products/import-export/using-csv),
# in template order, typed by hand. help.shopify.com could not be opened from the sandbox, so names marked *
# were matched against search-result quotes of that page, not the page itself. This list proves nothing
# about Shopify on its own: --template and --export check our file against files Shopify itself produced.
CURRENT_TEMPLATE = [
    'Title*', 'URL handle*', 'Description*', 'Vendor*', 'Product category*', 'Type', 'Tags',
    'Published on online store*', 'Status*', 'SKU*', 'Barcode*',
    'Option1 name*', 'Option1 value*', 'Option1 LinkedTo*', 'Option2 name', 'Option2 value', 'Option2 LinkedTo',
    'Option3 name', 'Option3 value', 'Option3 LinkedTo',
    'Price*', 'Compare-at price*', 'Cost per item*', 'Charge tax*', 'Tax code*',
    'Unit price total measure', 'Unit price total measure unit', 'Unit price base measure', 'Unit price base measure unit',
    'Inventory tracker*', 'Inventory quantity*', 'Continue selling when out of stock*',
    'Weight value (grams)*', 'Weight unit for display*', 'Requires shipping*', 'Fulfillment service*',
    'Product image URL', 'Image position', 'Image alt text', 'Variant image URL*', 'Gift card',
    'SEO title', 'SEO description',
]
CURRENT_TEMPLATE = [c.rstrip('*') for c in CURRENT_TEMPLATE]
# Shopify's older header row, verbatim from help.shopify.com/en/manual/products/import-export/common-import-issues,
# plus the later legacy-export columns (Product Category, SEO, Variant Weight Unit, Status).
LEGACY_TEMPLATE = ['Handle', 'Title', 'Body (HTML)', 'Vendor', 'Product Category', 'Type', 'Tags', 'Published',
                   'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value',
                   'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Qty',
                   'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price', 'Variant Compare-at Price',
                   'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode', 'Image Src', 'Image Position',
                   'Image Alt Text', 'Gift Card', 'SEO Title', 'SEO Description', 'Variant Image', 'Variant Weight Unit',
                   'Variant Tax Code', 'Cost per item', 'Status']
TO_CURRENT = {'Handle': 'URL handle', 'Body (HTML)': 'Description', 'Product Category': 'Product category',
              'Published': 'Published on online store', 'Variant SKU': 'SKU', 'Option1 Name': 'Option1 name',
              'Option1 Value': 'Option1 value', 'Option2 Name': 'Option2 name', 'Option2 Value': 'Option2 value',
              'Option3 Name': 'Option3 name', 'Option3 Value': 'Option3 value', 'Variant Price': 'Price',
              'Variant Taxable': 'Charge tax', 'Variant Inventory Tracker': 'Inventory tracker',
              'Variant Inventory Qty': 'Inventory quantity', 'Variant Inventory Policy': 'Continue selling when out of stock',
              'Variant Grams': 'Weight value (grams)', 'Variant Weight Unit': 'Weight unit for display',
              'Variant Requires Shipping': 'Requires shipping', 'Variant Fulfillment Service': 'Fulfillment service',
              'Image Src': 'Product image URL', 'SEO Title': 'SEO title', 'SEO Description': 'SEO description'}
MAX_VARIANTS, MAX_OPTIONS, MAX_BYTES = 2048, 3, 15 * 1024 * 1024
PRODUCT_COLS = ['Title', 'Description', 'Vendor', 'Product category', 'Type', 'Tags', 'Published on online store',
                'Status', 'Option1 name', 'Option2 name', 'Option3 name', 'SEO title', 'SEO description']

results = []


def check(name, ok, detail=''):
    """ok: truthy = PASS, falsy = FAIL, None = NOTE (nothing to compare; not a failure)."""
    results.append((name, None if ok is None else bool(ok), detail))


def find_site():
    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        d = start
        while os.path.dirname(d) != d:
            if os.path.isfile(os.path.join(d, 'sites', 'full-bars', 'shop.html')):
                return os.path.join(d, 'sites', 'full-bars')
            d = os.path.dirname(d)
    sys.exit('Could not find sites/full-bars; pass --site')


def site_truth(site):
    """{handle: {'prices': {storage: {grade: int}}, 'colours': [...], 'model': str}} straight from the pages."""
    out = {}
    pdir = os.path.join(site, 'products')
    for f in sorted(os.listdir(pdir)):
        if not f.endswith('.html'):
            continue
        src = open(os.path.join(pdir, f), encoding='utf-8').read()
        tag = re.search(r'<form[^>]*id="picker"[^>]*>', src).group(0)
        form = src[src.index(tag):src.index('</form>', src.index(tag))]
        out[f[:-5]] = {
            'prices': json.loads(html.unescape(re.search(r'data-prices="([^"]*)"', tag).group(1))),
            'model': html.unescape(re.search(r'data-model="([^"]*)"', tag).group(1)),
            'colours': [html.unescape(c) for c in re.findall(r'name="colour" value="([^"]*)"', form)],
        }
    return out


def read_csv(path):
    raw = open(path, 'rb').read()
    check('file: UTF-8 without BOM', not raw.startswith(b'\xef\xbb\xbf'))
    try:
        raw.decode('utf-8')
        check('file: valid UTF-8', True)
    except UnicodeDecodeError as e:
        check('file: valid UTF-8', False, str(e))
    check('file: under Shopify 15 MB limit', len(raw) < MAX_BYTES, f'{len(raw)} bytes')
    with open(path, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    return rows[0], [dict(zip(rows[0], r)) for r in rows[1:]], rows


def report(products='?', variants='?'):
    width = max(len(n) for n, _, _ in results)
    for n, ok, d in results:
        show = d and (not ok or n.startswith(('prices', 'products: count', 'values: SKU', 'values: weights',
                                              'file: under', 'values: Product')))
        label = 'NOTE' if ok is None else 'PASS' if ok else 'FAIL'
        print(f"{label}  {n.ljust(width)}  {d if show else ''}".rstrip())
    fails = sum(1 for _, ok, _ in results if ok is False)
    notes = sum(1 for _, ok, _ in results if ok is None)
    note_txt = f", {notes} {'note' if notes == 1 else 'notes'} (nothing to compare)" if notes else ''
    print(f'\n{len(results) - fails - notes}/{len(results) - notes} checks passed{note_txt}. '
          f'{products} products, {variants} variants.')
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument('csv', nargs='?', default=os.path.join(here, 'products-shopify.csv'))
    ap.add_argument('--site')
    ap.add_argument('--template')
    ap.add_argument('--export')
    ap.add_argument('--legacy')
    a = ap.parse_args()
    site = a.site or find_site()
    truth = site_truth(site)

    header, rows, raw_rows = read_csv(a.csv)
    # ---------------- header against Shopify's template
    check('header: no duplicate columns', len(header) == len(set(header)))
    unknown = [h for h in header if h not in CURRENT_TEMPLATE]
    check('header: every column is in the hand-typed template list (confirm with --export)', not unknown,
          f'unknown: {unknown}')
    idx = [CURRENT_TEMPLATE.index(h) for h in header if h in CURRENT_TEMPLATE]
    check('header: columns in template order', idx == sorted(idx))
    check('header: required columns present (Title, URL handle)', {'Title', 'URL handle'} <= set(header))
    check('header: option name/value pairs complete',
          all((f'Option{i} name' in header) == (f'Option{i} value' in header) for i in (1, 2, 3)))
    check('rows: every row has the header’s column count', all(len(r) == len(header) for r in raw_rows))
    tmpl = []
    if a.template:
        with open(a.template, encoding='utf-8-sig', newline='') as f:
            tmpl = next(csv.reader(f))
        missing = [h for h in header if h not in tmpl]
        check('header: every column found verbatim in the downloaded Shopify sample', not missing, f'not in sample: {missing}')
    needed = ['URL handle', 'Price', 'SKU', 'Option1 value', 'Option2 value', 'Option3 value'] + PRODUCT_COLS + [
        'Status', 'Continue selling when out of stock', 'Inventory tracker', 'Inventory quantity', 'Requires shipping',
        'Charge tax', 'Fulfillment service', 'Product image URL', 'Weight value (grams)']
    gone = sorted(set(needed) - set(header))
    check('header: has every column the brief and the checks below need', not gone, f'missing: {gone}')
    if gone:
        report()

    # ---------------- product grouping
    handles = []
    for r in rows:
        if not handles or handles[-1] != r['URL handle']:
            handles.append(r['URL handle'])
    check('products: each handle’s rows are contiguous', len(handles) == len(set(handles)), f'{handles}')
    shop = open(os.path.join(site, 'shop.html'), encoding='utf-8').read()
    shop_cards = re.findall(r'<article class="card"[^>]*><a href="products/([a-z0-9-]+)\.html"', shop)
    pay = open(os.path.join(site, 'pay.js'), encoding='utf-8').read()
    pay_models = {re.sub(r' (\d+GB|1TB) (Excellent|Very Good|Good)$', '', k)
                  for k in re.findall(r'^\s*"([^"]+)":\s*"', pay, re.M)}
    check('products: count matches site product pages', len(set(handles)) == len(truth), f'{len(set(handles))} vs {len(truth)} pages')
    check('products: count matches shop.html cards', len(set(handles)) == len(shop_cards), f'{len(shop_cards)} cards')
    check('products: count matches models in pay.js', len(set(handles)) == len(pay_models), f'{len(pay_models)} models')
    check('products: handles are exactly the site’s product URLs', set(handles) == set(truth),
          f'missing {sorted(set(truth) - set(handles))}, extra {sorted(set(handles) - set(truth))}')

    by = {h: [r for r in rows if r['URL handle'] == h] for h in handles}
    price_rows = price_ok = 0
    bad_prices, dupes, incomplete, levels, other = [], [], [], [], []
    for h, rs in by.items():
        first, rest = rs[0], rs[1:]
        # product-level fields on the first row only
        if not all(first[c] for c in PRODUCT_COLS if c in first and c != 'SEO description') or \
                any(r[c] for r in rest for c in PRODUCT_COLS if c in r):
            levels.append(h)
        names = [first[f'Option{i} name'] for i in (1, 2, 3) if first.get(f'Option{i} name')]
        if len(names) > MAX_OPTIONS or len(names) != len(set(names)):
            other.append(f'{h}: options {names}')
        if len(rs) > MAX_VARIANTS:
            other.append(f'{h}: {len(rs)} variants > {MAX_VARIANTS}')
        combos = [(r['Option1 value'], r['Option2 value'], r['Option3 value']) for r in rs]
        if len(combos) != len(set(combos)):
            dupes.append(h)
        t = truth.get(h)
        if t:
            want = {(s, g, c) for s, gs in t['prices'].items() for g in gs for c in t['colours']}
            if set(combos) != want:
                incomplete.append(f'{h}: missing {len(want - set(combos))}, extra {len(set(combos) - want)}')
        for r in rs:
            price_rows += 1
            p = r['Price']
            try:
                ok = bool(re.fullmatch(r'\d+\.\d{2}', p)) and Decimal(p) > 0
            except InvalidOperation:
                ok = False
            site_price = t and t['prices'].get(r['Option1 value'], {}).get(r['Option2 value'])
            if ok and site_price is not None and Decimal(p) == Decimal(site_price):
                price_ok += 1
            else:
                bad_prices.append(f"{h} {r['Option1 value']} {r['Option2 value']} {r['Option3 value']}: csv {p!r} site {site_price!r}")
    check('variants: option combinations unique within every product', not dupes, f'{dupes}')
    check('variants: exactly the site’s storage × grade × colour choices, per product', not incomplete, '; '.join(incomplete))
    check('variants: product-level fields only on each product’s first row', not levels, f'{levels}')
    check(f'variants: ≤{MAX_OPTIONS} options and ≤{MAX_VARIANTS} variants per product', not other, '; '.join(other))
    check('prices: every row parses and equals the site’s data-prices, row by row', not bad_prices,
          f'{price_ok}/{price_rows} match' + ('; first bad: ' + bad_prices[0] if bad_prices else ''))

    # ---------------- fixed values the brief sets
    def every(col, want, rs=rows):
        bad = [r['URL handle'] for r in rs if r.get(col) != want]
        check(f'values: {col} = {want!r} on every applicable row', not bad, f'{len(bad)} rows wrong')
    firsts = [rs[0] for rs in by.values()]
    every('Status', 'draft', firsts)
    every('Published on online store', 'FALSE', firsts)
    every('Type', 'Refurbished smartphone', firsts)
    every('Continue selling when out of stock', 'deny')
    every('Inventory tracker', 'shopify')
    every('Inventory quantity', '0')
    every('Requires shipping', 'TRUE')
    every('Charge tax', 'TRUE')
    every('Fulfillment service', 'manual')
    every('Product image URL', '')
    check('values: Vendor is Apple, Samsung or Google', all(r['Vendor'] in ('Apple', 'Samsung', 'Google') for r in firsts))
    check('values: Product category is one breadcrumb (not ID + breadcrumb)',
          all(r['Product category'].count(' > ') == 3 and r['Product category'] == firsts[0]['Product category'] for r in firsts),
          firsts[0]['Product category'])
    grams = [r['Weight value (grams)'] for r in rows]
    check('values: weights are whole grams, 100–2000', all(g.isdigit() and 100 <= int(g) <= 2000 for g in grams),
          f'range {min(grams)}–{max(grams)}')
    skus = [r['SKU'] for r in rows]
    check('values: SKUs present and unique', all(skus) and len(skus) == len(set(skus)), f'{len(set(skus))} unique of {len(skus)}')
    bodies = [r['Description'] for r in firsts]
    check('description: says warranty is on top of Consumer Rights Act 2015 rights',
          all('on top of your Consumer Rights Act 2015 rights' in b for b in bodies))
    check('description: says every phone is IMEI-checked on CheckMEND', all('IMEI-checked on CheckMEND' in b for b in bodies))
    check('description: mentions the 14-day right to cancel', all('within 14 days' in b for b in bodies))
    check('description: no site-relative links or scripts', not any(re.search(r'href="\.\.|<script|\[', b) for b in bodies))
    check('description: no fake urgency or review wording',
          not any(re.search(r'(?i)only \d+ left|selling fast|best[- ]?seller|\breview|★|limited time', b) for b in bodies))
    check('seo: titles ≤ 70 chars, descriptions ≤ 320',
          all(len(r['SEO title']) <= 70 and len(r['SEO description']) <= 320 for r in firsts))

    # ---------------- tags rebuild every site collection exactly (for Shopify automated collections)
    tagset = {r['URL handle']: {t.strip() for t in r['Tags'].split(',')} for r in firsts}
    rules = {'iphone-12-series': {'iPhone 12 series'}, 'iphone-13-series': {'iPhone 13 series'},
             'iphone-14-series': {'iPhone 14 series'}, 'iphone-15-series': {'iPhone 15 series'},
             'iphone-16-series': {'iPhone 16 series'}, 'samsung-galaxy': {'Samsung Galaxy'},
             'google-pixel': {'Google Pixel'}, 'pro-models': {'Pro', 'iPhone'}, 'big-screen': {'Big screen'},
             'usb-c-iphones': {'USB-C', 'iPhone'}, 'under-300': {'Under £300'}}
    cdir = os.path.join(site, 'collections')
    pages = sorted(f[:-5] for f in os.listdir(cdir) if f.endswith('.html'))
    bad = []
    for c in pages:
        src = open(os.path.join(cdir, c + '.html'), encoding='utf-8').read()
        on_page = set(re.findall(r'<article class="card"[^>]*>\s*<a href="\.\./products/([a-z0-9-]+)\.html"', src))
        by_tag = {h for h, ts in tagset.items() if rules.get(c, {'?'}) <= ts}
        if on_page != by_tag:
            bad.append(f'{c}: page {sorted(on_page)} tags {sorted(by_tag)}')
    check(f'tags: reproduce all {len(pages)} site collections exactly', not bad, '; '.join(bad))

    # ---------------- against an export of one hand-made test product from Ash's own store, if given
    if a.export:
        with open(a.export, encoding='utf-8-sig', newline='') as f:
            er = [r for r in csv.reader(f) if any(c.strip() for c in r)]
        eh = er[0] if er else []
        legacy_export = 'Handle' in eh and 'URL handle' not in eh
        check('export: your store uses the current column names', not legacy_export,
              'it exports the older names: import products-shopify-legacy-headers.csv instead')
        to_legacy = {v: k for k, v in TO_CURRENT.items()}
        ours = [to_legacy.get(h, h) for h in header] if legacy_export else header
        # Exports can leave out import-only columns, so a column in Shopify's import sample counts too.
        missing = [h for h in ours if h not in eh and h not in tmpl]
        check('export: every column we import is in your export (or the import sample)', not missing,
              f'in neither: {missing}')
        erows = [{TO_CURRENT.get(k, k): v for k, v in zip(eh, r)} for r in er[1:]]
        check('export: holds at least one product row', erows, 'export one product with three options, not an empty file')
        same = {'Status': firsts, 'Published on online store': firsts, 'Product category': firsts,
                'Continue selling when out of stock': rows, 'Inventory tracker': rows, 'Requires shipping': rows,
                'Charge tax': rows, 'Fulfillment service': rows, 'Weight unit for display': rows}
        for col, rs in same.items():
            mine = sorted({r[col] for r in rs})
            theirs = sorted({r.get(col, '').strip() for r in erows if r.get(col, '').strip()})
            if col not in {TO_CURRENT.get(h, h) for h in eh}:
                ok, why = None, 'your export has no such column, so there is nothing to compare'
            elif mine == theirs:
                ok, why = True, ''
            elif not theirs:
                ok, why = False, f'export has no value; set up the test product as GO-LIVE 5.3 says (ours: {mine})'
            elif [m.lower() for m in mine] == [t.lower() for t in theirs]:
                ok, why = False, f'case differs: ours {mine}, your store writes {theirs}. Don’t import: the builder (and the values: checks here) must change to match.'
            elif col == 'Product category' and any('el-4-8-5' in t for t in theirs):
                ok, why = True, ''  # store writes the taxonomy ID of the same category; our breadcrumb is the other allowed form
            else:
                ok, why = False, (f'ours {mine}, your store writes {theirs}. If the test product was set up as GO-LIVE 5.3 '
                                  f'says, don’t import: the builder (and the values: checks here) must change to match.')
            check(f'export: {col} spelt as your store writes it', ok, why)

    # ---------------- legacy-header twin file, if given
    if a.legacy:
        lh, lrows, lraw = read_csv(a.legacy)
        check('legacy: every column is in the legacy template', all(h in LEGACY_TEMPLATE for h in lh),
              f'{[h for h in lh if h not in LEGACY_TEMPLATE]}')
        conv = [{TO_CURRENT.get(k, k): v for k, v in r.items()} for r in lrows]
        check('legacy: same rows and values as the current-format file', conv == rows)

    report(len(set(handles)), len(rows))

if __name__ == '__main__':
    main()
