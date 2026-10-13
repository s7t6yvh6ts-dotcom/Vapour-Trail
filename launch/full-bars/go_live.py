#!/usr/bin/env python3
"""Full Bars launch-day switch: turns the preview site into the live site in one go.

What it does, in plain English (for Ash)
----------------------------------------
The site in sites/full-bars is a preview: search engines are blocked, every page has a "not trading yet"
banner, and the Order buttons, contact form and trade-in tool are switched off. Doing that by hand on launch
day means editing 56 pages. This script does the mechanical part for you, and refuses to run while anything
would make launching a mistake.

It switches, on every page that has them:
  - robots.txt: "Disallow: /" becomes "Allow: /" and the preview comments go
  - <meta name="robots" content="noindex"> becomes index,follow (404.html keeps noindex on purpose)
  - the yellow "Preview: Full Bars isn't trading yet" banner is removed
  - data-preview="1" is removed from the 19 product pickers and the contact form (and from the 7 trade-in
    quote tools if you pass --trade-ins open)
  - the dead "Opening soon" span on each product page becomes a real Order link to the contact page
  - the "Not trading yet" boxes on terms, privacy, cookies, warranty, delivery-returns and contact go
  - the contact form gets its "Order a phone" topic (site.js looks for it)
  - "Last updated ..." on the legal pages and every <lastmod> in sitemap.xml become the launch date. Only in
    the run that switches the site out of preview, or when you pass --launch-date: rerunning on a site that is
    already live leaves those dates alone, because nothing on those pages changed
  - every https://www.fullbars.co.uk link and hello@fullbars.co.uk address follows --domain
  - your --rewrites (below): the preview wording, in every place it appears

It will NOT run (exit code 1, nothing written) while any of these launch blockers remain:
  - a [placeholder] in square brackets on any page (the "leave these alone" ones in GO-LIVE.md section 3,
    such as the customer's [date] in the cancellation form, are allowed)
  - a price problem found by check_site_prices.py, or by set_prices.py --check (which also catches a stale
    "Price for ... From" line and a "Lowest price" badge on a phone that is no longer the cheapest)
  - a handset spec that disagrees with facts.json (check_site_facts.py)
  - checkout not chosen, or pay.js not matching it: --checkout stripe needs at least one https Payment
    Link in pay.js; --checkout shopify needs pay.js empty, or you'd sell the same phone twice
  - a data-stock attribute that isn't valid JSON (site.js would ignore it and show everything in stock)
  - --trade-ins open while the sell pages have no quote-sending form
  - preview wording ("Preview prices: we're not taking orders yet", "When we open ...") that would still be
    on the live pages. It is future-tense, so it can't be switched mechanically: you write the new wording
    once in a --rewrites file and the script puts it on every page. Trade-in wording that stays true while
    trade-ins are closed is listed separately and doesn't block.
    To switch anyway and fix the wording by hand afterwards, pass --allow-preview-wording: the run then ends
    "NOT READY TO PUBLISH" with exit code 3, and you must not publish until the wording is done.

How to use it
-------------
Always run it on a copy of the site folder or on a git branch (GO-LIVE.md section 7 says how the switched
copy becomes the site you publish), never on your only copy.

  1. See what it would change and what is still blocking launch. Changes nothing:
       python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout stripe --dry-run \\
           --out ~/go-live-report.txt --rewrites-template ~/rewrites.json
  2. Just the blockers:
       python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout stripe --check-only
  3. Fill in ~/rewrites.json (below), fix the other blockers, dry-run again with --rewrites ~/rewrites.json
     until it says "No blockers", then do it for real (edits COPY in place):
       python3 launch/full-bars/go_live.py --site COPY --domain fullbars.co.uk --checkout stripe \\
           --rewrites ~/rewrites.json --out ~/go-live-report.txt
  4. Do the items listed under STILL TO DO BY HAND, republish, and put one real order through.

The --rewrites file:
  --rewrites-template FILE writes every preview sentence still on the pages, one per key, each set to null.
  Each key is one sentence as a customer reads it (&rsquo; and the like already turned into ’). Replace each
  null with your new wording in plain text, or "" to delete the sentence. Then pass the file with --rewrites:
  each sentence is replaced wherever it appears, in the page text, in meta descriptions and in the structured
  data (FAQ answers), with quotes and & made safe for each place. Plain text only: < and > are refused, so
  links and bold stay as they are on the page. If one of your sentences sits inside a longer one of yours at
  the same place, the longer one wins there; two that partly overlap are refused, and every clash is listed.
  A sentence left null is skipped, and blocks the switch if it is preview wording.

Options: --launch-date YYYY-MM-DD (default today) sets the "Last updated" and sitemap dates.
--trade-ins closed (the default) keeps the trade-in quote tool in guide-price mode; --trade-ins open switches it on.
--no-www uses https://fullbars.co.uk/ instead of https://www.fullbars.co.uk/ for page addresses.

Exit codes: 0 = done and ready to publish (with --dry-run or --check-only: no blockers);
1 = blockers, nothing written (or, after writing, a re-check failed: the report says so, don't publish);
2 = bad arguments; 3 = switched (or would switch), but NOT READY TO PUBLISH: preview wording is still on the
pages because you passed --allow-preview-wording.
The script writes only inside --site, plus the --out report and the --rewrites-template file you name (both
must be outside --site, so they never get published). Python 3 standard library only.
"""
import argparse
import bisect
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_CHECKER = os.path.join(HERE, 'check_site_prices.py')
SET_PRICES = os.path.join(HERE, 'set_prices.py')
FACTS_CHECKER = os.path.join(HERE, 'check_site_facts.py')

TEXT_EXT = ('.html', '.js', '.css', '.txt', '.xml', '.json', '.svg', '.webmanifest')   # read, and domain-rewritten
SCAN_EXT = ('.html', '.js', '.css', '.txt', '.xml')                                       # scanned for preview wording

# GO-LIVE.md section 7's grep, plus preview phrasings it misses ("not taking payments yet", "until then" ...)
GOLIVE_GREP = r'preview|when we open|once we open|open soon|opening soon|not trading|trading yet'
_APOS = r"(?:&rsquo;|’|')"
SHOP_WORDS = re.compile(
    GOLIVE_GREP + r'|not taking (?:orders|payments|messages)'
    r'|not (?:buying|selling|sending|accepting)\b[^.<]{0,60}?\byet\b'
    r'|isn' + _APOS + r't (?:selling|sending)\b[^.<]{0,80}?\byet\b'
    r'|can' + _APOS + r't take orders|goes live when|until then', re.I)
# Trade-in wording that is true while trade-ins stay closed, and wrong once they open
TRADE_WORDS = re.compile(r'trade-ins open|trade-ins aren|guide price|guide figure|expect to pay', re.I)
# A sentence that is explicitly about trade-ins: on a sell page, preview wording like this stays true while trade-ins
# are closed. ("When we open, we'll quote ..." is not: once the shop is live, "when we open" reads as wrong.)
TRADE_CONTEXT = re.compile(r'\btrade-?ins?\b|buying phones|guide (?:price|figure)|expect to pay', re.I)

# Same pattern as GO-LIVE.md section 3's placeholder grep (no ] < > " = inside the brackets)
PLACEHOLDER = re.compile(r'\[[^\]<>"=\n]+\]')
# GO-LIVE.md section 3 "Leave these alone": (file, placeholder, the context it must sit in)
LEAVE_ALONE = (
    ('delivery-returns.html', '[phone, storage, grade, colour]', r'I hereby give notice.*?</div>'),
    ('delivery-returns.html', '[date]', r'I hereby give notice.*?</div>'),
    ('delivery-returns.html', '[your name]', r'I hereby give notice.*?</div>'),
    ('delivery-returns.html', '[your address]', r'I hereby give notice.*?</div>'),
    ('guides/remove-find-my-before-selling-iphone.html', '[your name]', r'Settings (?:&gt;|>) \[your name\]'),
)

# Script text that only ever runs while data-preview is on, so it never shows on the live site
PREVIEW_ONLY_JS = (
    ('site.js', 'Opening soon'),
    ('site.js', 'Full Bars isn’t trading yet, so questions can’t be sent'),
    ('site.js', 'Nothing has been sent. Full Bars isn’t trading yet'),
    ('quote-ui.js', 'Guide price only: trade-ins open soon.'),
)
# What quote-ui.js needs on a sell page before trade-in quotes can be sent
QT_SEND_IDS = ('qtSend', 'qtName', 'qtNotes', 'qtOwner', 'qtStatus')
PICKER_TAG = re.compile(r'<form class="picker" id="picker"[^>]*>')   # as in check_site_prices.py
NO_INDEX_KEEP = ('404.html',)   # an error page should never be indexed


class Fail(Exception):
    """A problem that stops the run (bad input, unexpected site structure)."""


# ----------------------------------------------------------------------------------------------- reading
def load_site(root):
    """Every text file under root, as {relative/path: text}. Symlinks and dot-folders are skipped."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('.') and not os.path.islink(os.path.join(dirpath, d)))
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            if f.startswith('.') or os.path.islink(p) or not f.lower().endswith(TEXT_EXT):
                continue
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            try:
                with open(p, encoding='utf-8', newline='') as fh:
                    files[rel] = fh.read()
            except UnicodeDecodeError:
                raise Fail(f'{rel} is not UTF-8 text')
    return files


def attr(tag, name):
    m = re.search(r'(?<![\w-])' + re.escape(name) + r'="([^"]*)"', tag)
    return html.unescape(m.group(1)) if m else None


def line_of(src, pos):
    return src.count('\n', 0, pos) + 1


def element_end(src, start, tag='div'):
    """Index just past the </tag> closing the element whose start tag begins at start, or -1."""
    depth = 0
    for m in re.finditer(r'<(/?)' + tag + r'\b[^>]*>', src[start:], re.I):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start + m.end()
    return -1


def closing(rel, src, start):
    end = element_end(src, start)
    if end < 0:
        raise Fail(f'{rel}:{line_of(src, start)}: <div> with no closing </div>, so it can\'t be removed safely')
    return end


def widen_to_line(src, s, e):
    """If src[s:e] is alone on its line(s), widen it to take the whole line and its newline."""
    ls = src.rfind('\n', 0, s) + 1
    le = src.find('\n', e)
    le = len(src) if le < 0 else le
    if not src[ls:s].strip() and not src[e:le].strip():
        return ls, min(le + 1, len(src))
    return s, e


def pickers(files):
    """(rel, picker start tag, its position) for each product page's #picker form."""
    out = []
    for rel in sorted(files):
        if rel.startswith('products/') and rel.endswith('.html'):
            m = PICKER_TAG.search(files[rel])
            if m:
                out.append((rel, m.group(0), m.start()))
    return out


def robots_rules(text):
    """(line_start, line, field, value, agents) for each Allow/Disallow line of robots.txt, with the user-agents it applies to."""
    out, agents, in_rules, pos = [], [], False, 0
    for line in text.splitlines(True):
        body = line.split('#', 1)[0].strip()
        field, _, value = body.partition(':')
        field, value = field.strip().lower(), value.strip()
        if field == 'user-agent':
            if in_rules:
                agents, in_rules = [], False
            agents.append(value)
        elif field in ('allow', 'disallow'):
            in_rules = True
            out.append((pos, line, field, value, tuple(agents)))
        pos += len(line)
    return out


def robots_blocks_all(text):
    """True if robots.txt tells every crawler (User-agent: *) to keep out of the whole site."""
    return any(f == 'disallow' and v == '/' and '*' in a for _, _, f, v, a in robots_rules(text))


def pay_links(src):
    """[(key, link)] from pay.js, as check_site_prices.py reads its keys."""
    body = src[src.index('window.FULLBARS_PAY'):] if 'window.FULLBARS_PAY' in src else ''
    return re.findall(r'^\s*"([^"]+)":\s*"([^"]*)",?\s*$', body, re.M)


# ----------------------------------------------------------------------------------------------- edits
class Edit:
    """Replace src[start:end] of one file with new. prio 0 = switch, 1 = domain (dropped inside a switch)."""
    __slots__ = ('rel', 'start', 'end', 'new', 'what', 'prio', 'line')

    def __init__(self, rel, start, end, new, what, prio=0):
        self.rel, self.start, self.end, self.new, self.what, self.prio = rel, start, end, new, what, prio
        self.line = 0


def resolve(files, edits):
    """Drop domain edits that sit inside a block a switch replaces; refuse any other overlap."""
    by_file = {}
    for e in edits:
        by_file.setdefault(e.rel, []).append(e)
    kept = []
    for rel, es in by_file.items():
        es.sort(key=lambda e: (e.start, -e.end, e.prio))
        out = []
        for e in es:
            clash = [k for k in out if e.start < k.end and k.start < e.end or (e.start == e.end == k.start == k.end)]
            if not clash:
                out.append(e)
                continue
            if all(k.prio < e.prio and k.start <= e.start and e.end <= k.end for k in clash):
                continue   # e.g. a domain inside a removed banner: it goes with the banner
            raise Fail(f'{rel}: overlapping changes ({e.what} / {clash[0].what}) at line {line_of(files.get(rel, ""), e.start)}')
        kept.extend(out)
    for e in kept:
        e.line = line_of(files.get(e.rel, ''), e.start)
    return sorted(kept, key=lambda e: (e.rel, e.start))


def apply_edits(files, edits):
    out = dict(files)
    by_file = {}
    for e in edits:
        by_file.setdefault(e.rel, []).append(e)
    for rel, es in by_file.items():
        src = out.get(rel, '')
        for e in sorted(es, key=lambda e: e.start, reverse=True):
            src = src[:e.start] + e.new + src[e.end:]
        out[rel] = src
    return out


def show(text, limit=None):
    t = text.replace('\n', '⏎')
    return t if limit is None or len(t) <= limit else t[:limit] + '…'


def describe(files, e, ctx=40):
    src = files.get(e.rel, '')
    ls = src.rfind('\n', 0, e.start) + 1
    le = src.find('\n', e.end)
    le = len(src) if le < 0 else le
    old, new = src[e.start:e.end], e.new
    whole_line = old.endswith('\n') and not new and e.start == ls
    left = src[max(ls, e.start - ctx):e.start]
    right = '' if whole_line else src[e.end:min(le, e.end + ctx)]
    lpad = '…' if e.start - ctx > ls else ''
    rpad = '…' if not whole_line and e.end + ctx < le else ''
    lines = [f'  {e.rel}:{e.line}  {e.what}']
    lines.append(f'    before: {lpad}{show(left)}[-{show(old.rstrip(chr(10)) if whole_line else old)}-]{show(right)}{rpad}')
    lines.append('    after:  (line removed)' if whole_line else f'    after:  {lpad}{show(left)}{{+{show(new)}+}}{show(right)}{rpad}')
    return '\n'.join(lines)


# ----------------------------------------------------------------------------------------------- domain
def parse_domain(value, no_www):
    d = re.sub(r'^https?://', '', value.strip().lower()).rstrip('/').rstrip('.')
    bare = d[4:] if d.startswith('www.') else d
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', bare):
        raise Fail(f'--domain {value!r} is not a domain name like fullbars.co.uk')
    return bare, (bare if no_www else 'www.' + bare)


def current_host(files):
    m = re.search(r'<link\b[^>]*\brel="canonical"[^>]*\bhref="https?://([^/"]+)/', files.get('index.html', ''))
    if not m:
        raise Fail('index.html has no canonical link, so the current domain is unknown')
    return m.group(1).lower()


def domain_edits(files, old_host, new_bare, new_host):
    old_bare = old_host[4:] if old_host.startswith('www.') else old_host
    if old_bare == new_bare and old_host == new_host:
        return []
    dom = re.escape(old_bare) + r'(?![\w-]|\.\w)'
    rules = (
        (re.compile(r'https?://(?:www\.)?' + dom, re.I), 'https://' + new_host, 'web address'),
        (re.compile(r'(?<=@)' + dom, re.I), new_bare, 'email domain'),
        (re.compile(r'(?<![\w@/.-])www\.' + dom, re.I), new_host, 'web address'),
        (re.compile(r'(?<![\w@/.-])' + dom, re.I), new_bare, 'domain'),
    )
    edits = []
    for rel, src in files.items():
        taken = []
        for rx, new, what in rules:
            for m in rx.finditer(src):
                if any(a < m.end() and m.start() < b for a, b in taken):
                    continue
                taken.append(m.span())
                if m.group(0) != new:
                    edits.append(Edit(rel, m.start(), m.end(), new, f'{what}: {m.group(0)} -> {new}', prio=1))
    return edits


# ----------------------------------------------------------------------------------------------- switches
def plan_switches(files, opt):
    """The mechanical preview -> live edits, and notes about what was deliberately left."""
    edits, notes = [], []
    long_date = f'{opt.launch_date.day} {opt.launch_date:%B %Y}'
    for rel in sorted(files):
        src = files[rel]
        if not rel.endswith('.html'):
            continue
        # robots meta
        for m in re.finditer(r'<meta\b[^>]*\bname="robots"[^>]*>', src):
            content = attr(m.group(0), 'content') or ''
            if 'noindex' not in content.lower():
                continue
            if rel in NO_INDEX_KEEP:
                notes.append(f'{rel} keeps noindex on purpose: an error page should never be in search results.')
                continue
            new = re.sub(r'content="[^"]*"', 'content="index,follow"', m.group(0))
            edits.append(Edit(rel, m.start(), m.end(), new, 'search engines: noindex -> index,follow'))
        # preview banner
        for m in re.finditer(r'<div\b[^>]*\bclass="preview-bar\b[^"]*"[^>]*>', src):
            end = closing(rel, src, m.start())
            s, e = widen_to_line(src, m.start(), end)
            edits.append(Edit(rel, s, e, '', 'preview banner removed'))
        # data-preview attributes
        for m in re.finditer(r'<[a-zA-Z][^>]*?\sdata-preview(?:="[^"]*")?[^>]*>', src):
            tag = m.group(0)
            if opt.trade_ins == 'closed' and attr(tag, 'id') == 'qt':
                continue
            a = re.search(r'\sdata-preview(?:="[^"]*")?', tag)
            where = {'picker': 'product picker', 'contactForm': 'contact form', 'qt': 'trade-in quote tool'}.get(attr(tag, 'id'), 'element')
            edits.append(Edit(rel, m.start() + a.start(), m.start() + a.end(), '', f'{where}: data-preview removed (switches it on)'))
        # dead Order span -> link
        for m in re.finditer(r'<span\b[^>]*\bid="orderBtn"[^>]*>.*?</span>', src, re.S):
            tag = m.group(0)[:m.group(0).index('>') + 1]
            cls = ' '.join(c for c in (attr(tag, 'class') or 'btn btn-hot btn-block').split() if c != 'btn-off')
            pk = PICKER_TAG.search(src)
            href = (attr(pk.group(0), 'data-contact') if pk else None) or '../contact.html'
            new = f'<a class="{html.escape(cls)}" id="orderBtn" href="{html.escape(href)}">Order</a>'
            edits.append(Edit(rel, m.start(), m.end(), new, 'Order button: dead "Opening soon" span -> link'))
        # preview-only notes
        if opt.trade_ins == 'open':
            for m in re.finditer(r'<div\b[^>]*\bid="qtPreview"[^>]*>', src):
                end = closing(rel, src, m.start())
                s, e = widen_to_line(src, m.start(), end)
                edits.append(Edit(rel, s, e, '', 'trade-in "open soon" note removed'))
        for m in re.finditer(r'<div\b[^>]*\bclass="[^"]*\bpreview-note\b[^"]*"[^>]*>', src):
            end = closing(rel, src, m.start())
            s, e = widen_to_line(src, m.start(), end)
            edits.append(Edit(rel, s, e, '', '"Not trading yet" box removed'))
        for m in re.finditer(r'<div\b[^>]*>\s*<h[1-6][^>]*>\s*Not trading yet\.?\s*</h[1-6]>', src):
            end = closing(rel, src, m.start())
            s, e = widen_to_line(src, m.start(), end)
            edits.append(Edit(rel, s, e, '', '"Not trading yet" panel removed'))
        # contact form: the topic site.js picks for ?order= links
        if 'id="contactForm"' in src:
            sm = re.search(r'<select\b[^>]*\bid="cTopic"[^>]*>(.*?)</select>', src, re.S)
            if sm and 'Order a phone' not in sm.group(1):
                first = src.find('</option>', sm.start(), sm.end())
                at = first + len('</option>') if first >= 0 else sm.start() + sm.group(0).index('>') + 1
                edits.append(Edit(rel, at, at, '<option>Order a phone</option>', 'contact form: "Order a phone" topic added'))
        # legal pages' date: only in the run that switches the site out of preview (or with --launch-date)
        for m in re.finditer(r'(<p\b[^>]*\bclass="legal-updated"[^>]*>)([^<]*)(</p>)', src) if opt.set_dates else ():
            want = f'Last updated {long_date}'
            if m.group(2).strip() != want:
                edits.append(Edit(rel, m.start(2), m.end(2), want, 'legal page date -> launch date'))
    # sitemap
    sm = files.get('sitemap.xml')
    if sm is None:
        notes.append('No sitemap.xml in the site folder: search engines will find pages by links only.')
    elif opt.set_dates:
        for m in re.finditer(r'<lastmod>([^<]*)</lastmod>', sm):
            if m.group(1).strip() != opt.launch_date.isoformat():
                edits.append(Edit('sitemap.xml', m.start(1), m.end(1), opt.launch_date.isoformat(), 'sitemap date -> launch date'))
    # robots.txt
    rb = files.get('robots.txt')
    if rb is None:
        new = f'User-agent: *\nAllow: /\n\nSitemap: https://{opt.host}/sitemap.xml\n'
        edits.append(Edit('robots.txt', 0, 0, new, 'robots.txt created (allows crawling)'))
    else:
        pos = 0
        for line in rb.splitlines(True):
            body = line.strip()
            if body.startswith('#') and (SHOP_WORDS.search(body) or re.search(r'at launch|placeholder', body, re.I)):
                edits.append(Edit('robots.txt', pos, pos + len(line), '', 'robots.txt: preview comment removed'))
            pos += len(line)
        # only the rule that shuts out every crawler; a Disallow you add for one named bot is left alone
        for at, line, field, value, agents in robots_rules(rb):
            if field == 'disallow' and value == '/' and '*' in agents:
                body = line.split('#', 1)[0].strip()
                s = at + line.index(body)
                edits.append(Edit('robots.txt', s, s + len(body), 'Allow: /', 'robots.txt: crawlers allowed'))
    return edits, notes


# ----------------------------------------------------------------------------------------------- blockers
def code_mask(src):
    """src with <style>, non-JSON-LD <script> and <!-- --> contents blanked (newlines kept)."""
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    src = re.sub(r'<!--.*?-->', blank, src, flags=re.S)
    src = re.sub(r'(<style\b[^>]*>)(.*?)(?=</style)', lambda m: m.group(1) + re.sub(r'[^\n]', ' ', m.group(2)), src, flags=re.S | re.I)

    def script(m):
        if 'application/ld+json' in m.group(1):
            return m.group(0)
        return m.group(1) + re.sub(r'[^\n]', ' ', m.group(2))
    return re.sub(r'(<script\b[^>]*>)(.*?)(?=</script)', script, src, flags=re.S | re.I)


def placeholders(files):
    """{placeholder: [rel:line, ...]} still on customer-facing pages."""
    found = {}
    for rel in sorted(files):
        if not rel.endswith('.html'):
            continue
        src = files[rel]
        masked = code_mask(src)
        allowed = []
        for f, text, ctx in LEAVE_ALONE:
            if f == rel:
                for m in re.finditer(ctx, src, re.S):
                    allowed.append((text, m.start(), m.end()))
        for m in PLACEHOLDER.finditer(masked):
            if any(t == m.group(0) and a <= m.start() and m.end() <= b for t, a, b in allowed):
                continue
            found.setdefault(m.group(0), []).append(f'{rel}:{line_of(src, m.start())}')
    return found


def _run(cmd):
    """Run one of the pack's checkers. Returns the CompletedProcess, or None if it took over 5 minutes."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None


def run_price_check(site):
    """[] if check_site_prices.py passes, else the reasons."""
    if not os.path.isfile(PRICE_CHECKER):
        return [f'check_site_prices.py is missing from {HERE}, so prices can\'t be checked']
    r = _run([sys.executable, PRICE_CHECKER, '--site', site, '--quiet'])
    if r is None:
        return ['check_site_prices.py took over 5 minutes and was stopped']
    if r.returncode == 0:
        return []
    fails = [ln[5:] for ln in r.stdout.splitlines() if ln.startswith('FAIL ')]
    if fails:
        return [f'price check: {f}' for f in fails]
    tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['no output'])[-1]
    return [f'check_site_prices.py stopped with an error, which usually means a mistyped data-prices on a product page '
            f'(GO-LIVE.md section 6, step 3): {tail}']


def run_set_prices_check(site, price_check_failed=False):
    """[] if set_prices.py --check passes, else its NEEDS A HAND EDIT items, stale derived prices and errors.
    It checks everything check_site_prices.py does, plus the #pdFrom line and the "Lowest price" badge."""
    if not os.path.isfile(SET_PRICES):
        return [f'set_prices.py is missing from {HERE}, so the "Lowest price" badge and "From" lines can\'t be checked']
    r = _run([sys.executable, SET_PRICES, '--check', site])
    if r is None:
        return ['set_prices.py --check took over 5 minutes and was stopped']
    if r.returncode == 0:
        return []
    out, section, stale = [], None, []
    for ln in r.stdout.splitlines():
        if not ln.strip():
            continue
        if not ln.startswith(' '):
            section = 'hand' if ln.startswith('NEEDS A HAND EDIT') else 'stale' if ln.startswith('Out of date') else None
            continue
        if section == 'hand' and ln.startswith('  - '):
            out.append(f'set_prices.py: needs a hand edit: {ln[4:]}')
        elif section == 'stale':
            if re.match(r'  \S', ln):
                page = ln.strip()
            elif re.match(r'\s+line \d+', ln):
                stale.append(f'{page}: {ln.strip()}')
    m = re.search(r'^(\d+) derived price\(s\) out of date', r.stdout, re.M)
    if m:
        out.append(f'set_prices.py: {m.group(1)} price(s) shown on the pages don\'t match data-prices '
                   f'({"; ".join(stale[:3])}{"; ..." if len(stale) > 3 else ""}). Fix them all with: '
                   f'python3 launch/full-bars/set_prices.py --write {site}')
    out += [f'set_prices.py: {ln[7:]}' for ln in r.stderr.splitlines() if ln.startswith('ERROR: ')]
    if not out and not price_check_failed:
        tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['no output'])[-1]
        out.append(f'set_prices.py --check failed (exit {r.returncode}): {tail}')
    return out


def run_facts_check(site):
    """[] if check_site_facts.py finds no spec that disagrees with facts.json, else the conflicts."""
    if not os.path.isfile(FACTS_CHECKER):
        return [f'check_site_facts.py is missing from {HERE}, so handset specs can\'t be checked']
    r = _run([sys.executable, FACTS_CHECKER, '--site', site, '--quiet'])
    if r is None:
        return ['check_site_facts.py took over 5 minutes and was stopped']
    if r.returncode == 0:
        return []
    fails = [ln[5:] for ln in r.stdout.splitlines() if ln.startswith('FAIL ')]
    if fails:
        return [f'facts check (facts.json): {f}' for f in fails]
    tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['no output'])[-1]
    return [f'check_site_facts.py stopped (exit {r.returncode}): {tail}']


def run_checks(site):
    """Every content check in this folder, run on site: prices, derived prices and badge, handset specs."""
    price = run_price_check(site)
    return price + run_set_prices_check(site, bool(price)) + run_facts_check(site)


def find_blockers(site, files, opt):
    blockers, warnings = [], []
    # 1. placeholders
    for ph, where in sorted(placeholders(files).items(), key=lambda kv: (-len(kv[1]), kv[0])):
        pages = len({w.rsplit(':', 1)[0] for w in where})
        blockers.append(f'placeholder {ph} still on {pages} page{"s" if pages != 1 else ""} ({len(where)}x): {", ".join(where)}')
    # 2. prices (check_site_prices.py and set_prices.py --check) and handset specs (check_site_facts.py)
    blockers.extend(run_checks(site))
    # 3. checkout
    links = pay_links(files.get('pay.js', ''))
    filled = [(k, v.strip()) for k, v in links if v.strip()]
    if opt.checkout is None:
        blockers.append('checkout not chosen: pass --checkout shopify or --checkout stripe (GO-LIVE.md section 1, decision 1)')
    elif opt.checkout == 'shopify':
        if filled:
            blockers.append(f'--checkout shopify, but pay.js has {len(filled)} Stripe Payment Link(s) ({", ".join(k for k, _ in filled)}). '
                            'Clear them: running both checkouts sells the same phone twice')
    else:
        if 'pay.js' not in files:
            blockers.append('--checkout stripe, but the site has no pay.js')
        elif not filled:
            blockers.append('--checkout stripe, but every Payment Link in pay.js is empty, so nothing can be paid for. '
                            'Add a link for each phone you hold (rules at the top of pay.js), or choose --checkout shopify')
        for k, v in filled:
            if not v.startswith('https://'):
                blockers.append(f'pay.js "{k}": "{v}" is not an https:// link, so site.js ignores it')
            elif not v.startswith('https://buy.stripe.com/'):
                warnings.append(f'pay.js "{k}" is not a buy.stripe.com link: fine only if it is your Stripe custom domain')
        cap = re.search(r"BUY_NOW_MAX\s*=\s*Number\('(\d+)'\)", files.get('site.js', ''))
        prices = {}
        for rel, tag, _ in pickers(files):
            try:
                for st, g in json.loads(attr(tag, 'data-prices') or '{}').items():
                    for gr, p in g.items():
                        prices[f'{attr(tag, "data-model")} {st} {gr}'] = p
            except (ValueError, AttributeError):
                pass   # check_site_prices.py reports this
        if cap:
            over = [k for k, v in filled if isinstance(prices.get(k), (int, float)) and prices[k] > int(cap.group(1))]
            if over:
                warnings.append(f'pay.js has links for phones priced above the GBP {cap.group(1)} cap (BUY_NOW_MAX), which site.js '
                                f'never shows: {", ".join(over)}')
    # 4. data-stock
    any_stock = False
    for rel, tag, pos in pickers(files):
        raw = attr(tag, 'data-stock')
        if raw is None:
            continue
        any_stock = True
        try:
            stock = json.loads(raw)
            if not isinstance(stock, dict):
                raise ValueError('not an object')
        except ValueError as e:
            blockers.append(f'{rel}:{line_of(files[rel], pos)}: data-stock is not valid JSON ({e}), so site.js ignores it and '
                            'every option looks in stock')
            continue
        try:
            combos = {f'{st}|{gr}' for st, g in json.loads(attr(tag, 'data-prices') or '{}').items() for gr in g}
        except ValueError:
            combos = set()
        odd = [k for k in stock if combos and k not in combos]
        if odd:
            warnings.append(f'{rel}: data-stock has keys no option uses, so they do nothing: {", ".join(odd)}')
    if not any_stock:
        warnings.append('no product page has data-stock yet, so every option shows as available to order '
                        '(GO-LIVE.md section 4 and section 6, step 2)')
    # 5. trade-ins
    if opt.trade_ins == 'open':
        for rel in sorted(files):
            src = files[rel]
            if rel.endswith('.html') and re.search(r'\bid="qt"', src):
                missing = [i for i in QT_SEND_IDS if f'id="{i}"' not in src]
                if missing:
                    blockers.append(f'--trade-ins open, but {rel} has no way to send a quote (missing #{", #".join(missing)}): '
                                    'quote-ui.js would give a quote nobody can accept. Add the send form, or use --trade-ins closed')
    return blockers, warnings


# ----------------------------------------------------------------------------------------------- leftover wording
TEXT, TAG, CODE, LDJSON = 0, 1, 2, 3
# Attributes customers read but scripts also use, so --rewrites never touches them: a person edits these
HAND_ATTRS = {'data-title', 'data-grades', 'data-copy', 'data-model', 'value', 'label'}
# Attributes whose value is only ever shown to people, so --rewrites may change them
TEXT_ATTRS = {'alt', 'title', 'aria-label', 'placeholder'}
# <meta name/property> whose content is wording (description, og:title, twitter:description, og:image:alt ...)
META_TEXT = re.compile(r'(?:^|:)(?:description|title|site_name|alt)$', re.I)


def html_marks(src):
    marks = bytearray(len(src))

    def put(a, b, k):
        marks[a:b] = bytes([k]) * (b - a)
    for m in re.finditer(r'<!--.*?-->|<(script|style)\b[^>]*>.*?</\1\s*>|<[^>]*>', src, re.S | re.I):
        s = m.group(0)
        if s.startswith('<!--'):
            put(m.start(), m.end(), CODE)
        elif m.group(1):
            o = s.index('>') + 1
            c = s.lower().rindex('</')
            put(m.start(), m.start() + o, TAG)
            put(m.start() + c, m.end(), TAG)
            put(m.start() + o, m.start() + c, LDJSON if 'application/ld+json' in s[:o] else CODE)
        else:
            put(m.start(), m.end(), TAG)
    return marks


def js_marks(src):
    """0 code, 1 comment, 2 string (contents) for a JavaScript file; rough but regex-literal aware."""
    marks = bytearray(len(src))
    i, n, last = 0, len(src), ''
    while i < n:
        c = src[i]
        if c == '/' and src.startswith('//', i):
            j = src.find('\n', i)
            j = n if j < 0 else j
            marks[i:j] = b'\x01' * (j - i)
            i = j
            continue
        if c == '/' and src.startswith('/*', i):
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            marks[i:j] = b'\x01' * (j - i)
            i = j
            continue
        if c in '"\'`':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            marks[i + 1:min(j, n)] = b'\x02' * (min(j, n) - i - 1)
            i, last = j + 1, c
            continue
        if c == '/' and (last == '' or last in '(,=:[!&|?{};+-*%<>~^' or re.search(r'\b(?:return|typeof|case)\s*$', src[max(0, i - 8):i])):
            j, cls = i + 1, False
            while j < n and src[j] != '\n':
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == '[':
                    cls = True
                elif src[j] == ']':
                    cls = False
                elif src[j] == '/' and not cls:
                    break
                j += 1
            i, last = j + 1, '/'
            continue
        if not c.isspace():
            last = c
        i += 1
    return marks


def js_literal_is_code(rel, lit):
    """A JS string that is never shown on the live site: preview-only text, or a selector / attribute name."""
    if any(rel.split('/')[-1] == f and lit.startswith(p) for f, p in PREVIEW_ONLY_JS):
        return True
    return bool(re.fullmatch(r'[#.\[]?[\w-]+(?:=["\']?[\w-]*["\']?)?\]?', lit))   # e.g. '#qtPreview', 'data-preview'


def classify(rel, src, marks, pos):
    """(kind, snippet_start, snippet_end) for a match at pos that is NOT inside a text segment (see segments()):
    kind is hook (a class, id or attribute name: never shown), hand (customer-facing, but where scripts read it
    too, so a person must edit it), or code (scripts, styles, comments, preview-only script text)."""
    if rel.endswith('.html'):
        k = marks[pos]
        if k == CODE:
            return 'code', pos, pos
        if k in (TEXT, LDJSON):
            a = max(src.rfind('>', 0, pos) + 1, src.rfind('\n', 0, pos) + 1)
            b = min(x for x in (src.find('<', pos), src.find('\n', pos), len(src)) if x >= 0)
            return 'hand', a, b
        ts = src.rfind('<', 0, pos)
        te = src.find('>', pos) + 1
        for am in re.finditer(r'([^\s=<>/"\']+)(?:\s*=\s*"([^"]*)")?', src[ts + 1:te]):
            ns, ne = ts + 1 + am.start(1), ts + 1 + am.end(1)
            if ns <= pos < ne:
                return 'hook', ns, ne
            if am.group(2) is not None:
                vs, ve = ts + 1 + am.start(2), ts + 1 + am.end(2)
                if vs <= pos < ve:
                    return ('hand' if am.group(1).lower() in HAND_ATTRS else 'hook'), vs, ve
        return 'hook', ts, te
    if rel.endswith('.js'):
        if marks[pos] == 2:
            a, b = pos, pos
            while a > 0 and marks[a - 1] == 2:
                a -= 1
            while b < len(src) and marks[b] == 2:
                b += 1
            return ('code' if js_literal_is_code(rel, src[a:b]) else 'hand'), a, b
        return 'code', pos, pos
    if rel.endswith('.css'):
        return 'code', pos, pos
    ls = src.rfind('\n', 0, pos) + 1
    le = src.find('\n', pos)
    le = len(src) if le < 0 else le
    return ('code' if src[ls:le].lstrip().startswith('#') else 'hand'), ls, le


# ----------------------------------------------------------------------------------------------- text segments
# A segment is one run of customer-facing text in one context: an HTML text node, a wording attribute (meta
# description, alt ...), a string in the structured data (JSON-LD), or a JavaScript string shown on the page.
# Its text is what a customer reads: entities (&rsquo;) and escapes (\u003e) decoded, whitespace collapsed.
# Each decoded character remembers where it came from in the file, so a sentence found in the text maps
# back to the exact characters to replace, and the new wording is escaped for that context.
ENTITY_RX = r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);'
TOKEN_RX = {
    'html': re.compile(ENTITY_RX),
    'attr': re.compile(ENTITY_RX),
    'json': re.compile(r'\\(?:u[0-9a-fA-F]{4}|.)', re.S),
    'js': re.compile(r'\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)', re.S),
    'jshtml': re.compile(r'\\(?:u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)|' + ENTITY_RX, re.S),
}
JS_SIMPLE = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0', '\n': ''}
# Folded for matching only (same length): curly and straight quotes alike
FOLD = str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"'})
# A sentence ends at . ! or ? (plus any closing quote or bracket), then a space, then anything but lower case
SENT_BREAK = re.compile(r'(?<=[.!?])(["\'\u201d\u2019)\]]*)(\s+)(?=[^\sa-z])')
CTX_NAME = {'html': 'page text', 'attr': 'attribute', 'json': 'structured data', 'js': 'script text', 'jshtml': 'script text'}


def decode_token(tok):
    if tok.startswith('&'):
        return html.unescape(tok)
    c = tok[1]
    if c in 'ux' and len(tok) > 2:
        return chr(int(tok[2:], 16))
    return JS_SIMPLE.get(c, c)


class Segment:
    """One run of customer-facing text. text is what a customer reads; starts[i]/ends[i] are where character i of
    text came from in the file (built only when needed: most segments never match anything)."""
    __slots__ = ('rel', 'start', 'end', 'ctx', 'quote', 'text', 'fold', '_src', '_starts', '_ends')

    def __init__(self, rel, src, a, b, ctx, quote=''):
        self.rel, self.start, self.end, self.ctx, self.quote, self._src = rel, a, b, ctx, quote, src
        raw = src[a:b]
        dec = TOKEN_RX[ctx].sub(lambda m: decode_token(m.group(0)), raw) if ('&' in raw or '\\' in raw) else raw
        self.text = re.sub(r'\s+', ' ', dec)
        self.fold = self.text.translate(FOLD)
        self._starts = self._ends = None

    def _build(self):
        chars, starts, ends = [], [], []

        def put(ch, s, e):
            if ch.isspace():
                if chars and chars[-1] == ' ':
                    ends[-1] = e
                    return
                ch = ' '
            chars.append(ch)
            starts.append(s)
            ends.append(e)
        src, i = self._src, self.start
        for m in TOKEN_RX[self.ctx].finditer(src, self.start, self.end):
            for k in range(i, m.start()):
                put(src[k], k, k + 1)
            for ch in decode_token(m.group(0)):
                put(ch, m.start(), m.end())
            i = m.end()
        for k in range(i, self.end):
            put(src[k], k, k + 1)
        if ''.join(chars) != self.text:
            raise Fail(f'internal: {self.rel}:{line_of(src, self.start)}: text decoded two ways differs')
        self._starts, self._ends = starts, ends

    @property
    def starts(self):
        if self._starts is None:
            self._build()
        return self._starts

    @property
    def ends(self):
        if self._ends is None:
            self._build()
        return self._ends

    def index(self, pos):
        """Index in text of the character that raw position pos belongs to."""
        return max(0, bisect.bisect_right(self.starts, pos) - 1)


_SEGMENTS = {}


def segments(rel, src, marks=None):
    """Every customer-facing text segment of one file, in file order (cached: the same text gives the same list)."""
    key = (rel, src)
    if key not in _SEGMENTS:
        _SEGMENTS[key] = _segments(rel, src, marks)
    return _SEGMENTS[key]


def _segments(rel, src, marks=None):
    out = []
    if rel.endswith('.html'):
        marks = html_marks(src) if marks is None else marks
        flat = bytes(marks)
        for m in re.finditer(b'\x00+', flat):
            if src[m.start():m.end()].strip():
                out.append(Segment(rel, src, m.start(), m.end(), 'html'))
        for m in re.finditer(b'\x03+', flat):
            for sm in re.finditer(r'"((?:[^"\\]|\\.)*)"(\s*:)?', src[m.start():m.end()], re.S):
                if not sm.group(2) and sm.group(1).strip():
                    out.append(Segment(rel, src, m.start() + sm.start(1), m.start() + sm.end(1), 'json'))
        for m in re.finditer(r'<([a-zA-Z][\w:-]*)(\s[^>]*)?>', src):
            if marks[m.start()] != TAG or not m.group(2):
                continue
            tag, base = m.group(0), m.start(2)
            meta_text = m.group(1).lower() == 'meta' and META_TEXT.search(attr(tag, 'name') or attr(tag, 'property') or '')
            for am in re.finditer(r'([^\s=<>/"\']+)(?:\s*=\s*"([^"]*)")?', m.group(2)):
                name = am.group(1).lower()
                if am.group(2) and am.group(2).strip() and (name in TEXT_ATTRS or (name == 'content' and meta_text)):
                    out.append(Segment(rel, src, base + am.start(2), base + am.end(2), 'attr'))
    elif rel.endswith('.js'):
        marks = js_marks(src) if marks is None else marks
        for m in re.finditer(b'\x02+', bytes(marks)):
            a, b = m.start(), m.end()
            q = src[a - 1]
            lit = src[a:b]
            if q == '`' or js_literal_is_code(rel, lit) or not lit.strip():
                continue
            if re.search(r'<[a-zA-Z/]', lit):          # HTML in a string (innerHTML): the text between the tags
                for tm in re.finditer(r'[^<>]+', lit):
                    if tm.group(0).strip() and (tm.start() == 0 or lit[tm.start() - 1] != '<'):
                        out.append(Segment(rel, src, a + tm.start(), a + tm.end(), 'jshtml', q))
            else:
                out.append(Segment(rel, src, a, b, 'jshtml' if re.search(ENTITY_RX, lit) else 'js', q))
    out.sort(key=lambda s: s.start)
    return out


def sentence_bounds(text):
    """[(start, end)] of each sentence in text, without surrounding spaces."""
    spans, s = [], 0
    for m in SENT_BREAK.finditer(text):
        spans.append((s, m.end(1)))
        s = m.end(2)
    spans.append((s, len(text)))
    out = []
    for a, b in spans:
        while a < b and text[a] == ' ':
            a += 1
        while b > a and text[b - 1] == ' ':
            b -= 1
        if a < b:
            out.append((a, b))
    return out


def sentence_at(text, i):
    bounds = sentence_bounds(text)
    for a, b in bounds:
        if i < b:
            return a, b
    return bounds[-1] if bounds else (0, len(text))


def covering(segs, starts, pos):
    k = bisect.bisect_right(starts, pos) - 1
    if k >= 0 and segs[k].start <= pos < segs[k].end:
        return segs[k]
    return None


def element_spans(src, id_):
    out = []
    for m in re.finditer(r'<div\b[^>]*\bid="' + re.escape(id_) + r'"[^>]*>', src):
        e = element_end(src, m.start())
        out.append((m.start(), e if e > 0 else len(src)))
    return out


def is_sell_page(rel):
    return rel == 'sell.html' or (rel.startswith('sell/') and rel.endswith('.html'))


def leftovers(files, opt):
    """Preview wording still in the site, as {category: {snippet: [rel:line, ...]}}.
    rewrite = customer-facing, needs new wording (one sentence per snippet, as a --rewrites key);
    hand = customer-facing, but in a place scripts read too, so a person edits it;
    later = trade-in wording that stays true until trade-ins open; kept = preview hooks deliberately left
    (class, id and attribute names); code = scripts/styles/comments that never show on the live site."""
    items, seen_locs = {}, set()
    rank = {'rewrite': 0, 'hand': 0, 'later': 1, 'kept': 2, 'code': 3}
    for rel in sorted(files):
        if not rel.endswith(SCAN_EXT):
            continue
        src = files[rel]
        marks = html_marks(src) if rel.endswith('.html') else js_marks(src) if rel.endswith('.js') else None
        segs = segments(rel, src, marks) if rel.endswith(('.html', '.js')) else []
        seg_starts = [g.start for g in segs]
        boxes = element_spans(src, 'qtPreview') if rel.endswith('.html') else []
        sell = is_sell_page(rel)
        for rx, trade in ((SHOP_WORDS, False), (TRADE_WORDS, True)):
            for m in rx.finditer(src):
                pos = m.start()
                loc = f'{rel}:{line_of(src, pos)}'
                seg = covering(segs, seg_starts, pos)
                if seg is not None:
                    a, b = sentence_at(seg.text, seg.index(pos))
                    snippet, kind = seg.text[a:b], 'text'
                else:
                    kind, a, b = classify(rel, src, marks, pos)
                    snippet = src[a:b].strip()
                if kind == 'code':
                    ls = src.rfind('\n', 0, pos) + 1
                    le = src.find('\n', pos)
                    line = src[ls:(len(src) if le < 0 else le)]
                    o = pos - ls
                    snippet = line.strip() if len(line.strip()) <= 160 else '…' + line[max(0, o - 60):o + 100].strip() + '…'
                    cat = 'code'
                elif kind == 'hook':
                    cat = 'kept'
                else:
                    shop = not trade or bool(SHOP_WORDS.search(snippet))
                    in_box = any(x <= pos < y for x, y in boxes)
                    if opt.trade_ins == 'open':
                        cat = 'rewrite'
                    elif in_box or (sell and TRADE_CONTEXT.search(snippet)) or not shop:
                        cat = 'later'      # trade-in wording: still true while trade-ins are closed
                    else:
                        cat = 'rewrite'
                    if cat == 'rewrite' and kind == 'hand':
                        cat = 'hand'
                if cat == 'code' and loc in seen_locs:
                    continue   # one entry per line of code
                seen_locs.add(loc)
                key = (snippet, loc)
                if key not in items or rank[cat] < rank[items[key]]:
                    items[key] = cat
    out = {}
    for (snippet, loc), cat in items.items():
        out.setdefault(cat, {}).setdefault(snippet, [])
        if loc not in out[cat][snippet]:
            out[cat][snippet].append(loc)
    return out


def wording_left(left):
    """(pieces, places) of preview wording that must change before the site can be published."""
    groups = list(left.get('rewrite', {}).values()) + list(left.get('hand', {}).values())
    return len(groups), sum(len(v) for v in groups)


# ----------------------------------------------------------------------------------------------- rewrites
def norm_text(s):
    """A --rewrites key or new wording as plain text: entities decoded, whitespace collapsed."""
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def load_rewrites(path):
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        raise Fail(f'--rewrites {path}: {e}')
    if not isinstance(data, dict) or not all(isinstance(k, str) and k and (v is None or isinstance(v, str)) for k, v in data.items()):
        raise Fail(f'--rewrites {path} must be a JSON object of "exact text": "new text" (or null to skip)')
    rewrites, skipped, bad = {}, [], []
    for k, v in data.items():
        if v is None:
            skipped.append(k)
            continue
        key, new = norm_text(k), norm_text(v)
        if not key:
            bad.append(f'"{show(k, 60)}": the text to find is empty')
            continue
        if '<' in new or '>' in new:
            bad.append(f'"{show(k, 60)}": the new wording has < or >. Rewrites are plain text, so tags can\'t go in them: '
                       'keep links and bold on the page as they are, and rewrite the text around them')
            continue
        if key in rewrites and rewrites[key] != new:
            bad.append(f'"{show(k, 60)}" is in the file twice with different new wording')
            continue
        rewrites[key] = new
    if bad:
        raise Fail(f'--rewrites {path}: {len(bad)} problem(s), nothing written:\n  - ' + '\n  - '.join(bad))
    return rewrites, sorted(skipped)


def encode(plain, seg):
    """plain text, made safe for the place it goes."""
    if seg.ctx == 'html':
        return plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if seg.ctx == 'attr':
        return plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    if seg.ctx == 'json':
        return json.dumps(plain, ensure_ascii=False)[1:-1].replace('<', '\\u003c').replace('>', '\\u003e')
    s = plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') if seg.ctx == 'jshtml' else plain
    s = s.replace('\\', '\\\\').replace(seg.quote, '\\' + seg.quote)
    return s.replace('\n', '\\n').replace('\r', '\\r').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def match_rewrites(files, keys):
    """Where each key would apply. Returns (hits, clashes, found): hits are (segment, start, end, key) in decoded
    text, with a key that sits inside a longer key at the same place dropped (the longer one wins); clashes are
    the places where two keys partly overlap; found is the set of keys found anywhere."""
    folded = {k: k.translate(FOLD) for k in keys}
    hits, clash_at, found = [], {}, set()
    for rel in sorted(files):
        if not rel.endswith(('.html', '.js')):
            continue
        src = files[rel]
        for seg in segments(rel, src):
            hs = []
            for key, fk in folded.items():
                i = seg.fold.find(fk)
                while i >= 0 and fk:
                    hs.append((seg, i, i + len(fk), key))
                    i = seg.fold.find(fk, i + len(fk))
            if not hs:
                continue
            hs.sort(key=lambda h: (h[1], -(h[2] - h[1])))
            kept = []
            for h in hs:
                found.add(h[3])
                if any(k[1] <= h[1] and h[2] <= k[2] for k in kept):
                    continue
                other = next((k for k in kept if h[1] < k[2] and k[1] < h[2]), None)
                if other:
                    clash_at.setdefault((other[3], h[3]), []).append(f'{rel}:{line_of(src, seg.starts[h[1]])}')
                    continue
                kept.append(h)
            hits.extend(kept)
    clashes = [f'two of your texts overlap: "{show(a, 70)}" and "{show(b, 70)}", at {", ".join(dict.fromkeys(locs))}. '
               'Use one or the other, or split them into separate sentences' for (a, b), locs in clash_at.items()]
    return hits, clashes, found


def found_whole(files, texts):
    """The texts that appear somewhere as a whole run of words (not inside a longer word): an earlier run's rewrite."""
    rx = {t: re.compile(r'(?<!\w)' + re.escape(t.translate(FOLD)) + r'(?!\w)') for t in texts if t}
    out = set()
    for rel in sorted(files):
        if rel.endswith(('.html', '.js')) and len(out) < len(rx):
            for seg in segments(rel, files[rel]):
                out.update(t for t, r in rx.items() if t not in out and r.search(seg.fold))
    return out


def rewrite_edits(files, rewrites, bare, host, old_host):
    """The edits for your --rewrites. Refuses (Fail, listing every problem) if a text is nowhere, two texts
    partly overlap, or new wording can't go where its text is."""
    def follow(t):
        if old_host:
            ob = old_host[4:] if old_host.startswith('www.') else old_host
            t = re.sub(r'https?://(?:www\.)?' + re.escape(ob), 'https://' + host, t)
            t = re.sub(r'(?<=@)' + re.escape(ob), bare, t)
        return t
    rw = {}
    for k, v in rewrites.items():
        rw.setdefault(follow(k), follow(v))
    hits, problems, found = match_rewrites(files, list(rw))
    notes = []
    missing = [k for k in rw if k not in found]
    if missing:
        already = found_whole(files, [rw[k] for k in missing if rw[k]])
        for k in missing:
            if rw[k] and rw[k] in already:
                notes.append(f'--rewrites: "{show(k, 80)}" is on no page, but your new wording is: taken as already done.')
            else:
                problems.append(f'not on any page (copy it exactly from the report or the template'
                                f'{"; if you deleted it in an earlier run, set it to null" if not rw[k] else ""}): "{show(k, 120)}"')
    edits, last_end = [], {}
    for seg, ds, de, key in sorted(hits, key=lambda h: (h[0].rel, h[0].start, h[1])):
        new, text = rw[key], seg.text
        prev = last_end.get(id(seg), 0)
        if not new:   # deleting a sentence: take one neighbouring space with it, but never the space next to a tag
            if ds > 1 and text[ds - 1] == ' ' and ds - 1 >= prev:
                ds -= 1
            elif de + 1 < len(text) and text[de] == ' ':
                de += 1
        last_end[id(seg)] = de
        if seg.ctx in ('js', 'jshtml') and seg.quote not in '\'"':
            problems.append(f'{seg.rel}:{line_of(files[seg.rel], seg.start)}: "{show(key, 80)}" is in a script string '
                            'this tool can\'t safely change; edit it by hand')
            continue
        edits.append(Edit(seg.rel, seg.starts[ds], seg.ends[de - 1], encode(new, seg),
                          f'your rewrite (--rewrites), {CTX_NAME[seg.ctx]}'))
    if problems:
        raise Fail(f'--rewrites: {len(problems)} problem(s), nothing written:\n  - ' + '\n  - '.join(problems))
    return edits, notes


def template_keys(files, left):
    """The --rewrites-template keys: every preview sentence still to rewrite, minus any that only ever sits
    inside a longer one (it could never apply), with notes for any two that partly overlap."""
    keys = sorted(left.get('rewrite', {}))
    hits, clashes, _ = match_rewrites(files, keys)
    used = {h[3] for h in hits}
    notes = [f'--rewrites-template: fill in only one of these: {c}' for c in clashes]
    return [k for k in keys if k in used], notes


# ----------------------------------------------------------------------------------------------- checks after
TAG_TOKEN = re.compile(r'<!--.*?-->|<(/?)([a-zA-Z][\w:-]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*)>', re.S)
ATTR_NAME = re.compile(r'([^\s=/"\'>]+)(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\'>]+))?')


def shape(rel, src):
    """The tags and attribute names of a page, or the code (strings left out) of a script, in order. A rewrite
    changes wording only, so it must never change this: a stray quote or tag would."""
    if rel.endswith('.html'):
        return [(m.group(1), m.group(2).lower(), tuple(a.group(1).lower() for a in ATTR_NAME.finditer(m.group(3))))
                for m in TAG_TOKEN.finditer(src) if m.group(2)]
    if rel.endswith('.js'):
        return ''.join(c for c, k in zip(src, js_marks(src)) if k != 2)
    return None


def rewrite_damage(before, after, rels):
    """Files where a rewrite changed the markup or script structure (a stray quote, a tag): [] when none."""
    bad = []
    for rel in sorted(rels):
        if shape(rel, before[rel]) != shape(rel, after[rel]):
            bad.append(f'{rel}: your rewrite changed the page\'s tags or script, not just its wording')
    return bad


LDJSON_BLOCK = re.compile(r'<script\b[^>]*\btype="application/ld\+json"[^>]*>(.*?)</script\s*>', re.S | re.I)


def verify(files, opt, new_host, old_host_changed):
    """What must be true of a switched site. [] when all good."""
    bad = []
    long_date = f'{opt.launch_date.day} {opt.launch_date:%B %Y}'
    for rel in sorted(files):
        src = files[rel]
        if not rel.endswith('.html'):
            continue
        for m in re.finditer(r'<meta\b[^>]*\bname="robots"[^>]*>', src):
            if 'noindex' in (attr(m.group(0), 'content') or '').lower() and rel not in NO_INDEX_KEEP:
                bad.append(f'{rel}: still noindex')
        if re.search(r'class="preview-bar\b', src):
            bad.append(f'{rel}: preview banner still there')
        for m in re.finditer(r'<[a-zA-Z][^>]*?\sdata-preview\b[^>]*>', src):
            if not (opt.trade_ins == 'closed' and attr(m.group(0), 'id') == 'qt'):
                bad.append(f'{rel}:{line_of(src, m.start())}: data-preview still on <{m.group(0)[1:].split()[0]} id="{attr(m.group(0), "id")}">')
        if re.search(r'class="[^"]*\bpreview-note\b', src):
            bad.append(f'{rel}: "Not trading yet" box still there')
        if opt.trade_ins == 'open' and 'id="qtPreview"' in src:
            bad.append(f'{rel}: trade-in "open soon" note still there')
        if rel.startswith('products/'):
            ob = re.search(r'<(\w+)\b[^>]*\bid="orderBtn"[^>]*>', src)
            if not ob or ob.group(1).lower() != 'a' or not attr(ob.group(0), 'href'):
                bad.append(f'{rel}: Order control is not a link with an href ({ob.group(0) if ob else "missing"})')
        if 'id="contactForm"' in src and 'Order a phone' not in src:
            bad.append(f'{rel}: contact form has no "Order a phone" topic')
        if opt.set_dates:
            for m in re.finditer(r'<p\b[^>]*\bclass="legal-updated"[^>]*>([^<]*)</p>', src):
                if m.group(1).strip() != f'Last updated {long_date}':
                    bad.append(f'{rel}: "{m.group(1).strip()}" is not the launch date')
        for m in re.finditer(r'<link\b[^>]*\brel="canonical"[^>]*>', src):
            if not (attr(m.group(0), 'href') or '').startswith(f'https://{new_host}/'):
                bad.append(f'{rel}: canonical {attr(m.group(0), "href")} is not on https://{new_host}/')
        for m in LDJSON_BLOCK.finditer(src):
            try:
                json.loads(m.group(1))
            except ValueError as e:
                bad.append(f'{rel}:{line_of(src, m.start(1))}: structured data (JSON-LD) is no longer valid JSON ({e})')
    if 'robots.txt' not in files or robots_blocks_all(files['robots.txt']):
        bad.append('robots.txt does not allow crawling')
    sm = files.get('sitemap.xml')
    if sm is not None:
        for m in re.finditer(r'<lastmod>([^<]*)</lastmod>', sm) if opt.set_dates else ():
            if m.group(1).strip() != opt.launch_date.isoformat():
                bad.append(f'sitemap.xml: lastmod {m.group(1)} is not the launch date')
                break
        for m in re.finditer(r'<loc>([^<]*)</loc>', sm):
            if not m.group(1).startswith(f'https://{new_host}/'):
                bad.append(f'sitemap.xml: {m.group(1)} is not on https://{new_host}/')
    if old_host_changed:
        ob = old_host_changed[4:] if old_host_changed.startswith('www.') else old_host_changed
        nb = new_host[4:] if new_host.startswith('www.') else new_host
        # the old bare domain must be gone; if only www changed, every page address must be on the new host
        rx = (re.escape(ob) + r'(?![\w-]|\.\w)') if ob != nb else \
            (r'https?://(?!' + re.escape(new_host) + r'(?![\w-]|\.\w))(?:www\.)?' + re.escape(ob))
        left = [rel for rel, src in files.items() if re.search(rx, src, re.I)]
        if left:
            bad.append(f'old address {old_host_changed} still in: {", ".join(sorted(left))}')
    return bad


def in_preview(files):
    """True while any preview switch is still on: banner, noindex, data-preview on a picker or the contact
    form, or robots.txt shutting out every crawler. Then this run is the launch, and sets the dates."""
    for rel, src in files.items():
        if not rel.endswith('.html'):
            continue
        if re.search(r'class="preview-bar\b', src):
            return True
        if rel not in NO_INDEX_KEEP and any('noindex' in (attr(m.group(0), 'content') or '').lower()
                                            for m in re.finditer(r'<meta\b[^>]*\bname="robots"[^>]*>', src)):
            return True
        if re.search(r'<(?:form)\b[^>]*\bid="(?:picker|contactForm)"[^>]*\sdata-preview\b', src):
            return True
    return 'robots.txt' in files and robots_blocks_all(files['robots.txt'])


# ----------------------------------------------------------------------------------------------- report
def manual_items(opt, files):
    pages = sum(1 for r in files if r.startswith('products/') and r.endswith('.html'))
    items = []
    if opt.checkout == 'shopify':
        items.append('Shopify: set the products to Active and publish them (GO-LIVE.md section 5). The static product pages\' '
                     'Order buttons still take email orders through contact.html: point each one at its Shopify product, or retire '
                     'the static shop, or you will take orders in two places.')
    elif opt.checkout == 'stripe':
        filled = [k for k, v in pay_links(files.get('pay.js', '')) if v.strip()]
        items.append(f'Stripe: pay.js has {len(filled)} Payment Link(s). Deactivate the link in Stripe and clear it in pay.js the '
                     'moment that phone sells.')
    items.append('Republish the site (sites/README.md) and put one real order through end to end, then refund it.')
    items.append(f'Open all {pages} product pages on the published site. Each needs a clickable "Order — £…" button '
                 '("Buy now — £…" with a Payment Link, "Not in stock — ask us" for an option you don\'t hold) that '
                 'changes when you change storage, condition or colour. "Opening soon" or greyed-out options mean site.js didn\'t '
                 'load or data-prices is wrong (GO-LIVE.md section 6, step 3).')
    items.append('Open sell.html: the quote questions must appear, not "The instant quote hasn\'t loaded".')
    if opt.trade_ins == 'closed':
        items.append('Trade-ins stay closed: the quote tool still gives guide prices only. To open them, add a quote-sending form '
                     f'(#{", #".join(QT_SEND_IDS)}, as quote-ui.js expects) to sell.html and the sell/*.html pages, confirm the '
                     'trade-in prices (GO-LIVE.md section 1, item 7), then run this again with --trade-ins open.')
    items.append('Check the sections it can\'t judge: VAT line in the footers, WEEE take-back wording, the privacy policy naming '
                 'your host and email provider (GO-LIVE.md sections 1 to 3).')
    return items


def group_lines(groups, indent='    '):
    out = []
    for snippet, locs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[1][0])):
        files_n = len({x.rsplit(':', 1)[0] for x in locs})
        out.append(f'{indent}- {files_n} file{"s" if files_n != 1 else ""}: {show(snippet)}')
        out.append(f'{indent}  at {", ".join(locs)}')
    return out


def build_report(mode, site, opt, edits, edited_from, notes, blockers, warnings, left, rewrite_skipped, result):
    L = []
    L.append(f'Full Bars go-live switch: {mode}')
    L.append(f'Site: {os.path.abspath(site)}')
    dates = (f'{opt.launch_date.day} {opt.launch_date:%B %Y}' if opt.set_dates else 'left as they are (site already live)')
    L.append(f'Domain: {opt.bare} (pages at https://{opt.host}/, email hello@{opt.bare})   Checkout: {opt.checkout or "NOT CHOSEN"}   '
             f'Trade-ins: {opt.trade_ins}   Launch date: {dates}')
    if edits is not None:
        L.append('')
        changed_files = len({e.rel for e in edits})
        L.append(f'CHANGES ({len(edits)} in {changed_files} file{"s" if changed_files != 1 else ""}; '
                 f'{"none written: dry run" if mode.startswith("DRY") else "written" if mode.startswith(("DONE", "WRITTEN")) else "none written"})')
        L.append('  Line numbers are in the file as it was before the switch, except for your --rewrites, which are in the switched file.')
        for e in edits:
            L.append(describe(edited_from[e], e))
        kinds = {}
        for e in edits:
            k = re.sub(r':.*', '', e.what) if e.prio else e.what
            kinds[k] = kinds.get(k, 0) + 1
        L.append('  Summary:')
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            L.append(f'    {n:4d}  {k}')
    if left is not None:
        L.append('')
        rw, hand = left.get('rewrite', {}), left.get('hand', {})
        pieces, places = wording_left(left)
        L.append('STILL TO DO BY HAND')
        if pieces:
            L.append(f'  1. Rewrite the preview wording: {pieces} piece(s) of text in {places} place(s). It says the shop isn\'t '
                     'open, or talks about opening in the future, so it can\'t be switched mechanically, and a real run refuses '
                     'while any of it is left (unless you pass --allow-preview-wording: then don\'t publish until it\'s done). '
                     'Each sentence is shown as a customer reads it, which is exactly the key to put in a --rewrites file '
                     '(--rewrites-template writes them all for you).')
            L.extend(group_lines(rw))
            if hand:
                L.append('    Edit these by hand: scripts read these attributes too, so --rewrites leaves them alone.')
                L.extend(group_lines(hand, '      '))
        else:
            L.append('  1. Preview wording: none left on the pages.')
        if rewrite_skipped:
            L.append(f'    ({len(rewrite_skipped)} entr{"y" if len(rewrite_skipped) == 1 else "ies"} in your --rewrites file still null, so skipped)')
        for i, item in enumerate(manual_items(opt, result), 2):
            L.append(f'  {i}. {item}')
        if left.get('later'):
            L.append('')
            L.append('LEFT FOR WHEN TRADE-INS OPEN (true while they are closed; rewrite these when you run with --trade-ins open)')
            L.extend(group_lines(left['later']))
        if left.get('kept'):
            L.append('')
            L.append('PREVIEW HOOKS KEPT ON PURPOSE (trade-ins closed: the quote tool stays in guide-price mode)'
                     if opt.trade_ins == 'closed' else 'PREVIEW HOOKS LEFT (class, id and attribute names: never shown to customers)')
            L.extend(group_lines(left['kept']))
        if left.get('code'):
            L.append('')
            L.append('CODE THAT MENTIONS PREVIEW (no action: it only runs while data-preview is on, or it is a comment or a style)')
            L.extend(group_lines(left['code']))
    if notes:
        L.append('')
        L.append('NOTES')
        L.extend(f'  - {n}' for n in dict.fromkeys(notes))
    if warnings:
        L.append('')
        L.append(f'WARNINGS ({len(warnings)}: worth fixing, not blocking)')
        L.extend(f'  - {w}' for w in warnings)
    L.append('')
    if blockers:
        L.append(f'BLOCKERS ({len(blockers)}): fix these first, then run again')
        L.extend(f'  {i}. {b}' for i, b in enumerate(blockers, 1))
    else:
        L.append('BLOCKERS: none')
    return L


# ----------------------------------------------------------------------------------------------- main
def write_site(root, before, after):
    realroot = os.path.realpath(root)
    n = 0
    for rel, text in sorted(after.items()):
        if before.get(rel) == text:
            continue
        path = os.path.join(root, *rel.split('/'))
        real = os.path.realpath(path)
        if not real.startswith(realroot + os.sep) or os.path.islink(path):
            raise Fail(f'refusing to write {rel}: it is outside {root}')
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.go_live-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text)
            if os.path.exists(path):
                shutil.copymode(path, tmp)
            else:
                os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        n += 1
    return n


def outside(path, site):
    rp, rs = os.path.realpath(path), os.path.realpath(site)
    return rp != rs and not rp.startswith(rs + os.sep)


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog='go_live.py',
        description='Full Bars launch-day switch: turns the preview site live (robots, noindex, banner, data-preview, Order '
                    'buttons, preview notes, dates, domain, and your --rewrites of the preview wording), and refuses while '
                    'launch blockers remain. Do the real run on a copy or a git branch. Plain-English guide: the top of this file.',
        epilog='Example: python3 launch/full-bars/go_live.py --site ~/full-bars-copy --domain fullbars.co.uk --checkout stripe '
               '--dry-run --out ~/go-live-report.txt --rewrites-template ~/rewrites.json   (exit 0 = done and ready to publish, '
               '1 = blockers or a failed check, 2 = bad arguments, 3 = switched but NOT READY TO PUBLISH: preview wording left)')
    ap.add_argument('--site', required=True, metavar='DIR', help='the site folder to switch (edited in place unless --dry-run)')
    ap.add_argument('--domain', required=True, help='the shop\'s domain, e.g. fullbars.co.uk (pages go on www.DOMAIN, email hello@DOMAIN)')
    ap.add_argument('--checkout', choices=('shopify', 'stripe'), help='GO-LIVE.md decision 1. Required before it will switch anything')
    ap.add_argument('--trade-ins', dest='trade_ins', choices=('closed', 'open'), default='closed',
                    help='closed (default): the quote tool keeps giving guide prices only. open: switch it on (needs a send form)')
    ap.add_argument('--dry-run', action='store_true', help='print exactly what would change (file, line, before, after); write nothing')
    ap.add_argument('--check-only', dest='check_only', action='store_true',
                    help='only list the launch blockers (exit 1 if there are any); writes nothing')
    ap.add_argument('--force-preview-check-only', dest='check_only', action='store_true', help=argparse.SUPPRESS)  # old name
    ap.add_argument('--allow-preview-wording', action='store_true',
                    help='switch even though preview wording ("When we open ...") is still on the pages; the run then ends '
                         'NOT READY TO PUBLISH (exit 3) and you rewrite it by hand before publishing')
    ap.add_argument('--out', metavar='REPORT', help='also save the full report to this file (must be outside --site)')
    ap.add_argument('--launch-date', metavar='YYYY-MM-DD',
                    help='date for "Last updated" and the sitemap (default: today, and only in the run that switches the site '
                         'out of preview; on a site that is already live the dates change only if you pass this)')
    ap.add_argument('--rewrites', metavar='JSON', help='file of {"sentence as on the page": "new wording"} applied wherever the '
                    'sentence appears, escaped for each place (null = skip, "" = delete)')
    ap.add_argument('--rewrites-template', metavar='JSON', help='write a --rewrites file listing every sentence still to rewrite')
    ap.add_argument('--no-www', action='store_true', help='use https://DOMAIN/ rather than https://www.DOMAIN/ for page addresses')
    return ap.parse_args(argv)


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors='replace')
    except AttributeError:
        pass
    opt = parse_args(argv)
    try:
        return run(opt)
    except Fail as e:
        print(f'go_live.py: {e}', file=sys.stderr)
        return 1


def run(opt):
    site = opt.site
    if not os.path.isdir(site) or not os.path.isfile(os.path.join(site, 'index.html')) \
            or not os.path.isdir(os.path.join(site, 'products')):
        print(f'go_live.py: {site} is not the Full Bars site folder (no index.html and products/)', file=sys.stderr)
        return 2
    for flag, path in (('--out', opt.out), ('--rewrites-template', opt.rewrites_template)):
        if path and not outside(path, site):
            print(f'go_live.py: {flag} {path} is inside --site, so it would be published with the site. Put it somewhere else.',
                  file=sys.stderr)
            return 2
        if path and os.path.isdir(path):
            print(f'go_live.py: {flag} {path} is a folder, not a file', file=sys.stderr)
            return 2
    if opt.rewrites_template and os.path.exists(opt.rewrites_template):
        print(f'go_live.py: {opt.rewrites_template} already exists; delete or move it first (it may hold your rewrites)', file=sys.stderr)
        return 2
    opt.launch_date_given = bool(opt.launch_date)
    try:
        opt.launch_date = datetime.date.fromisoformat(opt.launch_date) if opt.launch_date else datetime.date.today()
    except ValueError:
        print(f'go_live.py: --launch-date {opt.launch_date!r} is not YYYY-MM-DD', file=sys.stderr)
        return 2
    try:
        opt.bare, opt.host = parse_domain(opt.domain, opt.no_www)
    except Fail as e:
        print(f'go_live.py: {e}', file=sys.stderr)
        return 2

    files = load_site(site)
    blockers, warnings = find_blockers(site, files, opt)

    old_host = current_host(files)
    # Dates change only in the run that takes the site out of preview, or when asked: a rerun on a live site
    # (to apply more --rewrites, say) must not claim the legal pages were updated today.
    opt.set_dates = in_preview(files) or opt.launch_date_given
    mech, notes = plan_switches(files, opt)
    if not opt.set_dates:
        notes.append('The site is already out of preview, so the "Last updated" dates on the legal pages and the sitemap '
                     'dates were left as they are. Pass --launch-date YYYY-MM-DD if you do want to change them.')
    dom = domain_edits(files, old_host, opt.bare, opt.host)
    stage_a = resolve(files, mech + dom)
    if old_host != opt.host:
        for e in stage_a:
            if e.prio == 0 and old_host in e.new:
                raise Fail(f'internal: switch at {e.rel}:{e.line} would write the old domain')
    switched = apply_edits(files, stage_a)
    edited_from = {e: files for e in stage_a}
    edits = list(stage_a)
    skipped, rewritten = [], set()
    if opt.rewrites:
        rewrites, skipped = load_rewrites(opt.rewrites)
        rw_edits, rw_notes = rewrite_edits(switched, rewrites, opt.bare, opt.host, old_host if old_host != opt.host else None)
        stage_b = resolve(switched, rw_edits)
        notes += rw_notes
        edited_from.update({e: switched for e in stage_b})
        edits += stage_b
        result = apply_edits(switched, stage_b)
        rewritten = {e.rel for e in stage_b}
    else:
        result = switched
    left = leftovers(result, opt)
    changed_host = old_host if old_host != opt.host else None
    problems = verify(result, opt, opt.host, changed_host) + rewrite_damage(switched, result, rewritten)

    if opt.rewrites_template:
        keys, tnotes = template_keys(result, left)
        with open(opt.rewrites_template, 'w', encoding='utf-8') as fh:
            json.dump({k: None for k in keys}, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
        notes += tnotes
        notes.append(f'Wrote {opt.rewrites_template}: {len(keys)} sentence(s), each set to null. Replace each null with the new '
                     'wording in plain text ("" deletes the sentence), then run again with --rewrites.')
    if problems:
        blockers = blockers + [f'the switch would be incomplete: {p}' for p in problems]
    pieces, places = wording_left(left)
    if pieces and not opt.allow_preview_wording:
        blockers.append(wording_blocker(left, listing=opt.check_only))
    elif pieces:
        warnings.append(f'--allow-preview-wording: {pieces} piece(s) of preview wording in {places} place(s) would stay on the '
                        'pages, so the switched site is NOT READY TO PUBLISH until they are rewritten.')

    if opt.check_only:
        report = build_report('BLOCKER CHECK ONLY (nothing written)', site, opt, None, None, notes if opt.rewrites_template else [],
                              blockers, warnings, None, [], files)
        if blockers:
            report.append(f'RESULT: {len(blockers)} blocker(s): not ready to launch.')
            return finish(report, opt, 1)
        if pieces:
            report.append(f'RESULT: no blockers, but NOT READY TO PUBLISH: the switch would leave {pieces} piece(s) of preview '
                          'wording on the pages (--allow-preview-wording).')
            return finish(report, opt, 3)
        report.append('RESULT: no blockers: ready to switch.')
        return finish(report, opt, 0)

    if opt.dry_run:
        report = build_report('DRY RUN (nothing written)', site, opt, edits, edited_from, notes, blockers, warnings, left, skipped, result)
        head = f'RESULT: dry run. {len(edits)} change(s) would be made. '
        if blockers:
            report.append(head + f'{len(blockers)} blocker(s): a real run would refuse.')
            return finish(report, opt, 1)
        if pieces:
            report.append(head + 'No blockers: a real run would go ahead, but end NOT READY TO PUBLISH, because preview '
                          'wording would still be on the pages (--allow-preview-wording).')
            return finish(report, opt, 3)
        report.append(head + 'No blockers: a real run would go ahead.')
        return finish(report, opt, 0)

    if blockers:
        report = build_report('REFUSED (nothing written)', site, opt, edits, edited_from, notes, blockers, warnings, left, skipped, result)
        report.append(f'RESULT: REFUSED. {len(blockers)} blocker(s) remain, so nothing was written. Fix them and run again.')
        return finish(report, opt, 1)

    n = write_site(site, files, result)
    after = load_site(site)
    problems = verify(after, opt, opt.host, changed_host) + run_checks(site)
    left_after = leftovers(after, opt)
    pieces, places = wording_left(left_after)
    mode = 'WRITTEN, BUT CHECKS FAILED' if problems else 'WRITTEN, NOT READY TO PUBLISH' if pieces else 'DONE'
    report = build_report(mode, site, opt, edits, edited_from, notes, [f'after writing: {p}' for p in problems], warnings,
                          left_after, skipped, after)
    if problems:
        report.append(f'RESULT: {len(edits)} change(s) written to {n} file(s), but the checks above failed. Don\'t publish yet.')
        return finish(report, opt, 1)
    if pieces:
        report.append(f'RESULT: NOT READY TO PUBLISH. {len(edits)} change(s) written to {n} file(s) and the checks pass, but '
                      f'{pieces} piece(s) of preview wording in {places} place(s) are still on the pages (you passed '
                      '--allow-preview-wording). Rewrite them (STILL TO DO BY HAND, item 1), for example by running this again '
                      'with --rewrites, before you publish.')
        return finish(report, opt, 3)
    report.append(f'RESULT: done. {len(edits)} change(s) written to {n} file(s); checks pass and no preview wording is left. '
                  'Now do the items under STILL TO DO BY HAND, then publish.')
    return finish(report, opt, 0)


def wording_blocker(left, listing=False):
    pieces, places = wording_left(left)
    msg = (f'preview wording would still be on the live pages: {pieces} piece(s) of text in {places} place(s) '
           f'({"listed below" if listing else "STILL TO DO BY HAND, item 1"}). Put the new wording in a --rewrites file '
           '(--rewrites-template writes one for you), or pass --allow-preview-wording to switch anyway and rewrite it by '
           'hand before you publish')
    if listing:
        groups = list(left.get('rewrite', {}).items()) + [(k + '  [edit by hand]', v) for k, v in left.get('hand', {}).items()]
        for k, locs in sorted(groups, key=lambda kv: (-len(kv[1]), kv[0])):
            msg += f'\n       - {show(k, 110)} ({len(locs)} place{"s" if len(locs) != 1 else ""})'
    return msg


def finish(report, opt, code):
    text = '\n'.join(report) + '\n'
    sys.stdout.write(text)
    if opt.out:
        with open(opt.out, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return code


if __name__ == '__main__':
    sys.exit(main())
