"""Fetch Bremen law from the Transparenzportal (www.transparenz.bremen.de) into .cache/.

    python -X utf8 fetch.py act <gsid>     # an act's Fassungen list, then the full text of every version
Private (never published). One process, one request at a time, at least 3 s apart (robots.txt is empty), curl with
a browser User-Agent, cached by the sha256 of the URL; stops on 403/429 or a challenge page, on a 404 for an act page,
and on an implausibly large version list (the portal-wide list served for an unknown gsid).

2026-10-30 fix: an act's gsid is read from its own page (the index's "Vorschrift direkt aufrufen" link), never built
from the index id: `bremen203.c.<index id>.de` is not a gsid (act page 404, Fassungen = all 8,933 portal versions).
"""
import hashlib, html, json, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
BASE = 'https://www.transparenz.bremen.de'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
_last = [0.0]


def cpath(url: str) -> Path:
    return CACHE / 'url' / (hashlib.sha256(url.encode()).hexdigest()[:32] + '.html')


def get(url: str) -> Path | None:
    out = cpath(url)
    if out.exists() and out.stat().st_size:
        return out
    wait = 3.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.part')
    p = subprocess.run(['curl', '-s', '-L', '--compressed', '--max-time', '90', '-A', UA, '-o', str(tmp),
                        '-w', '%{http_code}', url], capture_output=True, text=True)
    _last[0] = time.time()
    code = int(p.stdout.strip() or 0)
    body = tmp.read_bytes() if tmp.exists() else b''
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'code': code,
                            'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
    if code in (403, 429) or b'Just a moment' in body[:5000] or b'captcha' in body[:5000].lower():
        tmp.unlink(missing_ok=True)
        raise SystemExit(f'stop: {code} on {url}')
    if code == 404 and 'template=20_gp_ifg_meta_detail_d' in url and '&ts=' not in url:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f'stop: act page 404 on {url}')
    if code == 200 and body:
        tmp.replace(out)
        return out
    tmp.unlink(missing_ok=True)
    return None


def fassungen_url(gsid: str) -> str:
    return f'{BASE}/sixcms/detail.php?gsid={gsid}&asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_fassungen_d'


def current_url(gsid: str) -> str:
    return f'{BASE}/sixcms/detail.php?gsid={gsid}&asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_detail_d'


def versions(gsid: str) -> list[tuple[str, str, str | None]]:
    """(url, valid from, valid to) for every earlier version listed, oldest first."""
    f = cpath(fassungen_url(gsid))
    if not f.exists():
        return []
    s = f.read_text(encoding='utf-8', errors='replace')
    out = []
    for href, body in re.findall(r'<a[^>]*href="([^"]*template=20_gp_ifg_meta_detail_d[^"]*)"[^>]*>(.*?)</a>', s, re.S):
        t = html.unescape(re.sub(r'<[^>]+>', ' ', body))
        m = re.search(r'gültig von:\s*(\d\d\.\d\d\.\d{4})(?:\s*gültig bis:\s*(\d\d\.\d\d\.\d{4}))?', t)
        if m:
            u = html.unescape(href)
            out.append((u if u.startswith('http') else BASE + u, m.group(1), m.group(2)))
    return list(reversed(out))


MAX_VERSIONS = 200
MAX_SERIES = 30


def guard(gsid: str):
    """Stop before downloading a version list that cannot be one act's (the portal-wide list)."""
    f = cpath(fassungen_url(gsid))
    n, k = len(versions(gsid)), len(series_heads(gsid))
    if n > MAX_VERSIONS or k > MAX_SERIES or f.stat().st_size > 1_000_000:
        f.rename(f.with_suffix('.toolarge'))
        raise SystemExit(f'stop: {gsid} lists {n} versions in {k} series ({f.stat().st_size if f.exists() else 0} '
                         f'bytes): not one act')


def act(gsid: str):
    if not get(current_url(gsid)):
        raise SystemExit(f'stop: no act page for {gsid}')
    has_f, _ = links(gsid)
    if has_f:  # an act with no earlier versions has no Fassungen link; never ask for one (portal-wide list)
        if not get(fassungen_url(gsid)):
            raise SystemExit(f'stop: no Fassungen page for {gsid}')
        guard(gsid)
        for u, _, _ in versions(gsid):
            get(u)


def historie_url(gsid: str) -> str:
    return f'{BASE}/sixcms/detail.php?gsid={gsid}&asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_historie_d'


def series_heads(gsid: str) -> list[str]:
    """The gsid of the newest version of each 'Gesamtausgabe' on the Fassungen page (the current one first)."""
    f = cpath(fassungen_url(gsid))
    if not f.exists():
        return [gsid]
    s = f.read_text(encoding='utf-8', errors='replace')
    out = [gsid]
    for sec in re.split(r'Frühere Fassungen der Gesamtausgabe', s)[2:]:
        m = re.search(r'gsid=([^&"]+)&[^"]*template=20_gp_ifg_meta_detail_d', sec)
        if m:
            out.append(m.group(1))
    return out


def histories(gsid: str):
    if not any(links(gsid)):
        return
    for g in series_heads(gsid):
        get(historie_url(g))


INDEX = (BASE + '/vorschriften-72741?id=72743&gsid=kogis_tp_berlin01.c.60176.de&_article_id=72741&fulltext=Gesetz'
         '&vorschriften%5B0%5D=Gesetze+und+Rechtsverordnungen&skip={skip}&max=50')


GSID_LINK = re.compile(r'gsid=([A-Za-z0-9_.]+)&(?:amp;)?asl=bremen203_tpgesetz\.c\.55340\.de&(?:amp;)?template='
                       r'20_gp_ifg_meta_(?:fassungen|historie)_d')


PDF_LINK = re.compile(r'gsid=([A-Za-z0-9_.]+)&(?:amp;)?template=00_html_to_pdf_d')


def gsid_of(meta_url: str) -> str | None:
    """The act's real gsid, read from its own page (cached): the gsid of its Fassungen/Historie links, or for an act
    with neither (no earlier versions) the gsid of its PDF link."""
    f = cpath(meta_url)
    if not f.exists():
        return None
    s = f.read_text(encoding='utf-8', errors='replace')
    ids = set(GSID_LINK.findall(s)) or set(PDF_LINK.findall(s))
    if len(ids) != 1:
        raise SystemExit(f'stop: {meta_url} names {len(ids)} gsids {sorted(ids)[:5]}')
    return ids.pop()


def links(gsid: str) -> tuple[bool, bool]:
    """(has a Fassungen link, has a Historie link) on the act's cached current page."""
    s = cpath(current_url(gsid)).read_text(encoding='utf-8', errors='replace')
    return (f'gsid={gsid}&asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_fassungen_d' in s.replace('&amp;', '&'),
            f'gsid={gsid}&asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_historie_d' in s.replace('&amp;', '&'))


def index_entries() -> list[tuple[str | None, str, str, str]]:
    """(gsid or None if its page is not cached yet, title, index id, "Vorschrift direkt aufrufen" url) of every
    Stammgesetz on the cached index pages (amending acts and Verordnungen left out), in index order."""
    out, seen = [], set()
    skip = 0
    while True:
        f = cpath(INDEX.format(skip=skip))
        if not f.exists():
            break
        s = f.read_text(encoding='utf-8', errors='replace')
        items = re.findall(r'(?s)<li class="search-result-item" data-id="(\d+)">\s*<h2>(.*?)</h2>(.*?)</li>', s)
        for iid, h2, rest in items:
            title = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', h2))).strip()
            if iid in seen:
                continue
            seen.add(iid)
            if re.search(r'(?i)gesetz', title) and not re.match(r'(?i)^(w+ )?Ortsgesetz|^Ortsgesetz', title) and not re.match(r'(?i)^(\w+ )?(Gesetz|Verordnung) (zur|über die) (Änderung|Aufhebung)|^(Erste|Zweite|Dritte|Vierte|Fünfte)s? Gesetz zur Änderung|Verordnung', title)                     and re.search(r'\([^()]*[A-Z][A-Za-zÄÖÜäöüß]*G[\w ]*\)', title):
                m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>\s*<b>Vorschrift direkt aufrufen</b>', rest)
                if not m:
                    raise SystemExit(f'stop: index entry {iid} has no "Vorschrift direkt aufrufen" link')
                meta = html.unescape(m.group(1))
                out.append((gsid_of(meta), title, iid, meta))
        if not items:
            break
        skip += 50
    return out


def entry(meta_url: str) -> str:
    """Fetch an act's own page from the index link; return its gsid."""
    if not get(meta_url):
        raise SystemExit(f'stop: no page for {meta_url}')
    return gsid_of(meta_url)


def index():
    skip = 0
    while True:
        f = get(INDEX.format(skip=skip))
        if not f or 'Vorschrift direkt aufrufen' not in f.read_text(encoding='utf-8', errors='replace'):
            break
        skip += 50
        print('index', skip, flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'index':
        index()
    elif sys.argv[1] == 'gesetze':
        for n, (g, t, iid, meta) in enumerate(index_entries()[:int(sys.argv[2]) if sys.argv[2:] else None]):
            g = g or entry(meta)
            act(g)
            histories(g)
            print(n, iid, g, len(versions(g)) if cpath(fassungen_url(g)).exists() else 0, t[:70], flush=True)
    elif sys.argv[1] == 'act':
        for g in sys.argv[2:]:
            act(g)
            histories(g)
            print(g, flush=True)


