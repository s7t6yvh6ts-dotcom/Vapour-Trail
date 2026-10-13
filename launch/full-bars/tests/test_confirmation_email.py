#!/usr/bin/env python3
"""Tests for the order confirmation templates (order-confirmation-email.md and .html).

Run from the repo root:  python3 launch/full-bars/tests/test_confirmation_email.py
They only read files. Python 3 standard library only.
"""
import html
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'full-bars')


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def text(src):
    """Visible text of an HTML fragment: tags dropped, <br> as a new line, entities decoded, spaces collapsed."""
    src = re.sub(r'<br\s*/?>', '\n', src)
    src = html.unescape(re.sub(r'<[^>]+>', '', src))
    return '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in src.split('\n'))


class ConfirmationEmailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = read(os.path.join(PACK, 'order-confirmation-email.md'))
        cls.html = read(os.path.join(PACK, 'order-confirmation-email.html'))
        cls.comment, cls.body = cls.html.split('{% endcomment %}', 1)
        cls.returns = read(os.path.join(SITE, 'delivery-returns.html'))
        cls.golive = read(os.path.join(PACK, 'GO-LIVE.md'))

    def test_imei_matches_the_sites_promise(self):
        """delivery-returns.html says the identifier never appears in emails. While it does, the Shopify template sends
        nothing about the IMEI, and both files tell Ash to change that sentence first if he wants the last 4 digits."""
        never = 'never appears on our website, emails or receipts'
        if never in self.returns:
            self.assertNotIn('imei', self.body.lower())   # the customer-facing part of the Shopify template
        self.assertIn('IMEI (YOUR CALL', self.comment)
        self.assertIn(f'"{never}"', self.comment)
        self.assertIn('FIRST change that sentence on delivery-returns.html', self.comment)
        self.assertIn('This decision covers both files', self.md)
        self.assertIn('change that sentence on `delivery-returns.html` first', self.md)
        self.assertIn('It covers both files.', self.golive)

    def test_cancellation_form_is_the_sites_word_for_word(self):
        m = re.search(r'<div class="callout"><p>(To \[Company name\].*?)</p></div>', self.returns, re.S)
        site_form = text(m.group(1))
        box = re.search(r'<p class="box"[^>]*>(To \[Company name\].*?)</p>', self.body, re.S)
        self.assertEqual(text(box.group(1)), site_form)
        quoted = '\n'.join(line[2:].rstrip() for line in self.md.splitlines() if line.startswith('> '))
        self.assertEqual(quoted, '\n'.join(line.rstrip() for line in site_form.split('\n')))

    def test_required_information_is_in_both(self):
        for name, src in (('md', self.md), ('html', text(self.body))):
            for needed in ('you can cancel for any reason within 14 days, starting the day after your phone is delivered',
                           'we send you a free, tracked returns label, so you don’t pay to return it'
                           if name == 'html' else "we send you a free, tracked returns label, so you don't pay to return it",
                           'within 14 days of receiving the phone back',
                           'It is on top of your Consumer Rights Act 2015 rights, not instead of them.',
                           'Our 30-day satisfaction guarantee', 'Your 12-month warranty',
                           'This warranty is given by [Company name], trading as Full Bars, [Registered business address]',
                           'Citizens Advice consumer helpline'):
                self.assertIn(needed, src, f'{name}: {needed}')

    def test_replaced_parts_line_points_at_the_item_title(self):
        """A replaced-part unit is sold through a draft order whose custom item title names the part (GO-LIVE.md
        section 4), so the Parts line has to point at the item title, not at a listing."""
        self.assertIn('all original manufacturer parts, unless the item title above names a replaced part', self.body)
        self.assertIn('the draft order\'s custom item title must name the replaced part', self.comment)
        self.assertIn('Shopify draft order', self.golive)

    def test_ask_before_you_order_promises_hold_on_every_route(self):
        """R8: the photos and battery promises say "ask us before you order", true when ordering is paying (Shopify, or
        Buy now), so GO-LIVE.md records them as done instead of listing them for rewriting."""
        golive = self.golive.replace('’', "'")
        faq = html.unescape(read(os.path.join(SITE, 'faq.html'))).replace('’', "'")
        home = html.unescape(read(os.path.join(SITE, 'index.html'))).replace('’', "'")
        self.assertEqual(faq.count("If you'd like photos of the exact phone you're buying, ask us before you order and we'll "
                                   'send them.'), 2)   # the page and the structured data
        self.assertEqual(faq.count('Want the exact figure for any phone? Ask us before you order.'), 2)
        self.assertIn('Want the exact figure for any phone? Ask us before you order.', home)
        for src in (faq, home):
            self.assertNotIn('ask when you order', src.lower())
        self.assertIn('now say "ask us before you order"', golive)


if __name__ == '__main__':
    unittest.main()
