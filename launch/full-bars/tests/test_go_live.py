#!/usr/bin/env python3
"""Tests for go_live.py, the Full Bars launch-day switch.

Run from the repo root:  python3 launch/full-bars/tests/test_go_live.py
Each test works on a fresh copy of sites/full-bars in a temporary folder (set TMPDIR to choose where).
The real site folder is only ever read. Python 3 standard library only.
"""
import collections
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


def handles(site):
    return [r[len('products/'):-len('.html')] for r in product_pages(site)]


def set_stock_js(site, entries=None, raw=None):
    """Write stock.js as Ash would: its header kept, then the entries as JSON (or raw text after the header)."""
    src = read(site, 'stock.js')
    head = src[:src.rindex('window.FULLBARS_STOCK =')]
    body = raw if raw is not None else 'window.FULLBARS_STOCK = ' + json.dumps(entries or {}, indent=2) + ';\n'
    write(site, 'stock.js', head + body)


def add_stock(site):
    """stock.js for every phone, as Ash fills it on the static route: nothing held, except one iPhone 13 128GB Good
    (the phone with the test Payment Link)."""
    set_stock_js(site, {h: ({'128GB|Good': 1} if h == 'iphone-13' else {}) for h in handles(site)})


def add_page_stock(site):
    """The older way: data-stock on every product page (and stock.js empty)."""
    set_stock_js(site, {})
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
        self.assertIn('NOT READY TO GO LIVE', out)
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
        # R12: the static route fails closed: every product picker, card grid and row of range tiles is marked
        marked, unmarked = go_live.stock_marks(go_live.load_site(site))
        self.assertEqual((len(marked), unmarked), (58, []))
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
        self.assertIn('RESULT: NOT READY TO GO LIVE.', out)
        self.assertIn('before you deploy the site to your web host.', out)
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
            self.assertIn(f'<a class="btn btn-hot btn-block" id="orderBtn" href="{url}" aria-describedby="handoffNote">'
                          'Choose and pay on the next page</a>', src, rel)
            self.assertIn('<p class="small handoff-note" id="handoffNote">You&rsquo;ll pick storage', src, rel)
        for rel in html_files(self.site):
            self.assertNotIn('?order=', read(self.site, rel), rel)
        contact = read(self.site, 'contact.html')
        self.assertNotIn('Order a phone', contact)
        self.assertIn('<select id="cTopic"><option>Question about a phone</option><option>Selling my phone</option>', contact)
        r = subprocess.run([sys.executable, '-B', CHECKER, '--site', self.site, '--quiet'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # R12: no fail-closed mark on the Shopify route (stock.js is optional there)
        self.assertEqual(go_live.stock_marks(go_live.load_site(self.site))[0], [])

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
        self.assertIn('  19  product picker: data-stock-required removed (Shopify route: stock.js is optional)\n', out)
        self.assertIn('  38  card grid: data-stock-required removed (Shopify route: stock.js is optional)\n', out)
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
        """The older per-page data-stock is still read and checked (stock.js empty here). On the static route a phone whose
        stock is only there is itself a blocker (its cards can't read it), so a well-formed data-stock leaves exactly that
        one blocker."""
        self.ready()
        add_page_stock(self.site)
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
        self.assertIn('no stock data for 1 of 19 product pages (products/galaxy-s23.html): neither stock.js nor the page\'s '
                      'data-stock says what you hold', out)
        # the right format: units per storage and condition, any whole number, {} = none held. It passes its own checks,
        # leaving only the blocker that the stock isn't in stock.js
        only_attr = ('BLOCKERS (1): fix these first', '1. 19 phone(s) keep their stock only in the older data-stock attribute')
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 2, "256GB|Very Good": 0}')
        for rel in ('products/iphone-14.html', 'products/iphone-15.html', 'products/pixel-8.html', 'products/galaxy-s23.html'):
            set_stock(self.site, rel, '{}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        for line in only_attr:
            self.assertIn(line, out)
        # 2.0 and 1e0 are whole numbers in JSON (site.js counts them as held); NaN and Infinity aren't JSON at all
        set_stock(self.site, 'products/iphone-14.html', '{"128GB|Good": 2.0, "256GB|Good": 1e0}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        for line in only_attr:
            self.assertIn(line, out)
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
        self.assertEqual(code, 1, out)
        for line in only_attr:
            self.assertIn(line, out)
        self.assertIn('pay.js has Payment Link(s) for phones your stock data says you don\'t hold', out)
        # Shopify: Shopify's stock decides, so no data-stock is fine, and hand-kept data-stock that is there gets a warning
        edit(self.site, 'pay.js', LINK, '')
        self.fill_rewrites(checkout='shopify')
        shopify = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--check-only')
        code, out = self.run_tool(*shopify)
        self.assertEqual(code, 0, out)
        self.assertIn('19 product page(s) have the older data-stock attribute, kept by hand, which doesn\'t follow Shopify\'s '
                      'stock', out)
        # and it is checked there just as on the Stripe route: a bad count blocks
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 1.5}')
        code, out = self.run_tool(*shopify)
        self.assertEqual(code, 1, out)
        self.assertIn('products/iphone-13.html:84: data-stock count(s) that aren\'t a whole number of units', out)
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
        terms2 = ('On an email order we confirm the colour and grade before you pay; if you pay straight away online, we '
                  'confirm them by email within one working day, and if we can’t match your choice, we refund you in full.')
        for text in terms3 + faq_pay + [stripe_line, terms2, 'Contact Us & Order by Email | Full Bars',
                                        'For orders: the phone, storage, grade and colour, your delivery address and a phone number for the courier.',
                                        'Phones with any replaced part are sold by email order only, never through a Buy now button.',
                                        'Card payments will be handled by Stripe; we will never see or store your card details.']:
            self.assertIn(f': {text}\n', checkout_part)
        # R8: the photos and battery answers and the colour note now hold on every route ("ask us before you order",
        # "confirmed by email"), so they aren't listed; nor is terms section 3's online-ordering paragraph (regulation 9)
        for text in ('ask us before you order', 'Ask us before you order', 'confirmed by email', 'If you buy online, these are the steps',
                     'The contract is in English only', 'Every phone is a one-off'):
            self.assertNotIn(text, checkout_part)
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
        for text in terms3 + faq_pay + [stripe_line, terms2]:
            self.assertIn(text, keys)
        # keep a sentence that is still true on Shopify by giving it its own text: listed as kept, not changed
        keep = terms2
        data = {k: (k if k == keep else f'Shopify line {i}.') for i, k in enumerate(keys)}
        # privacy.html's quote-tool line already matches cookies.html, so there is no reminder about it
        self.rw = self.write_rewrites(data, 'shopify-filled.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('for this tab only', html.unescape(read(self.site, 'privacy.html')))
        self.assertNotIn('privacy.html still says', out)
        self.assertIn(keep, html.unescape(read(self.site, 'terms.html')))
        self.assertIn('Checkout wording you kept as it is', out)
        self.assertIn(f': {keep}\n', out.split('Checkout wording you kept as it is')[1])
        self.assertIn('Shopify line', read(self.site, 'faq.html'))
        faq = read(self.site, 'faq.html')
        self.assertNotIn('ask when you order', faq.lower())
        # the photos answer (page and structured data) was already true on Shopify, so it is untouched
        self.assertNotIn('Shopify line', ld_blocks(faq)[0]['mainEntity'][2]['acceptedAnswer']['text'])
        self.assertIn('ask us before you order and we’ll send them.', ld_blocks(faq)[0]['mainEntity'][2]['acceptedAnswer']['text'])
        pay = [q for q in ld_blocks(faq)[0]['mainEntity'] if q['name'] == 'How do I pay?'][0]['acceptedAnswer']['text']
        self.assertEqual(len(re.findall(r'Shopify line \d+\.', pay)), 4)   # every sentence: Stripe, email order, Buy now, preview
        # terms section 3's online-ordering paragraph (E-Commerce Regulations 2002, reg 9) survives the Shopify rewrite
        terms = html.unescape(read(self.site, 'terms.html'))
        self.assertIn('If you buy online, these are the steps:', terms)
        self.assertIn('The contract is in English only.', terms)
        # preview wording can't be "kept": mapping it to itself still blocks
        shutil.rmtree(self.site)
        shutil.copytree(SITE, self.site, ignore=shutil.ignore_patterns('*.png'))
        self.ready(checkout='shopify', rewrites=False)
        data['We’re not taking payments yet.'] = 'We’re not taking payments yet.'
        self.rw = self.write_rewrites(data, 'shopify-keep-preview.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run')
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('preview wording would still be on the live pages: 1 piece(s) of text in 2 place(s)', out)

    # ------------------------------------------------------------------ R8: stock.js, Shopify variants, Buy now wording, hosting
    def test_stock_js_is_the_one_place(self):
        """stock.js holds the static route's stock: checked like data-stock, and a phone missing from it (with no
        data-stock either) blocks the Stripe route."""
        self.ready()
        stripe = ('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        self.assertNotIn('stock', out.split('BLOCKERS')[-1].lower().replace('blockers: none', ''))
        good = {h: {} for h in handles(self.site)}
        good['iphone-13'] = {'128GB|Good': 1, '256GB|Very Good': 2}
        # every kind of mistake, reported by name
        bad = dict(good)
        bad['iphone-99'] = {'128GB|Good': 1}
        bad['iphone-14'] = {'128GB|Good|Blue': 1, '128GB|Mint': 1, '256GB|Good': 1.5, '512GB|Good': '2', '128GB|Excellent': -1}
        bad['pixel-8'] = [1]
        del bad['galaxy-s23']
        set_stock_js(self.site, bad)
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        self.assertIn('stock.js: "iphone-99" is not a product page (there is no products/iphone-99.html)', out)
        self.assertIn('stock.js "iphone-14" key(s) with a colour in them: 128GB|Good|Blue', out)
        self.assertIn('stock.js "iphone-14" key(s) that aren\'t a storage and condition on that phone\'s page: 128GB|Mint', out)
        self.assertIn('stock.js "iphone-14" count(s) that aren\'t a whole number of units (0 or more): "256GB|Good": 1.5, '
                      '"512GB|Good": "2", "128GB|Excellent": -1', out)
        self.assertIn('stock.js: "pixel-8" must be its storage and condition counts in braces', out)
        self.assertIn('no stock data for 2 of 19 product pages (products/galaxy-s23.html, products/pixel-8.html)', out)
        # not JSON (single quotes), NaN, and anything after the list: refused with the reason
        for raw, why in (("window.FULLBARS_STOCK = {'iphone-13': {}};\n", 'Expecting property name enclosed in double quotes'),
                         ('window.FULLBARS_STOCK = {"iphone-13": {"128GB|Good": NaN}};\n', 'NaN isn\'t allowed in JSON'),
                         ('window.FULLBARS_STOCK = {};\nwindow.x = 1;\n', 'has something after the stock list')):
            set_stock_js(self.site, raw=raw)
            code, out = self.run_tool(*stripe)
            self.assertEqual(code, 1, out)
            self.assertIn(why, out)
        # comments and trailing commas are fine (they're fine in JavaScript too)
        body = ',\n'.join(f'  "{h}": {json.dumps(v)}' for h, v in good.items())
        set_stock_js(self.site, raw='window.FULLBARS_STOCK = {\n  // what we hold\n' + body + ',\n};\n')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        # data-stock for a page stock.js doesn't list: its product page would sell the phone, but its cards and range
        # tiles read stock.js alone and would say "None in stock right now", so on the static route it is a blocker
        del good['galaxy-s23']
        set_stock_js(self.site, good)
        set_stock(self.site, 'products/galaxy-s23.html', '{"128GB|Good": 1}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        self.assertIn('1 phone(s) keep their stock only in the older data-stock attribute: products/galaxy-s23.html. Their '
                      'product pages use it, but their cards and range tiles can\'t read it, so on the live static route they '
                      'would say "None in stock right now" while the page sells the phone', out)
        self.assertNotIn('no stock data for', out)
        # where both exist stock.js wins, with a warning
        set_stock_js(self.site, dict(good, **{'galaxy-s23': {'128GB|Good': 1}}))
        set_stock(self.site, 'products/iphone-13.html', '{"128GB|Good": 5}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        self.assertIn('2 product page(s) have data-stock as well as an entry in stock.js: products/galaxy-s23.html, '
                      'products/iphone-13.html. stock.js wins', out)
        # the Payment Link's phone: stock.js says 1 held, so no warning; at 0 the link is flagged even though data-stock says 5
        self.assertNotIn('your stock data says you don\'t hold', out)
        good['iphone-13'] = {'128GB|Good': 0}
        set_stock_js(self.site, dict(good, **{'galaxy-s23': {'128GB|Good': 1}}))
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)
        self.assertIn('pay.js has Payment Link(s) for phones your stock data says you don\'t hold, so the page shows "Not in '
                      'stock" and never offers them: iPhone 13 128GB Good', out)
        # a product page that doesn't load stock.js would never see its stock: a blocker
        edit(self.site, 'products/pixel-8.html', '<script src="../stock.js" defer></script>\n', '\n')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        self.assertIn('1 product page(s) have stock in stock.js but don\'t load it before site.js, so site.js never sees it: '
                      'products/pixel-8.html', out)
        edit(self.site, 'products/pixel-8.html', '<script src="../pay.js" defer></script>\n\n',
             '<script src="../pay.js" defer></script>\n<script src="../stock.js" defer></script>\n')
        # a missing stock.js is only a warning on Shopify (and stock data there is a warning too)
        set_stock_js(self.site, good)         # 18 phones: galaxy-s23 left out
        edit(self.site, 'pay.js', LINK, '')   # Shopify needs pay.js empty
        for rel in ('products/galaxy-s23.html', 'products/iphone-13.html'):
            set_stock(self.site, rel, None)
        self.fill_rewrites(checkout='shopify')
        shopify = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--check-only')
        code, out = self.run_tool(*shopify)
        self.assertEqual(code, 0, out)
        self.assertIn('stock.js lists 18 phone(s) but wasn\'t written by fetch_shopify_variants.py --write-stock, so it '
                      'doesn\'t follow Shopify\'s stock', out)
        self.assertIn('1 product page(s) have no stock data while stock.js lists other phones: products/galaxy-s23.html', out)
        os.remove(os.path.join(self.site, 'stock.js'))
        code, out = self.run_tool(*shopify)
        self.assertEqual(code, 0, out)
        self.assertIn('the pages load stock.js, but the site folder has none', out)

    # ------------------------------------------------------------------ R12: stock.js after launch, fail closed
    def stock_body(self, drop=()):
        """stock.js's code as add_stock() writes it (one iPhone 13 128GB Good, every other phone {}), minus drop."""
        entries = {h: ({'128GB|Good': 1} if h == 'iphone-13' else {}) for h in handles(self.site) if h not in drop}
        return 'window.FULLBARS_STOCK = ' + json.dumps(entries, indent=2) + ';\n'

    def test_stock_js_typos_a_browser_cant_read_block_the_launch(self):
        """Typos that make browsers drop the whole of stock.js are blockers, with the line, even the ones outside the
        stock list (before it, or a comment closed twice); comments and trailing commas are still fine. They are reported
        once, by go_live.py itself (set_prices.py --check, which it also runs, leaves stock to it)."""
        self.ready()
        stripe = ('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        good = self.stock_body()
        js = read(self.site, 'stock.js')
        head = js[:js.rindex('window.FULLBARS_STOCK =')]   # the header comment
        n = head.count('\n') + 1                          # the first line after it
        for raw, why in ((',\n' + good, f'stock.js line {n}: "," is outside the comment, before window.FULLBARS_STOCK'),
                         ('s' + good, f'stock.js line {n}: "s" is outside the comment, before window.FULLBARS_STOCK'),
                         ('*/\n' + good, f'stock.js line {n}: "*/" is outside the comment'),
                         ('/* a /* b */ c */\n' + good, f'stock.js line {n}: "c */" is outside the comment'),
                         (good.replace('"128GB|Good": 1', '"128GB|Good": 1,,'), 'is not valid JSON'),
                         # a phone's last count deleted, its comma left: {,} (browsers refuse it; a JSON reader that
                         # drops "trailing" commas would read {})
                         (good.replace('"pixel-8": {}', '"pixel-8": {,}'), '(a comma with no entry before it, as in {,} or '
                          '1,,: delete it)'),
                         (good.replace('};', '},'), 'has something after the stock list (",")'),
                         (good + '}\n', 'has something after the stock list ("}")')):
            write(self.site, 'stock.js', head + raw)
            code, out = self.run_tool(*stripe)
            self.assertEqual(code, 1, out[-2000:])
            self.assertIn(why, out)
            self.assertNotIn('no stock data for', out)   # the typo is the problem to fix, not 19 phones
            self.assertIn('If a browser can\'t run the file (a stray comma, a missing brace or a stray character stops it), '
                          'it ignores all of it', out)
            self.assertNotIn('set_prices.py --check failed', out)
            self.assertEqual(out.count('stock.js line'), 1, out[-3000:])
        for raw in (good.replace('};', '}; // sold the 13 on Monday'), good.replace('\n', '\r\n'),
                    good.replace('{}\n};', '{},\n};')):
            write(self.site, 'stock.js', head + raw)
            code, out = self.run_tool(*stripe)
            self.assertEqual(code, 0, out[-2000:])

    def test_static_route_needs_stock_js_on_every_page(self):
        """With the pages failing closed, the static route needs stock.js itself and every page with a picker, cards or
        range tiles must load it; a phone whose stock is only in the older data-stock is a blocker (its cards can't
        read it). The Shopify route needs none of this."""
        self.ready()
        stripe = ('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        js = read(self.site, 'stock.js')
        os.remove(os.path.join(self.site, 'stock.js'))
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out[-2000:])
        self.assertIn('the site folder has no stock.js. On the live static route site.js fails closed without it', out)
        write(self.site, 'stock.js', js)
        edit(self.site, 'shop.html', '<script src="stock.js" defer></script>', '')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out[-2000:])
        self.assertIn('1 page(s) with a product picker, phone cards or range tiles don\'t load stock.js before site.js: '
                      'shop.html', out)
        edit(self.site, 'shop.html', '<script src="site.js"', '<script src="stock.js" defer></script><script src="site.js"')
        set_stock_js(self.site, raw=self.stock_body(drop=('galaxy-s23',)))
        set_stock(self.site, 'products/galaxy-s23.html', '{"128GB|Good": 1}')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out[-2000:])   # its cards would say "None in stock right now" while the page sells it
        self.assertIn('1 phone(s) keep their stock only in the older data-stock attribute: products/galaxy-s23.html. Their '
                      'product pages use it, but their cards and range tiles can\'t read it', out)
        self.assertIn('Copy each phone\'s data-stock list into stock.js under its handle ("galaxy-s23": {...})', out)
        self.assertNotIn('no stock data for', out)
        # moved into stock.js (the page's data-stock left too: stock.js wins, a warning only): it launches
        set_stock_js(self.site, raw=self.stock_body())
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out[-2000:])
        self.assertNotIn('keep their stock only in the older data-stock', out)
        self.assertIn('1 product page(s) have data-stock as well as an entry in stock.js: products/galaxy-s23.html', out)

    def test_after_launch_set_prices_check_reads_stock_js(self):
        """The routine check after every stock edit (set_prices.py --check) runs go_live.py's stock check on the switched
        static site: it passes as switched, and fails on a typo, a phone left out, a lost mark or a missing stock.js."""
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        self.assertEqual(go_live.site_route(go_live.load_site(self.site)), 'stripe')

        def check():
            r = subprocess.run([sys.executable, '-B', os.path.join(PACK, 'set_prices.py'), '--check', self.site],
                               capture_output=True, text=True, timeout=300)
            return r.returncode, r.stdout + r.stderr
        code, out = check()
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('STOCK (stock.js), checked as go_live.py checks it, on the static (Stripe) route', out)
        js = read(self.site, 'stock.js')
        for name, raw, why in (
                ('stray comma', js.replace('"128GB|Good": 1', '"128GB|Good": 1,,'), 'is not valid JSON'),
                ('phone left out', re.sub(r'\n  "pixel-8": \{\}', '', js).replace('},\n}', '}\n}'),
                 'no stock data for 1 of 19 product pages (products/pixel-8.html)'),
                ('negative count', js.replace('"128GB|Good": 1', '"128GB|Good": -1'),
                 'stock.js "iphone-13" count(s) that aren\'t a whole number of units (0 or more): "128GB|Good": -1'),
                # a phone's last count deleted, its comma left: browsers drop the whole file
                ('{,}', js.replace('"pixel-8": {}', '"pixel-8": {,}'), '(a comma with no entry before it'),
                ('{ , } as the list', js[:js.rindex('window.FULLBARS_STOCK =')] + 'window.FULLBARS_STOCK = {\n  ,\n};\n',
                 '(a comma with no entry before it')):
            self.assertNotEqual(raw, js, name)
            write(self.site, 'stock.js', raw)
            code, out = check()
            self.assertEqual(code, 1, name)
            self.assertIn(why, out, name)
            self.assertIn('RESULT: FAIL', out, name)
            code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
            self.assertEqual(code, 1, name)
            self.assertIn(why, out, name)
        write(self.site, 'stock.js', js)
        # a phone held only in its page's older data-stock: the page would sell it while its cards said "None in stock
        # right now", so both checks fail until it is moved into stock.js
        write(self.site, 'stock.js', re.sub(r'\n  "galaxy-s23": \{\},?', '', js))
        set_stock(self.site, 'products/galaxy-s23.html', '{"128GB|Good": 2}')
        code, out = check()
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('1 phone(s) keep their stock only in the older data-stock attribute: products/galaxy-s23.html', out)
        self.assertEqual(self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')[0], 1)
        write(self.site, 'stock.js', js)
        set_stock(self.site, 'products/galaxy-s23.html', None)
        edit(self.site, 'shop.html', ' id="shopGrid" data-stock-required="1"', ' id="shopGrid"')
        code, out = check()
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('1 product picker(s), card grid(s) or row(s) of range tiles have no data-stock-required="1": '
                      'shop.html:', out)
        # go_live.py puts the mark back (and reports it as the switch would be incomplete without it otherwise)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe')
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('card grid: data-stock-required added', out)
        self.assertEqual(check()[0], 0)

    def test_stock_marks_and_route(self):
        """stock_mark_tags finds what go_live.py marks; verify() wants the marks on the static route and none on Shopify;
        site_route reads the route off the pages."""
        files = go_live.load_site(SITE)
        marked, unmarked = go_live.stock_marks(files)
        self.assertEqual((marked, len(unmarked)), ([], 58))
        kinds = collections.Counter(u.rsplit('(', 1)[1] for u in unmarked)
        self.assertEqual(kinds, {'product picker)': 19, 'card grid)': 38, 'range tiles)': 1})
        self.assertIsNone(go_live.site_route(files))   # the preview
        page = '<div class="x"><div class="grid"><article class="card"><a href="products/a.html">A</a></article></div></div>' \
               '<article class="card"><a href="products/b.html">B</a></article>'
        tags = [(w, m.group(0)) for w, m in go_live.stock_mark_tags(page)]
        self.assertEqual(tags, [('card grid', '<div class="grid">'), ('product card', '<article class="card">')])
        self.assertTrue(go_live.stock_mark_problems({'p.html': page}, 'stripe'))
        self.assertEqual(go_live.stock_mark_problems({'p.html': page}, 'shopify'), [])
        marked_page = page.replace('<div class="grid">', '<div class="grid" data-stock-required="1">')
        self.assertTrue(go_live.stock_mark_problems({'p.html': marked_page}, 'shopify'))
        self.assertEqual(go_live.site_route({'p.html': marked_page}), 'stripe')

    def variants_file(self, pick=lambda h, i: True, name='variants.json', extra=None):
        """A --shop-variants file as fetch_shopify_variants.py writes it, with made-up IDs for every option on the pages
        (pick(handle, i) chooses which to include)."""
        data, n = {}, 44000000000000
        for rel in product_pages(self.site):
            src = read(self.site, rel)
            tag = picker_tag(src)
            h = rel[len('products/'):-len('.html')]
            keys = sorted(f'{c}|{col}' for c in go_live.picker_combos(tag) for col in go_live.picker_colours(src))
            for i, k in enumerate(keys):
                n += 1
                if pick(h, i):
                    data.setdefault(h, {})[k] = str(n)
        data.update(extra or {})
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
        return path, data

    def test_shop_variants_open_the_chosen_phone(self):
        """--shop-variants: each picker gets data-variants, the no-JavaScript Order link opens the variant ticked in the
        HTML, a page with no IDs gets none, and every bad key or ID is refused."""
        self.ready(checkout='shopify')
        # iPhone 13: every variant; Pixel 8: every other one; the rest: none
        path, data = self.variants_file(lambda h, i: h == 'iphone-13' or (h == 'pixel-8' and i % 2 == 0))
        base = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        code, out = self.run_tool(*base, '--shop-variants', path)
        self.assertEqual(code, 0, out[-3000:])
        src = read(self.site, 'products/iphone-13.html')
        tag = picker_tag(src)
        self.assertEqual(json.loads(html.unescape(re.search(r' data-variants="([^"]*)"', tag).group(1))), data['iphone-13'])
        self.assertEqual(go_live.picker_default(src), '128GB|Very Good|Blue')
        vid = data['iphone-13']['128GB|Very Good|Blue']
        self.assertIn(f'<a class="btn btn-hot btn-block" id="orderBtn" href="{SHOP}/products/iphone-13?variant={vid}">Order</a>', src)
        self.assertIn('<p class="small handoff-note" id="handoffNote" hidden>', src)
        self.assertIn(f' data-shop="{SHOP}/products/iphone-13"', tag)
        self.assertNotIn('data-variants', picker_tag(read(self.site, 'products/iphone-12.html')))
        # no ID for the phone ticked in the HTML: never "Order" beside our price, and the note under the button shows
        self.assertIn(f'href="{SHOP}/products/iphone-12" aria-describedby="handoffNote">Choose and pay on the next page</a>',
                      read(self.site, 'products/iphone-12.html'))
        self.assertIn('<p class="small handoff-note" id="handoffNote">', read(self.site, 'products/iphone-12.html'))
        # Pixel 8: every other variant has an ID; its link follows whether the ticked one does
        px = read(self.site, 'products/pixel-8.html')
        px_vid = data['pixel-8'].get(go_live.picker_default(px))
        if px_vid:
            self.assertIn(f'href="{SHOP}/products/pixel-8?variant={px_vid}">Order</a>', px)
        else:
            self.assertIn(f'href="{SHOP}/products/pixel-8" aria-describedby="handoffNote">Choose and pay on the next page</a>', px)
        self.assertIn('--shop-variants has no variant IDs for 17 product page(s)', out)
        self.assertIn('phone choices with no Shopify variant ID, whose Order button reads "Choose and pay on the next page"', out)
        self.assertRegex(out, r'products/pixel-8\.html \(\d+ of \d+\)')
        self.assertIn('Shopify variants: ', out.split('STILL TO DO BY HAND')[1])
        # the variant instructions live in GO-LIVE.md section 5, step 13
        self.assertIn('--shop-variants (GO-LIVE.md section 5, step 13)', out.split('STILL TO DO BY HAND')[1])
        self.assertNotIn('--shop-variants (GO-LIVE.md section 7)', out)
        # a rerun, with or without the file, changes nothing
        before = snapshot(self.site)
        for extra in ((), ('--shop-variants', path)):
            code, out = self.run_tool(*base, *extra)
            self.assertEqual(code, 0, out[-3000:])
            self.assertIn('RESULT: done. 0 change(s) written to 0 file(s)', out)
            self.assertEqual(snapshot(self.site), before)
        # a new file without the iPhone 13: its data-variants goes and its link is the plain product again
        path2, _ = self.variants_file(lambda h, i: h == 'pixel-8', name='variants2.json')
        code, out = self.run_tool(*base, '--shop-variants', path2)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('product picker: data-variants removed', out)
        src = read(self.site, 'products/iphone-13.html')
        self.assertNotIn('data-variants', picker_tag(src))
        self.assertIn(f'href="{SHOP}/products/iphone-13" aria-describedby="handoffNote">Choose and pay on the next page</a>', src)
        self.assertIn('<p class="small handoff-note" id="handoffNote">', src)
        self.assertIn(f'Order button: link -> {SHOP}/products/iphone-13\n', out)
        self.assertIn('aria-describedby="handoffNote">Choose and pay on the next page</a>+}', out)
        self.assertIn('hand-off note shown', out)
        # and back again: the iPhone 13's IDs return, so its link reads "Order" to the variant and the note hides
        code, out = self.run_tool(*base, '--shop-variants', path)
        self.assertEqual(code, 0, out[-3000:])
        src = read(self.site, 'products/iphone-13.html')
        self.assertIn(f'<a class="btn btn-hot btn-block" id="orderBtn" href="{SHOP}/products/iphone-13?variant={vid}">Order</a>', src)
        self.assertIn('<p class="small handoff-note" id="handoffNote" hidden>', src)
        self.assertIn('hand-off note hidden', out)
        # every key must be one of the page's storage, condition and colour options; every ID a whole number
        before = snapshot(self.site)
        path3, _ = self.variants_file(lambda h, i: h == 'iphone-13' and i < 2, name='bad.json',
                                      extra={'iphone-14': {'128GB|Good|Plum': '1', '128GB|Good': '2', '128GB|Good|Blue': 'abc',
                                                           '256GB|Good|Blue': 1.5}, 'iphone-99': {'128GB|Good|Blue': '3'}})
        code, out = self.run_tool(*base, '--shop-variants', path3)
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('--shop-variants "iphone-14": variant(s) that aren\'t a storage, condition and colour on '
                      'products/iphone-14.html: 128GB|Good, 128GB|Good|Plum', out)
        self.assertIn('--shop-variants "iphone-14": variant ID(s) that aren\'t a Shopify variant ID (a whole number): '
                      '"128GB|Good|Blue": "abc", "256GB|Good|Blue": 1.5', out)
        self.assertIn('--shop-variants has product(s) with no page on the site: iphone-99', out)
        self.assertEqual(snapshot(self.site), before)
        # only with --checkout shopify, and only a readable file of the right shape
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--shop-variants', path, '--check-only')
        self.assertEqual(code, 2, out)
        self.assertIn('--shop-variants is only for --checkout shopify', out)
        for content in ('not json', '[1, 2]', '{"iphone-13": [1]}'):
            with open(path3, 'w', encoding='utf-8') as fh:
                fh.write(content)
            code, out = self.run_tool(*base, '--shop-variants', path3, '--check-only')
            self.assertEqual(code, 2, out)
            self.assertIn('--shop-variants', out)

    def test_buy_now_wording_gate(self):
        """With a Payment Link in pay.js, a promise to confirm or send something "before you pay" is checkout wording
        on the static route too, unless the sentence limits it to email orders."""
        self.ready()
        stripe = ('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 0, out)   # the site's own wording already holds beside Buy now
        # the R7 wording, put back: listed and blocking
        with open(os.path.join(PACK, '..', '..', 'sites', 'full-bars', 'terms.html'), encoding='utf-8') as fh:
            assert 'On an email order we confirm the colour and grade before you pay' in fh.read()
        edit(self.site, 'terms.html', 'Colour and grade availability is subject to stock. On an email order we confirm the colour '
             'and grade before you pay; if you pay straight away online, we confirm them by email within one working day, and '
             'if we can&rsquo;t match your choice, we refund you in full.',
             'Colour and grade availability is subject to stock and confirmed before you pay.')
        edit(self.site, 'products/iphone-13.html', 'subject to stock; confirmed by email', 'subject to stock; we confirm before you pay')
        edit(self.site, 'faq.html', 'ask us before you order and we&rsquo;ll send them.',
             'ask when you order and we&rsquo;ll send them before you pay.')
        edit(self.site, 'faq.html', 'Want the exact figure for any phone? Ask us before you order.',
             'Want the exact figure for any phone? Ask when you order.')
        edit(self.site, 'products/pixel-8.html', 'Ask before you order and we&rsquo;ll send photos of the exact phone.',
             'Ask and we&rsquo;ll send photos of the exact phone before you pay.')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        listed = out.split("checkout wording that doesn't fit --checkout stripe")[1]
        for text in ('Colour and grade availability is subject to stock and confirmed before you pay.',
                     'subject to stock; we confirm before you pay',
                     'If you’d like photos of the exact phone you’re buying, ask when you order and we’ll send them before you pay.',
                     'Ask when you order.', 'Ask and we’ll send photos of the exact phone before you pay.'):
            self.assertIn(f'- {text}', listed)
        # an email-order promise is still true beside Buy now, so it isn't listed
        self.assertNotIn('On an email order', listed)
        self.assertNotIn('If you order by email, we’ll reply with a payment link', listed)
        # without a Payment Link there is no Buy now, so the same sentences are fine (the empty pay.js blocks instead)
        edit(self.site, 'pay.js', LINK, '')
        code, out = self.run_tool(*stripe)
        self.assertEqual(code, 1, out)
        self.assertIn('every Payment Link in pay.js is empty', out)
        self.assertNotIn('confirmed before you pay', out)

    def test_shopify_lists_a_claim_that_orders_cant_be_seen_online(self):
        """Terms section 3 says how the contract is kept (E-Commerce Regulations 2002, reg 9(1)(b)) in words true on both
        routes. Shopify shows each order on its order status page, so a sentence saying customers can't see their order
        on the website is checkout wording there (listed for rewriting), but not on the static route."""
        self.ready(checkout='shopify', rewrites=False)
        terms = read(self.site, 'terms.html')
        self.assertIn('We keep a record of your order, as our <a href="privacy.html">privacy policy</a> explains, and you '
                      'can email us for a copy of it.', terms)
        old = 'We keep a record of your order, but you can&rsquo;t view it on our website.'
        edit(self.site, 'terms.html', 'We keep a record of your order, as our <a href="privacy.html">privacy policy</a> '
             'explains, and you can email us for a copy of it.', old)
        tpl = os.path.join(self.tmp, 'shopify-old.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run',
                                  '--rewrites-template', tpl, rewrites=False)
        self.assertEqual(code, 1, out[-3000:])
        checkout_part = out.split("Checkout wording that doesn't fit --checkout shopify")[1].split('\n  2. ')[0]
        self.assertIn(': We keep a record of your order, but you can’t view it on our website.\n', checkout_part)
        with open(tpl, encoding='utf-8') as fh:
            self.assertIn('We keep a record of your order, but you can’t view it on our website.', json.load(fh))
        # on the static route (email orders and Payment Links) it is true, so it isn't listed there
        set_link(self.site, LINK_KEY, LINK)
        add_stock(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run', rewrites=False)
        self.assertNotIn('view it on our website', out)

    def test_hosting_is_a_launch_step(self):
        """The switch's checklist and GO-LIVE.md send the switched site to a web host, not the claude.ai preview."""
        self.ready()
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        todo = out.split('STILL TO DO BY HAND')[1]
        self.assertNotIn('Republish', todo)
        self.assertIn('Deploy the switched folder to your web host at https://www.fullbars.co.uk/, with HTTPS on', todo)
        self.assertIn('must answer 200 at that exact address', todo)
        self.assertIn('not a redirect to an address without .html', todo)
        # "publish" is what you do to the claude.ai artifact; the live site is deployed to the web host
        result = out.split('RESULT:')[-1]
        self.assertNotRegex(result, r'(?i)\bpublish\b')
        self.assertIn('The claude.ai artifact stays a preview copy', todo)
        self.assertIn('Stock: change stock.js (and only stock.js)', todo)
        with open(GOLIVE, encoding='utf-8') as fh:
            md = fh.read()
        self.assertNotRegex(md, r'(?i)\brepublish')
        accounts = md.split('## 2. Business and accounts')[1].split('## 3.')[0]
        self.assertIn('| Web host for the static site, with HTTPS |', accounts)
        self.assertIn('GitHub Pages doesn\'t', accounts)
        self.assertIn('domain, web host, inbox', md.split('## 1.')[0])
        deploy = md.split('**Deploy to your web host.**')[1].split('- [ ]')[0]
        for text in ('/robots.txt', '/sitemap.xml', '/products/iphone-13.html', 'no-such-page', 'curl -sI', '404',
                     'redirect to it permanently', '--no-www', 'confirmation emails', 'answers `200` at exactly that address',
                     "grep -o '<loc>[^<]*'", 'stripping `.html`', '`301` or `308`'):
            self.assertIn(text, deploy)
        # every check names the status it must answer: 200 directly, never a redirect
        checks = deploy.split('Check each of these')[1]
        for line in [ln for ln in checks.splitlines() if ln.strip().startswith('- ')]:
            self.assertRegex(line, r'`(200|301|404)`', line)
        # the host row warns that some hosts strip .html with a redirect, and endorses no provider
        self.assertIn('not a redirect.**', accounts)
        self.assertIn('Cloudflare Pages\' docs say it redirects `/contact.html` to `/contact`', accounts)
        self.assertNotIn('are two such services', accounts)
        step12 = md.split('12. **Which static pages stay live')[1].split('13. **Variant IDs')[0]
        self.assertIn('shop.fullbars.co.uk', step12)
        self.assertIn('hello@info.fullbars.co.uk', step12)


    # ------------------------------------------------------------------ R9: replaced-part wording, stock snapshot, prices
    def golive_examples(self):
        """GO-LIVE.md section 4's example rewrites for the replaced-part sentences, read from the file, so this test follows
        whatever the checklist tells Ash to write."""
        with open(GOLIVE, encoding='utf-8') as fh:
            md = fh.read()
        block = md.split('- **Replaced parts.**')[1].split('- **Weights.**')[0]
        faq = re.search(r'"(Phones with any replaced part are sold by email order only, never through a Buy now button\.)" In '
                        r'your `--rewrites` file, reword it without the Buy now part, for example "([^"]+)"', block)
        grading = re.search(r'"(Phones with a “Buy now” button have all original manufacturer parts\.)", for example "([^"]+)"', block)
        self.assertTrue(faq and grading, 'GO-LIVE.md section 4 no longer has the replaced-part examples')
        return {faq.group(1): faq.group(2), grading.group(1): grading.group(2)}

    def test_replaced_parts_rewrite_follows_go_live_md(self):
        """On the Shopify route, a sentence saying replaced-part phones are sold by email order is still true (GO-LIVE.md
        section 4), so it isn't listed; one that also mentions Buy now is. GO-LIVE.md's own example rewrites switch cleanly,
        in the page text and the FAQ's structured data, even with the new sentence also given as a keep-as-is key."""
        examples = self.golive_examples()
        self.assertEqual(examples['Phones with any replaced part are sold by email order only, never through a Buy now button.'],
                         'Phones with any replaced part are sold by email order only: ask us about one through the contact page.')
        self.ready(checkout='shopify', rewrites=False)
        keys = self.template(checkout='shopify')
        kept = 'Phones with any replaced part are sold by email order only, so you always hear about it before paying.'
        self.assertNotIn(kept, keys)                 # grading.html, first half: true on Shopify too
        for k in examples:
            self.assertIn(k, keys)                   # the FAQ sentence and grading.html's second half: they mention Buy now
        data = {k: examples.get(k, f'Shopify line {i}.') for i, k in enumerate(keys)}
        new_faq = examples['Phones with any replaced part are sold by email order only, never through a Buy now button.']
        data[new_faq] = new_faq                      # Ash keeping his own new sentence: this used to fail "not on any page"
        self.rw = self.write_rewrites(data, 'shopify-parts.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done.', out)
        self.assertIn('is your new wording for another sentence in the same file, so it isn\'t on the pages yet: nothing to keep', out)
        grading = html.unescape(read(self.site, 'grading.html'))
        self.assertIn(kept + ' ' + examples['Phones with a “Buy now” button have all original manufacturer parts.'] + '</p>', grading)
        self.assertNotIn('Buy now', grading)
        faq = read(self.site, 'faq.html')
        genuine = [q for q in ld_blocks(faq)[0]['mainEntity'] if q['name'] == 'Are they genuine phones?'][0]['acceptedAnswer']['text']
        self.assertIn(new_faq + ' Full Bars is an independent business', genuine)
        self.assertIn(new_faq + ' Full Bars is an independent business', html.unescape(faq).split('<summary>Are they genuine phones?')[1])
        self.assertNotIn('never through a Buy now button', html.unescape(faq))
        # nothing about replaced parts is left to rewrite, and a rerun with the same file changes nothing
        before = snapshot(self.site)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        self.assertEqual(code, 0, out[-3000:])
        self.assertIn('RESULT: done. 0 change(s) written to 0 file(s)', out)
        self.assertEqual(snapshot(self.site), before)
        self.assertNotIn('replaced part', out.split('STILL TO DO BY HAND')[1].split('\n  2. ')[0])

    def test_own_wording_is_never_checkout_wording(self):
        """Wording Ash supplies in --rewrites is his decision: checkout words in it are shown, never blocking. Preview
        wording in it is still caught."""
        self.ready(checkout='shopify', rewrites=False)
        keys = self.template(checkout='shopify')
        pay = 'If you order by email, we’ll reply with a payment link once we’ve confirmed your exact phone, its battery health and colour.'
        self.assertIn(pay, keys)
        mine = 'You pay at checkout in our Shopify shop; if you’d rather order by email, ask us first.'
        data = {k: (mine if k == pay else f'Shopify line {i}.') for i, k in enumerate(keys)}
        self.rw = self.write_rewrites(data, 'shopify-own.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        own = out.split('Checkout words in your own new wording')[1].split('\n  2. ')[0]
        self.assertIn(f': {mine}\n', own)
        self.assertNotIn(mine, out.split('BLOCKERS')[-1])
        # the same words in a sentence that is still the site's own are listed and block, as before
        self.assertIsNotNone(go_live.CHECKOUT_WORDS['shopify'].search(mine))
        data[pay] = 'Payments open soon.'
        self.rw = self.write_rewrites(data, 'shopify-own-preview.json')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run')
        self.assertEqual(code, 1, out[-3000:])
        self.assertIn('preview wording would still be on the live pages', out)

    def snapshot_stock(self, available=lambda h, key: True, fetched='now', shop=SHOP):
        """stock.js as fetch_shopify_variants.py --write-stock writes it from a saved copy of Shopify's answers (no
        network). fetched: when the copy was fetched ("now", a datetime, or None for a copy that doesn't say); the
        snapshot carries that time, as it would from a real --save-dump file."""
        sys.path.insert(0, HERE)
        import test_fetch_variants as tfv   # noqa: E402  (its fake live store)
        prices = tfv.csv_prices()
        dump = {'shop': shop, 'products': {h: tfv.live_product(h, pr, lambda k, h=h: available(h, k))
                                           for h, pr in prices.items()}}
        if fetched == 'now':
            fetched = go_live.utc_now()
        if fetched is not None:
            dump['fetched'] = fetched.strftime('%Y-%m-%dT%H:%M:%SZ')
        path = os.path.join(self.tmp, 'dump.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(dump, fh)
        r = subprocess.run([sys.executable, '-B', os.path.join(PACK, 'fetch_shopify_variants.py'), '--from-dump', path,
                            '--write-stock', os.path.join(self.site, 'stock.js')], capture_output=True, text=True, timeout=120)
        fresh = fetched is not None and go_live.staleness(fetched) is None
        self.assertEqual(r.returncode, 0 if fresh else 1, r.stdout + r.stderr)   # a stale copy is reported as such
        return r.stdout

    def test_shopify_stock_snapshot_is_checked_but_optional(self):
        """On the Shopify route stock.js is optional; a snapshot from Shopify is checked just as on the Stripe route, and
        a stale, other-store, hand-kept or partial one gets a warning."""
        self.ready(checkout='shopify')
        shopify = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        code, out = self.run_tool(*shopify, '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        todo = out.split('STILL TO DO BY HAND')[1]
        self.assertIn('Stock on the site (optional, recommended): stock.js has no Shopify stock snapshot', todo)
        self.assertIn(f'fetch_shopify_variants.py --shop-url {SHOP} --check-prices', todo)
        self.assertIn('never by importing the CSV again', todo)
        # a fresh snapshot of every phone: no stock warnings, and the checklist says to keep it fresh
        self.snapshot_stock(available=lambda h, k: h != 'iphone-12' and not (h == 'iphone-13' and k.startswith('128GB|Very Good')))
        code, out = self.run_tool(*shopify, '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        self.assertNotIn('stock.js', out.split('WARNINGS')[-1].split('BLOCKERS')[0] if 'WARNINGS' in out else '')
        todo = out.split('STILL TO DO BY HAND')[1]
        self.assertIn('Stock snapshot: stock.js holds Shopify\'s stock for 19 phone(s) as of ', todo)
        self.assertIn('straight after you add stock and at least daily', todo)
        entries = go_live.read_stock_js(go_live.load_site(self.site))[0]
        self.assertEqual(entries['iphone-12'], {})
        self.assertNotIn('128GB|Very Good', entries['iphone-13'])
        # checked as on the Stripe route: a bad key or count blocks
        js = read(self.site, 'stock.js')
        self.assertIn('\n  "iphone-13": {"', js)
        write(self.site, 'stock.js', js.replace('\n  "iphone-13": {', '\n  "iphone-13": {"128GB|Mint": 1, "128GB|Very Good": 1.5, ', 1))
        code, out = self.run_tool(*shopify, '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('stock.js "iphone-13" key(s) that aren\'t a storage and condition on that phone\'s page: 128GB|Mint', out)
        self.assertIn('stock.js "iphone-13" count(s) that aren\'t a whole number of units (0 or more): "128GB|Very Good": 1.5', out)
        write(self.site, 'stock.js', js)
        # stale, or from another store: warnings, not blockers. A saved copy fetched long ago keeps its own time
        self.snapshot_stock(fetched=go_live.datetime.datetime(2026, 1, 2, 9, 0, tzinfo=go_live.datetime.timezone.utc))
        self.assertIn('Shopify stock snapshot: 2026-01-02 09:00 UTC', read(self.site, 'stock.js'))
        code, out = self.run_tool(*shopify, '--check-only')
        self.assertEqual(code, 0, out)
        self.assertIn('stock.js is a Shopify stock snapshot from 2026-01-02 09:00 UTC (', out)
        self.assertIn('more than 24 hours old', out)
        self.snapshot_stock(shop='https://other-shop.example')
        code, out = self.run_tool(*shopify, '--check-only')
        self.assertEqual(code, 0, out)
        self.assertIn('stock.js is a stock snapshot from https://other-shop.example, not from --shop-url https://shop.example', out)
        # a partial snapshot: the phones it leaves out show every option as orderable
        js = read(self.site, 'stock.js')
        write(self.site, 'stock.js', re.sub(r'\n  "pixel-8": \{[^\n]*\}', '', js).replace('},\n};', '}\n};'))
        self.assertNotIn('pixel-8', go_live.read_stock_js(go_live.load_site(self.site))[0])
        code, out = self.run_tool(*shopify, '--check-only')
        self.assertEqual(code, 0, out)
        self.assertIn('1 product page(s) have no stock data while stock.js lists other phones: products/pixel-8.html', out)

    def test_snapshot_age_is_in_hours_and_comes_from_shopify(self):
        """go_live.py measures a snapshot's age in hours, from the time fetch_shopify_variants.py stamped on it: the time
        Shopify sent the data, so a snapshot written today from an old saved copy is still old. Over 24 hours, or with
        no time at all, it warns (never blocks); the checklist says a pre-deploy fetch must be live, not --from-dump."""
        self.ready(checkout='shopify')
        shopify = ('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP)
        now = go_live.utc_now().replace(second=0, microsecond=0)

        def stock_warnings(out):
            return [ln for ln in out.split('\n') if ln.startswith('  - stock.js is')]
        # 20 hours old: fresh, and the checklist gives its age
        self.snapshot_stock(fetched=now - go_live.datetime.timedelta(hours=20))
        code, out = self.run_tool(*shopify, '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        self.assertEqual(stock_warnings(out), [])
        todo = out.split('STILL TO DO BY HAND')[1]
        when = now - go_live.datetime.timedelta(hours=20)
        self.assertIn(f'Stock snapshot: stock.js holds Shopify\'s stock for 19 phone(s) as of {when:%Y-%m-%d %H:%M} UTC '
                      '(20 hours ago)', todo)
        self.assertIn('not --from-dump, which only repeats an old copy', todo)
        self.assertIn('Before a deploy it must be a live fetch (--shop-url), not --from-dump', todo)
        # 30 hours old (one or two calendar days, depending on the hour): stale, to the hour
        self.snapshot_stock(fetched=now - go_live.datetime.timedelta(hours=30))
        code, out = self.run_tool(*shopify, '--check-only')
        self.assertEqual(code, 0, out)
        warned = stock_warnings(out)
        self.assertEqual(len(warned), 1, out)
        self.assertIn('(30 hours ago), more than 24 hours old', warned[0])
        self.assertIn(f'fetch_shopify_variants.py --shop-url {SHOP} --write-stock', warned[0])
        # a copy that doesn't say when it was fetched: "time unknown", treated as stale
        self.snapshot_stock(fetched=None)
        self.assertIn('Shopify stock snapshot: time unknown from', read(self.site, 'stock.js'))
        code, out = self.run_tool(*shopify, '--check-only')
        self.assertEqual(code, 0, out)
        warned = stock_warnings(out)
        self.assertEqual(len(warned), 1, out)
        self.assertIn('stock.js is a Shopify stock snapshot with no time on it', warned[0])

    # ------------------------------------------------------------------ R10: Payment Link prices and payment limits
    def test_stripe_checklist_checks_every_buy_now_price(self):
        """A Payment Link charges the price it was made with and nothing here can read it, so the Stripe route's STILL TO
        DO BY HAND list names every link with the site's price (and says to deactivate and clear one for a storage and
        condition stock.js holds none of), says each has a payment limit of 1 (one link per unit), and says to open
        every Buy now button after deploying. The Shopify route has no such item."""
        self.ready()
        set_link(self.site, 'iPhone 13 256GB Good', 'https://buy.stripe.com/test_fullbars_256')   # stock.js holds none
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        todo = out.split('STILL TO DO BY HAND')[1]
        sale = re.search(r'^  \d+\. (Stripe: pay\.js has 2 Payment Link\(s\)\..*)$', todo, re.M)
        self.assertTrue(sale, todo)
        for text in ('One link per unit: each must have "Limit the number of payments" ticked',
                     'and set to 1, with the quantity fixed at 1, so Stripe deactivates it once that payment has completed',
                     'still clear its link in pay.js and lower its count in stock.js',
                     'If you hold another unit of that storage and condition, make a new link for it',
                     'check each Stripe payment against stock.js before dispatch and refund any payment for a phone already sold'):
            self.assertIn(text, sale.group(1))
        for text in ('units you hold', 'switches it off by itself after that sale', 'can\'t take a second payment'):
            self.assertNotIn(text, sale.group(1))
        self.assertNotIn('Deactivate the link in Stripe and clear it in pay.js the moment that phone sells', todo)
        item = re.search(r'^  \d+\. (Stripe prices: .*)$', todo, re.M)
        self.assertTrue(item, todo)
        item = item.group(1)
        for text in ('a Payment Link charges the price it was made with, and nothing here can read it',
                     'Stripe\'s API refuses any request without your API key, which must never be in this repo',
                     'After every deploy, open every Buy now button on the live site and check the Stripe page shows the '
                     'same price as the button, and in Stripe that the link has a payment limit of 1',
                     'iPhone 13 128GB Good (£209), iPhone 13 256GB Good (£239, none held: deactivate and clear it)',
                     'set_prices.py --set', 'set_prices.py --check'):
            self.assertIn(text, item)
        self.assertNotIn('payment limit 0', item)
        self.assertNotIn('units stock.js says you hold', item)
        # the stock item comes before the price check it refers to as "next item"
        self.assertLess(todo.index('Stripe: pay.js has 2'), todo.index('Stock: change stock.js'))
        self.assertLess(todo.index('Stock: change stock.js'), todo.index('Stripe prices: '))
        # set_prices.py --check lists the links too, and go_live.py reads none of that list as a blocker
        self.assertNotIn('PAYMENT LINKS', out)
        # a pay.js set_prices.py can't read in full (here, a comment after a link) is a launch blocker, never a missed link
        good = read(self.site, 'pay.js')
        edit(self.site, 'pay.js', '"https://buy.stripe.com/test_fullbars_256",', '"https://buy.stripe.com/test_fullbars_256", // 0 held')
        found = go_live.run_set_prices_check(self.site)
        self.assertTrue(any(f.startswith('set_prices.py: needs a hand edit: pay.js isn\'t laid out the way this tool reads it')
                            and 'pay.js line ' in f for f in found), found)
        write(self.site, 'pay.js', good)
        edit(self.site, 'products/iphone-13.html', '&quot;Good&quot;:209}', '&quot;Good&quot;:199}')   # a hand edit
        found = go_live.run_set_prices_check(self.site)
        self.assertTrue(found and all('PAYMENT LINKS' not in f and 'buy.stripe.com' not in f for f in found), found)
        # Shopify route: no Payment Links, so no such item (on a fresh copy)
        self.tearDown()
        self.setUp()
        self.ready(checkout='shopify')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--shop-url', SHOP, '--dry-run')
        self.assertEqual(code, 0, out[-3000:])
        self.assertNotIn('Stripe prices:', out)
        self.assertNotIn('Limit the number of payments', out)

    def test_payment_link_docs_say_how_links_are_priced_and_limited(self):
        """GO-LIVE.md and pay.js's header: each link at the site's price, one link per unit with a payment limit of 1 so
        Stripe deactivates it once that payment has completed (and no more than the docs say: a checkout already open
        isn't ruled out, so each payment is checked against stock.js), quantity fixed at 1, still cleared from pay.js and
        stock.js after a sale; a price change needs a new link; automatic tax off under the margin scheme; pay.js kept
        one entry per line; section 7 checks every Buy now price after deploying. Section 1 no longer says links are
        switched off by hand."""
        with open(GOLIVE, encoding='utf-8') as fh:
            md = fh.read()
        self.assertNotIn('switched off by hand', md)
        decide = md.split('## 1. Decide first')[1].split('\n2. **VAT')[0]
        for text in ('"Limit the number of payments" set to 1', 'Stripe deactivates it once that payment has completed',
                     'check each payment against `stock.js` before dispatch',
                     'you still clear the link from `pay.js` and lower `stock.js` by hand',
                     'a Payment Link charges the price it was made with', '`set_prices.py` lists them'):
            self.assertIn(text, decide)
        prices = md.split('6. **Prices.**')[1].split('7. **Trade-in prices**')[0]
        self.assertIn('a Payment Link in `pay.js` for a price you changed', prices)
        self.assertIn('**Static route, once `pay.js` has Payment Links:**', prices)
        step1 = md.split('## 6. If you stay on the static site')[1].split('\n2. **`stock.js`')[0]
        for text in ('exactly the site\'s price for that storage and condition, VAT included',
                     'A Stripe price\'s amount can\'t be changed', 'keep the quantity fixed at 1',
                     'tick **Limit the number of payments** and enter 1', 'deactivates the link by itself once that '
                     'payment has completed', 'check each Stripe payment against `stock.js` before dispatch, and refund '
                     'any payment for a phone already sold', 'leave Stripe\'s automatic tax off', '**Layout.**',
                     'make a new link for it (same price and settings, payment limit 1)',
                     'still clear its entry in `pay.js` and lower its count in `stock.js`', '`set_prices.py --set`',
                     '`set_prices.py --check` lists every link', 'Stripe\'s API refuses any request without your API key',
                     'Stripe adds VAT on top of the site\'s price'):
            self.assertIn(text, step1)
        launch = md.split('## 7. Launch day switches')[1].split('**Sources.**')[0]
        line = launch.split('- [ ] **Static route: every Buy now charges the site\'s price.**')[1].split('\n')[0]
        for text in ('open every Buy now button on the live site', 'The Stripe page must show the same price as the button',
                     '"Limit the number of payments" ticked, set to 1', 'Nothing in this folder can check it for you'):
            self.assertIn(text, line)
        for text in ('so it can\'t take a second payment', 'units you hold for that storage and condition',
                     'lower the link\'s limit', 'Stripe switches it off after that sale', 'payment limit it should have'):
            self.assertNotIn(text, md)
        sources = md.split('**Sources.**')[1]
        for url in ('https://docs.stripe.com/payment-links/customize', 'https://docs.stripe.com/products-prices/manage-prices',
                    'https://docs.stripe.com/api/authentication'):
            self.assertIn(url, sources)
        self.assertIn('checked only through search results', sources.split('docs.stripe.com/payment-links/customize')[1])
        with open(os.path.join(SITE, 'pay.js'), encoding='utf-8') as fh:
            pay = fh.read()
        header = pay[:pay.index('window.FULLBARS_PAY')]
        self.assertNotIn('limit quantity to 1', header)
        for text in ('exactly the site\'s price', 'A Stripe price can\'t be changed', 'set_prices.py --set',
                     'keep the quantity fixed at 1', 'ONE LINK PER UNIT', '\'Limit the number of payments\' and enter 1',
                     'deactivates the link once that payment has completed',
                     'check each Stripe payment against stock.js before dispatch, and refund any payment for a phone already sold',
                     'VAT margin scheme', 'leave Stripe\'s automatic tax off', 'LAYOUT: keep one entry per line',
                     'still clear its link here and lower its count in stock.js',
                     'check Stripe\'s page shows the same price as the button'):
            self.assertIn(text, ' '.join(header.split()), text)
        for text in ('so it can\'t take a second payment', 'lower the link\'s limit', 'the units you hold'):
            self.assertNotIn(text, ' '.join(header.split()), text)
        # the header is a comment: every entry is still read, and still empty in the preview
        self.assertEqual(len(go_live.pay_links(pay)), 183)
        self.assertFalse([k for k, v in go_live.pay_links(pay) if v])


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
                f'<a class="btn" id="orderBtn" href="{SHOP}/products/x">Choose and pay on the next page</a>')
        files = {'products/x.html': good, 'robots.txt': 'User-agent: *\nAllow: /\n'}
        self.assertEqual(go_live.verify(files, opt, 'www.fullbars.co.uk', None), [])
        # a bare Shopify product link (no variant ID) that reads "Order" beside our price is caught
        files['products/x.html'] = good.replace('Choose and pay on the next page</a>', 'Order</a>')
        self.assertIn('opens Shopify on its own first variant but reads "Order"',
                      ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        files['products/x.html'] = good.replace(f'href="{SHOP}/products/x"', 'href="../contact.html"')
        self.assertIn('Order link goes to ../contact.html', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        files['products/x.html'] = good.replace('/products/x"', '/products/y"', 1)
        self.assertIn('data-shop is', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        files['contact.html'] = head + '<form id="contactForm"><select id="cTopic"><option>Order a phone</option></select></form>'
        self.assertIn('still has the "Order a phone" topic', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))
        opt.checkout = 'stripe'
        files['products/x.html'] = good
        self.assertIn('data-shop is still on the page', ' '.join(go_live.verify(files, opt, 'www.fullbars.co.uk', None)))

    def test_read_stock_js(self):
        src = ('/* example: window.FULLBARS_STOCK = {"x": {}}; */\nwindow.FULLBARS_STOCK = {\n  // held\n'
               '  "iphone-13": {"128GB|Good": 2,},\n  "pixel-8": {},\n};\n')
        self.assertEqual(go_live.read_stock_js({'stock.js': src}), ({'iphone-13': {'128GB|Good': 2}, 'pixel-8': {}}, []))
        self.assertEqual(go_live.read_stock_js({}), (None, []))
        with open(os.path.join(SITE, 'stock.js'), encoding='utf-8') as fh:
            self.assertEqual(go_live.read_stock_js({'stock.js': fh.read()}), ({}, []))   # the preview's: empty
        for bad in ('var x = 1;', 'window.FULLBARS_STOCK = [];', 'window.FULLBARS_STOCK = {"a": Infinity};',
                    '/* note\nwindow.FULLBARS_STOCK = {};',
                    # an object holding only a comma: browsers refuse it (a "trailing" comma needs an entry before it)
                    'window.FULLBARS_STOCK = {,};', 'window.FULLBARS_STOCK = {\n ,\n };', 'window.FULLBARS_STOCK = {"a": {,}};',
                    'window.FULLBARS_STOCK = {"a": { , }};', 'window.FULLBARS_STOCK = {"a": {/* sold */,}};',
                    'window.FULLBARS_STOCK = {"a": {"x|y": 1,,}};', 'window.FULLBARS_STOCK = {"a": [,]};',
                    # let and const don't put it on window: site.js would find no stock
                    'let FULLBARS_STOCK = {};', 'const FULLBARS_STOCK = {};',
                    # deliberately refused although browsers run them (see read_stock_js)
                    '<!-- note\nwindow.FULLBARS_STOCK = {};', 'window.FULLBARS_STOCK = {"a": {"x|y": 0x2}};',
                    'window.FULLBARS_STOCK = {};\nwindow.FULLBARS_STOCK = {};', "window.FULLBARS_STOCK = {'a': {}};",
                    'self.FULLBARS_STOCK = {};', 'varFULLBARS_STOCK = {};'):
            self.assertTrue(go_live.read_stock_js({'stock.js': bad})[1], bad)
        self.assertIn('makes a variable browsers don\'t put on window', go_live.read_stock_js({'stock.js': 'let FULLBARS_STOCK = {};'})[1][0])
        # the other spellings of the assignment that browsers run the same way are read
        for good in ('window["FULLBARS_STOCK"] = {"a": {}};', "window['FULLBARS_STOCK'] = {\"a\": {}};",
                     'window . FULLBARS_STOCK = {"a": {}};', 'FULLBARS_STOCK = {"a": {}};', 'var FULLBARS_STOCK = {"a": {}};',
                     ';\nwindow.FULLBARS_STOCK = {"a": {},};;', 'window.FULLBARS_STOCK = {"a": {"x|y": 1,},};'):
            self.assertEqual(go_live.read_stock_js({'stock.js': good})[0], {'a': {'x|y': 1}} if 'x|y' in good else {'a': {}}, good)

    def test_variant_helpers(self):
        self.assertEqual([go_live.variant_id(v) for v in (44012345678901, '44012345678901', ' 7 ', 0, -1, 1.5, True, 'abc', '01', None)],
                         ['44012345678901', '44012345678901', '7', None, None, None, None, None, None, None])
        with open(os.path.join(SITE, 'products', 'iphone-13.html'), encoding='utf-8') as fh:
            src = fh.read()
        self.assertEqual(go_live.picker_default(src), '128GB|Very Good|Blue')
        self.assertEqual(go_live.picker_colours(src), ['Blue', 'Midnight', 'Starlight', 'Pink', 'Green', 'Red'])
        self.assertEqual(go_live.shop_href(SHOP + '/products/iphone-13', {'128GB|Very Good|Blue': '9'}, src),
                         SHOP + '/products/iphone-13?variant=9')
        self.assertEqual(go_live.shop_href(SHOP + '/products/iphone-13', {}, src), SHOP + '/products/iphone-13')
        self.assertTrue(go_live.loads_stock_js(src))
        self.assertFalse(go_live.loads_stock_js('<script src="site.js"></script><script src="stock.js"></script>'))

    def test_order_cant_be_seen_online_pattern(self):
        rx = go_live.CHECKOUT_WORDS
        old = 'We keep a record of your order, but you can&rsquo;t view it on our website; our confirmation email'
        for hit in (old, 'You cannot see your order on this site.', "you can't view it on our website"):
            self.assertTrue(rx['shopify'].search(hit), hit)
            self.assertFalse(rx['stripe-buy-now'].search(hit), hit)   # true for email orders and Payment Links
        with open(os.path.join(SITE, 'terms.html'), encoding='utf-8') as fh:
            terms = fh.read()
        sec3 = terms.split('<h2>3. Ordering and when the contract is made</h2>')[1].split('<h2>4.')[0]
        para = sec3.split('If you buy online')[1]
        self.assertIsNone(rx['shopify'].search(para))

    def test_replaced_part_email_order_is_true_on_shopify(self):
        """Shopify route: "replaced-part phones are sold by email order" isn't checkout wording; a Buy now beside it is."""
        opt = type('O', (), {'checkout': 'shopify', 'trade_ins': 'closed'})()

        def listed(sentence, own=()):
            left = go_live.leftovers({'x.html': f'<p>{sentence}</p>'}, opt, own=own)
            return [k for cat in ('checkout', 'checkout-hand') for k in left.get(cat, {})], list(left.get('checkout-own', {}))
        for ok in ('Phones with any replaced part are sold by email order only, so you always hear about it before paying.',
                   'Phones with any replaced part are sold by email order only: ask us about one through the contact page.',
                   'If a part has been replaced, we sell that phone by email order only.'):
            self.assertEqual(listed(ok), ([], []), ok)
        for bad in ('Phones with any replaced part are sold by email order only, never through a Buy now button.',
                    'If you order by email, we’ll reply with a payment link.',
                    'Phones with a replaced part are sold through Stripe.'):
            self.assertEqual(listed(bad)[0], [bad], bad)
        # wording Ash wrote himself: shown, never listed for rewriting
        mine = 'You can also order by email if you prefer.'
        self.assertEqual(listed(mine, own=[mine]), ([], [mine]))
        self.assertEqual(listed(mine, own=['Something else.'])[0], [mine])

    def test_golive_md_shopify_prices_and_stock(self):
        """GO-LIVE.md: on Shopify, prices change in Shopify admin in the same sitting as set_prices.py (never by importing
        the CSV again), a clean price check comes before every deploy, and the stock snapshot is fetched again and deployed
        whenever stock changes, at least daily; stock.js's header says the same."""
        with open(GOLIVE, encoding='utf-8') as fh:
            md = fh.read()
        prices = md.split('6. **Prices.**')[1].split('7. **Trade-in prices**')[0]
        for text in ('Bulk edit', 'In the same sitting', 'Never import the CSV again to change a price', '--check-prices',
                     '"Price check: passed"', 'Then deploy the site'):
            self.assertIn(text, prices)
        launch = md.split('## 7. Launch day switches')[1].split('**Sources.**')[0]
        self.assertIn('**Shopify route: a clean price check, and a fresh stock snapshot, before every deploy.**', launch)
        self.assertIn("don't deploy until it passes", launch)
        self.assertIn('It must be a live fetch, run just before you deploy, with `--shop-url` as here: not `--from-dump`', launch)
        step13 = md.split('13. **Variant IDs')[1].split('## 6.')[0]
        dump = step13.split('`--save-dump ~/shopify-products.json`')[1]
        for text in ('**It is never a live check.**', 'carries the copy\'s fetch time, not the time you ran it',
                     'never ends "Price check: passed"', 'Before a deploy, fetch live with `--shop-url`'):
            self.assertIn(text, dump)
        self.assertIn('more than 24 hours old (to the minute', step13)
        self.assertNotIn('more than a day old', md)
        stock4 = md.split('## 4. Pictures and stock')[1].split('- **Replaced parts.**')[0]
        for part in (step13, stock4):
            self.assertIn('--write-stock', part)
            self.assertRegex(part, r'[Ff]etch again and deploy (?:the site )?whenever stock changes in Shopify, straight after '
                                   r'you add stock,? and at least daily')
        self.assertIn('a phone added since shows "Not in stock — ask us"', step13)   # stale both ways, said precisely
        self.assertIn('never sell a phone Shopify doesn\'t have', step13)
        self.assertNotIn('only ever shows more stock', md)
        after = md.split('**After any edit to the site**')[1]
        self.assertIn('--check-prices', after)
        with open(os.path.join(SITE, 'stock.js'), encoding='utf-8') as fh:
            header = fh.read()
        self.assertNotIn('leave this empty', header)
        for text in ('fetch_shopify_variants.py --write-stock', 'straight after you add stock, and at least daily',
                     'a phone sold since still shows as in stock', 'a phone\n   added since shows "Not in stock — ask us"'):
            self.assertIn(text, header)

    def test_docs_say_to_check_stock_js_after_every_edit(self):
        """R12: GO-LIVE.md section 6 step 2, the "After any edit" line and stock.js's header all say to run
        set_prices.py --check after every stock edit and before every deploy, and what the fail-closed pages look like
        if you forget; section 6 step 1 turns on Stripe's receipts and the confirmation-page message."""
        with open(GOLIVE, encoding='utf-8') as fh:
            md = fh.read()
        step2 = md.split('\n2. **`stock.js`: edit this file only.**')[1].split('\n3. **Order button')[0]
        for text in ('After every edit, and again just before every deploy, run `python3 launch/full-bars/set_prices.py '
                     '--check sites/full-bars`', '`go_live.py ... --checkout stripe --check-only` runs the same stock check',
                     'a stray comma, a missing brace', 'If you forget and a broken `stock.js` goes up, the live pages fail closed',
                     '"Not in stock — ask us" on every option and "None in stock right now" on its cards, nothing offers '
                     'Order or Buy now', '"Full Bars: stock.js ..."'):
            self.assertIn(text, step2)
        after = md.split('**After any edit to the site**')[1].split('\n')[0]
        for text in ('(`stock.js` included), and again just before every deploy', 'set_prices.py --check',
                     'check_site_facts.py', 'fail closed'):
            self.assertIn(text, after)
        step1 = md.split('## 6. If you stay on the static site')[1].split('\n2. **`stock.js`')[0]
        for text in ('Settings > Business > Customer emails', '**Successful payments**', '**After the payment**',
                     '**Confirmation page**', 'within one working day'):
            self.assertIn(text, step1)
        with open(os.path.join(SITE, 'stock.js'), encoding='utf-8') as fh:
            header = fh.read()
        for text in ('After\n   every edit, and again just before every deploy, run python3 launch/full-bars/set_prices.py --check',
                     'fail closed', 'every phone shows "Not in stock — ask us" and "None in stock right now"', 'Full Bars: stock.js'):
            self.assertIn(text, header)

    def test_stock_snapshot_line(self):
        js = ('/* header */\n/* Shopify stock snapshot: 2026-10-13 09:05 UTC from https://shop.example (19 phones), written by '
              'fetch_shopify_variants.py --write-stock. */\nwindow.FULLBARS_STOCK = {\n};\n')
        utc = go_live.datetime.timezone.utc
        snap = go_live.stock_snapshot(js)
        self.assertEqual(snap, (go_live.datetime.datetime(2026, 10, 13, 9, 5, tzinfo=utc), 'https://shop.example', 19))
        self.assertEqual((snap.shop, snap.phones), ('https://shop.example', 19))
        self.assertEqual(go_live.read_stock_js({'stock.js': js}), ({}, []))
        self.assertIsNone(go_live.stock_snapshot('window.FULLBARS_STOCK = {};'))
        # a time that isn't real, or "time unknown": a snapshot of unknown age, which counts as stale
        self.assertEqual(go_live.stock_snapshot(js.replace('2026-10-13', '2026-13-45')), (None, 'https://shop.example', 19))
        unknown = js.replace('2026-10-13 09:05 UTC', 'time unknown')
        self.assertEqual(go_live.stock_snapshot(unknown), (None, 'https://shop.example', 19))
        self.assertEqual(go_live.read_stock_js({'stock.js': unknown}), ({}, []))

    def test_snapshot_staleness_in_hours(self):
        """Stale means more than 24 hours old, to the minute and in UTC (not calendar days): 23h59m is fresh, 24h01m is
        stale, 47h30m is stale even though it is only "2 days" by date. Unknown or future times count as stale."""
        dt, utc = go_live.datetime, go_live.datetime.timezone.utc
        now = dt.datetime(2026, 10, 13, 17, 0, tzinfo=utc)

        def warn(when):
            return go_live.snapshot_age_warning(go_live.Snapshot(when, 'https://shop.example', 19), 'CMD', now)
        for when in (now, now - dt.timedelta(hours=23, minutes=59), dt.datetime(2026, 10, 12, 17, 0, tzinfo=utc),
                     now + dt.timedelta(minutes=5)):   # a clock a few minutes fast is not "the future"
            self.assertIsNone(warn(when), when)
        # the old check (calendar days, local date) let all of these through
        self.assertIn('from 2026-10-12 16:59 UTC (24 hours ago), more than 24 hours old', warn(dt.datetime(2026, 10, 12, 16, 59, tzinfo=utc)))
        self.assertIn('from 2026-10-11 17:30 UTC (47 hours ago)', warn(dt.datetime(2026, 10, 11, 17, 30, tzinfo=utc)))
        self.assertIn('from 2026-09-01 09:00 UTC (42 days ago)', warn(dt.datetime(2026, 9, 1, 9, 0, tzinfo=utc)))
        self.assertIn('with no time on it', warn(None))
        self.assertIn('dated 2026-10-14 17:00 UTC, which is in the future', warn(now + dt.timedelta(days=1)))
        for w in (warn(None), warn(now - dt.timedelta(days=3)), warn(now + dt.timedelta(days=1))):
            self.assertIn('Fetch it again from the live store and deploy the site (at least daily): CMD', w)
        self.assertEqual([go_live.age_words(now - d, now) for d in (dt.timedelta(minutes=59), dt.timedelta(hours=1),
                                                                     dt.timedelta(hours=47, minutes=59), dt.timedelta(days=2))],
                         ['less than an hour ago', '1 hour ago', '47 hours ago', '2 days ago'])

    def test_buy_now_patterns(self):
        rx = go_live.CHECKOUT_WORDS['stripe-buy-now']
        for hit in ('subject to stock; we confirm before you pay', 'and confirmed before you pay',
                    'ask when you order and we’ll send them before you pay', 'Ask when you order.',
                    'Ask and we’ll send photos of the exact phone before you pay', 'through Stripe, our intended payment provider'):
            self.assertTrue(rx.search(hit), hit)
        for miss in ('If a part has been replaced, we tell you before you pay.', 'subject to stock; confirmed by email',
                     'ask us before you order and we’ll send them.', 'Ask us before you order.'):
            self.assertFalse(rx.search(miss), miss)
        self.assertTrue(go_live.EMAIL_ORDER_ONLY.search('On an email order we confirm the colour and grade before you pay'))

    def test_parse_domain(self):
        self.assertEqual(go_live.parse_domain('https://www.FullBars.co.uk/', False), ('fullbars.co.uk', 'www.fullbars.co.uk'))
        self.assertEqual(go_live.parse_domain('fullbars.co.uk', True), ('fullbars.co.uk', 'fullbars.co.uk'))
        with self.assertRaises(go_live.Fail):
            go_live.parse_domain('full bars', False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
