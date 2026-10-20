#!/usr/bin/env python3
"""Check products-shopify.csv against Shopify's product CSV template and the Grace & Bloom site.

The shop sells digital downloads only, so this checks the file is set up for downloads: nothing needs
shipping, no weights, no stock tracking, and no physical wording (postage, envelopes, paper weights...)
in the descriptions.

Rules come from https://help.shopify.com/en/manual/products/import-export/using-csv and Shopify's
sample product_template.csv. Prices are checked against the site itself: assets/js/products.js is
run in Node and each price is worked out the way shop.js does (base price + option surcharge).

Usage: python3 -I validate_csv.py <csv> <site folder> [taxonomy categories.txt]
The taxonomy file is Shopify/product-taxonomy's dist/en/categories.txt (download it from GitHub).
With none given it looks for web/taxonomy/cat-v2026-08.txt or web/taxonomy/categories.txt next to this
script; if neither exists the breadcrumb check prints SKIP, never PASS.
Exit code 0 = every check passed (warnings and skips allowed), 1 = at least one check failed.
"""
import csv
import html
import json
import os
import re
import subprocess
import sys
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))

# Shopify's current product CSV template header, in order (57 columns).
SHOPIFY_HEADER = [
    'Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
    'Published on online store', 'Status', 'SKU', 'Barcode',
    'Option1 name', 'Option1 value', 'Option1 Linked To',
    'Option2 name', 'Option2 value', 'Option2 Linked To',
    'Option3 name', 'Option3 value', 'Option3 Linked To',
    'Price', 'Compare-at price', 'Cost per item', 'Charge tax', 'Tax code',
    'Unit price total measure', 'Unit price total measure unit', 'Unit price base measure', 'Unit price base measure unit',
    'Inventory tracker', 'Inventory quantity', 'Continue selling when out of stock',
    'Weight value (grams)', 'Weight unit for display', 'Requires shipping', 'Fulfillment service',
    'Product image URL', 'Image position', 'Image alt text', 'Variant image URL', 'Gift card',
    'SEO title', 'SEO description', 'Color (product.metafields.shopify.color-pattern)',
    'Google Shopping / Google product category', 'Google Shopping / Gender', 'Google Shopping / Age group',
    'Google Shopping / Manufacturer part number (MPN)', 'Google Shopping / Ad group name',
    'Google Shopping / Ads labels', 'Google Shopping / Condition', 'Google Shopping / Custom product',
    'Google Shopping / Custom label 0', 'Google Shopping / Custom label 1', 'Google Shopping / Custom label 2',
    'Google Shopping / Custom label 3', 'Google Shopping / Custom label 4',
]
# Fields that belong to the product, so only the first row of each product may fill them.
PRODUCT_LEVEL = ['Title', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
                 'Published on online store', 'Status', 'Option1 name', 'Option2 name', 'Option3 name', 'Gift card']
MUST_BE_BLANK = ['Product image URL', 'Image position', 'Variant image URL', 'Compare-at price',
                 'Option2 name', 'Option2 value', 'Option3 name', 'Option3 value']
SKU_RE = re.compile(r'^GB-DL-[A-Z]{3}-[A-Z0-9]+(-[A-Z0-9]+)?$')
HANDLE_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
PRICE_RE = re.compile(r'^\d+\.\d{2}$')
WEIGHT_UNITS = {'', 'g', 'kg', 'lb', 'oz'}

# How shop.js prices things. If any of these lines change, the price check below may no longer
# reproduce what the site shows, so the check fails until someone re-reads shop.js.
SHOP_JS_PRICING = {
    'basket line price (unit)': 'function unit(l) { var p = GB.byId(l.id); return p.price + (p.variants ? p.variants.options[l.v][1] : 0); }',
    'quick view price': 'function price() { return p.price + (vr ? vr.options[qv.v][1] : 0); }',
    'grid card price': '<span class="price">\' + money(p.price) + \'</span>',
    'money format': "var money = function (n) { return cfg.currency + n.toFixed(2); };",
}

# Physical-product wording that must not appear in a download's title or description.
PHYSICAL_WORDS = [
    (r'\bpostage\b', 'postage'), (r'\bpostal\b', 'postal'), (r'\benvelopes?\b', 'envelope'),
    (r'(?<![A-Za-z])gsm\b', 'gsm'), (r'\bgicl[ée]e\b', 'giclée'), (r'\bA6\b', 'A6'),  # "350gsm" counts too
    (r'\bdeliver(y|ies|ed|s)?\b', 'delivery'), (r'\bdispatch(ed|es)?\b', 'dispatch'), (r'\bcouriers?\b', 'courier'),
    (r'\bparcels?\b', 'parcel'), (r'\bship(ping|ped|s)?\b', 'shipping'), (r'\bfoil\b', 'foil'),
    (r'\bcotton rag\b', 'cotton rag'), (r'\bpacked\b', 'packed'), (r'\bin stock\b', 'in stock'),
]

# The digital wording every description must carry (same as the site's Digital delivery and Refunds text).
REQUIRED_PHRASES = [
    ('<strong>Digital download.</strong>', 'the "Digital download." note'),
    ('Nothing is posted.', '"Nothing is posted."'),
    ('Formats and sizes:', 'a "Formats and sizes:" line'),
    ('What you may do with the files:', 'the licence line ("What you may do with the files:")'),
    ('How you get your files:', 'a "How you get your files:" line'),
    ('You normally have 14 days to cancel an online order', 'the 14-day cancellation sentence'),
    ('as long as you agreed to this before buying', 'the condition that the customer agreed before buying'),
    ('We confirm that agreement in your order confirmation email.', 'the promise to confirm it by email'),
    ('Consumer Rights Act 2015', 'the Consumer Rights Act 2015 faulty-file rights'),
]
# "...right ends once X" / "can't be cancelled|returned ... once X": X must be one thing, the download starting.
TRIGGER_RE = re.compile(r'(?:right ends|can’t be (?:cancelled|returned)[^.<]*?)\s+once ([^,.<]+)')
EXPECTED_TRIGGER = 'your download starts'

DEFAULT_TAXONOMY = [os.path.join(HERE, 'web', 'taxonomy', 'cat-v2026-08.txt'),
                    os.path.join(HERE, 'web', 'taxonomy', 'categories.txt')]


class Report:
    def __init__(self):
        self.fails, self.warns, self.passes, self.skips = [], [], [], []

    def skip(self, name, why):
        self.skips.append(name)
        print(f'SKIP  {name} ({why})')

    def check(self, name, problems):
        if problems:
            self.fails.append((name, problems))
            print(f'FAIL  {name}')
            for p in problems[:12]:
                print(f'        - {p}')
            if len(problems) > 12:
                print(f'        ... and {len(problems) - 12} more')
        else:
            self.passes.append(name)
            print(f'PASS  {name}')

    def warn(self, msg):
        self.warns.append(msg)
        print(f'WARN  {msg}')


def site_catalogue(site):
    out = subprocess.run(['node', os.path.join(HERE, 'load_products.cjs'), site],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def main(csv_path, site, taxonomy_path=None):
    r = Report()
    raw = open(csv_path, 'rb').read()

    # --- file ---
    probs = []
    if raw.startswith(b'\xef\xbb\xbf'):
        probs.append('file starts with a byte-order mark; the first header would not read as "Title"')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        probs.append(f'not UTF-8: {e}')
        text = raw.decode('utf-8', 'replace')
    if len(raw) > 15 * 1024 * 1024:
        probs.append(f'{len(raw)} bytes is over Shopify’s 15 MB product CSV limit')
    r.check('File is UTF-8 without a byte-order mark and under 15 MB', probs)

    table = list(csv.reader(text.splitlines()))
    if not table:
        print('\nStopping: the file is empty.')
        return 1
    header, body = table[0], [row for row in table[1:] if any(c.strip() for c in row)]

    # --- header: against the list here and the saved copy of Shopify's template ---
    probs = []
    if header != SHOPIFY_HEADER:
        for i in range(max(len(header), len(SHOPIFY_HEADER))):
            a = header[i] if i < len(header) else '(missing)'
            b = SHOPIFY_HEADER[i] if i < len(SHOPIFY_HEADER) else '(extra)'
            if a != b:
                probs.append(f'column {i + 1}: file has "{a}", Shopify template has "{b}"')
    ref = os.path.join(HERE, 'shopify-template-header.csv')
    if not os.path.exists(ref):
        probs.append('tools/shopify-template-header.csv (the saved copy of Shopify’s template header) is missing')
    else:
        sample = next(csv.reader(open(ref, encoding='utf-8')))
        if sample != SHOPIFY_HEADER:
            probs.append('the saved copy of Shopify’s template header differs from the list in this validator')
        if header != sample:
            probs.append('the file’s header differs from tools/shopify-template-header.csv')
    r.check(f'Header matches Shopify’s product CSV template exactly ({len(SHOPIFY_HEADER)} columns, same order)', probs)

    r.check('Every row has the same number of fields as the header',
            [f'row {i + 2}: {len(row)} fields' for i, row in enumerate(body) if len(row) != len(header)])
    keys = [header[0].lstrip('﻿')] + header[1:] if header else header
    if 'URL handle' not in keys or 'Title' not in keys:
        print('\nStopping: without "Title" and "URL handle" columns the rest cannot be checked.')
        return 1
    rows = [dict(zip(keys, row)) for row in body]

    # --- grouping: one row per variant, product fields on the first row only ---
    probs, groups = [], {}
    prev = None
    for i, row in enumerate(rows, start=2):
        h = row.get('URL handle', '')
        if not HANDLE_RE.match(h):
            probs.append(f'row {i}: URL handle "{h}" is not lower-case letters, numbers and dashes')
        if h != prev:
            if h in groups:
                probs.append(f'row {i}: rows for "{h}" are not next to each other')
            groups.setdefault(h, [])
            if not row.get('Title'):
                probs.append(f'row {i}: first row of "{h}" has no Title')
        else:
            filled = [c for c in PRODUCT_LEVEL if row.get(c)]
            if filled:
                probs.append(f'row {i}: later variant row of "{h}" fills product-level columns {filled}')
        groups[h].append((i, row))
        prev = h
    r.check('One row per variant; product details only on each product’s first row', probs)

    site_data = site_catalogue(site)
    products = {p['id']: p for p in site_data['products']}
    cat_label = {c['id']: c['label'] for c in site_data['categories']}
    tags = site_data['tags']
    site_variants = sum(len(p['rows']) for p in products.values())

    # --- product count and identity ---
    probs = []
    if len(groups) != len(products):
        probs.append(f'{len(groups)} products in the CSV, {len(products)} on the site')
    if len(rows) != site_variants:
        probs.append(f'{len(rows)} variant rows in the CSV, {site_variants} on the site')
    for h in groups:
        if h not in products:
            probs.append(f'"{h}" is in the CSV but not on the site')
    for pid in products:
        if pid not in groups:
            probs.append(f'"{pid}" is on the site but missing from the CSV')
    for h, grp in groups.items():
        if h in products and grp[0][1].get('Title', '') != products[h]['name']:
            probs.append(f'"{h}": Title "{grp[0][1]["Title"]}" differs from the site name "{products[h]["name"]}"')
    r.check(f'Product count and names match the site ({len(products)} products, {site_variants} variants)', probs)

    # --- options ---
    probs = []
    for h, grp in groups.items():
        first = grp[0][1]
        name = first.get('Option1 name', '')
        values = [row.get('Option1 value', '') for _, row in grp]
        combos = [(row.get('Option1 value', ''), row.get('Option2 value', ''), row.get('Option3 value', '')) for _, row in grp]
        dupes = sorted({c for c in combos if combos.count(c) > 1})
        if dupes:
            probs.append(f'"{h}": option combination repeated: {dupes}')
        if any(not v for v in values):
            probs.append(f'"{h}": a variant row has no Option1 value')
        if h not in products:
            continue
        p = products[h]
        if p['optionLabel'] is None:
            if (name, values) != ('Title', ['Default Title']):
                probs.append(f'"{h}" has no options on the site, so it needs one row with Option1 name "Title" '
                             f'and value "Default Title"; found {name!r} {values}')
        else:
            if name != p['optionLabel']:
                probs.append(f'"{h}": Option1 name "{name}" differs from the site’s "{p["optionLabel"]}"')
            site_values = [x['option'] for x in p['rows']]
            if values != site_values:
                probs.append(f'"{h}": option values {values} differ from the site’s {site_values}')
    r.check('Option combinations are unique per product and match the site’s options', probs)

    # --- how the site prices things ---
    shop_js = open(os.path.join(site, 'assets/js/shop.js'), encoding='utf-8').read()
    r.check('shop.js still prices items the way this validator reproduces (base + option surcharge, £ and 2 decimals)',
            [f'{what}: expected line not found in shop.js, re-read how it prices before trusting the price check'
             for what, line in SHOP_JS_PRICING.items() if line not in shop_js])

    # --- prices, row by row against the site ---
    probs, checked = [], 0
    for h, grp in groups.items():
        if h not in products:
            continue
        site_rows = {x['option'] if x['option'] is not None else 'Default Title': x for x in products[h]['rows']}
        for n, (i, row) in enumerate(grp):
            price = row.get('Price', '')
            label = row.get('Option1 value')
            if not PRICE_RE.match(price):
                probs.append(f'row {i} "{h}": price "{price}" is not a plain number with 2 decimals (no £ sign)')
                continue
            try:
                value = Decimal(price)
            except InvalidOperation:
                probs.append(f'row {i} "{h}": price "{price}" does not parse')
                continue
            if value <= 0:
                probs.append(f'row {i} "{h}": price {price} is not above zero')
            s = site_rows.get(label)
            if s is None:
                probs.append(f'row {i} "{h}": no site price for option "{label}"')
            elif price != s['shown']:
                probs.append(f'row {i} "{h}" / {label}: CSV £{price}, site shows £{s["shown"]}')
            if n == 0 and price != products[h]['gridShown']:
                probs.append(f'row {i} "{h}": first variant £{price} differs from the site’s grid price '
                             f'£{products[h]["gridShown"]} (Shopify shows the first variant’s price in lists)')
            checked += 1
    r.check(f'Prices match the site’s own prices row by row ({checked} rows)', probs)

    # --- digital: no shipping, no weight, manual fulfilment ---
    probs = []
    for h, grp in groups.items():
        for i, row in grp:
            if row.get('Requires shipping') != 'FALSE':
                probs.append(f'row {i} "{h}": Requires shipping is "{row.get("Requires shipping")}", must be FALSE for a download')
            if row.get('Weight value (grams)', '') not in ('', '0'):
                probs.append(f'row {i} "{h}": weight "{row.get("Weight value (grams)")}" should be blank or 0 for a download')
            if row.get('Weight unit for display', '') not in WEIGHT_UNITS:
                probs.append(f'row {i} "{h}": Weight unit for display "{row.get("Weight unit for display")}" is not g, kg, lb, oz or blank')
            if row.get('Fulfillment service') != 'manual':
                probs.append(f'row {i} "{h}": Fulfillment service is "{row.get("Fulfillment service")}", expected "manual"')
    r.check('Digital set-up on every row: Requires shipping FALSE, no weight, Fulfillment service manual', probs)

    # --- inventory: downloads are not stock-tracked; the three columns must agree ---
    probs = []
    for h, grp in groups.items():
        for i, row in grp:
            tracker = row.get('Inventory tracker', '')
            qty = row.get('Inventory quantity', '')
            policy = row.get('Continue selling when out of stock', '')
            if tracker == '':
                if qty != '':
                    probs.append(f'row {i} "{h}": stock not tracked but Inventory quantity is "{qty}" (leave it blank)')
                if policy != 'continue':
                    probs.append(f'row {i} "{h}": stock not tracked, so "Continue selling when out of stock" should be '
                                 f'"continue", not "{policy}" (deny only applies to tracked stock)')
            elif tracker == 'shopify':
                probs.append(f'row {i} "{h}": Inventory tracker is "shopify"; a download should not be stock-tracked '
                             f'(it would show as sold out at 0)')
                if not qty.isdigit():
                    probs.append(f'row {i} "{h}": tracked stock needs a whole-number quantity, has "{qty}"')
                if policy != 'deny':
                    probs.append(f'row {i} "{h}": tracked stock should use "deny", has "{policy}"')
            else:
                probs.append(f'row {i} "{h}": Inventory tracker "{tracker}" is not blank or "shopify"')
    r.check('Inventory not tracked on every row (tracker blank, quantity blank, keep selling = continue)', probs)

    # --- launch settings ---
    probs = []
    for h, grp in groups.items():
        first = grp[0][1]
        for col, want in (('Status', 'draft'), ('Published on online store', 'FALSE'), ('Vendor', 'Grace & Bloom'),
                          ('Gift card', 'FALSE')):
            if first.get(col) != want:
                probs.append(f'"{h}": {col} is "{first.get(col)}", expected "{want}"')
        for i, row in grp:
            if row.get('Charge tax') != 'TRUE':
                probs.append(f'row {i} "{h}": Charge tax is "{row.get("Charge tax")}", expected "TRUE"')
            for col in MUST_BE_BLANK:
                if row.get(col):
                    probs.append(f'row {i} "{h}": {col} should be blank, has "{row.get(col)}"')
    r.check('Draft, unpublished, Vendor Grace & Bloom, taxable, no images, no compare-at price, one option at most', probs)

    # --- type, tags, category ---
    probs = []
    for h, grp in groups.items():
        if h not in products:
            continue
        first, p = grp[0][1], products[h]
        if first.get('Type') != cat_label[p['cat']]:
            probs.append(f'"{h}": Type "{first.get("Type")}" should be the site category "{cat_label[p["cat"]]}"')
        want_tags = ', '.join(tags.get(h, []))
        if first.get('Tags') != want_tags:
            probs.append(f'"{h}": Tags "{first.get("Tags")}" differ from the site’s "{want_tags}"')
        if not first.get('Product category', ''):
            probs.append(f'"{h}": Product category is blank')
    r.check('Type = site category, Tags = site search tags, Product category filled in', probs)

    # A breadcrumb is only checked against a real taxonomy file; with none found the check is SKIPPED, not passed.
    if taxonomy_path is None:
        taxonomy_path = next((t for t in DEFAULT_TAXONOMY if os.path.exists(t) and os.path.getsize(t) > 1000), None)
    name = 'Product category is a real Shopify Standard Product Taxonomy breadcrumb'
    if not taxonomy_path or not os.path.exists(taxonomy_path):
        r.skip(name, f'no taxonomy file found ({taxonomy_path or "none given, defaults missing"})')
    else:
        taxonomy, version = set(), '?'
        for line in open(taxonomy_path, encoding='utf-8'):
            if line.startswith('#') and 'Categories:' in line:
                version = line.split('Categories:', 1)[1].strip()
            elif ' : ' in line:
                taxonomy.add(line.split(' : ', 1)[1].strip())
        probs = []
        if len(taxonomy) < 1000:
            probs.append(f'{taxonomy_path} holds only {len(taxonomy)} categories: not a real taxonomy file')
        for h, grp in groups.items():
            pc = grp[0][1].get('Product category', '')
            if pc and pc not in taxonomy:
                probs.append(f'"{h}": Product category "{pc}" is not in the taxonomy file')
        r.check(f'{name} (checked against {os.path.basename(taxonomy_path)}, taxonomy {version}, '
                f'{len(taxonomy)} categories)', probs)

    # --- SKUs ---
    skus = [row.get('SKU', '') for row in rows]
    probs = [f'SKU "{s}" is blank or not in the GB-DL-XXX-NAME[-OPTION] pattern' for s in skus if not SKU_RE.match(s)]
    probs += [f'SKU "{s}" is used more than once' for s in sorted({s for s in skus if skus.count(s) > 1})]
    r.check(f'SKUs are present, unique and follow one pattern ({len(skus)} SKUs)', probs)

    # --- descriptions: site text, digital wording, one cancellation point ---
    probs = []
    for h, grp in groups.items():
        if h not in products:
            continue
        d, p = grp[0][1].get('Description', ''), products[h]
        if html.escape(p['blurb'], quote=False) not in d:
            probs.append(f'"{h}": description does not contain the site blurb')
        for det in p['details']:
            if html.escape(det, quote=False) not in d:
                probs.append(f'"{h}": description is missing the site detail "{det}"')
        for phrase, what in REQUIRED_PHRASES:
            if phrase not in d:
                probs.append(f'"{h}": description is missing {what}')
        triggers = {t.strip() for t in TRIGGER_RE.findall(d)}
        if triggers != {EXPECTED_TRIGGER}:
            probs.append(f'"{h}": the point where the right to cancel ends should be "once {EXPECTED_TRIGGER}" '
                         f'and nothing else; found {sorted(triggers) or "none"}')
        if re.search(r'<script|\son\w+\s*=', d, re.I):
            probs.append(f'"{h}": description contains script or event-handler HTML')
    r.check('Descriptions carry the site blurb and details, the digital-download note, formats, licence, '
            'and one cancellation point (once the download starts)', probs)

    # --- no physical wording ---
    probs = []
    for h, grp in groups.items():
        first = grp[0][1]
        for col in ('Title', 'Description'):
            text_ = html.unescape(re.sub(r'<[^>]+>', ' ', first.get(col, '')))
            for pat, word in PHYSICAL_WORDS:
                m = re.search(pat, text_, re.I if word != 'A6' else 0)
                if m:
                    probs.append(f'"{h}" {col}: physical-product wording "{m.group(0)}" ({word})')
    r.check('No physical-product wording (postage, envelope, gsm, giclée, A6, delivery, dispatch, courier, '
            'parcel, shipping, foil, cotton rag, packed, in stock) in titles or descriptions', probs)

    # --- placeholders still to fill: one warning per distinct placeholder ---
    seen = {}
    for h, grp in groups.items():
        for ph in re.findall(r'\[[^\]]+\]', html.unescape(grp[0][1].get('Description', ''))):
            seen.setdefault(ph, []).append(h)
    for ph, hs in seen.items():
        where = 'every product' if len(set(hs)) == len(groups) else ', '.join(sorted(set(hs)))
        r.warn(f'placeholder {ph} is in {where}: fill it in (build_csv.py or Shopify) before products go Active')

    print()
    print(f'{len(r.passes)} checks passed, {len(r.fails)} failed, {len(r.skips)} skipped, {len(r.warns)} warning(s).')
    return 1 if r.fails else 0


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
