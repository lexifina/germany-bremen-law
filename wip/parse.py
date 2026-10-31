"""Bremen law from Transparenzportal Bremen pages (.cache/url) into corpus.d/ parts.

    python -X utf8 parse.py

Reads only the cache; the same cache gives the same bytes. For each act the "Frühere Fassungen" list gives every
earlier version with its validity dates; each version's page gives its full text and the last amendment it takes
into account ("letzte berücksichtigte Änderung"). Parts:
  10-verfassung.json   the Landesverfassung der Freien Hansestadt Bremen
  20-gesetze-NN.json   other Gesetze, about 50 acts a part
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402  (cache paths and URLs only; no network here)

RETRIEVED = '2026-10-30'
# Where parts are written (a staging copy of corpus.d while parts are verified).
PARTS = Path(os.environ.get('PARSE_OUT') or HERE / 'corpus.d')
BASE = 'https://www.transparenz.bremen.de'

COUNTRY = {
    'code': 'DE-HB', 'name': 'Bremen', 'slug': 'germany-bremen', 'lang': 'de', 'tz': 'Europe/Berlin',
    'future_branch': 'zukunft',
    'publisher': {'name': 'Freie Hansestadt Bremen (Transparenzportal Bremen)',
                  'email': 'vorschriften@transparenz.bremen.de.invalid'},
    'default_in_force_rule': {
        'text': 'Landesverfassung der Freien Hansestadt Bremen Art. 123 Abs. 3: "Jedes Gesetz soll den Tag des '
                'Inkrafttretens bestimmen. Fehlt eine solche Bestimmung, so tritt es mit dem vierzehnten Tage nach '
                'Ablauf des Tages in Kraft, an dem das Gesetzblatt ausgegeben worden ist." Each version here is dated '
                'by the first day of validity the Transparenzportal gives it ("gültig von").',
        'source': 'https://www.transparenz.bremen.de/vorschriften-72741'},
    'licence_note': 'Texts: Transparenzportal Bremen, Freie Hansestadt Bremen, www.transparenz.bremen.de. Gesetze '
                    'and Verordnungen are not protected by copyright (§ 5 Abs. 1 UrhG); the portal lists "Amtliches '
                    'Werk, lizenzfrei nach §5 Abs. 1 UrhG" among its licences. Non-official text: only the Bremisches '
                    'Gesetzblatt is authoritative.',
}

VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'col', 'wbr'}


class Node:
    __slots__ = ('tag', 'attrs', 'kids', 'parent')

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, dict(attrs), [], parent


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root', {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        x = self.cur
        while x is not self.root and x.tag != tag:
            x = x.parent
        if x is not self.root:
            self.cur = x.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def norm(s: str) -> str:
    s = s.replace(' ', ' ').replace('­', '').replace(' ', ' ').replace(' ', ' ')
    s = s.replace(',,', '„').replace('”', '“')
    s = re.sub(r'([(\[„]) +', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def flat(n) -> str:
    if isinstance(n, str):
        return n
    if n.tag == 'br':
        return ' '
    if n.tag in ('script', 'style'):
        return ''
    return ''.join(flat(k) for k in n.kids)


HAS_BLOCK = ('p', 'div', 'table', 'ol', 'ul', 'dl', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6')


def lines(n: Node) -> list[str]:
    """One line per paragraph, heading, list entry or table row. A numbered entry (<dt>1.</dt><dd>...) is one line."""
    out: list[str] = []
    buf: list[str] = []

    def flush():
        s = norm(''.join(buf))
        if s:
            out.append(s)
        buf.clear()
    dt_mark = ''
    for k in n.kids:
        if isinstance(k, str):
            buf.append(k)
            continue
        if k.tag == 'tr':
            flush()
            cells = [norm(' '.join(lines(c)) if any(isinstance(x, Node) and x.tag in HAS_BLOCK for x in c.kids) else flat(c))
                     for c in k.kids if isinstance(c, Node) and c.tag in ('td', 'th')]
            if any(cells):
                out.append(' | '.join(c for c in cells))
        elif k.tag == 'dt':
            flush()
            if dt_mark:
                out.append(dt_mark)
            dt_mark = norm(flat(k))
        elif k.tag == 'dd':
            flush()
            ls = lines(k) if any(isinstance(x, Node) and x.tag in HAS_BLOCK for x in k.kids) else [norm(flat(k))]
            ls = [x for x in ls if x]
            if dt_mark:
                ls = [f'{dt_mark} {ls[0]}' if ls else dt_mark] + ls[1:]
                dt_mark = ''
            out += ls
        elif k.tag in ('p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'table', 'tbody', 'thead', 'ol', 'ul',
                       'dl', 'blockquote', 'center'):
            flush()
            if any(isinstance(x, Node) and x.tag in HAS_BLOCK + ('tr', 'dt', 'dd', 'li', 'tbody') for x in k.kids):
                out += lines(k)
            else:
                s = norm(flat(k))
                if s:
                    out.append(s)
        elif k.tag in ('script', 'style'):
            continue
        else:
            buf.append(flat(k))
    flush()
    if dt_mark:
        out.append(dt_mark)
    return out


UNIT_HEAD = re.compile(r'^(Artikel|Art\.|§§?)\s*\d|^(Präambel|Eingangsformel|Schlussformel|Anlage|Anhang)', re.I)


def unit_key(label: str, seen: set) -> tuple[str, str]:
    m = re.match(r'^(Artikel|Art\.|§§?)\s*(\d+)\s*([a-z]?)\b', label)
    if m:
        pre = 'art' if m.group(1).startswith('Art') else 'par'
        k, kind = f'{pre}-{int(m.group(2)):03d}{m.group(3)}', pre
    elif label == 'Titel':
        k, kind = '000-titel', 'title'
    elif re.match(r'(?i)eingangsformel|pr(ä|ae)ambel', label):
        k, kind = '001-' + ('praeambel' if 'mbel' in label.lower() else 'eingangsformel'), 'preamble'
    elif re.match(r'^(Anlage|Anhang)', label):
        mm = re.match(r'^(\w+)\s*(\d*)', label)
        k, kind = 'z-' + mm.group(1).lower() + (f'-{int(mm.group(2)):02d}' if mm.group(2) else ''), 'annex'
    else:
        k = 'y-' + (re.sub(r'[^a-z0-9]+', '-', label.lower().translate(str.maketrans('äöüß', 'aous'))).strip('-')[:40] or 'teil')
        kind = 'other'
    base, n = k, 2
    while k in seen:
        k = f'{base}-{n}'
        n += 1
    seen.add(k)
    return k, kind


def doc_region(raw: str) -> str:
    i = raw.index('<div class="jgwsAiZDoc"')
    j = raw.index('<a name="DocInhaltEnde"', i)
    return raw[i:j]


def parse_version(raw: str, title: str = '') -> tuple[dict, str | None]:
    """Units of one version, and its 'letzte berücksichtigte Änderung' line."""
    toc = dict(re.findall(r'<a class="Overl" href="#(jlr-[^"]+)"><span[^>]*>(.*?)</span></a>', raw))
    toc = {k: norm(html.unescape(re.sub(r'<[^>]+>', '', v))) for k, v in toc.items()}
    stand = re.search(r'letzte berücksichtigte Änderung:\s*(.*?)</td>', raw, re.S)
    stand = norm(html.unescape(re.sub(r'<[^>]+>', '', stand.group(1)))) if stand else None
    region = doc_region(raw)
    parts = re.split(r'(?=<div class="jgwsAiZDoc" id="jgwsAiZDoc-jlr-)', region)
    units: dict[str, dict] = {}
    seen: set = set()
    pending: list[str] = []
    last = None
    for part in parts:
        m = re.match(r'<div class="jgwsAiZDoc" id="jgwsAiZDoc-(jlr-[^"]+)"', part)
        if not m:
            continue
        t = Tree()
        t.feed(part)
        ls = lines(t.root)
        label = toc.get(m.group(1), '')
        if not ls:
            continue
        has_text = bool(re.search(r'<p\b|<dl\b|<table\b|<ol\b|<ul\b', part))
        if 'class="standangaben"' in part:
            continue
        if label == 'Titel':
            key, kind = unit_key('Titel', seen)
            units[key] = {'label': 'Titel', 'kind': kind, 'text': '\n'.join(['# ' + ls[0]] + ls[1:]) + '\n'}
            last = key
            continue
        if not has_text and not UNIT_HEAD.match(label):
            pending.append('## ' + ' '.join(ls))
            continue
        key, kind = unit_key(label or ls[0], seen)
        head = ls[0] if re.match(r'^(Artikel|Art\.|§)', ls[0]) else None
        body = ls[1:] if head else ls
        heading = '# ' + (head if head else (label or 'Text'))
        units[key] = {'label': label or (head or 'Text'), 'kind': kind, 'text': '\n'.join(pending + [heading] + body) + '\n'}
        pending = []
        last = key
    if pending and last:
        units[last]['text'] += '\n'.join(pending) + '\n'
    if '000-titel' not in units and title:
        units = {'000-titel': {'label': 'Titel', 'kind': 'title', 'text': f'# {title}\n'}, **units}
    return units, stand


def de(d: str) -> str:
    dd, mm, yy = d.split('.')
    return f'{yy}-{mm}-{dd}'


def law_of(stand: str | None) -> tuple[str, dict] | None:
    if not stand:
        return None
    m = re.search(r'(Gesetz(?:es)?|Verordnung|Bekanntmachung|Beschluss(?:es)?)\s+vom\s+(\d\d)\.(\d\d)\.(\d{4})\s*\(Brem\.GBl\.\s*(?:(\d{4})\s*)?S\.\s*(\d+)', stand)
    if not m:
        return None
    kind, d, mo, y, gy, page = m.groups()
    day = f'{y}-{mo}-{d}'
    key = f'hb-gbl-{gy or y}-{int(page):04d}-{day.replace("-", "")}'
    return key, {'label': f'Änderung vom {int(d)}.{int(mo)}.{y} (Brem.GBl. {gy or y} S. {int(page)})', 'title': stand,
                 'kind': 'law', 'enacted': day, 'published': None, 'url': None, 'temporary_until': None,
                 'restores': None, 'note': None}


# Versions whose parsed text differs from the page (the letters check of a new part; written by the part driver,
# private): source url -> reason. Left out rather than published with a difference.
_LD = HERE / 'letters-differ.json'
LETTERS_DIFFER = json.loads(_LD.read_text(encoding='utf-8')) if _LD.exists() else {}
BAD_ENTRIES: list[str] = []
# Label each amending instrument by its kind ("Verordnung vom ..."); the published Gesetze parts say "Gesetz vom"
# for every one and stay as published, so this is set only for the Verordnungen parts.
LABEL_KIND = False


def history_entries(gsid: str) -> list[dict]:
    """Every entry of the Änderungshistorie of each Gesamtausgabe: the provisions it names, its date and GBl page."""
    out = []
    for g in fetch.series_heads(gsid):
        f = fetch.cpath(fetch.historie_url(g))
        if not f.exists():
            continue
        s = f.read_text(encoding='utf-8', errors='replace')
        i = s.find('Änderungshistorie')
        j = s.find('Fehler melden', i)
        if i < 0:
            continue
        for li in re.findall(r'(?s)<dd[^>]*>(.*?)</dd>', s[i:j]):
            t = norm(html.unescape(re.sub(r'<[^>]+>', ' ', li)))
            m = re.search(r'(Gesetz(?:es)?|Verordnung|Bekanntmachung|Beschluss(?:es)?)\s+vom\s+(\d\d)\.(\d\d)\.(\d{4})\s*\(Brem\.?\s*GBl\.\s*(?:(\d{4})\s*)?S\.\s*(\d+)', t)
            if not m or ' durch ' not in t:
                continue
            word, d, mo, y, gy, page = m.groups()
            word = re.sub(r'(es)$', '', word) if word != 'Verordnung' else word
            try:
                dt.date(int(y), int(mo), int(d))
            except ValueError:  # the portal's own typo (e.g. "27.20.1998"): never guessed, never credited
                BAD_ENTRIES.append(f'{gsid}: Änderungshistorie entry with an impossible date not used for credits: "{t}"')
                continue
            what = t.split(' durch ', 1)[0]
            nums = set(re.findall(r'\b(\d+[a-z]?)\b', re.sub(r'Artikel \d+ des Gesetzes', '', what)))
            key = f'hb-gbl-{gy or y}-{int(page):04d}-{y}{mo}{d}'
            same = [e for e in out if e['key'] == key]
            if same:  # one act listed twice (two of its articles): its provisions together
                same[0]['nums'] |= nums
                same[0]['all'] |= 'mehrfach' in what
                continue
            out.append({'key': key, 'day': f'{y}-{mo}-{d}', 'nums': nums, 'all': 'mehrfach' in what,
                        'pre': bool(re.search(r'Präambel|Eingangsformel', what)), 'text': t,
                        'law': {'label': f'{word if LABEL_KIND else "Gesetz"} vom {int(d)}.{int(mo)}.{y} (Brem.GBl. {gy or y} S. {int(page)})',
                                'title': t, 'kind': 'law', 'enacted': f'{y}-{mo}-{d}', 'published': None, 'url': None,
                                'temporary_until': None, 'restores': None, 'note': None}})
    return sorted(out, key=lambda e: e['day'])


def names_unit(e: dict, key: str) -> bool:
    if e['all']:
        return True
    m = re.match(r'^(?:art|par)-0*(\d+[a-z]?)$', key)
    if m:
        return m.group(1) in e['nums']
    return e['pre'] and key.startswith('001-')


def act_of(gsid: str, slug: str, short: str) -> tuple[dict | None, dict, list[str]]:
    cur = fetch.cpath(fetch.current_url(gsid))
    vs = fetch.versions(gsid)
    raw_cur = cur.read_text(encoding='utf-8', errors='replace')
    title = norm(html.unescape(re.sub(r'<[^>]+>', '', re.search(r'<title>(.*?)</title>', raw_cur, re.S).group(1)))).split(' - Transparenzportal')[0]
    seq = []
    for u, frm, to in vs:
        seq.append((u, de(frm), de(to) if to else None))
    last_to = seq[-1][2] if seq else None
    cur_from = (dt.date.fromisoformat(last_to) + dt.timedelta(days=1)).isoformat() if last_to else None
    if cur_from is None:
        g = re.search(r'Gültig(?:\s|&nbsp;)ab:(?:\s|<[^>]+>)*(\d\d\.\d\d\.\d{4})', raw_cur)  # \s takes the NBSP
        cur_from = de(g.group(1)) if g else None
    seq.append((fetch.current_url(gsid), cur_from, None))
    laws, problems, versions = {}, [], []
    prev_units = None
    BAD_ENTRIES.clear()
    entries = history_entries(gsid)
    problems += [b.replace(gsid + ':', title + ':', 1) for b in BAD_ENTRIES]
    used: set = set()
    prev_title = None
    heads = {}
    for g in fetch.series_heads(gsid):
        f = fetch.cpath(fetch.historie_url(g))
        if f.exists():
            hr = f.read_text(encoding='utf-8', errors='replace')
            ht = norm(html.unescape(re.sub(r'<[^>]+>', '', re.search(r'<title>(.*?)</title>', hr, re.S).group(1)))).split(' - Transparenzportal')[0]
            heads[ht] = hr
    for u, frm, to in seq:
        p = fetch.cpath(u)
        if not p.exists():
            problems.append(f'{title}: version from {frm} not retrieved')
            continue
        if re.sub(r'&ts=[^&]*', '', u) in LETTERS_DIFFER:
            problems.append(f'{title}: version from {frm} left out: {LETTERS_DIFFER[re.sub(r"&ts=[^&]*", "", u)]}')
            continue
        raw = p.read_text(encoding='utf-8', errors='replace')
        own = re.search(r'<title>(.*?)</title>', raw, re.S)
        own = norm(html.unescape(re.sub(r'<[^>]+>', '', own.group(1)))).split(' - Transparenzportal')[0] if own else title
        units, stand = parse_version(raw, own or title)
        if not frm:
            problems.append(f'{title}: a version has no date; left out')
            continue
        if versions and frm <= versions[-1]['from']:
            if frm == versions[-1]['from']:
                problems.append(f'{title}: two versions valid from {frm}; the later one is kept')
                versions.pop()
                prev_units = versions[-1]['units'] if versions else None
            else:
                problems.append(f'{title}: version from {frm} not after {versions[-1]["from"]}; left out')
                continue
        v = {'from': frm, 'source_url': re.sub(r'&ts=[^&]*', '', u),
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'units': units, 'credits': {}}
        vtitle = norm(html.unescape(re.sub(r'<[^>]+>', '', re.search(r'<title>(.*?)</title>', raw, re.S).group(1)))).split(' - Transparenzportal')[0]
        neu_key, neu_law = None, None
        hraw = heads.get(vtitle, '')
        neu = re.search(r'Neugefasst:(?:\s|<[^>]+>)*(\d\d)\.(\d\d)\.(\d{4})', hraw)
        fund = re.search(r'Fundstelle:(?:\s|<[^>]+>)*Brem\.GBl\.\s*(\d{4}),\s*(\d+)', hraw)
        if neu and fund:
            d, mo, y = neu.groups()
            neu_key = f'hb-gbl-{fund.group(1)}-{int(fund.group(2)):04d}-{y}{mo}{d}'
            neu_law = {'label': f'Bekanntmachung der Neufassung vom {int(d)}.{int(mo)}.{y} (Brem.GBl. {fund.group(1)} '
                                f'S. {int(fund.group(2))})', 'title': None, 'kind': 'law', 'enacted': f'{y}-{mo}-{d}',
                       'published': None, 'url': None, 'temporary_until': None, 'restores': None,
                       'note': 'The text published anew in one piece (Neubekanntmachung); the changes it shows are '
                               'the editorial ones of the new publication.'}
        if prev_units is not None:
            changed = [k for k in sorted(set(prev_units) | set(units))
                       if prev_units.get(k, {}).get('text') != units.get(k, {}).get('text')]
            nums = {re.sub(r'^(?:art|par)-0*', '', k) for k in changed}
            # "mehrfach geändert" names no provision: it counts only for a version that starts within 60 days of it.
            near = (dt.date.fromisoformat(versions[-1]['from']) - dt.timedelta(days=60)).isoformat()
            cands = [e for e in entries if e['day'] <= frm and (e['all'] or e['key'] not in used)
                     and (not e['all'] or e['day'] >= near)]

            def rank(e):
                return (not e['all'], len(e['nums'] & nums), e['day'])
            for k in changed:
                c = [e for e in cands if names_unit(e, k)]
                if c:
                    best = max(c, key=rank)
                    v['credits'][k] = [best['key']]
                    laws[best['key']] = best['law']
            if neu_key and vtitle != prev_title:
                for k in changed:
                    if k not in v['credits']:
                        v['credits'][k] = [neu_key]
                        laws[neu_key] = neu_law
            used.update(x for ks in v['credits'].values() for x in ks)
        prev_title = vtitle
        versions.append(v)
        prev_units = units
    if not versions:
        return None, laws, problems
    act = {'slug': slug, 'short': short, 'title': title, 'url': fetch.current_url(gsid), 'first_law': None,
           'earlier_laws': [], 'versions': versions}
    return act, laws, problems


def write_part(name: str, acts_in: list[tuple[str, str, str]], country: bool, label_kind: bool = False) -> None:
    global LABEL_KIND
    LABEL_KIND = label_kind
    acts, laws, problems = [], {}, []
    for gsid, slug, short in acts_in:
        a, lw, pr = act_of(gsid, slug, short)
        problems += pr
        if a:
            acts.append(a)
            laws.update(lw)
    nv = sum(len(a['versions']) for a in acts)
    # One law, one entry: in a Verordnungen part, a key another part already holds keeps that part's entry word for
    # word (the published Gesetze parts are left exactly as they were written).
    for other in sorted(PARTS.glob('*.json')) if label_kind else []:
        if other.stem != name:
            for k, lw in json.loads(other.read_text(encoding='utf-8'))['laws'].items():
                if k in laws:
                    laws[k] = lw
    out = {'acts': acts, 'laws': dict(sorted(laws.items())), 'applies': [],
           'sources': [{'name': 'Transparenzportal Bremen (Freie Hansestadt Bremen), Vorschriften: current and earlier '
                                'versions of each act ("Frühere Fassungen")',
                        'url': BASE + '/vorschriften-72741', 'retrieved': RETRIEVED,
                        'licence': '§ 5 Abs. 1 UrhG: Gesetze, Verordnungen and amtliche Erlasse enjoy no copyright '
                                   'protection; the portal lists "Amtliches Werk, lizenzfrei nach §5 Abs. 1 UrhG" among '
                                   'its licences. Its pages carry a general CC BY-NC-ND notice "sofern nicht anders '
                                   'angegeben", which cannot extend to texts § 5 UrhG exempts.',
                        'notes': f'{len(acts)} acts, {nv} versions in this part.'}],
           'decisions': [
               'Every version the portal lists under "Frühere Fassungen", plus the current one, is one version here, '
               'dated by its "gültig von" day; the current version is dated the day after the newest earlier version '
               'ends. The oldest is credited to the publisher as the oldest version available.',
               'Each provision that differs from the version before is credited to the latest amendment in the '
               'portal\'s "Änderungshistorie" that names that provision (or says "mehrfach geändert"), is dated on or '
               'before the version\'s first day and has not been credited to an earlier version; if there is none, '
               'the change is labelled unexplained.',
               'One file per Artikel or Paragraph; headings of Hauptteile and Abschnitte stand above the first provision '
               'under them. Numbered entries are one line each; tables are one line per row, cells separated by " | ".']
               + (['The Verordnungen are the entries of the portal's list of Gesetze und Rechtsverordnungen (searched '
                   'for "Verordnung") whose title names a Verordnung, amending Verordnungen left out, in list order, 50 '
                   'a part. Rechtsverordnungen titled otherwise ("...ordnung", Satzungen) are not included. Each '
                   'amending act is labelled by its kind as the Änderungshistorie names it ("Verordnung vom ...").']
                  if label_kind else [])
               + [f'Left out: {p}' for p in problems],
           'ai_use': ['Claude Code (claude-opus-5-5) wrote Lexifina\'s code and chose the sources. No model output is '
                      'used as legal text, dates or credits: every word, date and credit comes from the Transparenzportal '
                      'Bremen pages.']}
    if country:
        out['country'] = COUNTRY
    d = PARTS
    tmp = d / (name + '.json.tmp')
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(d / (name + '.json'))
    print(name, len(acts), 'acts', nv, 'versions', len(problems), 'problems')
    for p in problems:
        print('  ', p)


PART_SIZE = 50


def complete(gsid: str | None) -> bool:
    if not gsid or not fetch.cpath(fetch.current_url(gsid)).exists():
        return False
    has_f, has_h = fetch.links(gsid)
    if has_f and not fetch.cpath(fetch.fassungen_url(gsid)).exists():
        return False
    if not (has_f or has_h):
        return True  # no earlier versions and no history: current text only
    return all(fetch.cpath(u).exists() for u, _, _ in fetch.versions(gsid)) and         all(fetch.cpath(fetch.historie_url(g)).exists() for g in fetch.series_heads(gsid))


def abbrev(title: str) -> str | None:
    m = re.search(r'\((?:[^()]*?[-–]\s*)?([A-ZÄÖÜ][\wÄÖÜäöüß./-]*)\)', title)
    return m.group(1) if m and len(m.group(1)) < 30 else None


def abbrev_vo(title: str) -> str | None:
    """A Verordnung's short name from the last bracket of its title: the abbreviation after " - " when it is one
    (two or more capitals: "Schiedsstellenverordnung - SchStV"), else the bracket's own one-word name
    ("Infektionshygiene-Verordnung"); never a reference such as "(EU)"."""
    head = re.split(r'\s+(?:vom|in der Fassung)\s', title)[0]
    for g in reversed(re.findall(r'\(([^()]*)\)', head)):
        g = g.strip().rstrip(',')
        if re.fullmatch(r'[A-Z]{1,7}', g) or re.match(r'\d', g):
            continue
        parts = re.split(r'\s+[-–,]\s+|\s*,\s+', g)
        if len(parts) > 1 and sum(ch.isupper() for ch in parts[-1]) >= 2 and len(parts[-1]) < 30:
            return parts[-1]
        if ' ' not in g and len(g) < 60:
            return g
        if len(parts) > 1 and ' ' not in parts[-1] and sum(ch.isupper() for ch in parts[-1]) >= 2:
            return parts[-1]
        if len(g) < 50 and g.count(' ') <= 3:  # a short name of a few words ("Emissionserklärungsverordnung - Abwasser")
            return g
        return None
    return None


def slugs_for(entries, taken: set, prefix: str = '') -> list[tuple[str | None, str, str]]:
    out = []
    for g, t, iid, _ in entries:  # g None until the act's own page is cached (complete() is then False)
        a = abbrev_vo(t) if prefix else abbrev(t)
        slug = re.sub(r'[^a-z0-9]+', '-', (a or prefix + iid).lower().translate(str.maketrans('äöüß', 'aous'))).strip('-')
        if slug in taken:
            slug = f'{slug}-{iid}'
        taken.add(slug)
        out.append((g, slug, a or t[:60]))
    return out


if __name__ == '__main__':
    # python -X utf8 parse.py [<part> ...]: write only the named parts (all of them when none is named). A part is
    # written only when every act in it is completely retrieved.
    only = set(sys.argv[1:])
    if not only or '10-verfassung' in only:
        write_part('10-verfassung', [('bremen203.c.232507.de', 'verfassung', 'BremLV')], country=True)
    taken = {'verfassung'}
    acts = slugs_for(fetch.index_entries(), taken)
    for n in range(0, len(acts), PART_SIZE):
        chunk = acts[n:n + PART_SIZE]
        name = f'20-gesetze-{n // PART_SIZE + 1:02d}'
        if not all(complete(g) for g, _, _ in chunk):
            break
        if not only or name in only:
            write_part(name, chunk, country=False)
    # Verordnungen: slugs after every Gesetz's, so no Gesetz's slug ever changes; one without an abbreviation is
    # "vo-<index id>".
    vos = slugs_for(fetch.verordnung_entries(), taken, prefix='vo-')
    for n in range(0, len(vos), PART_SIZE):
        chunk = vos[n:n + PART_SIZE]
        name = f'30-verordnungen-{n // PART_SIZE + 1:02d}'
        if not all(complete(g) for g, _, _ in chunk):
            break
        if not only or name in only:
            write_part(name, chunk, country=False, label_kind=True)
