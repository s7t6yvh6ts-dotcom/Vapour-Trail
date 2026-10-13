#!/usr/bin/env python3
"""Tests for fetch_shopify_variants.py: variant IDs, the price check (--check-prices), saved dumps (--save-dump,
--from-dump) and the stock snapshot (--write-stock). No network: Shopify's answers are faked by replacing its urlopen.

Run from the repo root:  python3 launch/full-bars/tests/test_fetch_variants.py
"""
import contextlib
import datetime
import email.message
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'full-bars')
CSV = os.path.join(PACK, 'products-shopify.csv')

sys.dont_write_bytecode = True
sys.path.insert(0, PACK)
import fetch_shopify_variants as fv  # noqa: E402
import go_live  # noqa: E402

SHOP = 'https://shop.example'


def product_js(handle, combos, start=44000000000000, option_style='objects', value_style='option_n', skip=()):
    """A product as Shopify's /products/<handle>.js gives it (the fields the script reads, plus a few it ignores)."""
    names = ['Storage', 'Condition', 'Colour']
    options = ([{'name': n, 'position': i + 1, 'values': sorted({c[i] for c in combos})} for i, n in enumerate(names)]
               if option_style == 'objects' else names)
    variants = []
    for i, c in enumerate(sorted(combos)):
        if c in skip:
            continue
        v = {'id': start + i, 'title': ' / '.join(c), 'available': False, 'price': 20900, 'sku': f'SKU-{i}'}
        if value_style == 'option_n':
            v.update(option1=c[0], option2=c[1], option3=c[2])
        else:
            v['options'] = list(c)
        variants.append(v)
    return {'id': 1, 'handle': handle, 'title': handle, 'options': options, 'variants': variants}


def csv_prices(path=CSV):
    """{handle: {"storage|condition|colour": price in pence}} from products-shopify.csv (the prices it copied from the site)."""
    import csv as _csv
    out = {}
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for r in _csv.DictReader(fh):
            key = '|'.join(r[f'Option{n} value'] for n in (1, 2, 3))
            out.setdefault(r['URL handle'], {})[key] = int(round(float(r['Price']) * 100))
    return out


def live_product(handle, prices, available=lambda key: True, price=lambda key, p: p, start=45000000000000):
    """A product as Shopify's /products/<handle>.js gives it once it is live: each variant's price in pence (an integer,
    as Shopify's reference shows it) and its "available" flag."""
    variants = []
    for i, key in enumerate(sorted(prices)):
        st, gr, col = key.split('|')
        variants.append({'id': start + i, 'title': f'{st} / {gr} / {col}', 'option1': st, 'option2': gr, 'option3': col,
                         'price': price(key, prices[key]), 'compare_at_price': None, 'available': available(key),
                         'sku': f'SKU-{i}'})
    return {'id': 1, 'handle': handle, 'title': handle, 'available': any(v['available'] for v in variants),
            'options': [{'name': 'Storage', 'position': 1}, {'name': 'Condition', 'position': 2},
                        {'name': 'Colour', 'position': 3}], 'variants': variants}


class FakeResponse:
    def __init__(self, url, body, ctype='application/json'):
        self.url, self.body = url, body
        self.headers = email.message.Message()
        self.headers['Content-Type'] = ctype

    def geturl(self):
        return self.url

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FetchVariantsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='fetch_variants_test_')
        self.out = os.path.join(self.tmp, 'variants.json')
        self.csv = fv.csv_options(CSV)
        self.routes, self.calls = {}, []
        self.real = fv.urlopen
        fv.urlopen = self.fake
        self.cwd = os.getcwd()
        os.chdir(self.tmp)   # a default output file (shopify-variants.json) lands here, never in the pack

    def tearDown(self):
        fv.urlopen = self.real
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake(self, req, timeout=None):
        url = req.full_url
        self.calls.append(url)
        r = self.routes.get(url)
        if r is None or isinstance(r, int):
            hdrs = email.message.Message()
            raise urllib.error.HTTPError(url, r or 404, 'error', hdrs, io.BytesIO(b''))
        if isinstance(r, Exception):
            raise r
        return r

    def serve(self, handle, **kw):
        body = json.dumps(product_js(handle, self.csv[handle], **kw)).encode()
        self.routes[f'{SHOP}/products/{handle}.js'] = FakeResponse(f'{SHOP}/products/{handle}.js', body)

    def run_main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = fv.main(['--shop-url', SHOP, '--out', self.out, '--delay', '0', *args])
        return code, buf.getvalue()

    def test_every_variant_found(self):
        self.serve('iphone-13')
        self.serve('pixel-8', option_style='names', value_style='options')   # the other shapes Shopify may use
        code, out = self.run_main('--handles', 'iphone-13,pixel-8')
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls, [f'{SHOP}/products/iphone-13.js', f'{SHOP}/products/pixel-8.js'])
        with open(self.out, encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertEqual(set(data), {'iphone-13', 'pixel-8'})
        self.assertEqual(len(data['iphone-13']), len(self.csv['iphone-13']))   # 3 storages x 3 grades x 6 colours
        self.assertEqual(len(data['iphone-13']), 54)
        first = sorted(self.csv['iphone-13'])[0]
        self.assertEqual(data['iphone-13']['|'.join(first)], '44000000000000')   # IDs as digits, in a string
        self.assertTrue(all(k.count('|') == 2 for k in data['pixel-8']))
        self.assertIn('Wrote', out)
        self.assertIn('--shop-variants', out)

    def test_every_key_is_an_option_on_the_page(self):
        """What it writes is what go_live.py --shop-variants accepts: each key a storage|condition|colour on the page."""
        for h in self.csv:
            self.serve(h)
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        with open(self.out, encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertEqual(len(data), 19)
        self.assertEqual(sum(len(v) for v in data.values()), 873)
        for h, ids in data.items():
            with open(os.path.join(SITE, 'products', h + '.html'), encoding='utf-8') as fh:
                src = fh.read()
            tag = go_live.PICKER_TAG.search(src).group(0)
            want = {f'{c}|{col}' for c in go_live.picker_combos(tag) for col in go_live.picker_colours(src)}
            self.assertEqual(set(ids), want, h)

    def test_gaps_are_reported_and_the_rest_written(self):
        skip = sorted(self.csv['iphone-13'])[:2]
        self.serve('iphone-13', skip=skip)
        renamed = product_js('pixel-8', self.csv['pixel-8'])
        renamed['variants'][0]['option3'] = 'Hazelnut'   # renamed in Shopify: not in the CSV
        self.routes[f'{SHOP}/products/pixel-8.js'] = FakeResponse(f'{SHOP}/products/pixel-8.js', json.dumps(renamed).encode())
        # iphone-12: not published (404); iphone-14: password page (HTML after a redirect); iphone-15: refused
        self.routes[f'{SHOP}/products/iphone-14.js'] = FakeResponse(f'{SHOP}/password', b'<html>Opening soon</html>', 'text/html')
        self.routes[f'{SHOP}/products/iphone-15.js'] = 403
        self.routes[f'{SHOP}/products/iphone-16.js'] = urllib.error.URLError('no route to host')
        code, out = self.run_main('--handles', 'iphone-13,pixel-8,iphone-12,iphone-14,iphone-15,iphone-16')
        self.assertEqual(code, 1, out)
        self.assertIn('iphone-13: 52 of 54 variant ID(s); none in Shopify for 2: ' + ', '.join('|'.join(k) for k in skip), out)
        self.assertIn('left out 1 Shopify variant(s) that don\'t match the CSV', out)
        self.assertIn('Hazelnut', out)
        self.assertIn('iphone-12: FAILED: not found (404)', out)
        self.assertIn('iphone-14: FAILED: the store sent its password page', out)
        self.assertIn('iphone-15: FAILED: refused (403)', out)
        self.assertIn('iphone-16: FAILED: couldn\'t reach the store (no route to host)', out)
        with open(self.out, encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertEqual(sorted(data), ['iphone-13', 'pixel-8'])
        self.assertEqual(len(data['iphone-13']), 52)
        self.assertNotIn('Hazelnut', json.dumps(data))

    def test_nothing_fetched_writes_nothing(self):
        code, out = self.run_main('--handles', 'iphone-13')
        self.assertEqual(code, 2, out)
        self.assertIn('Nothing could be fetched, so no file was written', out)
        self.assertFalse(os.path.exists(self.out))

    def test_shop_url_is_checked_like_go_live(self):
        for bad in ('http://shop.example', 'https://shop.example/products/iphone-13', 'shop.example'):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = fv.main(['--shop-url', bad, '--out', self.out])
            self.assertEqual(code, 2, bad)
        self.assertEqual(self.calls, [])

    def test_locale_path_is_kept(self):
        """A store address with a path (Shopify Markets, e.g. /en-gb) is used as given: requests should be locale-aware."""
        body = json.dumps(product_js('iphone-13', self.csv['iphone-13'])).encode()
        self.routes[f'{SHOP}/en-gb/products/iphone-13.js'] = FakeResponse(f'{SHOP}/en-gb/products/iphone-13.js', body)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fv.main(['--shop-url', SHOP + '/en-gb/', '--out', self.out, '--delay', '0', '--handles', 'iphone-13'])
        self.assertEqual(code, 0, buf.getvalue())

    # ------------------------------------------------------------------ R9: price check, dumps, stock snapshot
    def serve_live(self, available=lambda h, key: True, price=lambda h, key, p: p):
        """Every product in the CSV, as the live store would answer, with the CSV's (= the site's) prices."""
        self.prices = csv_prices()
        for h, pr in self.prices.items():
            body = json.dumps(live_product(h, pr, lambda k: available(h, k), lambda k, p: price(h, k, p))).encode()
            self.routes[f'{SHOP}/products/{h}.js'] = FakeResponse(f'{SHOP}/products/{h}.js', body)

    def test_check_prices_passes_when_shopify_matches_the_site(self):
        self.serve_live()
        buf = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.tmp)   # the old default --out (shopify-variants.json) would land here
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = fv.main(['--shop-url', SHOP, '--delay', '0', '--check-prices', '--site', SITE])
        finally:
            os.chdir(cwd)
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertIn('Price check: passed. All 873 Shopify variant(s) on 19 product(s) match the site\'s data-prices.', out)
        self.assertNotIn('MISMATCH', out)
        # with --check-prices the variant IDs are written only when asked for
        self.assertEqual(os.listdir(self.tmp), [])

    def test_check_prices_lists_every_mismatch(self):
        """A planted price change in Shopify (one colour of one storage and condition) and a variant whose storage and
        condition the site doesn't sell: each listed with handle, variant, site £ and Shopify £; exit 3."""
        def price(h, key, p):
            if h == 'iphone-13' and key == '128GB|Good|Blue':
                return 21900
            if h == 'pixel-8' and key.startswith('256GB|Excellent|'):
                return str(p + 50)       # a string of digits: pence too
            return p
        self.serve_live(price=price)
        extra = json.loads(self.routes[f'{SHOP}/products/galaxy-s23.js'].body)
        extra['variants'].append({'id': 46000000000001, 'option1': '1TB', 'option2': 'Good', 'option3': 'Black',
                                  'price': 99900, 'available': True})
        extra['variants'].append({'id': 46000000000002, 'option1': '128GB', 'option2': 'Good', 'option3': 'Mint',
                                  'price': 'call us', 'available': True})
        self.routes[f'{SHOP}/products/galaxy-s23.js'] = FakeResponse(f'{SHOP}/products/galaxy-s23.js', json.dumps(extra).encode())
        code, out = self.run_main('--check-prices', '--site', SITE, '--out', self.out)
        self.assertEqual(code, 3, out)
        self.assertIn('  iphone-13  128GB|Good|Blue  site £209  Shopify £219\n', out)
        site_px = self.prices['pixel-8']
        for key in sorted(k for k in site_px if k.startswith('256GB|Excellent|')):
            self.assertIn(f'  pixel-8  {key}  site {fv.gbp(site_px[key])}  Shopify {fv.gbp(site_px[key] + 50)}\n', out)
        self.assertIn('  galaxy-s23  1TB|Good|Black  site no price on the site  Shopify £999\n', out)
        self.assertIn('  galaxy-s23  128GB|Good|Mint  site £', out)
        self.assertIn('Shopify unreadable price "call us"', out)
        n = 1 + len([k for k in site_px if k.startswith('256GB|Excellent|')]) + 2
        self.assertIn(f'PRICE MISMATCHES ({n})', out)
        self.assertIn(f'Price check: FAILED. {n} of 875 Shopify variant(s) don\'t match the site.', out)
        self.assertTrue(os.path.exists(self.out))   # --out still written: the IDs are right even when a price isn't

    def test_price_formats(self):
        """Shopify's reference shows a whole number of pence; a string of digits is pence too, a decimal string is pounds.
        Anything else can't be read, and is reported as a mismatch rather than passed."""
        for given, pence in ((20900, 20900), ('20900', 20900), ('209.00', 20900), ('209.5', 20950), ('209.05', 20905),
                             (20900.0, 20900), (0, 0)):
            self.assertEqual(fv.price_pence(given), pence, given)
        for bad in (True, -1, 'abc', '£209', 209.5, None, [209], '209.001'):
            self.assertIsNone(fv.price_pence(bad), bad)
        self.assertEqual((fv.gbp(20900), fv.gbp(100050), fv.gbp(5)), ('£209', '£1,000.50', '£0.05'))
        prices = {'128GB|Good': 20900}
        product = live_product('x', {'128GB|Good|Blue': 20900, '128GB|Good|Pink': 0}, price=lambda k, p: p)
        product['variants'][1]['price'] = '209.00'
        self.assertEqual(fv.price_mismatches(product, prices), [])
        product['variants'][1]['price'] = 209   # pounds as a bare number would be 209 pence: listed, never passed
        self.assertEqual(fv.price_mismatches(product, prices), [('128GB|Good|Pink', 20900, 209, 209)])

    def test_dump_saved_and_read_back_offline(self):
        self.serve_live()
        dump = os.path.join(self.tmp, 'dump.json')
        code, out = self.run_main('--handles', 'iphone-13,pixel-8', '--save-dump', dump)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.calls), 2)
        with open(dump, encoding='utf-8') as fh:
            saved = json.load(fh)
        self.assertEqual((saved['shop'], sorted(saved['products'])), (SHOP, ['iphone-13', 'pixel-8']))
        # read back with no network at all: any request fails the test
        self.routes.clear()
        calls = len(self.calls)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = fv.main(['--from-dump', dump, '--check-prices', '--site', SITE, '--handles', 'iphone-13,pixel-8',
                            '--out', os.path.join(self.tmp, 'ids.json')])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertEqual(len(self.calls), calls)
        # a fresh copy matches, but a saved copy is never a live check: it never says "passed"
        self.assertIn('Price check: all 78 Shopify variant(s) on 2 product(s) in the saved copy fetched ', buf.getvalue())
        self.assertIn('(less than an hour ago) match the site\'s data-prices. A saved copy is not a live check', buf.getvalue())
        self.assertNotIn('Price check: passed', buf.getvalue())
        self.assertNotIn('NOT LIVE', buf.getvalue())
        with open(os.path.join(self.tmp, 'ids.json'), encoding='utf-8') as fh:
            self.assertEqual(len(json.load(fh)['iphone-13']), 54)
        # a phone that isn't in the dump can't be checked: not a clean check
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = fv.main(['--from-dump', dump, '--check-prices', '--site', SITE])
        self.assertEqual(code, 1, buf.getvalue())
        self.assertIn('iphone-14: FAILED: not in the dump', buf.getvalue())
        self.assertIn('not a clean check', buf.getvalue())
        # a file that isn't a dump, or no source at all: bad arguments
        bad = os.path.join(self.tmp, 'bad.json')
        with open(bad, 'w', encoding='utf-8') as fh:
            fh.write('[1, 2]')
        for args in (['--from-dump', bad], ['--from-dump', os.path.join(self.tmp, 'missing.json')], ['--check-prices']):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                self.assertEqual(fv.main(args), 2, args)
        self.assertEqual(len(self.calls), calls)

    def write_stock(self, *extra, available=lambda h, key: True, site=SITE):
        self.serve_live(available=available)
        stock = os.path.join(self.tmp, 'stock.js')
        if not os.path.exists(stock):
            shutil.copy(os.path.join(site, 'stock.js'), stock)
        code, out = self.run_main('--write-stock', stock, '--site', site, *extra)
        with open(stock, encoding='utf-8') as fh:
            return code, out, fh.read()

    def test_write_stock_snapshot(self):
        """Each phone's available variants per storage|condition (any colour counts 1); {} for a phone with nothing
        available; written in the format go_live.py and site.js read, under stock.js's own header."""
        on = {('iphone-13', '128GB|Good|Blue'), ('iphone-13', '128GB|Good|Midnight'), ('iphone-13', '256GB|Very Good|Pink')}
        avail = lambda h, k: (h, k) in on if h in ('iphone-13', 'iphone-12') else not k.startswith('128GB|Excellent|')  # noqa: E731
        code, out, js = self.write_stock(available=avail)
        self.assertEqual(code, 0, out)
        entries, problems = go_live.read_stock_js({'stock.js': js})
        self.assertEqual(problems, [])
        self.assertEqual(entries['iphone-13'], {'128GB|Good': 2, '256GB|Very Good': 1})
        self.assertEqual(entries['iphone-12'], {})
        self.assertEqual(len(entries), 19)
        self.assertNotIn('128GB|Excellent', entries['pixel-8'])
        self.assertEqual(entries['pixel-8']['128GB|Good'], 4)    # 4 colours available
        self.assertIn('nothing available for 1: iphone-12 (their cards say "None in stock right now")', out)
        # every key is one of that page's storage|condition pairs, every count a whole number: go_live.py accepts it
        for h, counts in entries.items():
            with open(os.path.join(SITE, 'products', h + '.html'), encoding='utf-8') as fh:
                tag = go_live.PICKER_TAG.search(fh.read()).group(0)
            self.assertEqual(go_live.stock_problems(h, counts, go_live.picker_combos(tag)), [], h)
        # stock.js's own header is kept, with one snapshot line that go_live.py reads
        with open(os.path.join(SITE, 'stock.js'), encoding='utf-8') as fh:
            header = fh.read().split('window.FULLBARS_STOCK = {\n};')[0]
        self.assertTrue(js.startswith(header), js[:300])
        snap = go_live.stock_snapshot(js)
        self.assertEqual((snap.shop, snap.phones), (SHOP, 19))
        now = datetime.datetime.now(datetime.timezone.utc)
        self.assertLess(abs((now - snap.when).total_seconds()), 180)   # a live fetch is stamped with the time it ran
        self.assertIsNone(go_live.staleness(snap.when))
        # the same again: still one snapshot line
        code, out, js2 = self.write_stock(available=avail)
        self.assertEqual(js2.count('Shopify stock snapshot:'), 1)
        self.assertEqual(go_live.read_stock_js({'stock.js': js2})[0], entries)

    def test_stock_header_finds_every_spelling_go_live_reads(self):
        """--write-stock keeps a stock.js's own header whichever spelling of the assignment go_live.py reads it in (the
        example inside the header comment, indented, is not the assignment)."""
        with open(os.path.join(SITE, 'stock.js'), encoding='utf-8') as fh:
            src = fh.read()
        head = src[:src.rindex('window.FULLBARS_STOCK =')]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'stock.js')
            for spelling in ('window.FULLBARS_STOCK', 'window["FULLBARS_STOCK"]', "window['FULLBARS_STOCK']",
                             'FULLBARS_STOCK', 'var FULLBARS_STOCK', ';window.FULLBARS_STOCK'):
                with open(p, 'w', encoding='utf-8') as fh:
                    fh.write(head + spelling + ' = {\n  "pixel-8": {}\n};\n')
                self.assertEqual(go_live.read_stock_js({'stock.js': head + spelling + ' = {};'}), ({}, []), spelling)
                self.assertEqual(fv.stock_header(p, SITE), head, spelling)

    def test_write_stock_leaves_out_what_it_cant_read(self):
        """A phone whose variants have no true/false "available", or that can't be fetched, gets no stock data (all its
        options show as orderable; Shopify decides), never a false "none in stock"."""
        self.serve_live()
        p = json.loads(self.routes[f'{SHOP}/products/iphone-14.js'].body)
        del p['variants'][3]['available']
        self.routes[f'{SHOP}/products/iphone-14.js'] = FakeResponse(f'{SHOP}/products/iphone-14.js', json.dumps(p).encode())
        self.routes[f'{SHOP}/products/pixel-8.js'] = 404
        stock = os.path.join(self.tmp, 'stock.js')
        code, out = self.run_main('--write-stock', stock, '--site', SITE)
        self.assertEqual(code, 1, out)
        with open(stock, encoding='utf-8') as fh:
            entries, problems = go_live.read_stock_js({'stock.js': fh.read()})
        self.assertEqual(problems, [])
        self.assertNotIn('iphone-14', entries)
        self.assertNotIn('pixel-8', entries)
        self.assertEqual(len(entries), 17)
        self.assertIn('has no true/false "available" flag', out)
        self.assertIn('pixel-8: FAILED: not found (404)', out)
        # a file that doesn't exist yet gets a short header of its own, still in the format go_live.py reads
        with open(stock, encoding='utf-8') as fh:
            self.assertTrue(fh.read().startswith('/* Full Bars - stock'))

    def test_write_stock_into_a_site_folder(self):
        """--write-stock <site>/stock.js on a copy: --site defaults to that folder, and go_live.py's checks pass."""
        site = os.path.join(self.tmp, 'site')
        shutil.copytree(SITE, site, ignore=shutil.ignore_patterns('*.png'))
        self.serve_live(available=lambda h, k: h != 'galaxy-s23')
        code, out = self.run_main('--write-stock', os.path.join(site, 'stock.js'))
        self.assertEqual(code, 0, out)
        files = go_live.load_site(site)
        entries, problems = go_live.read_stock_js(files)
        self.assertEqual((problems, entries['galaxy-s23']), ([], {}))

    # ------------------------------------------------------------------ R9 fix: saved copies carry their own time
    def saved_copy(self, fetched, available=lambda h, key: True, drop=False, name='dump.json'):
        """A --save-dump file of the fake live store, with its "fetched" time set to fetched (or removed)."""
        self.serve_live(available=available)
        dump = os.path.join(self.tmp, name)
        code, out = self.run_main('--save-dump', dump)
        self.assertEqual(code, 0, out)
        with open(dump, encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertRegex(data['fetched'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')   # --save-dump records when
        if drop:
            del data['fetched']
        else:
            data['fetched'] = fetched
        with open(dump, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
        self.routes.clear()   # from here on, any request would fail the test: no network
        return dump

    def run_dump(self, dump, *args):
        stock = os.path.join(self.tmp, 'stock.js')
        shutil.copy(os.path.join(SITE, 'stock.js'), stock)
        calls = len(self.calls)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = fv.main(['--from-dump', dump, '--check-prices', '--site', SITE, '--write-stock', stock, *args])
        self.assertEqual(len(self.calls), calls)
        with open(stock, encoding='utf-8') as fh:
            return code, buf.getvalue(), fh.read()

    def test_old_dump_keeps_its_own_time(self):
        """A snapshot written from a saved copy is stamped with when Shopify sent the data, not with now, so go_live.py
        sees its real age; the report says how old the copy is, and the price check from it doesn't pass."""
        dump = self.saved_copy('2026-09-01T09:00:00Z')
        code, out, js = self.run_dump(dump)
        self.assertEqual(code, 1, out)
        then = datetime.datetime(2026, 9, 1, 9, 0, tzinfo=datetime.timezone.utc)
        days = (datetime.datetime.now(datetime.timezone.utc) - then).days
        self.assertIn(f'from a saved copy ({dump}) of {SHOP}, fetched 2026-09-01 09:00 UTC ({days} days ago)', out)
        self.assertIn('NOT LIVE: it is more than 24 hours old.', out)
        self.assertIn('/* Shopify stock snapshot: 2026-09-01 09:00 UTC from https://shop.example (19 phones)', js)
        self.assertIn('STALE: the saved copy is stale', out)
        self.assertIn('Price check: NOT PASSED. All 873 Shopify variant(s) in the saved copy match the site\'s data-prices, '
                      f'but the copy was fetched 2026-09-01 09:00 UTC ({days} days ago): not a live check', out)
        self.assertNotIn('Price check: passed', out)
        snap = go_live.stock_snapshot(js)
        self.assertEqual(snap, (then, SHOP, 19))
        warning = go_live.snapshot_age_warning(snap, 'CMD')
        self.assertIn(f'stock.js is a Shopify stock snapshot from 2026-09-01 09:00 UTC ({days} days ago), more than 24 hours '
                      'old', warning)
        # a copy of the copy keeps the original time
        again = os.path.join(self.tmp, 'again.json')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fv.main(['--from-dump', dump, '--save-dump', again, '--handles', 'iphone-13', '--out',
                     os.path.join(self.tmp, 'ids-again.json')])
        with open(again, encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['fetched'], '2026-09-01T09:00:00Z')
        # a planted price difference in an old copy still fails, and the age is still given
        with open(dump, encoding='utf-8') as fh:
            data = json.load(fh)
        data['products']['iphone-13']['variants'][0]['price'] += 1000
        with open(dump, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
        code, out, _ = self.run_dump(dump)
        self.assertEqual(code, 3, out)
        self.assertIn('Price check: FAILED. 1 of 873', out)
        self.assertIn('fetched 2026-09-01 09:00 UTC', out)

    def test_dump_without_a_time_counts_as_stale(self):
        """No "fetched" time in the copy (or one in the future): the snapshot says "time unknown", go_live.py treats it
        as stale, and the price check doesn't pass."""
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
        for label, dump in (('missing', self.saved_copy(None, drop=True, name='missing.json')),
                            ('future', self.saved_copy(future, name='future.json')),
                            ('no zone', self.saved_copy('2026-10-13T09:00:00', name='nozone.json')),
                            ('nonsense', self.saved_copy('yesterday', name='nonsense.json'))):
            code, out, js = self.run_dump(dump)
            self.assertEqual(code, 1, (label, out))
            self.assertIn('/* Shopify stock snapshot: time unknown from https://shop.example (19 phones)', js, label)
            snap = go_live.stock_snapshot(js)
            self.assertEqual(snap, (None, SHOP, 19), label)
            self.assertIn('with no time on it', go_live.snapshot_age_warning(snap, 'CMD'), label)
            self.assertIn('Price check: NOT PASSED.', out, label)
            self.assertNotIn('Price check: passed', out, label)
            self.assertIn('stamped "time unknown"', out, label)
            if label == 'future':
                self.assertIn('NOT LIVE: its fetch time is in the future', out)
            elif label == 'missing':
                self.assertIn('fetched at an unknown time (the file doesn\'t say when)', out)
                self.assertIn('NOT LIVE: it doesn\'t say when it was fetched', out)

    def test_fresh_dump_is_stamped_with_its_time(self):
        """A copy fetched 2 hours ago: the snapshot carries that time (fresh for go_live.py), exit 0, and the price check
        says the prices match without calling it a pass."""
        t = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0) - datetime.timedelta(hours=2)
        code, out, js = self.run_dump(self.saved_copy(t.strftime('%Y-%m-%dT%H:%M:%SZ')))
        self.assertEqual(code, 0, out)
        self.assertEqual(go_live.stock_snapshot(js), (t, SHOP, 19))
        self.assertIsNone(go_live.snapshot_age_warning(go_live.stock_snapshot(js), 'CMD'))
        self.assertIn(f'fetched {t:%Y-%m-%d %H:%M} UTC (2 hours ago)', out)
        self.assertNotIn('NOT LIVE', out)
        self.assertNotIn('STALE', out)
        self.assertIn('match the site\'s data-prices. A saved copy is not a live check, so it never reads "passed"', out)
        self.assertNotIn('Price check: passed', out)
        # and a live fetch says "passed"
        self.serve_live()
        code, out = self.run_main('--check-prices', '--site', SITE)
        self.assertEqual(code, 0, out)
        self.assertIn(f'Shopify data from {SHOP}, fetched live', out)
        self.assertIn('Price check: passed.', out)

    def test_available_variant_that_matches_no_choice_leaves_the_phone_out(self):
        """A variant whose condition was renamed in Shopify ("good") can't be placed on the page. If Shopify can sell it,
        the phone gets no stock data (so no choice Shopify might sell reads "Not in stock — ask us"); if it isn't
        available, it adds nothing anyway and the phone keeps its counts."""
        on = {'256GB|Very Good|Pink', '256GB|Very Good|Blue', '128GB|Good|Blue'}
        for avail, kept in ((True, False), (False, True)):
            self.serve_live(available=lambda h, k: k in on if h == 'iphone-13' else True)
            p = json.loads(self.routes[f'{SHOP}/products/iphone-13.js'].body)
            v = next(v for v in p['variants'] if (v['option1'], v['option2'], v['option3']) == ('128GB', 'Good', 'Blue'))
            v['option2'], v['available'] = 'good', avail
            self.routes[f'{SHOP}/products/iphone-13.js'] = FakeResponse(f'{SHOP}/products/iphone-13.js', json.dumps(p).encode())
            stock = os.path.join(self.tmp, f'stock-{avail}.js')
            code, out = self.run_main('--write-stock', stock, '--site', SITE)
            self.assertEqual(code, 1, out)   # the renamed variant is a gap either way
            with open(stock, encoding='utf-8') as fh:
                entries, problems = go_live.read_stock_js({'stock.js': fh.read()})
            self.assertEqual(problems, [])
            if kept:
                self.assertEqual(entries['iphone-13'], {'256GB|Very Good': 2})
                self.assertIn('iphone-13: 1 Shopify variant(s) left out of the stock: 128GB / good / Blue', out)
            else:
                self.assertNotIn('iphone-13', entries)
                self.assertIn('iphone-13: 1 variant(s) Shopify says are available don\'t match a storage and condition on the '
                              'page: 128GB / good / Blue', out)
            self.assertEqual(len(entries), 19 if kept else 18)
        # straight from the function too
        product = live_product('x', {'128GB|Good|Blue': 20900, '128GB|Good|Pink': 20900})
        product['variants'][0]['option2'] = 'good'
        with self.assertRaises(fv.Problem):
            fv.stock_counts(product, ['128GB|Good'])
        product['variants'][0]['available'] = False
        self.assertEqual(fv.stock_counts(product, ['128GB|Good'])[0], {'128GB|Good': 1})

    def test_help(self):
        r = subprocess.run([sys.executable, '-B', os.path.join(PACK, 'fetch_shopify_variants.py'), '--help'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for flag in ('--shop-url', '--out', '--shopify-csv', '--handles', '--check-prices', '--write-stock', '--from-dump',
                     '--save-dump', '--site'):
            self.assertIn(flag, r.stdout)
        self.assertIn('plain english', fv.__doc__.lower())
        self.assertIn('no variant ID column', fv.__doc__)


if __name__ == '__main__':
    unittest.main(verbosity=2)
