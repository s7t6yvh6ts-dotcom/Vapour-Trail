#!/usr/bin/env python3
"""Write the bike cards and the bikes' structured data into sites/chainline/index.html, from the page's own bike data.

The bike data is the JSON block <script type="application/json" id="shop-data"> near the end of the page. It's the only
place a bike, its details or its price is typed. The page's script draws the cards and the basket from it. This script
writes the same cards into the HTML (so the bikes still show with JavaScript off), the matching Product and Offer
structured data (<script type="application/ld+json" id="ld-bikes">), the bike count, and the example workshop ticket in
the hero (every row of it, for the bike named by "heroTicket" in the data). Run it after every change to the data (a bike sold, a price changed), then run
check_site.py.

  python3 sync_bikes.py [--site PATH] [--check]

--check   change nothing; exit 1 if the cards, structured data, count or ticket don't match the data.

The warranty length on the cards ("3-month warranty") is typed here and in the page's script; check_site.py checks it
matches the warranty everywhere else on the page.
Python 3 standard library only.
"""
import argparse
import json
import os
import re
import sys

TYPE_LABEL = {'road': 'Road', 'hybrid': 'Hybrid', 'gravel': 'Gravel', 'ebike': 'E-bike', 'folding': 'Folding', 'kids': 'Kids'}
CATEGORY = {'road': 'Road bike', 'hybrid': 'Hybrid bike', 'gravel': 'Gravel bike', 'ebike': 'Electric bike',
            'folding': 'Folding bike', 'kids': "Kids' bike"}
BANDS = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'ONE', 'K14', 'K16', 'K20', 'K24', 'K26']
# Shown wherever the e-bike courier price would go while "ebike" is null in the data (it isn't set yet).
EBIKE_TBC = '£[e-bike delivery price]'
REQUIRED = ('id', 'no', 'make', 'model', 'year', 'type', 'size', 'band', 'gears', 'tagLabel', 'tag', 'price')

HERE = os.path.dirname(os.path.abspath(__file__))


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


def esc(s):
    """The same escaping as esc() in the page's script, so the two produce identical markup."""
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#39;'))


def money(n):
    return '£{:,}'.format(n)


def read_data(src):
    """The parsed #shop-data block. Stops with a plain message if it's missing or wrong."""
    m = re.search(r'<script type="application/json" id="shop-data">(.*?)</script>', src, re.S)
    if not m:
        sys.exit('index.html has no <script type="application/json" id="shop-data"> block')
    try:
        data = json.loads(m.group(1))
    except ValueError as e:
        sys.exit(f'The bike data (#shop-data) is not valid JSON: {e}')
    problems = data_problems(data)
    if problems:
        sys.exit('The bike data (#shop-data) has problems:\n  ' + '\n  '.join(problems))
    return data


def data_problems(data):
    out = []
    if not isinstance(data, dict) or not isinstance(data.get('bikes'), list):
        return ['it must be {"delivery": {...}, "bikes": [...]}']
    dl = data.get('delivery')
    if not isinstance(dl, dict) or not isinstance(dl.get('bike'), int) or isinstance(dl.get('bike'), bool) or dl['bike'] <= 0:
        out.append('"delivery": {"bike": …} must be a whole number of pounds above 0')
    elif dl.get('ebike') is not None and (not isinstance(dl.get('ebike'), int) or isinstance(dl.get('ebike'), bool) or dl['ebike'] <= 0):
        out.append('"delivery": {"ebike": …} must be null (not set yet) or a whole number of pounds above 0')
    seen_id, seen_no = set(), set()
    for i, b in enumerate(data['bikes']):
        where = f'bike {i + 1}'
        if not isinstance(b, dict):
            out.append(f'{where} is not an object')
            continue
        where = f'bike {i + 1} ({b.get("id", "no id")})'
        missing = [k for k in REQUIRED if k not in b]
        if missing:
            out.append(f'{where} is missing {", ".join(missing)}')
            continue
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', str(b['id'])):
            out.append(f'{where}: id must be lower-case letters, digits and hyphens (it becomes the Shopify URL handle)')
        if b['id'] in seen_id:
            out.append(f'{where}: id used twice')
        if not re.fullmatch(r'\d{4}', str(b['no'])):
            out.append(f'{where}: "no" (the workshop ticket number) must be four digits, as a string')
        if b['no'] in seen_no:
            out.append(f'{where}: ticket number {b["no"]} used twice')
        seen_id.add(b['id'])
        seen_no.add(b['no'])
        if b['type'] not in TYPE_LABEL:
            out.append(f'{where}: type must be one of {", ".join(TYPE_LABEL)}')
        if b['band'] not in BANDS:
            out.append(f'{where}: band must be one of {", ".join(BANDS)}')
        if not isinstance(b['price'], int) or isinstance(b['price'], bool) or b['price'] <= 0:
            out.append(f'{where}: price must be a whole number of pounds above 0')
        if not isinstance(b['year'], int) or isinstance(b['year'], bool) or not 1900 <= b['year'] <= 2100:
            out.append(f'{where}: year must be a four-digit number')
        for key in ('specs', 'ticketRows'):
            rows = b.get(key, [])
            if not isinstance(rows, list) or not all(isinstance(r, list) and len(r) == 2 and all(isinstance(x, str) for x in r) for r in rows):
                out.append(f'{where}: {key} must be a list of ["Label", "value"] pairs')
        if 'checked' in b and not isinstance(b['checked'], str):
            out.append(f'{where}: "checked" (the BikeRegister check date on the ticket) must be text')
    hero = data.get('heroTicket')
    if hero not in seen_id:
        out.append(f'"heroTicket" must be the id of a bike in the data (the bike the example workshop ticket describes); '
                   f'it is {hero!r}. If that bike has sold, point it at one that is in stock.')
    return out


def delivery_note(b, delivery):
    if b['type'] == 'ebike':
        return 'Free collection · e-bike courier ' + (money(delivery['ebike']) if delivery.get('ebike') else EBIKE_TBC)
    return 'Free collection · ' + money(delivery['bike']) + ' UK delivery'


def glyph(kind):
    kind = kind if kind in TYPE_LABEL else 'road'
    return ('<svg class="glyph" viewBox="0 0 120 76" aria-hidden="true" focusable="false"><use href="#g-' + kind + '"/></svg>')


def card(b, delivery):
    """One card, exactly as cardHTML(b, false) in the page's script writes it."""
    name = b['make'] + ' ' + b['model']
    rows = [['Size', b['size']], ['Gears', b['gears']]] + list(b.get('specs', []))
    return ('<li class="card" id="bike-' + esc(b['id']) + '">'
            + '<div class="card-top">' + glyph(b['type']) + '<span class="card-no">Ticket ' + esc(b['no']) + '</span></div>'
            + '<div><h3>' + esc(name) + '</h3><p class="card-meta">' + esc(b['year']) + ' · ' + esc(TYPE_LABEL[b['type']]) + ' · 3-month warranty</p></div>'
            + '<dl class="specs">' + ''.join('<div><dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd></div>' for k, v in rows) + '</dl>'
            + '<p class="fit"><b>' + esc(b['tagLabel']) + '</b><span>' + esc(b['tag']) + '</span></p>'
            + '<div class="card-foot"><p class="price-wrap"><span class="price">' + money(b['price']) + '</span><small>'
            + esc(delivery_note(b, delivery)) + '</small></p>'
            + '<button type="button" class="btn btn-sm btn-primary js-only" data-add="' + esc(b['id'])
            + '" aria-label="Add to basket: ' + esc(name) + '">Add to basket</button>'
            + '</div></li>')


def newest_first(bikes):
    """The shop's default order ("Newest in"): highest ticket number first, as the page's script sorts."""
    return sorted(bikes, key=lambda b: -int(b['no']))


def product_name(b):
    return f"{b['make']} {b['model']} ({b['year']})"


def structured_data(data):
    """Product and Offer structured data for every bike, as one ItemList. Honest by construction: no ratings or
    reviews, every bike a used one refurbished in the workshop, one in stock each, and a delivery price only where
    the price is set."""
    delivery = data['delivery']
    items = []
    for pos, b in enumerate(newest_first(data['bikes']), 1):
        offer = {
            '@type': 'Offer',
            'price': f"{b['price']}.00",
            'priceCurrency': 'GBP',
            'itemCondition': 'https://schema.org/RefurbishedCondition',
            'availability': 'https://schema.org/InStock',
            'inventoryLevel': {'@type': 'QuantitativeValue', 'value': 1},
            'seller': {'@id': '#store'},
        }
        rate = delivery['ebike'] if b['type'] == 'ebike' else delivery['bike']
        if rate:
            offer['shippingDetails'] = {
                '@type': 'OfferShippingDetails',
                'shippingRate': {'@type': 'MonetaryAmount', 'value': f'{rate}.00', 'currency': 'GBP'},
                'shippingDestination': {'@type': 'DefinedRegion', 'addressCountry': 'GB'},
            }
        items.append({
            '@type': 'ListItem', 'position': pos,
            'item': {
                '@type': 'Product',
                '@id': '#bike-' + b['id'],
                'name': product_name(b),
                'sku': 'CL-' + b['no'],
                'brand': {'@type': 'Brand', 'name': b['make']},
                'model': b['model'],
                'category': CATEGORY[b['type']],
                'size': b['size'],
                'description': (f"Used {b['year']} {b['make']} {b['model']}, refurbished in our workshop. "
                                f"Workshop ticket {b['no']}. {b['tagLabel']}: {b['tag']}. Size {b['size']}, {b['gears']} gears."),
                'offers': offer,
            },
        })
    ld = {'@context': 'https://schema.org', '@type': 'ItemList', 'name': 'Bikes in stock',
          'numberOfItems': len(items), 'itemListElement': items}
    # "</" can't appear inside a <script> block
    return json.dumps(ld, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def count_text(n):
    return f"{n} {'bike' if n == 1 else 'bikes'} in stock"


GRID_RX = re.compile(r'(<ul class="bike-grid" id="bike-grid">)(.*?)(</ul>)', re.S)
LD_RX = re.compile(r'(<script type="application/ld\+json" id="ld-bikes">)(.*?)(</script>)', re.S)
COUNT_RX = re.compile(r'(<p id="result-count" class="mono" aria-live="polite">)(.*?)(</p>)', re.S)
TICKET_RX = re.compile(r'(<!-- ticket: written by sync_bikes\.py[^>]*-->\n)(.*?)([ \t]*<!-- /ticket -->)', re.S)
CHECKED_TBC = '[check date]'


def ticket(b):
    """The example workshop ticket's body for bike b: its number, its rows and the link to its card."""
    rows = [('Bike', esc(b['make'] + ' ' + b['model'])), ('Year', esc(b['year'])), ('Size', esc(b['size'])),
            ('30-point check', '<span class="stamp">Passed</span>'),
            ('Frame number', 'Not listed as stolen on BikeRegister (checked ' + esc(b.get('checked', CHECKED_TBC)) + ')'),
            (esc(b['tagLabel']), esc(b['tag']))] + [(esc(k), esc(v)) for k, v in b.get('ticketRows', [])]
    return ('      <p class="ticket-no"><span>Ticket</span><b>' + esc(b['no']) + '</b></p>\n      <dl>\n'
            + ''.join(f'       <div><dt>{k}</dt><dd>{v}</dd></div>\n' for k, v in rows)
            + '      </dl>\n      <p class="ticket-foot"><span>In the shop now</span><a href="#bike-' + esc(b['id'])
            + '" id="ticket-link">See it, ' + money(b['price']) + '<span class="vh"> (' + esc(b['make'] + ' ' + b['model'])
            + ')</span></a></p>\n')


def synced(src):
    """The page with every generated part rewritten from the data. Stops with a message if a part can't be found."""
    data = read_data(src)
    delivery = data['delivery']
    cards = ''.join(card(b, delivery) for b in newest_first(data['bikes']))
    for rx, what in ((GRID_RX, 'the bike grid <ul class="bike-grid" id="bike-grid">'), (LD_RX, 'the #ld-bikes structured data'),
                     (COUNT_RX, 'the #result-count line'), (TICKET_RX, 'the example ticket\'s markers (<!-- ticket: written by sync_bikes.py … --> and <!-- /ticket -->)')):
        if not rx.search(src):
            sys.exit(f'Could not find {what} in index.html')
    out = GRID_RX.sub(lambda m: m.group(1) + cards + m.group(3), src, count=1)
    out = LD_RX.sub(lambda m: m.group(1) + structured_data(data) + m.group(3), out, count=1)
    out = COUNT_RX.sub(lambda m: m.group(1) + count_text(len(data['bikes'])) + m.group(3), out, count=1)
    bike = next(b for b in data['bikes'] if b['id'] == data['heroTicket'])
    out = TICKET_RX.sub(lambda m: m.group(1) + ticket(bike) + m.group(3), out, count=1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--site', help='the sites/chainline folder (found automatically)')
    ap.add_argument('--check', action='store_true', help='change nothing; exit 1 if the page is out of date')
    a = ap.parse_args()
    path = os.path.join(a.site or find_site(), 'index.html')
    with open(path, encoding='utf-8') as f:
        src = f.read()
    out = synced(src)
    n = len(read_data(src)['bikes'])
    if a.check:
        if out != src:
            print(f'OUT OF DATE: the cards, structured data, count or ticket in {path} do not match the bike data. '
                  'Run sync_bikes.py (without --check).')
            sys.exit(1)
        print(f'Up to date: {n} bikes.')
        return
    if out == src:
        print(f'Already up to date: {n} bikes.')
        return
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print(f'Updated {path}: {n} bikes.')


if __name__ == '__main__':
    main()
