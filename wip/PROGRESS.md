# Bremen (germany-bremen-law) - private

State 2026-10-31 07:20 UTC (gitlaw-scraper-dell, CLAIMED): Verordnungen fetching; parts published by the driver.
- Fetch: `fetch.py verordnungen` (PID 34308, BelowNormal, from 05:47 UTC): the portal's list searched for "Verordnung"
  (index pages cached, 28 pages), 644 Verordnungen by title (VO_TITLE, amending ones left out by VO_AMEND; "...ordnung"
  titles such as Prüfungs-/Gebührenordnungen, Ortsgesetze and Gesetze not taken), each act in full; 3 s pace, same
  guards as the Gesetze. About 40 s an act (~7 h). Log fetch-verordnungen.log. Restart with the same command (cached
  pages are skipped; the index is re-read from the cache only if all pages are cached - index() asks again otherwise).
- parse.py: `PARSE_OUT=<stage>/corpus.d python -X utf8 parse.py 30-verordnungen-NN` writes only the named parts (no
  argument = all, as before). Verordnungen slugs: abbrev_vo() (abbreviation with 2+ capitals, else the one-word name in
  the bracket, else "vo-<index id>"), taken after every Gesetz slug; amending acts labelled by kind ("Verordnung vom");
  a law key another part holds keeps that part's entry (Verordnungen parts only). letters-differ.json (private, written
  by the driver) leaves out versions whose parsed text differs from the page.
  Regression: all five published parts re-parse byte-identical. 30-verordnungen-01 staged: 50 acts, 201 versions,
  letters 0, local build check.py 0/0/0 (209 acts, 1,614 versions), audit [].
- Driver: scripts/world-law/laender_vo_driver.py (PID 45548, both Länder, a pass every 10 min, BelowNormal, CPU gate):
  parses the next unpublished parts into .tmp/vo-stage, publishes 5-10 at a time (fewer only at the end), letters check
  (mismatches -> letters-differ.json, reparse), verify_parts_local, published parts byte-identical, then corpus.d +
  .PUBLISH. Status VO-DRIVER.json, log vo-driver.log. On any failure it stops this Land and records why. When all 13
  parts are published and the fetch has finished it deletes this Land's claim.
- README: Verordnungen row + rule paragraph (counts come from REPRODUCE.md as parts land).

Earlier state (superseded):

State 2026-10-31 05:05 UTC (gitlaw-scraper-dell): Gesetze PUBLISHED, claim deleted. Fetch 19704 finished all 161
index Stammgesetze. Parts 20-gesetze-01..04 (50/50/48/10 acts; 1,376 versions) verified (check_letters 0; local build
159 acts / 1,413 versions, check.py 0/0/0; audit_push []) and published: main 2aff67d (verified rebuild, 1,853 tags).
Left out (in decisions): GrEStVG, BremBrexitÜG, BremFidatasG (no "Gültig ab" day on the page, never guessed); one BrBerG
version (1964-06-30, not after 1987-10-15); RBG history entry "Gesetz vom 27.20.1998" (impossible date) not used for
credits (parse.py now skips such entries). README updated (158 Gesetze; Verordnungen not yet).
Next (not claimed): Verordnungen.

State 2026-10-30 12:21 UTC (gitlaw-scraper-dell, Länder agent): FIXED. 49788 stopped by the coordinator; its 899 pages
quarantined in .cache/quarantine-2026-10-30-bad-gsid/. fetch.py now reads each act's gsid from its own page (index
"Vorschrift direkt aufrufen" link: Fassungen/Historie links, else the PDF link bremen2014_tp.c.<id>.de), asks for
Fassungen only when linked, stops on an act-page 404 or a list > 200 versions / 30 series / 1 MB; 3 s pace.
parse.py: index_entries() gives (gsid|None, title, index id, url); slug fallback is the index id; complete() follows
the page's own links; "Gültig ab" matched across the NBSP. Fetch PID 19704 `fetch.py gesetze` (161 acts) from 12:21.
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
