#!/usr/bin/env python3
"""Browser tests for site.js's Order button and contact form, in headless Chromium (Playwright for Node).

What they pin down:
  - preview: the Order control stays the inert "Opening soon" span;
  - static route: data-stock counts any whole number above 0 as held (2 units is in stock), 0 or a missing key is not;
    a Payment Link makes "Buy now";
  - Shopify route (data-shop on #picker): the Order button goes to the Shopify product, and no email-order
    (contact.html?order=) or Payment Link is ever built on the page. With a variant ID for the choice (data-variants) it
    reads "Order — £…" and opens ?variant=<id>; without one it reads "Choose and pay on the next page" and shows the
    hand-off note, never a price;
  - stock.js: it wins over a page's data-stock; a phone it lists with no units gets "None in stock right now" on its
    cards (and a range tile when every phone in the range has none); the card stays; a missing stock.js breaks nothing;
    on the Shopify route a snapshot written by fetch_shopify_variants.py --write-stock turns an option Shopify can't sell
    into "Not in stock — ask us" instead of an Order link to a sold-out variant;
  - with stock data, a page whose ticked storage and condition isn't held opens on the cheapest held one (the first in
    the page's order on a tie), keeping the ticked colour and leaving the address bare; a storage or condition the
    address names is kept, held or not, and only the other one can move; a storage is marked "not in stock" only when
    none of its conditions is held, and "not in this condition" when it's held but not in the chosen condition (the
    price on it is for that condition); a condition is "not in stock" when it isn't held in the chosen storage; the
    "From £…" line says when that cheapest option isn't held; without stock data nothing changes;
  - contact.html ignores ?order= unless the form has the "Order a phone" topic (the static route only).

Pages are opened straight from a temporary copy of the site (file://), so no web server is needed. Skipped if Node
or its playwright package isn't installed. Run from the repo root:  python3 launch/full-bars/tests/test_site_js.py
"""
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
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'full-bars')
NODE = shutil.which('node') or '/opt/node22/bin/node'
NODE_PATH = os.environ.get('NODE_PATH') or '/opt/node22/lib/node_modules'
SHOP_URL = 'https://shop.example/products/iphone-13'
PAY_LINK = 'https://buy.stripe.com/test_fullbars_example'

# For each case: open the page (with an optional query), optionally tick a radio, and report the Order button,
# every href on the page that builds an email order, and the contact form's topic and message.
DRIVER = r"""
const { chromium } = require('playwright');
const cases = JSON.parse(process.argv[2]);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const out = [];
  for (const c of cases) {
    await page.goto(c.url, { waitUntil: 'load' });
    if (c.click) { await page.click(c.click); }
    out.push(await page.evaluate(() => {
      const b = document.getElementById('orderBtn');
      const topic = document.getElementById('cTopic'), msg = document.getElementById('cMsg');
      const h = document.getElementById('handoffNote');
      return {
        tag: b ? b.tagName : null, text: b ? b.textContent : null, href: b ? b.getAttribute('href') : null,
        orderLinks: Array.from(document.querySelectorAll('[href*="?order="]')).map(a => a.getAttribute('href')),
        topic: topic ? topic.value : null, msg: msg ? msg.value : null,
        handoff: h ? !h.hidden && h.offsetParent !== null : null,
        describedBy: b ? b.getAttribute('aria-describedby') : null,
        noneCards: Array.from(document.querySelectorAll('article.card .card-stock')).map(p => p.closest('article').querySelector('a').getAttribute('href') + ': ' + p.textContent),
        noneTiles: Array.from(document.querySelectorAll('a.tile .tile-stock')).map(e => e.closest('a').getAttribute('href') + ': ' + e.textContent),
        cards: document.querySelectorAll('article.card').length,
        hiddenCards: document.querySelectorAll('article.card[hidden]').length,
        na: Array.from(document.querySelectorAll('#picker .opt.na input')).map(i => i.value),
        nacond: Array.from(document.querySelectorAll('#picker .opt.na-cond input')).map(i => i.value),
        from: (document.getElementById('pdFrom') || {}).textContent || null,
        picked: ['storage', 'grade', 'colour'].map(n => { const i = document.querySelector('#picker input[name="' + n + '"]:checked'); return i ? i.value : ''; }).join('|'),
        price: (document.getElementById('pdPrice') || {}).textContent || null,
        search: location.search,
      };
    }));
  }
  await browser.close();
  console.log(JSON.stringify({ out, errors }));
})().catch(e => { console.error(e); process.exit(1); });
"""


def node_ready():
    if not os.path.exists(NODE):
        return False
    r = subprocess.run([NODE, '-e', "require('playwright')"], capture_output=True, text=True,
                       env=dict(os.environ, NODE_PATH=NODE_PATH))
    return r.returncode == 0


@unittest.skipUnless(node_ready(), 'needs Node with the playwright package (and its Chromium)')
class SiteJsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='site_js_test_')
        cls.site = os.path.join(cls.tmp, 'site')
        shutil.copytree(SITE, cls.site, ignore=shutil.ignore_patterns('*.png'))
        cls.driver = os.path.join(cls.tmp, 'driver.cjs')
        with open(cls.driver, 'w', encoding='utf-8') as fh:
            fh.write(DRIVER)
        # a Payment Link for the iPhone 13 128GB Good (as Ash would paste it into pay.js on the static route)
        cls.patch('pay.js', '"iPhone 13 128GB Good": ""', f'"iPhone 13 128GB Good": "{PAY_LINK}"')
        src = cls.read('products/iphone-13.html')
        tag = re.search(r'<form class="picker" id="picker"[^>]*>', src).group(0)
        live = tag.replace(' data-preview="1"', '')
        assert live != tag

        def variant(name, extra):
            with open(os.path.join(cls.site, 'products', name), 'w', encoding='utf-8') as fh:
                fh.write(src.replace(tag, live[:-1] + extra + '>'))
        variant('t-static.html', ' data-stock="{&quot;128GB|Very Good&quot;: 2, &quot;128GB|Good&quot;: 1}"')
        variant('t-static-zero.html', ' data-stock="{&quot;128GB|Very Good&quot;: 0, &quot;128GB|Good&quot;: 3}"')
        variant('t-shop.html', f' data-shop="{SHOP_URL}"')
        variant('t-shop-stock.html', f' data-shop="{SHOP_URL}" data-stock="{{&quot;128GB|Very Good&quot;: 0}}"')
        variant('t-shop-bad.html', ' data-shop="http://shop.example/products/iphone-13"')
        # Shopify variant IDs for two choices only: 128GB and 256GB, Very Good, Blue
        cls.variants = {'128GB|Very Good|Blue': '44000000000111', '256GB|Very Good|Blue': 44000000000222}
        variant('t-shop-variants.html', f' data-shop="{SHOP_URL}" data-variants="' + html.escape(json.dumps(cls.variants), quote=True) + '"')
        variant('t-shop-variants-bad.html', f' data-shop="{SHOP_URL}" data-variants="{{&quot;128GB|Very Good|Blue&quot;:&quot;abc&quot;}}"')
        variant('t-nostock.html', '')   # static route, no stock data from either place
        # a second copy whose stock.js lists some phones (and a third with no stock.js at all)
        cls.site2 = os.path.join(cls.tmp, 'site2')
        shutil.copytree(cls.site, cls.site2)
        stock = {'iphone-13': {'128GB|Very Good': 0, '128GB|Good': 2}, 'iphone-12': {}, 'iphone-12-pro': {'64GB|Good': 0},
                 'galaxy-s23': {'128GB|Good': 0}}
        js = cls.read('stock.js')
        with open(os.path.join(cls.site2, 'stock.js'), 'w', encoding='utf-8') as fh:
            fh.write(js[:js.rindex('window.FULLBARS_STOCK =')] + 'window.FULLBARS_STOCK = ' + json.dumps(stock) + ';\n')
        with open(os.path.join(cls.site2, 'products', 't-static-js.html'), 'w', encoding='utf-8') as fh:
            fh.write(src.replace(tag, live[:-1] + ' data-stock="{&quot;128GB|Very Good&quot;: 5}">'))
        cls.site3 = os.path.join(cls.tmp, 'site3')
        shutil.copytree(cls.site, cls.site3)
        os.remove(os.path.join(cls.site3, 'stock.js'))
        # Shopify route with a stock snapshot, written as fetch_shopify_variants.py --write-stock writes it: the iPhone 13
        # has one 128GB Good available (any colour), the iPhone 12 nothing; variant IDs for 128GB Good and Very Good, Blue
        cls.site4 = os.path.join(cls.tmp, 'site4')
        shutil.copytree(cls.site, cls.site4)
        sys.path.insert(0, PACK)
        import fetch_shopify_variants as fv   # noqa: E402
        import datetime
        snap = fv.stock_js({'iphone-13': {'128GB|Good': 1}, 'iphone-12': {}}, fv.stock_header(os.path.join(SITE, 'stock.js'), SITE),
                           'https://shop.example', datetime.datetime(2026, 10, 13, 9, 0))
        with open(os.path.join(cls.site4, 'stock.js'), 'w', encoding='utf-8') as fh:
            fh.write(snap)
        cls.snap_variants = {'128GB|Good|Blue': '44000000000333', '128GB|Very Good|Blue': '44000000000111'}
        with open(os.path.join(cls.site4, 'products', 't-shop-snap.html'), 'w', encoding='utf-8') as fh:
            fh.write(src.replace(tag, live[:-1] + f' data-shop="{SHOP_URL}" data-variants="'
                                 + html.escape(json.dumps(cls.snap_variants), quote=True) + '">'))
        # one-off stock, sparse as it will really be, on live (not preview) pages: which option each page opens on
        cls.site5 = os.path.join(cls.tmp, 'site5')
        shutil.copytree(cls.site, cls.site5)
        stock5 = {'iphone-14': {'256GB|Excellent': 1},
                  'iphone-12': {'64GB|Good': 1},
                  'iphone-13': {'128GB|Excellent': 1, '256GB|Good': 1},        # £249 and £239: the later one is cheaper
                  'iphone-16-pro': {'512GB|Good': 1, '128GB|Excellent': 1}}   # both £699: page order decides
        with open(os.path.join(cls.site5, 'stock.js'), 'w', encoding='utf-8') as fh:
            fh.write(js[:js.rindex('window.FULLBARS_STOCK =')] + 'window.FULLBARS_STOCK = ' + json.dumps(stock5) + ';\n')
        for h in stock5:
            p = os.path.join(cls.site5, 'products', h + '.html')
            with open(p, encoding='utf-8') as fh:
                page = fh.read()
            ptag = re.search(r'<form class="picker" id="picker"[^>]*>', page).group(0)
            assert ' data-preview="1"' in ptag, h
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(page.replace(ptag, ptag.replace(' data-preview="1"', '')))
        contact = cls.read('contact.html').replace(' data-preview="1"', '')
        with open(os.path.join(cls.site, 't-contact-shopify.html'), 'w', encoding='utf-8') as fh:
            fh.write(contact)
        with open(os.path.join(cls.site, 't-contact-static.html'), 'w', encoding='utf-8') as fh:
            fh.write(contact.replace('<option>Question about a phone</option>',
                                     '<option>Question about a phone</option><option>Order a phone</option>', 1))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def read(cls, rel):
        with open(os.path.join(cls.site, rel), encoding='utf-8') as fh:
            return fh.read()

    @classmethod
    def patch(cls, rel, old, new):
        src = cls.read(rel)
        assert old in src, old
        with open(os.path.join(cls.site, rel), 'w', encoding='utf-8') as fh:
            fh.write(src.replace(old, new, 1))

    def browse(self, cases, site=None):
        for c in cases:
            c['url'] = 'file://' + os.path.join(site or self.site, c['page']) + c.get('query', '')
        r = subprocess.run([NODE, self.driver, json.dumps(cases)], capture_output=True, text=True, timeout=180,
                           env=dict(os.environ, NODE_PATH=NODE_PATH))
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        data = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(data['errors'], [])
        return data['out']

    def test_preview_page_is_unchanged(self):
        (b,) = self.browse([{'page': 'products/iphone-13.html'}])
        self.assertEqual((b['tag'], b['text'], b['href']), ('SPAN', 'Opening soon', None))

    def test_static_route_stock_counts_and_links(self):
        held2, good_paylink, zero, zero_bare = self.browse([
            {'page': 'products/t-static.html'},                       # 128GB Very Good: 2 units
            {'page': 'products/t-static.html', 'query': '?grade=Good'},   # 128GB Good: 1 unit, has a Payment Link
            # 128GB Very Good: 0 units. Named in the address, so the page keeps it (opened bare, it would move to a held
            # option: the next case)
            {'page': 'products/t-static-zero.html', 'query': '?grade=Very%20Good'},
            {'page': 'products/t-static-zero.html'},
        ])
        self.assertEqual((held2['tag'], held2['text']), ('A', 'Order — £230'))
        self.assertTrue(held2['href'].startswith('../contact.html?order=iPhone%2013%20128GB%2C%20Very%20Good'), held2['href'])
        self.assertEqual((good_paylink['text'], good_paylink['href']), ('Buy now — £209', PAY_LINK))
        self.assertEqual(zero['text'], 'Not in stock — ask us')
        self.assertIn('?ask=', zero['href'])
        # opened bare, 0 counts as not held: the page skips 128GB Very Good for the held 128GB Good (3 units)
        self.assertEqual((zero_bare['picked'], zero_bare['text']), ('128GB|Good|Blue', 'Buy now — £209'))

    def test_shopify_route_sends_order_to_shopify_only(self):
        default, paylinked, clicked, unheld, bad = self.browse([
            {'page': 'products/t-shop.html'},
            {'page': 'products/t-shop.html', 'query': '?grade=Good'},  # pay.js has a link for this one: never used here
            {'page': 'products/t-shop.html', 'click': 'input[name="storage"][value="256GB"]'},
            {'page': 'products/t-shop-stock.html'},
            {'page': 'products/t-shop-bad.html'},
        ])
        # no variant IDs on this page: never a price on a button that may open another variant
        self.assertEqual((default['tag'], default['text'], default['href']), ('A', 'Choose and pay on the next page', SHOP_URL))
        self.assertTrue(default['handoff'])
        self.assertEqual((paylinked['text'], paylinked['href']), ('Choose and pay on the next page', SHOP_URL))
        self.assertEqual((clicked['text'], clicked['href']), ('Choose and pay on the next page', SHOP_URL))
        self.assertFalse(unheld['handoff'])
        self.assertEqual(unheld['text'], 'Not in stock — ask us')
        self.assertIn('?ask=', unheld['href'])
        self.assertEqual(bad['text'], 'Ask us about this phone')
        self.assertIn('?ask=', bad['href'])
        for b in (default, paylinked, clicked, unheld, bad):
            self.assertEqual(b['orderLinks'], [])
            self.assertNotIn('?order=', b['href'])
            self.assertNotEqual(b['href'], PAY_LINK)

    def test_shopify_variant_ids_open_the_chosen_phone(self):
        mapped, mapped_click, unmapped_colour, unmapped_grade, bad = self.browse([
            {'page': 'products/t-shop-variants.html'},                                             # 128GB Very Good Blue
            {'page': 'products/t-shop-variants.html', 'click': 'input[name="storage"][value="256GB"]'},
            {'page': 'products/t-shop-variants.html', 'click': 'input[name="colour"][value="Midnight"]'},
            {'page': 'products/t-shop-variants.html', 'query': '?grade=Good'},
            {'page': 'products/t-shop-variants-bad.html'},
        ])
        self.assertEqual((mapped['text'], mapped['href']), ('Order — £230', SHOP_URL + '?variant=44000000000111'))
        self.assertEqual((mapped['handoff'], mapped['describedBy']), (False, None))
        self.assertEqual((mapped_click['text'], mapped_click['href']), ('Order — £255', SHOP_URL + '?variant=44000000000222'))
        for b in (unmapped_colour, unmapped_grade, bad):   # no ID for this choice (or not a number): no price, the note shows
            self.assertEqual((b['text'], b['href']), ('Choose and pay on the next page', SHOP_URL))
            self.assertTrue(b['handoff'])
            self.assertEqual(b['describedBy'], 'handoffNote')
        for b in (mapped, mapped_click, unmapped_colour, unmapped_grade, bad):
            self.assertEqual(b['orderLinks'], [])

    def test_preview_has_no_stock_or_handoff_notes(self):
        home, shop, product = self.browse([{'page': 'index.html'}, {'page': 'shop.html'}, {'page': 'products/iphone-13.html'}])
        for b in (home, shop, product):
            self.assertEqual((b['noneCards'], b['noneTiles']), ([], []))
        self.assertFalse(product['handoff'])
        self.assertEqual(product['na'], [])
        self.assertEqual((shop['cards'], shop['hiddenCards']), (19, 0))

    def test_stock_js(self):
        shop, home, product, static, static_good, preview, static_vg = self.browse([
            {'page': 'shop.html'}, {'page': 'index.html'}, {'page': 'products/iphone-14.html'},
            {'page': 'products/t-static-js.html'}, {'page': 'products/t-static-js.html', 'query': '?grade=Good'},
            {'page': 'products/iphone-13.html'},
            {'page': 'products/t-static-js.html', 'query': '?grade=Very%20Good'},
        ], site=self.site2)
        none = 'None in stock right now'
        # listed with no units: iPhone 12 ({}), 12 Pro and Galaxy S23 (only zeros); iPhone 13 holds 2, the rest aren't listed
        self.assertEqual(sorted(shop['noneCards']), sorted(f'products/{h}.html: {none}' for h in ('iphone-12', 'iphone-12-pro', 'galaxy-s23')))
        self.assertEqual((shop['cards'], shop['hiddenCards']), (19, 0))   # cards stay
        # tiles: the iPhone 12 range (both phones at none) and the Galaxy; not the iPhone 13 range (one phone holds stock)
        self.assertEqual(sorted(home['noneTiles']), [f'collections/iphone-12-series.html: {none}', f'collections/samsung-galaxy.html: {none}'])
        self.assertIn(f'products/galaxy-s23.html: {none}', home['noneCards'])
        self.assertIn(f'../products/iphone-12.html: {none}', preview['noneCards'])   # 'Similar phones' on a product page
        self.assertEqual(product['noneCards'], [])   # the iPhone 14's similar phones are all unlisted or held
        # the product page: stock.js (128GB Very Good: 0, Good: 2) wins over the page's data-stock (Very Good: 5). Opened
        # bare, it moves off the ticked 128GB Very Good to the held 128GB Good (with the data-stock it would have stayed
        # on Very Good at £230); Very Good is still marked, as a condition is checked against the chosen storage (128GB)
        self.assertEqual((static['picked'], static['text']), ('128GB|Good|Blue', 'Buy now — £209'))
        self.assertIn('Very Good', static['na'])
        # named in the address, 128GB Very Good is kept, and stock.js's 0 makes it "Not in stock — ask us"; 128GB itself
        # isn't marked, because 128GB Good is held
        self.assertEqual((static_vg['picked'], static_vg['text']), ('128GB|Very Good|Blue', 'Not in stock — ask us'))
        self.assertEqual(static_vg['na'], ['256GB', '512GB', 'Excellent', 'Very Good'])
        # the cheapest option (128GB Good, £209) is held, so the from-line has no "not in stock" note
        self.assertEqual(static_vg['from'], 'Price for 128GB in Very Good. From £209 in Good.')
        self.assertEqual((static_good['text'], static_good['href']), ('Buy now — £209', PAY_LINK))   # held (2) and has a Payment Link
        self.assertEqual(preview['text'], 'Opening soon')   # preview pages never order, whatever stock.js says

    def test_missing_stock_js_breaks_nothing(self):
        static, shop = self.browse([{'page': 'products/t-static.html'}, {'page': 'shop.html'}], site=self.site3)
        self.assertEqual(static['text'], 'Order — £230')   # the page's data-stock still works
        self.assertEqual(shop['noneCards'], [])

    def test_shopify_route_with_a_stock_snapshot(self):
        """Shopify route plus a stock.js snapshot: a storage and condition Shopify can't sell reads "Not in stock — ask us"
        (never an Order link to a sold-out variant); one it can opens the variant; a phone with nothing available shows
        "None in stock right now" on its cards."""
        unheld, held, held_other_colour, shop, bare = self.browse([
            # 128GB Very Good: not in the snapshot (named in the address, so the page keeps it)
            {'page': 'products/t-shop-snap.html', 'query': '?grade=Very%20Good'},
            {'page': 'products/t-shop-snap.html', 'query': '?grade=Good'},           # 128GB Good: 1 available
            {'page': 'products/t-shop-snap.html', 'query': '?grade=Good&colour=Midnight'},
            {'page': 'shop.html'},
            {'page': 'products/t-shop-snap.html'},   # opened bare: moves off the ticked Very Good to the held 128GB Good
        ], site=self.site4)
        self.assertEqual(unheld['text'], 'Not in stock — ask us')
        self.assertIn('../contact.html?ask=', unheld['href'])
        self.assertNotIn('variant=', unheld['href'])
        self.assertFalse(unheld['handoff'])
        self.assertIn('Very Good', unheld['na'])
        self.assertEqual((held['text'], held['href']), ('Order — £209', SHOP_URL + '?variant=44000000000333'))
        self.assertEqual((bare['picked'], bare['text'], bare['href']), ('128GB|Good|Blue', 'Order — £209', SHOP_URL + '?variant=44000000000333'))
        # colour isn't in the stock key: a held storage and condition in a colour with no variant ID hands off to Shopify
        self.assertEqual((held_other_colour['text'], held_other_colour['href']), ('Choose and pay on the next page', SHOP_URL))
        self.assertEqual(shop['noneCards'], ['products/iphone-12.html: None in stock right now'])
        for b in (unheld, held, held_other_colour, bare):
            self.assertEqual(b['orderLinks'], [])

    def test_page_opens_on_a_held_option(self):
        """Real one-off stock is sparse, so the option ticked in the HTML (128GB Very Good) is usually not held. Opened
        without ?storage or ?grade, the page moves to the cheapest held storage and condition instead of showing
        "Not in stock — ask us" with the one held unit hidden behind options labelled not in stock."""
        (one, one_good, twelve, named, named_grade, colour_only, stale, cheaper, tie,
         storage_only, storage_only_none, grade_only) = self.browse([
            {'page': 'products/iphone-14.html'},                                     # only 256GB Excellent held
            {'page': 'products/iphone-14.html', 'click': 'input[name="grade"][value="Good"]'},
            {'page': 'products/iphone-12.html'},                                     # only 64GB Good held
            {'page': 'products/iphone-14.html', 'query': '?storage=128GB&grade=Very%20Good&colour=Blue'},
            {'page': 'products/iphone-14.html', 'query': '?grade=Good'},
            {'page': 'products/iphone-14.html', 'query': '?colour=Blue'},
            {'page': 'products/iphone-14.html', 'query': '?storage=9TB'},
            {'page': 'products/iphone-13.html'},             # 128GB Excellent £249 and 256GB Good £239 held
            {'page': 'products/iphone-16-pro.html'},         # 512GB Good and 128GB Excellent held, both £699
            {'page': 'products/iphone-14.html', 'query': '?storage=256GB'},
            {'page': 'products/iphone-14.html', 'query': '?storage=512GB'},
            {'page': 'products/iphone-14.html', 'query': '?grade=Excellent'},
        ], site=self.site5)
        # iPhone 14: opens on the one held unit, with a live button; 256GB isn't marked, the address stays bare
        self.assertEqual((one['picked'], one['price'], one['text']), ('256GB|Excellent|Purple', '£389', 'Order — £389'))
        self.assertTrue(one['href'].startswith('../contact.html?order=iPhone%2014%20256GB%2C%20Excellent%2C%20Purple&price=389'), one['href'])
        self.assertEqual((one['na'], one['nacond']), (['128GB', '512GB', 'Very Good', 'Good'], []))
        self.assertEqual(one['search'], '')
        # the from-line still quotes the cards' "from" price (the lowest of any option), and says it isn't held
        self.assertEqual(one['from'], 'Price for 256GB in Excellent. From £309 for 128GB in Good (not in stock right now).')
        # choosing Good there: 256GB Good isn't held. 256GB isn't "not in stock" (its Excellent is held), but its chip now
        # shows the Good price (£329), which we can't sell: "not in this condition". Good itself is "not in stock"
        self.assertEqual((one_good['picked'], one_good['text']), ('256GB|Good|Purple', 'Not in stock — ask us'))
        self.assertEqual((one_good['na'], one_good['nacond']), (['128GB', '512GB', 'Very Good', 'Good'], ['256GB']))
        # iPhone 12: only 64GB Good, which is also the HTML's storage and the cheapest option
        self.assertEqual((twelve['picked'], twelve['text']), ('64GB|Good|Blue', 'Order — £139'))
        self.assertEqual((twelve['na'], twelve['nacond']), (['128GB', '256GB', 'Excellent', 'Very Good'], []))
        self.assertEqual(twelve['from'], 'Price for 64GB in Good: the lowest for this phone.')
        # an option the address names is kept, held or not: the customer chose it
        self.assertEqual((named['picked'], named['text']), ('128GB|Very Good|Blue', 'Not in stock — ask us'))
        self.assertIn('?ask=', named['href'])
        # 256GB is held in Excellent, so not "not in stock"; its chip shows the Very Good price (£360), not held
        self.assertEqual((named['na'], named['nacond']), (['128GB', '512GB', 'Excellent', 'Very Good', 'Good'], ['256GB']))
        # only the condition named, and no storage holds it: nothing to move to
        self.assertEqual((named_grade['picked'], named_grade['text']), ('128GB|Good|Purple', 'Not in stock — ask us'))
        self.assertEqual(named_grade['nacond'], ['256GB'])
        # only one of the two named: that one is kept, and the other moves to the cheapest held with it
        self.assertEqual((storage_only['picked'], storage_only['text']), ('256GB|Excellent|Purple', 'Order — £389'))
        self.assertEqual(storage_only['search'], '?storage=256GB')
        self.assertEqual((grade_only['picked'], grade_only['text']), ('256GB|Excellent|Purple', 'Order — £389'))
        # ... unless that storage isn't held in any condition: then it stays as it is, marked
        self.assertEqual((storage_only_none['picked'], storage_only_none['text']), ('512GB|Very Good|Purple', 'Not in stock — ask us'))
        self.assertIn('512GB', storage_only_none['na'])
        # only a colour in the address: still moves to the held option, keeping that colour
        self.assertEqual((colour_only['picked'], colour_only['text']), ('256GB|Excellent|Blue', 'Order — £389'))
        # an unknown storage names nothing: the page moves to the held option and the address follows what's ticked
        self.assertEqual(stale['picked'], '256GB|Excellent|Purple')
        self.assertEqual(stale['search'], '?storage=256GB&grade=Excellent&colour=Purple')
        # two held: the cheaper wins, even though it comes later on the page. 128GB is held, but in Excellent only
        self.assertEqual((cheaper['picked'], cheaper['text']), ('256GB|Good|Blue', 'Order — £239'))
        self.assertEqual((cheaper['na'], cheaper['nacond']), (['512GB', 'Excellent', 'Very Good'], ['128GB']))
        self.assertEqual(cheaper['from'], 'Price for 256GB in Good. From £209 for 128GB in Good (not in stock right now).')
        # a tie at the same price: the first in the page's order (128GB Excellent), not stock.js's order
        self.assertEqual((tie['picked'], tie['text']), ('128GB|Excellent|Desert Titanium', 'Order — £699'))

    def test_no_stock_data_keeps_the_page_default(self):
        """Without stock data (the preview, or a live page with neither stock.js nor data-stock) the page opens on the
        option ticked in its HTML, marks nothing, and offers every option, exactly as before."""
        preview, live, live_click, shop = self.browse([
            {'page': 'products/iphone-14.html'}, {'page': 'products/t-nostock.html'},
            {'page': 'products/t-nostock.html', 'click': 'input[name="storage"][value="512GB"]'},
            {'page': 'products/t-shop.html'},
        ])
        self.assertEqual((preview['picked'], preview['price'], preview['text'], preview['na'], preview['nacond']),
                         ('128GB|Very Good|Purple', '£330', 'Opening soon', [], []))
        self.assertEqual(preview['from'], 'Price for 128GB in Very Good. From £309 in Good.')   # as in the page's HTML
        self.assertEqual((live['picked'], live['price'], live['text'], live['na'], live['nacond'], live['search']),
                         ('128GB|Very Good|Blue', '£230', 'Order — £230', [], [], ''))
        self.assertEqual(live['from'], 'Price for 128GB in Very Good. From £209 in Good.')
        self.assertEqual((live_click['picked'], live_click['text'], live_click['na'], live_click['nacond']),
                         ('512GB|Very Good|Blue', 'Order — £290', [], []))
        self.assertEqual(live_click['from'], 'Price for 512GB in Very Good. From £209 for 128GB in Good.')
        self.assertEqual((shop['picked'], shop['text']), ('128GB|Very Good|Blue', 'Choose and pay on the next page'))

    def test_contact_form_takes_email_orders_only_with_the_topic(self):
        q = '?order=iPhone%2013%20128GB%2C%20Good%2C%20Blue&price=209'
        shopify, static = self.browse([{'page': 't-contact-shopify.html', 'query': q},
                                       {'page': 't-contact-static.html', 'query': q}])
        self.assertEqual((shopify['topic'], shopify['msg']), ('Question about a phone', ''))
        self.assertEqual(static['topic'], 'Order a phone')
        self.assertTrue(static['msg'].startswith('I’d like to order:\n- iPhone 13 128GB, Good, Blue (£209)'), static['msg'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
