#!/usr/bin/env python3
"""Tests for the site's shared markup (R8): the one-off stock line beside every list of "from" prices, stock.js loaded
before site.js wherever cards or a picker are, wording that is true on every checkout route, terms section 3's online
ordering paragraph (E-Commerce Regulations 2002, regulation 9), and the FAQ page agreeing with its structured data.

Run from the repo root:  python3 launch/full-bars/tests/test_site_markup.py   (reads the site only; standard library)
"""
import html
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'full-bars')

sys.dont_write_bytecode = True
sys.path.insert(0, PACK)
import go_live  # noqa: E402

DISC = ('<p class="small oneoff-note">Every phone is a one-off, so not every storage, condition and colour is in stock '
        'at every price, including the &ldquo;from&rdquo; price.</p>')
# the same sentence, as a customer reads it
PLAIN = 'Every phone is a one-off, so not every storage, condition and colour is in stock at every price, including the “from” price'


def pages():
    out = {}
    for d, _, fs in os.walk(SITE):
        for f in fs:
            if f.endswith('.html'):
                rel = os.path.relpath(os.path.join(d, f), SITE).replace(os.sep, '/')
                with open(os.path.join(d, f), encoding='utf-8') as fh:
                    out[rel] = fh.read()
    return out


class SiteMarkupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = pages()

    def test_disclosure_beside_every_list_of_from_prices(self):
        """Each card grid, the home page's range tiles, every comparison table with a "From" column and every product
        page's price carry the same one-off line, in the same markup."""
        checked = 0
        for rel, src in self.pages.items():
            main = src[src.index('<main'):src.index('</main>')]
            self.assertEqual(len(re.findall(r'class="[^"]*\boneoff-note\b', main)), main.count(DISC), f'{rel}: a different variant of the line')
            for m in re.finditer(r'<div class="grid"[^>]*>', main):
                if '<article class="card"' not in main[m.end():m.end() + 400]:
                    continue
                before = main[max(0, m.start() - 900):m.start()]
                self.assertIn(DISC, before, f'{rel}: card grid at {m.start()} has no one-off line just before it')
                checked += 1
            for m in re.finditer(r'<th>From</th>', main):
                after = main[m.end():main.find('</table>', m.end()) + 1200]
                self.assertIn(DISC, after, f'{rel}: comparison table with a From column has no one-off line after it')
                checked += 1
            if '<div class="tiles">' in main:
                i = main.index('<div class="tiles">')
                self.assertIn(DISC, main[i - 300:i], f'{rel}: range tiles have no one-off line')
                checked += 1
            if rel.startswith('products/'):
                self.assertRegex(main, r'<p class="pd-config" id="pdFrom">[^<]*</p>' + re.escape(DISC), rel)
                checked += 1
        self.assertGreaterEqual(checked, 19 + 19 + 11 + 6 + 1 + 1 + 1 + 12)
        # 70 placements, all identical (applied by script), each tying the line to the advertised "from" price
        self.assertEqual(sum(src.count(DISC) for src in self.pages.values()), 70)
        self.assertFalse([r for r, src in self.pages.items()
                          if re.search(r'oneoff-note">[^<]*at every price\.</p>', src)], 'an old, shorter line is left')
        # the same sentence in terms section 2 and the FAQ (page and structured data)
        terms2 = html.unescape(self.pages['terms.html'].split('<h2>2. Our phones</h2>')[1].split('<h2>3.')[0])
        self.assertIn(PLAIN + '.', terms2)
        faq = self.pages['faq.html']
        self.assertIn('<summary>Is every storage, condition and colour in stock?</summary>', faq)
        self.assertEqual(html.unescape(faq).count(PLAIN), 2)

    def test_stock_js_loads_before_site_js(self):
        with open(os.path.join(SITE, 'stock.js'), encoding='utf-8') as fh:
            self.assertEqual(go_live.read_stock_js({'stock.js': fh.read()}), ({}, []))   # empty in the preview
        n = 0
        for rel, src in self.pages.items():
            needs = '<article class="card"' in src or 'id="picker"' in src
            self.assertEqual(go_live.loads_stock_js(src), needs, rel)
            if needs:
                pre = '../' if '/' in rel else ''
                self.assertIn(f'<script src="{pre}pay.js" defer></script>\n<script src="{pre}stock.js" defer></script>\n'
                              f'<script src="{pre}site.js" defer onerror=', src, rel)
                n += 1
        self.assertEqual(n, 38)

    def test_wording_true_on_every_route(self):
        products = {r: s for r, s in self.pages.items() if r.startswith('products/')}
        self.assertEqual(len(products), 19)
        for rel, src in products.items():
            self.assertIn('<legend>Colour <em>subject to stock; confirmed by email</em></legend>', src, rel)
            self.assertIn('Ask before you order and we&rsquo;ll send photos of the exact phone.', src, rel)
            self.assertIn('<p class="small handoff-note" id="handoffNote" hidden>You&rsquo;ll pick storage, condition and colour '
                          'again there; anything we don&rsquo;t have shows as sold out.</p>', src, rel)
        rx = go_live.CHECKOUT_WORDS['stripe-buy-now']
        for rel, src in self.pages.items():
            for seg in go_live.segments(rel, src):
                for m in rx.finditer(seg.fold):
                    if 'intended payment provider' in m.group(0):
                        continue   # terms section 4: listed for rewriting on both routes at launch
                    a, b = go_live.sentence_at(seg.text, m.start())
                    self.assertRegex(seg.text[a:b], go_live.EMAIL_ORDER_ONLY, f'{rel}: "{seg.text[a:b]}" promises something '
                                     'before payment that a Buy now payment can\'t wait for')

    def test_terms_section_3_has_the_online_ordering_information(self):
        """E-Commerce Regulations 2002, reg 9(1): the steps, filing and access, correcting input errors, languages."""
        sec3 = html.unescape(self.pages['terms.html'].split('<h2>3. Ordering and when the contract is made</h2>')[1].split('<h2>4.')[0])
        for text in ('If you buy online, these are the steps: choose the storage, condition and colour',
                     'You can check and change your choice on the product page, and check it again with the total before you pay',
                     'If you spot a mistake after paying, email us straight away.',
                     'The contract is in English only.',
                     'We keep a record of your order, as our privacy policy explains, and you can email us for a copy of it.',
                     'Our confirmation email gives you these terms as they stood on the day you ordered, so please keep it.'):
            self.assertIn(text, re.sub(r'<[^>]+>', '', sec3))
        # whether the contract is filed and accessible (reg 9(1)(b)), in words true on both routes: Shopify shows each
        # order on its order status page, so the paragraph mustn't say the order can't be seen online
        self.assertNotRegex(sec3, r'(?i)can(?:not|’t|\'t) (?:view|see)')
        # it names no checkout, so the Shopify route's wording check leaves it alone
        para = sec3.split('If you buy online')[1]
        self.assertIsNone(go_live.CHECKOUT_WORDS['shopify'].search(para))

    def test_faq_page_and_structured_data_agree(self):
        faq = self.pages['faq.html']
        asked = [html.unescape(q) for q in re.findall(r'<summary>(.*?)</summary>', faq)]
        ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', faq, re.S)]
        page = [b for b in ld if b.get('@type') == 'FAQPage'][0]
        self.assertEqual([q['name'] for q in page['mainEntity']], asked)
        for q in page['mainEntity']:
            i = faq.index('<summary>' + html.escape(q['name'], quote=False).replace('’', '&rsquo;').replace('‘', '&lsquo;'))
            ans = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', faq[i:faq.index('</details>', i)].split('</summary>')[1])))
            self.assertEqual(ans.strip(), q['acceptedAnswer']['text'], q['name'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
