#!/usr/bin/env python3
"""Build the Shopify product import (products-shopify.csv) for Chainline Cycles from the site's own bike data.

Every bike, price and detail comes from the bike data on the page (<script type="application/json" id="shop-data"> in
sites/chainline/index.html): the same data the page's script draws the cards and the basket from. The delivery and
return-collection prices in the descriptions come from the page's own wording. Nothing about a bike is typed here.
Change a bike on the site (then run sync_bikes.py), run this again, then validate_shopify_csv.py.

  python3 build_shopify_csv.py [--site PATH] [--out DIR]

Each bike is a one-off, so each is its own product with a single variant: stock 1, never oversold, draft, not yet on
the Online Store. Shopify is fine for bikes (its ban is on vapes and e-liquids). Python 3 standard library only.
"""
import argparse
import csv
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Shopify's current product CSV columns, in template order: the same header row as launch/full-bars/products-shopify.csv
# (validate_shopify_csv.py checks every column against the template list copied from launch/full-bars).
CURRENT = ['Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
           'Published on online store', 'Status', 'SKU',
           'Option1 name', 'Option1 value', 'Option2 name', 'Option2 value', 'Option3 name', 'Option3 value',
           'Price', 'Charge tax', 'Inventory tracker', 'Inventory quantity',
           'Continue selling when out of stock', 'Weight value (grams)', 'Weight unit for display',
           'Requires shipping', 'Fulfillment service', 'Product image URL', 'SEO title', 'SEO description']

TYPE_LABEL = {'road': 'Road', 'hybrid': 'Hybrid', 'gravel': 'Gravel', 'ebike': 'E-bike', 'folding': 'Folding', 'kids': 'Kids'}
TYPE_WORD = {'road': 'road bike', 'hybrid': 'hybrid bike', 'gravel': 'gravel bike', 'ebike': 'e-bike',
             'folding': 'folding bike', 'kids': "kids' bike"}
# Fixed choices, not business facts:
# - Product category is left blank: pick it in Shopify admin (GO-LIVE.md section 5). Shopify doesn't require it.
# - Weight: every bike gets the same nominal shipping weight, SHIPPING_UNIT_G. It is NOT the bike's real weight: it's a
#   counter. Shopify's own shipping rates are per order, not per item, so GO-LIVE.md section 5 step 4 sets weight-based
#   rates in 1 kg steps (up to 1 kg £39, up to 2 kg £78, ...), which makes Shopify charge £39 per bike, exactly as the
#   site's basket adds it up. If a courier ever prices by real weight, replace these with real weights and change the
#   rates to match. validate_shopify_csv.py checks every bike carries the same unit.
# - Charge tax is TRUE until the accountant says otherwise (GO-LIVE.md section 1).
SINGLE_OPTION = ('Title', 'Default Title')   # how Shopify marks a product with no options
SHIPPING_UNIT_G = 1000   # one bike = 1 kg in Shopify's weight-based rates (a counter, not a real weight; see above)
EBIKE_TBC = '£[e-bike delivery price]'


def find_site():
    for start in (HERE, os.getcwd()):
        d = start
        while True:
            cand = os.path.join(d, 'sites', 'chainline', 'index.html')
            if os.path.isfile(cand):
                return os.path.dirname(cand)
            if os.path.dirname(d) == d:
                break
            d = os.path.dirname(d)
    sys.exit('Could not find sites/chainline/index.html; pass --site')


def one(rx, src, what):
    m = re.search(rx, src, re.S)
    if not m:
        sys.exit(f'Not found in index.html: {what}')
    return m


def text(fragment):
    t = re.sub(r'<[^>]+>', '', fragment)
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()


def read_site(site):
    """The bike data, plus the return-collection prices as the page's cancellation section states them."""
    src = open(os.path.join(site, 'index.html'), encoding='utf-8').read()
    data = json.loads(one(r'<script type="application/json" id="shop-data">(.*?)</script>', src, 'the #shop-data block').group(1))
    cancel = text(one(r'<details id="cancel">(.*?)</details>', src, 'the "Cancelling an order" block (#cancel)').group(1))
    m = one(r"we'll collect it for (£\d+) \(e-bikes ([^)]+)\)", cancel, 'the return collection price in #cancel')
    return data, {'bike': m.group(1), 'ebike': m.group(2)}


def esc(s):
    return html.escape(str(s), quote=False)


def money(n):
    return '£{:,}'.format(n)


def title(b):
    return f"{b['make']} {b['model']} ({b['year']})"


def body_html(b, delivery, collect):
    ebike = b['type'] == 'ebike'
    rows = [('Size', b['size']), ('Gears', b['gears'])] + [tuple(r) for r in b.get('specs', [])]
    send = (f"E-bikes go by a specialist courier, because Royal Mail and Parcelforce don't carry them: "
            f"{money(delivery['ebike']) if delivery.get('ebike') else EBIKE_TBC}." if ebike
            else f"UK delivery is {money(delivery['bike'])}, boxed and 90% built, with the tools you need in the box.")
    parts = [
        f"<p>Used {esc(b['year'])} {esc(b['make'])} {esc(b['model'])} ({TYPE_WORD[b['type']]}), refurbished in our workshop. "
        'Each bike is a one-off: this listing is for this exact bike.</p>',
        '<h2>The bike</h2>',
        '<ul>' + ''.join(f'<li><strong>{esc(k)}:</strong> {esc(v)}</li>' for k, v in rows) + '</ul>',
        f"<h2>Workshop ticket {esc(b['no'])}</h2>",
        f"<p>Our 30-point workshop check: passed, and every point signed off on the ticket, which comes with the bike. "
        f"{esc(b['tagLabel'])}: {esc(b['tag'])}.</p>",
        '<p>Frame number checked on BikeRegister: not listed as stolen there when we checked. '
        'We only buy bikes with proof of ownership and photo ID.</p>',
    ]
    if ebike:
        parts.append("<p>Battery health is our capacity test result as a share of the battery's rated capacity "
                     "(the watt-hours on its label). Range also depends on the rider, the route, the weather and the "
                     "assist level, so it isn't a range promise. Like every e-bike we sell, it meets the UK rules for "
                     "an electrically assisted pedal cycle: motor rated at no more than 250W, and assistance cuts out at "
                     "15.5 mph. Riders must be 14 or over.</p>")
    parts += [
        '<h2>Collection or delivery</h2>',
        f"<p>Collect it from the workshop for free and we'll set the saddle height with you. {esc(send)}</p>",
        '<h2>Warranty and your rights</h2>',
        "<p>3-month warranty on the whole bike, parts and labour, from the day you collect it or it's delivered. "
        "It's on top of your Consumer Rights Act 2015 rights, not instead of them.</p>",
        '<p>You can also cancel for any reason within 14 days, starting the day after you get the bike (Consumer '
        f"Contracts Regulations 2013). Returning it is at your cost: bring it back to the workshop, or we collect it for "
        f"{collect['bike']} (e-bikes {esc(collect['ebike'])}).</p>",
        '<p>The drawings on our website are illustrations, not photos of this bike: ask us for photos before you buy.</p>',
    ]
    return ''.join(parts)


def tags(b):
    t = ['Refurbished', TYPE_LABEL[b['type']], 'Size ' + b['size'], str(b['year'])]
    if b['type'] == 'ebike':
        t.append('Specialist courier')   # for the e-bike shipping profile (GO-LIVE.md section 5)
    return ', '.join(t)


def seo_description(b):
    s = (f"Used {b['year']} {b['make']} {b['model']}, refurbished and checked in our workshop. Size {b['size']}. "
         f"{b['tagLabel']}: {b['tag']}. Frame number checked on BikeRegister. 3-month warranty on top of your legal rights.")
    return s[:320]


def build(site):
    data, collect = read_site(site)
    delivery = data['delivery']
    rows = []
    # The shop's default order: newest in (highest ticket number) first
    for b in sorted(data['bikes'], key=lambda b: -int(b['no'])):
        r = dict.fromkeys(CURRENT, '')
        r.update({
            'Title': title(b), 'URL handle': b['id'], 'Description': body_html(b, delivery, collect),
            'Vendor': b['make'], 'Product category': '',
            'Type': 'Refurbished e-bike' if b['type'] == 'ebike' else 'Refurbished bike', 'Tags': tags(b),
            'Published on online store': 'FALSE', 'Status': 'draft', 'SKU': 'CL-' + b['no'],
            'Option1 name': SINGLE_OPTION[0], 'Option1 value': SINGLE_OPTION[1],
            'Price': f"{b['price']}.00", 'Charge tax': 'TRUE', 'Inventory tracker': 'shopify', 'Inventory quantity': '1',
            'Continue selling when out of stock': 'deny', 'Weight value (grams)': str(SHIPPING_UNIT_G), 'Weight unit for display': 'kg',
            'Requires shipping': 'TRUE', 'Fulfillment service': 'manual', 'Product image URL': '',
            'SEO title': (title(b) + ' | Chainline Cycles')[:70], 'SEO description': seo_description(b),
        })
        rows.append(r)
    return data, rows


def write(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(CURRENT)
        for r in rows:
            w.writerow([r[h] for h in CURRENT])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--site', help='the sites/chainline folder (found automatically)')
    ap.add_argument('--out', default=HERE, help='folder to write products-shopify.csv to (default: this folder)')
    a = ap.parse_args()
    data, rows = build(a.site or find_site())
    path = os.path.join(a.out, 'products-shopify.csv')
    write(path, rows)
    print(f'{len(rows)} bikes, one draft product each -> {path}')


if __name__ == '__main__':
    main()
