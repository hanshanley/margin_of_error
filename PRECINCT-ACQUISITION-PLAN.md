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

## Acquisition batch at `391c681`

- Minnesota 2026: **4,105** exact county/precinct joins to September 18, 2026
  official reference boundaries; **4,073** nonzero colorable precincts. House
  candidate counts reconcile from precinct to county to congressional district.
- Separate Minnesota voting statistics: **4,105** rows, using the official 2026
  media field layout. Only 2,490 precincts report statistics; **1,735 rates are
  withheld**, including incomplete reporting, small/inconsistent denominators,
  15 ballot-mode discrepancies, and House counts exceeding reported voters.
  Keep the original values and quality flags; do not repair them by substituting
  candidate votes for voters or calling an election-night fraction final turnout.
- Original 2020 NYT release: **146,596** reporting shapes across **46 states and
  D.C.**, with **142,609** colorable shapes. Preserve 96 missing-count Nevada
  rows as missing. Alabama, Alaska, Louisiana, and Virginia are absent from this
  source, not established unavailable. Reconstructed boundaries lack individual
  official flags, and some jurisdictions report by municipality.
- Complete source ZIP is byte-verified after upload:
  `voter-precinct-expansion-20261105/complete-additional-precinct-results.zip`,
  **398,235,632 bytes**, SHA-256
  `f0d46aa827cda1f0c47a3f5089a859c44c61e497b9386a89598878eef9d4c094`.
  This includes the full 276 MB original 2020 national GeoJSON gzip, not just
  metadata or the simplified map layers.
- Primary 2024 and NC/NM 2026 deployment `41944997086` passed the full live
  browser suite, including zoom, exact candidate colors/counts, and fallbacks.
  Expanded UI commit `8652eeec7df17cee362624c6fa22f8dfa9000ac2` deployed
  successfully in exact run **41949760328**. Its full live browser suite passed:
  actual candidate counts and exact fills in all 47 acquired 2020 jurisdictions
  and all 50 acquired 2024 jurisdictions; MN/NC/NM 2026; zoom/pan, histories,
  mobile, downloads, and no-JS/fetch-error fallbacks. The supplement is now
  **live-verified partial coverage**, not complete state/year coverage.

## 2022 original-source batch at `b645345`

Acquired **3,683,815 complete original CSV rows** for AZ, CO, CT, FL, GA, IA, LA,
MI, MN, MS, ND, NM, NV, NY, OR, PA, RI, SC, SD, TN, TX, UT, WI, WV, and WY.
Each file matches the exact Git blob from the reviewed archive inventory and has
an immutable source-commit URL. All original rows, ballot-mode columns, and
repository documentation are retained. The CSV structure audit found no malformed
rows, but **does not independently reconcile candidate totals or establish
complete statewide ballot coverage**. Georgia supplies separate ballot-mode
columns rather than a candidate-total column; do not silently manufacture totals.

The complete archive is
`voter-precinct-sources-2022-20261105/complete-2022-precinct-source-batch.zip`,
**22,214,839 bytes**, SHA-256
`3525bd75010236853748ed04edc0545c1a24834a0a0c9deb411d8c11885494d1`.
Keep these cells `acquired_originals_review_pending` / `full_originals_download_only`
until actual contest/scope/count reconciliation and correct-election geometry
checks pass. These are **not 25 published maps or turnout datasets**.

Next executable historical work: independently reconcile these 2022 returns and
acquire correct-election geometry; acquire county-only original leads for other
states rather than repeatedly downloading these 25 completed source files.
Broader Harvard search identified MIT datasets `doi:10.7910/DVN/EOKNGW` (House),
`doi:10.7910/DVN/IAD3XR` (Senate), and `doi:10.7910/DVN/UYQIEP` (state packages).
House file `13996912` has 784,248 observations and MD5
`8922970b43a9c0db4830b1a164988b5c`, but metadata/export/download requests returned
HTTP 403. These are identified leads, **not acquired data**. Use legitimate
published alternatives; do not bypass access restrictions.

## North Dakota 2026 count acquisition at `dc3dce1`

All **358** House reporting rows and separate precinct ballot counts reconcile
through **53 counties** to statewide totals: **234,595 House votes** and
**239,057 ballots**. Candidate votes are not turnout. All **358 precinct rates**
remain withheld because the source omits an appropriate precinct denominator.
The [official terminology](https://www.sos.nd.gov/elections/election-results)
defines eligible voters as the Census annual estimate of residents age 18+,
despite the API field being named `registeredVoters`.

The complete, independently redownloaded and byte-verified archive is
`voter-precinct-north-dakota-20261105/complete-north-dakota-precinct-source-review.zip`,
**2,426,904 bytes**, SHA-256
`2d33d487e1eca9cab798b8ed192ef43495025598206ba39e79816f9fae2fc6c6`.
Data: `data/precinct-source-reviews/20261105/ND/`. The archive contains the full
all-contest original, every normalized House and ballot row, all reviewed API/GIS
captures and original-byte checksums. Reproduce with
`scripts/review-north-dakota-precinct-results.py`; 54 collector tests pass.

The official current-portal GIS manifest was generated March 9, 2026. Sampled
Adams County has **five split polygons for one House reporting unit**, using UUID
boundary IDs, not the reporting ID. This is a one-county diagnostic, not a
statewide unavailability finding. Keep `full_counts_download_only` and withhold
geometry in this immutable initial review until the reporting-unit/split
crosswalk is established. The subsequent mapped supplement is documented below;
do not overwrite the original count review.

## North Dakota 2026 mapped supplement at `4c9682b`

The official Secretary of State election-resources page links its **2026 boundary
package**, and the linked GIS layer explicitly describes **2026 election precinct
splits**. Acquired all **912** GIS split records, both complete native Esri and
GeoJSON exports, full layer metadata, and the original 2026 geodatabase ZIP.
The native Esri ring roles preserve holes misgrouped in the service's GeoJSON
export. The complete original exports are retained for independent review.

Join the explicit **CountyID + Precinct** fields to the county-scoped reporting
labels, requiring each county's entire code set to match. Do not infer this join
from part-ID prefixes. This yields **338** reporting-unit geometries across
**51 counties**, **335** with nonzero candidate results. All split parts are
dissolved into one reporting-unit shape; candidate votes are counted once.
All **358** original normalized House rows remain byte-equivalent to the original
count review, including the 20 unmapped rows. All 358 ballot rows remain separate
and all participation rates remain withheld for missing precinct denominators.

Remaining source defects: **Morton** uses county ID `30859` instead of `38059`;
**Towner** has an extra `48150` precinct label. Both counties remain withheld
without independently documented corrections. The source also has **200**
overlapping reference-geometry pairs. Their ambiguous strips are removed from
both affected precincts, not assigned to either, so state fallback remains
visible there. **172** units are affected; the largest excluded fraction is
**0.363%**. Votes still describe the entire reporting unit, never an allocation
to the clipped area. The excluded-area GeoJSON and per-unit areas are retained.
The geometry pipeline records **26** area-preserving topology repairs, uses a
`1e-9`-degree processing grid, and checks remaining overlaps against an explicit
`1e-10`-square-degree numerical tolerance.

Immutable data: `data/precinct-results/20261105-north-dakota-02/`.
Reproduce with `scripts/build-north-dakota-precinct-results.py`; **59** collector
tests cover count reconciliation, split dissolution, holes, wrong parent IDs,
wrong reporting sets, substantive repair rejection, duplicate geometry, and
ambiguity masks without vote reallocation. Seven existing renderer tests pass.
The complete archive was uploaded and independently redownloaded byte-for-byte:
`voter-precinct-north-dakota-maps-20261105/complete-north-dakota-2026-precinct-maps.zip`,
**12,179,890 bytes**, SHA-256
`355f116484e104eac422a6a24057600af70ec6ada83e3eb34c3c57bbebdb54d0`.

Publication status: **live-verified partial coverage**, not complete statewide
coverage. UI commit `0696cbf94302dde7bc9f7456920a539e540e0b05` deployed in exact
successful run **41954565149**; live registry, ledger and renderer bytes match
that commit. The full live browser suite passes, including exact
North Dakota counts/fills, truthful ballot-count/no-denominator details, selection
and zoom; every acquired 2020/2024 jurisdiction; mobile, downloads, no-JS and
failed-fetch fallbacks. The initial live run stopped on exactly one pixel of
page-position variation during wheel zoom. The checker now permits that one-pixel
rounding difference while still requiring prevented wheel defaults and actual
map zoom; the full rerun passed without any renderer change.
Astro check has zero errors/warnings and five existing
hints; build and all four built-in caucus tests pass. Pages preparation verifies
94 byte-identical relocated originals and a **986,189,318-byte** artifact.
The website now uses source-specific documentation links instead
of attaching the NYT 2020 license to every supplemental dataset.

## Next 2026 acquisition: Vermont

While North Dakota deploys, acquired **nine original JSON files**, **5,007,208
bytes**, from the actual public requests of `https://electionresults.vermont.gov/`.
Cache: session `files/precinct-expansion-sources/VT-2026/`, with exact URL/length/
SHA-256 receipts in `sources.json`. These are **session-cache acquisitions only**,
not yet committed, publicly downloadable, independently reconciled or mapped;
do not change the worklist's publication status on this evidence alone.

The public election metadata identifies election **7100**, GUID
`68d61e96-1d28-4210-8c1d-8e90512ae105`, **2026 GENERAL ELECTION**, November 3,
2026, unofficial, and advertises timestamped source paths under
`https://static.electionresults.vermont.gov/elections/`. Acquired metadata:
`elections.json` and `68d61e96-1d28-4210-8c1d-8e90512ae105.json`.
Its source timestamp is `20261104211117`. All advertised office tabs are captured:
federal (`-f-`), statewide (`-s-`), senate (`-sn-`), house (`-h-`), county
(`-cty-`), town (`-t-`), plus separate turnout (`-turnout-`).
The cache filename `full-results-20261104211117.json` contains **federal only**,
not every contest; the other captured files are necessary for the complete set.

Next: reconcile the federal `d/o/cs` records and `rc`/`wc` candidate counts to
source totals, preserving blank/overvotes separately; establish whether each
return is town-aggregate or a distinct polling unit. The turnout feed has `tid`,
`tn`, `tvr`, `tvc`, `tabs`, `tdis`, `tdisr`, and `hl`; confirm their meanings from
the public UI before using any denominator or absentee count. Do not equate
town totals or House-district splits with precincts. Acquire explicit current
geography and a source-backed identity crosswalk; preserve a complete immutable
download before calling any source acquired in the published ledger.
The general SOS results page returned HTTP 403 to requests; no bypass was used.
The public election portal and its normally requested static JSON were accessible.

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

- **North Dakota 2026 is the next concrete acquisition to normalize.** The
  official archive links current results to `https://resultsnd.sos.nd.gov/`,
  while `https://results.sos.nd.gov/` defaults to the older 2024 election.
  The new public API identifies election **348**, `2026 General Election`,
  November 3, 2026, unofficial, source version `v75`. The advertised complete
  original has been acquired and reconciled (5,779,260 uncompressed bytes):
  `https://resultsnd.sos.nd.gov/results/north-dakota/348/FullDataFile.json`.
  It contains `ElectionData`, `TurnoutData`, and `ContestData`, including nested
  county and precinct rows. The committed count review and complete release are
  documented above. Cached sources and checksums are in the session's
  `files/precinct-expansion-sources/ND-2026/`; this is **reconciled count coverage,
  not a published map**. Public feeds:
  `https://api.resultsnd.sos.nd.gov/Election/GetElectionInfo?cId=north-dakota`,
  `https://api.resultsnd.sos.nd.gov/Turnout/GetTurnout?cId=north-dakota&electionID=348`.
  GIS manifest:
  `https://resultsnd.sos.nd.gov/gis/states/north-dakota/manifest.json`
  (generated March 9, 2026; precinct ID field `boundary_id`, name `CntyPrecSp`).
  Actual geometry is county-sharded:
  `https://resultsnd.sos.nd.gov/gis/states/north-dakota/counties-precincts/38001-precincts.json`
  is the acquired Adams sample. Replace the county FIPS only with IDs from the
  official county layer; the advertised statewide `precincts.json` returns 404.
  All **53** old-portal county shards have now been acquired in session cache
  (**635** features); their exploratory prefix diagnostics are not a validated
  crosswalk. The explicitly identified 2026 Secretary of State GIS source and
  mapped supplement above supersede those diagnostics for publication.
  Exact live verification passed in run **41954565149**. Next: move to Vermont
  and other 2026 jurisdictions; retain Morton/Towner corrections as follow-ups.
  Do not repeat the completed old-shard acquisition. The API's `registeredVoters`
  field is not a registration definition: the official explanatory page defines
  eligible voters as the Census annual estimate of residents age 18+. Precinct
  leaves omit this denominator; retain counts and withhold rates rather than
  borrowing county denominators. Update supplemental download metadata for a
  non-NYT batch rather than displaying 2020 license links for unrelated data.
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
  This batch is now acquired at `391c681`; do not redownload its immutable
  snapshot. The field-layout URL sometimes returns a CAPTCHA to direct requests;
  its publicly accessible 2026 text was independently read and confirms all
  twelve voting-statistics fields. Use published documentation, never a challenge
  page as source data. The builder rejects HTML responses before caching them.
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

The original primary suite passed after exact deployment `41944997086`.
The expanded suite passed after exact deployment `41949760328` (session shell
`449`). Do not rerun these completed checks as a substitute for new acquisition.
For a metadata-only follow-up with unchanged renderer and geometry, verify its
exact deployment, live registry/worklist, complete downloads and unchanged
renderer bytes rather than duplicating the entire source-matched matrix.

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

Recurring prompt **#3** is active at a **15-minute interval** in the current CLI
session, replacing stopped prompts #1 and #2. It reads the updated plan, recognizes
the completed ND geometry acquisition and 338-unit mapped supplement, prioritizes
remaining 2026 jurisdictions, and resumes only unfinished exact live verification
rather than restarting old checks. Inspect active schedules to verify
its current status; the document alone does not establish a running scheduler.

Stop the recurring schedule when the requested acquisition/publication work is
finished, when the user asks to stop, or when no actionable work remains after
documented alternative attempts. If a scheduled run is blocked, persist the exact
blocker and next action rather than manufacturing a completed status.
