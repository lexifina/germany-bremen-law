# How this repository was made (Bremen)

This file is written by the build on 2026-10-30, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| Transparenzportal Bremen (Freie Hansestadt Bremen), Vorschriften: current and earlier versions of each act ("Frühere Fassungen") | <https://www.transparenz.bremen.de/vorschriften-72741> | 2026-10-30 | § 5 Abs. 1 UrhG: Gesetze, Verordnungen and amtliche Erlasse enjoy no copyright protection; the portal lists "Amtliches Werk, lizenzfrei nach §5 Abs. 1 UrhG" among its licences. Its pages carry a general CC BY-NC-ND notice "sofern nicht anders angegeben", which cannot extend to texts § 5 UrhG exempts. |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `verfassung` | Landesverfassung der Freien Hansestadt Bremen in der Fassung der Bekanntmachung vom 12. August 2019 | 37 | 1947-10-22 to 2024-06-25 |

The build made 40 commits:

| Commits | Kind |
| ---: | --- |
| 1 | first version of an act |
| 38 | one law on its in-force day |
| 1 | changes no amendment note explains, credited to the publisher |

Other counts:
- 0 commits on the branch `zukunft`: laws not yet in force on 2026-10-30.
- 4 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 37 laws in the record.
- 74 tags.

## Dates

Each commit is dated at noon (Europe/Berlin) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: Landesverfassung der Freien Hansestadt Bremen Art. 123 Abs. 3: "Jedes Gesetz soll den Tag des Inkrafttretens bestimmen. Fehlt eine solche Bestimmung, so tritt es mit dem vierzehnten Tage nach Ablauf des Tages in Kraft, an dem das Gesetzblatt ausgegeben worden ist." Each version here is dated by the first day of validity the Transparenzportal gives it ("gültig von"). https://www.transparenz.bremen.de/vorschriften-72741

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `b9b715cca5821f01b2560f0bbf5b8507854e429c53e1b76ad30e4fd544cb40d1` (3355440 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `a97ff7ea62c3c7595c5668a297d533da0b74373c`, `check.py` `3e59cb6f05eccb94a9ec14431a7f6781221e83ef`, `on.py` `644a6c0857fbcc72562032b58d57aa113fee0641`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

Not yet run for this build.

No second build of this corpus has been compared yet.

## Decisions made by hand

- Every version the portal lists under "Frühere Fassungen", plus the current one, is one version here, dated by its "gültig von" day; the current version is dated the day after the newest earlier version ends. The oldest is credited to the publisher as the oldest version available.
- Each provision that differs from the version before is credited to the latest amendment in the portal's "Änderungshistorie" that names that provision (or says "mehrfach geändert"), is dated on or before the version's first day and has not been credited to an earlier version; if there is none, the change is labelled unexplained.
- One file per Artikel or Paragraph; headings of Hauptteile and Abschnitte stand above the first provision under them. Numbered entries are one line each; tables are one line per row, cells separated by " | ".

## What AI did and did not do

The scripts that read the sources and build this repository were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is used as legal text, dates or credits: every word, date and credit comes from the Transparenzportal Bremen pages.
