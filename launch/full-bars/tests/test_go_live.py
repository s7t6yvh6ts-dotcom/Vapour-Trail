#!/usr/bin/env python3
"""Tests for go_live.py, the Full Bars launch-day switch.

Run from the repo root:  python3 launch/full-bars/tests/test_go_live.py
Each test works on a fresh copy of sites/full-bars in a temporary folder (set TMPDIR to choose where).
The real site folder is only ever read. Python 3 standard library only.
"""
import hashlib
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


def ld_blocks(src):
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)]


class GoLiveTest(unittest.TestCase):
    TEMPLATE_KEYS = {}   # trade-ins mode -> the --rewrites-template keys for the ready site (the same for every test)

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

    def template(self, trade_ins='closed'):
        """The keys --rewrites-template writes for this copy, made once per trade-ins mode."""
        if trade_ins not in GoLiveTest.TEMPLATE_KEYS:
            tpl = os.path.join(self.tmp, f'template-{trade_ins}.json')
            code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--trade-ins', trade_ins,
                                      '--dry-run', '--rewrites-template', tpl, rewrites=False)
            self.assertIn(code, (0, 1), out[-2000:])
            with open(tpl, encoding='utf-8') as fh:
                GoLiveTest.TEMPLATE_KEYS[trade_ins] = list(json.load(fh))
        return GoLiveTest.TEMPLATE_KEYS[trade_ins]

    def write_rewrites(self, mapping, name='rewrites.json'):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(mapping, fh, ensure_ascii=False)
        return path

    def fill_rewrites(self, trade_ins='closed', value=lambda i, key: f'Rewritten line {i}.'):
        """A --rewrites file with every template key filled in: Ash's finished wording."""
        self.rw = self.write_rewrites({k: value(i, k) for i, k in enumerate(self.template(trade_ins))}, f'rewrites-{trade_ins}.json')
        return self.rw

    def ready(self, link=True, rewrites=True):
        fill_placeholders(self.site)
        if link:
            set_link(self.site, LINK_KEY, LINK)
        if rewrites:
            self.fill_rewrites()

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
        self.assertNotIn('CHANGES', out)
        self.ready(link=False)
        before = snapshot(self.site)
        # the preview wording is a blocker too, listed sentence by sentence
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--check-only', rewrites=False)
        self.assertEqual(code, 1, out)
        self.assertIn('preview wording would still be on the live pages', out)
        self.assertIn('- Preview prices: we’re not taking orders yet. (33 places)', out)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--check-only', '--allow-preview-wording',
                                  rewrites=False)
        self.assertEqual(code, 3, out)
        self.assertIn('NOT READY TO PUBLISH', out)
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'shopify', '--check-only')
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
        edit(self.site, 'products/iphone-13.html', ' data-preview="1">', ' data-stock="{&quot;128GB|Good&quot;:1," data-preview="1">')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 1, out)
        self.assertIn('data-stock is not valid JSON', out)
        edit(self.site, 'products/iphone-13.html', '1," data-preview', '1,&quot;9TB|Good&quot;:1}" data-preview')
        code, out = self.run_tool('--domain', 'fullbars.co.uk', '--checkout', 'stripe', '--check-only')
        self.assertEqual(code, 0, out)
        self.assertIn('data-stock has keys no option uses', out)

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

    def test_parse_domain(self):
        self.assertEqual(go_live.parse_domain('https://www.FullBars.co.uk/', False), ('fullbars.co.uk', 'www.fullbars.co.uk'))
        self.assertEqual(go_live.parse_domain('fullbars.co.uk', True), ('fullbars.co.uk', 'fullbars.co.uk'))
        with self.assertRaises(go_live.Fail):
            go_live.parse_domain('full bars', False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
