# Bremen (germany-bremen-law) - private

State 2026-10-30 12:35 UTC (gitlaw-scraper-dell, Länder agent): FIXED. 49788 stopped by the coordinator; its 899 pages
quarantined in .cache/quarantine-2026-10-30-bad-gsid/. fetch.py now reads each act's gsid from its own page (index
"Vorschrift direkt aufrufen" link: Fassungen/Historie links, else the PDF link bremen2014_tp.c.<id>.de), asks for
Fassungen only when linked, stops on an act-page 404 or a list > 200 versions / 30 series / 1 MB; 3 s pace.
parse.py: index_entries() gives (gsid|None, title, index id, url); slug fallback is the index id; complete() follows
the page's own links; "Gültig ab" matched across the NBSP. Fetch PID 19704 `fetch.py gesetze` (161 acts) from 12:35.
Parts: `python -X utf8 parse.py`, check_letters.py, local build + check.py, audit_push, then <part>.PUBLISH.

Earlier state (superseded):

State 2026-10-30 12:00 UTC (gitlaw-scraper-dell):
- Published: 10-verfassung (BremLV, 37 versions), main fc58060.
- Fetch PID 49788 (`python -X utf8 fetch.py gesetze 100`, started 10:45 UTC, cache .cache/url) is running but
  BLOCKED by a bug: `fetch.index_entries()` builds each act's gsid as `bremen203.c.<id>.de` from the numeric id at the
  end of the index's /metainformationen/ link (e.g. 166782 for ZensAG 2022). That is not a sixcms gsid:
  - the detail page for it is HTTP 404 (requests.jsonl 10:45:02), so `parse.complete()` is False for every act;
  - the Fassungen page for an unknown gsid is the portal-wide list (2.7 MB, 2,995 "Frühere Fassungen der
    Gesamtausgabe" groups, 8,933 earlier versions of every Gesetz, Verordnung and Allgemeinverfügung), so the fetcher
    is downloading all 8,933 versions (626 by 11:45), then 2,995 Historie pages: about 20 h at 2.5 s+.
  No Gesetze part can be built from this run. Not stopped (not mine to stop).
- Fix before restarting: resolve each act's real gsid from the index's "Vorschrift direkt aufrufen" link
  (/metainformationen/<slug>-<id>?asl=bremen203_tpgesetz.c.55340.de&template=20_gp_ifg_meta_detail_d, which is the
  detail page itself; read the gsid from its Fassungen/Historie links), or match index titles to the portal-wide
  Fassungen groups already cached. Then fetch per act, as `act()` intends. Index: 161 Stammgesetze (fetch was capped
  at the first 100).
- Restart (after the fix, once 49788 has been stopped by its owner): `python -X utf8 fetch.py gesetze` in this folder,
  same cache, BelowNormal, output to fetch-gesetze.log.
- Parts: `python -X utf8 parse.py` writes 20-gesetze-NN of 50 acts once every act in the chunk is complete.
