#!/usr/bin/env python3
"""Full Bars: check every handset spec the site states against facts.json.

WHAT IT IS FOR
  The same facts about each phone (weight, screen size, chip, port, battery hours, launch year, main
  camera, telephoto zoom, software-update estimate, water resistance, Apple Intelligence, ProMotion and
  refresh rate) are written on up to 20 pages: the product page, the cards and comparison tables on
  collection pages, the buying guide, FAQs, structured data (JSON-LD), titles and meta tags. facts.json,
  next to this script, is the one place they are written down. This script reads every page of the site
  and fails if any value it finds disagrees with facts.json, and says exactly where.

HOW TO USE IT (from the repo root)
  python3 launch/full-bars/check_site_facts.py                 check sites/full-bars
  python3 launch/full-bars/check_site_facts.py --site DIR      check another copy of the site
  python3 launch/full-bars/check_site_facts.py --where "iPhone 12 Pro" weight_g
                                                               list every place that fact appears (the
                                                               page name iphone-12-pro works too)
  python3 launch/full-bars/check_site_facts.py --stats         how many mentions of each spec it found

  To change a fact (say a weight was wrong): edit the value in facts.json, run this, and fix every page
  it lists as FAIL. After editing wording on any page, run it again. build_shopify_csv.py reads the
  handset weights from facts.json too, so rebuild the CSV after changing a weight.

HOW IT DECIDES WHICH PHONE A VALUE BELONGS TO
  - Product-page spec rows, the year under the product name and the "In the box" cable: that page's phone.
  - Tables with a "Model" column: the row's phone; the column header says which spec it is.
  - Product cards: the phone the card links to (including its data-usbc attribute).
  - Sentences: the phones named in that sentence, or in that part of it when it is split by ";" or
    ", and / but / while the iPhone X...". A sentence that names none is about the page's own phone
    (product and trade-in pages) or the phones on a collection page. On a product page the page's phone
    counts too unless the sentence opens with another phone ("The iPhone 15 Pro adds USB-C").
  - Tied values: "iPhone 14 Plus (203g)", "early 2028 (S23)", "164g for the iPhone 12" and
    "2x on the iPhone 12 Pro" belong to that phone only. A value after "against", "instead of" or
    "rather than" belongs to the phone being compared, and a phone after "Over the", "Against the" or
    "than the" is only the comparison, not the subject.
  - Every / all / iPhone 15 and later: true of each phone in the group. Otherwise, when a sentence names
    several phones, a value passes if it is right for at least one of them.
  - FAQ answers: also about the phone named in the question. "Does the iPhone 15 support Apple
    Intelligence?" answered "No" is checked as a no.
  - Differences ("31g heavier than the iPhone 14", "six more hours", "(28 against 22)") and
    "at 85% health expect roughly 14 hours" are worked out from facts.json and checked too.
  Skipped on purpose: approximate values ("around 200g", "6.1 inches or larger"), questions, cable and
  charger names ("USB-C to Lightning cable"), range names ("USB-C iPhones") and any sentence that
  names a phone we don't sell.

OUTPUT AND EXIT CODE
  FAIL lines (exit 1) for every conflict, NOTE lines for things it couldn't read, then a summary.
  Exit 2 if facts.json is missing or malformed, doesn't match the product pages, or the site can't be
  read. It only reads files; it never writes anything.
Python 3 standard library only.
"""
import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FACTS = os.path.join(HERE, 'facts.json')

SPEC_LABEL = {
    'weight_g': 'weight', 'screen_in': 'screen size', 'chip': 'chip', 'port': 'port',
    'battery_hours': 'battery hours', 'battery_mah': 'battery capacity', 'year': 'launch year',
    'launch_month': 'launch month', 'main_camera_mp': 'main camera', 'updates_until': 'software updates',
    'android_until': 'last Android version', 'ip_rating': 'water resistance', 'apple_intelligence':
    'Apple Intelligence', 'promotion': 'ProMotion', 'max_refresh_hz': 'screen refresh rate',
    'telephoto_x': 'telephoto zoom',
}
REQUIRED = {
    'name': str, 'aliases': list, 'weight_g': int, 'screen_in': str, 'chip': str, 'port': str,
    'battery_hours': int, 'battery_basis': str, 'year': int, 'main_camera_mp': int,
    'updates_until': str, 'ip_rating': str, 'apple_intelligence': bool, 'promotion': bool,
    'max_refresh_hz': int, 'telephoto_x': int,
}
OPTIONAL = {'battery_mah': int, 'launch_month': str, 'android_until': int, 'updates_basis': str}

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']
MONTH_RX = (r'(?:January|February|March|April|May|June|July|August|September|October|November|December|'
            r'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)')
WORDNUM = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
           'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
NUM_RX = r'(\d{1,2}|' + '|'.join(WORDNUM) + r')'


class FactsError(Exception):
    pass


# ------------------------------------------------------------------------------------------ helpers

def find_site():
    for start in (HERE, os.getcwd()):
        d = start
        while True:
            cand = os.path.join(d, 'sites', 'full-bars')
            if os.path.isfile(os.path.join(cand, 'shop.html')):
                return cand
            if os.path.dirname(d) == d:
                break
            d = os.path.dirname(d)
    return None


INLINE_TAG = re.compile(r'</?(?:a|b|i|em|strong|span|small|abbr|code|sup|sub|time|mark|q|s|u|bdi|wbr)\b[^>]*>')


def to_text(fragment):
    """Visible text of an HTML fragment: inline tags dropped, other tags become spaces, entities decoded."""
    t = re.sub(r'<br\s*/?>', ' ', fragment)
    t = INLINE_TAG.sub('', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html.unescape(t).replace('\xa0', ' ').replace('\u2009', ' ')
    return re.sub(r'\s+', ' ', t).strip()


def attr(tag, name):
    m = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', tag)
    return html.unescape(m.group(1)) if m else None


def month_name(s):
    if not s:
        return None
    s = s.rstrip('.').lower()
    for m in MONTHS:
        if m.lower().startswith(s[:3]):
            return m
    return None


def norm_chip(s):
    s = s or ''
    m = re.search(r'\bA(1\d)(\s+Pro)?\b', s)
    if m:
        return 'A' + m.group(1) + (' Pro' if m.group(2) else '')
    m = re.search(r'Snapdragon\s+8\s+Gen\s+(\d)', s)
    if m:
        return 'Snapdragon 8 Gen ' + m.group(1)
    m = re.search(r'Tensor\s+G(\d)', s)
    if m:
        return 'Tensor G' + m.group(1)
    return s.strip()


UNTIL_RX = re.compile(r'(?:(?P<qual>early|mid|late)[\s-]+)?(?:(?P<mon>' + MONTH_RX + r')\.?\s+)?'
                      r'(?P<y1>20\d\d)(?:\s*[\u2013\u2014-]\s*(?P<y2>\d{4}|\d{2})\b)?')


def parse_until(s):
    m = UNTIL_RX.search(s or '')
    if not m:
        return None
    y1 = int(m.group('y1'))
    y2 = m.group('y2')
    y2 = y1 if not y2 else (int(y2) if len(y2) == 4 else y1 // 100 * 100 + int(y2))
    return {'y1': y1, 'y2': y2, 'mon': month_name(m.group('mon')), 'qual': m.group('qual')}


def until_text(u):
    s = f"{u['y1']}" if u['y1'] == u['y2'] else f"{u['y1']}\u2013{u['y2']}"
    if u['mon']:
        s = u['mon'] + ' ' + s
    if u['qual']:
        s = u['qual'] + ' ' + s
    return s


def num(s):
    s = s.lower()
    return WORDNUM[s] if s in WORDNUM else int(s)


# ------------------------------------------------------------------------------------------ facts

def load_facts(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FactsError(f'{path} not found')
    except json.JSONDecodeError as e:
        raise FactsError(f'{path} is not valid JSON: {e}')
    models = data.get('models') if isinstance(data, dict) else None
    if not isinstance(models, dict) or not models:
        raise FactsError(f'{path}: no "models" object')
    problems = []
    for h, m in models.items():
        if not isinstance(m, dict):
            problems.append(f'{h}: not an object')
            continue
        for k, t in REQUIRED.items():
            v = m.get(k)
            if not isinstance(v, t) or (t is int and isinstance(v, bool)):
                problems.append(f'{h}: "{k}" must be {t.__name__}, got {v!r}')
        for k, t in OPTIONAL.items():
            if k in m and m[k] is not None and (not isinstance(m[k], t) or (t is int and isinstance(m[k], bool))):
                problems.append(f'{h}: "{k}" must be {t.__name__} or null, got {m[k]!r}')
        if isinstance(m.get('port'), str) and m['port'] not in ('Lightning', 'USB-C'):
            problems.append(f'{h}: "port" must be "Lightning" or "USB-C"')
        if isinstance(m.get('screen_in'), str) and not re.fullmatch(r'\d\.\d', m['screen_in']):
            problems.append(f'{h}: "screen_in" must look like "6.1"')
        if isinstance(m.get('updates_until'), str) and not parse_until(m['updates_until']):
            problems.append(f'{h}: "updates_until" has no year')
        if isinstance(m.get('weight_g'), int) and not 80 <= m['weight_g'] <= 400:
            problems.append(f'{h}: "weight_g" {m["weight_g"]} is not a handset weight in grams')
        if m.get('launch_month') and not month_name(m['launch_month']):
            problems.append(f'{h}: "launch_month" {m["launch_month"]!r} is not a month')
    if problems:
        raise FactsError(f'{path}:\n  ' + '\n  '.join(problems))
    return data


# ------------------------------------------------------------------------------------------ phone names

class Lexicon:
    """Finds phone names, short names and groups ("every iPhone 15", "iPhone 14 and earlier") in text."""

    def __init__(self, models):
        self.models = models
        self.handles = list(models)
        self.series = {}     # handle -> (series number, variant) for iPhones
        alias_list = []
        for h, m in models.items():
            mm = re.fullmatch(r'iPhone (\d+)(?: (Pro Max|Pro|Plus|mini))?', m['name'])
            if mm:
                self.series[h] = (int(mm.group(1)), mm.group(2) or '')
            for a in {m['name'], *m.get('aliases', [])}:
                alias_list.append((a, h))
        alias_list.sort(key=lambda x: -len(x[0]))
        self.alias_rx = [(re.compile(r'(?<![\w-])' + re.escape(a).replace(r'\ ', r'\s+') + r'(?![\w-])'), h)
                         for a, h in alias_list]
        self.by_series = {}
        for h, (n, v) in self.series.items():
            self.by_series.setdefault(n, []).append(h)

    def series_set(self, test):
        return {h for h, (n, _) in self.series.items() if test(n)}

    def find(self, text, context=()):
        """Return a list of mentions: dicts with start, end, handles (set), kind, all (quantified group)."""
        found = []

        def add(m, handles, kind, prio, quant=False):
            if handles or kind == 'unknown':
                found.append({'start': m.start(), 'end': m.end(), 'handles': set(handles), 'kind': kind,
                              'prio': prio, 'all': quant})

        S = self.series_set
        for m in re.finditer(r'\b(?P<q>[Ee]very|[Aa]ll|[Aa]ny)\s+iPhone\s+(?P<a>1\d)(?:\s+(?:and|&)\s+(?P<b>1\d))?'
                             r'(?!\s*(?:Pro|Plus|mini)\b)(?:\s+(?:we sell|models?))?', text):
            ns = {int(m.group('a'))} | ({int(m.group('b'))} if m.group('b') else set())
            add(m, S(lambda n: n in ns), 'group', 0, quant=True)
        for m in re.finditer(r'\biPhone\s+(1\d)\s+(?:(?:and|or)\s+(?:later|newer)|onwards)\b', text):
            n0 = int(m.group(1))
            add(m, S(lambda n: n >= n0), 'group', 0, quant=True)
        for m in re.finditer(r'\b[Ee]very\s+iPhone\s+(?:before|until|up to)\s+the\s+(1\d)\b', text):
            n0 = int(m.group(1))
            add(m, S(lambda n: n < n0), 'group', 0, quant=True)
        for m in re.finditer(r'\biPhone\s+(1\d)\s+(?:and|or)\s+(?:earlier|older)\b', text):
            n0 = int(m.group(1))
            add(m, S(lambda n: n <= n0), 'group', 0, quant=True)
        for m in re.finditer(r'\biPhone\s+(1\d)\s+(?:range|series|family|line-up|models)\b', text):
            n0 = int(m.group(1))
            add(m, S(lambda n: n == n0), 'group', 0)
        for m in re.finditer(r'\biPhone\s+(1\d)\s+(?:and|&)\s+(1\d)\b(?!\s*(?:Pro|Plus|mini)\b)', text):
            ns = {int(m.group(1)), int(m.group(2))}
            add(m, S(lambda n: n in ns), 'group', 0)
        for m in re.finditer(r'\b(?:iPhone\s+)?(1\d)\s+Pro\s+models\b', text):
            n0 = int(m.group(1))
            add(m, {h for h, (n, v) in self.series.items() if n == n0 and v.startswith('Pro')}, 'group', 0)
        for m in re.finditer(r'\b[Ee]very\s+(?:model|phone)\s+we\s+sell\b', text):
            add(m, set(self.handles), 'group', 0, quant=True)
        # phones we don't sell: any value near them can't be checked
        for m in re.finditer(r'\biPhone\s+(?:1[01]|1[7-9]|[2-9])\b|\biPhone\s+(?:X[SR]?|SE|Air)\b|'
                             r'\bGalaxy\s+(?:S(?!23\b)\d+|A\d+|Z\s?\w+|Note)\b|\bPixel\s+(?!8\b)\d+\w*|'
                             r'(?<![\w-])1[7-9]\s+(?:Pro|Plus|Air)\b', text):
            add(m, set(), 'unknown', 0)
        for rx, h in self.alias_rx:
            for m in rx.finditer(text):
                if h in ('pixel-8',) and re.match(r'\s*Stand\b', text[m.end():]):
                    continue
                add(m, {h}, 'model', 1)
        for m in re.finditer(r'\b(?:the|standard)\s+(1[2-6])(?=[\s.,;:!?)]|$)(?!\s+(?:Pro|Plus|mini|series|range|'
                             r'models?|family|line|onwards|months?|days?|hours?|GB|TB|MP|x\b|g\b|mm\b|%))', text):
            add(m, set(self.by_series.get(int(m.group(1)), [])) & {h for h, s in self.series.items() if s[1] == ''},
                'model', 2)
        for m in re.finditer(r'\b[Tt]he\s+(Pro\s+Max|Pro(?!\s+Max)|Plus|mini)\b(?!\s+(?:models?|iPhones?|phones?))', text):
            v = re.sub(r'\s+', ' ', m.group(1))
            pool = {h for h in context if self.series.get(h, (0, None))[1] == v}
            if len(pool) == 1:
                add(m, pool, 'model', 2)
            else:
                add(m, set(), 'unknown', 2)
        found.sort(key=lambda f: (f['start'], -(f['end'] - f['start']), f['prio']))
        out, last_end = [], -1
        for f in found:
            if f['start'] >= last_end:
                out.append(f)
                last_end = f['end']
        return out


# ------------------------------------------------------------------------------------------ claims

class Claim:
    """One value stated in the text: spec, value and where it sits (start/end offsets in that text)."""
    __slots__ = ('spec', 'value', 'start', 'end', 'raw', 'comparison', 'derived85', 'negated', 'kind')

    def __init__(self, spec, value, start, end, raw, comparison=False, derived85=False, negated=False, kind='value'):
        self.spec, self.value, self.start, self.end, self.raw = spec, value, start, end, raw
        self.comparison = comparison    # follows "against", "instead of"...: about the other phone
        self.derived85 = derived85      # "at 85% health, roughly N hours": N = 85% of the battery figure
        self.negated = negated          # "no ProMotion", "doesn't have USB-C"
        self.kind = kind                # 'value', or 'diff' for "31g heavier", "six more hours"


COMPARE_BEFORE = re.compile(r'(?:\bagainst|\binstead of|\brather than(?: the)?|\bthan(?: the| an?)?|'
                            r'\bcompared with(?: the| an?)?|\bvs\.?|\bsame as(?: the| an?)?|\blike(?: the| an?)?)\s*$', re.I)
APPROX_BEFORE = re.compile(r'\b(?:around|about|roughly|approximately|nearly|almost|some|under|over|'
                           r'less than|more than|up to)\s*$', re.I)
APPROX_BEFORE_HOURS = re.compile(r'\b(?:around|about|roughly|approximately|nearly|almost|some)\s*$', re.I)
RELATIVE_AFTER = re.compile(r'^\s*(?:more|less|fewer|extra|heavier|lighter|longer|shorter|bigger|smaller|'
                            r'taller|thinner)\b', re.I)
CLAUSE_BREAK = re.compile(r'[,;:()\u2014]|\bbut\b|\bwhile\b|\bwhereas\b', re.I)
NEG_DIRECT = re.compile(r"(?:\b(?:no|not|without|lacks?)|n['\u2019]t\s+(?:have|use|support|get|come\s+with|charge\s+(?:over|with)))"
                        r"\s+(?:an?\s+|the\s+)?$", re.I)
NEGATION = re.compile(r"\b(?:no|not|none|neither|nor|without|lacks?|lacking)\b|n['\u2019]t\b", re.I)
COMPARATOR_BEFORE = re.compile(r'(?:\bover|\bagainst|\bthan|\bdifference from|\bcompared (?:with|to)|\bunlike|'
                               r'\bversus|\bvs\.?)\s+(?:the\s+|an?\s+)?$', re.I)
CLAUSE_SPLIT = re.compile(r';\s*|,\s+(?=(?:and|but|while|whereas|which)\s)')
PRONOUN = re.compile(r"\b(?:it|it['\u2019]s|its|they|these|those|here|this phone|this one)\b", re.I)
UPDATE_CONTEXT = re.compile(r'\b(?:updates?|upgrades?|iOS|support(?:ed)?|security|Android|promise)\b', re.I)
BATTERY_CONTEXT = re.compile(r'\b(?:video|playback|battery|batteries|typical use|stamina|use)\b', re.I)


def negated_before(text, pos):
    seg = text[:pos]
    cut = 0
    for m in CLAUSE_BREAK.finditer(seg):
        cut = m.end()
    return bool(NEGATION.search(seg[cut:]))


def extract_claims(text, only=None):
    """Find every spec value stated in a sentence or table cell. `only` limits it to some specs."""
    claims = []

    def want(*specs):
        return only is None or any(s in only for s in specs)

    def before(m, n=40):
        return text[max(0, m.start() - n):m.start()]

    def after(m, n=30):
        return text[m.end():m.end() + n]

    def mk(spec, value, m, grp=0, **kw):
        s, e = (m.start(grp), m.end(grp))
        kw.setdefault('comparison', bool(COMPARE_BEFORE.search(text[max(0, s - 30):s])))
        claims.append(Claim(spec, value, s, e, m.group(0), **kw))

    if want('weight_g'):
        for m in re.finditer(r'(?<![\d.,])(\d{2,3})\s?g\b', text):
            if RELATIVE_AFTER.match(after(m)):
                c = Claim('weight_g', int(m.group(1)), m.start(), m.end(), m.group(0), kind='diff')
                if not re.search(r'\d\s*(?:to|-|\u2013)\s*$', before(m, 8)):     # "28 to 36g more": a range
                    claims.append(c)
                continue
            if re.search(r'\d\s*(?:to|-|\u2013)\s*$', before(m, 8)) or len(m.group(1)) < 3:
                continue
            if APPROX_BEFORE.search(before(m, 20)):
                continue
            mk('weight_g', int(m.group(1)), m)
    if want('screen_in'):
        for m in re.finditer(r'(?<![\d.])(\d\.\d)\s?(?:-inch|\u2033|\u201d|"| inches\b| inch\b|-in\b)', text):
            if APPROX_BEFORE.search(before(m, 20)) or RELATIVE_AFTER.match(after(m)) or \
                    re.match(r'\s*(?:or|and)\s+(?:larger|bigger|smaller|more|less|up|over|under)\b', after(m)):
                continue
            mk('screen_in', m.group(1), m)
    if want('chip'):
        for m in re.finditer(r'\bA1\d(?:\s+Pro\b|\s+Bionic\b)?|\bSnapdragon\s+8\s+Gen\s+\d|\b(?:Google\s+)?Tensor\s+G\d', text):
            mk('chip', norm_chip(m.group(0)), m)
    if want('port'):
        for m in re.finditer(r'\bUSB-C\b|\bLightning\b', text):
            b, a = before(m, 6), after(m, 40)
            if re.search(r'(?:USB-C|Lightning)\s+to\s*$', text[max(0, m.start() - 16):m.start()]) or \
                    re.match(r'\s+to\s+(?:USB-C|Lightning)\b', a):
                continue            # a cable: "USB-C to Lightning"
            if re.match(r'\s+(?:power\s+adapters?|adapters?|chargers?|power\s+banks?|cables?)\b', a):
                continue            # an accessory, not the phone's port
            if re.match(r'\s+(?:iPhones?|phones?|models?|range|collection)\b', a):
                continue            # a category name: "USB-C iPhones"
            mk('port', m.group(0), m, negated=bool(NEG_DIRECT.search(before(m, 40))))
    if want('battery_hours') and re.search(r'\b(?:hours?|hrs)\b', text) and BATTERY_CONTEXT.search(text):
        for m in re.finditer(r'(?<![\d.,])(\d{1,2})\s?(?:hours?|hrs)\b', text):
            if RELATIVE_AFTER.match(after(m)):
                claims.append(Claim('battery_hours', int(m.group(1)), m.start(), m.end(), m.group(0), kind='diff'))
                continue
            if APPROX_BEFORE_HOURS.search(before(m, 20)):
                if '85%' in text:
                    mk('battery_hours', int(m.group(1)), m, derived85=True)
                continue
            if re.search(r'\b(?:within|in|every|after|for)\s*$', before(m, 10)):
                continue            # "within 24 hours of it arriving"
            mk('battery_hours', int(m.group(1)), m)
        # bare numbers tied to hours: "(28 against 22)", "17 against 19 hours", "29 on the iPhone 14 Pro Max"
        for m in re.finditer(r'(?<![\d.,\u00a3])\b(\d{1,2})\s+against\s+(\d{1,2})\b(?![.,]\d)(\s*(?:hours?|hrs)\b)?', text):
            claims.append(Claim('battery_hours', int(m.group(1)), m.start(1), m.end(1), m.group(0)))
            if not m.group(3):      # "19 hours" is already picked up above
                claims.append(Claim('battery_hours', int(m.group(2)), m.start(2), m.end(2), m.group(0), comparison=True))
        for m in re.finditer(r'(?<![\d.,\u00a3])\bagainst\s+(\d{1,2})\b(?![.,]\d)(?!\s*(?:hours?|hrs|g\b|mm|MP|%))', text):
            if not re.search(r'\d\s+$', text[:m.start()]):
                claims.append(Claim('battery_hours', int(m.group(1)), m.start(1), m.end(1), m.group(0), comparison=True))
        for m in re.finditer(r'(?:,|\band)\s+(\d{1,2})\s+(?=on\s+the\s|for\s+the\s)', text):
            claims.append(Claim('battery_hours', int(m.group(1)), m.start(1), m.end(1), m.group(0)))
        for m in re.finditer(r'\b' + NUM_RX + r'\s+(?:more|fewer|less|extra)\s+(?:hours?\b|than\b)|'
                             r'\b' + NUM_RX + r'\s+hours?\s+(?:less|more|longer|shorter)\b', text, re.I):
            g = m.group(1) or m.group(2)
            claims.append(Claim('battery_hours', num(g), m.start(), m.end(), m.group(0), kind='diff'))
    if want('battery_mah'):
        for m in re.finditer(r'\b(\d,\d{3}|\d{4})\s?mAh\b', text):
            mk('battery_mah', int(m.group(1).replace(',', '')), m)
    if want('year', 'launch_month'):
        for m in re.finditer(r'\b(?:a|the)\s+(20[12]\d)\s+model\b', text):
            mk('year', int(m.group(1)), m, 1)
        for m in re.finditer(r'\b(?:its|their)\s+(?:(' + MONTH_RX + r')\s+)?(20[12]\d)\s+launch\b|'
                             r'\blaunch(?:ed)?\s+in\s+(?:(' + MONTH_RX + r')\s+)?(20[12]\d)\b', text):
            y = m.group(2) or m.group(4)
            mon = m.group(1) or m.group(3)
            grp = 2 if m.group(2) else 4
            mk('year', int(y), m, grp)
            if mon:
                mk('launch_month', month_name(mon), m, 1 if m.group(1) else 3)
    if want('updates_until', 'android_until') and UPDATE_CONTEXT.search(text):
        for m in re.finditer(r'\b(?:until|to|till|through|end)\s+(?:around\s+|about\s+)?((?:(?:early|mid|late)[\s-]+)?'
                             r'(?:' + MONTH_RX + r'\.?\s+)?20\d\d(?:\s*[\u2013\u2014-]\s*(?:\d{4}|\d{2})\b)?)', text):
            mk('updates_until', parse_until(m.group(1)), m, 1)
            for m2 in re.finditer(r'\)\s*(?:,|and)\s+((?:(?:early|mid|late)[\s-]+)?(?:' + MONTH_RX + r'\.?\s+)?20\d\d'
                                  r'(?:\s*[\u2013\u2014-]\s*(?:\d{4}|\d{2})\b)?)(?=\s*\()', text[m.end():m.end() + 60]):
                off = m.end()
                claims.append(Claim('updates_until', parse_until(m2.group(1)), off + m2.start(1), off + m2.end(1), m2.group(1)))
        for m in re.finditer(r'\bAndroid\s+(\d{2})\b', text):
            mk('android_until', int(m.group(1)), m, 1)
    if want('main_camera_mp'):
        for m in re.finditer(r'(?<![\d.])(\d{1,2})\s?MP\s+(?:(?:main|Main|Fusion)\b|Wide\b(?!\s*(?:and\s+)?Ultra)|camera\b)', text):
            mk('main_camera_mp', int(m.group(1)), m, 1)
    if want('ip_rating'):
        for m in re.finditer(r'\bIP\d{2}\b', text):
            mk('ip_rating', m.group(0), m, negated=bool(NEG_DIRECT.search(before(m, 40))))
    if want('apple_intelligence'):
        for m in re.finditer(r'\bApple Intelligence\b|\bApple[\u2019\']s AI features\b', text):
            mk('apple_intelligence', True, m, negated=negated_before(text, m.start()))
    if want('promotion'):
        for m in re.finditer(r'\bProMotion\b', text):
            mk('promotion', True, m, negated=negated_before(text, m.start()))
    if want('max_refresh_hz'):
        for m in re.finditer(r'(?<![\d.])(60|90|120|144)\s?Hz\b', text):
            mk('max_refresh_hz', int(m.group(1)), m, negated=bool(NEG_DIRECT.search(before(m, 40))))
    if want('telephoto_x'):
        # "3x telephoto", "3x optical zoom", "2x Telephoto" - but not the 2x crop "option" on standard iPhones,
        # an "optical-quality 2x zoom" or "digital zoom up to 30x"
        for m in re.finditer(r'(?<![\w.])(\d{1,2})x\s+(?:optical\s+)?(?:telephoto|Telephoto|tele|zoom)\b(?!\s+option)', text):
            if re.search(r'(?:optical-quality|digital|up to)\s*$', before(m, 20)):
                continue
            mk('telephoto_x', int(m.group(1)), m, 1)
        if re.search(r'\b(?:zoom|telephoto)\b', text, re.I):     # "2x on the iPhone 12 Pro, 3x on the 13 Pro..."
            for m in re.finditer(r'(?<![\w.])(\d{1,2})x(?=\s+on\s)', text):
                mk('telephoto_x', int(m.group(1)), m)
        for m in re.finditer(r'\b(?:no|without(?:\s+(?:a|the))?)\s+telephoto\b', text, re.I):
            claims.append(Claim('telephoto_x', 0, m.start(), m.end(), m.group(0)))
    return claims


# ------------------------------------------------------------------------------------------ comparing

def fact_ok(spec, claim_value, fact, derived85=False):
    """Is claim_value right for this phone's fact? None = the fact isn't recorded (can't say)."""
    if fact is None:
        return None
    if spec == 'battery_hours' and derived85:
        return int(fact * 0.85 + 0.5) == claim_value
    if spec == 'chip':
        return norm_chip(fact) == claim_value
    if spec == 'updates_until':
        f = parse_until(fact)
        c = claim_value
        if (f['y1'], f['y2']) != (c['y1'], c['y2']):
            return False
        if c['mon'] and f['mon'] and c['mon'] != f['mon']:
            return False
        if c['qual'] and f['qual'] and c['qual'] != f['qual']:
            return False
        if c['mon'] and not f['mon'] or c['qual'] and not f['qual']:
            return False
        return True
    if spec == 'launch_month':
        return month_name(fact) == claim_value
    return fact == claim_value


def show(spec, v, derived85=False):
    if spec == 'updates_until':
        return until_text(v) if isinstance(v, dict) else v
    if spec == 'weight_g':
        return f'{v}g'
    if spec == 'screen_in':
        return f'{v}-inch'
    if spec == 'battery_hours':
        return f'roughly {v} hours at 85% health' if derived85 else f'{v} hours'
    if spec in ('apple_intelligence', 'promotion'):
        return 'yes' if v else 'no'
    if spec == 'main_camera_mp':
        return f'{v}MP'
    if spec == 'max_refresh_hz':
        return f'{v}Hz'
    if spec == 'telephoto_x':
        return 'no telephoto' if v == 0 else f'{v}x telephoto'
    if spec == 'battery_mah':
        return f'{v:,}mAh'
    return str(v)


def show_fact(spec, fact, derived85=False):
    if spec == 'battery_hours' and derived85 and fact is not None:
        return f'{fact} hours, so roughly {int(fact * 0.85 + 0.5)} at 85%'
    return show(spec, fact)


class Checker:
    def __init__(self, facts, site):
        self.facts = facts
        self.models = facts['models']
        self.site = site
        self.lex = Lexicon(self.models)
        self.fails = []
        self.notes = []
        self.mentions = []       # (rel, line, location, handle, spec, said, ok)
        self.checked = 0

    # -- record
    def record(self, rel, line, where, handles, spec, said, ok, context, fact_shown):
        self.checked += 1
        for h in sorted(handles):
            self.mentions.append((rel, line, where, h, spec, said, ok))
        if not ok:
            names = ', '.join(self.models[h]['name'] for h in sorted(handles, key=self.lex.handles.index))
            self.fails.append(f'{rel}:{line} [{where}] {names}: {SPEC_LABEL.get(spec, spec)} says {said}, '
                              f'facts.json says {fact_shown}\n      "{context}"')

    def check_value(self, rel, line, where, claim, handles, context, mode='any'):
        """mode 'any': right for at least one phone; 'all': right for every phone; negated claims invert."""
        spec = claim.spec
        results = {}
        for h in handles:
            r = fact_ok(spec, claim.value, self.models[h].get(spec), claim.derived85)
            if r is not None and claim.negated:
                r = not r
            results[h] = r
        known = {h: r for h, r in results.items() if r is not None}
        if not known:
            return
        ok = all(known.values()) if mode == 'all' else any(known.values())
        said = ('not ' if claim.negated else '') + show(spec, claim.value, claim.derived85)
        if spec == 'telephoto_x' and claim.value == 0:
            said = 'a telephoto' if claim.negated else 'no telephoto'
        elif isinstance(claim.value, bool):
            said = show(spec, claim.value != claim.negated)
        if ok:
            shown_handles = [h for h, r in known.items() if r] if mode == 'any' else list(known)
            self.record(rel, line, where, shown_handles, spec, said, True, context, '')
        else:
            bad = [h for h, r in known.items() if not r]
            fact_shown = '; '.join(f"{self.models[h]['name']} {show_fact(spec, self.models[h].get(spec), claim.derived85)}"
                                   for h in bad) if len(bad) > 1 else show_fact(spec, self.models[bad[0]].get(spec), claim.derived85)
            self.record(rel, line, where, bad, spec, said, False, context, fact_shown)

    def check_diff(self, rel, line, where, claim, pair, context):
        spec = claim.spec
        a, b = (self.models[h].get(spec) for h in pair)
        if a is None or b is None:
            return
        ok = abs(a - b) == claim.value
        unit = 'g' if spec == 'weight_g' else ' hours'
        said = f'a difference of {claim.value}{unit}'
        names = [self.models[h]['name'] for h in pair]
        self.record(rel, line, where, set(pair), spec, said, ok, context,
                    f'{names[0]} {a}{unit} and {names[1]} {b}{unit}, a difference of {abs(a - b)}{unit}')

    # -- structured values: one phone, every claim must match
    def check_strict(self, rel, line, where, handle, text, only=None, claims=None):
        if handle not in self.models:
            return
        for c in (claims if claims is not None else extract_claims(text, only)):
            if c.kind == 'diff':
                continue
            self.check_value(rel, line, where, c, {handle}, text, mode='all')

    # -- prose: a sentence, with the phones it is about
    def check_sentence(self, rel, line, where, sent, implicit=(), carry=(), subject=False):
        """Check one sentence. Returns the phones it names (for the next sentence) if it names only phones."""
        if sent.rstrip().endswith('?'):
            return []
        mentions = self.lex.find(sent, context=set(implicit) | set(carry))
        explicit = set()
        for m in mentions:
            explicit |= m['handles']
        claims = extract_claims(sent)
        carry_out = sorted(explicit) if mentions and all(m['kind'] == 'model' for m in mentions) else []
        if not claims:
            return carry_out
        unknown = any(m['kind'] == 'unknown' for m in mentions)
        # a phone named only to compare with ("Over the iPhone 13, you get...", "...than the iPhone 12")
        swapped = re.search(r'\b(?:give up|lose|losing|miss out|trade off)\b', sent, re.I)
        for m in mentions:
            m['comparator'] = bool(not swapped and COMPARATOR_BEFORE.search(sent[max(0, m['start'] - 40):m['start']]))
        base = set(implicit) if implicit else set(carry)
        quant_all = bool(re.match(r"\s*(?:All\s+(?:four|three|two|of them)|Both|None of them|Every one)\b", sent))

        def scope_of(a, b):
            """Who a value between offsets a and b of the sentence is about."""
            ms = [m for m in mentions if a <= m['start'] < b]
            text = sent[a:b]
            allexp = set().union(*(m['handles'] for m in ms)) if ms else set()
            exp = set().union(*(m['handles'] for m in ms if not m['comparator'])) if ms else set()
            first = ms[0] if ms else None
            led = bool(first and first['handles'] and not first['comparator']
                       and re.fullmatch(r'[\s,]*(?:(?:and|but|while|whereas)\s+)?(?:the\s+)?', sent[a:first['start']], re.I))
            cands = set(exp)
            if subject and implicit:
                # product, trade-in or FAQ answer: about the page's phone unless it opens with another phone
                # ("The iPhone 15 Pro adds USB-C...") or recommends one ("If you want USB-C, look at...")
                led_other = (led and not (first['handles'] & set(implicit))) or \
                    bool(exp and re.match(r'\s*(?:If you want|For)\b', text))
                if not exp or not led_other:
                    cands |= base
                subj = set(implicit) | (first['handles'] if led else set())
            else:
                if not exp or PRONOUN.search(text):
                    cands |= base
                subj = first['handles'] if led else set()
            mode = 'any'
            if len(ms) == 1 and ms[0]['all'] and cands == exp:
                mode = 'all'            # "Every iPhone 15 has USB-C": true of each of them
            elif quant_all and not exp:
                mode = 'all'            # "All four use Lightning" on a collection page
            return ms, cands, allexp - subj, mode

        whole = scope_of(0, len(sent))
        cuts = [0] + [m.end() for m in CLAUSE_SPLIT.finditer(sent)] + [len(sent)]
        for c in claims:
            if c.kind == 'diff':
                pair = self.diff_pair(rel, explicit, implicit, unknown)
                if pair:
                    self.check_diff(rel, line, where, c, pair, sent)
                continue
            bound = self.binding(sent, c, mentions)
            if bound:
                self.check_value(rel, line, where, c, bound, sent, mode='all')
                continue
            if unknown:
                continue
            a = max(x for x in cuts if x <= c.start)
            b = min(x for x in cuts if x > c.start)
            scope = scope_of(a, b)
            ms, cands, others, mode = scope if scope[0] else whole   # a clause naming no phone: use the sentence
            prev = [m for m in mentions if m['end'] <= a and m['handles']]
            if not scope[0] and prev and re.match(r'which\s', sent[a:]):
                cands, mode = prev[-1]['handles'], 'any'            # "...the Pixel 8, which has no telephoto"
            if c.comparison:
                if others:
                    self.check_value(rel, line, where, c, others, sent)
                continue
            if cands:
                self.check_value(rel, line, where, c, cands, sent, mode=mode)
        return carry_out

    def diff_pair(self, rel, explicit, implicit, unknown):
        if unknown:
            return None
        implicit = list(implicit)
        if rel.startswith(('products/', 'sell/')) and len(implicit) == 1:
            others = explicit - set(implicit)
            if len(others) == 1:
                return (others.pop(), implicit[0])
            return None
        if len(explicit) == 2:
            return tuple(sorted(explicit))
        if len(explicit) == 1 and len(implicit) == 2 and explicit <= set(implicit):
            return tuple(sorted(implicit))
        return None

    @staticmethod
    def binding(sent, c, mentions):
        """Values tied to one phone by layout: "iPhone 14 Plus (203g)", "early 2028 (S23)", "164g for the iPhone 12"."""
        for m in mentions:
            if m['kind'] != 'model':
                continue
            if m['end'] <= c.start:
                gap = sent[m['end']:c.start]
                if re.fullmatch(r'\s*\(\s*', gap) and re.match(r'[^()]{0,12}\)', sent[c.end:]):
                    return m['handles']
            if m['start'] >= c.end:
                gap = sent[c.end:m['start']]
                if re.fullmatch(r'(?:\s+[\w-]+)?\s*\(\s*', gap) and re.match(r'(?:\s+onwards)?\s*\)', sent[m['end']:]):
                    return m['handles']
                if re.fullmatch(r'(?:\s*(?:hours?|hrs))?\s+(?:on|for)\s+(?:the\s+|an?\s+)?', gap):
                    return m['handles']
        return None

    # -- Q&A: "Does the iPhone 15 support Apple Intelligence?" "No."
    def check_qa(self, rel, line, where, q, a):
        q = q.strip()
        ans = re.match(r'\s*(Yes|No)\b', a)
        if not ans:
            return
        yes = ans.group(1) == 'Yes'
        m = re.match(r'(?:Does|Do|Has|Have|Can)\s+(?:the\s+)?(.+?)\s+(?:support|have|use|come with|get|run|charge with)\s+'
                     r'(?:a\s+|an\s+)?(.+?)\?$', q)
        if m:
            who = {h for mm in self.lex.find(m.group(1)) for h in mm['handles']}
            if len(who) != 1:
                return
            feat = m.group(2)
            claim = None
            if re.fullmatch(r'Apple Intelligence', feat):
                claim = Claim('apple_intelligence', True, 0, 0, feat)
            elif re.fullmatch(r'ProMotion(?: screen| display)?', feat):
                claim = Claim('promotion', True, 0, 0, feat)
            elif re.fullmatch(r'(USB-C|Lightning)(?: port)?', feat):
                claim = Claim('port', re.match(r'USB-C|Lightning', feat).group(0), 0, 0, feat)
            elif re.fullmatch(r'(\d+)\s?Hz(?: screen| display)?', feat):
                claim = Claim('max_refresh_hz', int(re.match(r'\d+', feat).group(0)), 0, 0, feat)
            elif re.fullmatch(r'telephoto(?: camera| lens)?|zoom lens', feat):
                claim = Claim('telephoto_x', 0, 0, 0, feat)
                yes = not yes                   # "has a telephoto" = "telephoto zoom is not 0"
            if claim:
                claim.negated = not yes
                self.check_value(rel, line, where + ' Q&A', claim, who, f'{q} {a[:60]}', mode='all')
            return
        m = re.match(r'Is\s+(?:the\s+)?(.+?)\s+(heavier|lighter)\s+than\s+(?:the\s+)?(.+?)\?$', q)
        if m:
            a1 = {h for mm in self.lex.find(m.group(1)) for h in mm['handles']}
            a2 = {h for mm in self.lex.find(m.group(3)) for h in mm['handles']}
            if len(a1) == 1 and len(a2) == 1:
                h1, h2 = a1.pop(), a2.pop()
                w1, w2 = self.models[h1]['weight_g'], self.models[h2]['weight_g']
                truth = (w1 > w2) if m.group(2) == 'heavier' else (w1 < w2)
                self.record(rel, line, where + ' Q&A', {h1, h2}, 'weight_g',
                            f"{'yes' if yes else 'no'} to '{m.group(2)}'", truth == yes, f'{q} {a[:60]}',
                            f'{self.models[h1]["name"]} {w1}g, {self.models[h2]["name"]} {w2}g')

    def check_prose_block(self, rel, line, where, text, implicit=(), q_context=()):
        imp = sorted(set(implicit) | set(q_context))
        subject = bool(q_context) or rel.startswith(('products/', 'sell/'))
        carry = []
        for sent in split_sentences(text):
            # "Best camera for the money: iPhone 15 Pro. 3x telephoto, ..." - the next sentence is about it too
            carry = self.check_sentence(rel, line, where, sent, implicit=imp, carry=carry, subject=subject)

    # ------------------------------------------------------------------------------ pages
    def page_models(self, rel, src):
        parts = rel.split('/')
        if parts[0] in ('products', 'sell') and len(parts) == 2 and parts[1][:-5] in self.models:
            return [parts[1][:-5]]
        if parts[0] == 'collections':
            main = src[src.find('<main'):]
            return [h for h in re.findall(r'<article class="card"[^>]*>\s*<a href="\.\./products/([a-z0-9-]+)\.html"', main)
                    if h in self.models]
        return []

    def run(self):
        files = []
        for root, dirs, fs in os.walk(self.site):
            dirs.sort()
            for f in sorted(fs):
                if f.endswith('.html'):
                    files.append(os.path.relpath(os.path.join(root, f), self.site).replace(os.sep, '/'))
        if not files:
            raise FactsError(f'no .html pages under {self.site}')
        self.pages = files
        for rel in files:
            with open(os.path.join(self.site, rel), encoding='utf-8') as f:
                src = f.read()
            self.check_page(rel, src)

    def check_page(self, rel, src):
        lineno = lambda off: src.count('\n', 0, off) + 1
        implicit = self.page_models(rel, src)
        page_h = implicit[0] if rel.startswith('products/') and implicit else None

        # head: title and meta descriptions
        seen = set()
        for label, rx in (('title', r'<title>(.*?)</title>'),
                          ('meta description', r'<meta name="description" content="([^"]*)"'),
                          ('og:title', r'<meta property="og:title" content="([^"]*)"'),
                          ('og:description', r'<meta property="og:description" content="([^"]*)"')):
            m = re.search(rx, src, re.S)
            if m:
                t = to_text(m.group(1))
                if t not in seen:
                    seen.add(t)
                    self.check_prose_block(rel, lineno(m.start()), label, t, implicit)

        # JSON-LD
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', src, re.S):
            try:
                j = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                self.notes.append(f'{rel}:{lineno(m.start())} JSON-LD block is not valid JSON ({e}); not checked')
                continue
            self.check_jsonld(rel, lineno(m.start()), j, implicit)

        mi, me = src.find('<main'), src.find('</main>')
        if mi < 0:
            return
        me = me if me > mi else len(src)
        main = src[:me]
        mask = list(main)

        def blank(a, b):
            mask[a:b] = ' ' * (b - a)

        for m in re.finditer(r'<(script|style|svg|noscript)\b.*?</\1>', main, re.S):
            blank(m.start(), m.end())
        for m in re.finditer(r'<form class="picker".*?</form>|<nav\b.*?</nav>|<ul class="chips[^"]*".*?</ul>', main, re.S):
            blank(m.start(), m.end())   # the picker, breadcrumbs and range links: names, not claims

        # product page: spec rows, the year under the name, the In-the-box cable
        if page_h:
            rows = []
            for m in re.finditer(r'<div><dt>(.*?)</dt><dd>(.*?)</dd></div>', main, re.S):
                rows.append(to_text(m.group(1)))
                self.check_spec_row(rel, lineno(m.start()), page_h, rows[-1], to_text(m.group(2)))
                blank(m.start(), m.end())
            for dt in self.SPEC_ROWS:
                if dt not in rows:
                    self.notes.append(f'{rel}: no "{dt}" spec row (renamed or removed?); its facts are not checked there')
            m = re.search(r'<div class="eyebrow">(.*?)</div>', main, re.S)
            if m:
                last = to_text(m.group(1)).split('\u00b7')[-1].strip()
                if re.fullmatch(r'20\d\d', last):
                    self.check_value(rel, lineno(m.start()), 'year under the product name',
                                     Claim('year', int(last), 0, 0, last), {page_h}, to_text(m.group(1)), 'all')
                blank(m.start(), m.end())
            for m in re.finditer(r'<li>[^<]*\b(USB-C|Lightning) to (USB-C|Lightning) (?:charging )?cable[^<]*</li>', main):
                self.check_value(rel, lineno(m.start()), 'In the box cable', Claim('port', m.group(2), 0, 0, m.group(0)),
                                 {page_h}, to_text(m.group(0)), 'all')

        # comparison tables
        for m in re.finditer(r'<table\b.*?</table>', main, re.S):
            self.check_table(rel, lineno(m.start()), m.group(0))
            blank(m.start(), m.end())

        # product cards
        for m in re.finditer(r'<article class="card"([^>]*)>(.*?)</article>', main, re.S):
            self.check_card(rel, lineno(m.start()), m.group(1), m.group(2))
            blank(m.start(), m.end())

        # FAQ details: question, answer
        for m in re.finditer(r'<details\b[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>', main, re.S):
            q, a = to_text(m.group(1)), to_text(m.group(2))
            qh = sorted({h for mm in self.lex.find(q) for h in mm['handles']})
            self.check_qa(rel, lineno(m.start()), 'FAQ', q, a)
            self.check_prose_block(rel, lineno(m.start()), 'FAQ answer', a, implicit, q_context=qh)
            blank(m.start(), m.end())

        # everything else in <main>: split into blocks at block-level tags
        masked = ''.join(mask)
        block_tag = re.compile(r'<(?:/?(?:p|li|h[1-6]|div|section|ul|ol|dl|dt|dd|summary|details|article|table|tr|td|th|'
                               r'nav|figure|figcaption|header|footer|aside|blockquote|form|fieldset|legend|label|main)'
                               r')\b[^>]*>')
        pos = mi
        for m in list(block_tag.finditer(masked, mi)) + [None]:
            end = m.start() if m else len(masked)
            chunk = masked[pos:end]
            t = to_text(chunk)
            if t:
                self.check_prose_block(rel, lineno(pos + len(chunk) - len(chunk.lstrip())), 'text', t, implicit)
            if m is None:
                break
            pos = m.end()

    def check_jsonld(self, rel, line, j, implicit):
        def walk(o, path):
            if isinstance(o, dict):
                if o.get('@type') == 'Question':
                    q = o.get('name', '')
                    ans = o.get('acceptedAnswer', {})
                    a = ans.get('text', '') if isinstance(ans, dict) else ''
                    qh = sorted({h for mm in self.lex.find(q) for h in mm['handles']})
                    self.check_qa(rel, line, f'JSON-LD {path}', q, to_text(a))
                    self.check_prose_block(rel, line, f'JSON-LD {path} answer', to_text(a), implicit, q_context=qh)
                    return
                for k, v in o.items():
                    if k in ('url', 'item', '@id', '@context', 'image', 'logo', 'sku', 'mainEntityOfPage',
                             'datePublished', 'dateModified', 'priceCurrency', 'email'):
                        continue
                    walk(v, f'{path}.{k}' if path else k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f'{path}[{i}]')
            elif isinstance(o, str):
                self.check_prose_block(rel, line, f'JSON-LD {j.get("@type", "")} {path}', to_text(o), implicit)
        walk(j, '')

    SPEC_ROWS = ('Display', 'Chip', 'Rear cameras', 'Connector', 'Battery when new', 'Water resistance',
                 'Released', 'Software updates', 'Highlights')

    def check_spec_row(self, rel, line, h, dt, dd):
        where = f'spec row "{dt}"'
        if dt == 'Display':
            self.check_strict(rel, line, where, h, dd, only=('screen_in',))
            pro = bool(re.search(r'\bProMotion\b', dd))
            hz = re.search(r'(\d+)\s?Hz', dd)
            hz = int(hz.group(1)) if hz else (120 if pro else 60)
            self.check_value(rel, line, where, Claim('promotion', pro, 0, 0, dd), {h}, dd, 'all')
            self.check_value(rel, line, where, Claim('max_refresh_hz', hz, 0, 0, dd), {h}, dd, 'all')
        elif dt == 'Chip':
            self.check_value(rel, line, where, Claim('chip', norm_chip(dd), 0, 0, dd), {h}, dd, 'all')
        elif dt == 'Rear cameras':
            mp = re.search(r'(\d+)\s?MP', dd)
            if mp:
                self.check_value(rel, line, where, Claim('main_camera_mp', int(mp.group(1)), 0, 0, dd), {h}, dd, 'all')
            tele = re.search(r'(\d+)x\s+(?:optical\s+)?[Tt]elephoto\b(?!\s+option)', dd)
            self.check_value(rel, line, where, Claim('telephoto_x', int(tele.group(1)) if tele else 0, 0, 0, dd), {h}, dd, 'all')
        elif dt == 'Connector':
            p = re.match(r'(USB-C|Lightning)', dd)
            if p:
                self.check_value(rel, line, where, Claim('port', p.group(1), 0, 0, dd), {h}, dd, 'all')
        elif dt == 'Battery when new':
            hrs = re.search(r'(\d{1,2})\s+hours', dd)
            if hrs:
                self.check_value(rel, line, where, Claim('battery_hours', int(hrs.group(1)), 0, 0, dd), {h}, dd, 'all')
            self.check_strict(rel, line, where, h, dd, only=('battery_mah',))
        elif dt == 'Water resistance':
            self.check_strict(rel, line, where, h, dd, only=('ip_rating',))
        elif dt == 'Released':
            if re.fullmatch(r'20\d\d', dd):
                self.check_value(rel, line, where, Claim('year', int(dd), 0, 0, dd), {h}, dd, 'all')
        elif dt == 'Software updates':
            self.check_strict(rel, line, where, h, dd, only=('updates_until', 'android_until'))
        elif dt == 'Highlights':
            ai = bool(re.search(r'Apple Intelligence', dd))
            self.check_value(rel, line, where, Claim('apple_intelligence', ai, 0, 0, dd), {h}, dd, 'all')
            self.check_strict(rel, line, where, h, dd, only=('ip_rating', 'max_refresh_hz', 'promotion', 'port', 'telephoto_x'))

    HEADER_SPECS = [
        (r'weight', ('weight_g',)), (r'screen|display', ('screen_in', 'max_refresh_hz')), (r'chip|processor', ('chip',)),
        (r'port|connector|charging', ('port',)), (r'main camera|camera', ('main_camera_mp', 'telephoto_x')),
        (r'battery', ('battery_hours', 'battery_mah')), (r'software|updates|support', ('updates_until', 'android_until')),
        (r'released|launch|year', ('year',)), (r'water|\bip\b', ('ip_rating',)), (r'apple intelligence', ('apple_intelligence',)),
        (r'promotion|refresh', ('promotion', 'max_refresh_hz')),
    ]

    def check_table(self, rel, line, t):
        head = re.search(r'<thead>(.*?)</thead>', t, re.S)
        rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', t, re.S)
        if head:
            headers = [to_text(c) for c in re.findall(r'<th\b[^>]*>(.*?)</th>', head.group(1), re.S)]
            body = re.findall(r'<tr\b[^>]*>(.*?)</tr>', t[head.end():], re.S)
        elif rows and '<th' in rows[0]:
            headers = [to_text(c) for c in re.findall(r'<t[hd]\b[^>]*>(.*?)</t[hd]>', rows[0], re.S)]
            body = rows[1:]
        else:
            return
        if not headers or not re.match(r'(?i)model|phone', headers[0]):
            return
        specs = []
        for hd in headers:
            low = hd.lower()
            specs.append(next((s for rx, s in self.HEADER_SPECS if re.search(rx, low)), None))
        # a Screen column where some rows say "120Hz": a row without a rate is a 60Hz screen
        cells_by_row = [re.findall(r'<t[hd]\b[^>]*>(.*?)</t[hd]>', r, re.S) for r in body]
        hz_cols = {i for i, s in enumerate(specs) if s and 'screen_in' in s and
                   any(len(c) > i and re.search(r'\d\s?Hz', to_text(c[i])) for c in cells_by_row)}
        # likewise a camera column where some rows say "+ 3x tele": a row without one has no telephoto
        tele_cols = {i for i, s in enumerate(specs) if s and 'telephoto_x' in s and
                     any(len(c) > i and re.search(r'\dx\s+tele', to_text(c[i])) for c in cells_by_row)}
        for cells in cells_by_row:
            if not cells:
                continue
            link = set(re.findall(r'href="(?:\.\./)?products/([a-z0-9-]+)\.html"', cells[0]))
            who = link if len(link) == 1 else {h for mm in self.lex.find(to_text(cells[0])) for h in mm['handles']}
            if len(who) != 1 or not who <= set(self.models):
                self.notes.append(f'{rel}:{line} table row "{to_text(cells[0])[:40]}": no single phone we sell; not checked')
                continue
            h = who.pop()
            for i, cell in enumerate(cells[1:], 1):
                if i >= len(specs) or not specs[i]:
                    continue
                txt = to_text(cell)
                where = f'table "{headers[i]}" column, {self.models[h]["name"]} row'
                spec = specs[i]
                if spec == ('main_camera_mp', 'telephoto_x'):
                    mp = re.search(r'(\d+)\s?MP', txt)
                    claims = [Claim('main_camera_mp', int(mp.group(1)), 0, 0, txt)] if mp else []
                    tele = extract_claims(txt, only=('telephoto_x',))
                    claims += tele or ([Claim('telephoto_x', 0, 0, 0, txt)] if i in tele_cols else [])
                elif spec == ('battery_hours', 'battery_mah'):
                    hrs = re.search(r'(\d{1,2})\s?(?:hours?|hrs)', txt)
                    claims = [Claim('battery_hours', int(hrs.group(1)), 0, 0, txt)] if hrs else []
                    claims += extract_claims(txt, only=('battery_mah',))
                elif spec == ('updates_until', 'android_until'):
                    claims = extract_claims('updates ' + txt, only=spec)
                elif spec == ('apple_intelligence',) or spec == ('promotion', 'max_refresh_hz'):
                    yn = re.match(r'(?i)(yes|no|\u2713|\u2717|\u2014|-)', txt)
                    claims = extract_claims(txt, only=('max_refresh_hz',)) if 'max_refresh_hz' in spec else []
                    if yn:
                        claims.append(Claim(spec[0], yn.group(1).lower() in ('yes', '\u2713'), 0, 0, txt))
                elif spec == ('weight_g',):
                    w = re.search(r'(\d{2,3})\s?g\b', txt)
                    claims = [Claim('weight_g', int(w.group(1)), 0, 0, txt)] if w else []
                elif spec == ('year',):
                    y = re.search(r'\b(20[12]\d)\b', txt)
                    claims = [Claim('year', int(y.group(1)), 0, 0, txt)] if y else []
                else:
                    claims = extract_claims(txt, only=spec)
                    if i in hz_cols and not any(c.spec == 'max_refresh_hz' for c in claims):
                        claims.append(Claim('max_refresh_hz', 60, 0, 0, txt))
                if not claims and txt not in ('', '\u2014', '-'):
                    self.notes.append(f'{rel}:{line} {where}: couldn\'t read "{txt}"; not checked')
                self.check_strict(rel, line, where, h, txt, claims=claims)

    def check_card(self, rel, line, tag, body):
        hs = set(re.findall(r'href="(?:\.\./)?products/([a-z0-9-]+)\.html"', body))
        if len(hs) != 1 or not hs <= set(self.models):
            return
        h = hs.pop()
        name = self.models[h]['name']
        usbc = attr(tag, 'data-usbc')
        if usbc in ('0', '1'):
            self.check_value(rel, line, f'card data-usbc for {name}', Claim('port', 'USB-C' if usbc == '1' else 'Lightning',
                             0, 0, usbc), {h}, f'data-usbc="{usbc}"', 'all')
        for meta in re.findall(r'<div class="card-meta">(.*?)</div>', body, re.S):
            t = to_text(meta)
            self.check_strict(rel, line, f'card for {name}', h, t, only=('screen_in', 'chip', 'port'))
        for badge in re.findall(r'<span class="card-badge">(.*?)</span>', body, re.S):
            t = to_text(badge)
            if re.search(r'(?i)update|support', t):
                self.check_strict(rel, line, f'card badge for {name}', h, t, only=('updates_until',))


def split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9\u201c"\u2018(]|iP)', text)
    return [p.strip() for p in parts if p.strip()]


# ------------------------------------------------------------------------------------------ main

def norm_name(s):
    return re.sub(r'[\s_-]+', ' ', s.strip().lower())


def find_model(models, wanted):
    """The handle for --where MODEL, matched as set_prices.py matches it: case, spaces and hyphens don't matter,
    and the page name ("iphone-13-pro"), the name ("iPhone 13 Pro") or any alias in facts.json will do."""
    w = norm_name(wanted)
    for cand in (w, re.sub(r'^(?:apple|samsung|google) ', '', w)):
        for h, m in models.items():
            if cand in {norm_name(h), norm_name(m['name']), *(norm_name(x) for x in m.get('aliases', []))}:
                return h
    return None



def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', help='site folder to check (default: sites/full-bars in this repo)')
    ap.add_argument('--facts', default=DEFAULT_FACTS, help='facts file (default: facts.json next to this script)')
    ap.add_argument('--where', nargs='+', metavar=('MODEL', 'SPEC'),
                    help='list every place a phone (and optionally one spec) is stated, e.g. --where "iPhone 12 Pro" weight_g '
                         '(the page name iphone-12-pro works too)')
    ap.add_argument('--stats', action='store_true', help='count the mentions found for each spec')
    ap.add_argument('--quiet', action='store_true', help='print only FAIL lines and the summary')
    a = ap.parse_args(argv)
    site = a.site or find_site()
    if not site or not os.path.isfile(os.path.join(site, 'shop.html')):
        print(f'ERROR: no Full Bars site at {site or "sites/full-bars"}; pass --site', file=sys.stderr)
        return 2
    try:
        facts = load_facts(a.facts)
        ck = Checker(facts, site)
        missing = [f for f in os.listdir(os.path.join(site, 'products')) if f.endswith('.html') and f[:-5] not in ck.models]
        extra = [h for h in ck.models if not os.path.isfile(os.path.join(site, 'products', h + '.html'))]
        if missing or extra:
            raise FactsError(f'facts.json and the product pages disagree: pages with no facts {missing}, '
                             f'facts with no page {extra}')
        for h, m in ck.models.items():
            src = open(os.path.join(site, 'products', h + '.html'), encoding='utf-8').read()
            dm = re.search(r'<form class="picker" id="picker"[^>]*\bdata-model="([^"]*)"', src)
            if dm and html.unescape(dm.group(1)) != m['name']:
                raise FactsError(f'{h}: facts.json name "{m["name"]}" but the page sells "{html.unescape(dm.group(1))}"')
        ck.run()
    except (FactsError, OSError, UnicodeDecodeError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2

    if a.where:
        if len(a.where) > 2:
            print('ERROR: --where takes a model and at most one spec', file=sys.stderr)
            return 2
        h = find_model(ck.models, a.where[0])
        spec = a.where[1] if len(a.where) > 1 else None
        if h is None:
            print(f'ERROR: unknown model {a.where[0]!r}; use a name such as "iPhone 13 Pro" or a page name such as '
                  f'iphone-13-pro. One of: {", ".join(m["name"] for m in ck.models.values())}', file=sys.stderr)
            return 2
        if spec and spec not in SPEC_LABEL:
            print(f'ERROR: unknown spec {spec!r}; one of: {", ".join(SPEC_LABEL)}', file=sys.stderr)
            return 2
        rows = [x for x in ck.mentions if x[3] == h and (spec is None or x[4] == spec)]
        print(f'{ck.models[h]["name"]}{" " + SPEC_LABEL[spec] if spec else ""}: {len(rows)} mentions'
              + (f' (facts.json: {show(spec, ck.models[h].get(spec))})' if spec else ''))
        for rel, line, where, _, sp, said, ok in sorted(set(rows)):
            print(f'  {"ok  " if ok else "FAIL"} {rel}:{line} [{where}] {SPEC_LABEL[sp]}: {said}')

    if a.stats:
        from collections import Counter
        c = Counter(x[4] for x in ck.mentions)
        pages = Counter(sp for _, sp in set((x[0], x[4]) for x in ck.mentions))
        print('mentions per spec (pages):')
        for s in SPEC_LABEL:
            print(f'  {s:20} {c.get(s, 0):5}  ({pages.get(s, 0)} pages)')

    for f in ck.fails:
        print('FAIL', f)
    if not a.quiet:
        for n in ck.notes:
            print('NOTE', n)
    print(f'pages: {len(ck.pages)}  models: {len(ck.models)}  checks: {ck.checked}  conflicts: {len(ck.fails)}')
    return 1 if ck.fails else 0


if __name__ == '__main__':
    sys.exit(main())
