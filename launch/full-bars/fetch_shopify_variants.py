#!/usr/bin/env python3
"""Full Bars: fetch each phone's Shopify variant IDs, for go_live.py --shop-variants.

What it does, in plain English (for Ash)
----------------------------------------
On the Shopify route each product page's Order button goes to that phone's Shopify product. Without a variant ID
Shopify opens on its own first variant, which may be a different storage, condition, colour and price from the one
the customer picked on our page. This script asks your store for every phone's variants and writes them to a file:

    {"iphone-13": {"128GB|Good|Blue": "44012345678901", ...}, ...}

keyed exactly as products-shopify.csv names the options (Storage|Condition|Colour). Give that file to go_live.py and
each Order button opens Shopify on exactly the phone chosen (https://SHOP/products/iphone-13?variant=44012345678901):

    python3 launch/full-bars/fetch_shopify_variants.py --shop-url https://shop.fullbars.co.uk --out ~/shopify-variants.json
    python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout shopify \\
        --shop-url https://shop.fullbars.co.uk --shop-variants ~/shopify-variants.json --dry-run

Where the IDs come from
-----------------------
Shopify's public product data (the Ajax Product API): https://SHOP/products/<handle>.js lists the product's options
and each variant's id with its option values (option1, option2, option3). Shopify only serves it for a product that is
active and published to the Online Store, on a store whose password page is off, so run this on launch day, after you
publish the products. Shopify's product CSV export has no variant ID column, so there is no offline route.
Run it again whenever you add, delete or re-import variants (re-importing can give them new IDs), then rerun go_live.py.

usage: python3 launch/full-bars/fetch_shopify_variants.py --shop-url https://SHOP [--out FILE] [--shopify-csv CSV]
       [--handles iphone-13,pixel-8] [--delay SECONDS]
Exit codes: 0 = every phone and variant in the CSV found; 1 = something missing or refused (the file is still written
with what was found, and the report lists the gaps; a choice without an ID reads "Choose and pay on the next page");
2 = bad arguments, or nothing could be fetched at all (no file written). Python 3 standard library only.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import go_live  # noqa: E402  (same folder: its --shop-url rules and the CSV location)

# The option names products-shopify.csv uses, in the order of the key: storage|condition|colour
OPTION_NAMES = (('storage',), ('condition', 'grade'), ('colour', 'color'))
urlopen = urllib.request.urlopen   # tests replace this: no network in tests


class Problem(Exception):
    """A product that couldn't be fetched or read, with the reason in plain English."""


def csv_options(path):
    """{handle: {(storage, condition, colour)}} from a Shopify product CSV (current or older column names)."""
    with open(path, encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return {}
    head = rows[0].keys()
    hcol = 'URL handle' if 'URL handle' in head else 'Handle'

    def col(n):
        for name in (f'Option{n} value', f'Option{n} Value'):
            if name in head:
                return name
        raise ValueError(f'{path} has no Option{n} value column')
    cols = [col(1), col(2), col(3)]
    out = {}
    for r in rows:
        h = (r.get(hcol) or '').strip()
        if h and all((r.get(c) or '').strip() for c in cols):
            out.setdefault(h, set()).add(tuple(r[c].strip() for c in cols))
    return out


def fetch(url, timeout=20, tries=2):
    """The product data at url, parsed. Raises Problem with a plain reason."""
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'FullBars-variant-ids/1.0'})
    for attempt in range(tries):
        try:
            with urlopen(req, timeout=timeout) as r:
                final, ctype, body = r.geturl(), r.headers.get('Content-Type', ''), r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt + 1 < tries:
                wait = e.headers.get('Retry-After', '2') if e.headers else '2'
                time.sleep(min(10.0, float(wait) if re.fullmatch(r'\d+(?:\.\d+)?', str(wait)) else 2.0))
                continue
            if e.code == 404:
                raise Problem('not found (404): the product isn\'t active and published to the Online Store, or its URL '
                              'handle in Shopify differs from the page name')
            if e.code in (401, 403):
                raise Problem(f'refused ({e.code}): the store is probably still behind its password page')
            raise Problem(f'Shopify answered {e.code}')
        except urllib.error.URLError as e:
            raise Problem(f'couldn\'t reach the store ({e.reason})')
        except OSError as e:
            raise Problem(f'couldn\'t reach the store ({e})')
    if '/password' in final:
        raise Problem('the store sent its password page: turn the password page off (Online Store > Preferences) first')
    try:
        data = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise Problem(f'Shopify sent a web page ({ctype or "unknown type"}), not product data: is the password page on?')
    if not isinstance(data, dict) or not isinstance(data.get('variants'), list):
        raise Problem('the product data has no list of variants')
    return data


def option_positions(product):
    """[i, j, k]: the variant option index (0-2) holding storage, condition and colour, by the product's option names.
    Falls back to the CSV's order (Storage, Condition, Colour) when the names are missing or unexpected."""
    names = []
    for o in product.get('options') or []:
        names.append((o.get('name') if isinstance(o, dict) else o) or '')
    pos = []
    for wanted in OPTION_NAMES:
        i = next((k for k, n in enumerate(names) if str(n).strip().lower() in wanted), None)
        pos.append(i)
    return pos if None not in pos and len(set(pos)) == 3 else [0, 1, 2]


def variant_values(v):
    """The variant's three option values, from option1..option3 or its options list."""
    vals = [v.get('option1'), v.get('option2'), v.get('option3')]
    if any(x is None for x in vals) and isinstance(v.get('options'), list):
        vals = [(o.get('value') if isinstance(o, dict) else o) for o in v['options']] + [None, None, None]
    return [None if x is None else str(x).strip() for x in vals[:3]]


def variant_ids(product, want):
    """({"storage|condition|colour": id digits} for the variants that match want, [Shopify variants that don't])."""
    pos = option_positions(product)
    ids, odd = {}, []
    for v in product['variants']:
        vals = variant_values(v)
        key = tuple(vals[i] for i in pos) if None not in vals else None
        vid = go_live.variant_id(v.get('id'))
        label = ' / '.join(x for x in vals if x) or str(v.get('title') or '?')
        if key is None or vid is None:
            odd.append(f'{label} (no usable option values or id)')
        elif want and key not in want:
            odd.append(f'{label} (not in the CSV: renamed in Shopify?)')
        else:
            ids['|'.join(key)] = vid
    return ids, odd


def parse_args(argv):
    ap = argparse.ArgumentParser(prog='fetch_shopify_variants.py',
                                 description='Fetch each phone\'s Shopify variant IDs for go_live.py --shop-variants. '
                                             'Plain-English guide: the top of this file.')
    ap.add_argument('--shop-url', dest='shop_url', required=True, metavar='https://SHOP',
                    help='your Shopify store\'s own address, as you give it to go_live.py (not a /products/ page)')
    ap.add_argument('--out', default='shopify-variants.json', metavar='FILE',
                    help='where to write the IDs (default: shopify-variants.json in the current folder)')
    ap.add_argument('--shopify-csv', dest='shopify_csv', default=go_live.SHOPIFY_CSV, metavar='CSV',
                    help='the product CSV you imported, for the handles and option values (default: products-shopify.csv)')
    ap.add_argument('--handles', help='only these handles, comma-separated (default: every product in the CSV)')
    ap.add_argument('--delay', type=float, default=0.5, metavar='SECONDS', help='pause between requests (default 0.5)')
    return ap.parse_args(argv)


def main(argv=None):
    opt = parse_args(argv)
    try:
        shop = go_live.parse_shop_url(opt.shop_url)
    except go_live.Fail as e:
        print(f'fetch_shopify_variants.py: {e}', file=sys.stderr)
        return 2
    try:
        want_all = csv_options(opt.shopify_csv)
    except (OSError, ValueError, csv.Error) as e:
        print(f'fetch_shopify_variants.py: can\'t read {opt.shopify_csv} ({e})', file=sys.stderr)
        return 2
    handles = [h.strip() for h in opt.handles.split(',') if h.strip()] if opt.handles else sorted(want_all)
    if not handles:
        print(f'fetch_shopify_variants.py: no products in {opt.shopify_csv}', file=sys.stderr)
        return 2
    out, lines, gaps = {}, [], 0
    for n, h in enumerate(handles):
        if n and opt.delay > 0:
            time.sleep(opt.delay)
        want = want_all.get(h, set())
        url = f'{shop}/products/{h}.js'
        try:
            ids, odd = variant_ids(fetch(url), want)
        except Problem as e:
            lines.append(f'  {h}: FAILED: {e} ({url})')
            gaps += 1
            continue
        missing = sorted('|'.join(k) for k in want if '|'.join(k) not in ids)
        if ids:
            out[h] = dict(sorted(ids.items()))
        line = f'  {h}: {len(ids)} of {len(want) if want else len(ids)} variant ID(s)'
        if missing:
            line += f'; none in Shopify for {len(missing)}: {", ".join(missing[:6])}{" ..." if len(missing) > 6 else ""}'
        if odd:
            line += f'; left out {len(odd)} Shopify variant(s) that don\'t match the CSV: {", ".join(odd[:4])}{" ..." if len(odd) > 4 else ""}'
        if missing or odd or not want:
            gaps += 1
        if not want:
            line += ' (this handle isn\'t in the CSV, so its option values weren\'t checked)'
        lines.append(line)
    print(f'Shopify variant IDs from {shop} ({len(handles)} product(s))')
    print('\n'.join(lines))
    if not out:
        print('Nothing could be fetched, so no file was written. Publish the products to the Online Store, turn the store\'s '
              'password page off, check --shop-url, and run this again.')
        return 2
    with open(opt.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write('\n')
    total = sum(len(v) for v in out.values())
    print(f'Wrote {opt.out}: {total} variant ID(s) for {len(out)} product(s).'
          + (f' {gaps} product(s) have gaps (above): their missing choices read "Choose and pay on the next page".' if gaps else ''))
    print(f'Next: python3 launch/full-bars/go_live.py --site <your copy> --domain <your domain> --checkout shopify '
          f'--shop-url {shop} --shop-variants {opt.out} --dry-run')
    return 1 if gaps else 0


if __name__ == '__main__':
    sys.exit(main())
