#!/usr/bin/env python3
"""Build products-shopify.csv for Grace & Bloom from the site's own catalogue (assets/js/products.js).

The shop sells DIGITAL DOWNLOADS ONLY: nothing is posted, so every row has Requires shipping FALSE,
no weight, and no stock tracking (a file never runs out).

Format: Shopify's current product CSV template (57 columns, "Title, URL handle, Description, ..."),
saved in shopify-template-header.csv. Source: https://help.shopify.com/en/manual/products/import-export/using-csv
and its sample product_template.csv. One row per variant; the first row of a product carries the product
fields, later rows repeat only the URL handle and the variant fields.

Column choices for a digital product (Shopify Help Center, product CSV pages):
- Requires shipping FALSE, Weight value (grams) blank (blank or 0 when shipping isn't required),
  Weight unit for display blank (Shopify's default applies).
- Inventory tracker blank = inventory not tracked. Inventory quantity is then left blank too.
- Continue selling when out of stock: "continue". "deny" only means something when stock is tracked,
  and with tracking off a download can never show as sold out.
- Fulfillment service "manual" (no third-party fulfilment service). The Digital Products app sends the files.

Usage: python3 -I build_csv.py <site folder> <output csv>
"""
import csv
import html
import json
import os
import subprocess
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER_FILE = os.path.join(HERE, 'shopify-template-header.csv')

# ---------------------------------------------------------------------------------------------
# Answers still to come. When they're known, put them here (keep the wording plain), rebuild and
# re-import, instead of editing 19 descriptions by hand in Shopify. Anything in [square brackets]
# is flagged by validate_csv.py as still to fill in.
FORMATS = '[to confirm]'
HOW_YOU_GET_FILES = '[to confirm: a download link on the order page, by email, or both]'
LICENCE = ('[to confirm: personal use only, or small-business use, and what isn’t allowed, '
           'such as reselling or sharing the files]')
# ---------------------------------------------------------------------------------------------

# Shopify Standard Product Taxonomy breadcrumbs, checked against Shopify/product-taxonomy release v2026-08
# (dist/en/categories.txt). "Media > Printables" has no card, tag or bookmark child, so those use the parent,
# as Shopify's help suggests when there is no exact match.
CATEGORY = {
    'printable': 'Media > Printables',
    'wallart':   'Media > Printables > Wall Art',
    'planner':   'Media > Printables > Planners',
}

# product id -> (SKU, taxonomy key). Every product on the site must be listed here.
# GB-DL- marks a download, so these never clash with the SKUs of the earlier physical range.
PRODUCT = {
    'peony-birthday':      ('GB-DL-CRD-PEONY',    'printable'),
    'sweetpea-thanks':     ('GB-DL-CRD-SWEETPEA', 'printable'),
    'winter-bloom-xmas':   ('GB-DL-CRD-WINTER',   'printable'),
    'anemone-thinking':    ('GB-DL-CRD-ANEMONE',  'printable'),
    'birthday-collection': ('GB-DL-CRD-BDAY5',    'printable'),
    'dusk-dahlia':         ('GB-DL-PRT-DAHLIA',   'wallart'),
    'wild-meadow':         ('GB-DL-PRT-MEADOW',   'wallart'),
    'birth-flower':        ('GB-DL-PRT-BIRTH',    'wallart'),
    'botanical-trio':      ('GB-DL-PRT-TRIO',     'wallart'),
    'pressed-bookmark':    ('GB-DL-KPS-BOOKMARK', 'printable'),
    'posy-gift-tags':      ('GB-DL-KPS-TAGS12',   'printable'),
    'focus-planner':       ('GB-DL-JNL-FOCUS',    'planner'),
    'weekly-reset':        ('GB-DL-JNL-WEEKLY',   'planner'),
    'brain-dump-pad':      ('GB-DL-JNL-BRAINDUMP', 'planner'),
    'wall-calendar-2027':  ('GB-DL-JNL-CAL2027',  'planner'),
    'gym-journal':         ('GB-DL-SLF-GYM',      'planner'),
    'home-reset':          ('GB-DL-SLF-HOME',     'planner'),
    'money-planner':       ('GB-DL-SLF-MONEY',    'planner'),
    'habit-pad':           ('GB-DL-SLF-HABITS',   'planner'),
}

# option value -> SKU suffix (only the Focus Day Planner has options: its Cover)
OPTION_CODE = {
    'Charcoal bloom': 'CHARCOAL', 'Blush bloom': 'BLUSH',
}

# The same wording as the site (index.html "Digital delivery" and "Refunds & cancellations", and the
# product quick view in shop.js). Plain text; escaped when the description is built.
DIGITAL_NOTE = 'Digital download.'
DIGITAL_TEXT = 'You download the files after you pay. Nothing is posted.'
DEVICE_TEXT = 'You’ll need a device that can open the files. For a paper copy, you’ll need a printer or a print shop.'
CANCEL_TEXT = ('Your files are available straight away. You normally have 14 days to cancel an online order, '
               'but for digital content that right ends once your download starts, as long as you agreed to this '
               'before buying. We confirm that agreement in your order confirmation email.')
FAULTY_TEXT = ('If a file is faulty, can’t be opened or isn’t as described, you’re entitled to a repair or a '
               'replacement or, if that can’t be done or doesn’t fix it, money off the price, up to a full refund, '
               'under the Consumer Rights Act 2015. Nothing here affects those rights.')


def esc(s):
    return html.escape(s, quote=False)


def load_site(site):
    out = subprocess.run(['node', os.path.join(HERE, 'load_products.cjs'), site],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def body_html(p):
    li = lambda items: '<ul>' + ''.join('<li>' + esc(x) + '</li>' for x in items) + '</ul>'
    return ''.join([
        '<p>' + esc(p['blurb']) + '</p>',
        li(p['details']),
        '<p><strong>' + esc(DIGITAL_NOTE) + '</strong> ' + esc(DIGITAL_TEXT) + '</p>',
        li(['Formats and sizes: ' + FORMATS,
            'How you get your files: ' + HOW_YOU_GET_FILES,
            'What you may do with the files: ' + LICENCE,
            DEVICE_TEXT]),
        '<p><strong>Cancelling.</strong> ' + esc(CANCEL_TEXT) + '</p>',
        '<p>' + esc(FAULTY_TEXT) + '</p>',
    ])


def money(x):
    return str(Decimal(str(x)).quantize(Decimal('0.01')))


def main(site, out_path):
    header = next(csv.reader(open(HEADER_FILE, encoding='utf-8')))
    data = load_site(site)
    cat_label = {c['id']: c['label'] for c in data['categories']}
    tags = data['tags']
    missing = [p['id'] for p in data['products'] if p['id'] not in PRODUCT]
    if missing:
        sys.exit('No SKU/category mapping for: ' + ', '.join(missing) + ' (add them to PRODUCT in build_csv.py)')
    unknown = sorted({r['option'] for p in data['products'] for r in p['rows']
                      if r['option'] is not None and r['option'] not in OPTION_CODE})
    if unknown:
        sys.exit('No SKU suffix for option(s): ' + ', '.join(unknown) + ' (add them to OPTION_CODE in build_csv.py)')

    rows = []
    for p in data['products']:
        sku, tax_key = PRODUCT[p['id']]
        for i, r in enumerate(p['rows']):
            row = dict.fromkeys(header, '')
            row['URL handle'] = p['id']
            if r['option'] is None:
                row['Option1 value'] = 'Default Title'
                row['SKU'] = sku
            else:
                row['Option1 value'] = r['option']
                row['SKU'] = sku + '-' + OPTION_CODE[r['option']]
            # base price plus the option's surcharge, exactly as shop.js adds them
            row['Price'] = money(Decimal(str(p['price'])) + Decimal(str(r['surcharge'])))
            row['Charge tax'] = 'TRUE'
            row['Inventory tracker'] = ''            # not tracked: a download never runs out
            row['Inventory quantity'] = ''
            row['Continue selling when out of stock'] = 'continue'
            row['Weight value (grams)'] = ''
            row['Weight unit for display'] = ''
            row['Requires shipping'] = 'FALSE'
            row['Fulfillment service'] = 'manual'
            if i == 0:
                row['Title'] = p['name']
                row['Description'] = body_html(p)
                row['Vendor'] = data['config']['shopName']
                row['Product category'] = CATEGORY[tax_key]
                row['Type'] = cat_label[p['cat']]
                row['Tags'] = ', '.join(tags.get(p['id'], []))
                row['Published on online store'] = 'FALSE'
                row['Status'] = 'draft'
                row['Option1 name'] = p['optionLabel'] or 'Title'
                row['Gift card'] = 'FALSE'
            rows.append(row)

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    print(f'wrote {out_path}: {len(data["products"])} products, {len(rows)} variant rows')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
