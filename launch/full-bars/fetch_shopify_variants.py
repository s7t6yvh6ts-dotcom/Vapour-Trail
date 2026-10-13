#!/usr/bin/env python3
"""Full Bars: read each phone's live Shopify data for the static site: variant IDs (go_live.py --shop-variants), a price
check against the site's prices (--check-prices) and a stock snapshot for stock.js (--write-stock).

What it does, in plain English (for Ash)
----------------------------------------
On the Shopify route the static site is the information front and every Order button goes to Shopify. This script
asks your store for every phone's variants (storage, condition and colour) and can do three things with the answer:

1. Variant IDs (--out FILE). Without them Shopify opens each product on its own first variant, which may be another
   storage, condition, colour and price from the one picked on our page. The file is keyed exactly as
   products-shopify.csv names the options (Storage|Condition|Colour):
       {"iphone-13": {"128GB|Good|Blue": "44012345678901", ...}, ...}
   Give it to go_live.py --shop-variants and each Order button opens Shopify on exactly the phone chosen.

2. Price check (--check-prices). Compares every Shopify variant's price with the site's data-prices for that phone
   (the price depends on storage and condition, not colour) and lists every one that differs: handle, variant, site
   price, Shopify price. Exit code 3 if any differ. Run it after every price change, and before every deploy on the
   Shopify route (GO-LIVE.md sections 1 and 7): set_prices.py only changes the site, and Shopify's prices are changed
   in Shopify admin (Products > Bulk edit), never by importing the CSV again.

3. Stock snapshot (--write-stock PATH, normally <your live site folder>/stock.js). Writes stock.js from each variant's
   "available" flag: for each phone, the number of available variants per storage|condition, any colour counting 1
   each; a phone with nothing available gets {} (its cards say "None in stock right now"). site.js then shows "Not
   in stock — ask us" for a storage and condition Shopify can't sell, instead of an Order button that lands on a
   sold-out Shopify page. A phone whose available flags can't be read, or with an available variant that matches no
   storage and condition on its page (an option renamed in Shopify), is left out: all its options show as orderable.
   It is a snapshot: run it again and deploy the site whenever stock changes in Shopify (straight after you add stock,
   and at least daily). A stale snapshot never sells a phone Shopify doesn't have (Shopify refuses
   a sold-out variant), but it is wrong both ways until you fetch again: a phone sold since still shows as in stock
   (its button opens a sold-out Shopify page), and a phone added since shows "Not in stock — ask us".

    python3 launch/full-bars/fetch_shopify_variants.py --shop-url https://shop.fullbars.co.uk --out ~/shopify-variants.json
    python3 launch/full-bars/fetch_shopify_variants.py --shop-url https://shop.fullbars.co.uk --check-prices \\
        --write-stock sites/full-bars/stock.js --save-dump ~/shopify-products.json

--save-dump FILE keeps exactly what Shopify sent, with the time it was fetched; --from-dump FILE reads it back instead
of the network (to compare the site with what Shopify had, say after set_prices.py, and for the tests, which never touch
the network). A saved copy is never a live check: the report says how old it is, a snapshot written from it is stamped
with the time the copy was fetched (or "time unknown" if the file doesn't say, or says a time in the future), so
go_live.py warns once it is more than 24 hours old, and the price check never ends "Price check: passed" from a copy.
Before a deploy, always fetch live with --shop-url (GO-LIVE.md section 7).

Where the data comes from
-------------------------
Shopify's public product data (the Ajax Product API): https://SHOP/products/<handle>.js lists the product's options
and its variants, each with its id, its option values (option1, option2, option3), its price and an "available" flag.
Shopify only serves it for a product that is active and published to the Online Store, on a store whose password page
is off, so run this once the products are published. Shopify's product CSV export has no variant ID column, so there
is no offline route to the IDs. Prices: Shopify's reference shows each variant's price as a whole number of pence
(12900 for £129.00); a string of digits is read the same way, and a decimal string ("129.00", as Shopify's admin
APIs write prices) as pounds. Money comes back in the store's currency for the visitor, so the store must sell in GBP
only (GO-LIVE.md section 5, step 1). A product's data lists at most 250 variants (Full Bars' largest has 54).
Fetch again whenever you add, delete or re-import variants (re-importing can give them new IDs), then rerun go_live.py.

usage: python3 launch/full-bars/fetch_shopify_variants.py (--shop-url https://SHOP | --from-dump FILE) [--out FILE]
       [--check-prices] [--write-stock PATH] [--site DIR] [--save-dump FILE] [--shopify-csv CSV]
       [--handles iphone-13,pixel-8] [--delay SECONDS]
Without --check-prices or --write-stock it writes the variant IDs to --out (default shopify-variants.json); with either,
it writes them only if you give --out.
Exit codes: 0 = every phone and variant found (and, with --check-prices, every price matches); 1 = something missing or
refused (the files are still written with what was found, and the report lists the gaps), or --check-prices or
--write-stock from a saved copy more than 24 hours old or of unknown age; 2 = bad arguments, or nothing could be fetched
at all (no file written); 3 = --check-prices found a price that differs from the site (takes precedence over 1). Only a
live fetch (--shop-url) ends "Price check: passed". Python 3 standard library only.
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.normpath(os.path.join(HERE, '..', '..', 'sites', 'full-bars'))
sys.path.insert(0, HERE)
import go_live  # noqa: E402  (same folder: its --shop-url rules, the CSV location and the stock.js reader)

# The option names products-shopify.csv uses, in the order of the key: storage|condition|colour
OPTION_NAMES = (('storage',), ('condition', 'grade'), ('colour', 'color'))
MAX_VARIANTS = 250                 # Shopify's product data lists at most this many variants
SNAPSHOT_MARK = 'Shopify stock snapshot:'
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


def check_product(data):
    """data, if it looks like Shopify's product data (a variants list); else Problem."""
    if not isinstance(data, dict) or not isinstance(data.get('variants'), list):
        raise Problem('the product data has no list of variants')
    return data


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
    return check_product(data)


def parse_fetched(value):
    """The time a dump was fetched ("2026-10-13T09:05:00Z", as --save-dump writes it) as an aware UTC datetime, or None
    if it is missing or can't be read. A time without a time zone is unknown too: it can't be placed."""
    if not isinstance(value, str):
        return None
    try:
        t = datetime.datetime.fromisoformat(value.strip().replace('Z', '+00:00').replace('z', '+00:00'))
    except ValueError:
        return None
    return t.astimezone(datetime.timezone.utc) if t.tzinfo else None


def load_dump(path):
    """(shop address or None, fetched time or None, {handle: product data}) from a --save-dump file (or a plain
    {handle: product data}, which has no time)."""
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(f'can\'t read {path} ({e})')
    shop, fetched = None, None
    if isinstance(data, dict) and isinstance(data.get('products'), dict):
        shop = data.get('shop') if isinstance(data.get('shop'), str) else None
        fetched, data = parse_fetched(data.get('fetched')), data['products']
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, dict) for k, v in data.items()):
        raise ValueError(f'{path} isn\'t a product dump: it must be {{"products": {{"<handle>": <product data>}}}}, as '
                         '--save-dump writes it')
    return shop, fetched, data


def copy_age(fetched, now):
    """How a saved copy is described in the report: when it was fetched, and how long ago."""
    if fetched is None:
        return 'fetched at an unknown time (the file doesn\'t say when)'
    return f'fetched {fetched:%Y-%m-%d %H:%M} UTC ({go_live.age_words(fetched, now)})'


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


def variant_key(v, pos):
    """(storage, condition, colour) of a variant, or None if its option values can't be read."""
    vals = variant_values(v)
    return tuple(vals[i] for i in pos) if None not in vals else None


def variant_label(v):
    vals = variant_values(v)
    return ' / '.join(x for x in vals if x) or str(v.get('title') or '?')


def variant_ids(product, want):
    """({"storage|condition|colour": id digits} for the variants that match want, [Shopify variants that don't])."""
    pos = option_positions(product)
    ids, odd = {}, []
    for v in product['variants']:
        key = variant_key(v, pos)
        vid = go_live.variant_id(v.get('id'))
        label = variant_label(v)
        if key is None or vid is None:
            odd.append(f'{label} (no usable option values or id)')
        elif want and key not in want:
            odd.append(f'{label} (not in the CSV: renamed in Shopify?)')
        else:
            ids['|'.join(key)] = vid
    return ids, odd


# ------------------------------------------------------------------------------------------------ prices
def price_pence(v):
    """A Shopify variant price in pence, or None if it can't be read. Shopify's Ajax Product API reference shows it as a
    whole number of pence (12900 for £129.00); a string of digits is read the same way, and a decimal string ("129.00",
    as the admin APIs write it) as pounds. Anything else (a fraction of a penny, a negative, true/false) is unreadable."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if v >= 0 else None
    if isinstance(v, float):
        return int(v) if v >= 0 and v.is_integer() else None
    if isinstance(v, str):
        t = v.strip()
        if re.fullmatch(r'\d+', t):
            return int(t)
        m = re.fullmatch(r'(\d+)\.(\d{1,2})', t)
        if m:
            return int(m.group(1)) * 100 + int(m.group(2).ljust(2, '0'))
    return None


def gbp(pence):
    return f'£{pence // 100:,}' if pence % 100 == 0 else f'£{pence // 100:,}.{pence % 100:02d}'


def site_page(site, handle):
    p = os.path.join(site, 'products', handle + '.html')
    if not os.path.isfile(p):
        return None
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def site_prices(src):
    """{"storage|condition": price in pence} from a product page's data-prices, or None if it can't be read."""
    m = go_live.PICKER_TAG.search(src or '')
    try:
        raw = json.loads(go_live.attr(m.group(0), 'data-prices')) if m else None
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    out = {}
    for st, grades in raw.items():
        for gr, p in (grades or {}).items() if isinstance(grades, dict) else ():
            if isinstance(p, (int, float)) and not isinstance(p, bool) and p > 0:
                out[f'{st}|{gr}'] = int(round(p * 100))
    return out


def price_mismatches(product, prices):
    """[(variant "storage|condition|colour", site price in pence or None, Shopify's price as given, Shopify pence or None)]
    for every variant whose price isn't the site's price for its storage and condition. Colour never changes a price."""
    pos = option_positions(product)
    bad = []
    for v in product['variants']:
        key = variant_key(v, pos)
        shop_p = price_pence(v.get('price'))
        if key is None:
            bad.append((variant_label(v), None, v.get('price'), shop_p))
            continue
        site_p = prices.get(f'{key[0]}|{key[1]}')
        if site_p is None or shop_p is None or site_p != shop_p:
            bad.append(('|'.join(key), site_p, v.get('price'), shop_p))
    return bad


# ------------------------------------------------------------------------------------------------ stock
def stock_counts(product, pairs):
    """({"storage|condition": available variants} with only the ones above 0, [variants left out]) from each variant's
    "available" flag, any colour counting 1. pairs: the storage|condition pairs the page offers (a variant outside them
    is left out). Raises Problem when the flags can't be read: then the phone gets no stock data at all, so the site
    never shows a phone Shopify might sell as out of stock."""
    if len(product['variants']) >= MAX_VARIANTS:
        raise Problem(f'Shopify lists at most {MAX_VARIANTS} variants per product and this one has {len(product["variants"])}, '
                      'so some may be missing: left out of the stock snapshot')
    pos = option_positions(product)
    counts, left_out, sellable = {}, [], []
    for v in product['variants']:
        if not isinstance(v.get('available'), bool):
            raise Problem(f'variant {variant_label(v)} has no true/false "available" flag, so its stock can\'t be read: '
                          'left out of the stock snapshot')
        key = variant_key(v, pos)
        pair = f'{key[0]}|{key[1]}' if key else None
        if pair is None or (pairs and pair not in pairs):
            (sellable if v['available'] else left_out).append(f'{variant_label(v)} (not a storage and condition on the page)')
            continue
        if v['available']:
            counts[pair] = counts.get(pair, 0) + 1
    if sellable:
        # Shopify can sell it, but we can't tell which of the page's choices it is (an option renamed in Shopify?).
        # Partial counts would mark that choice "Not in stock — ask us", so the phone gets no stock data at all
        raise Problem(f'{len(sellable)} variant(s) Shopify says are available don\'t match a storage and condition on the '
                      f'page: {", ".join(sellable[:4])}{" ..." if len(sellable) > 4 else ""}. Left out of the stock snapshot '
                      '(all its options show as orderable) until the option values in Shopify match the page again')
    order = {p: i for i, p in enumerate(pairs or ())}   # the page's own order (128GB before 1TB), then any others
    return dict(sorted(counts.items(), key=lambda kv: (order.get(kv[0], len(order)), kv[0]))), left_out


def stock_header(path, site):
    """The comment that heads stock.js: the one already in path (or else in the site's own stock.js), without an
    earlier snapshot line, so the file keeps its explanation of the format."""
    for p in (path, os.path.join(site, go_live.STOCK_JS)):
        try:
            with open(p, encoding='utf-8') as fh:
                src = fh.read()
        except OSError:
            continue
        m = re.search(r'^window\.FULLBARS_STOCK\s*=', src, re.M)
        if m:
            head = re.sub(r'(?m)^/\* ' + re.escape(SNAPSHOT_MARK) + r'.*?\*/[ \t]*\n', '', src[:m.start()])
            return head if head.endswith('\n') or not head else head + '\n'
    return ('/* Full Bars - stock, read by site.js as window.FULLBARS_STOCK: for each phone (its page name), the units held '
            'per\n   "storage|condition", every colour counted together. A storage and condition that is missing, or 0, '
            'is not in\n   stock; {} means none of that phone. JSON only: keys in double quotes, counts as whole numbers. */\n')


def stock_js(entries, header, shop, when, saved_copy=False):
    """The text of stock.js for these entries, as go_live.py reads it (JSON after "window.FULLBARS_STOCK ="). when is the
    time Shopify sent the data (aware UTC), or None if nobody knows (a saved copy with no time): then the snapshot says
    "time unknown" and go_live.py treats it as stale."""
    lines = [f'  {json.dumps(h, ensure_ascii=False)}: {json.dumps(entries[h], ensure_ascii=False)}' for h in sorted(entries)]
    stamp_time = f'{when:%Y-%m-%d %H:%M} UTC' if when else 'time unknown'
    shop = re.sub(r'\s+', '-', str(shop or 'unknown-store'))   # one word, as go_live.py reads the line
    stamp = (f'/* {SNAPSHOT_MARK} {stamp_time} from {shop} ({len(entries)} phones), written by '
             f'fetch_shopify_variants.py --write-stock{" from a saved copy (--from-dump)" if saved_copy else ""}. '
             'Fetch again and deploy whenever stock changes. */\n')
    body = 'window.FULLBARS_STOCK = {\n' + ',\n'.join(lines) + ('\n' if lines else '') + '};\n'
    return header + stamp + body


def write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.fetch-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ------------------------------------------------------------------------------------------------ main
def parse_args(argv):
    ap = argparse.ArgumentParser(prog='fetch_shopify_variants.py',
                                 description='Read each phone\'s Shopify data: variant IDs for go_live.py --shop-variants, '
                                             'a price check against the site, and a stock.js snapshot. '
                                             'Plain-English guide: the top of this file.')
    ap.add_argument('--shop-url', dest='shop_url', metavar='https://SHOP',
                    help='your Shopify store\'s own address, as you give it to go_live.py (not a /products/ page). '
                         'Needed unless you use --from-dump')
    ap.add_argument('--from-dump', dest='from_dump', metavar='FILE',
                    help='read the product data from a file --save-dump wrote, instead of from the store (no network)')
    ap.add_argument('--save-dump', dest='save_dump', metavar='FILE',
                    help='also save the product data exactly as Shopify sent it, for a later --from-dump')
    ap.add_argument('--out', metavar='FILE',
                    help='where to write the variant IDs (default: shopify-variants.json in the current folder, unless '
                         '--check-prices or --write-stock is given, when they are written only if you name a file)')
    ap.add_argument('--check-prices', dest='check_prices', action='store_true',
                    help='compare every Shopify variant\'s price with the site\'s data-prices (exit 3 if any differ)')
    ap.add_argument('--write-stock', dest='write_stock', metavar='PATH',
                    help='write a stock.js snapshot from each variant\'s "available" flag (normally <site>/stock.js)')
    ap.add_argument('--site', metavar='DIR',
                    help='the site folder whose product pages to compare with (default: the folder --write-stock writes '
                         'into, if it is a site folder, else sites/full-bars)')
    ap.add_argument('--shopify-csv', dest='shopify_csv', default=go_live.SHOPIFY_CSV, metavar='CSV',
                    help='the product CSV you imported, for the handles and option values (default: products-shopify.csv)')
    ap.add_argument('--handles', help='only these handles, comma-separated (default: every product in the CSV, plus every '
                                      'product page with --check-prices)')
    ap.add_argument('--delay', type=float, default=0.5, metavar='SECONDS', help='pause between requests (default 0.5)')
    return ap.parse_args(argv)


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors='replace')
    except AttributeError:
        pass
    opt = parse_args(argv)
    err = lambda msg: print(f'fetch_shopify_variants.py: {msg}', file=sys.stderr) or 2  # noqa: E731
    if not opt.shop_url and not opt.from_dump:
        return err('give --shop-url https://SHOP (your store) or --from-dump FILE (a saved copy of its product data)')
    shop, dump, fetched = None, None, None
    try:
        if opt.shop_url:
            shop = go_live.parse_shop_url(opt.shop_url)
    except go_live.Fail as e:
        return err(e)
    if opt.from_dump:
        try:
            dump_shop, fetched, dump = load_dump(opt.from_dump)
        except ValueError as e:
            return err(e)
        shop = shop or (dump_shop.rstrip('/') if dump_shop else None)
    for flag, path in (('--out', opt.out), ('--save-dump', opt.save_dump), ('--write-stock', opt.write_stock)):
        if path and os.path.isdir(path):
            return err(f'{flag} {path} is a folder, not a file')
        if path and not os.path.isdir(os.path.dirname(os.path.abspath(path))):
            return err(f'{flag} {path}: there is no folder {os.path.dirname(os.path.abspath(path))}')
    out_path = opt.out if (opt.out or opt.check_prices or opt.write_stock) else 'shopify-variants.json'
    site = opt.site
    if site is None:
        ws_dir = os.path.dirname(os.path.abspath(opt.write_stock)) if opt.write_stock else None
        site = ws_dir if ws_dir and os.path.isdir(os.path.join(ws_dir, 'products')) else SITE
    if (opt.check_prices or opt.write_stock) and not os.path.isdir(os.path.join(site, 'products')):
        return err(f'{site} is not the Full Bars site folder (no products/ folder): give --site')
    try:
        want_all = csv_options(opt.shopify_csv)
    except (OSError, ValueError, csv.Error) as e:
        return err(f'can\'t read {opt.shopify_csv} ({e})')
    if opt.handles:
        handles = [h.strip() for h in opt.handles.split(',') if h.strip()]
    else:
        pages = set()
        if opt.check_prices:
            pages = {f[:-len('.html')] for f in os.listdir(os.path.join(site, 'products')) if f.endswith('.html')}
        handles = sorted(set(want_all) | pages)
    if not handles:
        return err(f'no products in {opt.shopify_csv}')

    out, lines, gaps, raw = {}, [], 0, {}
    stock, stock_notes = {}, []
    mismatches, compared, price_notes = [], 0, []
    fetched_from_network = False
    for n, h in enumerate(handles):
        want = want_all.get(h, set())
        url = f'{shop}/products/{h}.js' if shop else f'(dump)/{h}'
        try:
            if dump is not None:
                if h not in dump:
                    raise Problem('not in the dump')
                product = check_product(dump[h])
            else:
                if fetched_from_network and opt.delay > 0:
                    time.sleep(opt.delay)
                fetched_from_network = True
                product = fetch(url)
            ids, odd = variant_ids(product, want)
        except Problem as e:
            lines.append(f'  {h}: FAILED: {e} ({url if dump is None else opt.from_dump})')
            gaps += 1
            continue
        raw[h] = product
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
        src = site_page(site, h) if (opt.check_prices or opt.write_stock) else None
        prices = site_prices(src) if src is not None else None
        if opt.check_prices:
            if src is None:
                price_notes.append(f'{h}: no product page on the site (products/{h}.html), so its prices weren\'t compared')
            elif not prices:
                price_notes.append(f'{h}: products/{h}.html has no readable data-prices, so its prices weren\'t compared '
                                   '(check_site_prices.py says why)')
                gaps += 1
            else:
                compared += len(product['variants'])
                mismatches += [(h,) + b for b in price_mismatches(product, prices)]
        if opt.write_stock and src is None:
            stock_notes.append(f'{h}: no product page on the site (products/{h}.html), so it isn\'t in the stock snapshot')
        elif opt.write_stock:
            pairs = list(prices) if prices else sorted({f'{k[0]}|{k[1]}' for k in want})
            try:
                counts, left_out = stock_counts(product, pairs)
            except Problem as e:
                stock_notes.append(f'{h}: {e}')
                continue
            stock[h] = counts
            if left_out:
                stock_notes.append(f'{h}: {len(left_out)} Shopify variant(s) left out of the stock: {", ".join(left_out[:4])}'
                                   f'{" ..." if len(left_out) > 4 else ""}')
    now = datetime.datetime.now(datetime.timezone.utc)
    if dump is None:
        when, copy_state = now, None
        print(f'Shopify data from {shop}, fetched live ({len(handles)} product(s))')
    else:
        # A saved copy is only as fresh as the day it was fetched: its snapshot and price check carry that time, never now
        copy_state = go_live.staleness(fetched, now)          # None (at most 24 hours old), 'old', 'unknown' or 'future'
        when = None if copy_state in ('unknown', 'future') else fetched
        print(f'Shopify data from a saved copy ({opt.from_dump}) of {shop or "an unnamed store"}, {copy_age(fetched, now)} '
              f'({len(handles)} product(s)). Not a live check.')
        if copy_state:
            why = {'old': 'it is more than 24 hours old',
                   'unknown': 'it doesn\'t say when it was fetched, so it counts as stale',
                   'future': 'its fetch time is in the future, so its age can\'t be trusted and it counts as stale'}[copy_state]
            print(f'NOT LIVE: {why}. Shopify\'s prices and stock may have changed since. Before a deploy, fetch live with '
                  '--shop-url.')
    print('\n'.join(lines))
    if not raw:
        print('Nothing could be fetched, so no file was written. Publish the products to the Online Store, turn the store\'s '
              'password page off, check --shop-url, and run this again.')
        return 2
    if opt.save_dump:
        saved = {'shop': shop, 'products': raw}
        if when:   # a copy of a copy keeps the original fetch time; an unknown one stays unknown
            saved['fetched'] = when.strftime('%Y-%m-%dT%H:%M:%SZ')
        with open(opt.save_dump, 'w', encoding='utf-8') as fh:
            json.dump(saved, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write('\n')
        print(f'Saved the product data Shopify sent to {opt.save_dump} (check it again offline with --from-dump).')
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write('\n')
        total = sum(len(v) for v in out.values())
        print(f'Wrote {out_path}: {total} variant ID(s) for {len(out)} product(s).'
              + (f' {gaps} product(s) have gaps (above): their missing choices read "Choose and pay on the next page".' if gaps else ''))
        print(f'Next: python3 launch/full-bars/go_live.py --site <your copy> --domain <your domain> --checkout shopify '
              f'--shop-url {shop or "<your shop>"} --shop-variants {out_path} --dry-run')
    code = 1 if gaps else 0
    if opt.write_stock:
        header = stock_header(opt.write_stock, site)
        write_atomic(opt.write_stock, stock_js(stock, header, shop or opt.from_dump, when, saved_copy=dump is not None))
        none = sorted(h for h, c in stock.items() if not c)
        print(f'Wrote {opt.write_stock}: a stock snapshot for {len(stock)} phone(s) from each variant\'s "available" flag'
              + (f', from the saved copy {copy_age(fetched, now)}, stamped with that time' if dump is not None and when else '')
              + (', from a saved copy of unknown age, stamped "time unknown"' if dump is not None and not when else '')
              + (f'; nothing available for {len(none)}: {", ".join(none)} (their cards say "None in stock right now")' if none else '')
              + '. It is right only until stock changes in Shopify: fetch again and deploy the site straight after you add '
                'stock, and at least daily. A phone missing from it has no stock data, so all its options show as orderable '
                '(Shopify still refuses what it doesn\'t have).')
        if copy_state:
            print('  STALE: the saved copy is stale (above), so this snapshot is too, and go_live.py warns about it. Fetch '
                  'live with --shop-url before you deploy.')
            code = max(code, 1)
        for note in stock_notes:
            print(f'  {note}')
        if stock_notes:
            code = max(code, 1)
    if opt.check_prices:
        for note in price_notes:
            print(f'  NOTE {note}')
        if mismatches:
            print(f'PRICE MISMATCHES ({len(mismatches)}): Shopify\'s price differs from the site\'s data-prices. Change one '
                  'of them so they agree (Shopify admin: Products > Bulk edit, Price column; the site: set_prices.py), '
                  'then run this again. Don\'t deploy until it passes.')
            for h, key, site_p, given, shop_p in mismatches:
                print(f'  {h}  {key}  site {gbp(site_p) if site_p is not None else "no price on the site"}  '
                      f'Shopify {gbp(shop_p) if shop_p is not None else "unreadable price " + json.dumps(given)}')
            print(f'Price check: FAILED. {len(mismatches)} of {compared} Shopify variant(s) don\'t match the site.')
            code = 3
        elif gaps:
            print(f'Price check: the {compared} Shopify variant(s) read match the site, but not every product could be '
                  'compared (above): not a clean check.')
        elif dump is not None and copy_state:
            print(f'Price check: NOT PASSED. All {compared} Shopify variant(s) in the saved copy match the site\'s '
                  f'data-prices, but the copy was {copy_age(fetched, now)}: not a live check, and Shopify\'s prices may have '
                  'changed since. Run it again with --shop-url before you deploy.')
            code = max(code, 1)
        elif dump is not None:
            print(f'Price check: all {compared} Shopify variant(s) on {len(raw)} product(s) in the saved copy '
                  f'{copy_age(fetched, now)} match the site\'s data-prices. A saved copy is not a live check, so it never '
                  'reads "passed": before a deploy, run it with --shop-url.')
        else:
            print(f'Price check: passed. All {compared} Shopify variant(s) on {len(raw)} product(s) match the site\'s '
                  'data-prices.')
    return code


if __name__ == '__main__':
    sys.exit(main())
