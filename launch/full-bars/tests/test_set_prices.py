#!/usr/bin/env python3
"""Tests for set_prices.py. Every test works on a fresh temporary copy of sites/full-bars; the real site is
hashed before and after the run to prove it was never written.

Run from the repo root:   python3 launch/full-bars/tests/test_set_prices.py
or:                       python3 -m unittest discover -s launch/full-bars/tests -p 'test_set_prices.py'
Set FULLBARS_SITE to test against another copy of the site. Python 3 standard library only.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, '..', 'set_prices.py')
CHECKER = os.path.join(HERE, '..', 'check_site_prices.py')
SITE = os.environ.get('FULLBARS_SITE') or os.path.normpath(os.path.join(HERE, '..', '..', '..', 'sites', 'full-bars'))


def snapshot(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            if os.path.islink(p):
                out[os.path.relpath(p, root)] = 'link:' + os.readlink(p)
            else:
                with open(p, 'rb') as fh:
                    out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return f.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


class SetPricesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(os.path.join(SITE, 'shop.html')):
            raise unittest.SkipTest(f'site not found at {SITE}')
        cls.live_before = snapshot(SITE)
        cls.tmp = tempfile.mkdtemp(prefix='set_prices_test_')
        cls.orig = os.path.join(cls.tmp, 'orig')
        shutil.copytree(SITE, cls.orig, ignore=shutil.ignore_patterns('*.png'))
        cls.orig_snap = snapshot(cls.orig)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        assert snapshot(SITE) == cls.live_before, 'the real site changed during the tests'

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix='case_', dir=self.tmp)
        self.site = os.path.join(self.work, 'site')
        shutil.copytree(self.orig, self.site)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # -------------------------------------------------------------------------------------------- helpers
    def run_tool(self, *args):
        r = subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True)
        out = r.stdout + r.stderr
        self.assertNotIn('Traceback', out, out)
        return r.returncode, out

    def checker(self):
        r = subprocess.run([sys.executable, CHECKER, '--site', self.site, '--quiet'], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def changed(self):
        now = snapshot(self.site)
        return sorted(k for k in set(now) | set(self.orig_snap) if now.get(k) != self.orig_snap.get(k))

    def page(self, rel):
        return read(os.path.join(self.site, rel))

    def assert_only_number_swaps(self, swaps):
        """Every changed file differs from the original only by numbers in `swaps` (old -> new)."""
        for rel in self.changed():
            old = read(os.path.join(self.orig, rel)).split('\n')
            new = self.page(rel).split('\n')
            self.assertEqual(len(old), len(new), rel)
            for a, b in zip(old, new):
                if a == b:
                    continue
                num = r'(\d{1,3}(?:,\d{3})+(?!\d)|\d+)'
                ta, tb = re.split(num, a), re.split(num, b)
                self.assertEqual(len(ta), len(tb), f'{rel}: structure changed on line\n{a[:200]}\n{b[:200]}')
                for x, y in zip(ta, tb):
                    if x != y:
                        self.assertIn((x, y), swaps, f'{rel}: unexpected change {x!r} -> {y!r}')

    # -------------------------------------------------------------------------------------------- basics
    def test_help(self):
        code, out = self.run_tool('--help')
        self.assertEqual(code, 0)
        for word in ('--check', '--write', '--set', '--dry-run', '--allow-hand-edits', 'Exit codes'):
            self.assertIn(word, out)

    def test_check_passes_on_current_site(self):
        code, out = self.run_tool('--check', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn('RESULT: PASS', out)
        self.assertIn('fails: 0', out)
        self.assertEqual(self.changed(), [])

    def test_write_is_idempotent(self):
        code, out = self.run_tool('--write', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn('No files needed changing', out)
        self.assertEqual(self.changed(), [])

    def test_write_restores_every_scrambled_price(self):
        """Wreck every derived price (not data-prices, not 'Under £300'-style thresholds): --write must restore
        the site byte for byte. This proves the tool reaches every place a price is shown."""
        n = 0
        for d, _, files in os.walk(self.site):
            for f in files:
                if not f.endswith('.html'):
                    continue
                p = os.path.join(d, f)
                s = o = read(p)
                s = re.sub(r'(?<![Uu]nder )(?<!below )(&pound;|£)(\d[\d,]*)', r'\g<1>7', s)
                s = re.sub(r'("(?:lowPrice|highPrice)":)\d+', r'\g<1>7', s)
                s = re.sub(r'data-from="\d+"', 'data-from="7"', s)
                s = re.sub(r'(id="pdFrom">)[^<]*', r'\1Price for x', s)
                s = re.sub(r'(class="result-line"><span>)\d+', r'\g<1>99', s)
                s = re.sub(r'(<a class="tile[^"]*" href="collections/[^"]+"[^>]*><b>[^<]*</b><span>)\d+', r'\g<1>99', s)
                if s != o:
                    write(p, s)
                    n += 1
        self.assertGreater(n, 30)
        self.assertEqual(self.checker()[0], 1)
        code, out = self.run_tool('--write', self.site)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.changed(), [], 'not every derived price was restored')

    def test_dry_run_writes_nothing(self):
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, '--dry-run')
        self.assertEqual(code, 0, out)
        self.assertIn('Would change: 39 place(s) in 15 file(s)', out)
        self.assertEqual(self.changed(), [])

    # -------------------------------------------------------------------------------------------- --set
    def test_set_iphone13_good_199(self):
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.changed(), sorted([
            'collections/iphone-13-series.html', 'collections/under-300.html',
            'guides/check-iphone-imei-stolen.html', 'guides/how-to-check-iphone-battery-health.html',
            'guides/which-used-iphone-to-buy-2026.html', 'index.html', 'shop.html',
            'products/galaxy-s23.html', 'products/iphone-12-pro.html', 'products/iphone-12.html',
            'products/iphone-13-mini.html', 'products/iphone-13-pro.html', 'products/iphone-13.html',
            'products/iphone-14.html', 'products/pixel-8.html']))
        self.assert_only_number_swaps({('209', '199')})
        p = self.page('products/iphone-13.html')
        self.assertIn('<title>Refurbished iPhone 13 from &pound;199 | Full Bars</title>', p)
        self.assertIn('"lowPrice":199,"highPrice":319', p)
        self.assertIn('id="pdFrom">Price for 128GB in Very Good. From &pound;199 in Good.<', p)
        self.assertIn('&quot;Good&quot;:199}', p)
        self.assertIn('value="Good"><span>Good<small>&pound;199</small>', p)
        for rel in ('shop.html', 'index.html', 'collections/under-300.html', 'products/pixel-8.html'):
            card = re.search(r'<article class="card"[^>]*><a href="(?:\.\./)?products/iphone-13\.html">.*?</article>', self.page(rel), re.S).group(0)
            self.assertIn('data-from="199"', card)
            self.assertIn('&pound;199</b>', card)
        self.assertEqual(self.checker()[0], 0)
        # and a second --write changes nothing
        before = snapshot(self.site)
        self.assertEqual(self.run_tool('--write', self.site)[0], 0)
        self.assertEqual(snapshot(self.site), before)

    def test_cheapest_in_collection_changes(self):
        code, out = self.run_tool('--set', 'iphone-13-pro', '128gb', 'good', '179', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn('9 models &middot; from &pound;179', self.page('collections/pro-models.html'))
        self.assertIn('4 models &middot; from &pound;179', self.page('collections/iphone-13-series.html'))
        self.assertIn('<b>iPhone 13</b><span>4 models &middot; from &pound;179</span>', self.page('index.html'))
        # the iPhone 13 page says "The standard 13 is lighter and cheaper" than the 13 Pro: no longer true
        self.assertIn('The standard 13 is lighter and cheaper', out)
        self.assertEqual(self.checker()[0], 0)

    def test_phone_going_over_300_is_flagged(self):
        # by default nothing is written, so the site never shows a £305 phone on "Under £300"
        code, out = self.run_tool('--set', 'iPhone 13 Pro', '128GB', 'Good', '305', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn('iPhone 13 Pro now starts at £305, so it no longer belongs on "Under £300"', out)
        self.assertIn('RESULT: NEEDS YOU (nothing written)', out)
        self.assertIn('--allow-hand-edits', out)
        self.assertEqual(self.changed(), [])
        code, out = self.run_tool('--set', 'iPhone 13 Pro', '128GB', 'Good', '305', self.site, '--allow-hand-edits')
        self.assertEqual(code, 1, out)
        self.assertIn('NEEDS YOU', out)
        under = self.page('collections/under-300.html')
        self.assertIn('../products/iphone-13-pro.html', under)          # not silently removed...
        self.assertIn('&pound;305', under)                              # ...but its price is right
        code, chk = self.checker()
        self.assertEqual(code, 1)
        self.assertEqual(len(re.findall(r'^FAIL', chk, re.M)), 1, chk)
        self.assertIn('FAIL under-300', chk)

    def test_phone_going_under_300_is_flagged(self):
        code, out = self.run_tool('--set', 'iPhone 14', '128GB', 'GD', '299', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn('iPhone 14 now starts at £299, so it belongs on "Under £300" but isn\'t there', out)
        self.assertIn('collections/iphone-14-series.html, which has the same columns', out)
        self.assertEqual(self.changed(), [])

    def test_lowest_price_badge_is_flagged(self):
        code, out = self.run_tool('--set', 'iPhone 13 mini', '128GB', 'Good', '129', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn('"Lowest price" badge is on the iPhone 12 card', out)
        self.assertEqual(self.changed(), [])
        code, out = self.run_tool('--set', 'iPhone 13 mini', '128GB', 'Good', '129', self.site, '--allow-hand-edits')
        self.assertEqual(code, 1, out)
        self.assertIn('for the lowest price we sell', out)
        self.assertIn('7 models &middot; from &pound;129', self.page('collections/under-300.html'))
        # check_site_prices.py alone would pass this wrong page: the badge is only caught here
        self.assertEqual(self.checker()[0], 0)

    def test_quote_js_is_flagged_never_touched(self):
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'vg', '225', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn("set '128GB': 22500 in quote.js by hand", out)
        self.assertEqual(self.changed(), [])
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'vg', '225', self.site, '--allow-hand-edits')
        self.assertEqual(code, 1, out)
        changed = self.changed()
        self.assertNotIn('quote.js', changed)
        self.assertNotIn('pay.js', changed)
        self.assertEqual(changed, ['products/iphone-13.html'])
        p = self.page('products/iphone-13.html')
        self.assertIn('id="pdPrice" class="tnum">&pound;225<', p)
        self.assertIn('Selected: iPhone 13 128GB, Very Good, Blue &mdash; &pound;225', p)

    def test_several_sets_and_thousands(self):
        code, out = self.run_tool('--set', 'iPhone 16 Pro Max', '1TB', 'Excellent', '1099', self.site,
                                  '--set', 'iPhone 16 Pro Max', '1TB', 'Very Good', '£1,010', self.site,
                                  '--set', 'iPhone 16 Pro Max', '1tb', 'gd', '949', self.site)
        self.assertEqual(code, 0, out)
        p = self.page('products/iphone-16-pro-max.html')
        self.assertIn('value="1TB"><span>1TB<small>&pound;1,010</small>', p)
        self.assertIn('"highPrice":1099', p)
        self.assertEqual(self.checker()[0], 0)

    def test_tie_makes_default_the_lowest(self):
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '230', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn('id="pdFrom">Price for 128GB in Very Good: the lowest for this phone.<', self.page('products/iphone-13.html'))

    def test_cap_and_courier_cover_notes(self):
        code, out = self.run_tool('--set', 'iPhone 15 Pro', '128GB', 'Good', '449', self.site,
                                  '--set', 'iPhone 16 Pro', '1TB', 'Good', '749', self.site, '--dry-run')
        self.assertEqual(code, 0, out)
        self.assertIn('within the static site\'s Buy now cap (BUY_NOW_MAX £450', out)
        self.assertIn('within Royal Mail Special Delivery\'s standard £750 cover', out)

    # -------------------------------------------------------------------------------------------- refusals
    def test_refuses_price_order_break(self):
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '240', self.site)
        self.assertEqual(code, 2, out)
        self.assertIn('a better condition costs less than a worse one', out)
        self.assertEqual(self.changed(), [])

    def test_refuses_bad_input(self):
        for args in (('iPhone 99', '128GB', 'Good', '199'), ('iPhone 13', '64GB', 'Good', '199'),
                     ('iPhone 13', '128GB', 'Fair', '199'), ('iPhone 13', '128GB', 'Good', '199.99'),
                     ('iPhone 13', '128GB', 'Good', '0'), ('iPhone 13', '128GB', 'Good', '1990000')):
            code, out = self.run_tool('--set', *args, self.site)
            self.assertEqual(code, 2, (args, out))
            self.assertIn('Nothing was written', out)
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '1990000', self.site)
        self.assertIn('more than £999,999', out)
        self.assertNotIn('no pence', out)
        for flag in ('--dry-run', '--allow-hand-edits'):     # meaningless with --check, which never writes
            code, out = self.run_tool('--check', self.site, flag)
            self.assertEqual(code, 2, out)
            self.assertIn('does nothing with --check', out)
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site,
                                  '--set', 'iPhone 13', '128GB', 'Excellent', '249', self.work)
        self.assertEqual(code, 2, out)
        code, out = self.run_tool('--write', self.work)          # not the site folder
        self.assertEqual(code, 2, out)
        self.assertEqual(self.changed(), [])

    def test_broken_data_prices_stops_everything(self):
        p = os.path.join(self.site, 'products/iphone-13.html')
        write(p, read(p).replace('&quot;Good&quot;:209}', '&quot;Good&quot;:209', 1))
        before = snapshot(self.site)
        for mode in ('--write', '--check'):
            code, out = self.run_tool(mode, self.site)
            self.assertEqual(code, 1, out)
            self.assertIn('data-prices is not valid JSON', out)
        self.assertEqual(snapshot(self.site), before)

    def test_check_finds_hand_edit_and_write_fixes_it(self):
        p = os.path.join(self.site, 'products/iphone-13.html')
        write(p, read(p).replace('&quot;Good&quot;:209}', '&quot;Good&quot;:199}', 1))
        code, out = self.run_tool('--check', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn('Out of date: 38 place(s) in 15 file(s)', out)
        self.assertIn('#pdFrom', out)               # check_site_prices.py doesn't check this one
        self.assertIn('RESULT: FAIL', out)
        self.assertEqual(self.run_tool('--write', self.site)[0], 0)
        self.assertEqual(self.run_tool('--check', self.site)[0], 0)

    def test_never_writes_through_a_symlink(self):
        outside = os.path.join(self.work, 'outside.html')
        target = os.path.join(self.site, 'collections', 'google-pixel.html')
        shutil.move(target, outside)
        os.symlink(outside, target)
        with open(outside, 'rb') as f:
            outside_before = f.read()
        before = snapshot(self.site)
        code, out = self.run_tool('--set', 'Pixel 8', '128GB', 'Good', '219', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn('symlink', out)
        with open(outside, 'rb') as f:
            self.assertEqual(f.read(), outside_before)
        self.assertEqual(snapshot(self.site), before, 'a refused write must leave every file alone')

    def test_disk_error_part_way_is_reported_honestly(self):
        import contextlib
        import importlib.util
        import io
        from unittest import mock
        spec = importlib.util.spec_from_file_location('set_prices_under_test', TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)            # importing must not run anything
        real_replace, calls = os.replace, []

        def flaky(a, b):
            calls.append(b)
            if len(calls) == 2:
                raise OSError(28, 'No space left on device')
            return real_replace(a, b)

        err = io.StringIO()
        with mock.patch.object(mod.os, 'replace', flaky), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            code = mod.main(['--set', 'iPhone 13', '128GB', 'Good', '199', self.site])
        self.assertEqual(code, 1)
        self.assertIn('No space left on device', err.getvalue())
        self.assertIn('Already written: ', err.getvalue())
        self.assertNotIn('Nothing was written', err.getvalue())
        self.assertFalse([f for d, _, fs in os.walk(self.site) for f in fs if f.startswith('.set_prices-')])
        # running --write again finishes the job
        self.assertEqual(self.run_tool('--write', self.site)[0], 0)
        self.assertEqual(self.checker()[0], 0)

    def test_writes_only_inside_the_folder(self):
        sibling = os.path.join(self.work, 'sibling.txt')
        write(sibling, 'leave me')
        listing = sorted(os.listdir(self.work))
        code, out = self.run_tool('--set', 'Galaxy S23', '128GB', 'Good', '239', self.site)
        self.assertEqual(code, 0, out)
        # the rebuild hint names this folder, not the live site
        self.assertIn(f'build_shopify_csv.py --site {self.site} && python3 launch/full-bars/validate_shopify_csv.py --site {self.site}', out)
        self.assertEqual(sorted(os.listdir(self.work)), listing)
        self.assertEqual(read(sibling), 'leave me')
        self.assertFalse([f for d, _, fs in os.walk(self.site) for f in fs if f.startswith('.set_prices-')],
                         'temporary files left behind')


if __name__ == '__main__':
    unittest.main(verbosity=2)
