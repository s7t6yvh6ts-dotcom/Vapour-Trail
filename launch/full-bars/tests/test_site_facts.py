#!/usr/bin/env python3
"""Tests for check_site_facts.py, facts.json and the facts.json weights in build_shopify_csv.py.

Every test that changes anything works on a temporary copy of sites/full-bars (or of facts.json); the real
site and the launch folder are hashed before and after the run to prove they were never written.

Run from the repo root:   python3 launch/full-bars/tests/test_site_facts.py
or:                       python3 -m unittest discover -s launch/full-bars/tests -p 'test_site_facts.py'
Set FULLBARS_SITE to test another copy of the site, TMPDIR to choose where the temporary copies go.
Python 3 standard library only.
"""
import csv
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
PACK = os.path.normpath(os.path.join(HERE, '..'))
TOOL = os.path.join(PACK, 'check_site_facts.py')
FACTS = os.path.join(PACK, 'facts.json')
BUILDER = os.path.join(PACK, 'build_shopify_csv.py')
VALIDATOR = os.path.join(PACK, 'validate_shopify_csv.py')
SITE = os.environ.get('FULLBARS_SITE') or os.path.normpath(os.path.join(PACK, '..', '..', 'sites', 'full-bars'))
sys.path.insert(0, PACK)
sys.dont_write_bytecode = True      # leave no __pycache__ behind in the launch folder
import check_site_facts as C  # noqa: E402

# The table build_shopify_csv.py used before it read facts.json: the weights must not have changed.
OLD_HANDSET_G = {
    'iphone-12': 164, 'iphone-12-pro': 189, 'iphone-13-mini': 141, 'iphone-13': 174,
    'iphone-13-pro': 204, 'iphone-13-pro-max': 240, 'iphone-14': 172, 'iphone-14-plus': 203,
    'iphone-14-pro': 206, 'iphone-14-pro-max': 240, 'iphone-15': 171, 'iphone-15-plus': 201,
    'iphone-15-pro': 187, 'iphone-15-pro-max': 221, 'iphone-16': 170, 'iphone-16-pro': 199,
    'iphone-16-pro-max': 227, 'galaxy-s23': 168, 'pixel-8': 187,
}


def snapshot(root, skip=('__pycache__',)):
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in skip]
        for f in files:
            p = os.path.join(d, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return f.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


class SiteFactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(os.path.join(SITE, 'shop.html')):
            raise unittest.SkipTest(f'site not found at {SITE}')
        cls.live_before = snapshot(SITE)
        cls.pack_before = {k: v for k, v in snapshot(PACK).items() if not k.startswith('tests')}
        cls.tmp = tempfile.mkdtemp(prefix='site_facts_test_')
        cls.orig = os.path.join(cls.tmp, 'orig')
        shutil.copytree(SITE, cls.orig, ignore=shutil.ignore_patterns('*.png'))
        cls.facts = json.loads(read(FACTS))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        assert snapshot(SITE) == cls.live_before, 'the real site changed during the tests'
        now = {k: v for k, v in snapshot(PACK).items() if not k.startswith('tests')}
        # other tools may be edited by hand while this runs; these files must be untouched by the tests
        for k in ('facts.json', 'products-shopify.csv', 'products-shopify-legacy-headers.csv'):
            assert now.get(k) == cls.pack_before.get(k), f'{k} changed during the tests'

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix='case_', dir=self.tmp)
        self.site = os.path.join(self.work, 'site')
        shutil.copytree(self.orig, self.site)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # -------------------------------------------------------------------------------------------- helpers
    def run_tool(self, *args, site=None):
        r = subprocess.run([sys.executable, TOOL, '--site', site or self.site, *args], capture_output=True, text=True)
        out = r.stdout + r.stderr
        self.assertNotIn('Traceback', out, out)
        return r.returncode, out

    @staticmethod
    def fails(out):
        return [l for l in out.splitlines() if l.startswith('FAIL ')]

    def edit(self, rel, old, new, count=1):
        p = os.path.join(self.site, rel)
        s = read(p)
        self.assertEqual(s.count(old), count, f'{rel}: {old!r}')
        write(p, s.replace(old, new))

    def facts_copy(self, change):
        data = json.loads(json.dumps(self.facts))
        change(data['models'])
        p = os.path.join(self.work, 'facts.json')
        write(p, json.dumps(data, ensure_ascii=False, indent=2))
        return p

    def add_weight_column(self, wrong=None):
        """Add a Weight column after Port in the buying guide's comparison table, values from facts.json."""
        rel = 'guides/which-used-iphone-to-buy-2026.html'
        p = os.path.join(self.site, rel)
        s = read(p)
        a, b = s.index('<table'), s.index('</table>')
        t = s[a:b].replace('<th>Port</th>', '<th>Port</th><th>Weight</th>', 1)

        def cell(m):
            row = m.group(0)
            h = re.search(r'products/([a-z0-9-]+)\.html', row).group(1)
            w = (wrong or {}).get(h, self.facts['models'][h]['weight_g'])
            port = re.findall(r'<td[^>]*>.*?</td>', row)[5]
            return row.replace(port, port + f'<td>{w}&nbsp;g</td>', 1)

        t2 = re.sub(r'<tr><td><a href="\.\./products/.*?</tr>', cell, t)
        self.assertEqual(t2.count('&nbsp;g</td>'), 19)
        write(p, s[:a] + t2 + s[b:])

    # -------------------------------------------------------------------------------------------- basics
    def test_help(self):
        r = subprocess.run([sys.executable, TOOL, '--help'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for word in ('facts.json', '--site', '--where', 'Exit 2', 'never writes'):
            self.assertIn(word, r.stdout)

    def test_real_site_passes_with_no_conflicts(self):
        code, out = self.run_tool(site=SITE)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.fails(out), [])
        m = re.search(r'pages: (\d+)\s+models: (\d+)\s+checks: (\d+)\s+conflicts: 0', out)
        self.assertTrue(m, out)
        self.assertEqual((int(m.group(1)), int(m.group(2))), (56, 19))
        self.assertGreater(int(m.group(3)), 1500, 'far fewer mentions found than expected: matching has broken')

    def test_finds_every_kind_of_spec_on_many_pages(self):
        code, out = self.run_tool('--stats', site=SITE)
        self.assertEqual(code, 0, out)
        stats = {m.group(1): (int(m.group(2)), int(m.group(3)))
                 for m in re.finditer(r'^\s+(\w+)\s+(\d+)\s+\((\d+) pages\)', out, re.M)}
        for spec in ('weight_g', 'screen_in', 'chip', 'port', 'battery_hours', 'year', 'main_camera_mp',
                     'updates_until', 'ip_rating', 'apple_intelligence', 'promotion', 'telephoto_x'):
            n, pages = stats[spec]
            self.assertGreaterEqual(pages, 9 if spec == 'weight_g' else 20, f'{spec}: {stats[spec]}')

    def test_checker_never_writes(self):
        before = snapshot(self.site)
        self.run_tool()
        self.run_tool('--stats', '--where', 'iphone-13', 'chip')
        self.assertEqual(snapshot(self.site), before)

    # -------------------------------------------------------------------------------------------- facts.json
    def test_facts_cover_the_19_models_the_shop_sells(self):
        products = sorted(f[:-5] for f in os.listdir(os.path.join(SITE, 'products')) if f.endswith('.html'))
        self.assertEqual(sorted(self.facts['models']), products)
        self.assertEqual(len(products), 19)
        for h, m in self.facts['models'].items():
            src = read(os.path.join(SITE, 'products', h + '.html'))
            self.assertIn(f'data-model="{m["name"]}"', src)
            for k in C.REQUIRED:
                self.assertIn(k, m, f'{h} has no {k}')
        C.load_facts(FACTS)    # raises if malformed

    def test_facts_weights_are_the_builders_old_table(self):
        self.assertEqual({h: m['weight_g'] for h, m in self.facts['models'].items()}, OLD_HANDSET_G)
        self.assertEqual(self.facts['conflicts'], [])

    def test_facts_match_each_product_pages_own_spec_rows(self):
        """facts.json was populated from the product pages: spot-check the values against the spec rows."""
        for h, m in self.facts['models'].items():
            src = read(os.path.join(SITE, 'products', h + '.html'))
            rows = {C.to_text(a): C.to_text(b) for a, b in re.findall(r'<div><dt>(.*?)</dt><dd>(.*?)</dd></div>', src)}
            self.assertTrue(rows['Display'].startswith(m['screen_in'] + '-inch'), h)
            self.assertIn(m['chip'], rows['Chip'])
            self.assertTrue(rows['Connector'].startswith(m['port']), h)
            self.assertIn(f"{m['battery_hours']} hours", rows['Battery when new'])
            self.assertEqual(rows['Released'], str(m['year']))
            self.assertIn(m['updates_until'], rows['Software updates'])
            self.assertEqual('ProMotion' in rows['Display'], m['promotion'], h)
            self.assertEqual('Apple Intelligence' in rows['Highlights'], m['apple_intelligence'], h)

    def test_bad_facts_file_exits_2(self):
        p = os.path.join(self.work, 'broken.json')
        write(p, '{"models": ')
        code, out = self.run_tool('--facts', p)
        self.assertEqual(code, 2, out)
        p = self.facts_copy(lambda ms: ms['iphone-13'].pop('chip'))
        code, out = self.run_tool('--facts', p)
        self.assertEqual(code, 2, out)
        self.assertIn('iphone-13: "chip"', out)
        p = self.facts_copy(lambda ms: ms.pop('pixel-8'))
        code, out = self.run_tool('--facts', p)
        self.assertEqual(code, 2, out)
        self.assertIn('pixel-8', out)
        p = self.facts_copy(lambda ms: ms['iphone-15'].update(name='iPhone 15e'))
        code, out = self.run_tool('--facts', p)
        self.assertEqual(code, 2, out)

    # -------------------------------------------------------------------------------------------- planted errors
    def test_three_planted_errors_are_all_caught_and_nothing_else(self):
        # 1. a wrong weight in a comparison table (a Weight column added to the guide; 187 g for the 12 Pro)
        self.add_weight_column(wrong={'iphone-12-pro': 187})
        # 2. a wrong chip in prose
        self.edit('products/iphone-13-mini.html', 'It has the same A15 Bionic chip and main cameras as',
                  'It has the same A14 Bionic chip and main cameras as')
        # 3. a wrong update year in a spec row
        self.edit('products/iphone-14.html', '<dd>Major iOS updates expected until around 2028&ndash;2029',
                  '<dd>Major iOS updates expected until around 2029&ndash;2030')
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        fails = self.fails(out)
        self.assertEqual(len(fails), 3, out)
        self.assertTrue(any('which-used-iphone-to-buy-2026.html' in f and 'table "Weight" column, iPhone 12 Pro row' in f
                            and 'says 187g, facts.json says 189g' in f for f in fails), out)
        self.assertTrue(any('products/iphone-13-mini.html' in f and 'chip says A14' in f for f in fails), out)
        self.assertTrue(any('products/iphone-14.html' in f and 'spec row "Software updates"' in f
                            and 'says 2029–2030, facts.json says 2028–2029' in f for f in fails), out)

    def test_weight_column_with_right_values_passes(self):
        self.add_weight_column()
        code, out = self.run_tool('--where', 'iphone-12-pro', 'weight_g')
        self.assertEqual(code, 0, out)
        self.assertIn('[table "Weight" column, iPhone 12 Pro row] weight: 189g', out)

    def test_wrong_value_in_json_ld_only(self):
        p = os.path.join(self.site, 'products/galaxy-s23.html')
        s = read(p)
        i = s.index('<script type="application/ld+json">')
        j = s.index('</script>', i)
        self.assertEqual(s[i:j].count('light 168g body'), 1)
        write(p, s[:i] + s[i:j].replace('light 168g body', 'light 172g body') + s[j:])
        code, out = self.run_tool()
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.fails(out)), 1, out)
        self.assertIn('[JSON-LD Product description] Galaxy S23: weight says 172g, facts.json says 168g', out)

    def test_card_meta_and_data_attribute(self):
        self.edit('collections/iphone-13-series.html',
                  '<h3>iPhone 13 mini</h3><div class="card-meta">5.4&Prime; &middot; A15 Bionic',
                  '<h3>iPhone 13 mini</h3><div class="card-meta">5.8&Prime; &middot; A15 Bionic')
        s = read(os.path.join(self.site, 'shop.html'))
        tag = re.search(r'<article class="card"[^>]*data-usbc="1"[^>]*><a href="products/iphone-15\.html"', s).group(0)
        self.edit('shop.html', tag, tag.replace('data-usbc="1"', 'data-usbc="0"'))
        code, out = self.run_tool()
        fails = self.fails(out)
        self.assertEqual(len(fails), 2, out)
        self.assertIn('[card for iPhone 13 mini] iPhone 13 mini: screen size says 5.8-inch', out)
        self.assertIn('[card data-usbc for iPhone 15] iPhone 15: port says Lightning', out)

    def test_faq_yes_no_answers(self):
        self.edit('products/iphone-15.html',
                  'Does the iPhone 15 support Apple Intelligence?</summary><div class="ans"><p>No.',
                  'Does the iPhone 15 support Apple Intelligence?</summary><div class="ans"><p>Yes.')
        code, out = self.run_tool()
        self.assertTrue(any('FAQ Q&A' in f and 'Apple Intelligence says yes' in f for f in self.fails(out)), out)

    def test_relative_and_derived_figures(self):
        # "31g heavier than the iPhone 14" (203 - 172) and "expect roughly 16 hours" at 85% of 19
        self.edit('products/iphone-14-plus.html', 'it&rsquo;s 31g heavier than the iPhone 14',
                  'it&rsquo;s 35g heavier than the iPhone 14')
        self.edit('products/iphone-13.html', 'expect roughly 16 hours', 'expect roughly 18 hours')
        code, out = self.run_tool()
        fails = self.fails(out)
        self.assertEqual(len(fails), 2, out)
        self.assertIn('weight says a difference of 35g', out)
        self.assertIn('battery hours says roughly 18 hours at 85% health, facts.json says 19 hours, so roughly 16', out)

    def test_changing_a_fact_lists_every_page_to_fix(self):
        """Say the iPhone 14 Plus really weighed 205g: every page that states or depends on 203g must be listed."""
        p = self.facts_copy(lambda ms: ms['iphone-14-plus'].update(weight_g=205))
        code, out = self.run_tool('--facts', p)
        self.assertEqual(code, 1, out)
        text = '\n'.join(self.fails(out))
        self.assertIn('products/iphone-14-plus.html', text)          # "At 203g" and "31g heavier"
        self.assertIn('products/iphone-13-pro-max.html', text)       # "the iPhone 14 Plus (203g)" and "37g more"
        self.assertIn('a difference of 31g', text)
        self.assertIn('a difference of 37g', text)

    def test_where_takes_the_names_set_prices_takes(self):
        """--where MODEL accepts the page name, the name on the page, an alias or brand and model, in any case."""
        outs = []
        for model in ('iphone-12-pro', 'iPhone 12 Pro', 'IPHONE 12 PRO', 'iphone 12-pro', 'Apple iPhone 12 Pro'):
            code, out = self.run_tool('--where', model, 'weight_g')
            self.assertEqual(code, 0, (model, out))
            self.assertIn('iPhone 12 Pro weight:', out)
            outs.append(out)
        self.assertEqual(len(set(outs)), 1)
        code, out = self.run_tool('--where', 'Samsung Galaxy S23', 'weight_g')
        self.assertEqual(code, 0, out)
        self.assertIn('Galaxy S23 weight:', out)
        code, out = self.run_tool('--where', 'iPhone 13', 'weight_g')
        self.assertEqual(code, 0, out)
        self.assertIn('iPhone 13 weight:', out)            # not the 13 mini or 13 Pro
        code, out = self.run_tool('--where', 'iPhone 99')
        self.assertEqual(code, 2, out)
        self.assertIn('unknown model', out)

    # -------------------------------------------------------------------------------------------- no false alarms
    def test_matching_rules_avoid_false_alarms(self):
        ck = C.Checker(self.facts, SITE)
        cases = [
            # (page, sentence, expected number of conflicts)
            ('products/iphone-12-pro.html', 'The stainless-steel frame makes it 189g against 164g for the iPhone 12.', 0),
            ('products/iphone-12-pro.html', 'The stainless-steel frame makes it 187g against 164g for the iPhone 12.', 1),
            ('products/iphone-12-pro.html', 'The stainless-steel frame makes it 189g against 166g for the iPhone 12.', 1),
            ('collections/big-screen.html', 'They weigh around 200g.', 0),                     # approximate
            ('products/iphone-13-mini.html', 'Every main-line iPhone since has been 6.1 inches or larger.', 0),
            ('products/iphone-12.html', 'Every phone comes with a USB-C to Lightning cable and any USB-C power adapter works.', 0),
            ('collections/usb-c-iphones.html', 'Not all USB-C iPhones are equal.', 0),           # a range name
            ('products/iphone-14-plus.html', 'The screen runs at 60Hz rather than the 120Hz of the Pro models.', 0),
            ('products/iphone-14-plus.html', 'The screen runs at 120Hz.', 1),
            ('products/galaxy-s23.html', 'That is the difference from the Pixel 8, which has no telephoto lens.', 0),
            ('products/iphone-14-pro.html', 'Over the iPhone 13 Pro, you get a 48MP main camera.', 0),
            ('products/iphone-14-pro.html', 'Over the iPhone 13 Pro, you get a 12MP main camera.', 1),
            ('products/iphone-12-pro.html', 'The iPhone 13 Pro adds a 120Hz ProMotion screen.', 0),
            ('products/iphone-12-pro.html', 'The iPhone 13 Pro adds a 3x telephoto and the A15 chip.', 0),
            ('products/iphone-12-pro.html', 'The iPhone 13 Pro adds a 3x telephoto and the A14 chip.', 1),
            ('collections/iphone-14-series.html', 'All four use Lightning, and none supports Apple Intelligence.', 0),
            ('collections/iphone-14-series.html', 'All four use USB-C.', 1),
            ('collections/iphone-15-series.html', 'Every iPhone 15 has USB-C and a 48MP main camera.', 0),
            ('collections/iphone-15-series.html', 'Every iPhone 15 has a 120Hz ProMotion display.', 2),  # Hz + ProMotion
            ('guides/index.html', 'The new iPhone 17 Pro has a 48MP 8x telephoto and weighs 206g.', 0),  # not sold here
            ('collections/pro-models.html', 'The zoom grows: 2x on the iPhone 12 Pro, 3x on the 13 Pro and 5x on the iPhone 16 Pro.', 0),
            ('collections/pro-models.html', 'The zoom grows: 2x on the iPhone 12 Pro, 5x on the 13 Pro and 5x on the iPhone 16 Pro.', 1),
            ('collections/under-300.html', 'Security updates until around early 2028 (S23) and October 2030 (Pixel 8).', 0),
            ('collections/under-300.html', 'Security updates until around early 2028 (S23) and October 2031 (Pixel 8).', 1),
        ]
        for rel, sent, want in cases:
            ck.fails = []
            implicit = ck.page_models(rel, read(os.path.join(SITE, rel)))
            ck.check_prose_block(rel, 1, 'test', sent, implicit)
            self.assertEqual(len(ck.fails), want, f'{rel}: {sent}\n' + '\n'.join(ck.fails))

    # -------------------------------------------------------------------------------------------- CSV builder
    def build_csv(self, *args):
        out = os.path.join(self.work, 'csv')
        os.makedirs(out, exist_ok=True)
        r = subprocess.run([sys.executable, BUILDER, '--site', SITE, '--out', out, *args], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr, out

    def test_builder_csv_is_byte_identical_and_validates(self):
        code, msg, out = self.build_csv()
        self.assertEqual(code, 0, msg)
        for f in ('products-shopify.csv', 'products-shopify-legacy-headers.csv'):
            with open(os.path.join(out, f), 'rb') as a, open(os.path.join(PACK, f), 'rb') as b:
                self.assertEqual(a.read(), b.read(), f'{f} differs from the committed file')
        r = subprocess.run([sys.executable, VALIDATOR, os.path.join(out, 'products-shopify.csv'), '--site', SITE],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('42/42 checks passed', r.stdout)   # 41 before R7 added the all-original-parts check

    def test_builder_takes_weights_from_facts_json(self):
        p = self.facts_copy(lambda ms: ms['iphone-14'].update(weight_g=173))
        code, msg, out = self.build_csv('--facts', p)
        self.assertEqual(code, 0, msg)
        with open(os.path.join(out, 'products-shopify.csv'), encoding='utf-8', newline='') as f:
            new = list(csv.DictReader(f))
        with open(os.path.join(PACK, 'products-shopify.csv'), encoding='utf-8', newline='') as f:
            old = list(csv.DictReader(f))
        self.assertEqual(len(new), len(old))
        changed = 0
        for a, b in zip(old, new):
            if a['URL handle'] == 'iphone-14':
                self.assertEqual((a['Weight value (grams)'], b['Weight value (grams)']), ('372', '373'))
                a = dict(a, **{'Weight value (grams)': '373'})
                changed += 1
            self.assertEqual(a, b)
        self.assertGreater(changed, 0)

    def test_builder_stops_if_a_weight_is_missing(self):
        p = self.facts_copy(lambda ms: ms['pixel-8'].pop('weight_g'))
        code, msg, out = self.build_csv('--facts', p)
        self.assertNotEqual(code, 0, msg)
        self.assertIn('pixel-8', msg)
        self.assertFalse(os.path.exists(os.path.join(out, 'products-shopify.csv')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
