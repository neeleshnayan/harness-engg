# CPI / Employment Situation (NFP) release-date dataset — sourcing notes
Built 2026-08-23 by the analyst seat. Companion file: `macro_release_dates_cpi_nfp.csv` (788 rows).

## What the file is
One row per (series, reference_period) for the two 8:30 ET US macro releases the
announcement-premium family needs: CPI and the Employment Situation ("NFP").
Coverage: reference periods **1994-01 → 2026-11**, 394 rows each series.
390 rows per series are PAST-DATED; 8 rows total are future-scheduled and carry
`flag=future_scheduled`.

## Columns
- `series` — CPI | EMPSIT
- `reference_period` — YYYY-MM, the DATA month, not the release month
- `release_date` — the date the release was published (see date_basis)
- `dow` — day of week of release_date
- `release_time_et` — embargo time, Eastern
- `date_basis` — how that date is known (see below)
- `scheduled_date` — the date BLS published in advance, where a schedule page exists
- `flag` — future_scheduled where release_date is after 2026-08-23
- `source_url` — the BLS document the date was taken from
- `schedule_source` — the BLS schedule page
- `in_bls_archive_index` — whether the date appears in BLS's own archived-release index

## date_basis values and counts
| basis | n | meaning |
|---|---|---|
| slug+schedule_agree | 664 | BLS archived-release index and BLS advance schedule give the same date |
| document_verified_embargo | 68 | 1994–1996: date and time read from the release's own EMBARGO line |
| schedule+archive_agree | 46 | schedule date corroborated by presence in the archive index |
| document_verified | 4 | index/schedule disagreed; resolved by the release document's own date line |
| slug_only | 2 | archive index only (EMPSIT 1995-01, 1995-05); no time captured |
| schedule_only | 4 | the four future-scheduled CPI rows |

**Every past-dated row is corroborated by two independent BLS surfaces or by the
release document itself. No row is filled from memory or from a secondary host.**

## Per-year sourcing
- **1994–1996** — bls.gov has NO schedule archive for these years (`/schedule/1996/home.htm`
  and earlier return HTTP 404; the earliest is `/schedule/1997/home.htm`). Dates come
  from BLS's own archived-release indexes
  (https://www.bls.gov/bls/news-release/cpi.htm and .../empsit.htm), and **all 68
  releases were opened and their embargo lines read**: 68/68 filename date == the
  date stated inside the release, and 68/68 state 8:30 A.M. (EST/EDT as applicable).
- **1997–2026** — dates from the same archived-release indexes AND from BLS's own
  advance schedule pages `https://www.bls.gov/schedule/YYYY/home.htm` (all 30 years
  fetched, zero failures). 1997–2007 pages are preformatted text; 2008–2026 are HTML
  tables with `date-cell`/`time-cell`/`desc-cell`.

## Caveats — read before using
1. **The earliest reference period is 1994-01, not 1993-12.** BLS's archive begins with
   the CPI released 1994-02-17 and the Employment Situation released 1994-02-04. The
   January-1994 releases (December-1993 data) are ABSENT. Reported absent, not filled.
2. **Reference period 2025-10 DOES NOT EXIST for either series.** Both go
   ...2025-09, 2025-11... The September-2025 data were released very late
   (CPI 2025-10-24; EMPSIT 2025-11-20 against a normal first-Friday date) and the
   October-2025 reference month has no release row on BLS's own surfaces. **Any code
   that assumes 12 releases per year will fabricate an event here.**
3. **Four scheduled/actual disagreements exist and are resolved by document:**
   - CPI 1998-01: archive slug 1998-02-25, document says *"Tuesday, February 24, 1998"* → 1998-02-24
   - EMPSIT 1997-06: slug 1997-07-09, document says *"Thursday, July 3, 1997."* → 1997-07-03
   - EMPSIT 1999-12: slug 2000-01-19, document says *"day, January 7, 2000."* → 2000-01-07
   - EMPSIT 1998-10: slug 1998-11-05, document says *"For release: 1:30 P.M. (EST) … Thursday,
     November 5, 1998"* → 1998-11-05 **at 1:30 PM, the only non-8:30 release in the file.**
   **Lesson: the BLS archive filename is a slug, not a release date.** A random audit of
   25 further releases found 23/23 parseable slugs matching the document date (2 could
   not be parsed), so the slug is right ~96%+ of the time and wrong sometimes.
4. **BLS's own index carries duplicate reference-period labels.** `cpi_03122019.pdf` and
   `cpi_02132019.pdf` are both labelled "January 2019"; same for September 2019. Resolved
   to the schedule-agreeing date. Two rows affected.
5. **Day-of-week structure differs sharply between the two series** and matters for any
   day-of-week control: EMPSIT is Friday 379/394 times; CPI is spread Wed 135 / Tue 91 /
   Fri 87 / Thu 81. A CPI-and-NFP pooled event study without a day-of-week control mixes
   two different calendar objects.
6. All times are the EMBARGO time (8:30 AM ET except the one 1998 case). This is the
   information-release instant; a daily-bar study cannot see it, and the pre-announcement
   window is therefore the prior session's close to the release-day open.
