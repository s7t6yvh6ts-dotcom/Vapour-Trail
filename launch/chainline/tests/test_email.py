#!/usr/bin/env python3
"""Tests for the order confirmation templates (order-confirmation-email.md and .html).

Run from launch/chainline:  python3 -m unittest discover -s tests
They only read files. Python 3 standard library only.
"""
import html
import json
import os
import re
import sys
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'chainline', 'index.html')


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def site_prices(site):
    """The prices the emails must repeat, read from the page itself: UK delivery from the bike data, the return
    collection prices from its "Cancelling an order" section (placeholders count as values)."""
    data = json.loads(re.search(r'<script type="application/json" id="shop-data">(.*?)</script>', site, re.S).group(1))
    cancel = html.unescape(re.sub(r'<[^>]+>', '', re.search(r'<details id="cancel">(.*?)</details>', site, re.S).group(1)))
    m = re.search(r"we'll collect it for (£[\d,]+) \(e-bikes (£(?:[\d,]+|\[[^\]]+\]))\)", cancel)
    ebike = data['delivery']['ebike']
    return {'delivery': '£{:,}'.format(data['delivery']['bike']), 'collect': m.group(1), 'collect_ebike': m.group(2),
            'ebike_delivery': '£{:,}'.format(ebike) if ebike else '£[e-bike delivery price]'}


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
        cls.site = read(SITE)
        cls.body_text = text(cls.body)
        cls.prices = site_prices(cls.site)

    def test_cancellation_form_is_the_sites_word_for_word(self):
        site_form = text(re.search(r'<p class="form-box">(.*?)</p>', self.site, re.S).group(1))
        box = re.search(r'<p class="box"[^>]*>(To \[Company name\].*?)</p>', self.body, re.S)
        self.assertEqual(text(box.group(1)), site_form)
        quoted = '\n'.join(line[2:].rstrip() for line in self.md.splitlines() if line.startswith('> '))
        self.assertEqual(quoted, '\n'.join(line.rstrip() for line in site_form.split('\n')))

    def test_schedule_2_and_regulation_16_information_is_in_both(self):
        needed = [
            'you can cancel for any reason within 14 days, starting the day after you get the bike',
            'returning it is at your cost',
            "we'll collect it for {collect} (e-bikes {collect_ebike})",
            "to your original payment method, within 14 days of getting the bike back, or of you showing us you've sent it, if that's sooner",
            'This warranty is given by [Company name], trading as Chainline Cycles, [Workshop address]',
            'applies in the UK, and lasts for 3 months',
            "It's on top of your Consumer Rights Act 2015 rights, not instead of them.",
            'Your legal rights come first',
            'Within 30 days of getting it, you can reject a faulty bike for a full refund.',
            'This warranty is extra',
            'it never limits your Consumer Rights Act rights: within 30 days of getting the bike you can reject it for a full refund',
            "you're entitled to a repair or replacement, and if that doesn't fix the problem, a price reduction or refund",
            'For other warranty claims, [who pays to collect and return the bike, and what it costs].',
            'five years in Scotland',
            'Citizens Advice consumer helpline on 0808 223 1133',
            'Chainline Cycles is a trading name of [Company name], a company registered in [England and Wales], company number [Company number]',
            'The bike is our responsibility until it',
            'Riders must be 14 or over.',
            "wasn't listed as stolen on BikeRegister when we checked",
            'Use only the maker',
        ]
        for name, src in (('md', self.md), ('html', self.body_text.replace('’', "'"))):
            for phrase in needed:
                phrase = phrase.format(**self.prices)
                self.assertIn(phrase.replace('’', "'"), src, f'{name}: {phrase}')
            self.assertNotRegex(src, r"(?i)we repair it first|if we can't, your legal rights", name)

    def test_the_unit_email_carries_the_bike_details(self):
        for field in ('{Frame number}', '{Ticket number}', '{BikeRegister check date}', '**Work done:** {from the ticket', '{rated Wh}',
                      "our capacity test measured {x}% of the battery's rated capacity", '{test method}'):
            self.assertIn(field, self.md)
        self.assertIn('**Collecting:**', self.md)
        self.assertIn('**Delivery:**', self.md)
        self.assertIn('Bikes sold in person at the workshop', self.md)

    def test_prices_in_the_unit_email_are_the_sites(self):
        """Read from the site, never typed here: a price changed on the site must be changed in the email too."""
        self.assertIn('{UK delivery, %s}' % self.prices['delivery'], self.md)
        self.assertIn('{E-bike courier, %s}' % self.prices['ebike_delivery'], self.md)
        for src in (self.md, self.body_text):
            self.assertIn("collect it for %s (e-bikes %s)" % (self.prices['collect'], self.prices['collect_ebike']), src.replace('’', "'"))

    def test_free_check_up_has_one_window(self):
        for src in (self.md, self.body_text, self.site):
            self.assertNotIn('6-week', src)
        self.assertIn('Bring the bike back within [8] weeks', self.md)

    def test_shopify_template_handles_collection_ebikes_and_the_ticket(self):
        # collection is tested with Shopify's documented pickup_in_store? (with and without order.), not delivery_method
        self.assertIn("{% if pickup_in_store? or order.pickup_in_store? %}", self.body)
        self.assertNotIn('delivery_method', self.body)
        # each payment method printed once: an authorisation and its capture are two transactions on one card
        self.assertIn('{% unless paid_by contains method %}', self.body)
        self.assertIn('<p><strong>Paid by:</strong> {{ paid_by }}.', self.body)
        self.assertIn("{% if line.product.type == 'Refurbished e-bike' %}", self.body)
        self.assertIn("{{ line.sku | remove_first: 'CL-' }}", self.body)
        self.assertIn('that email is when our contract is made', self.body_text.replace('’', "'"))
        # the Liquid type it tests for is the type the CSV writes
        build = read(os.path.join(PACK, 'build_shopify_csv.py'))
        self.assertIn("'Refurbished e-bike'", build)

    def test_dark_and_no_tax_line(self):
        self.assertIn('<meta name="color-scheme" content="dark">', self.body)
        self.assertNotRegex(self.body, r'(?i)\btax_price\b|\bVAT: ')

    def test_contract_wording_matches_the_sites_terms(self):
        self.assertIn('The contract is made when we email to confirm we\'ve accepted your order, which we do within [one working day]',
                      self.site)
        self.assertIn('This email confirms we\'ve accepted it, so our contract is now made.', self.md)


if __name__ == '__main__':
    unittest.main()
