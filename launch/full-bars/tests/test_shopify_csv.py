#!/usr/bin/env python3
"""Tests for build_shopify_csv.py and validate_shopify_csv.py: the replaced-parts line every Shopify listing carries.

Run from the repo root:  python3 launch/full-bars/tests/test_shopify_csv.py
The real site folder and the committed CSVs are only ever read; builds go to a temporary folder.
Python 3 standard library only.
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PACK))
SITE = os.path.join(REPO, 'sites', 'full-bars')
BUILD = os.path.join(PACK, 'build_shopify_csv.py')
VALIDATE = os.path.join(PACK, 'validate_shopify_csv.py')
# The site's own wording: "If a part has been replaced, we tell you before you pay", "Phones with any replaced part are
# sold by email order only, so you always hear about it before paying". Shopify takes payment at checkout.
PARTS = 'Every phone sold through this listing has all original manufacturer parts.'
CHECK = 'description: says every phone on the listing has all original manufacturer parts'

sys.dont_write_bytecode = True


def run(*cmd):
    r = subprocess.run([sys.executable, '-B'] + list(cmd), capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def read_rows(path):
    with open(path, encoding='utf-8', newline='') as fh:
        return list(csv.reader(fh))


class ShopifyCsvTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='shopify_csv_test_')
        code, out = run(BUILD, '--site', SITE, '--out', cls.tmp)
        assert code == 0, out
        cls.csv = os.path.join(cls.tmp, 'products-shopify.csv')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_listing_says_all_original_parts(self):
        rows = read_rows(self.csv)
        head = rows[0]
        firsts = [r for r in rows[1:] if r[head.index('Title')]]
        self.assertEqual(len(firsts), 19)
        for r in firsts:
            desc = r[head.index('Description')]
            self.assertIn(f'<p>{PARTS} Phones with any replaced part are sold by email order only, so you always hear about '
                          'it before paying.</p>', desc, r[head.index('URL handle')])
        code, out = run(VALIDATE, self.csv, '--site', SITE)
        self.assertEqual(code, 0, out)
        self.assertIn(f'PASS  {CHECK}', out)

    def test_validator_requires_the_parts_line(self):
        rows = read_rows(self.csv)
        i = rows[0].index('Description')
        rows[1][i] = rows[1][i].replace(PARTS, '')
        bad = os.path.join(self.tmp, 'missing-line.csv')
        with open(bad, 'w', encoding='utf-8', newline='') as fh:
            csv.writer(fh, lineterminator='\n').writerows(rows)
        code, out = run(VALIDATE, bad, '--site', SITE)
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r'FAIL  ' + CHECK + r'\s+1 product\(s\) without it')


if __name__ == '__main__':
    unittest.main(verbosity=2)
