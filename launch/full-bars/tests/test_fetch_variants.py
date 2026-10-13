#!/usr/bin/env python3
"""Tests for fetch_shopify_variants.py. No network: Shopify's answers are faked by replacing its urlopen.

Run from the repo root:  python3 launch/full-bars/tests/test_fetch_variants.py
"""
import contextlib
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

    def tearDown(self):
        fv.urlopen = self.real
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

    def test_help(self):
        r = subprocess.run([sys.executable, '-B', os.path.join(PACK, 'fetch_shopify_variants.py'), '--help'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for flag in ('--shop-url', '--out', '--shopify-csv', '--handles'):
            self.assertIn(flag, r.stdout)
        self.assertIn('plain english', fv.__doc__.lower())
        self.assertIn('no variant ID column', fv.__doc__)


if __name__ == '__main__':
    unittest.main(verbosity=2)
