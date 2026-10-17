#!/usr/bin/env python3
"""Check sites/chainline/index.html (and the two order emails) before you publish it, and again before launch.

  python3 check_site.py [--site PATH] [--csv products-shopify.csv] [--emails DIR] [--launch]

Without --launch (the preview): the page must be a safe, honest preview.
  - Every price that appears more than once agrees everywhere it appears: each bike (data, card, structured data, CSV,
    example ticket), each service (price list and booking form, the tube too), UK delivery, the e-bike courier, and
    both return-collection prices, on the page, in both order emails and in the CSV. A [placeholder] counts as a value:
    the same placeholder everywhere is fine, a mix of placeholder and price is a FAIL.
  - The rules that can close the business are pinned: the e-bike limits (250W, 15.5 mph, 14+, the 6 km/h throttle
    rule and that we sell no faster throttle), no derestriction kits, the 3-month warranty wherever it's stated, and the
    14-day cancellation wording. Changing or deleting any of them is a FAIL.
  - The legal sections are there, nothing forbidden is on the page, the contact links show what they dial or mail, and
    the preview switches are ON (search engines kept out, the prototype banner, the "not trading yet" notes), because
    the stock, prices and business details are still [placeholders]. Placeholders are listed as a NOTE.

With --launch: everything above, and it also fails while any preview switch is still on or any [placeholder] is left
on the page or in either order email (GO-LIVE.md, sections 3 and 10). The customer's own brackets in the cancellation
form ([your name], [date] and so on) are meant to stay and are never counted.

Exit code 0 = no FAIL. Python 3 standard library only.
"""
import argparse
import csv
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import sync_bikes  # noqa: E402  (same folder: the bike-data rules and the card/structured-data writer)

PLACEHOLDER = re.compile(r'\[[^\[\]<>"=]+\]')
MONEY = r'£(?:\d{1,3}(?:,\d{3})*(?!\d)|\[[^\]]+\])'   # a price (£39, £1,149), or a bracketed price placeholder
# The model cancellation form's blanks: the customer fills these in, so they stay at launch.
CUSTOMER_BLANKS = ['[bike, size, ticket number]', '[date]', '[your name]', '[your address]']
SCRIPT_HOSTS = ('https://cdnjs.cloudflare.com/', 'https://cdn.jsdelivr.net/npm/', 'https://unpkg.com/')
LEGAL = {
    'terms': ('Terms of sale', ['Chainline Cycles is a trading name of', 'The contract is made when',
                                'The contract is in English only', 'Our liability', 'Citizens Advice consumer helpline on 0808 223 1133']),
    'warranty': ('Warranty and your legal rights', ['This warranty is given by', 'applies in the UK', 'lasts for 3 months',
                                                    "It's on top of your Consumer Rights Act 2015 rights, not instead of them",
                                                    'How to claim', 'This warranty is extra, and it never limits your Consumer Rights Act rights',
                                                    'within 30 days of getting the bike you can reject it for a full refund',
                                                    "you're entitled to a repair or replacement",
                                                    'Within 30 days of getting it, you can reject a faulty bike',
                                                    'six years after delivery (five years in Scotland)']),
    'delivery': ('Delivery and returns', ['UK delivery is £', 'We always deliver within 30 days',
                                          'The bike is our responsibility until it', 'Royal Mail and Parcelforce']),
    'cancel': ('Cancelling an order', ['within 14 days, starting the day after you get the bike', 'returning it is at your cost',
                                       'to your original payment method', "if that's sooner"]),
    'cancel-form': ('the model cancellation form', ['I hereby give notice that I cancel my contract of sale of the following goods']),
    'workshop-terms': ('Workshop terms', ['sends a request, not a booking', "You don't pay anything online", 'reasonable care and skill']),
    'selling-terms': ('Selling us your bike', ["you're 18 or over", 'Cycle to Work', 'proof of ownership and photo ID',
                                               "it can't flag a bike that was never registered", 'never in cash', 'tell the police']),
    'privacy': ('Privacy and cookies', ['is the data controller', 'ICO registration number', 'Your rights',
                                        "we'll acknowledge your complaint within 30 days", 'Information Commission',
                                        'still known as the ICO']),
    'cookies': ('Cookies and what this page stores', ["doesn't set any cookies", 'saved in your browser, if your browser allows it',
                                                      "page's web address", 'Google Fonts']),
}
# The rules that can close the business (CLAUDE.md): each must stay on the page exactly as written.
RULES = [
    ('e-bike: 250W in the rules', '<span class="eapc-val">250W</span>'),
    ('e-bike: 250W explained', "The motor can't be rated above 250 watts continuous."),
    ('e-bike: 15.5 mph cut-out in the rules', '<span class="eapc-val">15.5 mph</span>'),
    ('e-bike: 15.5 mph explained', 'The motor stops helping at 15.5 mph.'),
    ('e-bike: riders 14 or over', '<span class="eapc-val">14+</span>'),
    ('e-bike: throttle limit without pedalling', 'a throttle can only power the bike up to 3.7 mph (6 km/h)'),
    ('e-bike: we sell no throttle above walking pace', 'Every e-bike we sell has no throttle, or one that stops at that speed.'),
    ('e-bike: we sell no faster throttle of any kind', "We don't sell any e-bike with a faster throttle, whichever kind it is."),
    ('e-bike: no fast-throttle e-bikes in "what we won\'t sell"', 'E-bikes with a throttle that works above 3.7 mph (6 km/h) without pedalling.'),
    ('e-bike: no derestriction kits', 'Derestriction kits, also sold as delimiters, that lift the 15.5 mph cut-out.'),
    ('e-bike: no conversion kits above 250W', 'Conversion kits above 250W.'),
    ('e-bike: no off-road or unlimited modes', 'E-bikes with an "off-road" or "unlimited" mode that lets the motor help above 15.5 mph.'),
    ('warranty: 3 months on the promise strip', '<h3>3-month warranty</h3>'),
    ('warranty: 3 months in the FAQ', 'Three months on the whole bike, parts and labour'),
    ('warranty: 3 months in the small print', 'lasts for 3 months from the day you collect the bike'),
    ('warranty: 3 months in the meta description', 'A 3-month warranty on top of your legal rights.'),
    ('cancellation: 14 days in the FAQ', 'you have 14 days from the day after you get the bike to change your mind'),
    ('cancellation: 14 days in the small print', 'you can cancel for any reason within 14 days, starting the day after you get the bike, whether we delivered it or you collected it'),
    ('cancellation: 14 days in the terms', 'you can cancel for any reason within 14 days, starting the day after you get the bike. <a href="#cancel">'),
]
# Strings that only belong on the preview. --launch fails while any is still there.
PREVIEW_STRINGS = [
    ('the prototype banner', '<strong>Prototype:</strong> placeholder stock'),
    ('the footer prototype line', 'Prototype: placeholder stock, prices and contact details.'),
    ('the "Not trading yet" note above the small print', 'Not trading yet.'),
    ('"In this preview the forms don\'t send anything" (privacy)', "In this preview the forms don't send anything."),
    ('the booking form\'s prototype reply (script)', "Prototype: requests aren't sent anywhere yet."),
    ('the offer form\'s prototype reply (script)', "Prototype: offers aren't sent yet."),
    ('the checkout\'s "Payments aren\'t connected yet" (script)', "Payments aren't connected yet."),
]
# Ofcom's numbers for drama and examples, and example domains: never real contact details.
FAKE_CONTACT = re.compile(r'(?:\+44\s?|0)(?:7700\s?900\d{3}|1632\s?960\d{3}|20\s?7946\s?0\d{3}|1[2-6]1\s?496\s?0\d{3}|11[3-8]\s?496\s?0\d{3}'
                          r'|191\s?498\s?0\d{3}|28\s?9649\s?6\d{3}|29\s?2018\s?0\d{3})|@example\.|chainline\.example|0191 000')

results = []


def check(name, ok, detail=''):
    """ok: truthy = PASS, falsy = FAIL, None = NOTE (worth knowing; not a failure)."""
    results.append((name, None if ok is None else bool(ok), detail))


def text(fragment):
    t = re.sub(r'<br\s*/?>', '\n', fragment)
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    return re.sub(r'[ \t]+', ' ', t)


def flat(fragment):
    """Visible text on one line: tags, scripts and styles dropped, entities decoded, spaces collapsed."""
    t = re.sub(r'<script>.*?</script>|<style>.*?</style>|<!--.*?-->', ' ', fragment, flags=re.S)
    return re.sub(r'\s+', ' ', text(t)).strip()


def block(src, rx):
    m = re.search(rx, src, re.S)
    return m.group(1) if m else ''


def read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None


def wrapped_in_try(script, needle):
    """Every use of needle in the script sits inside a try { } (a try opened before it with no catch yet)."""
    bad = 0
    for m in re.finditer(re.escape(needle), script):
        before = script[:m.start()]
        t = before.rfind('try {')
        if t == -1 or 'catch' in before[t:]:
            bad += 1
    return bad


def money(n):
    return '£{:,}'.format(n)


def same_everywhere(name, found, expected=None):
    """found: [(where, value)]. PASS when every value (and the expected one, if given) is the same."""
    values = {v for _, v in found} | ({expected} if expected is not None else set())
    detail = ', '.join(f'{w}: {v}' for w, v in found) + (f'; the data says {expected}' if expected is not None else '')
    check(name, found and len(values) == 1, detail if (not found or len(values) != 1) else '')


def check_head(src):
    check('head: starts <!doctype html>', src.lstrip().lower().startswith('<!doctype html>'))
    check('head: <html lang="en-GB">', re.search(r'<html lang="en-GB"', src) is not None)
    head = block(src, r'<head>(.*?)</head>')
    check('head: charset utf-8 first', re.match(r'\s*<meta charset="utf-8">', head) is not None)
    check('head: viewport with viewport-fit=cover', 'viewport-fit=cover' in block(head, r'<meta name="viewport" content="([^"]*)"'))
    check('head: color-scheme dark', '<meta name="color-scheme" content="dark">' in head)
    check('head: <title>', re.search(r'<title>[^<]+</title>', head) is not None)
    check('head: meta description', re.search(r'<meta name="description" content="[^"]{50,}"', head) is not None)
    check('head: theme-color', re.search(r'<meta name="theme-color" content="#[0-9a-fA-F]{6}"', head) is not None)
    check('head: SVG favicon', re.search(r'<link rel="icon" type="image/svg\+xml" href="data:image/svg\+xml,', head) is not None)
    check('head: Open Graph tags', all(f'property="og:{k}"' in head for k in ('type', 'site_name', 'locale', 'title', 'description')))
    style_at, fonts_at = head.find('<style>'), head.find('fonts.googleapis.com/css2')
    check('head: page CSS comes before the font stylesheet (dark from the first paint)', -1 < style_at < fonts_at)
    check('head: fonts load without blocking (media="print" onload) with a <noscript> copy',
          re.search(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]+" media="print" onload="this\.media=\'all\'"', head) is not None
          and re.search(r'<noscript><link rel="stylesheet" href="https://fonts\.googleapis\.com/', head) is not None)
    check('head: no-js/js switch (works even when a host strips the <html> tag)', 'class="no-js"' in src
          and "d.classList.remove('no-js'); d.classList.add('js');" in head)
    check('head: sets lang="en-GB" by script when a host strips <html lang> (the artifact bundle does)',
          "if (!d.lang) d.lang = 'en-GB';" in head)


def check_contract(src):
    scripts = ''.join(re.findall(r'<script>(.*?)</script>', src, re.S))
    for bad in ('alert(', 'confirm(', 'prompt(', 'window.open'):
        check(f'artifact: no {bad.rstrip("(")} in the page script', bad not in scripts)
    for needle, name in (('localStorage', 'localStorage'), ('sessionStorage', 'sessionStorage'), ('indexedDB', 'indexedDB'),
                         ('history.replaceState(', 'history.replaceState'), ('history.pushState(', 'history.pushState'),
                         ('clipboard.writeText(', 'clipboard.writeText'), ('new URLSearchParams(location', 'URLSearchParams(location)')):
        n = wrapped_in_try(scripts, needle + ('.' if needle.endswith('Storage') else ''))
        check(f'artifact: every {name} call is inside try/catch', n == 0, f'{n} not wrapped')
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', src)
    check('artifact: external scripts only from cdnjs, jsdelivr or unpkg, pinned', all(
        s.startswith(SCRIPT_HOSTS) and re.search(r'[@/]\d+\.\d+\.\d+', s) for s in srcs), f'{srcs}')
    sheets = re.findall(r'<link rel="stylesheet" href="([^"]+)"', src)
    check('artifact: stylesheets only from Google Fonts', all(s.startswith('https://fonts.googleapis.com/') for s in sheets), f'{sheets}')
    css = block(src, r'<style>(.*?)</style>')
    root = block(css, r'(:root \{.*?\n\})')
    rest = css.replace(root, '')
    literals = re.findall(r'#[0-9a-fA-F]{3,8}\b|rgba?\(', rest)
    check('artifact: every colour is a :root token', root and not literals, f'{literals[:5]}')
    check('artifact: sticky header uses top: env(safe-area-inset-top, 0px)',
          re.search(r'\.site-header \{\s*position: sticky; top: env\(safe-area-inset-top, 0px\)', css) is not None)
    check('artifact: forms send nothing (no action or method)', not re.search(r'<form[^>]*\b(action|method)=', src))
    check('artifact: skip link and <main id="main">', 'class="skip" href="#main"' in src and '<main id="main">' in src)
    check('artifact: the page only redraws itself on a back/forward-cache restore, never on first load',
          "window.addEventListener('pageshow', function (e) { if (e.persisted) start(); });" in scripts
          and "addEventListener('pageshow', start)" not in scripts)


def check_data_and_prices(src, csv_rows, emails):
    m = re.search(r'<script type="application/json" id="shop-data">(.*?)</script>', src, re.S)
    try:
        data = json.loads(m.group(1)) if m else None
    except ValueError as e:
        data = None
        check('data: the bike data (#shop-data) is valid JSON', False, str(e))
    if data is None:
        check('data: the bike data (#shop-data) is there', False)
        return None
    probs = sync_bikes.data_problems(data)
    check('data: every bike has a valid id, ticket, type, size band, year and price', not probs, '; '.join(probs))
    if probs:
        return None
    try:
        fresh = sync_bikes.synced(src)
        check('data: cards, structured data, count and ticket match the data (sync_bikes.py --check)', fresh == src,
              'run sync_bikes.py')
    except SystemExit as e:
        check('data: cards, structured data, count and ticket match the data (sync_bikes.py --check)', False, str(e))
    bikes = {b['id']: b for b in data['bikes']}
    want = {k: b['price'] for k, b in bikes.items()}

    # ---- each bike: card, structured data, CSV, example ticket
    cards = {cid: re.search(r'<span class="price">£([\d,]+)</span>', body)
             for cid, body in re.findall(r'<li class="card" id="bike-([a-z0-9-]+)">(.*?)</li>', src, re.S)}
    cards = {k: int(v.group(1).replace(',', '')) if v else None for k, v in cards.items()}
    check('prices: every card in the HTML shows the data’s price', cards == want, f'cards {cards}' if cards != want else '')
    try:
        ld = json.loads(block(src, r'<script type="application/ld\+json" id="ld-bikes">(.*?)</script>'))
        offers = {it['item']['@id'].replace('#bike-', ''): it['item']['offers'] for it in ld['itemListElement']}
        ld_prices = {k: float(o['price']) for k, o in offers.items()}
        check('prices: the structured data’s offers equal the data', ld_prices == {k: float(v) for k, v in want.items()}, f'{ld_prices}')
        check('honesty: every offer is RefurbishedCondition, in stock, one each, GBP', all(
            o.get('itemCondition') == 'https://schema.org/RefurbishedCondition' and o.get('availability') == 'https://schema.org/InStock'
            and o.get('inventoryLevel', {}).get('value') == 1 and o.get('priceCurrency') == 'GBP' for o in offers.values()))
    except (ValueError, KeyError, TypeError) as e:
        check('prices: the structured data (#ld-bikes) is valid', False, repr(e))
    store = block(src, r'<script type="application/ld\+json" id="ld-store">(.*?)</script>')
    try:
        st = json.loads(store)
        check('honesty: the store is a BikeStore with a 14-day return policy', st.get('@type') == 'BikeStore'
              and st.get('hasMerchantReturnPolicy', {}).get('merchantReturnDays') == 14)
    except ValueError as e:
        check('honesty: the store structured data (#ld-store) is valid JSON', False, str(e))
    check('honesty: no ratings or reviews in the structured data', not re.search(r'aggregateRating|"review', src))
    if csv_rows is not None:
        got = {r['URL handle']: float(r['Price']) for r in csv_rows if r.get('URL handle')}
        check('prices: products-shopify.csv equals the data (rebuild it with build_shopify_csv.py)',
              got == {k: float(v) for k, v in want.items()}, f'csv {got}')
    else:
        check('prices: products-shopify.csv', None, 'not found, so not compared')

    # ---- the example workshop ticket, row by row, against its bike's data
    hero = bikes.get(data.get('heroTicket'))
    region = block(src, r'<!-- ticket: written by sync_bikes\.py[^>]*-->(.*?)<!-- /ticket -->')
    rows = [(text(k).strip(), text(v).strip()) for k, v in re.findall(r'<div><dt>(.*?)</dt><dd>(.*?)</dd></div>', region)]
    if not hero or not region:
        check('ticket: the example ticket describes a bike in the data, row by row', False, 'ticket or its bike not found')
    else:
        r = dict(rows)
        bad = []
        for label, value in (('Bike', hero['make'] + ' ' + hero['model']), ('Year', str(hero['year'])), ('Size', hero['size']),
                             (hero['tagLabel'], hero['tag'])):
            if r.get(label) != value:
                bad.append(f'{label}: ticket {r.get(label)!r}, data {value!r}')
        for label, value in hero.get('specs', []):   # a ticket row with a spec's label must begin with that spec
            if label in r and not r[label].startswith(value):
                bad.append(f'{label}: ticket {r[label]!r}, card {value!r}')
        if f'<b>{hero["no"]}</b>' not in region:
            bad.append('ticket number')
        tm = re.search(r'id="ticket-link">See it, £([\d,]+)', region)
        if not tm or int(tm.group(1).replace(',', '')) != hero['price']:
            bad.append(f'price: ticket {tm and tm.group(1)}, data {hero["price"]}')
        title = block(src, r'<title id="bike-title">(.*?)</title>')
        if hero['make'] + ' ' + hero['model'] not in title:
            bad.append(f'the hero drawing is titled {title!r}')
        check('ticket: the example ticket describes its bike exactly as the data does (and the drawing names it)', not bad, '; '.join(bad))

    # ---- services: the price list and the booking form's options, the tube included
    svc = {v: k for k, v in re.findall(r'<p class="svc-price">£(\d+)(?:<span>[^<]*</span>)?</p><button[^>]*data-service="([a-z]+)"', src)}
    opts = dict(re.findall(r'<option value="([a-z]+)">[^<(]*\(£(\d+)', src))
    check('prices: every workshop price matches its booking-form option', svc and svc == opts, f'list {svc}, form {opts}')
    tubes = [('price list', v) for v in re.findall(r'<span>\+ (' + MONEY + r') if it needs a new tube</span>', src)]
    tubes += [('booking form', v) for v in re.findall(r'Puncture repair \(£\d+, \+ (' + MONEY + r') for a new tube\)', src)]
    same_everywhere('prices: the tube price is the same in the price list and the booking form', tubes)
    check('prices: the tube price is stated in both places', len(tubes) == 2, f'found {len(tubes)}')

    # ---- delivery, the e-bike courier and return collection: page prose, cards, emails and CSV
    page = flat(src)
    sources = [('page', page)] + [(name, t) for name, t in emails.items() if t] + \
              ([('CSV', ' '.join(flat(r.get('Description', '')) for r in csv_rows))] if csv_rows else [])
    bike_del = money(data['delivery']['bike'])
    uk = []
    for where, t in sources:
        uk += [(where, v) for v in re.findall(r'UK delivery is (' + MONEY + r')(?: per bike|,)', t)]
        uk += [(where, v) for v in re.findall(r'deliver to UK addresses for (' + MONEY + r')', t)]
        uk += [(where, v) for v in re.findall(r'\{UK delivery, (' + MONEY + r')\}', t)]
        uk += [(where, v) for v in re.findall(r'(' + MONEY + r') UK delivery', t)]
    uk += [('basket', v) for v in re.findall(r'<span class="mono">(' + MONEY + r') per bike</span>', src)]
    same_everywhere('prices: UK delivery is the same everywhere (page, basket, cards, emails, CSV) and equals the data', uk, bike_del)
    eb = data['delivery'].get('ebike')
    eb_expected = money(eb) if eb else sync_bikes.EBIKE_TBC
    ebike = []
    for where, t in sources:
        ebike += [(where, v) for v in re.findall(r'UK delivery is £[\d,]+ per bike \(e-bikes (' + MONEY + r')\)', t)]
        ebike += [(where, v) for v in re.findall(r'(' + MONEY + r') per e-bike', t)]
        ebike += [(where, v) for v in re.findall(r'e-bike courier,? (' + MONEY + r')', t, re.I)]
        ebike += [(where, v) for v in re.findall(r"don't carry them: (" + MONEY + r')', t)]
    same_everywhere('prices: the e-bike courier price is the same everywhere and equals the data ("ebike")', ebike, eb_expected)
    coll, ecoll = [], []
    for where, t in sources:
        for a, b in re.findall(r'collect it for (' + MONEY + r') \(e-bikes (' + MONEY + r')\)', t):
            coll.append((where, a))
            ecoll.append((where, b))
    same_everywhere('prices: the return collection price is the same everywhere (FAQ, cancelling, emails, CSV)', coll)
    same_everywhere('prices: the e-bike return collection price is the same everywhere', ecoll)
    return data


def check_rules(src, emails):
    for name, phrase in RULES:
        check('rules: ' + name, phrase in src, 'changed or missing')
    page = flat(src)
    every = ' '.join([page] + [t for t in emails.values() if t])
    watts = sorted(set(re.findall(r'(\d+)\s?(?:W\b|watts)', every)))
    check('rules: every motor power on the page and in the emails is 250W', watts == ['250'], f'found {watts}')
    mph = sorted(set(re.findall(r'(\d+(?:\.\d+)?) ?mph', every)))
    check('rules: every speed is 15.5 mph (the cut-out) or 3.7 mph (walking pace)', set(mph) <= {'15.5', '3.7'} and '15.5' in mph, f'found {mph}')
    kmh = sorted(set(re.findall(r'(\d+) ?km/h', every)))
    check('rules: every km/h figure is 25 or 6', set(kmh) <= {'25', '6'}, f'found {kmh}')
    months = re.findall(r'\b(\w+)[- ]month warranty', every, re.I) + re.findall(r'lasts for (\w+) months', every) + \
        re.findall(r'\b(\w+) months on the whole bike', every, re.I)
    check('rules: every warranty length says 3 months', months and all(m.lower() in ('3', 'three') for m in months), f'found {months}')
    cards = re.findall(r'<li class="card" id="bike-[a-z0-9-]+">(.*?)</li>', src, re.S)
    check('rules: every bike card says "3-month warranty"', cards and all('3-month warranty' in c for c in cards))
    days = re.findall(r'within (\d+) days, starting the day after', every) + re.findall(r'you have (\d+) days from the day after', every) + \
        re.findall(r'cancel (?:for any reason )?within (\d+) days', every)
    check('rules: every cancellation period says 14 days', days and all(d == '14' for d in days), f'found {days}')


def check_legal(src):
    for anchor, (name, phrases) in LEGAL.items():
        m = re.search(r'<(details|h3) id="' + re.escape(anchor) + r'">(.*?)</\1>', src, re.S)
        if anchor in ('cancel-form', 'cookies'):   # headings inside a details block: take the text after them
            start = src.find(f'id="{anchor}"')
            body = src[start:src.find('</details>', start)] if start > -1 else ''
        else:
            body = m.group(2) if m else ''
        missing = [p for p in phrases if p not in text(body)]
        check(f'legal: {name} (#{anchor})', body and not missing, f'missing: {missing}' if body else 'section not found')
    in_small_print = block(src, r'<section class="section faq small-print" id="small-print"(.*?)</section>')
    check('legal: the small print is <details> blocks in its own section',
          all(f'<details id="{a}">' in in_small_print for a in ('terms', 'warranty', 'delivery', 'cancel', 'workshop-terms', 'selling-terms', 'privacy')))
    footer = block(src, r'<nav class="wrap footer-links" aria-label="The small print">(.*?)</nav>')
    check('legal: the footer links to every small-print section', all(
        f'href="#{a}"' in footer for a in ('terms', 'warranty', 'delivery', 'cancel', 'workshop-terms', 'selling-terms', 'privacy')))
    check('legal: trader identity in the footer', 'Chainline Cycles is a trading name of' in block(src, r'<footer class="site-footer">(.*?)</footer>'))
    check('legal: warranty strip and FAQ both say "whole bike" (they must say the same thing)',
          'On the whole bike, parts and labour' in src and 'Three months on the whole bike, parts and labour' in src)
    check('legal: the warranty never puts a repair before the legal rights', not re.search(
        r"(?i)we repair it first|if we can't, your legal rights", src))
    check('legal: each form says what its details are used for, with a privacy link',
          src.count('We use these details only to deal with your') == 2 and src.count('(<a href="#privacy">privacy</a>') == 2)
    check('legal: the FAQ refund line keeps "or of you showing us you\'ve sent it"',
          "within 14 days of getting it back, or of you showing us you've sent it, if that's sooner." in src)
    check('honesty: the workshop takes requests, not bookings (no "Book" buttons)', not re.search(r'>Book(?: a service)?<', src)
          and src.count('aria-label="Request ') == 8)
    check('honesty: illustrations-not-photos line', 'The drawings are illustrations, not photos of the actual bike' in src)
    check('honesty: BikeRegister claims stay within what the check shows',
          'not listed as stolen' in src.lower() and not re.search(r"(?i)hasn't been reported stolen|guaranteed? not stolen|never stolen", src))
    check('honesty: battery health is defined against rated capacity', "of the battery's rated capacity" in src)
    check('honesty: e-bike facts (plate shows the maker; NI; off-road modes)', 'a plate showing its maker' in src
          and 'Northern Ireland uses the same limits' in src and 'mode that lets the motor help above 15.5 mph' in src)
    check('honesty: no fake urgency or countdowns', not re.search(r'(?i)only \d+ left|selling fast|hurry|countdown|ends in \d', src))


def phone_digits(p):
    """A UK phone number's digits, with +44 written as 0: '+44 191 496 0000' and '0191 496 0000' are the same."""
    d = re.sub(r'\D', '', p)
    return '0' + d[2:] if d.startswith('44') else d


def contact_matches(kind, href, shown):
    """The link dials or mails exactly what it shows."""
    if '[' in href or '[' in shown:   # placeholders: the same placeholder on both sides
        return href.replace(' ', '') == shown.replace(' ', '') and shown.strip() != ''
    if kind == 'phone':
        return phone_digits(href) == phone_digits(shown) and 10 <= len(phone_digits(shown)) <= 11
    return href.strip().lower() == shown.strip().lower() and '@' in shown


def check_contact(src):
    check('contact: no made-up contact details (example domains, chainline.example, 0191 000, Ofcom drama numbers)',
          not FAKE_CONTACT.search(flat(src)) and not FAKE_CONTACT.search(' '.join(re.findall(r'href="(?:mailto|tel):([^"]*)"', src))),
          ', '.join(FAKE_CONTACT.findall(flat(src)))[:120])
    links = re.findall(r'<a id="contact-(email|phone)" href="(mailto|tel):([^"]*)">([^<]*)</a>', src)
    ok = len(links) == 2 and all(contact_matches(kind, v, t) for kind, _, v, t in links)
    check('contact: email and phone are mailto:/tel: links that show what they mail or dial', ok, f'{links}')
    check('contact: Copy buttons say what they copy', 'data-copy="contact-email"><span class="copy-label">Copy</span><span class="vh"> email address' in src
          and 'data-copy="contact-phone"><span class="copy-label">Copy</span><span class="vh"> phone number' in src)
    check('contact: workshop address and opening hours shown', 'Workshop: ' in src and re.search(r'<p class="muted">Open [^<]+</p>', src) is not None)


def placeholders(src, data):
    """{placeholder: count} in what visitors see and in the data blocks, leaving out the page's own script (its code has
    square brackets of its own), comments, and the customer's blanks in the cancellation form."""
    body = re.sub(r'<script>.*?</script>|<style>.*?</style>|<!--.*?-->', '', src, flags=re.S)
    form = block(src, r'<p class="form-box">(.*?)</p>')
    if form:
        cleaned = form
        for b in CUSTOMER_BLANKS:
            cleaned = cleaned.replace(b, '')
        body = body.replace(form, cleaned)
    found = {}
    for p in PLACEHOLDER.findall(body):
        found[p] = found.get(p, 0) + 1
    # JSON "ebike": null means the e-bike courier price isn't set
    if data and data.get('delivery', {}).get('ebike') is None:
        found['"ebike": null (e-bike courier price, in #shop-data)'] = 1
    return found


def email_placeholders(emails):
    """{placeholder: count} in the parts of the two emails a customer receives: the .md email between its --- rules
    (not the notes for you around it, nor `code`), and the .html after its {% comment %} header. The customer's blanks
    in the cancellation form stay."""
    found = {}
    md = emails.get('order-confirmation-email.md') or ''
    parts = md.split('\n---\n')
    body = parts[1] if len(parts) >= 3 else md
    body = re.sub(r'`[^`]*`', '', body)
    form = '\n'.join(l for l in body.splitlines() if l.startswith('> '))
    htm = emails.get('order-confirmation-email.html') or ''
    htm = htm.split('{% endcomment %}', 1)[-1]
    hform = block(htm, r'<p class="box"[^>]*>(To [^<]*?trading as Chainline Cycles.*?I hereby give notice.*?)</p>')
    for name, t, f in (('md', body, form), ('html', htm, hform)):
        if f:
            cleaned = f
            for b in CUSTOMER_BLANKS:
                cleaned = cleaned.replace(b, '')
            t = t.replace(f, cleaned)
        for p in PLACEHOLDER.findall(html.unescape(t)):
            key = f'{p} ({name})'
            found[key] = found.get(key, 0) + 1
    return found


def check_switches(src, data, emails, launch):
    noindex = '<meta name="robots" content="noindex">' in src
    still = [name for name, s in PREVIEW_STRINGS if s in src]
    found = placeholders(src, data)
    summary = ', '.join(f'{k} ×{v}' if v > 1 else k for k, v in sorted(found.items()))
    in_emails = email_placeholders(emails)
    esummary = ', '.join(f'{k} ×{v}' if v > 1 else k for k, v in sorted(in_emails.items()))
    if launch:
        check('launch: robots noindex removed', not noindex)
        for name, s in PREVIEW_STRINGS:
            check(f'launch: {name} removed', s not in src)
        check('launch: no [placeholders] left on the page', not found, f'{sum(found.values())} left: {summary}')
        check('launch: no [placeholders] left in the order confirmation emails', not in_emails,
              f'{sum(in_emails.values())} left: {esummary}')
        check('launch: canonical link and og:url / og:image added', all(
            re.search(rx, src) for rx in (r'<link rel="canonical" href="https://', r'<meta property="og:url" content="https://',
                                          r'<meta property="og:image" content="https://')))
        check('launch: checkout and forms wired up (no prototype replies left)', not re.search(r"Prototype: (requests|offers)|Payments aren't connected", src))
    else:
        # A page with placeholder stock, prices and contact details must stay a clearly marked preview.
        check('preview: robots noindex is on', noindex, 'remove noindex only at launch (check_site.py --launch)')
        check('preview: every "this is a prototype" note is there', not [n for n, _ in PREVIEW_STRINGS if n not in still],
              f'missing: {[n for n, _ in PREVIEW_STRINGS if n not in still]}')
        check('preview: placeholders still to fill on the page before launch', None if found else True, f'{sum(found.values())}: {summary}')
        check('preview: placeholders still to fill in the order emails before launch', None if in_emails else True,
              f'{sum(in_emails.values())}: {esummary}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--site', help='the sites/chainline folder (found automatically)')
    ap.add_argument('--csv', default=os.path.join(HERE, 'products-shopify.csv'), help='the Shopify CSV to compare prices with')
    ap.add_argument('--emails', default=HERE, help='the folder with order-confirmation-email.md and .html (default: this folder)')
    ap.add_argument('--launch', action='store_true', help='fail while any preview switch or placeholder is left')
    a = ap.parse_args()
    site = a.site or sync_bikes.find_site()
    src = open(os.path.join(site, 'index.html'), encoding='utf-8').read()
    emails = {n: read(os.path.join(a.emails, n)) for n in ('order-confirmation-email.md', 'order-confirmation-email.html')}
    check('emails: both order confirmation emails found', all(emails.values()), f'missing in {a.emails}')
    emails_flat = {n: (flat(t.split('{% endcomment %}', 1)[-1]) if n.endswith('.html') else re.sub(r'\s+', ' ', t)) if t else ''
                   for n, t in emails.items()}
    csv_rows = None
    if a.csv and os.path.isfile(a.csv):
        with open(a.csv, encoding='utf-8', newline='') as f:
            csv_rows = list(csv.DictReader(f))
    check_head(src)
    check_contract(src)
    data = check_data_and_prices(src, csv_rows, emails_flat)
    check_rules(src, emails_flat)
    check_legal(src)
    check_contact(src)
    check_switches(src, data, emails, a.launch)
    width = max(len(n) for n, _, _ in results)
    for name, ok, d in results:
        label = 'NOTE' if ok is None else 'PASS' if ok else 'FAIL'
        print(f"{label}  {name.ljust(width)}  {d if d and ok is not True else ''}".rstrip())
    fails = sum(1 for _, ok, _ in results if ok is False)
    notes = sum(1 for _, ok, _ in results if ok is None)
    mode = 'launch' if a.launch else 'preview'
    print(f'\n{mode}: {len(results) - fails - notes}/{len(results) - notes} checks passed'
          + (f', {notes} {"note" if notes == 1 else "notes"}' if notes else '') + (f'. {fails} FAILED.' if fails else '.'))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
