"""Fetch Bremen law from the Transparenzportal (www.transparenz.bremen.de) into .cache/.

    python -X utf8 fetch.py act <gsid>     # an act's Fassungen list, then the full text of every version
Private (never published). One process, one request at a time, at least 2.5 s apart (robots.txt is empty), curl with
a browser User-Agent, cached by the sha256 of the URL; stops on 403/429 or a challenge page.
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
    wait = 2.5 - (time.time() - _last[0])
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
    s = f.read_text(encoding='utf-8', errors='replace')
    out = []
    for href, body in re.findall(r'<a[^>]*href="([^"]*template=20_gp_ifg_meta_detail_d[^"]*)"[^>]*>(.*?)</a>', s, re.S):
        t = html.unescape(re.sub(r'<[^>]+>', ' ', body))
        m = re.search(r'gültig von:\s*(\d\d\.\d\d\.\d{4})(?:\s*gültig bis:\s*(\d\d\.\d\d\.\d{4}))?', t)
        if m:
            u = html.unescape(href)
            out.append((u if u.startswith('http') else BASE + u, m.group(1), m.group(2)))
    return list(reversed(out))


def act(gsid: str):
    get(current_url(gsid))
    if get(fassungen_url(gsid)):
        for u, _, _ in versions(gsid):
            get(u)


def historie_url(gsid: str) -> str:
    return f'{BASE}/sixcms/detail.php?gsid={gsid}&asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_historie_d'


def series_heads(gsid: str) -> list[str]:
    """The gsid of the newest version of each 'Gesamtausgabe' on the Fassungen page (the current one first)."""
    s = cpath(fassungen_url(gsid)).read_text(encoding='utf-8', errors='replace')
    out = [gsid]
    for sec in re.split(r'Frühere Fassungen der Gesamtausgabe', s)[2:]:
        m = re.search(r'gsid=([^&"]+)&[^"]*template=20_gp_ifg_meta_detail_d', sec)
        if m:
            out.append(m.group(1))
    return out


def histories(gsid: str):
    for g in series_heads(gsid):
        get(historie_url(g))


INDEX = (BASE + '/vorschriften-72741?id=72743&gsid=kogis_tp_berlin01.c.60176.de&_article_id=72741&fulltext=Gesetz'
         '&vorschriften%5B0%5D=Gesetze+und+Rechtsverordnungen&skip={skip}&max=50')


def index_entries() -> list[tuple[str, str]]:
    """(gsid, title) of every Stammgesetz on the cached index pages (amending acts and Verordnungen left out), in
    index order."""
    out, seen = [], set()
    skip = 0
    while True:
        f = cpath(INDEX.format(skip=skip))
        if not f.exists():
            break
        s = f.read_text(encoding='utf-8', errors='replace')
        found = 0
        for m in re.finditer(r'<a[^>]*href="https://www\.transparenz\.bremen\.de/metainformationen/[^"]*?-(\d+)\?[^"]*"[^>]*>\s*Mehr', s):
            pass
        for h3 in re.findall(r'(?s)<h3[^>]*>(.*?)</h3>.*?href="https://www\.transparenz\.bremen\.de/metainformationen/[^"]*?-(\d+)(?:\?|")', s):
            title = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', h3[0]))).strip()
            found += 1
            gid = f'bremen203.c.{h3[1]}.de'
            if gid in seen:
                continue
            seen.add(gid)
            if re.search(r'(?i)gesetz', title) and not re.match(r'(?i)^(\w+ )?(Gesetz|Verordnung) (zur|über die) (Änderung|Aufhebung)|^(Erste|Zweite|Dritte|Vierte|Fünfte)s? Gesetz zur Änderung|Verordnung', title) \
                    and re.search(r'\([^()]*[A-Z][A-Za-zÄÖÜäöüß]*G[\w ]*\)', title):
                out.append((gid, title))
        if not found:
            break
        skip += 50
    return out


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
        for n, (g, t) in enumerate(index_entries()[:int(sys.argv[2]) if sys.argv[2:] else None]):
            act(g)
            histories(g)
            print(n, g, flush=True)
    elif sys.argv[1] == 'act':
        for g in sys.argv[2:]:
            act(g)
            histories(g)
            print(g, flush=True)


