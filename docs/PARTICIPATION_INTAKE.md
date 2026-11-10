# Participation intake

**Migration in progress.** The shared engine and a native Minnesota pilot work.
The website's active reader chain and coverage dashboard are not yet switched.
The data-only publisher has local Git tests; public activation remains pending.
Historical releases remain reproducible and unchanged.

## One contract

| Field | Meaning |
|---|---|
| Election | Source-qualified identity, year, date and election type |
| Geography | Native identity, parent and explicit approved/unmatched reference binding |
| Measure | Literal source label, unit and separately qualified mode |
| Count | Exact integer including genuine zero; unknown/withheld remain null |
| Denominator | Native count, meaning and explicit rate qualification |
| Source clock | Literal publication clock; unknown timezone stays null |
| Reporting | Literal status and complete/partial/unknown unit inventory |

Original hashes, selectors, native fields, conflicts and qualifications travel
with every observation. Candidate votes never substitute for participation;
source conflicts are retained, not repaired. The portable structural schema
is generated from the same contract code; the shared validator additionally
checks cross-field semantics.

## Intake, not importer wrappers

Registered field mappings feed direct CSV/delimited, JSON/API or PDF adapters.
None invokes an old state importer. Exact input/spec/code hashes skip unchanged
work. Approved reference hashes and native identity bindings are reused; a
count update does not trigger boundary acquisition or another topology campaign.
Conditional HTTP responses reuse verified originals. Access denials stop routes.

```bash
python scripts/participation-intake.py ingest \
  --source data/participation-intake/sources/mn-2026-statistics.json \
  --work-dir /path/to/private-intake-cache \
  --input statistics=/path/to/original-pctstats.txt \
  --input page=/path/to/original-statistics-page.html \
  --geometry mn-precincts=/path/to/approved-MN.geojson.gz \
  --geometry mn-counties=/path/to/approved-county-reference.geojson.gz
```

Supplied files use held originals without reacquisition. Without supplied inputs,
the engine acquires only the registered source routes. Supply approved geometry
once; later runs reuse its verified cached original.

## Complete downloads

Each accepted run produces full JSON/CSV queries, validation and a complete ZIP:
permitted sufficient originals, full reference geometries/bindings, source spec,
contract/schema, maintained code/tests, dependency pins and checksums. HTML
publisher scripts/styles are excluded; their complete visible factual text,
including every numerical table cell, is retained instead. Private person
records are quarantined and never packaged.

Extract the ZIP and run `python reproduce.py > reproduced-queries.json`.
Reproduction verifies every packaged member, reruns the direct adapter and
common checks, and requires exact full-query equality without acquisition.
Rejected reports reproduce their actual rejection rather than approved counts.

Run the focused checks with `python scripts/test-participation-intake.py`.

## Resident context and independent data publication

The same package provides direct native ACS tables and counted public ArcGIS
queries. County income, exclusive race/Hispanic-origin groups, age and education
retain their native Census identities, periods, special values and MOEs.
Conditional precinct context uses local block-group cells and explicit population
or housing-unit proxy fractions, not state survey allocation. Income uses bins;
source medians are never averaged. These are resident profiles, not voter
characteristics or demographic turnout.

`package-participation-context.py` packages all complete ACS originals, the native
Gazetteer original, full county queries, approved references and maintained code.
Its offline reproducer checks every member, every native county cell and exact
runtime bytes. No reference is reacquired or repaired.

`participation-dataset.py` creates content-addressed runtime shards.
`publish-participation-dataset.py` stages and anonymously checks those bytes on
the separate `participation-data` ref before activating the catalog. A complete,
anonymously verified immutable scientific download is required first. The
publisher uses a temporary Git index and never moves the source worktree HEAD
or index. A later data update does not trigger a main-branch Pages build.

County reproduction uses the standard library. The optional spatial checks use
the pinned `requirements-participation-context.txt`; no spatial qualification is
implied merely by publishing a county dataset.
