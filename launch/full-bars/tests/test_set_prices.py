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

    # -------------------------------------------------------------------------------------------- pay.js Payment Links
    LINK = 'https://buy.stripe.com/test_fullbars_example'

    def set_pay_link(self, key, url=LINK):
        """Paste a Payment Link into the copy's pay.js, as Ash would on the static route. Returns the copy's snapshot."""
        p = os.path.join(self.site, 'pay.js')
        src = read(p)
        self.assertEqual(src.count(f'"{key}": ""'), 1, key)
        write(p, src.replace(f'"{key}": ""', f'"{key}": "{url}"', 1))
        return snapshot(self.site)

    def test_changed_price_with_a_payment_link_needs_a_hand_edit(self):
        """A Stripe Payment Link charges the price it was made with. --set must never leave the site showing "Buy now —
        £199" while the link still charges £209 without saying so: it's a hand edit, so nothing is written by default."""
        before = self.set_pay_link('iPhone 13 128GB Good')
        pay_before = self.page('pay.js')
        msg = 'pay.js has a Payment Link for iPhone 13 128GB Good; Stripe still charges £209'
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, '--dry-run')
        self.assertEqual(code, 1, out)
        hand = out.split('NEEDS A HAND EDIT (1):')[1].split('\nREVIEW')[0]
        self.assertIn(msg, hand)
        self.assertIn('not £199: a Stripe price can\'t be changed', hand)
        self.assertIn('Deactivate it in Stripe, make a new link at £199 with the same settings (payment limit', hand)
        self.assertIn('paste it into pay.js in place of the old one', hand)
        self.assertIn('RESULT: would need a hand edit', out)
        self.assertEqual(snapshot(self.site), before)
        # a real run refuses and writes nothing, and says what to do first
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site)
        self.assertEqual(code, 1, out)
        self.assertIn(msg, out)
        self.assertIn('RESULT: NEEDS YOU (nothing written)', out)
        self.assertIn('For a Payment Link, the edit to make first is: deactivate it in Stripe and clear its entry in pay.js', out)
        self.assertEqual(snapshot(self.site), before)
        # --allow-hand-edits writes every price, never pay.js, and still exits 1
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, '--allow-hand-edits')
        self.assertEqual(code, 1, out)
        self.assertIn(msg, out)
        self.assertIn('Changed: 39 place(s) in 15 file(s)', out)
        self.assertIn('RESULT: NEEDS YOU (see above)', out)
        self.assertEqual(self.page('pay.js'), pay_before)
        self.assertIn('&quot;Good&quot;:199}', self.page('products/iphone-13.html'))
        self.assertEqual(self.checker()[0], 0)
        # --check then lists the link with the site's price now, and never claims to know what Stripe charges
        code, out = self.run_tool('--check', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn(f'  - iPhone 13 128GB Good: site price £199: {self.LINK}', out)
        self.assertNotIn('Stripe still charges', out)

    def test_clearing_the_link_first_lets_set_run(self):
        """GO-LIVE.md's order: deactivate the link and clear its pay.js entry, then --set runs clean."""
        self.set_pay_link('iPhone 13 128GB Good')
        p = os.path.join(self.site, 'pay.js')
        write(p, read(p).replace(f'"iPhone 13 128GB Good": "{self.LINK}"', '"iPhone 13 128GB Good": ""'))
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site)
        self.assertEqual(code, 0, out)
        self.assertNotIn('Payment Link', out)
        self.assertIn('RESULT: OK', out)

    def test_payment_link_is_only_flagged_when_its_own_price_changes(self):
        self.set_pay_link('iPhone 13 128GB Good')
        after = self.set_pay_link('iPhone 13 256GB Good')
        # the same price again; another storage/condition of the same phone; and a price changed then put back
        for args in ((('iPhone 13', '128GB', 'Good', '209'),),
                     (('iPhone 13', '512GB', 'Good', '265'),),
                     (('iPhone 13', '128GB', 'Good', '199'), ('iPhone 13', '128GB', 'Good', '209'))):
            cmd = [a for s in args for a in ('--set', *s, self.site)] + ['--dry-run']
            code, out = self.run_tool(*cmd)
            self.assertEqual(code, 0, (args, out))
            self.assertNotIn('pay.js has a Payment Link', out, args)
            self.assertIn('RESULT: OK to write', out)
        # with the link on the price that changes, it is listed (and only that one)
        code, out = self.run_tool('--set', 'iPhone 13', '256GB', 'Good', '235', self.site, '--dry-run')
        self.assertEqual(code, 1, out)
        self.assertIn('pay.js has a Payment Link for iPhone 13 256GB Good; Stripe still charges £239', out)
        self.assertNotIn('Payment Link for iPhone 13 128GB Good', out)
        self.assertEqual(len(re.findall(r'pay\.js has a Payment Link for', out)), 1, out)
        self.assertEqual(snapshot(self.site), after, 'a dry run writes nothing')

    def test_payment_link_price_going_over_the_cap(self):
        """Above BUY_NOW_MAX the site never shows the link, so the message says to deactivate and clear it, not replace it."""
        self.set_pay_link('iPhone 14 512GB Excellent')
        code, out = self.run_tool('--set', 'iPhone 14', '512GB', 'Excellent', '455', self.site, '--dry-run')
        self.assertEqual(code, 1, out)
        self.assertIn('pay.js has a Payment Link for iPhone 14 512GB Excellent; Stripe still charges £449', out)
        self.assertIn('At £455 it is above the £450 Buy now cap (BUY_NOW_MAX in site.js), so the site no longer shows Buy '
                      'now for it: deactivate the link in Stripe and clear it in pay.js.', out)
        self.assertNotIn('make a new link at £455', out)

    def test_check_lists_every_payment_link(self):
        code, out = self.run_tool('--check', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn('PAYMENT LINKS IN pay.js: none (every entry is empty).', out)
        self.set_pay_link('iPhone 13 128GB Good', 'https://buy.stripe.com/test_13')
        self.set_pay_link('iPhone 16 Pro Max 1TB Good', 'https://buy.stripe.com/test_16')
        self.set_pay_link('Pixel 8 128GB Good', 'buy.stripe.com/no_scheme')
        code, out = self.run_tool('--check', self.site)
        self.assertEqual(code, 0, out)          # never a failure: Stripe's price can't be seen from here
        self.assertIn('RESULT: PASS', out)
        links = out.split('PAYMENT LINKS IN pay.js (3):')[1].split('check_site_prices.py:')[0]
        self.assertIn('this tool can\'t see what Stripe charges', links)
        self.assertIn('"Limit the number of payments"', links)
        self.assertIn('  - iPhone 13 128GB Good: site price £209: https://buy.stripe.com/test_13\n', links)
        self.assertIn('  - iPhone 16 Pro Max 1TB Good: site price £819, above the £450 Buy now cap, so the site never shows '
                      'this link: deactivate it in Stripe and clear it (https://buy.stripe.com/test_16)', links)
        self.assertIn('  - Pixel 8 128GB Good: site price £229, but "buy.stripe.com/no_scheme" is not an https:// link', links)
        self.assertNotIn('Stripe charges £', links)
        # --write reminds that a hand edit of data-prices can't be matched to a link
        code, out = self.run_tool('--write', self.site)
        self.assertEqual(code, 0, out)
        self.assertIn('pay.js has 3 Payment Link(s), and a Payment Link keeps charging the price it was made with', out)

    def test_several_links_several_models_with_aliases(self):
        """Two --set changes on two phones, typed with aliases, each with a link: one item each, with the old and new
        price. A link whose price doesn't change (Galaxy S23) isn't listed."""
        self.set_pay_link('iPhone 13 128GB Good', 'https://buy.stripe.com/test_13')
        self.set_pay_link('Pixel 8 256GB Very Good', 'https://buy.stripe.com/test_p8')
        before = self.set_pay_link('Galaxy S23 128GB Good', 'https://buy.stripe.com/test_s23')
        args = ['--set', 'iphone 13', '128gb', 'gd', '199', self.site, '--set', 'pixel-8', '256GB', 'vg', '£275', self.site]
        code, out = self.run_tool(*args, '--dry-run')
        self.assertEqual(code, 1, out)
        items = re.findall(r'^  - (pay\.js has a Payment Link for .*)$', out, re.M)
        self.assertEqual(len(items), 2, out)
        self.assertIn('pay.js has a Payment Link for iPhone 13 128GB Good; Stripe still charges £209', items[0] + items[1])
        self.assertIn('pay.js has a Payment Link for Pixel 8 256GB Very Good; Stripe still charges £280', items[0] + items[1])
        self.assertTrue(any('make a new link at £199 with the same settings (payment limit 1' in i for i in items), items)
        self.assertTrue(any('make a new link at £275 with the same settings (payment limit 1' in i for i in items), items)
        self.assertNotIn('Galaxy S23 128GB Good', '\n'.join(items))
        self.assertEqual(snapshot(self.site), before)
        # a real run refuses; with --allow-hand-edits it writes both prices, never pay.js, and still exits 1
        code, out = self.run_tool(*args)
        self.assertEqual(code, 1, out)
        self.assertIn('RESULT: NEEDS YOU (nothing written)', out)
        self.assertEqual(snapshot(self.site), before)
        pay_before = self.page('pay.js')
        code, out = self.run_tool(*args, '--allow-hand-edits')
        self.assertEqual(code, 1, out)
        self.assertEqual(len(re.findall(r'^  - pay\.js has a Payment Link for ', out, re.M)), 2, out)
        self.assertEqual(self.page('pay.js'), pay_before)
        self.assertIn('&quot;Good&quot;:199}', self.page('products/iphone-13.html'))
        self.assertIn('&quot;Very Good&quot;:275,', self.page('products/pixel-8.html'))

    # pay.js layouts JavaScript accepts (site.js would use the link) but set_prices.py doesn't read line by line
    UNREADABLE = {
        'trailing comment': '"iPhone 13 128GB Good": "{L}", // added 13 Oct',
        'trailing block comment': '"iPhone 13 128GB Good": "{L}", /* note */',
        'single-quoted value': '"iPhone 13 128GB Good": \'{L}\',',
        'single-quoted key': '\'iPhone 13 128GB Good\': "{L}",',
        'space before the colon': '"iPhone 13 128GB Good" : "{L}",',
        'two entries on one line': '"iPhone 13 128GB Very Good": "", "iPhone 13 128GB Good": "{L}",',
    }

    def put_pay_line(self, new):
        """Replace the iPhone 13 128GB Good entry of the original pay.js (and, for a line that holds two, the Very Good
        one above it). Returns the copy's snapshot and the line's number."""
        p = os.path.join(self.site, 'pay.js')
        src = read(os.path.join(self.orig, 'pay.js'))
        old = '  "iPhone 13 128GB Good": "",'
        if new.startswith('"iPhone 13 128GB Very Good"'):
            old = '  "iPhone 13 128GB Very Good": "",\n' + old
        self.assertEqual(src.count(old), 1)
        src = src.replace(old, '  ' + new)
        write(p, src)
        return snapshot(self.site), src[:src.index('  ' + new)].count('\n') + 1

    def test_unreadable_pay_js_stops_set_before_anything_is_written(self):
        """A link on a line this tool can't read would slip past the Payment Link check: the site would show "Buy now —
        £199" while Stripe charges £209. So --set, even --dry-run and --allow-hand-edits, refuses (exit 2, nothing
        written) and says which line; --write refuses too, and --check fails with it under NEEDS A HAND EDIT."""
        node = shutil.which('node')
        for name, line in self.UNREADABLE.items():
            with self.subTest(name):
                before, n = self.put_pay_line(line.replace('{L}', self.LINK))
                if node:      # JavaScript (and so site.js) does read the link
                    r = subprocess.run([node, '-e', 'global.window = {}; require(process.argv[1]); '
                                        'console.log(window.FULLBARS_PAY["iPhone 13 128GB Good"])',
                                        os.path.join(self.site, 'pay.js')], capture_output=True, text=True)
                    self.assertEqual(r.stdout.strip(), self.LINK, r.stderr)
                for extra in (['--dry-run'], [], ['--allow-hand-edits']):
                    code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, *extra)
                    self.assertEqual(code, 2, (extra, out))
                    self.assertIn('ERROR: pay.js isn\'t laid out the way this tool reads it, so it can\'t tell whether a '
                                  'Payment Link charges a price this --set changes. Fix pay.js first', out)
                    self.assertIn(f'pay.js line {n} can\'t be read: ', out)
                    self.assertIn('Nothing was written.', out)
                    self.assertNotIn('OK to write', out)
                    self.assertEqual(snapshot(self.site), before)
                code, out = self.run_tool('--write', self.site)
                self.assertEqual(code, 2, out)
                self.assertIn('so it can\'t tell whether a price you changed by hand in data-prices has a Payment Link', out)
                self.assertEqual(snapshot(self.site), before)
                code, out = self.run_tool('--check', self.site)
                self.assertEqual(code, 1, out)
                hand = out.split('NEEDS A HAND EDIT (1):')[1]
                self.assertIn('  - pay.js isn\'t laid out the way this tool reads it', hand)
                self.assertIn(f'pay.js line {n} can\'t be read', hand.split('\n')[1])     # one line, for go_live.py
                self.assertIn('PAYMENT LINKS IN pay.js: can\'t all be listed', out)
                self.assertIn('RESULT: FAIL', out)

    def test_pay_js_problems_outside_the_entries(self):
        """Fail closed on the rest of the file too: a statement after the object, a duplicate key (JavaScript uses the
        last), an escaped key, no window.FULLBARS_PAY line. Comment lines and comment blocks are fine."""
        p = os.path.join(self.site, 'pay.js')
        src = read(p)
        cases = {
            'statement after the object': (src.replace('\n};', '\n};\nwindow.FULLBARS_PAY["iPhone 13 128GB Good"] = '
                                                       f'"{self.LINK}";'),
                                           f'line {src.count(chr(10), 0, src.index(chr(10) + "};")) + 3} can\'t be read: '
                                           'window.FULLBARS_PAY["iPhone 13 128GB Good"]'),
            'duplicate key': (src.replace('  "iPhone 13 128GB Good": "",', '  "iPhone 13 128GB Good": "",\n  '
                                          f'"iPhone 13 128GB Good": "{self.LINK}",'),
                              'the same key more than once (JavaScript uses the last): iPhone 13 128GB Good'),
            'escaped key': (src.replace('  "iPhone 13 128GB Good": "",', f'  "iPhone\\u002013 128GB Good": "{self.LINK}",'),
                            'pay.js has no entry for iPhone 13 128GB Good'),
            'no window.FULLBARS_PAY line': (src.replace('window.FULLBARS_PAY = {', 'window["FULLBARS_PAY"] = {'),
                                            'has no line "window.FULLBARS_PAY = {" on its own'),
        }
        for name, (text, msg) in cases.items():
            with self.subTest(name):
                write(p, text)
                before = snapshot(self.site)
                code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, '--dry-run')
                self.assertEqual(code, 2, out)
                self.assertIn(msg, out)
                self.assertEqual(snapshot(self.site), before)
        # comments inside the object are fine, and the link is still found
        write(p, src.replace('  "iPhone 13 128GB Good": "",', '  // iPhone 13, pasted 13 Oct\n  /* the old link was\n'
                             '  "iPhone 13 128GB Good": "https://buy.stripe.com/old",\n  */\n'
                             f'  "iPhone 13 128GB Good": "{self.LINK}",'))
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, '--dry-run')
        self.assertEqual(code, 1, out)
        self.assertIn('pay.js has a Payment Link for iPhone 13 128GB Good; Stripe still charges £209', out)
        self.assertNotIn('isn\'t laid out', out)
        # no pay.js at all: site.js has no Payment Links either, so nothing to guard
        os.remove(p)
        code, out = self.run_tool('--set', 'iPhone 13', '128GB', 'Good', '199', self.site, '--dry-run')
        self.assertEqual(code, 0, out)
        self.assertNotIn('pay.js', out)

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
