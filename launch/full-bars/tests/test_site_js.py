#!/usr/bin/env python3
"""Browser tests for site.js's Order button and contact form, in headless Chromium (Playwright for Node).

What they pin down:
  - preview: the Order control stays the inert "Opening soon" span;
  - static route: data-stock counts any whole number above 0 as held (2 units is in stock), 0 or a missing key is not;
    a Payment Link makes "Buy now";
  - Shopify route (data-shop on #picker): the Order button goes to the Shopify product, reads "Order — £…", and no
    email-order (contact.html?order=) or Payment Link is ever built on the page;
  - contact.html ignores ?order= unless the form has the "Order a phone" topic (the static route only).

Pages are opened straight from a temporary copy of the site (file://), so no web server is needed. Skipped if Node
or its playwright package isn't installed. Run from the repo root:  python3 launch/full-bars/tests/test_site_js.py
"""
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
      return {
        tag: b ? b.tagName : null, text: b ? b.textContent : null, href: b ? b.getAttribute('href') : null,
        orderLinks: Array.from(document.querySelectorAll('[href*="?order="]')).map(a => a.getAttribute('href')),
        topic: topic ? topic.value : null, msg: msg ? msg.value : null,
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

    def browse(self, cases):
        for c in cases:
            c['url'] = 'file://' + os.path.join(self.site, c['page']) + c.get('query', '')
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
        held2, good_paylink, zero = self.browse([
            {'page': 'products/t-static.html'},                       # 128GB Very Good: 2 units
            {'page': 'products/t-static.html', 'query': '?grade=Good'},   # 128GB Good: 1 unit, has a Payment Link
            {'page': 'products/t-static-zero.html'},                  # 128GB Very Good: 0 units
        ])
        self.assertEqual((held2['tag'], held2['text']), ('A', 'Order — £230'))
        self.assertTrue(held2['href'].startswith('../contact.html?order=iPhone%2013%20128GB%2C%20Very%20Good'), held2['href'])
        self.assertEqual((good_paylink['text'], good_paylink['href']), ('Buy now — £209', PAY_LINK))
        self.assertEqual(zero['text'], 'Not in stock — ask us')
        self.assertIn('?ask=', zero['href'])

    def test_shopify_route_sends_order_to_shopify_only(self):
        default, paylinked, clicked, unheld, bad = self.browse([
            {'page': 'products/t-shop.html'},
            {'page': 'products/t-shop.html', 'query': '?grade=Good'},  # pay.js has a link for this one: never used here
            {'page': 'products/t-shop.html', 'click': 'input[name="storage"][value="256GB"]'},
            {'page': 'products/t-shop-stock.html'},
            {'page': 'products/t-shop-bad.html'},
        ])
        self.assertEqual((default['tag'], default['text'], default['href']), ('A', 'Order — £230', SHOP_URL))
        self.assertEqual((paylinked['text'], paylinked['href']), ('Order — £209', SHOP_URL))
        self.assertEqual((clicked['text'], clicked['href']), ('Order — £255', SHOP_URL))
        self.assertEqual(unheld['text'], 'Not in stock — ask us')
        self.assertIn('?ask=', unheld['href'])
        self.assertEqual(bad['text'], 'Ask us about this phone')
        self.assertIn('?ask=', bad['href'])
        for b in (default, paylinked, clicked, unheld, bad):
            self.assertEqual(b['orderLinks'], [])
            self.assertNotIn('?order=', b['href'])
            self.assertNotEqual(b['href'], PAY_LINK)

    def test_contact_form_takes_email_orders_only_with_the_topic(self):
        q = '?order=iPhone%2013%20128GB%2C%20Good%2C%20Blue&price=209'
        shopify, static = self.browse([{'page': 't-contact-shopify.html', 'query': q},
                                       {'page': 't-contact-static.html', 'query': q}])
        self.assertEqual((shopify['topic'], shopify['msg']), ('Question about a phone', ''))
        self.assertEqual(static['topic'], 'Order a phone')
        self.assertTrue(static['msg'].startswith('I’d like to order:\n- iPhone 13 128GB, Good, Blue (£209)'), static['msg'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
