# Nationwide precinct acquisition and publication plan

## Objective and priority

Expand actual precinct coverage across all 50 states and D.C. and across election
years. Two partial 2026 states and one broadly mapped presidential election are
not an acceptable stopping point.

Work in this order: **2026, 2024 gaps, 2022, 2020, 2018, 2016, then every earlier
even year through 1964**. Include midterms. Pursue each jurisdiction separately;
do not add only one example state per year. While a newer source downloads or
awaits publication, acquire independent historical batches rather than idling.
Record unresolved newer-state work and return to it; do not silently abandon it.

The canonical state/year checklist is `public/precinct-coverage.csv`, with
`PRECINCT-COVERAGE.md` as its readable counterpart. Both track all 1,632
state/election cells. This plan specifies the work, not a second completion ledger.
Generate the ledger with `scripts/build-precinct-coverage.py`; do not hand-edit
generated statuses or treat source leads as acquired data.

## Starting point, not completion

At commit `5a6fb2a`:

| Election | Acquired candidate-result maps | Outstanding work |
|---|---|---|
| 2026 | NC: 2,591 shapes; NM: 598 shapes, both partial | Acquire every other jurisdiction; improve NC/NM ballot and boundary coverage |
| 2026 DE | All 530 House reporting districts reconciled; complete source ZIP available | Obtain matching 2026 boundaries; older official reference has conflicting IDs and remains withheld |
| 2024 | 163,788 mapped shapes across 49 states and D.C., with source caveats | Alaska, omitted precincts, missing geometry, and other documented gaps |
| 2022 and older | Broader precinct candidate-result integration unfinished | Acquire and map multi-state batches for each election, newest first |

These are candidate-result layers, not participation rates. Existing participation
series and NC precinct participation histories remain separate. No state/year is
declared fully complete.

## Resume procedure for every work session or scheduled prompt

1. Read `AGENTS.md`, `CLAUDE.md`, `PUBLISHING.md`, this plan, and the newest rows
   of `public/precinct-coverage.csv`. Check `public/precinct-results.json`, recent
   commits, the dirty worktree, and active acquisition/test/deployment processes.
2. Resume ongoing work before starting duplicate downloads or competing writers.
   Never revert another process's changes, rerun an immutable completed snapshot,
   or replace a published release asset.
3. Pick concrete next state/year cells in priority order. Execute acquisition and
   integration, not merely another inventory or progress summary. Use small
   independently verifiable batches; do not defer all commits until nationwide
   completion.
4. Update the acquisition record with the exact source URL/version, actual election
   identity, format, counts, boundary vintage, join key, audit outcomes, remaining
   gaps, and next executable action. Persist any new source review in the
   reproducible data workflow so ledger regeneration retains it.
5. Test, publish, and verify completed batches as below. Keep working on subsequent
   cells while independent bounded downloads, builds, or deployments run.

## Acquisition work

### 2026 first

Work through all 51 jurisdiction rows, not just NC/NM/DE. Search official statewide
precinct exports and exact-election boundary releases first, then county feeds
and authoritative GIS services. Review both returns and ballot/registration
counts where available.

Concrete next investigations already identified:

- Minnesota: official election ID `201` exposes federal results by precinct;
  investigate the official September 18, 2026 precinct boundary release and exact
  county/precinct identifiers. Verify election identity and reconcile totals.
  The official media page links to
  `https://electionresultsfiles.sos.mn.gov/20261103/ushousepct.txt`,
  `https://electionresultsfiles.sos.mn.gov/20261103/USHouseCty.txt`,
  `https://electionresultsfiles.sos.mn.gov/20261103/ushouse.txt`,
  `https://electionresultsfiles.sos.mn.gov/20261103/pctstats.txt`, and
  `https://electionresultsfiles.sos.mn.gov/20261103/PrctTbl.txt`.
  Read the field layout at
  `https://electionresults.sos.mn.gov/Results/MediaFileLayout/Index?erselectionId=201`.
  These links are inspected leads, not yet acquired or validated result layers.
- California: inspect the official 2026 media files and county exports; determine
  whether each feed contains actual precinct results rather than only counts of
  reporting precincts.
- Delaware: seek the correct 2026 boundary set or an official documented
  crosswalk. Keep all acquired reporting counts available while geometry is
  withheld.
- Continue all other states/DC from the canonical ledger. A missing file in
  OpenElections is not evidence that official or county data are unavailable.

### Historical multi-state acquisition

- Acquire 2022 first, including verified precinct-result/boundary packages from
  VEST, official state archives, and other primary research repositories.
  The initial Harvard Dataverse search restricted to `electionscience` did not
  identify a 2022 dataset; broaden collection/title filters rather than treating
  that search as evidence of unavailability.
- For 2020, inspect the original attributed-release dataset at
  `https://github.com/TheUpshot/presidential-precinct-map-2020`, including its
  license, complete state caveats, original geometry, and counts. Do not use
  reallocated 2020 comparisons from the 2024 map instead.
- Continue 2018, 2016, and older years using original exact-election releases,
  state GIS archives, OpenElections, and documented research datasets.
- Review allocation methods in research releases. Estimated, reallocated, or
  reconstructed counts must not be presented as directly observed precinct votes.
  Retain approximation flags on reconstructed boundaries.
- Integrate additional year/state indexes without breaking existing acquired
  layers. Do not reuse another year's shapes simply because precinct names match.

## Non-negotiable data and UI requirements

- Preserve original sources, all normalized rows including unmapped units,
  licenses, state notes, and checksum manifests. Provide **complete query/data-set
  downloads**, never metadata-only substitutes.
- Validate election date and contest identity, duplicate keys, candidate coverage,
  ballot-mode sums, precinct/county/state reconciliation, geometry identity, and
  suppression. Suppressed or missing votes are not zero.
- Do not allocate state/county results or administrative early/mail totals into
  residential precincts and label them observed precinct results.
- Precinct red/blue coloring uses that precinct's own candidate votes. Its margin
  is `100 * (Democratic - Republican) / all contest votes`.
- Keep state result colors underneath missing or withheld precinct layers. Do
  not replace valid red/blue results with gray or manufacture precinct colors.
- Candidate counts are not turnout. Participation requires source-defined ballots
  or voters and an appropriate electorate denominator; preserve definitions and
  distinguish demographic estimates from directly observed counts.
- Retain 2026 as default. Verify zoom, actual precinct fills, selection, counts,
  year switching, history, mobile touch, and state fallback.
- Cross-year matching of identifiers does not establish unchanged precinct
  geography or electorate. Do not claim a boundary crosswalk without evidence.

## Verification and publication

Use the existing research Python environment:
`../voter-participation/.venv/bin/python`.

Run focused collector tests for new parsers and joins, relevant Node tests and JS
syntax checks for renderer changes, and existing Astro checks/build when changing
the application. Run `git diff --check` before committing. Keep the pinned
`public/voter-participation/` research export byte-identical.

For browser-facing batches, build and prepare the Pages artifact, verify complete
release downloads and the Pages size limit, then run source-matched browser checks:

```sh
npm run build
node scripts/prepare-participation-pages.mjs
../voter-participation/.venv/bin/python scripts/check-participation-browser.py
```

After pushing, verify the deployment for the **exact commit**, then run the
necessary live checks against `https://www.themarginoferror.com`. A successful
older deployment or local suite is not proof that the latest revision is live.
Use `snapshot_ready` before live verification; use `published_partial` only for
live-verified mapped subsets. Withheld geometry stays withheld. Do not mark a
state/year complete merely because one source release is exhausted.

The full live suite for `5a6fb2a` was started after its exact deployment in shell
`402`. Check its actual outcome before launching another copy or setting the
publication flag; this statement is not a claim that the suite passed. Shell IDs
are session-local; the persistent GitHub deployment run ID is `41944997086`.

## Commits and recurring execution

Commit and push each coherent validated acquisition or integration batch
periodically as **Hans Hanley**, author and committer, with **no Copilot
attribution, co-author trailer, or session trailer**. Do not make empty heartbeat
commits or amend history. Preserve unrelated worktree changes.

The current working branch is `voter-participation-analysis`; publication uses
`git push origin HEAD:main`. Verify branch/remote state before using that command.
Bulk immutable geometry lives under `data/`, not duplicated into the near-limit
Pages artifact; retain complete release ZIPs and verified pointers.

The recurring prompt must read this plan and the ledger, resume existing work,
make concrete acquisition/integration progress, validate and commit useful
batches, and report actual gains and unresolved gaps honestly. It must not
repeatedly announce existing partial coverage as completion.

Recurring prompt **#1** was created with a **15-minute interval** in the current
CLI session. Inspect active schedules to verify its current status; the document
alone does not establish that a scheduler is still running.

Stop the recurring schedule when the requested acquisition/publication work is
finished, when the user asks to stop, or when no actionable work remains after
documented alternative attempts. If a scheduled run is blocked, persist the exact
blocker and next action rather than manufacturing a completed status.
