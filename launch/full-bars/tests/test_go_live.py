#!/usr/bin/env python3
"""Tests for go_live.py, the Full Bars launch-day switch.

Run from the repo root:  python3 launch/full-bars/tests/test_go_live.py
Each test works on a fresh copy of sites/full-bars in a temporary folder (set TMPDIR to choose where).
The real site folder is only ever read. Python 3 standard library only.
"""
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
TOOL = os.path.join(PACK, 'go_live.py')
CHECKER = os.path.join(PACK, 'check_site_prices.py')
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'full-bars')
GOLIVE = os.path.join(PACK, 'GO-LIVE.md')

sys.dont_write_bytecode = True
sys.path.insert(0, PACK)
import go_live  # noqa: E402

# Fake values for every GO-LIVE.md section 3 placeholder (what Ash would type in)
FAKE = {
    '[Company name]': 'Example Phones Ltd',
    '[registered in England and Wales]': 'registered in England and Wales',
    '[Company number]': '01234567',
    '[Registered business address]': '1 Example Street, Exampletown EX1 1AA',
    '[VAT number, if registered]': 'GB123456789',
    '[Phone number]': '01234 567890',
    '[Opening hours]': 'Monday to Friday, 9am to 5pm',
    '[Town, County]': 'Exampletown, Exampleshire',
    '[ICO registration number]': 'ZA123456',
    '[the law of England and Wales]': 'the law of England and Wales',
    '[the courts of England and Wales]': 'the courts of England and Wales',
    '[30]': '30',
}
# What Ash would add to each sell page before opening trade-ins (quote-ui.js reads these ids)
SEND_FORM = ('<form class="form" id="qtSend" hidden novalidate><label for="qtName">Your name<input type="text" id="qtName" '
             'autocomplete="name"></label><label for="qtNotes">Anything else?<textarea id="qtNotes"></textarea></label>'
             '<label><input type="checkbox" id="qtOwner"> The phone is mine to sell</label><div class="form-actions">'
             '<button type="submit" class="btn btn-solid">Email my quote</button><button type="button" class="btn btn-line" '
             'id="qtCopy">Copy quote</button></div><p class="status" id="qtStatus" role="status"></p></form>')
LINK_KEY, LINK = 'iPhone 13 128GB Good', 'https://buy.stripe.com/test_fullbars_example'
SHOP = 'https://shop.example'   # an obviously fake Shopify store address
CSV = os.path.join(PACK, 'products-shopify.csv')


def snapshot(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def read(site, rel):
    with open(os.path.join(site, rel), encoding='utf-8') as fh:
        return fh.read()


def write(site, rel, text):
    with open(os.path.join(site, rel), 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def edit(site, rel, old, new, count=1):
    src = read(site, rel)
    assert src.count(old) >= 1, f'{old!r} not in {rel}'
    write(site, rel, src.replace(old, new, count))


def html_files(site):
    return sorted(os.path.relpath(os.path.join(d, f), site).replace(os.sep, '/')
                  for d, _, fs in os.walk(site) for f in fs if f.endswith('.html'))


def fill_placeholders(site):
    for rel in html_files(site):
        src = read(site, rel)
        new = src
        for k, v in FAKE.items():
            new = new.replace(k, v)
        if new != src:
            write(site, rel, new)


def set_link(site, key, url):
    edit(site, 'pay.js', f'"{key}": ""', f'"{key}": "{url}"')


def add_send_forms(site):
    for rel in html_files(site):
        src = read(site, rel)
        if 'id="qtWorking"' in src and 'id="qtSend"' not in src:
            i = src.index('<div class="callout warn" id="qtPreview"')
            write(site, rel, src[:i] + SEND_FORM + src[i:])


def product_pages(site):
    return [r for r in html_files(site) if r.startswith('products/')]


def picker_tag(src):
    return re.search(r'<form class="picker" id="picker"[^>]*>', src).group(0)


def set_stock(site, rel, raw):
    """Put data-stock (raw JSON text, as Ash would type it) on one product page's #picker, replacing any there."""
    src = read(site, rel)
    tag = picker_tag(src)
    new = re.sub(r' data-stock="[^"]*"', '', tag)
    if raw is not None:
        new = new[:-1] + ' data-stock="' + html.escape(raw, quote=True) + '">'
    write(site, rel, src.replace(tag, new, 1))


def add_stock(site):
    """data-stock on every product page, as Ash adds it on the static route: nothing held, except one iPhone 13
    128GB Good (the phone with the test Payment Link)."""
    for rel in product_pages(site):
        set_stock(site, rel, '{"128GB|Good": 1}' if rel == 'products/iphone-13.html' else '{}')


def ld_blocks(src):
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)]


class GoLiveTest(unittest.TestCase):
    TEMPLATE_KEYS = {}   # (checkout, trade-ins) -> the --rewrites-template keys for the ready site (the same for every test)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='go_live_test_')
        self.site = os.path.join(self.tmp, 'site')
        self.rw = None
        # PNGs aren't text, so the switch never reads them: leave them out to keep copies fast
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns('*.png'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, *args, date='2026-10-20', rewrites=True):
        """Run go_live.py on the copy. Once ready() has run, every run gets the filled-in --rewrites file too
        (as Ash would pass it), unless rewrites=False or the test passes its own."""
        cmd = [sys.executable, '-B', TOOL, '--site', self.site] + (['--launch-date', date] if date else []) + list(args)
        if rewrites and self.rw and '--rewrites' not in args:
            cmd += ['--rewrites', self.rw]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr

    def template(self, trade_ins='closed', checkout='stripe'):
        """The keys --rewrites-template writes for this copy, made once per checkout and trade-ins mode."""
        if (checkout, trade_ins) not in GoLiveTest.TEMPLATE_KEYS:
            tpl = os.path.join(self.tmp, f'template-{checkout}-{trade_ins}.json')
            shop = ['--shop-url', SHOP] if checkout == 'shopify' else []
            code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', checkout, *shop, '--trade-ins', trade_ins,
                                      '--dry-run', '--rewrites-template', tpl, rewrites=False)
            self.assertIn(code, (0, 1), out[-2000:])
            with open(tpl, encoding='utf-8') as fh:
                GoLiveTest.TEMPLATE_KEYS[(checkout, trade_ins)] = list(json.load(fh))
            os.remove(tpl)
        return GoLiveTest.TEMPLATE_KEYS[(checkout, trade_ins)]

    def write_rewrites(self, mapping, name='rewrites.json'):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(mapping, fh, ensure_ascii=False)
        return path

    def fill_rewrites(self, trade_ins='closed', value=lambda i, key: f'Rewritten line {i}.', checkout='stripe'):
        """A --rewrites file with every template key filled in: Ash's finished wording."""
        name = f'rewrites-{trade_ins}.json' if checkout == 'stripe' else f'rewrites-{checkout}-{trade_ins}.json'
        self.rw = self.write_rewrites({k: value(i, k) for i, k in enumerate(self.template(trade_ins, checkout))}, name)
        return self.rw

    def ready(self, link=True, rewrites=True, checkout='stripe'):
        """The copy as Ash would have it on launch day: placeholders filled, and for the static (Stripe) route a
        Payment Link and data-stock on every product page; then the finished --rewrites file for that route."""
        fill_placeholders(self.site)
        if checkout == 'stripe':
            if link:
                set_link(self.site, LINK_KEY, LINK)
            add_stock(self.site)
        if rewrites:
            self.fill_rewrites(checkout=checkout)

    # ------------------------------------------------------------------ blockers
    def test_help(self):
        r = subprocess.run([sys.executable, '-B', TOOL, '--help'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for flag in ('--dry-run', '--check-only', '--allow-preview-wording', '--checkout', '--out', '--domain', '--site',
                     '--rewrites', '--rewrites-template', '--launch-date'):
            self.assertIn(flag, r.stdout)
        self.assertNotIn('--force-preview-check-only', r.stdout)   # old name: still works, no longer advertised
        self.assertIn('Plain English'.lower(), go_live.__doc__.lower())

    def test_dry_run_writes_nothing_and_lists_blockers(self):
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run')
        self.assertEqual(code, 1, out)
        self.assertEqual(snapshot(self.site), before)
        self.assertIn('placeholder [Company name] still on 56 pages', out)
        self.assertIn('every Payment Link in pay.js is empty', out)
        self.assertIn('preview wording would still be on the live pages', out)
        self.assertRegex(out, r'RESULT: dry run\. \d+ change\(s\) would be made\. \d+ blocker\(s\)')
        # file, line, before and after for each change
        self.assertRegex(out, r'products/iphone-13\.html:\d+  Order button')
        self.assertIn('[-<meta name="robots" content="noindex">-]', out)
        self.assertIn('{+<meta name="robots" content="index,follow">+}', out)

    def test_real_run_refuses_and_writes_nothing(self):
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify')
        self.assertEqual(code, 1, out)
        self.assertIn('RESULT: REFUSED', out)
        self.assertEqual(snapshot(self.site), before)

    def test_checkout_must_be_chosen(self):
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--force-preview-check-only')   # the old option name
        self.assertEqual(code, 1, out)
        self.assertIn('checkout not chosen', out)

    def test_check_only(self):
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('[Phone number] still on 2 pages', out)
        self.assertIn('--checkout shopify needs --shop-url', out)
        self.assertNotIn('CHANGES', out)
        self.ready(checkout='shopify', rewrites=False)
        before = snapshot(self.site)
        # the preview wording is a blocker too, listed sentence by sentence (and the Shopify route's checkout wording)
        shop = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--check-only')
        code, out = self.run_tool(*shop, rewrites=False)
        self.assertEqual(code, 1, out)
        self.assertIn('preview wording would still be on the live pages', out)
        self.assertIn('- Preview prices: we’re not taking orders yet. (33 places)', out)
        self.assertIn("checkout wording that doesn't fit --checkout shopify", out)
        self.assertIn('- In both cases the contract is made when we email to confirm your order has been accepted. (1 place)', out)
        code, out = self.run_tool(*shop, '--allow-preview-wording', rewrites=False)
        self.assertEqual(code, 3, out)
        self.assertIn('NOT READY TO PUBLISH', out)
        self.fill_rewrites(checkout='shopify')
        code, out = self.run_tool(*shop)
        self.assertEqual(code, 0, out)
        self.assertIn('BLOCKERS: none', out)
        self.assertEqual(snapshot(self.site), before)

    def test_leave_alone_placeholders_and_css_are_not_blockers(self):
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 0, out)
        self.assertIn('[your address]', read(self.site, 'delivery-returns.html'))
        self.assertIn('Settings &gt; [your name]', read(self.site, 'guides/remove-find-my-before-selling-iphone.html'))
        self.assertIn('[data-needs-quote]', read(self.site, 'index.html'))   # a CSS selector in <noscript><style>
        # the same text anywhere else is a blocker
        edit(self.site, 'about.html', '<h1>', '<h1>[date] ')
        edit(self.site, 'guides/remove-find-my-before-selling-iphone.html', '<h1>', '<h1>[your name] ')
        edit(self.site, 'delivery-returns.html', '<h1>', '<h1>[date] ')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r'placeholder \[date\] still on 2 pages \(2x\): about\.html:\d+, delivery-returns\.html:\d+')
        self.assertRegex(out, r'placeholder \[your name\] still on 1 page \(1x\): guides/remove-find-my-before-selling-iphone\.html:\d+')

    def test_placeholder_in_structured_data_and_meta_blocks(self):
        self.ready()
        edit(self.site, 'faq.html', '"@type":"Question","name":"', '"@type":"Question","name":"[Shop name] ')
        edit(self.site, 'shop.html', '<meta name="description" content="', '<meta name="description" content="[Tagline] ')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('[Shop name]', out)
        self.assertIn('[Tagline]', out)

    def test_leave_alone_list_matches_golive_md(self):
        with open(GOLIVE, encoding='utf-8') as fh:
            md = fh.read()
        para = re.search(r'\*\*Leave these alone:\*\*(.*?)\n\n', md, re.S).group(1)
        in_md = set(re.findall(r'`(\[[^\]`]+\])`', para)) | set(re.findall(r'"Settings > (\[[^\]]+\])"', para))
        in_tool = {text for _, text, _ in go_live.LEAVE_ALONE}
        self.assertEqual(in_md, in_tool, 'GO-LIVE.md section 3 "Leave these alone" and go_live.LEAVE_ALONE have drifted apart')
        files = {f for f, _, _ in go_live.LEAVE_ALONE}
        for f in files:
            self.assertIn(f, para)

    def test_price_problems_block(self):
        self.ready()
        edit(self.site, 'products/iphone-13.html', '&quot;Good&quot;:209', '&quot;Good&quot;:199')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('price check: products/iphone-13.html', out)
        # a mistyped data-prices makes check_site_prices.py crash rather than FAIL: still a blocker
        edit(self.site, 'products/iphone-13.html', '&quot;Good&quot;:199}', '&quot;Good&quot;:199')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('check_site_prices.py stopped with an error', out)

    def test_checkout_links(self):
        self.ready(link=False)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1)
        self.assertIn('every Payment Link in pay.js is empty', out)
        set_link(self.site, LINK_KEY, 'http://buy.stripe.com/insecure')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1)
        self.assertIn('is not an https:// link', out)
        edit(self.site, 'pay.js', 'http://buy.stripe.com/insecure', LINK)
        set_link(self.site, 'iPhone 16 Pro Max 1TB Excellent', 'https://buy.stripe.com/test_dear')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 0, out)
        self.assertIn('above the GBP 450 cap', out)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--check-only')
        self.assertEqual(code, 1)
        self.assertIn('sells the same phone twice', out)

    def test_bad_data_stock_blocks(self):
        self.ready()
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good":1,')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('data-stock is not valid JSON', out)
        # a key no option uses was a warning before R7; now a blocker, since that phone would show as not in stock
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good":1,"9TB|Good":1}')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('products/iphone-13.html:84: data-stock key(s) that aren\'t a storage and condition on this page: 9TB|Good', out)
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good":1}')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 0, out)

    def test_out_and_template_must_be_outside_site(self):
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--dry-run', '--out', os.path.join(self.site, 'report.txt'))
        self.assertEqual(code, 2)
        self.assertIn('inside --site', out)
        self.assertFalse(os.path.exists(os.path.join(self.site, 'report.txt')))
        code, out = self.run_tool('--domain', 'not a domain', '--dry-run')
        self.assertEqual(code, 2)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--dry-run', '--launch-date', '20/10/2026')
        self.assertEqual(code, 2)

    # ------------------------------------------------------------------ the switch itself
    def assert_switched(self, trade_ins='closed', host='www.fullbars.co.uk', date='2026-10-20', long_date='20 October 2026'):
        site = self.site
        for rel in html_files(site):
            src = read(site, rel)
            robots = re.findall(r'<meta name="robots" content="([^"]*)">', src)
            self.assertEqual(robots, ['noindex'] if rel == '404.html' else ['index,follow'], rel)
            self.assertNotIn('preview-bar', src, rel)
            self.assertNotIn('preview-note', src, rel)
            for tag in re.findall(r'<[a-z][^>]*\sdata-preview\b[^>]*>', src):
                self.assertEqual(trade_ins, 'closed', f'{rel}: {tag[:80]}')
                self.assertIn('id="qt"', tag, rel)
            if trade_ins == 'open':
                self.assertNotIn('qtPreview', src, rel)
            if rel.startswith('products/'):
                self.assertRegex(src, r'<a class="btn btn-hot btn-block" id="orderBtn" href="\.\./contact\.html">Order</a>', rel)
                self.assertNotIn('Opening soon', src, rel)
            for c in re.findall(r'<link rel="canonical" href="([^"]+)"', src):
                self.assertTrue(c.startswith(f'https://{host}/'), (rel, c))
        robots = read(site, 'robots.txt')
        self.assertIn('Allow: /', robots.splitlines())
        self.assertNotIn('Disallow: /', robots.splitlines())
        self.assertNotIn('#', robots)
        self.assertIn(f'Sitemap: https://{host}/sitemap.xml', robots)
        sm = read(site, 'sitemap.xml')
        self.assertEqual(set(re.findall(r'<lastmod>([^<]+)</lastmod>', sm)), {date})
        self.assertEqual(len(re.findall(r'<loc>https://' + re.escape(host) + '/', sm)), 55)
        for rel in ('terms.html', 'privacy.html', 'cookies.html', 'warranty.html', 'delivery-returns.html'):
            self.assertIn(f'<p class="legal-updated">Last updated {long_date}</p>', read(site, rel))
        contact = read(site, 'contact.html')
        self.assertIn('<option>Question about a phone</option><option>Order a phone</option>', contact)
        self.assertNotIn('Not trading yet', contact)
        r = subprocess.run([sys.executable, '-B', CHECKER, '--site', site, '--quiet'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('fails: 0', r.stdout)

    def test_full_switch_then_rerun_changes_nothing(self):
        self.ready()
        report = os.path.join(self.tmp, 'report.txt')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--out', report)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done.', out)
        self.assertIn('no preview wording is left', out)
        with open(report, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), out)
        self.assert_switched()
        # the trade-in tool keeps its preview hooks by default
        self.assertIn('data-preview="1"', read(self.site, 'sell.html'))
        self.assertIn('id="qtPreview"', read(self.site, 'sell.html'))
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done. 0 change(s) written to 0 file(s)', out)
        self.assertIn('taken as already done', out)   # the same --rewrites file again: already on the pages
        self.assertEqual(snapshot(self.site), before)
        # another day, no --launch-date: the live site's dates are left alone (nothing on those pages changed)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', date=None, rewrites=False)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done. 0 change(s) written to 0 file(s)', out)
        self.assertIn('already out of preview', out)
        self.assertEqual(snapshot(self.site), before)
        # unless Ash asks for a new date
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run', date='2026-10-21')
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: dry run. 60 change(s) would be made', out)

    def test_preview_wording_blocks_unless_allowed(self):
        """The switch refuses while customer-facing preview wording would stay on the live pages."""
        self.ready()
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', rewrites=False)
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('RESULT: REFUSED', out)
        self.assertIn('preview wording would still be on the live pages: 17 piece(s) of text in 140 place(s)', out)
        self.assertEqual(snapshot(self.site), before)
        # rewrites that cover only part of it still refuse
        partial = self.write_rewrites({'Preview prices: we’re not taking orders yet.': 'Each phone is a one-off.'}, 'partial.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', partial)
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('16 piece(s) of text in 107 place(s)', out)
        self.assertEqual(snapshot(self.site), before)
        # Ash can choose to switch anyway: written, but it says plainly it isn't publishable (exit 3)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--allow-preview-wording', rewrites=False)
        self.assertEqual(code, 3, out[-3000:])
        self.assertIn('RESULT: NOT READY TO PUBLISH.', out)
        self.assertIn('Preview prices: we&rsquo;re not taking orders yet.', read(self.site, 'products/iphone-13.html'))
        self.assertNotIn('preview-bar', read(self.site, 'products/iphone-13.html'))

    def test_dry_run_matches_real_run(self):
        self.ready()
        code, dry = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run')
        self.assertEqual(code, 0, dry[-3000:])
        n = int(re.search(r'RESULT: dry run\. (\d+) change', dry).group(1))
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0)
        self.assertEqual(int(re.search(r'RESULT: done\. (\d+) change', out).group(1)), n)
        strip = lambda t: re.sub(r'(?s)^.*?\nCHANGES', 'CHANGES', t).split('\nSTILL TO DO')[0].replace('none written: dry run', 'written')
        self.assertEqual(strip(dry), strip(out))

    def test_trade_ins_open_needs_send_form(self):
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--trade-ins', 'open')
        self.assertEqual(code, 1)
        self.assertIn('sell.html has no way to send a quote (missing #qtSend', out)
        add_send_forms(self.site)
        # with trade-ins open, the trade-in wording is a rewrite too (including the table caption in quote-ui.js)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--trade-ins', 'open', '--dry-run')
        self.assertEqual(code, 1, out[-3000:])
        self.assertNotIn('LEFT FOR WHEN TRADE-INS OPEN', out)
        todo = out.split('STILL TO DO BY HAND')[1]
        self.assertIn('Guide prices for when trade-ins open, not an offer.', todo)
        self.assertIn('Trade-ins open soon.', todo)
        js_before = read(self.site, 'quote-ui.js')
        self.fill_rewrites('open', lambda i, key: f'Rewritten "line" & {i}.')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--trade-ins', 'open')
        self.assertEqual(code, 0, out[-3000:])
        self.assert_switched(trade_ins='open')
        self.assertNotIn('LEFT FOR WHEN TRADE-INS OPEN', out)
        js = read(self.site, 'quote-ui.js')
        self.assertRegex(js, r"tbl\.innerHTML = '<caption>Rewritten \"line\" &amp; \d+\.</caption>' \+ head \+ body;")
        self.assertEqual(go_live.shape('quote-ui.js', js), go_live.shape('quote-ui.js', js_before))   # only string text changed

    def test_domain_change(self):
        self.ready()
        # new wording that keeps the email address: it follows --domain like every other address
        self.fill_rewrites(value=lambda i, key: 'Email hello@fullbars.co.uk any time.' if '@' in key else f'Line {i}.')
        code, out = self.run_tool('--domain', 'fullbars.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        self.assert_switched(host='www.fullbars.uk')
        for rel in html_files(self.site) + ['site.js', 'quote-ui.js', 'robots.txt', 'sitemap.xml']:
            src = read(self.site, rel)
            self.assertNotIn('fullbars.co.uk', src, rel)
        self.assertIn("var EMAIL = 'hello@fullbars.uk';", read(self.site, 'site.js'))
        with open(os.path.join(SITE, 'contact.html'), encoding='utf-8') as fh:
            want = fh.read().count('hello@fullbars.co.uk')
        self.assertEqual(read(self.site, 'contact.html').count('hello@fullbars.uk'), want)
        # apex host
        code, out = self.run_tool('--domain', 'fullbars.uk', '--no-www', '--checkout', 'stripe', rewrites=False)   # wording done
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('<link rel="canonical" href="https://fullbars.uk/">', read(self.site, 'index.html'))
        self.assertNotIn('www.fullbars', read(self.site, 'sitemap.xml'))

    def test_rewrites_template_and_apply(self):
        self.ready(rewrites=False)
        tpl = os.path.join(self.tmp, 'rewrites.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run', '--rewrites-template', tpl)
        self.assertEqual(code, 1, out[-2000:])   # the preview wording itself is the blocker
        with open(tpl, encoding='utf-8') as fh:
            data = json.load(fh)
        # one sentence per key, as a customer reads it, and no key inside another (so every key can be filled in)
        stock = 'Preview prices: we’re not taking orders yet.'
        self.assertIn(stock, data)
        self.assertIn('These are the prices we expect to charge when we open.', data)
        self.assertTrue(all(v is None for v in data.values()))
        self.assertEqual([(a, b) for a in data for b in data if a != b and a in b], [])
        self.assertFalse(any('&rsquo;' in k for k in data))
        data[stock] = 'Each phone is a one-off: we confirm the exact unit by email before you pay.'
        with open(tpl, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False)
        # replaced everywhere it appears: the 19 product pages, plus inside longer text on 14 other pages
        raw = 'Preview prices: we&rsquo;re not taking orders yet.'
        want = sum(read(self.site, rel).count(raw) for rel in html_files(self.site))
        self.assertEqual(want, 33)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', tpl, '--allow-preview-wording')
        self.assertEqual(code, 3, out[-2000:])
        self.assertEqual(len(re.findall(r'^  \S+:\d+  your rewrite \(--rewrites\)', out, re.M)), want)
        for rel in html_files(self.site):
            self.assertNotIn(raw, read(self.site, rel))
        self.assertIn('<p class="stock-note" id="stockNote">Each phone is a one-off: we confirm the exact unit by email before '
                      'you pay. These are the prices', read(self.site, 'products/pixel-8.html'))
        self.assertNotIn(stock, out.split('STILL TO DO BY HAND')[1])
        self.assertRegex(out, r'\(\d+ entries in your --rewrites file still null, so skipped\)')

    def test_rewrite_keys_in_any_form(self):
        """A key typed with &rsquo; or a straight apostrophe finds the same sentence; one that isn't on a page is an
        error; every overlap between two keys is listed in one run."""
        self.ready(rewrites=False)
        before = snapshot(self.site)
        for key in ('Preview prices: we&rsquo;re not taking orders yet.', "Preview prices: we're not taking orders yet."):
            path = self.write_rewrites({key: 'x'})
            code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', path, '--dry-run')
            self.assertEqual(len(re.findall(r'^  \S+:\d+  your rewrite', out, re.M)), 33, out[-2000:])
        path = self.write_rewrites({'This sentence is on no page.': 'x', 'We&rsquo;re not taking orders': 'a',
                                    'taking orders or messages': 'b', 'Preview prices: we’re not taking': 'c',
                                    'taking orders yet.': 'd'})
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', path)
        self.assertEqual(code, 1, out[-2000:])
        self.assertIn('3 problem(s), nothing written', out)
        self.assertIn('not on any page', out)
        self.assertEqual(out.count('two of your texts overlap'), 2)
        self.assertEqual(snapshot(self.site), before)
        # a shorter text inside a longer one of yours at the same place: the longer one wins there
        path = self.write_rewrites({'Preview prices: we’re not taking orders yet.': 'Short.',
                                    '“From” is our lowest price for that model, usually the smallest storage in Good grade. '
                                    'Preview prices: we’re not taking orders yet.': 'Long.'})
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', path, '--allow-preview-wording')
        self.assertEqual(code, 3, out[-2000:])
        self.assertIn('<p class="stock-note" id="stockNote">Short. These are the prices', read(self.site, 'products/iphone-13.html'))
        self.assertIn('>Long. These are the prices', read(self.site, 'guides/which-used-iphone-to-buy-2026.html'))
        self.assertIn('Good grade. Software updates:', read(self.site, 'collections/big-screen.html'))
        self.assertIn('published promises. Short. These are the prices', read(self.site, 'collections/big-screen.html'))
        # the template never overwrites an existing file
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run', '--rewrites-template', path)
        self.assertEqual(code, 2)

    def test_filled_template_switches_cleanly(self):
        """Fill every null in a generated template (with new wording, or "" to delete) and the switch goes through."""
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('no preview wording is left', out)
        self.assertIn('Rewritten line', read(self.site, 'products/iphone-13.html'))
        for rel in html_files(self.site):
            ld_blocks(read(self.site, rel))   # every block still parses
        # deleting every sentence instead leaves tidy text: no double spaces, no empty sentence left behind
        shutil.rmtree(self.site)
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns('*.png'))
        self.ready()
        self.fill_rewrites(value=lambda i, key: '')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        p = read(self.site, 'products/iphone-13.html')
        self.assertIn('<p class="stock-note" id="stockNote"></p>', p)
        self.assertIn('<meta name="description" content="Contact Full Bars about a refurbished iPhone, Galaxy or Pixel, a warranty '
                      'claim or selling your phone.">', read(self.site, 'contact.html'))
        self.assertIn('smallest storage in Good grade. Software updates:', read(self.site, 'collections/big-screen.html'))
        self.assertIn('published promises.</p>', read(self.site, 'collections/big-screen.html'))
        faq = [b for b in ld_blocks(read(self.site, 'faq.html')) if b.get('@type') == 'FAQPage'][0]
        answers = {q['name']: q['acceptedAnswer']['text'] for q in faq['mainEntity']}
        self.assertEqual(answers['How quickly will it arrive?'], 'That usually means it arrives the next working day. See delivery and returns.')

    def test_rewrite_escaping(self):
        """Quotes and & in new wording are escaped for where they land: page text, meta attribute, JSON-LD."""
        self.ready()
        with open(self.rw, encoding='utf-8') as fh:
            data = json.load(fh)
        card = 'Once we open, by card through a secure Stripe payment page; we’ll never see or store your card details.'
        data[card] = 'By card, through Stripe\'s "secure" page & nobody else\'s.'
        data['Opening soon.'] = 'Order now: we say "same day" & mean it.'
        path = self.write_rewrites(data, 'escaping.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', path)
        self.assertEqual(code, 0, out[-3000:])
        faq = read(self.site, 'faq.html')
        self.assertIn('<p>By card, through Stripe\'s "secure" page &amp; nobody else\'s.', faq)
        page = [b for b in ld_blocks(faq) if b.get('@type') == 'FAQPage'][0]
        self.assertTrue(page['mainEntity'][[q['name'] for q in page['mainEntity']].index('How do I pay?')]['acceptedAnswer']['text']
                        .startswith('By card, through Stripe\'s "secure" page & nobody else\'s. '))
        contact = read(self.site, 'contact.html')
        self.assertIn('selling your phone. Order now: we say &quot;same day&quot; &amp; mean it.">', contact)
        self.assertEqual(len(re.findall(r'content="[^"]*Order now: we say &quot;same day&quot; &amp; mean it\."', contact)), 2)
        # tags are refused outright, with nothing written
        shutil.rmtree(self.site)
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns('*.png'))
        self.ready()
        before = snapshot(self.site)
        data['Opening soon.'] = 'Order now: we say "same day" & mean it <b>'
        path = self.write_rewrites(data, 'escaping-bad.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--rewrites', path)
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('the new wording has < or >', out)
        self.assertEqual(snapshot(self.site), before)

    def test_trade_in_box_is_left_for_later(self):
        """With trade-ins closed, the #qtPreview box and the sell pages' trade-in sentences are true, so not a rewrite."""
        self.ready(rewrites=False)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run')
        todo, later = out.split('STILL TO DO BY HAND')[1].split('LEFT FOR WHEN TRADE-INS OPEN')
        for text in ('Trade-ins open soon.', 'We’re not buying phones yet, so this is a guide to what we expect to pay when we '
                     'open, not an offer.', 'Until then, the instant quote above gives a guide price for the six models it covers.'):
            self.assertNotIn(text, todo)
            self.assertIn(text, later)
        # on a live shop "When we open" reads as wrong, even on a sell page, so that one is a rewrite
        self.assertIn('When we open, we’ll quote most recent iPhone, Galaxy and Pixel models by email.\n      at sell.html:', todo)
        self.assertNotRegex(todo.split('\n  2. ')[0], r'sell(?:/[\w-]+)?\.html:(?:9[0-9])\b')   # nothing from the #qtPreview box

    def test_badge_and_facts_problems_block(self):
        """Problems only set_prices.py --check and check_site_facts.py see are launch blockers too."""
        self.ready()
        r = subprocess.run([sys.executable, '-B', os.path.join(PACK, 'set_prices.py'), '--set', 'iPhone 13 mini', '128GB', 'Good',
                            '129', self.site, '--allow-hand-edits'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('set_prices.py: needs a hand edit: "Lowest price" badge is on the iPhone 12 card', out)
        shutil.rmtree(self.site)
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns('*.png'))
        self.ready()
        edit(self.site, 'products/iphone-13-mini.html', 'weighing 141g instead of 174g', 'weighing 145g instead of 174g')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('facts check (facts.json): products/iphone-13-mini.html', out)
        self.assertIn('weight says 145g', out)

    def test_report_lists_every_leftover_grep_hit(self):
        """After the switch, every line GO-LIVE.md's grep (and go_live's wider net) finds is in the report."""
        self.ready(rewrites=False)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--allow-preview-wording')
        self.assertEqual(code, 3, out[-2000:])
        reported = set(re.findall(r'(?:^|, |at )([\w./-]+\.(?:html|js|css|txt|xml):\d+)', out, re.M))
        rx = re.compile(go_live.GOLIVE_GREP, re.I)
        hits = set()
        for d, _, fs in os.walk(self.site):
            for f in fs:
                if not f.endswith(('.html', '.js', '.css', '.txt', '.xml')):
                    continue
                rel = os.path.relpath(os.path.join(d, f), self.site).replace(os.sep, '/')
                for i, line in enumerate(read(self.site, rel).splitlines(), 1):
                    if rx.search(line) or go_live.SHOP_WORDS.search(line) or go_live.TRADE_WORDS.search(line):
                        hits.add(f'{rel}:{i}')
        self.assertTrue(hits)
        self.assertEqual(sorted(hits - reported), [], 'preview wording the report does not list')

    def test_never_writes_outside_site(self):
        self.ready()
        outside = os.path.join(self.tmp, 'outside')
        os.makedirs(outside)
        with open(os.path.join(outside, 'robots.txt'), 'w') as fh:
            fh.write('User-agent: *\nDisallow: /\n')
        os.symlink(os.path.join(outside, 'robots.txt'), os.path.join(self.site, 'guides', 'linked-robots.txt'))
        before = snapshot(outside)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-2000:])
        self.assertEqual(snapshot(outside), before)
        self.assertEqual(sorted(os.listdir(self.tmp)), ['outside', 'rewrites-closed.json', 'site'])
        self.assertEqual([f for d, _, fs in os.walk(self.site) for f in fs if f.startswith('.go_live')], [])

    def test_robots_rule_for_one_named_bot_is_kept(self):
        self.ready()
        edit(self.site, 'robots.txt', 'User-agent: *\nDisallow: /\n', 'User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow: /\n')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn('User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n', read(self.site, 'robots.txt'))

    def test_missing_robots_txt_is_created(self):
        self.ready()
        os.remove(os.path.join(self.site, 'robots.txt'))
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-2000:])
        self.assertEqual(read(self.site, 'robots.txt'), 'User-agent: *\nAllow: /\n\nSitemap: https://www.fullbars.co.uk/sitemap.xml\n')

    def test_unexpected_markup_is_caught(self):
        """If a page's Order span were hand-edited into something else, the run refuses instead of half-switching."""
        self.ready()
        edit(self.site, 'products/pixel-8.html', '<span class="btn btn-hot btn-block btn-off" id="orderBtn" aria-disabled="true">Opening soon</span>',
             '<button class="btn btn-hot btn-block btn-off" id="orderBtn" disabled>Opening soon</button>')
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 1)
        self.assertIn('products/pixel-8.html: Order control is not a link', out)
        self.assertEqual(snapshot(self.site), before)


    # ------------------------------------------------------------------ R7: Shopify order route, stock, checkout wording
    def assert_shopify_switched(self, shop=SHOP):
        for rel in product_pages(self.site):
            src = read(self.site, rel)
            url = f'{shop}/products/{rel[len("products/"):-len(".html")]}'
            tag = picker_tag(src)
            self.assertIn(f' data-shop="{url}"', tag, rel)
            self.assertNotIn('data-preview', tag, rel)
            self.assertIn(f'<a class="btn btn-hot btn-block" id="orderBtn" href="{url}">Order</a>', src, rel)
        for rel in html_files(self.site):
            self.assertNotIn('?order=', read(self.site, rel), rel)
        contact = read(self.site, 'contact.html')
        self.assertNotIn('Order a phone', contact)
        self.assertIn('<select id="cTopic"><option>Question about a phone</option><option>Selling my phone</option>', contact)
        r = subprocess.run([sys.executable, '-B', CHECKER, '--site', self.site, '--quiet'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_shopify_route_points_every_order_button_at_shopify(self):
        """--checkout shopify: data-shop and the Order link go to <shop>/products/<handle>, there is no email-order route,
        and the checklist covers the order confirmation email, Shopify stock and which static pages stay."""
        self.ready(checkout='shopify')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP + '/')
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done.', out)
        self.assertIn('Checkout: shopify (https://shop.example)', out)
        self.assertEqual(len(re.findall(r'^  products/[\w-]+\.html:84  product picker: data-shop added \(https://shop\.example/products/[\w-]+\)$', out, re.M)), 19)
        self.assertEqual(len(re.findall(r'^  products/[\w-]+\.html:93  Order button: dead "Opening soon" span -> link to the Shopify product$', out, re.M)), 19)
        self.assertIn('  19  product picker: data-shop added\n', out)   # the summary: one line per kind of change
        self.assert_shopify_switched()
        todo = out.split('STILL TO DO BY HAND')[1]
        for text in ('order-confirmation-email.html into Shopify\'s Settings > Notifications > Order confirmation',
                     'Place a test order', 'add stock only for units with all original manufacturer parts',
                     'Keep the static site live as the information front', 'no "Order a phone" topic, no ?order= links',
                     'send a Shopify draft order (a custom item whose title names the replaced part) as an invoice',
                     'Never a Payment Link: pay.js stays empty on this route', 'Decide the IMEI question at the top of both files'):
            self.assertIn(text, todo)
        self.assertNotIn('IMEI last 4', todo)
        self.assertNotIn('privacy.html still says', todo)   # privacy.html already matches cookies.html
        # a rerun changes nothing
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done. 0 change(s) written to 0 file(s)', out)
        self.assertEqual(snapshot(self.site), before)
        # and the Stripe route is refused while data-shop is on the pages (both checkouts at once = double-selling)
        set_link(self.site, LINK_KEY, LINK)
        add_stock(self.site)
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('--checkout stripe, but 19 product page(s) have data-shop (an Order link to Shopify)', out)
        self.assertEqual(snapshot(self.site), before)

    def test_moving_a_live_static_site_to_shopify(self):
        """Switched for Stripe first, then moved to Shopify: Order links follow, and the "Order a phone" topic goes."""
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('<option>Order a phone</option>', read(self.site, 'contact.html'))
        edit(self.site, 'pay.js', LINK, '')
        tpl = os.path.join(self.tmp, 'shopify-template.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run',
                                  '--rewrites-template', tpl, rewrites=False)
        self.assertEqual(code, 1, out[-3000:])   # the Shopify route's checkout wording is still to rewrite
        with open(tpl, encoding='utf-8') as fh:
            keys = list(json.load(fh))
        self.assertIn('In both cases the contract is made when we email to confirm your order has been accepted.', keys)
        self.rw = self.write_rewrites({k: f'Shopify line {i}.' for i, k in enumerate(keys)}, 'shopify.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('contact form: "Order a phone" topic removed (Shopify takes the orders)', out)
        self.assertEqual(len(re.findall(r'^  products/[\w-]+\.html:\d+  Order button: link -> https://shop\.example/products/[\w-]+$', out, re.M)), 19)
        self.assert_shopify_switched()

    def test_shopify_route_refusals(self):
        self.ready(checkout='shopify')
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify')
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('RESULT: REFUSED', out)
        self.assertIn('--checkout shopify needs --shop-url https://', out)
        for bad in ('http://shop.example', 'https://shop.example/?ref=1', 'shop.example', 'https://shop example',
                    'https://www.fullbars.co.uk', 'https://fullbars.co.uk/shop', 'https://shop.example/products'):
            code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', bad, '--check-only')
            self.assertEqual(code, 2, f'{bad}: {out}')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--shop-url', SHOP, '--check-only')
        self.assertEqual(code, 2, out)
        self.assertIn('--shop-url is only for --checkout shopify', out)
        # a product page whose handle isn't in the Shopify CSV: its Order button would have nowhere to go
        with open(CSV, encoding='utf-8', newline='') as fh:
            rows = fh.read().splitlines(True)
        short = os.path.join(self.tmp, 'short.csv')
        with open(short, 'w', encoding='utf-8', newline='') as fh:
            fh.writelines(r for r in rows if not r.startswith('iphone-13,') and ',iphone-13,' not in r[:80])
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--shopify-csv', short)
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('products/iphone-13.html: no product with URL handle "iphone-13" in short.csv', out)
        self.assertIn('data-shop is None, not the page\'s Shopify product (https://shop.example/products/iphone-13)', out)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--shopify-csv',
                                  os.path.join(self.tmp, 'missing.csv'), '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn("can't read", out)
        # the older column names (Handle) are read as well
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--shopify-csv',
                                  os.path.join(PACK, 'products-shopify-legacy-headers.csv'), '--check-only')
        self.assertEqual(code, 0, out)
        self.assertEqual(snapshot(self.site), before)

    def test_stock_validation_and_blockers(self):
        self.ready()
        stripe = ('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 1.5, "256GB|Good": "2", "512GB|Good": true, "128GB|Excellent": -1}')
        set_stock(self.site, 'products/iphone-14.html', '{"128GB|Good|Blue": 1}')
        set_stock(self.site, 'products/iphone-15.html', '{"128GB|Mint": 1}')
        set_stock(self.site, 'products/pixel-8.html', "{'128GB|Good': 1}")
        set_stock(self.site, 'products/galaxy-s23.html', None)
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        self.assertIn('products/iphone-13.html:84: data-stock count(s) that aren\'t a whole number of units (0 or more): '
                      '"128GB|Good": 1.5, "256GB|Good": "2", "512GB|Good": true, "128GB|Excellent": -1', out)
        self.assertIn('products/iphone-14.html:84: data-stock key(s) with a colour in them: 128GB|Good|Blue', out)
        self.assertIn('products/iphone-15.html:84: data-stock key(s) that aren\'t a storage and condition on this page: 128GB|Mint', out)
        self.assertIn('products/pixel-8.html:84: data-stock is not valid JSON', out)
        self.assertIn('data-stock is missing on 1 of 19 product pages (products/galaxy-s23.html)', out)
        # the right format passes: units per storage and condition, any whole number, {} = none held
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 2, "256GB|Very Good": 0}')
        for rel in ('products/iphone-14.html', 'products/iphone-15.html', 'products/pixel-8.html', 'products/galaxy-s23.html'):
            set_stock(self.site, rel, '{}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        # 2.0 and 1e0 are whole numbers in JSON (site.js counts them as held); NaN and Infinity aren't JSON at all
        set_stock(self.site, 'products/iphone-14.html', '{"128GB|Good": 2.0, "256GB|Good": 1e0}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        set_stock(self.site, 'products/iphone-14.html', '{"128GB|Good": NaN}')
        set_stock(self.site, 'products/iphone-15.html', '{"128GB|Good": Infinity}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        self.assertIn('products/iphone-14.html:84: data-stock is not valid JSON (NaN isn\'t allowed in JSON)', out)
        self.assertIn('products/iphone-15.html:84: data-stock is not valid JSON (Infinity isn\'t allowed in JSON)', out)
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 1.5}')
        code, out = self.run_tool(*stripe)
        self.assertIn('site.js treats them as not in stock. Write each as a plain number of units, such as 2', out)
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 2, "256GB|Very Good": 0}')
        for rel in ('products/iphone-14.html', 'products/iphone-15.html'):
            set_stock(self.site, rel, '{}')
        # a Payment Link for a phone data-stock says isn't held: never offered, so flagged
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 0}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        self.assertIn('pay.js has Payment Link(s) for phones data-stock says you don\'t hold', out)
        # Shopify: Shopify's stock decides, so no data-stock is fine, and data-stock that is there gets a warning
        edit(self.site, 'pay.js', LINK, '')
        self.fill_rewrites(checkout='shopify')
        shopify = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--check-only')
        code, out = self.run_tool(*shopify)
        self.assertEqual(code, 0, out)
        self.assertIn('19 product page(s) have data-stock. On the Shopify route Shopify\'s own stock decides', out)
        for rel in product_pages(self.site):
            set_stock(self.site, rel, None)
        code, out = self.run_tool(*shopify)
        self.assertEqual(code, 0, out)
        self.assertNotIn('data-stock', out)

    def test_checkout_wording_report(self):
        """The wording about ordering and paying that doesn't fit the chosen checkout is listed and blocks; a sentence
        that is still true can be kept by mapping it to itself, but preview wording can't."""
        self.ready(rewrites=False)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run')
        self.assertEqual(code, 1, out[-3000:])
        todo = out.split('STILL TO DO BY HAND')[1].split('\n  2. ')[0]
        stripe_line = 'Payment will be by card through Stripe, our intended payment provider; we will never see or store your card details.'
        self.assertIn("Checkout wording that doesn't fit --checkout stripe: 1 piece(s) of text in 1 place(s)", todo)
        self.assertIn(f'- 1 file: {stripe_line}\n      at terms.html:', todo)
        self.assertIn("checkout wording that doesn't fit --checkout stripe: 1 piece(s)", out.split('BLOCKERS')[-1])
        self.assertNotIn('ask when you order', todo.lower())   # still true on the static route: you order, then pay
        self.assertIn('order-confirmation-email.md, filled in, as the confirmation email for every order', out)
        edit(self.site, 'pay.js', LINK, '')   # Shopify needs pay.js empty
        # Shopify: terms section 3 (how the contract is made) and the FAQ's "How do I pay?" are listed in full
        tpl = os.path.join(self.tmp, 'shopify.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run',
                                  '--rewrites-template', tpl)
        self.assertEqual(code, 1, out[-3000:])
        todo, rest = out.split('STILL TO DO BY HAND')[1].split('\n  2. ', 1)
        preview_part, checkout_part = todo.split("Checkout wording that doesn't fit --checkout shopify")
        terms3 = ['When you send us an order by email, we reply to confirm availability, the exact phone and the total price, '
                  'with a secure payment link.',
                  'If you buy using a “Buy now” payment link on our website, you’ll be asked to accept these terms before '
                  'paying, and your payment is an offer to buy.',
                  'Buy now is only offered on phones with all original manufacturer parts.',
                  'In both cases the contract is made when we email to confirm your order has been accepted.']
        faq_pay = ['If you order by email, we’ll reply with a payment link once we’ve confirmed your exact phone, its battery '
                   'health and colour.',
                   'Some phones will also have a Buy now button: those have all original manufacturer parts, and we’ll confirm '
                   'the exact battery health and colour by email within one working day of payment, with a full refund if we '
                   'can’t match your choice.']
        for text in terms3 + faq_pay + [stripe_line, 'Contact Us & Order by Email | Full Bars', 'subject to stock; we confirm before you pay',
                                        'For orders: the phone, storage, grade and colour, your delivery address and a phone number for the courier.',
                                        'Phones with any replaced part are sold by email order only, never through a Buy now button.',
                                        'Card payments will be handled by Stripe; we will never see or store your card details.']:
            self.assertIn(f': {text}\n', checkout_part)
        # "ask when you order" promises: on Shopify, ordering is paying, so "before you pay" can't be kept as worded.
        # The photos answer is in the page and in the FAQ structured data; the battery answer on the FAQ and home page.
        photos = 'If you’d like photos of the exact phone you’re buying, ask when you order and we’ll send them before you pay.'
        self.assertRegex(checkout_part, re.escape(f'- 1 file: {photos}\n') + r'      at faq\.html:28, faq\.html:\d+\n')
        self.assertRegex(checkout_part, r'- 2 files: Ask when you order\.\n      at faq\.html:28, faq\.html:\d+, index\.html:\d+\n')
        # the FAQ answer's other two sentences are preview wording, listed (and rewritten) with the rest of it
        for text in ('Once we open, by card through a secure Stripe payment page; we’ll never see or store your card details.',
                     'We’re not taking payments yet.'):
            self.assertIn(f': {text}\n', preview_part)
        self.assertNotIn('buy now, pay later', checkout_part.lower())
        self.assertIn('SHOWN ONLY BESIDE A STRIPE BUY NOW LINK', rest)
        self.assertIn('Buy now phones have all original manufacturer parts.', rest.split('SHOWN ONLY BESIDE')[1])
        self.assertNotIn('Buy now phones have all original manufacturer parts.', todo)
        with open(tpl, encoding='utf-8') as fh:
            keys = json.load(fh)
        for text in terms3 + faq_pay + [stripe_line, photos, 'Ask when you order.']:
            self.assertIn(text, keys)
        # keep a sentence that is still true on Shopify by giving it its own text: listed as kept, not changed
        keep = 'Colour and grade availability is subject to stock and confirmed before you pay.'
        data = {k: (k if k == keep else f'Shopify line {i}.') for i, k in enumerate(keys)}
        # privacy.html's quote-tool line already matches cookies.html, so there is no reminder about it
        self.rw = self.write_rewrites(data, 'shopify-filled.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('for this tab only', html.unescape(read(self.site, 'privacy.html')))
        self.assertNotIn('privacy.html still says', out)
        self.assertIn(keep, read(self.site, 'terms.html'))
        self.assertIn('Checkout wording you kept as it is', out)
        self.assertIn(f': {keep}\n', out.split('Checkout wording you kept as it is')[1])
        self.assertIn('Shopify line', read(self.site, 'faq.html'))
        faq = read(self.site, 'faq.html')
        self.assertNotIn('ask when you order', faq.lower())   # gone from the page text and the structured data
        self.assertEqual(len(re.findall(r'Shopify line \d+\.', ld_blocks(faq)[0]['mainEntity'][2]['acceptedAnswer']['text'])), 1)
        # preview wording can't be "kept": mapping it to itself still blocks
        shutil.rmtree(self.site)
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns('*.png'))
        self.ready(checkout='shopify', rewrites=False)
        data['We’re not taking payments yet.'] = 'We’re not taking payments yet.'
        self.rw = self.write_rewrites(data, 'shopify-keep-preview.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run')
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('preview wording would still be on the live pages: 1 piece(s) of text in 2 place(s)', out)


class UnitTest(unittest.TestCase):
    def test_segments_decode_and_map_back(self):
        src = ('<p>We&rsquo;re open.\n   Order <a href="x">here</a> now.</p><meta name="description" content="A &amp; B">'
               '<script type="application/ld+json">{"text":"Say \\"hi\\" \\u003e there"}</script><img alt="Phone">')
        segs = go_live.segments('x.html', src)
        texts = [(g.ctx, g.text) for g in segs]
        self.assertIn(('html', 'We’re open. Order '), texts)
        self.assertIn(('attr', 'A & B'), texts)
        self.assertIn(('json', 'Say "hi" > there'), texts)
        self.assertIn(('attr', 'Phone'), texts)
        g = segs[0]
        i = g.text.index('open.')
        self.assertEqual(src[g.starts[i]:g.ends[i + 4]], 'open.')
        self.assertEqual(go_live.sentence_bounds('One. Two? e.g. three. “Four.” Five'), [(0, 4), (5, 21), (22, 29), (30, 34)])

    def test_encode_per_context(self):
        plain = 'Say "hi" & go \\ now'
        segs = {g.ctx: g for g in go_live.segments('x.html', '<p>t</p><img alt="t"><script type="application/ld+json">["t"]</script>')}
        self.assertEqual(go_live.encode(plain, segs['html']), 'Say "hi" &amp; go \\ now')
        self.assertEqual(go_live.encode(plain, segs['attr']), 'Say &quot;hi&quot; &amp; go \\ now')
        self.assertEqual(json.loads('"' + go_live.encode(plain, segs['json']) + '"'), plain)
        js = go_live.segments('x.js', "var a = 'it&rsquo;s';")[0]
        self.assertEqual(go_live.encode("it's & \\", js), "it\\'s &amp; \\\\")

    def test_verify_catches_broken_structured_data(self):
        import datetime
        import types
        opt = types.SimpleNamespace(trade_ins='closed', set_dates=False, launch_date=datetime.date(2026, 10, 20))
        page = '<link rel="canonical" href="https://www.fullbars.co.uk/"><script type="application/ld+json">{"a":"x"}</script>'
        files = {'a.html': page, 'robots.txt': 'User-agent: *\nAllow: /\n'}
        self.assertEqual(go_live.verify(files, opt, 'www.fullbars.co.uk', None), [])
        files['a.html'] = page.replace('"x"', '"say "x""')
        self.assertIn('structured data (JSON-LD) is no longer valid JSON', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))

    def test_damage_checks(self):
        before = {'a.html': '<p class="x">Hi</p><meta name="description" content="Hi">'}
        after = {'a.html': '<p class="x">Hi</p><meta name="description" content="Say "hi"">'}
        self.assertEqual(len(go_live.rewrite_damage(before, after, {'a.html'})), 1)
        self.assertEqual(go_live.rewrite_damage(before, before, {'a.html'}), [])
        js0, js1 = {'a.js': "var a = 'x'; f();"}, {'a.js': "var a = 'x'y'; f();"}
        self.assertEqual(len(go_live.rewrite_damage(js0, js1, {'a.js'})), 1)

    def test_js_marks(self):
        src = "var a = /^https:\\/\\//.test(x); // not 'a string'\nvar b = 'Opening soon'; /* when we open */ c = d / 2;"
        marks = go_live.js_marks(src)
        self.assertEqual(marks[src.index('Opening')], 2)
        self.assertEqual(marks[src.index('when we open')], 1)
        self.assertEqual(marks[src.index('a string')], 1)
        self.assertEqual(marks[src.index('test')], 0)

    def test_element_end(self):
        src = '<div a><div><p>x</p></div><div></div></div><div>after</div>'
        self.assertEqual(src[:go_live.element_end(src, 0)], '<div a><div><p>x</p></div><div></div></div>')

    def test_parse_shop_url(self):
        self.assertEqual(go_live.parse_shop_url(' HTTPS://Shop.Example/ '), 'https://shop.example')
        self.assertEqual(go_live.parse_shop_url('https://fullbars.myshopify.com'), 'https://fullbars.myshopify.com')
        self.assertEqual(go_live.parse_shop_url('https://shop.example/en-gb/'), 'https://shop.example/en-gb')
        for bad in ('http://shop.example', 'https://shop.example/?a=1', 'https://shop.example/#x', 'shop.example',
                    'https://shop example', 'https://shop.example/"><script>', 'javascript:alert(1)',
                    # a page inside the store, not its address: /products/<handle> would be doubled
                    'https://shop.example/products', 'https://shop.example/products/', 'https://shop.example/Products/iphone-13',
                    'https://shop.example/en-gb/products', 'https://shop.example/collections/all', 'https://shop.example/cart'):
            with self.assertRaises(go_live.Fail, msg=bad):
                go_live.parse_shop_url(bad)
        self.assertEqual(go_live.parse_shop_url('https://products.example'), 'https://products.example')   # a host, not a path
        with self.assertRaises(go_live.Fail) as cm:
            go_live.parse_shop_url('https://shop.example/products')
        self.assertIn('adds /products/<handle> for each phone itself', str(cm.exception))

    def test_csv_handles_and_whole_counts(self):
        tmp = tempfile.mkdtemp(prefix='go_live_unit_')
        try:
            for head in ('Title,URL handle,Price', 'Handle,Title,Variant Price'):
                p = os.path.join(tmp, 'a.csv')
                with open(p, 'w', encoding='utf-8') as fh:
                    col = head.split(',').index('URL handle' if 'URL handle' in head else 'Handle')
                    rows = [['x', 'y', 'z'], ['x', 'y', 'z']]
                    rows[0][col], rows[1][col] = 'iphone-13', 'pixel-8'
                    fh.write(head + '\n' + '\n'.join(','.join(r) for r in rows) + '\n')
                self.assertEqual(go_live.csv_handles(p), ({'iphone-13', 'pixel-8'}, None))
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write('Title,Price\nA,1\n')
            self.assertIsNone(go_live.csv_handles(p)[0])
        finally:
            shutil.rmtree(tmp)
        # JSON has one kind of number: site.js reads 2, 2.0 and 2e0 all as 2 (held), so go_live accepts them too
        self.assertEqual([go_live.whole_count(v) for v in (0, 2, 1.0, 2e0, 1.5, -1, -2.0, True, False, '1', None,
                                                           float('nan'), float('inf'))],
                         [True, True, True, True, False, False, False, False, False, False, False, False, False])

    def test_checkout_patterns(self):
        rx = go_live.CHECKOUT_WORDS
        self.assertTrue(rx['stripe'].search('through Stripe, our intended payment provider;'))
        self.assertFalse(rx['stripe'].search('Some phones will also have a Buy now button'))
        for hit in ('a Buy now button', 'a secure Stripe payment page', 'with a payment link', 'If you order by email',
                    'sold by email order only', 'we confirm before you pay',
                    'ask when you order and we&rsquo;ll send them before you pay', 'Ask when you order.'):
            self.assertTrue(rx['shopify'].search(hit), hit)
        self.assertFalse(rx['stripe'].search('ask when you order and we’ll send them before you pay'))
        self.assertFalse(rx['shopify'].search('ask us before you order and we’ll send them'))
        self.assertFalse(rx['shopify'].search('We do not offer credit, finance, pay monthly or buy now, pay later.'))
        # the sentences the Shopify route lists by name are still on the site, word for word
        pages = ''
        for f in ('terms.html', 'contact.html'):
            with open(os.path.join(SITE, f), encoding='utf-8') as fh:
                pages += fh.read()
        for sentence in go_live.SHOPIFY_SENTENCES:
            self.assertIn(sentence, pages)

    def test_verify_checks_the_order_route(self):
        import datetime
        import types
        opt = types.SimpleNamespace(trade_ins='closed', set_dates=False, launch_date=datetime.date(2026, 10, 20),
                                    checkout='shopify', shop_url=SHOP)
        head = '<link rel="canonical" href="https://www.fullbars.co.uk/x">'
        good = (head + f'<form class="picker" id="picker" data-model="X" data-shop="{SHOP}/products/x">'
                f'<a class="btn" id="orderBtn" href="{SHOP}/products/x">Order</a>')
        files = {'products/x.html': good, 'robots.txt': 'User-agent: *\nAllow: /\n'}
        self.assertEqual(go_live.verify(files, opt, 'www.fullbars.co.uk', None), [])
        files['products/x.html'] = good.replace(f'href="{SHOP}/products/x"', 'href="../contact.html"')
        self.assertIn('Order link goes to ../contact.html', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        files['products/x.html'] = good.replace('/products/x"', '/products/y"', 1)
        self.assertIn('data-shop is', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        files['contact.html'] = head + '<form id="contactForm"><select id="cTopic"><option>Order a phone</option></select></form>'
        self.assertIn('still has the "Order a phone" topic', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        opt.checkout = 'stripe'
        files['products/x.html'] = good
        self.assertIn('data-shop is still on the page', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))

    def test_parse_domain(self):
        self.assertEqual(go_live.parse_domain('https://www.FullBars.co.uk/', False), ('fullbars.co.uk', 'www.fullbars.co.uk'))
        self.assertEqual(go_live.parse_domain('fullbars.co.uk', True), ('fullbars.co.uk', 'fullbars.co.uk'))
        with self.assertRaises(go_live.Fail):
            go_live.parse_domain('full bars', False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
