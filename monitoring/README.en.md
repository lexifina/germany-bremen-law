<!-- lawwatch: written from data/checks by the check trail; edit the records, not this page -->

# Monitoring: what is read and what came of it

[Deutsch](README.md)

How global-law monitors every country: [global-law monitoring/](https://github.com/lexifina/global-law/tree/main/monitoring). This page is the same for Bremen only: every time an official source is read, when, and what came of it (acts added, changed and removed). The machine-readable form is [data/checks/](../data/checks/) (JSON Lines, schema `lexifina-check/1`), in `git log` as `Kind: check` commits, and month by month in [checks/](checks/).

**Last check:** 2026-11-25 07:45 UTC, Transparenzportal Bremen (Free Hanseatic City of Bremen): 143 addresses read; 24 added, 0 changed, 0 removed; changes found; 239 not published, 0 of them with no reason.

## Sources

| Source | Folders | How often | Last successful check | Last result | State |
| --- | --- | --- | --- | --- | --- |
| [Transparenzportal Bremen (Free Hanseatic City of Bremen)](https://www.transparenz.bremen.de) | `<act>/` | daily | 2026-11-25 07:45 UTC | changes found | watched |

## The last 30 days

| Started (UTC) | Source | Read | Added | Changed | Removed | Not published (no reason) | Result | Commits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| [2026-11-25 07:38](checks/2026-11.md#de-transparenz-bremen-20261125t073802z) | transparenz-bremen | 143 | 24 | 0 | 0 | 239 (0) | changes found | — |
| [2026-11-24 00:12](checks/2026-11.md#de-transparenz-bremen-20261124t001201z) | transparenz-bremen | 159 | 23 | 0 | 0 | 408 (0) | changes found | — |
| [2026-11-23 21:00](checks/2026-11.md#de-transparenz-bremen-20261123t210057z) | transparenz-bremen | 154 | 0 | 0 | 0 | 353 (0) | no change | — |

## Check it yourself

```
python tools/checktrail.py                      # the latest check of every source
python tools/checktrail.py --day 2026-11-23     # every check of a day
python tools/checktrail.py --act <id>           # when an act was seen and published
git log --grep='^Kind: check' --format='%ci %s'  # the checks in the history
```

Only the official publication has legal force; the texts here are copies for reading and searching.
