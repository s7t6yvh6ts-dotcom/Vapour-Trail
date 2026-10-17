#!/usr/bin/env python3
"""Browser tests for sites/chainline/index.html, in headless Chromium (Playwright for Node).

What they pin down:
  - with JavaScript off, all the bikes and their prices show, the size chart has its rows, and no control that needs a
    script is shown;
  - the cards the script draws are exactly the cards in the HTML (sync_bikes.py and the page's script agree);
  - the filters and size-finder choices live in the address: a reload, and Back after leaving the page, show the same
    bikes, the same controls and the same answer; unknown values in the address are dropped;
  - the basket: add, the count, UK delivery and its total, remove (with focus moving on), and the e-bike courier note;
  - the forms: an empty send shows a message on every missing field, flags it for screen readers and focuses the first;
    nothing is ever sent (no request, the address doesn't change); a complete send shows the prototype reply;
  - in an iframe with sandbox="allow-scripts" (as in a claude.ai artifact, where storage and the clipboard are refused)
    every feature works and nothing throws;
  - a slow font server holds up the load event, and the page doesn't redraw itself then: focus and a half-typed height
    stay as the visitor left them;
  - Back restored from the back/forward cache shows the same state, and picks up a basket change made in another tab
    (needs full Chromium with the cache allowed; that case reports itself skipped if it can't launch);
  - unwrapped for the artifact (no <html lang>), the page still sets lang="en-GB";
  - a deep link into the small print still lands below the sticky header when the fonts arrive late.

The page is served from a temporary copy over http on a free local port; Google Fonts requests get an empty
stylesheet, so no network is needed. Skipped if Node or its playwright package isn't installed.
Run from launch/chainline:  python3 -m unittest discover -s tests
"""
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
# CHAINLINE_SITE points the tests at another copy of the site folder (for example a copy you're about to publish).
SITE = os.environ.get('CHAINLINE_SITE') or os.path.join(REPO, 'sites', 'chainline')
NODE = shutil.which('node') or '/opt/node22/bin/node'
NODE_PATH = os.environ.get('NODE_PATH') or '/opt/node22/lib/node_modules'

DRIVER = r"""
const { chromium } = require('playwright');
const BASE = process.argv[2];
const FONT_CSS = "@font-face{font-family:'Barlow Condensed';font-weight:700;src:local('Arial Black')}";
const out = {};
const errors = [];
async function ctxFor(browser, opts = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', ...opts });
  await ctx.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
  // every frame, sandboxed ones included, reports uncaught errors to the console
  await ctx.addInitScript(() => {
    window.addEventListener('error', (e) => console.error('UNCAUGHT ' + e.message));
    window.addEventListener('unhandledrejection', (e) => console.error('UNHANDLED ' + (e.reason && e.reason.message || e.reason)));
  });
  return ctx;
}
function watch(page, tag) {
  page.on('pageerror', (e) => errors.push(tag + ' pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(tag + ' console: ' + m.text()); });
}
const snap = (f) => f.evaluate(() => ({
  search: location.search,
  chips: [...document.querySelectorAll('.chip[aria-pressed=true]')].map((c) => c.dataset.type).join(','),
  size: document.querySelector('#filter-size').value, sort: document.querySelector('#sort').value,
  count: document.querySelector('#result-count').textContent,
  ids: [...document.querySelectorAll('#bike-grid > li')].map((l) => l.id).join(','),
  prices: [...document.querySelectorAll('#bike-grid .price')].map((p) => p.textContent).join(' '),
  fit: document.querySelector('input[name=sf-type]:checked').value, unit: document.querySelector('input[name=sf-unit]:checked').value,
  ftShown: !document.querySelector('#sf-ft-wrap').hidden, cmShown: !document.querySelector('#sf-cm-wrap').hidden,
  cm: document.querySelector('#sf-cm').value, ft: document.querySelector('#sf-ft').value, inch: document.querySelector('#sf-in').value,
  answer: document.querySelector('#sf-size').textContent + ' ' + document.querySelector('#sf-detail').textContent,
  caption: document.querySelector('#sf-caption').textContent,
}));
async function setFilters(page) {
  await page.click('#chip-hybrid'); await page.click('#chip-ebike');
  await page.selectOption('#filter-size', 'M'); await page.selectOption('#sort', 'high');
  await page.click('label[for=sf-type-road]'); await page.click('label[for=sf-unit-ft]');
  await page.fill('#sf-ft', '6'); await page.fill('#sf-in', '1');
}
(async () => {
  const browser = await chromium.launch();
  // 1. JavaScript off
  {
    const ctx = await ctxFor(browser, { javaScriptEnabled: false });
    const page = await ctx.newPage(); watch(page, 'nojs');
    await page.goto(BASE + 'index.html');
    out.nojs = await page.evaluate(() => {
      const shown = (s) => [...document.querySelectorAll(s)].filter((e) => e.getClientRects().length > 0).length;
      return { html: document.documentElement.className, cards: shown('#bike-grid > li'),
        prices: [...document.querySelectorAll('#bike-grid .price')].map((p) => p.textContent),
        chartRows: shown('#sf-rows tr'), navLinks: shown('#site-nav a'),
        scriptControls: shown('.js-only, #menu-toggle, #basket-open, [data-add], .chip, #filter-size, #book, #sell-form, [data-copy]'),
        grid: document.querySelector('#bike-grid').innerHTML };
    });
    await ctx.close();
  }
  // 2-5. JavaScript on: markup, reload, Back, junk in the address
  {
    const ctx = await ctxFor(browser);
    const page = await ctx.newPage(); watch(page, 'js');
    await page.goto(BASE + 'index.html');
    out.jsGrid = await page.evaluate(() => document.querySelector('#bike-grid').innerHTML);
    out.data = await page.evaluate(() => JSON.parse(document.querySelector('#shop-data').textContent));
    await setFilters(page);
    out.before = await snap(page);
    await page.reload();
    out.reloaded = await snap(page);
    await page.goto(BASE + 'other.html');
    await page.goBack();
    await page.waitForTimeout(300);
    out.back = await snap(page);
    await page.goto(BASE + 'index.html?type=road,nonsense,constructor&size=M|<b>&sort=evil&fit=__proto__&unit=yards&h=9999&keep=1#faq');
    out.junk = await snap(page);
    out.junkHash = await page.evaluate(() => location.hash);
    await page.goto(BASE + 'index.html?type=kids&size=XXL');
    out.empty = await page.evaluate(() => ({ shown: !document.querySelector('#shop-empty').hidden, link: !!document.querySelector('#shop-empty a[href="#contact"]') }));
    await ctx.close();
  }
  // 6. basket
  {
    const ctx = await ctxFor(browser);
    const page = await ctx.newPage(); watch(page, 'basket');
    await page.goto(BASE + 'index.html');
    await page.click('#bike-fx2-2021 [data-add]');
    await page.click('#bike-motus-2021 [data-add]');
    const b = {};
    b.badge = await page.textContent('#basket-count');
    b.buttonName = await page.evaluate(() => document.querySelector('#basket-open').textContent.replace(/\s+/g, ' ').trim());
    b.inBasketLabel = await page.textContent('#bike-fx2-2021 [data-add]');
    await page.click('#basket-open'); await page.waitForTimeout(100);
    b.open = await page.evaluate(() => document.querySelector('#basket').classList.contains('open'));
    await page.check('#del-uk');
    b.sub = await page.textContent('#t-sub'); b.del = await page.textContent('#t-del'); b.total = await page.textContent('#t-total');
    b.ebikeNote = await page.evaluate(() => !document.querySelector('#ebike-note').hidden && document.querySelector('#ebike-note').textContent);
    await page.click('[data-remove="motus-2021"]');
    b.afterRemove = { badge: await page.textContent('#basket-count'), focus: await page.evaluate(() => document.activeElement.getAttribute('data-remove')),
      total: await page.textContent('#t-total'), noteHidden: await page.evaluate(() => document.querySelector('#ebike-note').hidden) };
    await page.keyboard.press('Escape');
    await page.reload();
    b.afterReload = await page.textContent('#basket-count');
    out.basket = b;
    await ctx.close();
  }
  // 7. forms
  {
    const ctx = await ctxFor(browser);
    const page = await ctx.newPage(); watch(page, 'forms');
    const requests = [];
    await page.goto(BASE + 'index.html');
    page.on('request', (r) => { if (!/fonts\.(googleapis|gstatic)/.test(r.url())) requests.push(r.method() + ' ' + r.url()); });
    const url0 = page.url();
    await page.click('#bk-submit');
    const f = {};
    f.book = await page.evaluate(() => ({ focus: document.activeElement.id,
      invalid: [...document.querySelectorAll('#book [aria-invalid=true]')].map((e) => e.id),
      described: [...document.querySelectorAll('#book [aria-invalid=true]')].every((e) => (e.getAttribute('aria-describedby') || '').split(' ').some((id) => { const el = document.getElementById(id); return el && el.classList.contains('field-error') && el.textContent.length > 5; })),
      result: document.querySelector('#book-result').textContent }));
    await page.fill('#bk-name', 'Sam Rider');
    f.cleared = await page.evaluate(() => !document.querySelector('#bk-name').hasAttribute('aria-invalid') && !document.querySelector('#bk-name-error'));
    await page.fill('#bk-phone', '07700 900123'); await page.fill('#bk-bike', 'Trek FX 2'); await page.selectOption('#bk-service', 'standard');
    await page.evaluate(() => { const d = document.querySelector('#bk-date'); d.value = d.min; });
    await page.press('#bk-bike', 'Enter');
    f.booked = await page.textContent('#book-result');
    await page.click('#sl-submit');
    f.sell = await page.evaluate(() => ({ focus: document.activeElement.id, invalid: [...document.querySelectorAll('#sell-form [aria-invalid=true]')].map((e) => e.id) }));
    await page.fill('#sl-name', 'Sam'); await page.fill('#sl-email', 'sam@example'); await page.fill('#sl-make', 'Raleigh'); await page.fill('#sl-model', 'Chopper');
    await page.fill('#sl-year', '1975'); await page.selectOption('#sl-condition', { index: 3 });
    await page.click('#sl-submit');
    f.badEmail = await page.evaluate(() => document.activeElement.id + ' / ' + ((document.querySelector('#sl-email-error') || {}).textContent || ''));
    await page.fill('#sl-email', 'sam@example.co.uk');
    await page.click('#sl-submit');
    f.offered = await page.textContent('#sell-result');
    f.requests = requests; f.urlUnchanged = page.url() === url0;
    out.forms = f;
    await ctx.close();
  }
  // 8. sandboxed iframe, as in a claude.ai artifact
  {
    const ctx = await ctxFor(browser);
    const page = await ctx.newPage(); watch(page, 'sandbox');
    await page.goto(BASE + 'frame.html');
    await page.waitForTimeout(500);
    const f = page.frames().find((fr) => fr.url().includes('index.html'));
    const s = {};
    s.storageThrows = await f.evaluate(() => { try { localStorage.getItem('x'); return false; } catch (e) { return true; } });
    await f.click('#chip-hybrid'); await f.selectOption('#filter-size', 'M');
    s.filtered = await f.textContent('#result-count');
    await f.click('label[for=sf-type-hybrid]'); await f.fill('#sf-cm', '180');
    await f.click('#sf-show');
    s.finder = await f.textContent('#result-count');
    await f.evaluate(() => document.querySelector('#bike-grid [data-add]').click());
    await f.evaluate(() => document.querySelector('#basket-open').click()); await page.waitForTimeout(100);
    await f.click('#checkout');
    s.checkout = await f.textContent('#checkout-msg');
    await f.evaluate(() => document.querySelector('#basket-close').click());
    await f.click('#bk-submit');
    s.bookErrors = await f.evaluate(() => document.querySelectorAll('#book .field-error').length);
    await f.evaluate(() => document.querySelector('.site-footer').scrollIntoView());
    await f.click('[data-copy="contact-email"]'); await page.waitForTimeout(100);
    s.copy = await f.textContent('[data-copy="contact-email"] .copy-label');
    await f.click('.footer-links a[href="#privacy"]');
    s.privacyOpen = await f.evaluate(() => document.querySelector('#privacy').open);
    out.sandbox = s;
    await ctx.close();
  }
  // 9. a slow font server: the load event waits for it, and the page must not redraw itself then
  {
    const ctx = await ctxFor(browser);
    await ctx.unroute(/fonts\.(googleapis|gstatic)\.com/);
    await ctx.route(/fonts\.(googleapis|gstatic)\.com/, async (r) => { await new Promise((ok) => setTimeout(ok, 2500)); r.fulfill({ status: 200, contentType: 'text/css', body: FONT_CSS }); });
    const page = await ctx.newPage(); watch(page, 'slowfonts');
    await page.goto(BASE + 'index.html', { waitUntil: 'domcontentloaded' });
    await page.click('label[for=sf-unit-ft]'); await page.fill('#sf-ft', '6'); await page.fill('#sf-in', '');
    await page.focus('#bike-fx2-2021 [data-add]');
    const loadedEarly = await page.evaluate(() => document.readyState === 'complete');
    await page.waitForLoadState('load'); await page.waitForTimeout(300);
    out.slowFonts = await page.evaluate(() => ({ unit: document.querySelector('input[name=sf-unit]:checked').value, ft: document.querySelector('#sf-ft').value,
      inch: document.querySelector('#sf-in').value, focus: document.activeElement.getAttribute('data-add') }));
    out.slowFonts.loadedEarly = loadedEarly;
    await ctx.close();
  }
  // 10. Back from the back/forward cache
  {
    let full = null;
    try { full = await chromium.launch({ channel: 'chromium', ignoreDefaultArgs: ['--disable-back-forward-cache'] }); } catch (e) { out.bfcache = { skipped: String(e.message).split('\n')[0] }; }
    if (full) {
      const ctx = await ctxFor(full);
      const page = await ctx.newPage(); watch(page, 'bfcache');
      await page.addInitScript(() => { window.addEventListener('pageshow', (e) => { window.__shows = (window.__shows || []).concat(e.persisted); }); });
      await page.goto(BASE + 'index.html');
      await page.click('#chip-road'); await page.selectOption('#sort', 'high'); await page.click('label[for=sf-type-kids]'); await page.fill('#sf-cm', '118');
      await page.click('#bike-allez-2020 [data-add]');
      const before = await snap(page);
      await page.evaluate(() => { const a = document.createElement('a'); a.href = 'other.html'; a.id = 'go'; a.textContent = 'go'; document.body.prepend(a); });
      await page.click('#go'); await page.waitForURL(/other/);
      const other = await ctx.newPage();
      await other.goto(BASE + 'index.html'); await other.click('#bike-motus-2021 [data-add]'); await other.close();
      await page.goBack({ waitUntil: 'commit' }); await page.waitForTimeout(600);
      out.bfcache = { before, after: await snap(page), shows: await page.evaluate(() => window.__shows), basket: await page.textContent('#basket-count') };
      await page.click('#chip-all');
      out.bfcache.worksAfter = await page.textContent('#result-count');
      await full.close();
    }
  }
  // 11. unwrapped for the artifact: no <html lang>
  {
    const ctx = await ctxFor(browser);
    const page = await ctx.newPage(); watch(page, 'shell');
    await page.goto(BASE + 'shell.html');
    out.shell = await page.evaluate(() => ({ lang: document.documentElement.lang, cards: document.querySelectorAll('#bike-grid > li').length, js: document.documentElement.className }));
    await ctx.close();
  }
  // 12. a deep link with the fonts arriving late (they reflow the page after the browser has scrolled)
  {
    const tops = [];
    for (let i = 0; i < 2; i++) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
      await ctx.route(/fonts\.(googleapis|gstatic)\.com/, async (r) => { await new Promise((ok) => setTimeout(ok, 1200)); r.fulfill({ status: 200, contentType: 'text/css', body: FONT_CSS }); });
      const page = await ctx.newPage(); watch(page, 'deeplink');
      await page.goto(BASE + 'index.html#cancel-form');
      await page.waitForTimeout(2500);
      tops.push(await page.evaluate(() => Math.round(document.getElementById('cancel-form').getBoundingClientRect().top)));
      await ctx.close();
    }
    out.deepLink = tops;
  }
  out.errors = errors;
  await browser.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ crash: String(e && e.stack || e) })); process.exit(0); });
"""

OTHER = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Other</title></head><body><p>Another page</p></body></html>'
FRAME = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Frame</title><style>html,body,iframe{margin:0;border:0;'
         'width:100%;height:100%}</style></head><body><iframe title="Chainline" sandbox="allow-scripts" src="index.html"></iframe></body></html>')


def have_playwright():
    if not os.path.exists(NODE):
        return False
    r = subprocess.run([NODE, '-e', "require('playwright')"], capture_output=True, env={**os.environ, 'NODE_PATH': NODE_PATH})
    return r.returncode == 0


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(have_playwright(), 'Node and its playwright package are needed for the browser tests')
class SiteBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='chainline_browser_')
        shutil.copy(os.path.join(SITE, 'index.html'), cls.tmp)
        page = open(os.path.join(SITE, 'index.html'), encoding='utf-8').read()
        unwrapped = page
        for pat in (r'<!doctype[^>]*>\s*', r'<html[^>]*>\s*', r'\s*</html>\s*$', r'<head>\s*', r'\s*</head>\s*', r'<body[^>]*>\s*', r'\s*</body>'):
            unwrapped = re.sub(pat, '', unwrapped, count=1, flags=re.I)   # as the artifact publisher's bundle does
        shell = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                 '</head><body>' + unwrapped + '</body></html>')
        for name, body in (('other.html', OTHER), ('frame.html', FRAME), ('shell.html', shell)):
            with open(os.path.join(cls.tmp, name), 'w', encoding='utf-8') as f:
                f.write(body)
        with open(os.path.join(cls.tmp, 'driver.cjs'), 'w', encoding='utf-8') as f:
            f.write(DRIVER)
        handler = functools.partial(_Quiet, directory=cls.tmp)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{cls.server.server_address[1]}/'
        r = subprocess.run([NODE, os.path.join(cls.tmp, 'driver.cjs'), base], capture_output=True, text=True, timeout=240,
                           env={**os.environ, 'NODE_PATH': NODE_PATH})
        try:
            cls.out = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            cls.out = {'crash': r.stdout + r.stderr}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.assertNotIn('crash', self.out, self.out.get('crash'))

    def test_no_uncaught_errors_anywhere(self):
        self.assertEqual(self.out['errors'], [])

    def test_bikes_show_with_javascript_off(self):
        n = self.out['nojs']
        self.assertEqual(n['html'], 'no-js')
        prices = sorted('£{:,}'.format(b['price']) for b in self.out['data']['bikes'])
        self.assertEqual(n['cards'], len(prices))
        self.assertEqual(sorted(n['prices']), prices)
        self.assertEqual(n['chartRows'], 4)
        self.assertEqual(n['navLinks'], 5)
        self.assertEqual(n['scriptControls'], 0, 'a control that needs JavaScript is showing with it off')

    def test_script_draws_exactly_the_cards_in_the_html(self):
        self.assertEqual(self.out['jsGrid'], self.out['nojs']['grid'])

    def test_filters_and_finder_survive_a_reload(self):
        before, after = self.out['before'], self.out['reloaded']
        self.assertEqual(before['chips'], 'hybrid,ebike')
        self.assertEqual((before['size'], before['sort'], before['fit'], before['unit']), ('M', 'high', 'road', 'ft'))
        self.assertEqual(before['ids'], 'bike-motus-2021,bike-crossfire-2023,bike-fx2-2021')
        self.assertEqual(after, before)

    def test_back_shows_the_same_state_as_the_screen_had(self):
        self.assertEqual(self.out['back'], self.out['before'])
        b = self.out['back']
        self.assertTrue(b['ftShown'] and not b['cmShown'])
        self.assertEqual((b['ft'], b['inch'], b['answer'], b['caption']), ('6', '1', 'XL 58–60cm frame', 'Road and gravel chart'))

    def test_unknown_values_in_the_address_are_dropped(self):
        j = self.out['junk']
        self.assertEqual((j['chips'], j['size'], j['sort'], j['fit'], j['unit'], j['cm']), ('road', 'all', 'featured', 'hybrid', 'cm', '172'))
        self.assertEqual(j['search'], '?keep=1&type=road')
        self.assertEqual(self.out['junkHash'], '#faq')
        self.assertEqual(self.out['empty'], {'shown': True, 'link': True})

    def test_basket_add_delivery_and_remove(self):
        b = self.out['basket']
        self.assertEqual(b['badge'], '2')
        self.assertEqual(b['buttonName'], 'Basket 2 bikes')
        self.assertEqual(b['inBasketLabel'], 'In basket')
        self.assertTrue(b['open'])
        self.assertEqual(b['sub'], '£1,528')
        # the e-bike courier price isn't set in the preview, so the total says so rather than leaving it out
        self.assertEqual(b['del'], '£39 + £[e-bike delivery price]')
        self.assertEqual(b['total'], '£1,567 + e-bike courier')
        self.assertIn('specialist courier', b['ebikeNote'])
        self.assertEqual(b['afterRemove'], {'badge': '1', 'focus': 'fx2-2021', 'total': '£418', 'noteHidden': True})
        self.assertEqual(b['afterReload'], '1')

    def test_forms_show_errors_and_send_nothing(self):
        f = self.out['forms']
        self.assertEqual(f['book']['focus'], 'bk-name')
        self.assertEqual(f['book']['invalid'], ['bk-name', 'bk-phone', 'bk-bike', 'bk-service', 'bk-date'])
        self.assertTrue(f['book']['described'])
        self.assertEqual(f['book']['result'], '')
        self.assertTrue(f['cleared'])
        self.assertIn("Prototype: requests aren't sent anywhere yet.", f['booked'])
        self.assertEqual(f['sell'], {'focus': 'sl-name', 'invalid': ['sl-name', 'sl-email', 'sl-make', 'sl-model', 'sl-condition']})
        self.assertEqual(f['badEmail'], 'sl-email / Enter an email address like name@example.co.uk.')
        self.assertIn("Prototype: offers aren't sent yet.", f['offered'])
        self.assertIn('1975 Raleigh Chopper', f['offered'])
        self.assertEqual(f['requests'], [])
        self.assertTrue(f['urlUnchanged'])

    def test_everything_works_in_a_sandboxed_iframe(self):
        s = self.out['sandbox']
        self.assertTrue(s['storageThrows'], 'the test frame should refuse storage, as an artifact can')
        self.assertEqual(s['filtered'], '1 bike matches your filters')
        self.assertEqual(s['finder'], '1 bike matches your filters')
        self.assertIn("Payments aren't connected yet.", s['checkout'])
        self.assertEqual(s['bookErrors'], 5)
        self.assertEqual(s['copy'], 'Selected')
        self.assertTrue(s['privacyOpen'])


    def test_a_slow_font_server_doesnt_make_the_page_redraw_itself(self):
        s = self.out['slowFonts']
        self.assertFalse(s['loadedEarly'], 'the font route should hold up the load event, or this test proves nothing')
        self.assertEqual((s['unit'], s['ft'], s['inch'], s['focus']), ('ft', '6', '', 'fx2-2021'))

    def test_back_from_the_back_forward_cache(self):
        b = self.out['bfcache']
        if 'skipped' in b:
            self.skipTest('full Chromium not available: ' + b['skipped'])
        self.assertEqual(b['shows'][-1], True, 'Back should have come from the back/forward cache')
        self.assertEqual(b['after'], b['before'])
        self.assertEqual(b['basket'], '2', 'a bike added in another tab meanwhile should show in the basket')
        self.assertEqual(b['worksAfter'], '10 bikes in stock')

    def test_unwrapped_page_still_says_it_is_in_british_english(self):
        self.assertEqual(self.out['shell'], {'lang': 'en-GB', 'cards': 10, 'js': 'js'})

    def test_a_deep_link_lands_below_the_header_when_fonts_are_late(self):
        for top in self.out['deepLink']:
            self.assertGreaterEqual(top, 66, f'landed at {top}px, under the 65px sticky header')
            self.assertLessEqual(top, 120)


if __name__ == '__main__':
    unittest.main(verbosity=2)
