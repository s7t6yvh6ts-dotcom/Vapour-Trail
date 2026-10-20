#!/usr/bin/env python3
"""Tests for sync_bikes.py, check_site.py, build_shopify_csv.py and validate_shopify_csv.py.

Run from launch/chainline:  python3 -m unittest discover -s tests
The real site and the committed CSV are only ever read; every change is made to a copy in a temporary folder.
Python 3 standard library only.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'chainline')
SYNC = os.path.join(PACK, 'sync_bikes.py')
CHECK = os.path.join(PACK, 'check_site.py')
BUILD = os.path.join(PACK, 'build_shopify_csv.py')
VALIDATE = os.path.join(PACK, 'validate_shopify_csv.py')
CSV = os.path.join(PACK, 'products-shopify.csv')


def run(*cmd):
    r = subprocess.run([sys.executable, '-B'] + list(cmd), capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def write(path, s):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def shop_data(src):
    return json.loads(re.search(r'<script type="application/json" id="shop-data">(.*?)</script>', src, re.S).group(1))


class CopyOfSite(unittest.TestCase):
    """Each test gets its own copy of sites/chainline/index.html and of the CSV."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='chainline_test_')
        self.site = os.path.join(self.tmp, 'site')
        os.makedirs(self.site)
        shutil.copy(os.path.join(SITE, 'index.html'), self.site)
        self.page = os.path.join(self.site, 'index.html')
        self.csv = os.path.join(self.tmp, 'products-shopify.csv')
        shutil.copy(CSV, self.csv)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit(self, old, new, count=1):
        s = read(self.page)
        self.assertIn(old, s)
        write(self.page, s.replace(old, new, count))

    def check_site(self, *extra):
        return run(CHECK, '--site', self.site, '--csv', self.csv, *extra)


class SyncBikesTest(CopyOfSite):
    def test_real_site_is_in_sync(self):
        code, out = run(SYNC, '--site', SITE, '--check')
        self.assertEqual(code, 0, out)
        self.assertIn('Up to date: 10 bikes.', out)

    def test_price_change_flows_to_cards_structured_data_and_ticket(self):
        self.edit('"id": "fx2-2021", "no": "0412", "make": "Trek", "model": "FX 2 Disc", "year": 2021, "type": "hybrid", '
                  '"size": "M (17.5in)", "band": "M", "gears": "2x9", "specs": [["Wheels", "700c"], ["Brakes", "Hydraulic disc"], '
                  '["Condition", "[condition notes]"]], "tagLabel": "Fitted", "tag": "New chain + cassette", "price": 379',
                  '"id": "fx2-2021", "no": "0412", "make": "Trek", "model": "FX 2 Disc", "year": 2021, "type": "hybrid", '
                  '"size": "M (17.5in)", "band": "M", "gears": "2x9", "specs": [["Wheels", "700c"], ["Brakes", "Hydraulic disc"], '
                  '["Condition", "[condition notes]"]], "tagLabel": "Fitted", "tag": "New chain + cassette", "price": 1379')
        code, out = run(SYNC, '--site', self.site, '--check')
        self.assertEqual(code, 1, out)
        self.assertIn('OUT OF DATE', out)
        code, out = run(SYNC, '--site', self.site)
        self.assertEqual(code, 0, out)
        s = read(self.page)
        card = re.search(r'<li class="card" id="bike-fx2-2021">(.*?)</li>', s, re.S).group(1)
        self.assertIn('<span class="price">£1,379</span>', card)
        self.assertIn('id="ticket-link">See it, £1,379<span class="vh"> (Trek FX 2 Disc)</span></a>', s)
        ld = json.loads(re.search(r'id="ld-bikes">(.*?)</script>', s, re.S).group(1))
        prices = {i['item']['@id']: i['item']['offers']['price'] for i in ld['itemListElement']}
        self.assertEqual(prices['#bike-fx2-2021'], '1379.00')
        self.assertEqual(run(SYNC, '--site', self.site, '--check')[0], 0)

    def test_selling_a_bike_removes_it_everywhere(self):
        s = read(self.page)
        data = shop_data(s)
        data['bikes'] = [b for b in data['bikes'] if b['id'] != 'allez-2020']
        old = re.search(r'(<script type="application/json" id="shop-data">)(.*?)(</script>)', s, re.S)
        write(self.page, s.replace(old.group(2), '\n' + json.dumps(data, ensure_ascii=False) + '\n'))
        code, out = run(SYNC, '--site', self.site)
        self.assertEqual(code, 0, out)
        s = read(self.page)
        self.assertNotIn('id="bike-allez-2020"', s)
        self.assertNotIn('Specialized Allez', s)
        self.assertIn('9 bikes in stock', s)
        self.assertEqual(json.loads(re.search(r'id="ld-bikes">(.*?)</script>', s, re.S).group(1))['numberOfItems'], 9)

    def test_ticket_pointing_at_a_sold_bike_stops_with_a_message(self):
        s = read(self.page)
        data = shop_data(s)
        data['bikes'] = [b for b in data['bikes'] if b['id'] != 'fx2-2021']
        old = re.search(r'(<script type="application/json" id="shop-data">)(.*?)(</script>)', s, re.S)
        write(self.page, s.replace(old.group(2), json.dumps(data)))
        code, out = run(SYNC, '--site', self.site)
        self.assertNotEqual(code, 0)
        self.assertIn('"heroTicket" must be the id of a bike in the data', out)

    def test_bad_data_is_refused_in_plain_words(self):
        self.edit('"price": 449}', '"price": "449"}')
        code, out = run(SYNC, '--site', self.site, '--check')
        self.assertNotEqual(code, 0)
        self.assertIn('price must be a whole number of pounds', out)


class CheckSiteTest(CopyOfSite):
    def test_real_site_passes_in_preview(self):
        code, out = run(CHECK, '--site', SITE, '--csv', CSV)
        self.assertEqual(code, 0, out)
        self.assertNotIn('FAIL', out)
        self.assertRegex(out, r'NOTE  preview: placeholders still to fill on the page before launch\s+\d+: ')
        self.assertRegex(out, r'NOTE  preview: placeholders still to fill in the order emails before launch\s+\d+: ')
        self.assertIn('PASS  preview: robots noindex is on', out)

    def test_launch_mode_fails_while_preview_switches_and_placeholders_remain(self):
        code, out = run(CHECK, '--site', SITE, '--csv', CSV, '--launch')
        self.assertEqual(code, 1, out)
        for line in ('FAIL  launch: robots noindex removed', 'FAIL  launch: the prototype banner removed',
                     'FAIL  launch: no [placeholders] left', 'FAIL  launch: canonical link and og:url / og:image added'):
            self.assertIn(line, out)
        self.assertIn('"ebike": null', out)
        # the customer's own blanks in the cancellation form are never counted
        for blank in ('[your name]', '[your address]', '[bike, size, ticket number]', '[date]'):
            self.assertNotIn(blank, out)

    def assertFails(self, line, *extra):
        code, out = self.check_site(*extra)
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  ' + line, out)

    def test_catches_an_alert(self):
        self.edit("  'use strict';", "  'use strict';\n  alert('hi');")
        self.assertFails('artifact: no alert in the page script')

    def test_catches_window_open(self):
        self.edit("  'use strict';", "  'use strict';\n  window.open('https://example.com');")
        self.assertFails('artifact: no window.open in the page script')

    def test_catches_unwrapped_storage(self):
        self.edit("  'use strict';", "  'use strict';\n  window.localStorage.setItem('x', '1');")
        self.assertFails('artifact: every localStorage call is inside try/catch')

    def test_catches_fake_contact_details(self):
        self.edit('>[Phone number]</a>', '>0191 000 0003</a>')
        self.assertFails('contact: no made-up contact details (example domains, chainline.example, 0191 000, Ofcom drama numbers)')

    def test_catches_a_card_price_that_differs_from_the_data(self):
        self.edit('<span class="price">£379</span>', '<span class="price">£349</span>')
        self.assertFails('prices: every card in the HTML shows the data’s price')

    def test_catches_structured_data_that_differs(self):
        self.edit('"price":"379.00"', '"price":"379.50"')
        self.assertFails('prices: the structured data’s offers equal the data')

    def test_catches_a_service_price_mismatch(self):
        self.edit('<option value="full">Full service (£120)</option>', '<option value="full">Full service (£125)</option>')
        self.assertFails('prices: every workshop price matches its booking-form option')

    def test_catches_a_delivery_price_mismatch(self):
        self.edit('<span class="mono">£39 per bike</span>', '<span class="mono">£45 per bike</span>')
        self.assertFails('prices: UK delivery is the same everywhere (page, basket, cards, emails, CSV) and equals the data')

    def test_catches_a_csv_out_of_step(self):
        s = read(self.csv).replace(',379.00,', ',389.00,')
        write(self.csv, s)
        self.assertFails('prices: products-shopify.csv equals the data (rebuild it with build_shopify_csv.py)')

    def test_catches_a_missing_legal_section(self):
        s = read(self.page)
        start = s.index('<details id="selling-terms">')
        write(self.page, s[:start] + s[s.index('</details>', start) + len('</details>'):])
        self.assertFails('legal: Selling us your bike (#selling-terms)')

    def test_catches_a_warranty_that_no_longer_says_on_top_of_cra(self):
        self.edit("It's on top of your Consumer Rights Act 2015 rights, not instead of them.</p>\n      <h3>What's covered",
                  "</p>\n      <h3>What's covered")
        self.assertFails('legal: Warranty and your legal rights (#warranty)')

    def test_catches_ratings_in_structured_data(self):
        self.edit('"name":"Chainline Cycles",', '"name":"Chainline Cycles","aggregateRating":{"ratingValue":5},')
        self.assertFails('honesty: no ratings or reviews in the structured data')

    def test_preview_must_keep_noindex_while_placeholders_remain(self):
        self.edit('<meta name="robots" content="noindex">', '')
        self.assertFails('preview: robots noindex is on')

    def test_catches_an_overclaiming_bikeregister_line(self):
        self.edit('so you know it isn\'t listed as stolen there.', "so you know it hasn't been reported stolen.")
        self.assertFails('honesty: BikeRegister claims stay within what the check shows')

    def test_catches_an_external_script_from_elsewhere(self):
        self.edit('</head>', '<script src="https://example.com/x.js"></script>\n</head>')
        self.assertFails('artifact: external scripts only from cdnjs, jsdelivr or unpkg, pinned')

    def test_catches_a_hard_coded_colour(self):
        self.edit('.card-no { font: 400 0.75rem/1.2 var(--font-data); color: var(--muted);',
                  '.card-no { font: 400 0.75rem/1.2 var(--font-data); color: #999999;')
        self.assertFails('artifact: every colour is a :root token')

    def test_catches_a_stale_generated_part(self):
        self.edit('10 bikes in stock', '11 bikes in stock')
        self.assertFails('data: cards, structured data, count and ticket match the data (sync_bikes.py --check)')


# Changes check_site.py must catch: (what, old text, new text, the FAIL line it must give). Prices that appear more than
# once must agree everywhere (a placeholder counts as a value), and the rules that can close the business are pinned.
MUTATIONS = [
    ('FAQ return collection only', 'we can collect it for £39 (e-bikes', 'we can collect it for £49 (e-bikes',
     'prices: the return collection price is the same everywhere'),
    ('Cancelling-section return collection only', "we'll collect it for £39 (e-bikes", "we'll collect it for £49 (e-bikes",
     'prices: the return collection price is the same everywhere'),
    ('e-bike collection price in one place', "(e-bikes £[e-bike collection price]), or use your own courier", "(e-bikes £59), or use your own courier",
     'prices: the e-bike return collection price is the same everywhere'),
    ('e-bike courier priced in one sentence only', 'batteries: £[e-bike delivery price] per e-bike', 'batteries: £69 per e-bike',
     'prices: the e-bike courier price is the same everywhere'),
    ('tube price filled in the price list only', '£12<span>+ £[tube price] if', '£12<span>+ £8 if',
     'prices: the tube price is the same in the price list and the booking form'),
    ('hero ticket Size row', '<dt>Size</dt><dd>M (17.5in)</dd>', '<dt>Size</dt><dd>L (19.5in)</dd>',
     'ticket: the example ticket describes its bike exactly as the data does'),
    ('hero ticket Bike row', '<dt>Bike</dt><dd>Trek FX 2 Disc</dd>', '<dt>Bike</dt><dd>Trek FX 3</dd>',
     'ticket: the example ticket describes its bike exactly as the data does'),
    ('250W -> 500W', '<span class="eapc-val">250W</span>', '<span class="eapc-val">500W</span>', 'rules: e-bike: 250W in the rules'),
    ('15.5 mph -> 20 mph', '<span class="eapc-val">15.5 mph</span>', '<span class="eapc-val">20 mph</span>', 'rules: e-bike: 15.5 mph cut-out in the rules'),
    ('no-derestriction line deleted', 'Derestriction kits, also sold as delimiters, that lift the 15.5 mph cut-out.', 'Upgrades available.',
     'rules: e-bike: no derestriction kits'),
    ('walking-pace throttle rule deleted', ' Every e-bike we sell has no throttle, or one that stops at that speed.', '',
     'rules: e-bike: we sell no throttle above walking pace'),
    ('strip says 6-month warranty', '<h3>3-month warranty</h3>', '<h3>6-month warranty</h3>', 'rules: warranty: 3 months on the promise strip'),
    ('a card says 6-month warranty', '· 3-month warranty</p>', '· 6-month warranty</p>', 'rules: every warranty length says 3 months'),
    ('small print says 12 months', 'lasts for 3 months from the day', 'lasts for 12 months from the day', 'rules: warranty: 3 months in the small print'),
    ('meta description says 6-month', 'A 3-month warranty on top', 'A 6-month warranty on top', 'rules: warranty: 3 months in the meta description'),
    ('FAQ cancellation 7 days', 'you have 14 days from the day after', 'you have 7 days from the day after', 'rules: cancellation: 14 days in the FAQ'),
    ('small-print cancellation 7 days', 'you can cancel for any reason within 14 days, starting the day after you get the bike, whether',
     'you can cancel for any reason within 7 days, starting the day after you get the bike, whether', 'rules: cancellation: 14 days in the small print'),
    ('repair-first warranty wording back', 'We put a covered fault right free of charge.', "We repair it first. If we can't, your legal rights below apply.",
     'legal: the warranty never puts a repair before the legal rights'),
    ('FAQ refund line shortened', "within 14 days of getting it back, or of you showing us you've sent it, if that's sooner.", 'within 14 days of getting it back.',
     'legal: the FAQ refund line keeps "or of you showing us you\'ve sent it"'),
    ('a Book button', 'aria-label="Request a safety check">Request</button>', 'aria-label="Book a safety check">Book</button>',
     'honesty: the workshop takes requests, not bookings (no "Book" buttons)'),
    ('redraw on every pageshow', "window.addEventListener('pageshow', function (e) { if (e.persisted) start(); });", "window.addEventListener('pageshow', start);",
     'artifact: the page only redraws itself on a back/forward-cache restore, never on first load'),
    ('lang fallback removed', " if (!d.lang) d.lang = 'en-GB';", '', 'head: sets lang="en-GB" by script when a host strips <html lang> (the artifact bundle does)'),
    ('unwrapped sessionStorage', "  'use strict';", "  'use strict';\n  sessionStorage.setItem('a', 'b');", 'artifact: every sessionStorage call is inside try/catch'),
    ('an Ofcom drama number', 'href="tel:[Phone number]">[Phone number]</a>', 'href="tel:+447700900123">07700 900123</a>',
     'contact: no made-up contact details (example domains, chainline.example, 0191 000, Ofcom drama numbers)'),
]


class MutationTest(CopyOfSite):
    def test_every_mutation_fails_with_the_right_line(self):
        original = read(self.page)
        for what, old, new, line in MUTATIONS:
            with self.subTest(what):
                self.assertIn(old, original)
                write(self.page, original.replace(old, new, 1))
                code, out = self.check_site()
                self.assertEqual(code, 1, f'{what}: not caught\n{out}')
                self.assertIn('FAIL  ' + line, out, what)
        write(self.page, original)

    def test_an_email_price_out_of_step_with_the_site(self):
        emails = os.path.join(self.tmp, 'emails')
        os.makedirs(emails)
        for n in ('order-confirmation-email.md', 'order-confirmation-email.html'):
            shutil.copy(os.path.join(PACK, n), emails)
        md = os.path.join(emails, 'order-confirmation-email.md')
        write(md, read(md).replace("we'll collect it for £39 (e-bikes", "we'll collect it for £49 (e-bikes"))
        code, out = run(CHECK, '--site', self.site, '--csv', self.csv, '--emails', emails)
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  prices: the return collection price is the same everywhere', out)

    def test_setting_the_ebike_price_everywhere_passes(self):
        """The legitimate path: set "ebike" in the data, sync, fill the prose and the email, rebuild the CSV."""
        s = read(self.page).replace('{"delivery": {"bike": 39, "ebike": null}', '{"delivery": {"bike": 39, "ebike": 69}', 1)
        for a, b in (('UK delivery is £39 per bike (e-bikes £[e-bike delivery price])', 'UK delivery is £39 per bike (e-bikes £69)'),
                     ('batteries: £[e-bike delivery price] per e-bike', 'batteries: £69 per e-bike'),
                     ('e-bikes: £[e-bike delivery price] per e-bike', 'e-bikes: £69 per e-bike')):
            self.assertIn(a, s)
            s = s.replace(a, b, 1)
        write(self.page, s)
        self.assertEqual(run(SYNC, '--site', self.site)[0], 0)
        emails = os.path.join(self.tmp, 'emails')
        os.makedirs(emails)
        for n in ('order-confirmation-email.md', 'order-confirmation-email.html'):
            shutil.copy(os.path.join(PACK, n), emails)
        md = os.path.join(emails, 'order-confirmation-email.md')
        write(md, read(md).replace('{E-bike courier, £[e-bike delivery price]}', '{E-bike courier, £69}'))
        code, out = run(BUILD, '--site', self.site, '--out', self.tmp)
        self.assertEqual(code, 0, out)
        code, out = run(CHECK, '--site', self.site, '--csv', self.csv, '--emails', emails)
        self.assertEqual(code, 0, out)
        self.assertIn('PASS  prices: the e-bike courier price is the same everywhere and equals the data ("ebike")', out)
        self.assertIn('£69', read(self.page)[read(self.page).index('id="bike-motus-2021"'):][:3000])

    def test_launch_fails_on_placeholders_left_in_the_emails_only(self):
        emails = os.path.join(self.tmp, 'emails')
        os.makedirs(emails)
        blanks = ('[bike, size, ticket number]', '[date]', '[your name]', '[your address]')
        for n in ('order-confirmation-email.md', 'order-confirmation-email.html'):
            shutil.copy(os.path.join(PACK, n), emails)
        code, out = run(CHECK, '--site', self.site, '--csv', self.csv, '--emails', emails, '--launch')
        self.assertIn('FAIL  launch: no [placeholders] left in the order confirmation emails', out)
        for b in blanks:   # the customer's blanks never count
            self.assertNotRegex(out, re.escape(b) + r' \((md|html)\)')
        for n in ('order-confirmation-email.md', 'order-confirmation-email.html'):
            p = os.path.join(emails, n)
            t = read(p)
            keep = {b: f'@@{i}@@' for i, b in enumerate(blanks)}
            for b, k in keep.items():
                t = t.replace(b, k)
            t = re.sub(r'\[[^\[\]<>"=]+\]', 'filled', t)
            for b, k in keep.items():
                t = t.replace(k, b)
            write(p, t)
        code, out = run(CHECK, '--site', self.site, '--csv', self.csv, '--emails', emails, '--launch')
        self.assertIn('PASS  launch: no [placeholders] left in the order confirmation emails', out)


class PhoneLinkTest(unittest.TestCase):
    """GO-LIVE section 3 says to write tel:+44…; the check must accept that for the number shown."""

    def test_plus_44_and_a_leading_0_are_the_same_number(self):
        sys.path.insert(0, PACK)
        import check_site
        self.assertEqual(check_site.phone_digits('+44 191 496 0000'), check_site.phone_digits('0191 496 0000'))
        self.assertTrue(check_site.contact_matches('phone', '+441914960000', '0191 496 0000'))
        self.assertTrue(check_site.contact_matches('phone', '01914960000', '0191 496 0000'))
        self.assertFalse(check_site.contact_matches('phone', '+441914960001', '0191 496 0000'))
        self.assertTrue(check_site.contact_matches('phone', '[Phone number]', '[Phone number]'))
        self.assertFalse(check_site.contact_matches('phone', '[Phone number]', '0191 496 0000'))
        self.assertTrue(check_site.contact_matches('email', 'Workshop@Chainline.co.uk', 'workshop@chainline.co.uk'))


class PhoneLinkOnPageTest(CopyOfSite):
    def test_a_correct_international_tel_link_passes(self):
        self.edit('href="tel:[Phone number]">[Phone number]</a>', 'href="tel:+441914960000">0191 496 0000</a>')
        code, out = self.check_site()
        self.assertIn('PASS  contact: email and phone are mailto:/tel: links that show what they mail or dial', out)

    def test_a_tel_link_that_dials_another_number_fails(self):
        self.edit('href="tel:[Phone number]">[Phone number]</a>', 'href="tel:+441914960001">0191 496 0000</a>')
        code, out = self.check_site()
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  contact: email and phone are mailto:/tel: links that show what they mail or dial', out)


class ShopifyCsvTest(CopyOfSite):
    def build(self):
        code, out = run(BUILD, '--site', self.site, '--out', self.tmp)
        self.assertEqual(code, 0, out)
        with open(self.csv, encoding='utf-8', newline='') as f:
            return list(csv.reader(f))

    def validate(self, *extra):
        return run(VALIDATE, self.csv, '--site', self.site, *extra)

    def rewrite(self, rows):
        with open(self.csv, 'w', encoding='utf-8', newline='') as f:
            csv.writer(f, lineterminator='\n').writerows(rows)

    def test_committed_csv_is_a_fresh_build(self):
        fresh = self.build()
        with open(CSV, encoding='utf-8', newline='') as f:
            self.assertEqual(list(csv.reader(f)), fresh, 'products-shopify.csv is stale: run build_shopify_csv.py')

    def test_build_is_ten_single_variant_drafts_at_the_sites_prices(self):
        rows = self.build()
        head, body = rows[0], rows[1:]
        full_bars = os.path.join(REPO, 'launch', 'full-bars', 'products-shopify.csv')
        with open(full_bars, encoding='utf-8', newline='') as f:
            self.assertEqual(head, next(csv.reader(f)), 'must use the same Shopify header as launch/full-bars')
        self.assertEqual(len(body), 10)
        col = {h: i for i, h in enumerate(head)}
        data = {b['id']: b for b in shop_data(read(self.page))['bikes']}
        for r in body:
            b = data[r[col['URL handle']]]
            self.assertEqual(r[col['Price']], f"{b['price']}.00")
            self.assertEqual((r[col['Status']], r[col['Published on online store']]), ('draft', 'FALSE'))
            self.assertEqual((r[col['Inventory quantity']], r[col['Continue selling when out of stock']]), ('1', 'deny'))
            self.assertEqual(r[col['Requires shipping']], 'TRUE')
            self.assertEqual((r[col['Option1 name']], r[col['Option1 value']]), ('Title', 'Default Title'))
            self.assertEqual(r[col['SKU']], 'CL-' + b['no'])
            self.assertEqual((r[col['Weight value (grams)']], r[col['Weight unit for display']]), ('1000', 'kg'))
            d = r[col['Description']]
            self.assertIn(f"<h2>Workshop ticket {b['no']}</h2>", d)
            self.assertIn('<strong>Condition:</strong>', d)
            self.assertIn("on top of your Consumer Rights Act 2015 rights, not instead of them", d)
            self.assertIn('Frame number checked on BikeRegister: not listed as stolen there when we checked', d)
            self.assertEqual('rated capacity' in d, b['type'] == 'ebike')
        code, out = self.validate()
        self.assertEqual(code, 0, out)
        self.assertIn('NOTE  placeholders still to fill on the site', out)

    def test_validator_catches_a_wrong_price(self):
        rows = self.build()
        rows[3][rows[0].index('Price')] = '1.00'
        self.rewrite(rows)
        code, out = self.validate()
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  prices: every row equals the site’s data, its card and its structured data', out)

    def test_validator_catches_overselling_and_live_products(self):
        rows = self.build()
        head = rows[0]
        rows[1][head.index('Inventory quantity')] = '2'
        rows[2][head.index('Continue selling when out of stock')] = 'continue'
        rows[3][head.index('Status')] = 'active'
        self.rewrite(rows)
        code, out = self.validate()
        self.assertEqual(code, 1, out)
        for line in ("FAIL  values: Inventory quantity = '1' on every row", "FAIL  values: Continue selling when out of stock = 'deny'",
                     "FAIL  values: Status = 'draft' on every row"):
            self.assertIn(line, out)

    def test_validator_catches_a_wrong_header(self):
        rows = self.build()
        rows[0][rows[0].index('Price')] = 'Variant Price'
        self.rewrite(rows)
        code, out = self.validate()
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  header: the same columns, in the same order, as launch/full-bars/products-shopify.csv', out)

    def test_validator_catches_a_missing_bike_and_a_missing_rights_line(self):
        rows = self.build()
        head = rows[0]
        rows[1][head.index('Description')] = rows[1][head.index('Description')].replace('on top of your Consumer Rights Act 2015 rights', '')
        del rows[2]
        self.rewrite(rows)
        code, out = self.validate()
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  products: count matches the bikes in the site data', out)
        self.assertIn('FAIL  description: says the warranty is on top of Consumer Rights Act 2015 rights', out)

    def test_validator_launch_mode_fails_on_placeholders(self):
        self.build()
        code, out = self.validate('--launch')
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  launch: no [placeholders] left in any column', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
