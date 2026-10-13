#!/usr/bin/env python3
"""Build Shopify product-import CSVs for Full Bars from the site's own pages.

Every price comes from the data-prices JSON on each product page's picker form, the same data
site.js uses to show prices on the site. Change a price on the site, run this again, then run
validate_shopify_csv.py. Handset weights come from facts.json (the file check_site_facts.py checks
the site against). Nothing here is typed in by hand except the packing-weight estimate.

  python3 build_shopify_csv.py [--site PATH] [--out DIR] [--facts FACTS.json]

Writes products-shopify.csv (Shopify's current column names) and
products-shopify-legacy-headers.csv (the same rows under Shopify's older column names, only for
use if the importer rejects the first file's headers).
"""
import argparse
import csv
import html
import json
import os
import re
import sys

# ---------------------------------------------------------------- fixed choices (not business facts)
TYPE = 'Refurbished smartphone'
# Shopify Standard Product Taxonomy: el-4-8-5. The CSV takes the breadcrumb or the ID, not both.
CATEGORY = 'Electronics > Communications > Telephony > Mobile & Smart Phones'
OPTION_NAMES = ('Storage', 'Condition', 'Colour')   # same labels as the site's picker
GRADE_CODE = {'Excellent': 'EX', 'Very Good': 'VG', 'Good': 'GD'}
# Handset weight in grams is the maker's figure, weight_g in facts.json (the same file the site's specs are
# checked against, so the CSV and the site can't drift apart), plus PACKING_G for box, cable, SIM tool,
# test printout and outer packaging. PACKING_G is an estimate: weigh one packed parcel and change it.
FACTS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'facts.json')
PACKING_G = 200
# Shopify takes payment at checkout, and the site promises "If a part has been replaced, we tell you before you pay"
# and "Phones with any replaced part are sold by email order only, so you always hear about it before paying". So only
# units with all original manufacturer parts are stocked on these listings, and every description says so.
PARTS_LINE = ('Every phone sold through this listing has all original manufacturer parts. Phones with any replaced part '
              'are sold by email order only, so you always hear about it before paying.')


def handset_weights(path, handles):
    """weight_g for each product handle, from facts.json. Stops with a message if any is missing."""
    try:
        with open(path, encoding='utf-8') as f:
            models = json.load(f)['models']
    except (OSError, ValueError, KeyError, TypeError) as e:
        sys.exit(f'Could not read handset weights from {path}: {e!r}')
    if not isinstance(models, dict):
        sys.exit(f'{path}: "models" is not an object')
    weights = {}
    for h in handles:
        w = models.get(h, {}).get('weight_g') if isinstance(models.get(h), dict) else None
        if not isinstance(w, int) or isinstance(w, bool) or not 80 <= w <= 400:
            sys.exit(f'{path}: no usable weight_g for {h} (got {w!r}); add the handset weight in grams')
        weights[h] = w
    return weights

# Current product CSV columns used here, in the order of Shopify's template. Columns we have no data for
# (barcode, compare-at price, cost, images per variant, Google Shopping...) are left out: Shopify only
# requires Title (plus URL handle when a product has variants).
CURRENT = ['Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
           'Published on online store', 'Status', 'SKU',
           'Option1 name', 'Option1 value', 'Option2 name', 'Option2 value', 'Option3 name', 'Option3 value',
           'Price', 'Charge tax', 'Inventory tracker', 'Inventory quantity',
           'Continue selling when out of stock', 'Weight value (grams)', 'Weight unit for display',
           'Requires shipping', 'Fulfillment service', 'Product image URL', 'SEO title', 'SEO description']
# The same fields under Shopify's older (legacy) column names.
LEGACY = {'Title': 'Title', 'URL handle': 'Handle', 'Description': 'Body (HTML)', 'Vendor': 'Vendor',
          'Product category': 'Product Category', 'Type': 'Type', 'Tags': 'Tags',
          'Published on online store': 'Published', 'Status': 'Status', 'SKU': 'Variant SKU',
          'Option1 name': 'Option1 Name', 'Option1 value': 'Option1 Value', 'Option2 name': 'Option2 Name',
          'Option2 value': 'Option2 Value', 'Option3 name': 'Option3 Name', 'Option3 value': 'Option3 Value',
          'Price': 'Variant Price', 'Charge tax': 'Variant Taxable', 'Inventory tracker': 'Variant Inventory Tracker',
          'Inventory quantity': 'Variant Inventory Qty', 'Continue selling when out of stock': 'Variant Inventory Policy',
          'Weight value (grams)': 'Variant Grams', 'Weight unit for display': 'Variant Weight Unit',
          'Requires shipping': 'Variant Requires Shipping', 'Fulfillment service': 'Variant Fulfillment Service',
          'Product image URL': 'Image Src', 'SEO title': 'SEO Title', 'SEO description': 'SEO Description'}
LEGACY_ORDER = ['Handle', 'Title', 'Body (HTML)', 'Vendor', 'Product Category', 'Type', 'Tags', 'Published',
                'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value',
                'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Qty',
                'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price',
                'Variant Requires Shipping', 'Variant Taxable', 'Image Src', 'SEO Title', 'SEO Description',
                'Variant Weight Unit', 'Status']
PRODUCT_LEVEL = {'Title', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
                 'Published on online store', 'Status', 'Option1 name', 'Option2 name', 'Option3 name',
                 'SEO title', 'SEO description'}


def find_site():
    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        d = start
        while True:
            cand = os.path.join(d, 'sites', 'full-bars')
            if os.path.isfile(os.path.join(cand, 'shop.html')):
                return cand
            if os.path.dirname(d) == d:
                break
            d = os.path.dirname(d)
    sys.exit('Could not find sites/full-bars; pass --site')


def text(fragment):
    t = re.sub(r'<[^>]+>', '', fragment)
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()


def esc(s):
    return html.escape(s, quote=False)


def one(rx, src, what):
    m = re.search(rx, src, re.S)
    if not m:
        sys.exit(f'Not found: {what}')
    return m.group(1)


def read_product(site, fname):
    src = open(os.path.join(site, 'products', fname), encoding='utf-8').read()
    form = one(r'(<form class="picker" id="picker".*?</form>)', src, fname + ' picker')
    tag = form[:form.index('>') + 1]
    attr = lambda n: html.unescape(one(r'\b' + n + r'="([^"]*)"', tag, fname + ' ' + n))
    radios = lambda n: [html.unescape(v) for v in re.findall(r'name="' + n + r'" value="([^"]*)"', form)]
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)]
    ld = next(j for j in ld if j.get('@type') == 'Product')
    panels = {text(h): [text(li) for li in re.findall(r'<li>(.*?)</li>', ul, re.S)]
              for h, ul in re.findall(r'<div class="panel[^"]*"[^>]*><h2[^>]*>(.*?)</h2><ul class="ticks">(.*?)</ul>', src, re.S)}
    box_note = text(one(r'In the box</h2><ul class="ticks">.*?</ul><p class="small">(.*?)<a ', src, fname + ' box note'))
    box_note = re.sub(r'\s*Sending a phone back.*$', '', box_note)
    return {
        'handle': fname[:-5], 'model': attr('data-model'),
        'prices': json.loads(attr('data-prices')), 'grade_text': json.loads(attr('data-grades')),
        'storages': radios('storage'), 'grades': radios('grade'), 'colours': radios('colour'),
        'h1': text(one(r'<h1>(.*?)</h1>', src, fname + ' h1')),
        'sub': text(one(r'<p class="pd-sub">(.*?)</p>', src, fname + ' pd-sub')),
        'year': text(one(r'<div class="eyebrow">(.*?)</div>', src, fname + ' eyebrow')).split('·')[-1].strip(),
        'title': text(one(r'<title>(.*?)</title>', src, fname + ' title')),
        'meta': html.unescape(one(r'<meta name="description" content="([^"]*)"', src, fname + ' meta')),
        'brand': ld['brand']['name'],
        'specs': [(text(a), text(b)) for a, b in re.findall(r'<div><dt>(.*?)</dt><dd>(.*?)</dd></div>', src)],
        'checks': panels['Checked before it ships'], 'box': panels['In the box'], 'box_note': box_note,
        'promise': re.sub(r'\s*How it works$', '', text(one(r'<p class="promise-note">(.*?)</p>', src, fname + ' promise'))),
        'buy_note': text(one(r'<p class="buy-note" id="buyNote"[^>]*>(.*?)</p>', src, fname + ' buy note')),
        'grade_intro': text(one(r'<h2>Condition grades</h2><p>(.*?)</p>', src, fname + ' grade intro')),
        'pictures': text(one(r'<p class="small">(Product pictures are illustrations.*?)</p>', src, fname + ' pictures note')),
    }


def shop_cards(site):
    src = open(os.path.join(site, 'shop.html'), encoding='utf-8').read()
    out = {}
    for tag, h in re.findall(r'(<article class="card"[^>]*>)<a href="products/([^"]+)\.html"', src):
        out[h] = {k: re.search(r'data-' + k + r'="([^"]*)"', tag).group(1) for k in ('series', 'type', 'usbc')}
    return out


def model_code(handle):
    m = re.match(r'iphone-(\d+)(?:-(pro-max|pro|plus|mini))?$', handle)
    if m:
        return 'IP' + m.group(1) + {'pro-max': 'PM', 'pro': 'P', 'plus': 'PL', 'mini': 'MI', None: ''}[m.group(2)]
    return {'galaxy-s23': 'GS23', 'pixel-8': 'PX8'}[handle]


def colour_code(colour):
    return re.sub(r'[^A-Za-z]', '', colour.split()[0])[:3].upper()


def tags(p, card):
    t = ['Refurbished', 'Unlocked', p['brand'], p['year']]
    s, types = card['series'], card['type'].split()
    if s.isdigit():
        t += ['iPhone', f'iPhone {s} series']
    else:
        t += [{'galaxy': 'Samsung Galaxy', 'pixel': 'Google Pixel'}[s], 'Android']
    if 'pro' in types:
        t.append('Pro')
    if 'big' in types:
        t.append('Big screen')
    if 'small' in types:
        t.append('Compact')
    t.append('USB-C' if card['usbc'] == '1' else 'Lightning')
    lowest = min(min(g.values()) for g in p['prices'].values())
    if lowest < 300:
        t.append('Under £300')
    return ', '.join(t)


def body_html(p):
    li = lambda items: '<ul>' + ''.join(f'<li>{esc(i)}</li>' for i in items) + '</ul>'
    parts = [
        f'<p>{esc(p["sub"])}</p>',
        f'<p>Refurbished and unlocked. Released {esc(p["year"])}. Every phone passes our full function test, '
        'has battery health of at least 85% and comes with our 12-month warranty. Every phone is IMEI-checked '
        'on CheckMEND when we buy it and again before it ships, and its IMEI is never altered.</p>',
        # The site promises that a replaced part is disclosed before payment, so a pay-first checkout only ever sells
        # phones with all original parts (GO-LIVE.md section 4). validate_shopify_csv.py requires PARTS_LINE.
        f'<p>{esc(PARTS_LINE)}</p>',
        '<h2>Condition grades</h2>',
        f'<p>{esc(p["grade_intro"])}</p>',
        '<ul>' + ''.join(f'<li><strong>{esc(g)}:</strong> {esc(p["grade_text"][g])}</li>' for g in p['grades']) + '</ul>',
        '<h2>Checked before it ships</h2>', li(p['checks']),
        '<h2>In the box</h2>', li(p['box']), f'<p>{esc(p["box_note"])}</p>',
        '<h2>Specifications</h2>',
        '<ul>' + ''.join(f'<li><strong>{esc(k)}:</strong> {esc(v)}</li>' for k, v in p['specs']) + '</ul>',
        # same line as the site: the ready-made product images (og/products/*.png) are illustrations too
        f'<p>{esc(p["pictures"])}</p>',
        '<h2>Warranty and your rights</h2>',
        f'<p>{esc(p["promise"])}</p>',
        '<p>You can also cancel for any reason within 14 days, starting the day after your phone is delivered '
        '(Consumer Contracts Regulations 2013).</p>',
        '<p>Exact battery % and colour are confirmed by email within 1 working day of your order; '
        'if we can’t match your choice, we refund you in full.</p>',
    ]
    return ''.join(parts)


def build(site, facts=FACTS_JSON):
    cards = shop_cards(site)
    files = sorted(f for f in os.listdir(os.path.join(site, 'products')) if f.endswith('.html'))
    products = [read_product(site, f) for f in files]
    handset_g = handset_weights(facts, [p['handle'] for p in products])
    # shop.html order: newest first, the same order the site lists them
    order = list(cards)
    products.sort(key=lambda p: order.index(p['handle']))
    rows = []
    for p in products:
        first = True
        for st in p['storages']:
            for gr in p['grades']:
                for co in p['colours']:
                    r = dict.fromkeys(CURRENT, '')
                    r.update({
                        'URL handle': p['handle'],
                        'SKU': f"{model_code(p['handle'])}-{st.replace('GB', '')}-{colour_code(co)}-{GRADE_CODE[gr]}",
                        'Option1 value': st, 'Option2 value': gr, 'Option3 value': co,
                        'Price': f"{p['prices'][st][gr]:.2f}",
                        'Charge tax': 'TRUE', 'Inventory tracker': 'shopify', 'Inventory quantity': '0',
                        'Continue selling when out of stock': 'deny',
                        'Weight value (grams)': str(handset_g[p['handle']] + PACKING_G),
                        'Weight unit for display': 'g', 'Requires shipping': 'TRUE',
                        'Fulfillment service': 'manual', 'Product image URL': '',
                    })
                    if first:
                        r.update({
                            'Title': p['h1'], 'Description': body_html(p), 'Vendor': p['brand'],
                            'Product category': CATEGORY, 'Type': TYPE, 'Tags': tags(p, cards[p['handle']]),
                            'Published on online store': 'FALSE', 'Status': 'draft',
                            'Option1 name': OPTION_NAMES[0], 'Option2 name': OPTION_NAMES[1],
                            'Option3 name': OPTION_NAMES[2],
                            'SEO title': p['title'], 'SEO description': p['meta'],
                        })
                        first = False
                    rows.append(r)
    return products, rows


def write(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(header)
        for r in rows:
            w.writerow([r[h] for h in header])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site')
    ap.add_argument('--out', default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--facts', default=FACTS_JSON, help='where the handset weights come from (default: facts.json here)')
    a = ap.parse_args()
    site = a.site or find_site()
    products, rows = build(site, a.facts)
    write(os.path.join(a.out, 'products-shopify.csv'), CURRENT, rows)
    legacy_rows = [{LEGACY[k]: v for k, v in r.items()} for r in rows]
    write(os.path.join(a.out, 'products-shopify-legacy-headers.csv'), LEGACY_ORDER, legacy_rows)
    print(f'{len(products)} products, {len(rows)} variants -> {a.out}')


if __name__ == '__main__':
    main()
