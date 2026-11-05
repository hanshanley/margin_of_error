# Nationwide precinct acquisition and publication plan

## Objective and priority

Expand actual precinct coverage across all 50 states and D.C. and across election
years. Two partial 2026 states and one broadly mapped presidential election are
not an acceptable stopping point.

The user also explicitly accepts **county results instead of precincts, or both**.
Acquire and publish verified county coverage in parallel with finer precinct
work; label the geography explicitly. Never paint county totals as precinct
results, allocate them into precincts, or call candidate margins participation.

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
Final status commit `b614fbc988c3efbfcddefaccf220e815b53f50e5` deployed
successfully in exact run **41955692859**; the live registry, full ledger and
unchanged renderer match that commit byte-for-byte.
Astro check has zero errors/warnings and five existing
hints; build and all four built-in caucus tests pass. Pages preparation verifies
94 byte-identical relocated originals and a **986,189,318-byte** artifact.
The website now uses source-specific documentation links instead
of attaching the NYT 2020 license to every supplemental dataset.

## Vermont 2026 source/count review at `1ed9421`

Acquired **nine original JSON files**, **5,007,208
bytes**, from the actual public requests of `https://electionresults.vermont.gov/`.
Cache: session `files/precinct-expansion-sources/VT-2026/`, with exact URL/length/
SHA-256 receipts in `sources.json`. All nine originals are now committed under
`data/precinct-source-reviews/20261105/VT/` and included in the complete,
independently redownloaded and byte-verified release:
`voter-precinct-vermont-20261105/complete-vermont-2026-source-review.zip`,
**412,981 bytes**, SHA-256
`7002f19e5002205cf3dcde93dd2870b1704d27a634c86b91b968b77e036a1df9`.
The immutable release tag targets exact data commit
`1ed9421a357a382c8b2b88474e7d104605d3fa31`. Website/worklist integration is
live-verified; this is **count/download coverage, not
mapped precinct coverage**.

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

Reconciled all **283 town/House-district/Senate-district reporting splits** to
the election metadata and statewide totals, candidate by candidate including
named write-ins: **304,588 candidate votes**, **594 overvotes**, **6,247 blanks**,
and **311,429 reported House-contest total**. The source's compact `ovc` ("other")
column includes blanks/overvotes; it is **not** other-candidate votes.
Source `countyId` values are local IDs, not FIPS. These are not established
polling precincts; this immutable count review claims no geography or map join.
The subsequent mapped supplement is documented separately below.

The separate **247-town** feed has **311,009** votes cast and **506,512**
registrations. The ordinary public app confirms `tvr` = registered voters,
`tvc` = votes cast and `tdisr/tdis` = districts reporting/total. The exact app
URL/hash and field definitions are preserved; copyrighted app code is not
redistributed. `tabs` remains uninterpreted. **241 provisional municipal
registered-voter fractions** are available; **six are withheld**. Grand Isle,
Orwell, Rockingham, West Rutland and Winooski disagree with House-contest
accounting; Colchester reports a different number of districts from its
legislative-split rows. Retain the original values and all flags, without
reallocation. Registration active/inactive definitions remain unspecified;
these rates are neither citizen/resident turnout nor demographic estimates.

Reproduce with `scripts/review-vermont-precinct-results.py`; **69 collector
tests pass**, including sparse write-ins, duplicate/unknown units, missing
counts, rollup errors, municipal disagreement and district-scope suppression.
Independent checks validate every original hash, normalized total, unique key,
municipal rate, ZIP member and CRC. All six office tabs are preserved, but only
federal House and municipal turnout are normalized; other offices remain
unreviewed.
Every review file was also reproduced byte-for-byte from only the nine
distributed original JSON files and their receipts. Website integration passes
all seven renderer tests, Astro check (zero errors/warnings, five existing
hints), build, the four built-in caucus tests, and Pages preparation:
94 byte-identical relocated originals and a **986,190,710-byte** artifact.
Focused production-preview checks pass for the VT complete-download link,
28 download-section links, honest municipal-only ledger, 2026 default, mobile
layout and no-JavaScript page. The unchanged map renderer already passed its
full live regression in the ND publication; do not repeat it solely for this
additional static source-review link.

Website integration commit `81a237cbd3d1f55f6fd80cd7ec52039b0935d93e` deployed
successfully in exact run **41956593219**. The live registry, full ledger and
unchanged renderer match that commit byte-for-byte. Live JS/no-JS checks pass
for the complete 412,981-byte download, correct source scope, 2026 default and
mobile layout. Next: publish the independently audited mapped supplement below.
Do not attach split counts to entire towns. Resolve
Colchester's reporting scope, the five ballot discrepancies, and registration
definitions; reconcile the remaining preserved office tabs.
The general SOS results page returned HTTP 403 to requests; no bypass was used.
The public election portal and its normally requested static JSON were accessible.

## Vermont 2026 conservative mapped supplement

Acquired the official VCGI item
`029e24e674234e2f8c1e3ae059931fcb`, owned by `Publisher_VCGI`, and its
advertised service:
`https://services1.arcgis.com/BkFxaEFNwHqX3tAw/arcgis/rest/services/FS_VCGI_VT_VOTE_AREAS_2026_general_WM_v1/FeatureServer`.
The service explicitly identifies the September 2026 release for the
**November 2026 general election**, not the separately captured August-primary
reference. All **318** source features are retained in both native Esri and
GeoJSON exports, with an independent count, item/service/layer metadata and
exact URL/length/hash receipts. General cache:
session `files/precinct-expansion-sources/VT-2026-general-boundaries/`.
Do not repeat or substitute the separate primary capture.

The mapper normalizes only case, whitespace, hyphens and underscores in district
labels, keeping town identities literal apart from case. Every town's entire
House/Senate split set must agree. Ward parts are dissolved into reporting
splits and votes counted once. This yields **248 mapped/colorable reporting
splits**, **44 Republican-leading and 204 Democratic-leading**, not certified
polling-precinct coverage. All **283** original normalized rows and all
**247** municipal participation observations remain byte-identical to the
published count review; no municipal denominator or rate is attached to a split.

**35 rows in 25 towns remain unmapped**. The official reference has **22**
overlapping pairs; the largest overlap occupies over **38%** of one reporting
shape. Entire affected towns are withheld rather than clipping, assigning
ambiguous areas, or pretending a substantial defect is numerical noise.
Essex Town/Essex Junction City have different literal municipality labels in
the GIS reference; their four rows stay withheld pending documented identities.
Unmatched unincorporated areas are preserved, not assigned host-town votes.
The mapped subset has valid, nonoverlapping geometry at the explicit
`1e-10`-square-degree overlap tolerance, using the existing `1e-9`-degree
native-geometry processing grid. Every published shape was independently
compared with the original GeoJSON union.

Reproduce with `scripts/build-vermont-precinct-results.py`, supplying the
original archive basename. All **82 collector tests pass**, including ward
dissolution without duplicated votes, full-town scope checks, overlaps with
unreported areas, literal town identity, punctuation collisions, geographic
identity, projection and truncation. Every output file reproduces byte-for-byte
from only distributed originals. Full archive CRCs, member bytes, source
checksums and unchanged original count-review files pass independent checks.

Data: `data/precinct-results/20261105-vermont-03/`.
Complete archive: `complete-vermont-2026-reporting-split-maps.zip`,
**4,857,690 bytes**, SHA-256
`0c3777c6a5691d8fe97709c12ed56ed06c7757ad56a5efe74cea392f011e274c`.
Data commit: `7deca2dad49cdf72515fd83abb065f5bcd628ac6`. The immutable release
`voter-precinct-vermont-maps-20261105` targets that exact commit; its full ZIP
was independently redownloaded and verified for length, SHA-256 and CRCs.
Website registration passes seven renderer tests, Astro check (zero errors and
warnings, five existing hints), build, four caucus tests and Pages preparation:
**94 byte-identical relocated originals**, **986,193,681-byte** artifact.
Focused production-preview checks pass for every mapped count and exact fill,
red/blue selection, separate municipal participation, button/wheel zoom,
2024/2026 switching, county/district state fallback, desktop/mobile layout,
31 complete-download links, no-JavaScript content and aborted-fetch fallback.
Selecting a small split legitimately reaches the maximum zoom; control tests
first zoom out before testing zoom in. Geographic fetch errors are disclosed
in the geography note, not the general caption. No renderer change was needed.
UI commit `84d9645d439f453afca788b410ab66d6d2d0143b` deployed successfully in
exact run **41958527818**. The live registry, ledger and unchanged renderer
match that commit byte-for-byte; every focused preview check above also passes
live. The complete mapped supplement is **live-verified partial coverage**,
not every precinct. Proceed with Idaho and other unacquired 2026 jurisdictions
rather than rerunning unchanged national layers.
Final status commit `5c71828190a324b92650091de7b9184ae8ba64f8` deployed
successfully in exact run **41959532077**. The production registry, full ledger
and unchanged renderer match that commit byte-for-byte.

## Idaho 2026 complete count review

The official public portal
`https://results.voteidaho.gov/results/public/id/elections/nov2026` identifies
the production November 3, 2026 general election, unofficial, state election
`01000000-9c16-51a0-5d47-08df20ba1eaa`, publish version
`f7c0af8a-b1f1-4001-b755-129b96f07982`, as of
`2026-11-04T22:15:32.675786Z`. Its statewide JSON is a summary, not precinct
results: precinct and turnout arrays are empty, and registration rows describe
44 counties. Do not mistake them for precinct observations.

The portal's visible **Download Reports** button opens a normal report page
with complete advertised downloads. Acquired both XLSX workbooks and both PDF
reports, retaining the already captured public `/data` and `/closeraces` JSON:
**six complete originals, 6,288,693 bytes**, with exact public URLs, sizes and
SHA-256 receipts in session
`files/precinct-expansion-sources/ID-2026/sources.json`. Unrelated basemap
responses are excluded. Do not reacquire these originals or retry the failed
exact-accessible-name selector/network-idle wait.

The results workbook has **141,838 precinct-result rows** and **6,302 county
summary rows**. An independent diagnostic finds no duplicate identities and
exact reconciliation of every precinct-to-county candidate/statistic key.
Both result and ballot workbooks identify the same **986 reporting units**
across all **44 counties**. Separate reported totals are **731,980 ballots**
and **1,055,089 registrations**. This is diagnostic evidence, not yet a
released normalized count review or mapped coverage. Twin Falls registrations
disagree with the API's county total; special absentee/early units and small,
zero or inconsistent denominators require explicit scope flags and withheld
rates, not fabricated turnout.

The reproducible count review is now built at
`data/precinct-source-reviews/20261105/ID/` using
`scripts/review-idaho-precinct-results.py`. **102 collector tests pass.**
All **986 House rows** reconcile to both district APIs by original native
candidate identity and name. County party labels differ only by an explicitly
accepted terminal ` Party`, not by candidate aliases. Candidate totals are
**242,058 Democratic**, **414,312 Republican**, **53,032 other**:
**709,402 candidate votes**, never turnout. House votes plus overvotes and
undervotes equal each unit's own House-contest ballot total.

Separate ballot totals independently match every county API total. **Seven**
House-contest versus separate-ballot disagreements are retained, with rates
withheld. Entire counties with separately reported absentee/early units or an
API registration disagreement also have no rate; no pooled ballots are
allocated. There are **815 provisional registered-voter fractions** and
**171 withheld rates**, with raw published percentages and every source count
preserved. These are source reporting units, not verified polling precincts or
demographic groups. All original-source hashes, normalized totals, rate flags,
unique identities and complete ZIP members/CRCs pass independent validation.
Every review file reproduces byte-for-byte using only the six distributed
originals and their receipts.

Complete review ZIP: **4,016,510 bytes**, SHA-256
`0b7eb5da2d55c80c9bb005741d2e95774d45db209d21f9cd753dc99b764bd8be`.
Immutable release `voter-precinct-idaho-20261105` targets exact data commit
`5c71828190a324b92650091de7b9184ae8ba64f8`; the complete uploaded asset was
independently redownloaded and passed size, SHA-256 and ZIP CRC checks. The
website count-download registration passed the build, Astro check, Pages
preparer (**94 byte-identical relocated originals**, **986,195,213-byte**
artifact) and focused desktop/mobile checks with and without JavaScript.
All **32** full-download links, latest-year default and honest Idaho state
fallback pass. Registration commit `51491ed9fc9d29001daa3c7b8b8981229a238f70`
deployed successfully in exact run **41960223557**. Production registry, ledger
and renderer bytes match the commit; all four desktop/mobile, JS/no-JS
full-download and honest fallback scenarios pass live.

The Secretary of State's `https://voteidaho.gov/data-and-dashboards/`
explicitly links precinct boundaries for **both 2026 primary and general
elections** to official ArcGIS item `0b4fbe4f3104487da8bc5087f9321705`,
owner `State_of_Idaho`, authoritative/public. All **976** features were
acquired, with an independent count, complete original projected Esri export,
geographic Esri and GeoJSON exports, item/service/layer metadata and source
receipts. Cache:
session `files/precinct-expansion-sources/ID-2026-general-boundaries/`.
No export is truncated. All rows have `ACTIVE=Y`, with effective/inactive dates
retained for election-date checks. This is a genuine official 2026 reference,
not the portal's `Idaho2025` basemap.

The independently reproduced conservative mapper supports **448 units in
14 whole counties**, before website publication. It removes only the universal result
county suffix ` County` and normalizes textual case, punctuation and numeric
padding; no abbreviated-name expansion, renumbering or ID-only matching.
County scope must match completely after separately reported pooled units are
excluded, and every explicit congressional district must agree. All **976**
native-ring geometries are valid after one area-preserving repair. Six tiny
cross-reference overlap pairs exceed the existing `1e-10` square-degree
tolerance; the six implicated counties remain withheld, not clipped or
silently assigned. The other name/code mismatches require official crosswalks;
for example, similar numeric IDs are demonstrably not a safe statewide join.
Keep all 986 returns and separate participation records regardless of mapping.

## Idaho 2026 conservative mapped supplement

Data: `data/precinct-results/20261105-idaho-01/`.
Reproduce with `scripts/build-idaho-precinct-results.py`; **115 collector tests**
and seven participation tests pass. Match only unique, complete county-scoped
textual precinct-name sets and explicit congressional districts, using the
reference's actual effective/inactive intervals on November 3, 2026. Preserve
native polygon ring roles, including holes. Audit **all 976 reference features**
for overlaps, including reference areas with no matched result. Any invalid
geometry, ambiguous scope or overlap above the established tolerance withholds
the whole implicated county. Do not decode numeric IDs or allocate pooled votes.

The **448 mapped/colorable units** comprise **315 Republican-leading**,
**132 Democratic-leading**, and **one tied** unit. **538 source reporting rows**
remain unmapped, not deleted. Of the mapped units, **435** retain a separate
provisional ballots/source-registration fraction and **13** have their rate
explicitly withheld. Source registrations are not assumed to be registrations
at opening, eligible voters, or demographic denominators. Every one of the
986 original result rows and 986 separate participation rows remains unchanged.

Independent checks pass for every output/original checksum, all mapped candidate
and participation fields, native-ring versus published polygon areas, zero
final cross-precinct overlaps, ZIP CRCs/exact members/bytes, and byte-for-byte
reproduction using only the distributed originals and immutable count review.
The complete archive `complete-idaho-2026-precinct-maps.zip` is **34,504,158 bytes**,
SHA-256 `e8057feb5f6ceddeb2c88a39be934bb2ebf8957eb71387477df8c0c6b9ac2d57`.
It includes every original workbook, PDF, API capture, complete native/geographic
GIS export, metadata/attribution, receipt, unmatched row and audit. The complete
official webpage's HTML/frontend is not redistributed.

Immutable release `voter-precinct-idaho-maps-20261105` targets exact data commit
`664ef298d33a26fb52deb399596aad76a11098ed`; the complete asset was independently
redownloaded and verified for tag target, length, SHA-256 and ZIP CRCs.
The website registration pins that exact data revision, initially `snapshot_ready`.
The new source-specific detail branch labels ballots and source-registered
voters separately, without borrowing Minnesota's opening-registration definition.
Quality flags are human-readable; withheld rates are explicit.

Astro check has zero errors/warnings and five existing hints. Build, all four
built-in caucus tests and Pages preparation pass: **94 byte-identical relocated
originals**, **986,198,395-byte** artifact. Focused production-preview checks
pass for all 448 exact candidate counts/fills, red/blue selections, available
and withheld source-defined rates, button/wheel zoom, 2024/2026 switching,
county/district state fallback, desktop/mobile layout, all **35** full-download
links, no-JavaScript downloads and aborted-fetch fallback. ND ballot-only,
MN opening/day-of registration and VT municipal-selection regressions pass.
The source-specific detail branch is now verified in a real browser.

UI commit `4ca90991e6378ee03389f80894f55b81031ec497` deployed successfully in
exact run **41961338739**. Production registry, ledger and renderer bytes match
that commit. The focused production suite passes all 448 exact candidate
colors/counts, separate source-defined participation and withheld rates,
button/wheel zoom, year switching, ND/MN/VT regressions, desktop/mobile,
all 35 complete downloads, no-JavaScript and failed-fetch fallbacks.
The map is **live-verified partial coverage**, not complete Idaho coverage.
The final registry/ledger status update deployed in commit
`bbe629c459e53ad29b2008e62a99f56cd2645a94`, exact successful run
**41962727822**. Production registry, ledger and unchanged renderer match that
commit byte-for-byte, and the focused publication suite confirms Idaho's final
partial-live status. Do not repeat the unchanged full national browser suite.
Pursue official crosswalks, the six overlap counties, pooled scope and registration
discrepancies without rewriting the immutable review or borrowing older boundaries.

## South Dakota 2026 official export acquisition

The actual official `https://electionresults.sd.gov/Default.aspx` identifies
**General Election November 3, 2026**, unofficial, with **671/671 precincts**
and **66/66 counties** reporting. Search also returns a stale special-election
page; verify the election in each actual response instead of trusting that
cached title. Complete home, export and turnout pages and URL/size/hash receipts
are cached in session `files/precinct-expansion-sources/SD-2026/`.

The advertised `https://electionresults.sd.gov/ResultsExport.aspx` uses public
ASP.NET postbacks for **Statewide Export** and **Legislative Export**, not direct
guessed data URLs. Initial identity checks stopped before accepting a file
because CSS renders the header uppercase. Whitespace/case normalization confirms
the exact general-election date. Both complete original workbooks are acquired:
**38,361 bytes/13 sheets statewide**, **84,741 bytes/72 sheets legislative**.
They contain **county aggregates, not precinct rows**. The separately advertised
Aurora county export (**24,170 bytes/15 sheets**) contains actual precinct rows.
Candidate-column order is reversed relative to the statewide export; parse by
candidate identity, never column position. All **66 county originals** are now
acquired through their advertised public export links. The 68 workbooks total
**1,982,013 bytes**, retaining every sheet and contest, not only the reviewed
House contest. Do not download this completed batch again.

The official page's normal public requests supply independent county turnout:
`https://sdresws.azurewebsites.us/ResultsAjax.svc/GetVoterTurnoutData?`,
and candidate/party metadata:
`https://sdresws.azurewebsites.us/ResultsAjax.svc/GetCandidates?ElectionType=General&ElectionID=0`.
Both complete JSON responses are preserved. Catalog office ID `215` is shared
by the two House candidates; it is not a unique candidate ID or workbook
contest ID `14869`. The complete nine-page official November 3, 2026
polling-place PDF is also retained; polling locations are **not polygons**.

## South Dakota 2026 complete count review

Data: `data/precinct-source-reviews/20261105/SD/`. Reproduce with
`scripts/review-south-dakota-precinct-results.py`; **127 collector tests pass**.
All **671 House reporting rows**, including zero-count and duplicate-name rows,
reconcile to all **66 county totals** and the independent statewide workbook.
Candidate identity and official parties, not column position, establish
**195,583 Republican**, **109,985 Democratic**, **305,568 candidate votes**.
Other contests remain available in their complete original workbooks but have
not yet been independently reviewed.

All **671 separate turnout observations** reconcile to every county API ballot
total: **310,298 ballots**, not the candidate-vote sum. Independent county
registrations total **628,563**; the hidden page field `318,265` is nonvoters,
not registrations. Twelve explicitly identified vote-center counties repeat
their entire county registration in all **72 center rows**. Never sum those
denominators or call the resulting ratio residential precinct turnout.

There are **596 provisional source-registration fractions** and **75 withheld
rates**. All raw counts and flags remain available, including two small/missing
denominators, one ballot/registration inconsistency and one House/separate-ballot
disagreement; overlapping flags are not additive. Oglala Lakota has two source
rows named `Sacred Heart Church Hall`, one zero-count and one nonzero. Both
original House rows and both turnout rows remain separately identified by
their own physical source rows. Their cross-source pairing is withheld;
never match them by row order, count similarity or an invented identity.
Only whitespace normalization resolves the four trailing-space label differences.
Explicit vote-center markers must agree across the page, API and statewide
workbook; the parser does not silently remove conflicting scope markers.

Independent checks pass for every original/output checksum, every candidate
row and county/state total, every separate ballot/registration observation,
every rate and withholding flag, unique row identities, and ZIP CRCs/exact
members/bytes. Every output reproduces byte-for-byte using **only distributed
files**, without the original website frontend.

The complete archive `complete-south-dakota-2026-source-review.zip` is
**1,751,516 bytes**, SHA-256
`e925f182618c1b9c6195ce1f204479df38270ad7145a37868a6f5fb6876439a8`.
It contains **71 complete native originals, 2,242,570 uncompressed bytes**:
68 workbooks, two JSON responses and the polling-place PDF. It also contains
all 671 factual turnout observations and every county heading, complete
normalized results/participation, audits and source receipts. Original HTML
URL/size/hash receipts are retained separately; copyrighted frontend/template
code is not redistributed or falsely claimed to be included.

Data/parser/tests commit `77916b2106cb331ebe4fb6a5d3501b14b9c536bd` is pushed,
authored and committed as Hans. Immutable release
`voter-precinct-south-dakota-20261105` targets that exact commit. The entire
uploaded asset was independently redownloaded: tag target, length, SHA-256,
ZIP CRCs and every archived byte match. Seven participation regression tests
also pass. Registration now adds its complete download and persistent audit
to the 1,632-cell ledger, keeping `full_counts_download_only` and map joins
withheld. Local and exact production verification are documented below.

Local publication checks now pass: Astro has zero errors/warnings and the
same five existing hints; the production build and four caucus tests pass.
Pages preparation verifies **94 byte-identical relocated originals** and a
**986,199,529-byte** artifact. All **36** complete-download links and the
new full SD archive appear on desktop/mobile with and without JavaScript.
The 2026 default, honest red/blue SD state fallback, absence of fabricated
precincts, zoom and failed-registry-fetch fallback all pass. The final Idaho
partial-live status also matches the generated ledger.

Website registration commit `bbe629c459e53ad29b2008e62a99f56cd2645a94`
deployed successfully in exact run **41962727822**. Production registry,
full 1,632-cell ledger and unchanged renderer match that commit byte-for-byte.
All four desktop/mobile, JS/no-JS checks pass live, including all 36 complete
downloads, the independently hashed full SD archive, latest 2026 default,
honest SD state colors, no fabricated precincts, zoom and failed-fetch
fallback. Idaho's final partial-live status is also exact-verified.
This is a live **complete count download**, not a South Dakota precinct map.

## South Dakota 2026 county geometry follow-up

The official Minnehaha precinct page
`https://minnehahacounty.gov/dept/au/election/precinct_info/precinct_info.php`
advertises its 2026 maps and public GIS app
`83db20af25c2402a8390082f51baa059`. That app points to public webmap
`7cc5bcba864d4d4781b83b229f2b8819`, whose voting-precinct layer is
`https://gis.minnehahacounty.gov/minnemap/rest/services/Election/Redistricting_2022/MapServer/4`.
The service name alone is not the election vintage. The separately acquired,
complete native county PDF is explicitly dated **March 25, 2026** and its
official link identifies the 2026 map. Direct requests to the county HTML
page returned 403; the advertised public GIS and PDF downloads work normally.
Do not bypass the denied HTML page or mistake polling locations for polygons.

Cache: session `files/precinct-expansion-sources/SD-2026-Minnehaha-boundaries/`.
All **81 reference features** are acquired in complete native Esri,
geographic Esri and GeoJSON exports, with independent count and full
app/webmap/service/layer metadata and exact-byte receipts. They represent
**80 unique displayed labels**; `VP-06` has two source polygon parts.
The House workbook has 80 Minnehaha reporting rows. Similar row counts
alone are **not a validated join**: source city names such as `1-4` differ
from result `Precinct-0104`; explicit native names, scope and formatting
need review, and all parts/topology must be audited before mapping.
No SD map is published and this cache does not overwrite the immutable
count review. Next: establish an official native-label/ID crosswalk, validate
the current reference against the dated 2026 maps and actual reporting
scope, inspect all polygon parts/overlaps, and test conservative joins.
Continue other counties without assigning vote-center returns to residential
precincts or pairing Oglala Lakota duplicates by row order.

The complete Sioux Falls city PDF is also acquired, explicitly dated
**March 13, 2026**. Its native table uses `01-04`, `01-05`, etc., providing
actual official formatting evidence between GIS `1-4` and source
`Precinct-0104`, not just equal row counts. The all-feature native-ring
diagnostic found no unrepaired invalid originals and one area-preserving
self-intersection repair, but **20 cross-precinct overlap pairs** exceed the
established `1e-10`-square-degree tolerance. Their largest area is
`4.6514208271236006e-08` square degrees. Do not waive that tolerance, silently
assign overlaps, or declare the county joined. `VP-06` must remain a single
reporting unit after dissolving its two source parts. The exact diagnostic
is retained alongside the complete originals; no SD mapped supplement exists.

## Alaska 2026 complete count review

The official homepage advertises the actual general-election page
`https://www.elections.alaska.gov/enr/26GENR/`. The superficially plausible
`/enr26/` page does not establish this election's identity and is not the
accepted source. The actual page's normal public data requests identify
**Alaska 2026 General Election**, unofficial, updated **November 4, 2026,
2:11 PM** in the source's displayed time. Schema `format="2024"` describes
its statistics format, not a 2024 election. Exact data paths advertised by
the application are `results/statewide.js`, `results/precincts.js`,
`shapes/districts.js` and `shapes/precincts.js`; those `.js` responses are
native JSON, not frontend code.

All **six complete native originals, 9,825,641 uncompressed bytes**, are
acquired: both result JSON responses, both shape responses, the full
**20,046-row all-contest CSV** and complete summary PDF. Full CSV/PDF URLs
come from the election response's advertised `precinctReportUrl` and
`summaryReportUrl`, not guessed filenames. Cache:
session `files/precinct-expansion-sources/AK-2026/`. Do not repeat this
completed download or distribute the cached HTML/frontend JavaScript.

Reproduce the immutable review at
`data/precinct-source-reviews/20261105/AK/` with
`scripts/review-alaska-precinct-results.py`; **146 collector tests pass**.
All **523 House reporting units** reconcile by literal candidate name and
party to both statewide native totals. All **402 geographic precincts**
also match their exact native IDs, names, candidate counts, ballots and
registrations. Preserve **120 pooled district units** (40 each for absentee,
early voting and question ballots) and **one federal overseas unit** rather
than allocating them into geographic precincts. Blank native IDs remain
separately identified by their actual source sequence and physical CSV rows.
The source reports 400/403 precincts, where 403 includes the federal unit;
this is not certified, complete geographic all-ballot reporting.

Totals: **15,550 Democratic**, **105,647 Republican**, **91,812 other**:
**213,009 candidate votes**, separately **215,906 ballots** and **605,433
source registrations**. Other candidates remain individually preserved;
do not relabel Bill Hill's `NON` votes Democratic. The original source has
**221** candidate-plus-under/overvote versus ballot discrepancies. Preserve
them, do not manufacture write-in counts or "correct" ballots. All **523
rates are withheld**: geographic units omit separately pooled ballot modes;
pooled/federal reporting units are not residential precincts. These are
unofficial reported candidate counts, not a final ranked-choice outcome
or demographic participation.

Independent checks pass for every original/output checksum, every candidate
and ballot/registration observation, all flags, 523 unique identities and
ZIP CRCs/exact members/bytes. All review files reproduce byte-for-byte using
only the six distributed originals and their receipts. Complete archive:
`complete-alaska-2026-source-review.zip`, **1,213,200 bytes**, SHA-256
`a38164a74cb3d433587891fdf243484f273a88f27f8439ceeeeb9da9c6772b3a`.
Data/parser/tests commit `683cd3f50e38b7555ff656df5c39eb59b1c061f6` is
pushed, authored and committed as Hans. Immutable release
`voter-precinct-alaska-20261105` targets that exact commit. The entire
uploaded ZIP was independently redownloaded: tag target, length, SHA-256,
CRCs and every archived byte match. The exact live publication proof follows.

Registration passes seven participation regression tests, Astro check
(zero errors/warnings, five existing hints), the production build and four
caucus tests. Pages preparation verifies **94 byte-identical relocated
originals** and a **986,201,012-byte** artifact. Focused production-preview
checks pass on desktop/mobile with and without JavaScript: all **37**
complete-download links, full AK ZIP length/hash, actual 1,632-cell ledger,
honest AK whole-state red/blue fallback without fabricated precincts,
latest 2026 default, zoom and failed-registry-fetch fallback. Idaho's final
partial-live and SD count-only metadata remain correct.

The complete count download is now **live-verified** at exact registration
commit `815a7a17a6921cb8e677ec6ad2a34c71f035c203`, successful Pages run
**41963874076**. Production registry, all 1,632 ledger rows and the unchanged
renderer match that commit byte-for-byte. The focused live checks pass
desktop/mobile with and without JavaScript, all **37** complete-download
links, the entire AK archive's exact length/hash, honest whole-state
red/blue fallback without invented precincts, latest 2026 default, zoom and
failed-registry-fetch fallback. This completes the count publication, not
Alaska's precinct map or any precinct participation rate. Proof: session
`files/ak-2026-count-live-validation/validation.json`.

The **402 unique native shape IDs** exactly match the geographic result
set, but this alone is not a validated map. The original map format has
delta-encoded paths grouped by polygon. Independently validate decoding,
ring roles, antimeridian handling, topology and actual 2026 reference scope
before a new immutable mapped supplement. Retain all 121 nongeographic
units without inventing residential locations or distributing district votes.
Other original contests remain available but have not yet been reviewed.

Full-path exploratory decoding examined all **478 polygon parts and 27
inner paths**, not a sample. There are no out-of-range coordinates or
antimeridian path jumps. Only **88 units** pass the initial strict polygon
repair check; **314** require additional handling of degenerate native
paths or zero-area line remnants returned by `make_valid`. Nine polygon
repairs preserve area. This is not a finding of source unavailability:
independently audit polygonal footprints and retain all source remnants
before accepting any area-preserving extraction. The zero overlaps found
among the 88 passing units are **not a statewide overlap audit** because
the other 314 references were excluded. Do not publish that subset before
checking overlaps against every full reference footprint.

The alternative all-feature polygonal-footprint diagnostic now includes
**all 402 units**. It finds **343** invalid-part repair records, **328**
GeometryCollection results and **117 cross-unit overlap pairs** above the
same `1e-10`-square-degree tolerance. **130 repairs across 127 units** change
area by more than that tolerance; zero-area line removal cannot justify
those substantive changes. One native outer path (`37-754`, part 2) has
only two distinct vertices. There is also an outside-shell inner path in
`08-085` and overlapping parts within `08-045`. Keep the simplified source
withheld rather than blindly accepting `make_valid` polygonal extraction.
The complete diagnostic is retained in the source cache as
`complete-polygonal-footprint-diagnostic.json`.

## Alaska complete full-precision locator reference

The actual official polling page,
`https://www.elections.alaska.gov/election-polls/`, advertises the public
locator app **579890d66c7e40ae9f7cc227d76669b1**. Followed its original app
configuration to webmap **6fac55e6f6914c0da0f90e7e444b3626**, then the
actually advertised precinct layer:
`https://services3.arcgis.com/AhVzMlCdMxpkPzPE/arcgis/rest/services/AK_Election_Geography/FeatureServer/7`.
App, webmap and service item **02dec5e7ae604bff951a95bc8a08f9e8** are public
and owned by **DOEALASKA**. Complete original item/service/layer/config
metadata, including source license information, are retained. The official
polling page explicitly says it was updated November 3, 2026 at 2:56pm,
but that establishes current use, not the boundary vintage.

Acquired **all 402 features** in three complete originals: native projected
Esri JSON (**28,994,894 bytes**), geographic Esri JSON (**35,529,088 bytes**)
and GeoJSON (**35,547,113 bytes**). All match the independent server count
and exact attribute/OBJECTID sets, without transfer truncation. All 402
literal precinct-number codes match the 2026 native geographic result set;
House district fields match their source precinct-code prefixes, not an
independently inferred spatial crosswalk. There are **nine label
differences**, retained individually rather than silently resolved as aliases.

Independent inverse-Web-Mercator calculations check **all 961,583
vertices**, with maximum coordinate error below `1e-9` degrees. All 402
native-ring footprints are valid after **two individually recorded
area-preserving repairs**; none has an antimeridian path jump. The complete
all-reference audit finds **20 cross-precinct overlap pairs** above the
unchanged tolerance. Three service GeoJSON geometries are invalid; do not
substitute their ring grouping for the native Esri roles.

Every feature's creation timestamp is from 2022; sample-ballot URL fields
are null. Neither that timestamp, a recent layer edit, exact matching IDs,
nor the current locator advertisement independently proves the exact 2026
boundary vintage. This is a more precise **acquired reference**, not an
accepted replacement for the explicitly dated election-native shapes.
No Alaska precinct map or rate is published from it.

The reproducible immutable reference review is
`data/precinct-boundary-reviews/20261105/AK/`, built with
`scripts/review-alaska-precinct-boundaries.py`; **162 collector tests pass**,
including 16 new reference-scope, projection, identity, truncation,
label-conflict, overlap and invalid-GeoJSON cases. It includes all 11
complete GIS/provenance JSON originals and a byte-identical copy of the
complete six-original count review, not only metadata. Cached polling-page
HTML is research-only and is not redistributed.

Complete archive: `complete-alaska-2026-boundary-reference-review.zip`,
**34,269,738 bytes**, SHA-256
`f8d07fbd8d4e7a463f1b21f10434fdae308588fa22505b5ea81f6b8821264811`.
Independent checks pass for every original receipt/uncompressed byte,
every output checksum, full ZIP members/CRCs/bytes, the previous independent
402-feature diagnostic, unchanged count-review files and byte-identical
review **and ZIP** reproduction using only distributed inputs.
Proof: session `files/ak-2026-boundary-independent-validation.json`.
The complete archive is now published in immutable release
`voter-precinct-alaska-reference-20261105`, targeting exact data/parser/tests
commit `a1ee6ee8c17bc1e9cb462c9954a030604f306ea6`, authored and committed as
Hans. An independent complete redownload verifies the exact remote tag,
asset length/hash, all **25 members**, CRCs and every member byte. Proof:
session `files/ak-2026-boundary-release-verification.json`. The separate
reference download does not change the live count-only registry, ledger,
renderer or their already verified publication status.

Next: seek explicit official 2026 boundary confirmation and audit the
reference against the actual 2026 native shape footprints. Resolve the
nine source-label differences without inferred aliases and handle all 20
overlaps conservatively against the complete reference, not only passing
units. If using the election-native simplified geometry instead, preserve
all remnants and withhold area-changing repairs; audit against all 402
footprints. Retain all 121 nongeographic reporting units without allocation.
Then build/test/reproduce a separate immutable mapped supplement before
changing the registry or coverage ledger. Do not overwrite either completed
review or repeat these original downloads. Continue other 2026 states/DC
and the acquired 2022 batch while independent publication steps run.

## Hawaii 2026: complete native count review; maps and rates withheld

The official `https://elections.hawaii.gov/election-results/` page advertises
eight available 2026 general-election originals under
`https://elections.hawaii.gov/wp-content/results/2026 General/`:
`media.txt`, `summary.txt`, `precinct.pdf`, `histatewide.pdf`, `cch.pdf`,
`coh.pdf`, `com.pdf`, and `cok.pdf`. The Statement of Vote label does not
currently have a download link; do not invent one. All eight complete
originals are acquired with exact final URLs, lengths and SHA-256 receipts.
No website frontend HTML is redistributed.

The PDFs identify **November 3, 2026**, **REPORT 3**, not certified results.
The statewide summary was printed November 4 at **09:09:04 am** and the
precinct report at **09:10:37 am**; county print times differ. The native
tab-delimited media file contains **25,766 all-contest candidate records**,
including quoted multiline names; the summary has **202 records**.
The parser preserves physical CSV start/end lines rather than treating
multiline names as additional records. House contests have native IDs
`30` (District I) and `5` (District II), with **1,438 candidate rows**
covering **496 distinct native reporting-unit IDs**.

Preserved scope: **247 geographic display labels with blank splits**,
**247 separate `VSC` split IDs**, and **OS I / OS II** blank-split units.
All blank-split units have native `Reporting=1`; all VSC units have
`Reporting=0`, despite nonzero in-person votes. Never turn that flag into
zero votes or merge identities by display-name similarity. Party fields
are blank; the candidate names carry explicit `(D)`, `(R)`, `(G)` or `(N)`
prefixes. Third-party votes and zero units are retained.

All six candidate identities and both ballot modes reconcile exactly
between complete media and summary text and the statewide PDF:
Case **115,188**, Lam **34,958**, Conley **5,792**, Berning **2,097**,
Tokuda **126,197**, Awa **61,839**. Candidate votes total **346,071**;
they are not the ballot numerator. House district denominators
**223 / 273** and counted flags **112 / 137** agree with the literal
reporting units; they are not established geographic precinct totals.
The summary repeats **853,399 statewide registrations** for both
districts. Sum unique native unit registrations once, not those repeated
district fields.

Actual unresolved source discrepancies are retained, not repaired:

- Native unit ballots total **365,903**, versus **365,897** in the
  statewide summary. Mail is **348,388 / 348,387** and in-person
  **17,515 / 17,510**. Summary candidate/blank/over/invalid accounting
  matches the statewide PDF exactly; native unit ballot counts do not.
- The complete **806-page** precinct PDF contains **498** distinct
  literal precinct/mode records. All **496** native units match their
  PDF candidate counts and ballot counts exactly. The two PDF-only
  records are zero-count **In-Person OS I / OS II**; preserve them rather
  than inventing additional native media rows.
- **235** VSC records have native registration zero but positive
  precinct registration in the corresponding PDF. All differences and
  PDF page references are saved. The native review has **261**
  zero-registration units and **230** ballots-above-native-registration
  flags. Do not copy PDF registrations into native rows or create rates.
- The four county PDFs sum to the same candidate counts and
  registrations as the statewide summary, but **two additional
  in-person ballots**. Their distinct printed snapshots remain separate.

Immutable review: `data/precinct-source-reviews/20261105/HI/`, produced by
`scripts/review-hawaii-precinct-results.py`. It includes all eight complete
compressed originals, all 496 normalized House and participation rows,
all six PDF observations, the complete discrepancy audit and checksums.
**179 collector tests pass**, including 17 new Hawaii native-identity,
mode, missing-count, source-line, PDF-vintage and denominator-preservation
cases. Independent checks verify every original/output receipt, all
**14 ZIP members** and CRCs, raw candidate/mode/participation rows, and
byte-identical review **and ZIP** reproduction solely from distributed
originals. Proof: session `files/hi-2026-independent-validation.json`.

Complete ZIP: `complete-hawaii-2026-source-review.zip`,
**4,331,576 bytes**, SHA-256
`e2d932615412d2d77436bda6566fa2c32692fff8b5ee622c47294afcead49d3f`.
The immutable release `voter-precinct-hawaii-20261105` targets exact
data/parser/tests commit `b01c32e84cb6346e6478f80c404eb82ec3e6bc7b`,
authored and committed as Hans without attribution trailers. An independent
full redownload verifies the remote tag, complete asset length/hash and
all 14 members/CRCs/bytes. Proof: session
`files/hi-2026-release-verification.json`. The count-only source-review
registry and generated 1,632-cell ledger now include Hawaii; exact UI
local validation passes: **179 collector tests**, **seven participation
Node tests**, all four build-time caucus checks, Astro check/build,
`git diff --check`, all **94** complete relocated asset bytes and a
**986,202,521-byte** prepared Pages artifact. Desktop/mobile with and
without JavaScript show all **38** complete download links. JS checks
retain default 2026, source-matched Hawaii **state** red/blue fallback
without fabricated precincts, working zoom and failed-registry-fetch
fallback. Registry, all 1,632 ledger cells and renderer match exact local
publication bytes. Proof: session `files/hi-2026-local-browser-validation.json`.

The build validator's obsolete participation-only wording, nine-download
constant and original-context national snapshot assumptions now follow
the current source registry and rendered nationwide snapshot, checking
every complete review link. All participation assertions pass. The full
site validator then reaches an **unrelated pre-existing UK topic-card
assertion**, `scripts/validate-build.mjs`: it expects 16 but the current
unchanged UK export has 23. The committed baseline contains the same UK
assertion; no UK source was modified. Do not report the site-wide
validator as passing or modify unrelated UK work to conceal the failure.
Exact count-publication commit
`6b6945b976efcebabf64b39cf1a90119108df365` was pushed as Hans
(author and committer) and Pages run **41967250527 succeeded**.
Production proof `files/hi-2026-live-browser-validation.json` passes
all the same exact registry/ledger/renderer, 38-download, desktop/mobile
JS/no-JS, source-matched Hawaii fallback, zoom and failed-registry-fetch
checks. The 496-unit Hawaii count review is **live as a full download**;
precinct geometry and rates remain withheld.

The advertised official GIS follow-up page is
`https://elections.hawaii.gov/resources/maps/geographic-information-systems-gis-files/`.
It labels its precinct sources **2022 Elections** and **2018 Elections**;
the current link is
`https://geoportal.hawaii.gov/datasets/HiStateGIS::election-precincts/about`.
Neither the map page's September 28, 2026 update nor a currently linked
older reference proves exact 2026 boundary vintage. Following that
dataset's own metadata identifies item
`37f83ac7f930421b97976956cccbd840`, owner `HawaiiStateGIS`, and exact layer
`https://geodata.hawaii.gov/arcgis/rest/services/AdminBnd/MapServer/13`.
The layer is explicitly **Election Precincts - 2024**, sourced from the
Office of Elections in **May 2024**, despite the older heading on the
elections GIS-link page. Treat it as a 2024 lead, not 2026 geometry.
Its advertised original metadata is
`https://files.hawaii.gov/dbedt/op/gis/data/precincts.pdf`.
The item URL already includes `/13`; do not append another layer suffix.
Session `official-geoportal-layer.json` is an unexpected response from
the initial duplicated suffix, **not accepted layer metadata**; the
validated exact response is `official-precinct-layer.json`.
No geometry has been
accepted or precinct map published. Seek explicit election-vintage
confirmation and a validated geographic/mode crosswalk before a separate
immutable mapped supplement; keep all overseas records separate.

All **39 actually advertised** general-election originals for **2024,
2022, 2020 and 2018** are now acquired in session
`files/precinct-expansion-sources/HI-{year}/`, including complete statewide
and county PDFs, precinct PDFs, Statements of Vote, media/summary text
and three recount documents. Per-file receipts and the combined
`files/hi-2024-2018-original-acquisition.json` preserve all URLs, final
URLs, bytes and SHA-256 values. Complete totals: **2024: 10 files,
23,490,452 bytes; 2022: 11 files, 21,400,912 bytes; 2020: nine files,
4,725,894 bytes; 2018: nine files, 5,083,966 bytes**. These acquired
historical originals have **not** been normalized or independently
reconciled; do not mark them reviewed or complete.

Do not reuse the 2026 text parser: **2024 uses BOM-marked UTF-16 CSV**,
**2022 uses BOM-less UTF-16LE CSV**, and **2020/2018 use UTF-8 CSV**.
The 2024/2022 `Format#1` metadata and headers omit a trailing empty
column present in every data row. Preserve this, rather than truncating
or rejecting valid rows. Original media candidate-record counts are
**17,944 / 9,050 / 9,497 / 8,030** in newest-first order; summary counts
are **182 / 255 / 226 / 148**. 2020/2018 distinguish absentee/early/
election columns; do not relabel them as 2026 Mail/In-Person.
The first acquisition attempt incorrectly assumed 2026 `FormatVersion`
text and stopped. The resumed attempt retained all completed PDFs
without redownloading and recorded the actual historical formats and
all 39 originals. Exact URL case differs by year; extract actual links
rather than guessing paths.

The full originals are now preserved reproducibly under
`data/precinct-source-acquisitions/20261105/HI-historical/`.
`scripts/archive-hawaii-historical-sources.py` verifies all original receipts
and native CSV record widths while preserving encodings, metadata,
multiline quoting and historical ballot-mode headers. The complete ZIP is
**38,713,054 bytes**, SHA-256
`9a0ce9f92d742d7bf8da230ca061bb6c86d603afff80ba746709110ccbc1ede1`,
containing all **39 originals / 54,701,224 uncompressed source bytes**
plus three provenance/checksum files. Independent proof verifies all
42 members/CRCs/bytes, every original receipt, immutable-overwrite refusal
and byte-identical archive/output reproduction **only from distributed
originals**, session `files/hi-historical-independent-validation.json`.
The historical collector tests cover both UTF-16 variants, quoted multiline
records, omitted trailing header fields, historical voting-mode columns
and rejection of truncated/ragged records.

Immutable source commit `e9607606c1b52ec93ae266ff69f563bb3c57fad5`
is published as tag/release `voter-precinct-hawaii-historical-20261105`.
Full remote redownload verifies the exact tag target, asset size/SHA-256,
all 42 members and CRCs byte-for-byte; proof:
`files/hi-historical-release-verification.json`.
Complete archive:
`https://github.com/hanshanley/margin_of_error/releases/download/voter-precinct-hawaii-historical-20261105/complete-hawaii-historical-originals.zip`.
All **184 collector tests** pass, including the multiyear ledger regression.
The source batch is registered locally, with **39** complete-download
links. All 184 collector tests, seven participation Node tests, four
build-time caucus checks and Astro check/build pass (zero errors/warnings,
five existing hints). The Pages preparer verifies all 94 complete
relocated assets and a **986,205,318-byte** artifact. Local desktop/mobile
JS/no-JS checks pass all 39 links, the four-year archive's exact URL and
review-pending label, full registry/ledger/renderer bytes, 2026 default,
Hawaii state red/blue fallback, zoom and failed-registry-fetch fallback;
proof: `files/hi-historical-local-browser-validation.json`. New build
assertions check every source-batch download, provenance/checksum link
and review-pending scope. At its required **pre-relocation build stage**,
the whole-site validator passes these assertions and again stops only
at the unchanged UK **23 vs. 16** card-count assertion. Historical
registration commit `99a45fa008b73930f432782e3f2544eaa21fad59`
was pushed as Hans (author and committer) and exact Pages run
**41968220027 succeeded**. Production proof
`files/hi-historical-live-browser-validation.json` passes the exact
registry/all-1,632-cell ledger/unchanged renderer bytes, all **39**
complete downloads, the four-year archive's exact URL and review-pending
label, desktop/mobile JS/no-JS, 2026 default, honest Hawaii state
red/blue fallback, zoom and failed-registry-fetch fallback.
Generic download labels accurately include PDF/text originals, not
only CSVs. No map renderer or pinned research export changed.
The multiyear source-batch ledger path preserves each actual election,
does not claim reconciled votes/turnout and does not override an existing
independently validated partial map with unreviewed official originals.
The official 2024 reference is also now completely acquired in session
`files/precinct-expansion-sources/HI-2024/boundary-reference/`:
**250** full native-coordinate polygons, exact advertised layer and
object-ID responses, and the complete original one-page metadata PDF.
All object IDs match with no pagination omission. The PDF explicitly
describes **May 2024** boundaries made for online voter registration and
aligned with the Esri Streets basemap. Its native spatial reference is
102202 / latest 3750. This acquisition is **not part of the 39-original
historical release**, not yet geometry/overlap/ballot-scope reviewed,
not joined, not published and not established for 2026.

Next: review each year independently and acquire its correct-year references. Continue
newest-first acquisition and distinguish acquired originals from reviewed
candidate totals, validated geometry and live maps. Hawaii is **not
complete**, and the other 2026 states/DC and all historical ledger cells
remain actionable.

## Rhode Island 2026: complete count review live; conservative reference map reviewed

The official Board of Elections archive page
`https://elections.ri.gov/elections/previous-election-results` returns HTTP
403 to both browser retrieval and Requests. This is **not unavailability**:
the actual official current interface is reachable at
`https://electionresults.ri.gov/results/public/rhodeisland/elections/2026StatewideGeneralElection`.
Its browser-discovered public endpoint
`https://electionresults.ri.gov/results/public/api/elections/rhodeisland/2026StatewideGeneralElection/data`
is completely acquired: **1,497,865 bytes**, 453 contests and 40 child
localities. Its exact original and receipt are cached under session
`files/precinct-expansion-sources/RI-2026/`, with the complete original
HTML, rendered interface, actual main bundle and all public-response receipts.

The native response explicitly advertises
`jurisdiction.mediaExportPath=RhodeIsland/export-2026StatewideGeneralElection.json`.
The actual main bundle explicitly sets CDN `/cdn/results`; it is not an
invented endpoint. The **complete** original
`https://electionresults.ri.gov/cdn/results/RhodeIsland/export-2026StatewideGeneralElection.json`
is cached as `official-media-export.json`: **11,103,548 bytes**, SHA-256
`5ad4afd10211821e360e4d5ca1714fedd318557e94a682dad8ba062af9a99b2f`.
It identifies **November 3, 2026**, Statewide General Election, created
`2026-11-05T01:03:12.7660788Z`, with complete statewide and 40-locality
originals, including every candidate's native precinct and voting-mode rows.
Do **not redownload this acquired snapshot**.

Exploratory evidence `exploratory-house-scope.json` verifies all seven
House candidate identities, names, native IDs, party values and total
counts against the separate public parent API. All totals and all **21**
candidate/mode totals reconcile across state, localities and native
reporting units. District 1 has Amo 111,639, Keenan 44,786, DeSouza 6,178,
write-ins 228; District 2 has Magaziner 120,586, Mellor 73,663,
write-ins 510. Preserve null native write-in party values; the API
represents these as an all-null party object with a display color.

There are **458 distinct native House reporting units**, **not 458
established residential precincts**. All source `isVirtual` values are
false, including four units in the separate **Federal** locality:
native IDs 1491/1497/1494/1500, Federal Precinct #1/#1S/#2/#2S.
Ordinary-town native rows also include limited-only clerk's-office
records, e.g. Barrington 0107. There are 41 locality/House comparisons
where native result-unit count differs from `precinctsParticipating`;
retain these rather than silently dropping records or calling them
geographic precincts. Same-locality candidate unit sets agree.
The parent API's statewide `ballotsCast=0` is **not** a usable turnout
numerator or proof of no participation; retain separate local facts
without substituting candidate totals or summing incompatible scopes.

The offline reviewer `scripts/review-rhode-island-precinct-results.py`
now preserves every House candidate/source identity, reporting status,
virtual flag and voting mode, including zeros and null write-in parties.
It rejects incorrect election/locality/candidate identity, missing or
duplicate native units, inconsistent repeated unit facts, malformed
counts, missing modes, and failures of independent API/state/local/native
candidate-mode reconciliation. Native row keys include contest identity;
unit counts are tracked separately rather than silently merging districts.
The **40** original locality ballot/registration observations remain
separate, with **all rates null**. Their raw totals are 364,082 ballots and
794,266 registered; these are not substituted for the parent's zero
ballots or presented as reconciled statewide/precinct turnout.

Immutable local review `data/precinct-source-reviews/20261105/RI/`
contains all five complete HTTP originals (native media, independent
public API and close-race response, discovery HTML and actual main
bundle), all **458** normalized House rows, 40 separate locality
observations and full receipts/audit/checksums. Complete ZIP:
**1,005,920 bytes**, SHA-256
`06dc93e688e524e45184dc6bccf83abbfdf849f5d8c487dcad912e857ee3ffa1`.
Independent proof verifies all 10 archive members/CRCs/bytes, every
original receipt and every native candidate/mode value in all 458 rows,
then reproduces identical output/ZIP **only from distributed originals**
and verifies immutable-overwrite refusal:
session `files/ri-2026-independent-validation.json`.
**197 collector tests pass**, including 13 focused Rhode Island cases.
Release tag **`voter-precinct-rhode-island-20261105`** targets data/parser
commit **`1b0227cf65efd04686620e2495cd858266b64f40`**. Full remote
redownload verifies the exact tag, ZIP size/hash and all 10 members against
the reviewed originals/output; session `files/ri-2026-release-verification.json`.
Site registration now adds the complete RI download and regenerates both
**1,632-cell** ledgers without accepting precinct geometry or rates.
Astro check, all seven participation JavaScript tests and the production
build (including four build-time caucus checks) pass. The whole build
validator, run **before** relocation, passes the changed participation
assertions and stops at the existing unrelated UK topic-card assertion
(line 1077: 23 actual versus 16 expected); it is not reported as passing.
Pages preparation verifies all 94 complete relocated assets and produces
a **986,205,928-byte** site. Desktop/mobile with and without JavaScript
pass exact registry/ledger/renderer bytes, all **40** download links and
correct RI review/original-batch labels. JavaScript checks also pass the
2026 default, source-matched RI state red/blue fallback, zoom and failed
registry-fetch behavior. Session proof:
`files/ri-2026-local-browser-validation.json`.
Exact site commit **`7d0db02061a3b6db2317ad478524ad73eb2286e1`**
deployed successfully in Pages run **41969630072**. Exact production
proof repeats every preceding desktop/mobile, JavaScript/no-JavaScript,
40-link, source-byte, default, state-color, zoom and failed-fetch check:
`files/ri-2026-live-browser-validation.json`. The complete 458-row count
review is live, not a precinct-map or rate claim.

### Conservative Rhode Island reference geometry: independent local proof

The actual RIGIS item `9104ca2e5e9b4cdb9985e8935ef2514d`, owned by
`URIEDC_RIGIS`, publishes `BND_Voting_Precincts_2022/FeatureServer`.
Its source description explicitly recommends the post-2022-redistricting
reference for **2022-2032** elections, warning that local changes remain
possible. It is **not relabeled a newly surveyed/certified 2026 snapshot**.
Full attribution/terms are retained: RIGIS, Election Data Services Inc,
each RI city/town Board of Canvassers and RI Department of State
Elections Division. All **416** native EPSG3438 and geographic features
match the complete native object-ID response and each other's attributes.
Every HTTP original and source receipt is preserved in session cache
`files/precinct-expansion-sources/RI-2026/boundary-reference/`.

`scripts/build-rhode-island-precinct-results.py` requires unique literal
town + four-digit native label identities, complete town sets, explicit
congressional-district agreement, nonvirtual scope and sound nonoverlapping
geometry. All Federal and literal LIMITED units are excluded, **not
allocated**, including Richmond's one nonzero limited-only Republican vote.
The map has **306 colored result units across 37 complete towns**.
Whole Cranston is withheld because boundary `0727` has no native return;
whole Providence is withheld because `28XX` is unassigned (Congress=0)
and absent from native returns. No suffix stripping, ID-prefix decoding,
borrowed precinct year, boundary clipping or vote allocation. All **458**
returns and **416** original boundaries remain downloadable; **152**
return rows are unmapped, including 40 LIMITED and four Federal units.
The 40 locality participation observations remain separate and all
precinct rates remain withheld.

The complete geometry audit finds **zero** overlap pairs above 1e-10
square degrees, with the established 1e-9-degree coordinate grid. Three
self-touching rings receive area-preserving repairs, all documented.
**206 collector tests pass**, including nine new conservative map cases:
complete sets, zero votes, nonzero excluded votes, source scope, incomplete
sets, House conflicts, unassigned areas, overlap and duplicate identities.

Immutable local snapshot `data/precinct-results/20261105-rhode-island-01/`
and complete ZIP **6,092,731 bytes**, SHA-256
`ec40b9fc967cdeb90356e0353184d79aa3ab07e4fd49f0fd9bf9b52b5a58ded9`.
Independent proof verifies all **27** archive members/CRCs/bytes, every
mapped native candidate/mode value, every original polygon, complete
eligible-town sets, all exclusions and zero overlaps, and reproduces the
entire output/ZIP **solely from distributed originals**. Preserve the
archive filename when reproducing: `index.json` intentionally records
`complete-rhode-island-2026-precinct-maps.zip`; renaming it changes index
and checksum bytes. Immutable overwrite refusal passes. Proof:
`files/ri-2026-map-independent-validation.json`.
Revision 01 was released at immutable tag
`voter-precinct-rhode-island-maps-20261105`, targeting
`46733eeeb532449ba54ed222fed92af7d2c5c554`. A complete remote redownload
matches all 27 members, the exact size/hash above and local originals.
Proof: `files/ri-2026-map-release-verification.json`. It was never registered
as a live map.

Pre-registration UI-contract review found that native result rows lacked
the renderer's `ballot_scope` presentation field. Immutable revision 02,
`data/precinct-results/20261105-rhode-island-02/`, adds explicit native
Election Day / Early Voting / Mail Ballots scope to every mapped feature.
Every count, candidate/mode value, polygon, exclusion and separate locality
observation is unchanged. The renderer is unchanged. All 206 collector
tests pass; all 27 revised archive members/CRCs/bytes and original receipts
pass, and distributed-original-only byte reproduction and overwrite refusal
pass again. Revision 02 ZIP: **6,098,657 bytes**, SHA-256
`a348107161caf1f50d0952e61d05d94d1edef9d91dbb13e2e85cc4e50f559c95`.
Proof: `files/ri-2026-map-02-independent-validation.json`.

Revision 02 release tag `voter-precinct-rhode-island-maps-20261105-02`
targets **`f1ba1e85307ab3a4b730f473327c6b47d61944a4`**. Its complete
remote redownload passes exact tag, size, hash, all 27 archive members/CRCs
and byte comparisons: `files/ri-2026-map-02-release-verification.json`.
The registry now pins this verified revision, with attribution/terms and
audit links. The additional participation-download label is deliberately
generic: RI has separate **locality** statistics, not precinct denominators.
The map renderer remains byte-identical.

Local publication checks pass: Astro check, seven participation tests,
production build and four build-time caucus checks. The whole build
validator reaches only the unchanged unrelated UK assertion at line 1077
(23 cards versus 16); it was run before Pages relocation, not after.
The Pages preparer verifies all **94** complete relocated assets and a
**986,209,496-byte** site. Desktop/mobile with and without JavaScript pass
all **43** full download links, exact registry/1,632-cell ledger/unchanged
renderer bytes, source geometry, all 306 precinct keys/counts/colors,
selection provenance/scope, zoom out/in, state fallback, honest withheld
participation rates and failed-registry-fetch fallback. Proof:
`files/ri-2026-map-02-local-browser-validation.json`.

Exact site commit **`7d2cef1a5ebeac5a36a220a00d01c96e8b428b1d`**
deployed successfully in Pages run **41971059459**. The production proof
passes every preceding desktop/mobile, JavaScript/no-JavaScript, 43-link,
source-byte, 306-precinct color/count/key, selection, zoom, state-fallback,
withheld-rate and failed-fetch check:
`files/ri-2026-map-02-live-browser-validation.json`. Only after that proof,
the registry marks RI **live-verified partial** and the regenerated ledger
records partial publication. RI and nationwide coverage are not complete.
The live-status follow-up **`0a581da4faa433918b86f2160c0977040df66504`**
also deployed successfully in exact run **41971899185**. Its exact production
registry/ledger bytes and unchanged renderer pass
`files/ri-2026-map-02-exact-status-live-proof.json`; the completed map
interaction suite was not unnecessarily repeated.

Next: continue remaining newest state/year cells. Connecticut 2026 has
actual full public EMS originals and the supported complete voting-district
CSV export in `files/precinct-expansion-sources/CT-2026/`, not just leads.
Election **108**, November 3, 2026, has captured API versions **52337**
and **52338**. The native export has **27,578** candidate/party/mode rows,
including **2,967 House rows**, a separate **722-row** registry/voted
section and a separate ballot-mode section. All House rows' five native
mode counts sum to their final counts. Do not mistake later sections for
candidate rows or use the summary CSV's stripped place labels as IDs.

Count reconciliation is **not complete**: the full export includes North
Canaan House votes **660 Democratic + 550 Republican + 34 Working Families**
that both captured API versions still report as zero, a **1,244-vote**
summary discrepancy. Six native place-label collisions and three literal
report/lookup label disagreements also require explicit source resolution;
do not merge duplicate labels or invent precinct aliases. The supported
XML export returns a 26-byte incomplete stub; actual TXT/CSV downloads
succeed. Raw receipts, all originals and exact diagnostics are retained,
including `source-structure-and-discrepancies.json`. The public native
voting-district report is acquired through the application's own
`GetVotingDistrictValues` / `Default.aspx?action=VotingDistrict` export,
not scraped county vote allocation. Separate 2024/2022/2020/2018/2016
official originals have now been acquired: **14 full HTTP originals each**,
with actual election IDs **91/80/54/31/1** respectively.
The complete reports include both candidate and separate registry/mode sections.
Native CSV quoting is nonstandard even in candidate names (for example
unescaped quoted nicknames), not just multiline ballot-question text;
strict CSV errors are recorded and all original bytes are preserved.
The 2022 report has **16 negative candidate Unknown-mode adjustments**;
2016 has **40** and one **-2 absentee-total** observation. They remain
negative, flagged source values, never clamped, silently treated as missing,
or approved for participation rates. Native `CO` values such as 0/1 are
not established fusion-parent IDs; do not infer candidate grouping from them.
The complete-original archive and independent receipt/byte/reproduction
checks are finished and live (exact proof below). Next resolve the summary discrepancy,
native ID collisions, original name quoting and fusion scope with supported
source-scoped exports before any result/rate/map normalization.

## Connecticut six-election complete-original batch

Offline builder: `scripts/archive-connecticut-election-sources.py`.
Snapshot: `data/precinct-source-acquisitions/20261105/CT-2016-2026-02/`.
It retains **115 full HTTP originals / 46,014,001 uncompressed bytes**:
2026 has 45 originals including both API versions and application/export
provenance; 2024/2022/2020/2018/2016 each have 14. Separate versions are
never overwritten. All-office candidate/party/mode reports contain
**177,082 rows** and separate registry/voted sections contain **4,482
observations** across the six elections. These are native observations,
not deduplicated precinct identities or demographic participation estimates.

The complete archive `complete-connecticut-2016-2026-originals.zip` is
**3,434,133 bytes**, SHA-256
`bf1756dd874eda8809339b7daccc41a8bbb70955475a8535d868e24854d2f439`.
Independent proof checks all **118** archive members/CRCs/local bytes,
all 115 original receipts and unmodified cache bodies, every exact
election identity and candidate/registry/mode section count, and all
**57 negative native values**. It reproduces every file and ZIP byte
**solely from distributed originals**, and verifies overwrite refusal:
`files/ct-2016-2026-independent-archive-verification.json`.
The 26-byte broken XML response is retained as a failed original attempt,
never mistaken for a full result dataset. Nonstandard name/question
quoting and every unreconciled count/identity issue above remain explicit.
All **213 collector tests** pass, including multiline sections, missing
counts, mixed election years, negative adjustments, native malformed quotes,
changed receipts and metadata-only archive refusal.

The coverage builder now carries an explicit source batch's pending
participation status instead of calling acquired-but-unreconciled originals
not acquired. Stronger existing published participation (including NC) is
preserved. These six captures remain **originals-review-pending**, not
reconciled counts, validated maps or rates.

Hans data commit **`9ca28444bf05924da3aa4d10234280da48de46df`** is available
at immutable tag **`voter-precinct-connecticut-originals-20261105`**.
The full remote archive redownload passes exact tag target, asset size,
SHA-256, all 118 members/CRCs/local bytes and all 115 original receipts:
`files/ct-2016-2026-remote-byte-verification.json` and
`files/ct-2016-2026-remote/remote-tag-and-asset.json`.
Only after that proof was it added as a third source batch, increasing
the server-rendered complete-data downloads from 43 to **44**.
Local publication passes Astro check, seven participation tests, the production
build and four build-time caucus checks. The whole build validator still stops
only at the unchanged unrelated UK assertion (line 1077, 23 cards versus 16),
before relocation. The Pages preparer verifies all **94** relocated originals;
the site is **986,214,134 bytes**. Bounded desktop/mobile with and without
JavaScript passes all 44 full downloads, the exact new ZIP and provenance
links, all 1,632 ledger cells, unchanged renderer, 2026 default and CT state
result fallback without invented precincts or rates:
`files/ct-2016-2026-local-browser-proof.json`.
Hans registration commit `70ae13643cc915fbb7c061de98386dc7a4fc1aec`
deployed successfully in exact Pages run **41973265542**. Production passes
the same bounded desktop/mobile with and without JavaScript checks, all
44 complete downloads, three immutable CT provenance documents, all 1,632
ledger cells, unchanged renderer, 2026 default and honest CT state fallback:
`files/ct-2016-2026-live-browser-proof.json`. Exact run metadata:
`files/ct-2016-2026-exact-pages-run.json`. The full originals are live;
this adds **zero** CT maps or precinct participation rates.

Independent 2026 identity follow-up exercised the application's actual
`pollingplaces: "<native ID>("` export filter, preserving the request
payload and response receipts in
`files/precinct-expansion-sources/CT-2026-scoped-native-ids/`.
Hartford ID **3331** returns **76 bytes / header only**, not explicit zero
votes. ID **3739** returns **623 bytes / six rows**, four House rows:
680 Democratic, 17 Republican, 11 Green, zero write-in. Non-House offices
still leak through the nominal congressional filter. These captures do
**not** resolve the full report's two nonzero same-label groups: do not
assign the leftover group to 3331 by elimination. Continue supported
single-town voting-district exports and native office/polling relationships;
retain all captured originals in the next count-review package.
Public ArcGIS discovery is also captured in
`files/precinct-expansion-sources/CT-2026-reference-discovery/`.
The first query returns seven leads, including Enfield and Plainville
municipal services, not verified statewide 2026 precinct geometry.
Check official service provenance, declared vintage, literal IDs and full
town sets before using any shape. UF/VEST has explicit 2016/2018 reconstructed
reference candidates; their 2020-Census-based shapes have documented
election-year corrections, not authority to map 2026. They remain leads,
not acquired maps.

## Florida 2026: Monroe reviewed counts; Palm Beach county-only originals

Offline builder: `scripts/review-florida-monroe-precinct-results.py`.
Snapshot: `data/precinct-source-reviews/20261105/FL-2026-MON/`.
Official identity: **MON / election 4109 / November 3, 2026 General**,
`https://enr.electionsfl.org/MON/4109/Reports/`. Six complete originals
retain both source HTML pages, both all-office CSVs and both full PDFs:
**1,483,944 uncompressed bytes**. The native precinct CSV has **1,551
candidate/option rows**; all **71** independently exported county-summary
candidate/options reconcile across **28 contests**. The House contest is
the literal `Representative in Congress Dist 28`: **99 candidate rows /
33 distinct complete precinct names**, REP **17,423**, DEM **14,328**,
NPA **367**, total **32,118**. Shared polling-place names remain separate
precincts; native full labels remain the identities, not fuzzy matches.

All **1,216** native suppressed mode fields remain missing in normalized
records, with their original dash strings retained. Unsuppressed mode
vectors reconcile; suppressed groups are explicitly not testable and are
never reconstructed from residuals or assigned zero. Separate county
HTML snapshots agree on **32,506 ballots / 54,704 registered**, displayed
**59.42%**, and **33 / 33** reporting. These are native unofficial
**Monroe County** counts and a source-displayed percentage, not precinct
denominators or demographic turnout. The current supervisor homepage
instead reports **55,151 active registered voters as of November 5**;
do not substitute a different snapshot/definition into election turnout.

Complete ZIP: `complete-florida-monroe-2026.zip`, **282,651 bytes**,
SHA-256 `992684207ebbd291a19f071a22c9b1a0afe2e3e7adaa46432a9d92d85d2617d0`.
Independent proof checks every receipt, all **12** ZIP members/CRCs/local
bytes, every original all-office candidate total, the 33 complete House
vectors, every suppressed field, original-only reproduction of **every
output and archive byte**, and immutable overwrite refusal:
`files/florida-monroe-2026-independent-archive-proof.json`.
All **231 collector tests** pass, including wrong county/year, changed
receipts, missing/suppressed counts, duplicate/name-collision identities,
missing candidate vectors, source-scope changes and independent total/mode
disagreements. Hans source commit
`2f26a01abe473bec14b5a601b7795c18a35af92a` is pinned by immutable tag
`voter-precinct-florida-monroe-20261105`. The complete remote asset
redownload passes exact tag target, size, SHA-256, full local-byte equality,
all ZIP members/CRCs and all six original receipts:
`files/florida-monroe-2026-remote-byte-proof.json`.
Only after that proof is it registered as a full-count source review,
increasing complete-data links from 44 to **45**, with the server-rendered
label explicitly **Monroe County only**. Astro check, seven participation
tests, the production build and four build-time caucus checks pass.
The whole validator reaches only the unchanged unrelated UK assertion
(line 1077, 23 cards versus 16), not a whole-suite pass.
The Pages preparer verifies **94 byte-identical relocated files** and a
**986,215,113-byte** site. Bounded desktop/mobile with and without JavaScript
passes all **45** identical complete downloads, explicit county-only scope,
all 1,632 ledger cells with exactly one changed FL cell, three immutable
provenance files, unchanged renderer, no overflow, 2026 precinct/margin
defaults and exact FL state-result fallback without invented precincts:
`files/florida-monroe-2026-local-browser-proof.json`.
Hans registration commit `6acb600633b342a82c6f60d0321b0d6e6bccb87f`
completed exact Pages run **41975524305** successfully. Its verified run SHA
and subsequent four-configuration production checker both pass:
`files/florida-monroe-2026-exact-pages-run.json` and
`files/florida-monroe-2026-live-browser-proof.json`.
No newer UI deployment superseded that proof.
This is **one county, not statewide Florida**, with
**zero new maps or precinct participation rates**.

The supervisor's current official domain is `www.votemonroeflkeys.gov`,
not the older guessed hostname. Its declared
`/Where-to-Vote/Precinct-Details-Demographics` page explicitly lists
precincts **1–33** and several **NEW 2026** polling-place changes.
Polling locations establish neither polygon geometry nor stable electorates.
The declared `/Where-to-Vote/Maps` page's actual HTML lists a current
precinct PDF explicitly dated **September 2, 2025**, at
`https://mcgis4.monroecounty-fl.gov/MCGIS/Maps/MC_Voting_Precincts.pdf`.
Its declared shapefile catalogue is
`https://mcgis4.monroecounty-fl.gov/MCGIS/Data-Download/MCGIS_Data_Download.html`
(search `Precincts`). The actual **11,533,295-byte / nine-page** PDF,
**42,562-byte** catalogue HTML and declared **6,447,598-byte** complete
`SF/Voting_Precincts.zip` have now been acquired successfully with receipts
in `files/precinct-expansion-sources/FL-2026-MON-reference/`.
The original ZIP passes CRC and has eight full members. Its DBF has
**153 polygon records / 33 distinct literal precinct numbers 1–33**,
including multiple islands per number; native metadata and ZIP members
are explicitly dated **December 23, 2025**, not 2026.
The source projection is NAD83(2011) Florida East, US survey feet
(EPSG:6438); do not treat native coordinates as longitude/latitude.
These are acquired **2025 current-reference** originals, not established
2026 boundaries. Do not copy candidate counts onto every repeated island
record or infer applicability from matching 33 IDs. Offline inspection also
finds **three invalid original rings** (native records 12, 18 and 116,
precincts 12, 13 and 33); no automatic repair, dissolve, vote allocation or
2026 publication was performed. Full diagnostic:
`files/florida-monroe-2025-current-reference-offline-geometry-audit.json`.
Seek explicit election
validity before a separately audited grouped-geometry supplement.
The text-only fetch initially omitted the main map content, so inspect
original HTML before concluding absence.
A direct homepage request returned **403**, retained with its
full body/receipt in `files/precinct-expansion-sources/FL-2026-MON-reference/`;
the ordinary fetch tool can read the site. Never turn that access difference
into a claim that boundaries do not exist. Seek an explicit 2026 reference
and independent election-defined precinct ballot/registration records.

Palm Beach has independently acquired complete **PAL / election 4131**
county summary HTML/CSV/PDF plus report-index and ArcGIS definition originals
in `files/precinct-expansion-sources/FL-2026-PAL/`. Its native `/Precincts`
endpoint returns **404** with an explicit unpublished-material response;
the reports index advertises summary exports only. The **814 reporting
units** shown by its summary are not precinct candidate returns. Three
CivicPlus map/June-2026 ZIP/PDF requests returned **403 challenge HTML**,
not valid geometry. Both alleged binary bodies are **5,662 bytes of HTML**.
The county-linked ArcGIS item `85e93905c13b43debf37a6cba372ba05` has a
June-2026 modified timestamp but explicitly describes **2023–2024**
precincts; do not relabel it as 2026. Its `PRECINCTS/FeatureServer/0`
service is only a lead pending election-vintage and full scope checks.
Old declared S3 `county.js` / `election.js` URLs return 404 XML.
All successful and failed original bodies/receipts are retained. Continue
official browser/download/GIS alternatives and additional Florida counties;
never allocate Palm Beach county totals into precincts or call the Monroe
subset statewide complete.

## Missouri 2026: Christian County complete originals and native-group review

The official Christian County election-information page declares a
**November 3, 2026** unofficial election section with three complete PDFs:
`https://www.christiancountymo.gov/offices/county-clerk/election-information/`.
Actual linked originals, all independently confirmed by every PDF page's
literal county/election/date identity, are:

- `https://www.christiancountymo.gov/wp-content/uploads/RUN6Election_Summary.pdf`
  (**83,071 bytes / three pages**).
- `https://www.christiancountymo.gov/wp-content/uploads/UNOFFICALP00100_to_P10000A_Election_Summary.pdf`
  (**221,106 bytes / 54 pages**, retaining the source's filename spelling).
- `https://www.christiancountymo.gov/wp-content/uploads/UNOFFICIALSOVC_Nov_3_2026_21_14_26.pdf`
  (**158,194 bytes / 59 pages**).

All three full PDFs and the **94,179-byte** official HTML index were
acquired with successful exact URL/status/size/SHA-256 receipts.
Original cache: `files/precinct-expansion-sources/MO-2026-CHRISTIAN/`.
The offline, network-free
`scripts/review-missouri-christian-precinct-results.py` validates source
receipts, declared links, every page's native election identity, the
complete two-page unit pairs and independently exported candidate matrices.
The complete archive preserves **all four originals / 556,550 bytes /
116 PDF pages**, all extracted page text, 27 normalized House vectors,
separate native participation records, audit and checksums.

The source reports **26 geographic/combined reporting groups plus one
countywide `ABSENTEE` bucket**, not 27 independent residential precincts.
Combined names stay literal, including
`1. E. BENTON/3. BRUNER` and
`4. CHADWICK 11. GARR 12. LH 16. SL 18. OF 25.SEN`.
No combined total is split among component precinct numbers.
Every House District 7 vector independently matches its `Normal` and
`Absentee` statement rows and the separate county summary:
**REP 23,419 / DEM 10,307 / LIB 883 / total 34,609**.
All units independently sum to **35,258 ballots / 70,148 registered**;
county source-displayed **50.26%** remains a separate native observation.
Registration repeated across statement modes is counted **once per
native group**, never summed across `Normal`, `Absentee` and `Total`.

The countywide absentee bucket has **5,635 ballots**, **5,577 House votes**
and **zero native registered voters / `N/A`**. Geographic groups exclude
that bucket. Their displayed source percentages are retained as native
fields, **not full precinct turnout rates**, and absent residential
absentee allocation is not reconstructed. All **27 rates are withheld**;
no geometry, demographic turnout, statewide completion or new map is claimed.
The normalized candidate audit is explicitly **House District 7 only**;
all other offices remain present in the complete original reports.

Snapshot: `data/precinct-source-reviews/20261105/MO-2026-CHRISTIAN/`.
Archive: `files/complete-missouri-christian-2026.zip`,
**450,107 bytes / 10 members**, SHA-256
`3dc52eb82d035c2c0cf0f7724476530cf62cf7c52124ab72cf16402f426828db`.
Independent verification checks every member, checksum, original receipt,
all 116 extracted pages, independently parsed per-unit/per-mode House
vectors, native participation and totals. Original-only reconstruction
reproduces **every snapshot file and the entire ZIP byte-for-byte**;
immutable overwrite refusal passes:
`files/missouri-christian-2026-independent-archive-proof.json`.
The collectors suite passes **275 tests**, including **44 new Missouri
regressions** covering combined/absentee identities, missing/duplicate
units and pages, wrong county/year/party/election, repeated registration,
source percentages, independent mismatches and changed/failed originals.

Hans source commit `b30aa24882968e614cb9a89e4812a154f0de18ab` is pushed
and pinned by immutable tag `voter-precinct-missouri-christian-20261105`.
The full `complete-missouri-christian-2026.zip` remote redownload passes
exact tag target, asset size, SHA-256, full local-byte equality, all
10 ZIP members/CRCs, all four original receipts and three immutable
provenance files:
`files/missouri-christian-2026-remote-byte-proof.json`.
Only after that proof is it registered as a **Christian County only**
complete-data link, increasing full downloads from 45 to **46**.
Astro check passes with zero errors/warnings and five existing hints;
all seven participation tests, the production build and four build-time
caucus tests pass. The whole validator reaches only the unchanged unrelated
UK assertion (23 cards versus 16, line 1077), not a whole-suite pass.
The Pages preparer verifies **94 byte-identical relocated downloads**;
the prepared site is **986,216,216 bytes**. Bounded desktop/mobile with
and without JavaScript passes all **46** identical complete downloads,
explicit Christian and Monroe county-only scope, all 1,632 cells with
exactly one changed MO cell, immutable provenance, unchanged renderer,
no overflow, 2026 precinct/margin default and exact MO state fallback
without invented precincts:
`files/missouri-christian-2026-local-browser-proof.json`.
Hans UI commit `9c9325c119aeb22334f97356620dfc5ac8493ed3` is pushed.
Its exact Pages run **41976901201** completed successfully, with the run's
SHA checked before the production checker ran. Live desktop/mobile with
and without JavaScript passes the same four configurations, all **46**
complete downloads, county-only scope, one MO cell among 1,632, immutable
provenance, unchanged renderer and exact state fallback:
`files/missouri-christian-2026-exact-pages-run.json` and
`files/missouri-christian-2026-live-browser-proof.json`.
This publication is finished; do not repeat its acquisition or release.
Keep MO 2026 `complete=no`; this is one county, not statewide Missouri.
Seek explicitly election-applicable boundaries and residential absentee
definitions while continuing the remaining 2026 state/DC queue.

## Nevada 2026: Clark declared aggregate app and original precinct GIS acquired

The actual official
`https://www.clarkcountynv.gov/government/departments/elections/26g-info`
page identifies **November 3, 2026** and links its unofficial county
election-night results. Its `Statement of Vote` and CVR entries currently
have **no link**; this is a bounded current-page observation, not an
absence claim. Historical aggregate results have a separate real native
selector at
`https://elections.clarkcountynv.gov/electionresultsTV/results.aspx`;
inspect that form's actual election and report choices before guessing files.
The linked county app
`https://elections.clarkcountynv.gov/ElectionResults_NV/EnrEng/EnrMain`
has been fully acquired (**467,327 bytes**, HTTP 200). It identifies
`2026 General Election` / `Unofficial Results`, shows county registration
**1,528,706**, and has county contest selection, but no precinct,
download or export string in this exact HTML. Do not turn county contest
totals into precinct records. Inspect actual declared form/data routes.

All six complete source bodies and exact receipts are retained in
`files/precinct-expansion-sources/NV-2026-CLARK/`: general index,
election-night index and app, historical aggregate selector, GIS index,
and the GIS index's actual
`https://mapsrv.clarkcountynv.gov/pub/crel/crel-shp.zip`.
The original **3,529,197-byte ZIP / 100 members** is HTTP 200 with passing
CRC, despite the ordinary web tool returning 502 at that same link.
Its `gisdata/crel/shapefil/precinct_p.shp` has **1,015 records** and native
numeric `PREC`, `CONGRESS` and other district fields.
Members and metadata sync/modification date are **March 25, 2026**;
metadata creation date is **February 12, 2019**, not an election date.
Native projection is NAD83 Nevada East FIPS 2701, US survey feet.
The native `PREC` values are all nonnull and unique: **1,015 distinct IDs**,
range **1000–7930**. Native congressional-district counts are **323** in
district 1, **289** in district 3 and **403** in district 4. Metadata
inspection found maintenance dates but no explicit general-election
applicability text. Election applicability and topology remain unapproved;
no join or map is approved from a modified timestamp.

The captured historical selector has **140 choices**, including a blank
choice. Its newest actual election is `26PE` / **2026 PRIMARY ELECTION
(06/09/2026)**, followed by `24G` / **2024 GENERAL ELECTION (11/05/2024)**.
There is **no 2026 general choice in this captured selector**. Do not invent
or submit `26G`. Native category `3` is `STATEMENT OF VOTE (RESULTS BY
PRECINCT)`; category `4` is turnout data by voting method. Valid fresh
ASP.NET form submissions, preserving native hidden state, successfully
selected `24G`, `22G` and `20G` with category `3`. Complete index responses
are saved in `files/precinct-expansion-sources/NV-CLARK-HISTORICAL/`.
They declare **200**, **200** and **264** PDF/Data report links respectively.
All **664** declared report bodies are now acquired: **48,901,936 report
bytes**, with HTTP 200, native PDF/text format checks and exact source
receipts. Seven complete native selector/form/index originals are also
retained. The new offline `scripts/archive-clark-historical-sources.py`
checks exact native selected election/category, the complete PDF/Data
pair inventory and every original receipt; it preserves suppressed votes,
repeated registration and malformed native nickname quoting without
normalizing candidate identities or inferring turnout.
Actual full-source validation found that PDF election/date/county
headers occur on the first page, not every continuation page. Validation
now requires the exact first-page identity and rejection of conflicting
repeated identities, recording headerless continuations rather than
pretending they repeat election headers. Native blank final pages are
retained only after checking no images/drawings and an entirely white
full-resolution rendering; blank first/interior pages and textless marked
pages fail validation.
Full-source validation and independent offline reconstruction now pass.
The immutable snapshot is
`data/precinct-source-acquisitions/20261105/NV-CLARK-2020-2024/`:
**671 originals / 49,214,821 original bytes / 675 ZIP members**.
The complete archive is **29,238,218 bytes**, SHA-256
`aade65d7ae37f3d9c9cde568ac15779d06cb4c5315b3ba8ac8c9a997b406b562`.
Native 2024/2022/2020 PDF pages are **3,691 / 4,368 / 8,108**; Data
records are **100,496 / 119,636 / 333,352**. There are **7 / 14 / 3**
verified blank endings, **14 / 18 / 20** strict CSV quoting failures,
**13,397 / 22,131 / 30,123** privacy-suppressed candidate fields and
**189 / 238 / 579** Totals records whose turnout exceeds registration.
These are record/field counts across contests, not distinct precincts,
rates or reconstructed suppressed values.
The independent checker re-parses native declarations with BeautifulSoup,
checks every original and receipt, verifies CSV counts without counting
the heterogeneous footer, and reconstructs every snapshot file and the
entire ZIP byte-for-byte using only distributed originals.
Proof: `files/nevada-clark-historical-offline-reproduction-proof.json`.
**308 collector/coverage tests pass**. Source commit
`96b735f02828b24cdb845851132c1450ab45eb55` is pushed as Hans, author and
committer, without attribution trailers. New immutable release
`voter-precinct-nevada-clark-historical-20261105` targets that exact commit.
The entire published archive was redownloaded and matched every local byte,
size and SHA; four pinned source metadata files also matched.
Remote proof: `files/nevada-clark-historical-remote-release-proof.json`.
Public registration passes local validation, not yet live verified:
exactly one new complete-download link (**47 total**) and one changed
ledger cell (**NV 2022**) among 1,632. NV 2020/2024 map rows, NV 2026,
all other cells and the renderer remain identical. County-only source
participation metadata must not overwrite independently mapped status.
No candidate reconciliation, new map or new participation rate is claimed.
The final production build passes all **308** collector/coverage tests,
the **7** participation unit tests and normal build checks; the release-aware
Pages preparer verifies **94** existing byte-identical relocated downloads.
Prepared site size is **986,218,808 bytes**. Bounded desktop/mobile with
and without JavaScript passes all **47** complete-download links, explicit
Clark-only scope, prior statewide 2022 originals retained, no overflow,
2026 precinct/margin default and exact NV state fallback without invented
precincts. Local proof:
`files/nevada-clark-historical-local-browser-proof.json`.
Temporary preview helper is stopped. Hans UI commit
`6816cc057344a096ff7349d9aa57a58ea81062bb` deployed successfully in exact
Pages run **41980202677**. The source-matched production checker passed:
all **47** identical complete downloads across desktop/mobile with and
without JavaScript, explicit Clark-only scope, no overflow, unchanged
2026 precinct/margin default, exact Nevada state fallback, and no
invented precincts. Only NV 2022 changes among all 1,632 ledger cells.
Proofs are `files/nevada-clark-historical-exact-pages-run.json` and
`files/nevada-clark-historical-live-browser-proof.json`. This publication
is done; do not repeat its completed live suite. It adds no maps, rates,
or statewide Nevada completion.
The native election selector reaches elections
before 1964, providing a concrete later historical route without replacing
the remaining 2026 work.

Washoe's actual homepage and `results/2026data.php` report index were
acquired in full with receipts, along with its linked public dashboard:
`https://electionresults.washoecounty.gov/`.
The dashboard requires normal JavaScript/Blazor rendering. Waiting for
`networkidle` timed out; an independent DOM-ready browser navigation
succeeded with no page errors or failed requests. It displays **General
2026**, **Washoe County - General Election 2026 Unofficial Results**, update
**11/4/2026 6:20 PM**, and a real `Download PDF` link under
`https://gis.washoecounty.us/webservices/gisdataservice/ElectionResults/resultpdf/`.
That is a declared county-summary export, not precinct results. The actual
2026 report-index statements currently linked are explicitly **primary**
reports. Personal mail-ballot, signature-cure and in-person voter-list
downloads are deliberately excluded; they are not aggregate participation
substitutes. Raw originals and the separately labeled derived browser
observation are in `files/precinct-expansion-sources/NV-2026-WASHOE/`.

The dashboard's actual declared full county-summary PDF is now acquired:
**553,410 bytes / 23 pages**, SHA-256
`ac8d43ad5b41e41ccb1ac6ddac54cb37630f00b979c44ba2067e4330ad35c63b`.
Its source generation timestamp is **11/4/2026 6:13:35 PM**, separately
from the app's later 6:20 PM update. Native county participation is
**191,830 / 329,777**, displayed **58.17%**; House CD2 candidate votes
are **189,752**, not ballots. Early Vote **54,762**, Election Day
**35,133**, Mail **101,935** are native county modes, not residential
precinct assignments. No precinct turnout or map is inferred.

The actual acquired Clark GIS index declares
`https://mapsrv.clarkcountynv.gov/pub/crgeodb/Election_Archive.zip`.
The previously inferred `/pub/crel/crelgeodb/` path is wrong; do not retry
it. The exact declared archive is fully acquired: **8,604,501 bytes /
209 ZIP members**, passing CRC, SHA-256
`97cd8af08bd142263a5c956c1b818be42f5703d51e71fa87ed32fe24ae06bd2e`.
A proper OpenFileGDB reader inspected its **31 actual layers**. Precinct
layers are named `prec0506_p`, `prec1990_p`, `prec2000_p`, `prec2002_p`,
`prec2004_p`, `prec2006_p`, `prec2008_p`, `prec2010_p`, `prec2012_p`,
`prec2013_p`, and `precinct2010_p`, with native `PREC` and district fields,
EPSG:3421, and **897–1,311** features per layer. The reader reports no
layer/dataset metadata. These native names are historical leads, not
proof of exact general-election applicability, and none establishes a
2020/2022/2024/2026 reference. The archive's November 2, 2026 modification
date must not become a modern boundary vintage. Derived catalog:
`files/precinct-expansion-sources/NV-2026-CLARK/derived-election-archive-layer-inventory.json`.

The Silver State endpoint reached from `https://results.nv.gov/` redirects
to `silverstateelection.nv.gov` and the ordinary web tool encounters a
real additional-security challenge. Pursue the legitimate official
county aggregate/result/export alternatives; do not describe the state
as permanently unavailable or download personal voter lists as a substitute.
The Clark historical originals are now independently reconstructed,
published and production-verified as recorded above; preserve the acquired
Washoe PDF and native GIS catalog without treating county summaries or
1990–2013 reference names as modern precinct coverage. Continue official
2026 precinct-statement alternatives in parallel. Independently reconcile
native units and election-applicable boundaries before mapping; package
all originals before registry/publication.
NV 2026 remains incomplete and unchanged in the public ledger.

## Colorado 2026: actual state results and Douglas map application

The full official
`https://www.sos.state.co.us/pubs/elections/resultsData.html`
index identifies **2026 General Election** and declares
`https://results.enr.clarityelections.com/CO/127407/`.
The actual state and Douglas (`CO/Douglas/127427/`) result requests return
**HTTP 403**; an ordinary browser navigation to Douglas also returned a
CloudFront 403, not candidate data. The county elections homepage returned
403 separately. Preserve these access results and pursue legitimate
official alternatives, not a bypass or a claim that returns do not exist.

The declared Douglas district/precinct map application
`d20d97824bee4291bbd2505443bcb8a3` and its full **121,176-byte** configuration
were acquired successfully from ArcGIS. Its actual web-map data source is
`1f8e398b9e204897832bc689e95c9459` on `dougco.maps.arcgis.com`.
The item title is `Douglas County District/Precinct Maps Application`;
its March 2026 modified date is not itself an election applicability
statement. Inspect the declared map's layer definitions and vintage before
any join. All original bodies and exact receipts, including failed HTML,
are retained in `files/precinct-expansion-sources/CO-2026-DOUGLAS/`.
No new Colorado map, precinct counts or turnout is claimed.

The actual web-map layer has now been followed to
`https://services.arcgis.com/seTexOicoRXDvRsJ/arcgis/rest/services/PRECINCTS_View/FeatureServer/0`,
and its item `3de6839224584b1fae43ed814bec6a2e`. Full original metadata
is acquired with receipts (**16,991** and **1,902 bytes**). The service
declares `Query`, maximum **1,000** features, native `PRECINCT`,
`STATE_PREC`, congressional/state districts and archival date fields.
Item title is `Voter Precincts`, description `Douglas County Voter
Precinct Boundaries`; neither gives explicit 2026-general applicability.
Complete native object-ID and geometry acquisition now passes:
**216 features / 216 distinct nonnull PRECINCT IDs**, exactly matching
the separately acquired official object-ID set without transfer-limit
truncation. Full GeoJSON is **2,526,078 bytes**, SHA-256
`114e58a73665ebdcf521a43aea46fd0269b4e1dba61e9883ee04fec8cdfce053`;
the official ID response is **802 bytes**. Every native field and original
geometry is retained. The item gives no explicit election applicability.
Seek actual general-election precinct returns and independent applicability
evidence; do not map or infer turnout from this reference alone.

## DC 2026: native plurality precinct map and separate provisional participation

The actual DCBOE homepage declares its `2026-General-Election` results app.
All **18 complete original bodies / 4,609,414 bytes** are retained with exact
source receipts: full **10,011-row CSV**, XML, PDF, election metadata,
144-precinct inventory, citywide counts and participation, native precinct
and ward map responses, and the original embedded-reference JavaScript.
This is not a metadata-only download. Do not reacquire those originals.

The map uses the explicitly **non-RCV Council-chair plurality contest**,
not the delegate contest's first ranks. All **144 precincts** reconcile
candidate-by-candidate between CSV and independently requested native map JSON,
then to citywide JSON and XML: **161,936 DEM, 10,629 REP, 2,013 write-in**.
OVER/UNDER VOTES are excluded by native record identity, never counted as
Republican candidate votes despite source citywide PartyCode quirks.
Independent CSV, XML and voter-summary totals agree on **185,086 ballots**
and **457,371 source-registered voters**. Reported registration fractions
are explicitly provisional election-night shares, not final turnout,
citizen/resident denominators or group-specific participation.
Eleven precincts have a **+1 ballot** difference against this local contest's
candidate + over + under accounting: 10, 15, 27, 28, 45, 55, 59, 60,
63, 71 and 72. Preserve and flag those differences; never allocate or repair.
The source update is **November 4, 2026, 04:36:21.283 UTC**;
outstanding ballots remain, with the source receipt deadline November 13.

Metadata explicitly selects `OCTO_VotingPrecinct_2019.json` for this election.
The full literal TopoJSON is extracted from native statistics module **834**
using the existing Acorn parser, without executing the downloaded bundle.
This is an election-selected reference, **not newly surveyed/certified 2026
boundaries or proof of stability across elections**. Its 144 complete IDs
join uniquely. The official browser's unmodified geometry independently
confirms three source overlap pairs: **1/130, 79/80 and 80/132**.
Following the established ND policy, exclude ambiguous strips from both
precincts, never assign them, and preserve whole-precinct counts, original
reference and excluded-area mask. All 144 retain nonambiguous geometry;
no topology repair is performed. Validate zero remaining distinct-precinct
overlaps above the audited `1e-10` square-degree numeric tolerance.

Immutable snapshot: `data/precinct-results/20261105-dc-01/`.
Complete ZIP: **1,461,521 bytes**, SHA-256
`7c181a8b03255bd26aded22b2ea91e60211386d3e766c91173920c56d96b6d2d`.
All **329 collector tests** pass, including wrong election/RCV rejection,
independent count mismatch, duplicates/missing precincts, over/under identity,
suppression, retained ballot-accounting discrepancies, signed arcs, exact
reference sets, geometry ambiguity and executable-export rejection.
Independent proof now passes: every original and receipt is rehydrated from
all **27 ZIP members**; all 144 decoded shapes exactly match captured
native-browser features; every snapshot and the ZIP reproduce byte-for-byte.
Session proof: `files/dc-2026-offline-reproduction-proof.json`.
Sources are committed/pushed as Hans at
`3f76e06af13cc1344f34da09be159eae042745f0`. Immutable release
`voter-precinct-dc-maps-20261105` was downloaded in full; its exact tag target,
entire ZIP bytes/SHA and pinned raw index/map/audit match. Remote proof:
`files/dc-2026-remote-release-proof.json`.
Registry appends one `live_verified_partial` supplement after the production
proof below, retaining all prior
47 complete downloads and bringing the total to **50**. Only **DC 2026**
changes among 1,632 ledger cells; it remains incomplete.

Local desktop/mobile with and without JavaScript now pass exact source-matched
144-precinct margins/counts/fills, separate participation and provenance/
accounting warnings, year switching, exact Nevada state fallback, 2026
precinct/margin default, all 50 identical download links and no overflow.
Source-matched fit checks exposed the nationwide **256x** zoom cap preventing
DC urban precinct selection from reaching its actual geometry. The only
renderer change raises that bounded maximum to **16,384x**; selection now fits
actual precinct bounds. Button zoom, real wheel, post-fit double-click and
real mobile two-pointer pinch are verified, preserving all exact count/colors.
An existing browser regression file now tests the actual DC feature fit.
Local proof: `files/dc-2026-local-browser-proof.json`. Seven targeted JS tests,
the normal build and Pages preparer pass; **94** existing bulk downloads remain
byte-verified and the prepared site is **986,222,920 bytes**. The previously
documented unrelated UK whole-validator card-count mismatch is not fixed or
reported as a passing whole suite.

The DC UI is committed/pushed as Hans at
`43a0d0d42899dcb192e92c9d30157b58320d8d51`. Its exact Pages run
**41982827435** completed successfully. Unqueried production registry,
ledger and renderer bytes match that exact commit; the new source-matched
desktop/mobile JS/no-JS browser proof also passes against production.
Proofs: `files/dc-2026-ui-exact-pages-run.json` and
`files/dc-2026-live-browser-proof.json`. This evidence permits the DC live
flag and corresponding ledger publication update, not statewide completion.
The flag/ledger publication must also receive exact-SHA deployment and
production-byte/browser verification before its bounded publication todo
is closed. Never call these provisional fractions final turnout.

The final DC flag/ledger commit is
`7a99695511f44ab7b6254be8c2cb7f88fed09284`. Its exact Pages run
**41983686641** also succeeded; unqueried production registry, ledger and
renderer bytes and all four source-matched desktop/mobile JS/no-JS checks
passed. Proofs: `files/dc-2026-final-exact-pages-run.json` and
`files/dc-2026-final-live-browser-proof.json`. The bounded DC publication
task is done. Do not rerun it in place of Massachusetts/new acquisition.

## Maryland 2026: native general reference link is an unexpanded template

The actual official `https://elections.maryland.gov/elections/2026/index.html`
declares unofficial general results and
`https://elections.maryland.gov/elections/2026/election_data/index.html`.
All three full index/result/data pages were acquired with HTTP 200 receipts.
The data index currently lists **primary** candidate exports only.
Its visible `State Precinct Reference for the 2026 General Election (Excel)`
label is not proof of a workbook: the actual href contains the literal
unexpanded `{*GENERAL_ELECTION_CODE*}` placeholder. Following that exact
declared link returns **14,548 bytes of HTML with HTTP 200**, not XLSX.
The acquisition correctly rejected its missing ZIP/XLSX signature.
Retain the failed original body/receipt, do not invent a replacement
election code, and do not claim a general-election reference was acquired.
Original cache: `files/precinct-expansion-sources/MD-2026/`.
Continue actual county aggregate/precinct reports and later state updates;
neither primary returns nor source-index labels become 2026 general data.

Following actual declared links, the **2026 general governor and all-eight-
district House reports** are now fully acquired, followed by **all nine**
declared governor/House county breakdowns: **11 full general result HTML
originals / 215,876 bytes**. Exact receipt URLs, native HTML and every
county breakdown are retained, not metadata-only downloads. Their native
refresh timestamp is **11/04/2026 11:25:23 PM**.
The governor report shows **1,969 / 1,979 election-day precincts reported**
and **1,862,847 candidate votes**, not ballots cast. Native provisional
counts are **NR**, not zero. These reports are state/district/county
aggregates; none supplies precinct candidate rows for a map.
The actual declared `using_election_data_instructions.html` is acquired
in full (**35,079 bytes**). Its explicit statement about all-mode precinct
reporting concerns the **2020 general election**; do not extend that to
2026 or older elections without source-specific checks.
The actual county-board directory is acquired. Legitimate next routes
declared there include Anne Arundel's board, `https://www.777vote.org/`
for Montgomery, and Frederick's elections page. Anne Arundel's original
homepage and its declared county general-result page are acquired.
Montgomery's declared `https://www.777vote.org/` fails the older Python
TLS stack, but ordinary curl with normal certificate verification succeeds
and redirects to `https://mcg.montgomerycountymd.gov/elections/index2.html`.
Its actual county general-result page is acquired. Frederick's declared
homepage timed out after 60 seconds with ordinary curl; this is an access
observation, not proof that no county data exists.

Montgomery's actual **Voter Count Report, 4:00 p.m. (Excel)** declaration
now yields a real **13,946-byte XLSX**, not the state's broken reference
template. The native `2026GG Voter Turnout` sheet has **72 data rows /
71 unique precinct IDs**, six native affiliation columns, and a cached
footer. The duplicate source code is now identified as **05-06**:
Excel rows **19/20** are `05-06 WHITE OAK MIDDLE SCHOOL` and
`05-06 White Oaks MS`. Their six native affiliation values are identical:
DEM **417**, REP **72**, GRN **1**, WCP **0**, UNA **6**, OTH **131**.
The cached footer equals the raw row-column sums **including both rows**;
it is not independently established unique-person participation.
The reason for the duplicate remains unresolved; preserve both complete
native labels and all values and do not silently deduplicate, pool, or interpret
this partial-day workbook as final/all-mode participation, registration,
candidate results, or demographic rates. The actual precinct-reference
index is also acquired, but its declared jurisdictional PDFs are under
**2022**, not independent 2026 applicability evidence.
The state election index's Box folders are explicitly **Polling Place
Plans and Canvass Schedules**, not result exports or verified precinct
boundaries; do not relabel them.

The actual state directory's Howard County homepage is now acquired
with normal verified requests: it redirects to
`https://www.howardcountymd.gov/boards-commissions/board-elections`
(**349,259 bytes**). Its declared 2026 general-result page is acquired:
`https://elections.maryland.gov/elections/2026/general_results/gen_results_2026_by_county_14.html`
(**65,305 bytes**, SHA-256
`f4268847471bbde3e2ba659fe887f891872fe3cd6fc11b671f79f83d82a7f9dd`).
It is a county aggregate, not precinct returns. The actually declared
`election-results-monthly-registration-reports` index is also acquired
(**304,761 bytes**); its data-file declarations currently concern 2024,
and its monthly 2026 registration declarations stop at September.
Neither establishes November 2026 precinct ballots or denominators.
Three complete new HTML bodies and receipts are retained in the Maryland
cache; no extra map, rate or statewide-completion claim is made.
Continue legitimate remaining county-board declarations or actual state
general-data updates, preserving broken/primary-only link evidence.

## Massachusetts 2026: complete city originals; mode and OCR checks remain

The state publication-policy URL
`https://www.sec.state.ma.us/divisions/elections/voting-information/announcing-certifying.htm`
returned **HTTP 403 / 883 bytes** through an ordinary request. Preserve its
original body and receipt; do not treat that access failure as evidence that
local results are unavailable or guess exports. Independent city alternatives
were acquired normally, without overwriting the failed response.

Boston's actual
`https://www.boston.gov/departments/elections/unofficial-election-results`
is acquired in full (**392,645 bytes**). Its native HTML has citywide/district
candidate summaries, not a verified combined precinct export.
Followed exact declarations, not invented filenames:
`https://www.boston.gov/sites/default/files/file/2026/11/20261103-Election-Night-Reporting-FAQs.pdf`
(**62,623 bytes / two pages**) and
`https://www.boston.gov/sites/default/files/file/2026/11/UNOFFICIAL-CENTRAL-TABULATION-RESULTS-11.03.26.pdf`
(**4,097,653 bytes / 288 pages**).
The FAQ explicitly distinguishes the **275** precinct machine tallies,
central-tabulation early/absentee ballots, and later combined online counts;
it lists provisional, overseas, hand-counted and later-arriving ballots
outside initial reporting. The acquired precinct-column PDF is explicitly
**CENTRAL TABULATION**, not combined/all-mode precinct results.
Never add its ballots to an already combined report, represent its margins as
all-mode margins, or infer final participation from candidate counts.

Worcester's actual
`https://www.worcesterma.gov/elections/election-results` index
(**69,813 bytes**) declares the November 3, 2026 unofficial report at
`https://www.worcesterma.gov/election-results/20261103.pdf`.
The complete **1,588,318-byte / 60-page** PDF and receipt are acquired.
All 60 pages have zero extractable native text; this is a scanned source,
not evidence of no precinct counts. Preserve complete page images and
use local OCR followed by source-image/count reconciliation. Tesseract
is not installed; the existing macOS Swift/Vision toolchain is available.
The rendered first page visibly reports **120,952 registered** and
**144,608 ballots**, exceeding registration. Do not silently drop ballot
style rows, repair the source, or publish a turnout fraction from it.
Establish full page/precinct/contest scope and reconcile all originals first.

Cache: `files/precinct-expansion-sources/MA-2026/`. Five successful complete
originals total **6,211,052 bytes**, plus the retained failed policy body;
each has an exact URL/status/size/SHA-256/retrieval receipt.
No Massachusetts map, rate, source-review completion or statewide completion
is registered from these acquisitions. Next execute local OCR/count review,
follow Boston's actual declared results archive for combined precinct exports,
and seek independently established exact-election reference applicability.

### Boston central-only mapped package: source and live UI verified

The declared archive was followed in full. Its only 2026 PDF declaration is the
September primary, not a combined general-election precinct export. The complete
Worcester report has now been rasterized at 240 dpi and locally OCRed on **all
60 pages**, using Apple Vision accurate English revision 3, correction disabled.
Text alternatives, confidence, normalized bounds, native PDF/image/output/helper
hashes and engine provenance are preserved. Structure: four three-page summary
groups, followed by four twelve-page precinct SOV groups; overall, election day,
early voting #1 and early voting #2. Governor counts are now independently
reconciled as described below; the other contests remain unverified. Do not rerun
unchanged OCR, discard alphabetic split precincts such as Ward 4 Precinct 2A,
turn blank cells into zeros, or infer unique voters from ballot-style counters.
The unexplained 144,608 / 120,952 ballot/registration anomaly remains unresolved.
The actual first-page governor **ticket-party labels** are visually checked:
Healey/Driscoll DEM, Minogue/Oliver REP, James/Kittredge IND. The separately
reconciled Worcester governor counts do not approve any other contest.

The actual official November 3 polling-locations page embeds Experience
`30b1667d4997442795ae4096b825bc19`. Normal browser navigation acquired its
actual selected webmap `58d8d0ed47c047dfa8bbe9c96390b848` and layer item
`8ae9900f3a394baeb490642f62c5f85b`. Despite the legacy title
`Boston_Precinct_Polling_Locations_-_Preliminary_Election_2026_Layer`,
layer 0 is **esriGeometryPolygon**, not polling points. The selected popup
explicitly states Tuesday, November 3, 2026. Preserve the contradictory older
Fall 2025 webmap metadata: this is an **app-selected reference**, not newly
surveyed/certified boundaries or proof of stability across elections.
Full object-ID inventory and native GeoJSON agree exactly on all **275**
objects; every redundant ward/precinct field agrees. All geometries are valid,
with zero distinct-precinct overlaps above `1e-10` square degrees. No repairs,
clipping or allocation are used. Genuine harbor/island extent remains intact.

`scripts/build-boston-precinct-results.py` now strictly reads all 18 native
governor slabs from the complete 288-page central-tabulation report, including
the native label/count fonts' 0.36-point bbox difference. All **275 unique**
precincts independently reconcile candidate/write-in/blank accounting and the
exact city footer: **25,030 DEM; 3,534 REP; 811 IND; 53 write-ins; 378 blanks;
29,806 contest-scoped central-tabulation ballots**. Of these, **252** precincts
have candidate votes; **23** retain actual reported zeros with null margins,
not manufactured colors. These are **central advanced-processing ONLY**, not
combined Election Day results, all-mode margins, statewide results, unique
voter counts or turnout. Never allocate the separate combined city HTML.
No registration denominator, participation rate, demographic rate or winner
claim is produced.

New immutable source directory:
`data/precinct-results/20261105-boston-central-01/`.
Complete archive: `complete-boston-2026-central-tabulation-precinct-maps.zip`,
**4,790,833 bytes**, SHA-256
`2e7e59b1878508deeb85641323bdba1c31471854157921ab0cd9525addb9aa1a`.
Includes **35 complete originals / 8,196,853 uncompressed bytes**, all exact
source receipts, the failed state-policy response, original app metadata,
complete native polygons, all candidate reporting rows, audit/checksums and
the full unverified OCR derivative. Session image paths are normalized to
basenames without altering OCR lines; original and normalized OCR hashes are
retained. Only the three visually checked ticket-party labels are approved.
All inputs needed for offline reproduction are inside the archive.

Independent verifier `files/verify-boston-2026-package.py` reads source headers
sequentially and counts through independent PDF column interiors, checks every
count, source hash and exact native geometry, and rebuilds from **archive-only**
rehydrated inputs. The entire resulting ZIP is byte-identical.
Proof: `files/boston-2026-offline-reproduction-proof.json`.
**352 collector tests pass**, including **23 new Boston regressions** for
native fonts, election/office/mode, missing/fractional counts, complete inventory,
footer, duplicates, unknown/inconsistent IDs, transfer truncation, invalid or
overlapping geometry, zero counts, and explicit party evidence. Seven relevant
Node tests pass. No whole-validator success is claimed.

Source committed/pushed as Hans at
`2b7785f38184428d3e27ea07c4ba1af417976656`. Immutable release
`voter-precinct-boston-central-maps-20261105` targets that exact commit.
Full remote asset redownload, size/SHA and tag-to-source checks pass:
`files/boston-2026-remote-release-proof.json`.
The registry appends this explicitly scoped source; its live flag is set only
after the exact UI deployment and production checks described below.
Optional `participation_available: false` omits its nonexistent participation
download and any participation-statistics ZIP claim; all prior sources retain
their original downloads. All prior **50** complete downloads remain byte/link
preserved; Boston's complete ZIP and all-row CSV bring the total to **52**.
All **1,632** ledger rows remain; only **MA 2026** changes and stays incomplete.

Astro check has zero errors/warnings (five existing hints), the seven relevant
Node tests, normal build, and Pages preparer pass. All **94** existing relocated
bulk assets remain byte-verified; prepared site size is **986,227,371 bytes**.
New `files/check-boston-2026-publication.py` passes on the prepared local site
for desktop/mobile x JS/no-JS, checking every one of the **252** actual colored
precincts against source counts/margins/exact red-blue fills; the **23** reported
zero rows are retained but not colored. It verifies central-only/city-only and
legacy-reference warnings, correct selection labels/source links, no fabricated
participation link, all prior 50 downloads, actual precinct fitting, zoom buttons,
desktop wheel/double-click, real mobile two-pointer pinch, state fallback,
2026 defaults, year switching and no overflow/page errors. Renderer bytes are
unchanged. Proof: `files/boston-2026-local-browser-proof.json`.

UI commit `c5f2cfef130a2184e3b2f880d82a6cb09dd7b9cf`, authored and committed
as Hans, deployed successfully in exact Pages run **41986198749**.
`files/boston-2026-ui-exact-pages-run.json` verifies the exact SHA and success.
The source-matched production suite passes all four desktop/mobile x JS/no-JS
configurations, all 252 actual colors/counts/margins, source labels/scope,
precinct fitting/zoom and real touch gestures, 2026 defaults, historical
switching, state fallback, all 52 downloads and prior 50-link retention.
Proof: `files/boston-2026-live-browser-proof.json`. Unqueried production
registry, ledger and unchanged renderer also match local bytes exactly:
`files/boston-2026-ui-unqueried-production-proof.json`.
Only after these checks is Boston marked **live_verified_partial**, with only
the MA 2026 publication cell changing; all 1,632 cells remain incomplete.
The final flag/ledger commit
`aa45cd25515a530c690c40f386f8c9392790c833` also deployed successfully in exact
Pages run **41987244820**. Final unqueried production bytes and all four browser
configurations passed again:
`files/boston-2026-final-exact-pages-run.json`,
`files/boston-2026-final-unqueried-production-proof.json`, and
`files/boston-2026-final-live-browser-proof.json`.
Boston's bounded publication is complete; do not repeat this finished suite
instead of acquiring new sources. Massachusetts and nationwide coverage remain
incomplete.

Worcester's actual governor SOV panels are now visually identified on PDF
**15/16, 27/28, 39/40 and 51/52** for the four modes. The overall
15/16 pair has **62 precincts**, preserving **4-2A and 7-5A**, with a native
footer **31,811 DEM; 13,750 REP; 2,038 IND; 69 write-ins; 662 blanks**.
Full-page OCR merged vertical numeric runs and missed cells, particularly in
sparse early modes; those incomplete matrices were rejected, not repaired.

### Worcester governor count review: source/release and production UI verified

The bounded second reading is now complete. Independently detected actual source
grid borders yielded **1,260** candidate/write-in/blank cells. Every original
eight-panel raster is pixel-identical to a fresh 240-dpi render of the complete
PDF. The canonical parser also reproduces every parent crop from original PDF
pixels and every tightened crop from unchanged parent grayscale pixels.
Apple Vision and independent, entirely local RapidOCR readings are preserved.
No source data was uploaded to an OCR service. Rectangular all-ink cropping,
upscaling and white padding are recorded; no inpainting, component removal,
letter deletion, numeral substitution or missing-to-zero conversion was used.

Both engines' **35** missing/noninteger or conflicting cells were explicitly
read on native-image crops, including actual printed zeros. All **62** actual
identities were read in every one of the four panel pairs, preserving **4-2A**
and **7-5A**. All four five-field native city footers reconcile, and all **310**
per-precinct candidate/write-in/blank equations satisfy
**overall = Election Day + early voting #1 + early voting #2**:

| Source reporting group | DEM | REP | IND | Write-ins | Blanks |
|---|---:|---:|---:|---:|---:|
| Overall | 31,811 | 13,750 | 2,038 | 69 | 662 |
| Election Day | 20,054 | 10,344 | 1,415 | 51 | 441 |
| Early voting #1 | 6,547 | 1,837 | 319 | 12 | 120 |
| Early voting #2 | 5,210 | 1,569 | 304 | 6 | 101 |

These are **unofficial November 3 governor contest counts for Worcester CITY
ONLY**. The four source groups are not summed together; overall already includes
the other three. Their accounting totals are not unique voters, statewide
results, final turnout or demographic participation.

Canonical script: `scripts/review-worcester-precinct-results.py`.
Snapshot: `data/precinct-source-reviews/20261105/MA-WORCESTER/`.
Complete ZIP: `complete-worcester-2026-governor-count-review.zip`,
**81,047,687 bytes**, SHA-256
`b801bba010f18826af0043a723d819d4a9ce88fb76e930f190fd2dc4ac5ad009`.
Includes **248 normalized precinct/group rows**, **17 complete source captures
/ 39,195,208 raw bytes**, all receipts, the full original 60-page PDF, all 60
native rasters and full OCR, both independent cell readings, all crop manifests,
identity evidence, explicit judgments and the canonical reproduction script.
The nested `complete-inputs.tar.gz` contains **2,946 complete input files /
91,944,306 raw bytes**, not metadata-only placeholders; `inputs.json.gz` records
every byte length and SHA-256. Session-local JSON path identifiers are normalized
to basenames without altering OCR observations; both hashes are retained.

`files/verify-worcester-2026-package.py` independently compares all 248 exported
rows/counts/margins/source panels against the prior native reconciliation,
verifies every source/input checksum, and runs the archived parser using
**archive-only** inputs. The rebuilt complete ZIP is **byte-identical**.
Proof: `files/worcester-2026-offline-reproduction-proof.json`.
All **366 collector tests pass**, including 14 focused Worcester regressions
for split units, actual zeros, ambiguous/missing OCR, explicit judgments,
duplicate/missing inventory, footer defects and mode discrepancies.

The official `Your Vote Counts` page and its declared two-page November 2026
voter guide were acquired in full; neither resolves the card counter. The
ordinary state advisory request returned 403; Boston's card instruction page
returned 503. Those complete failure bodies and receipts remain archived.
The **144,608 / 120,952** ballot/registration anomaly is still unexplained and
unused. Never divide the ballot counter by three or infer turnout.

The city's actual elections page labels its declared Experience
`c1bfa1552cd34985b53d4ba5bcb5b56d` **2025 - Municipal Election Map Dashboard**;
the acquired item/config corroborate that election. It is not 2026 authority.
Independent official alternatives are now acquired: the actual
`/elections/candidates` map index, complete ward/precinct map
`/elections/document-center/wp_all.pdf` (**11,798,024 bytes**), and complete
House/Senate maps (**9,943,179 / 14,760,104 bytes**). The ward map explicitly
prints **June 10, 2026**, with boundaries effective December 31, 2021; the
House map prints January 19, 2022 and the Senate PDF metadata is February 2023.
The June 2026 polling list includes additional split labels absent from the
62-row source: do not infer missing returns, combine split shapes or allocate
counts into them.

The actual city GIS page also declares Worcester Atlas Experience
`503920c4ab1b4404bee9dce73114538d`. Its acquired config selects webmap
`644498610e3c493787e07c0cbc6ac4b7`; the acquired webmap declares
`Administrative_Boundaries_and_Elections/FeatureServer/5` as
**Ward-Precinct Boundaries**, item `f14e934ee09441b6b7acc72667a9ebb9`.
These two newest webmap captures are in the separate
`MA-2026/worcester-reference-followup/` cache, not retroactively included in the
completed count archive. Next acquire that actual layer/item/full native ID
inventory and geometry, audit split identities and November 2026 applicability.
No Worcester geometry or participation file is published from count accounting.

Source is now committed/pushed as Hans at
`509f4ba98a3fb8802d0c313f1a1d2c8f35863a42`.
Immutable release `voter-precinct-worcester-counts-20261105` targets that exact
source commit. Its full remote ZIP was redownloaded; size/SHA-256 and exact
tag-to-source checks pass:
`files/worcester-2026-remote-release-proof.json`.
No original or immutable asset is replaced.

The published UI adds only the city/office-scoped count-review download; all
**52** existing complete downloads remain, for **53** total. The registry's
mapped snapshots, Boston's live flag/MA shard, and renderer are unchanged.
Ledger regeneration still has **1,632 incomplete cells**; only the **MA 2026
notes** change to retain both Boston's mapped subset and Worcester's separate
count review. A regression prevents the count-only review from replacing the
existing map or its separately scoped participation metadata.
All **367** collector tests and seven relevant Node tests pass. Astro check
has zero errors/warnings and the same five existing hints. The normal build
and Pages preparer pass; all **94** relocated bulk assets remain byte-verified,
and the prepared site is **986,228,851 bytes**.
`files/check-worcester-2026-publication.py` passes on the prepared local site
for desktop/mobile x JS/no-JS, verifying all 53 downloads, exact retention of
the prior 52, city-and-governor-only wording, no false county/participation
label, unchanged registry/map renderer, preserved Boston map and 2026 defaults,
unqueried static bytes, no overflow/errors and the notes-only ledger change.
Proof: `files/worcester-2026-local-browser-proof.json`.
UI commit `e8631f8168a7f5589df6bc7ff274b07464fb8987` passed exact Pages run
**41990181780**, including build and deploy. Unqueried production registry,
ledger and renderer bytes match the committed sources. All four production
desktop/mobile x JS/no-JS checks pass, retaining all **53** complete downloads,
Boston's **252** colored precincts and central-tabulation-only warning, working
zoom and the 2026 defaults. Proofs:
`files/worcester-2026-exact-ui-deployment.json` and
`files/worcester-2026-live-browser-proof.json`. This verifies the count-download
publication, not a Worcester map or participation rate.

The separate Atlas follow-up now contains the complete actual layer/item,
native object-ID query and GeoJSON, each with full receipt. The **371,500-byte**
geometry contains **66 unique IDs / 66 unique precinct labels**, exactly
matching the independent native ID inventory, with no transfer truncation,
invalid geometries or overlaps above `1e-10` square degrees.
It is **not** an approved join: native result-only **7-5A** is missing from this
reference, while reference-only **2-6A, 3-3A, 3-5A, 4-2B and 10-4A** have no
separate count rows. All native properties and exact mismatch/geometry
diagnostics are retained in
`files/worcester-2026-native-atlas-reference-audit.json`.
Do not treat the service's November 2026 edit timestamp as proof of election
applicability, merge split areas into a broader result row, infer five zero
returns, or manufacture a 7-5A shape. This bounded reference/scope follow-up
remains open; it does not block the complete, explicitly unmapped count download.

## Washington 2026: all county originals acquired; House count review

The official Secretary of State elections index declares the current VoteWA
portal. Its actual public 2026 election and all **39** declared county APIs
are acquired, together with **both complete published Excel exports for every
county (78 originals)**, native metadata, full receipts and ZIP integrity
checks. Empty native `precincts` arrays and `includePrecinctResults=false`
do not establish missing precinct counts: the published workbooks contain
populated **Precinct Results** sheets.

The official precinct-shapefile index explicitly declares both **2026 General**
boundary packages, created October 15, 2026: **8,119 base records** and
**13,774 split records**, across all 39 counties. Complete original ZIPs,
metadata, projection, inventories and schemas are retained. Native records
are not presumed unique reporting units; inspect county/name/St_Code/CD/LD
and complete base/split identity universes before dissolving or joining.

Canonical parser: `scripts/review-washington-precinct-results.py`.
It verifies original-byte receipts and declared county/report bindings, exact
election and production/general-election scope, both workbook schemas and
complete identity inventories. Each accepted House contest's detailed counts
sum exactly to its county summary, every native summary candidate
ID/name/literal-party/count agrees, all explicitly reported counts agree
between exports, and candidate votes + overvotes + undervotes equal explicit
single-seat contest ballots for each reporting row. All **391 collector tests**
pass, including **24 focused Washington cases**.

**36 counties / 5,804 House reporting rows pass**. Keep **King** withheld for
duplicate House reporting identities and **Jefferson / Walla Walla** withheld
for House ballot-accounting discrepancies. These are source-specific open
issues, not permission to repair, deduplicate or allocate counts. Some
All Results count cells are blank while the detailed export explicitly
supplies counts: preserve the original blanks and use only separately explicit
detailed counts after independent summary/API checks, never missing-to-zero.
Source party whitespace is retained literally in validation; surrounding
whitespace is ignored only for party classification. This matters for
Okanogan's explicitly Democratic John Duresky label.

Other-office review is independent: Pacific's Timberland library measure and
Wahkiakum's commissioner contest do not sum to their county summaries; full
diagnostics and originals remain without discarding separately verified House
contests. No participation rate or demographic inference is approved.
King's official index announces its first precinct release November 6 at
4 p.m.; do not mistake a county summary for a precinct file.

The first, now superseded, complete count package is
`data/precinct-source-reviews/20261105/WA/`. Its ZIP is
`complete-washington-2026-count-review.zip`, **109,998,129 bytes**, SHA-256
`dd51f894522ba53cd7ad392babb4c234c768a1d2bf0d2eb19365423fcd46bd82`.
Both full input archives are below GitHub's individual-file limit: the largest
committed file is **64,248,062 bytes**. Independent full input/checksum and
78-workbook CRC verification passes. The archived parser rebuilds the complete
ZIP **byte-identically using archive-only inputs**.
Proof: `files/washington-2026-offline-reproduction-proof.json`.
Validated House candidate totals are **932,493 Democratic + 671,234 Republican
+ 6,640 other = 1,610,367** across the 36 accepted counties; these are neither
statewide totals nor unique voters. The corrected package below is canonical.

The first source package was committed/pushed as Hans at
`f219c127274d75a0d0532be52844a8f09467652d`. Its complete remote ZIP and exact
release-tag target were verified:
`files/washington-2026-remote-release-proof.json`.
**Do not use that first package's derived margin sign:** before UI integration,
the site-convention check found R-minus-D instead of the renderer's D-minus-R.
All original files and candidate counts are unaffected. The first release is
explicitly marked superseded; no asset was replaced.

The corrected canonical count version is
`data/precinct-source-reviews/20261105/WA-02/`, ZIP
`complete-washington-2026-count-review-02.zip`, **109,998,400 bytes**, SHA-256
`9dfe1086140b217a23842f0b5bad5601e05f74ebac07962916ed7315c9d11a84`.
The parser now explicitly uses **100 x (D - R) / all candidate votes**;
focused regressions cover both party leads. The map builder independently
rejects any normalized margin inconsistent with the underlying counts.

### Washington mapped supplement: verified in production

Canonical builder: `scripts/build-washington-precinct-results.py`.
Complete literal name or explicit precinct-number **plus CD** sets match in
15 counties. Alternate passing fields must assign every label to the same
native St_Code; contradictory complete crosswalks are rejected. Only parts
of one explicit reporting/CD/St_Code identity are dissolved, counting votes
once. No padding, alias, prefix decoding or guessed boundaries are used.

Pierce has malformed native geographic rings and remains wholly withheld.
The other **14 counties** yield **1,533 mapped reporting-unit geometries**,
**1,499** with nonzero candidate results. The source has **294** overlapping
reference pairs. As in the already-reviewed North Dakota treatment, ambiguous
strips are excluded from **both** affected precincts, never assigned to either.
Full original boundaries, excluded-strip GeoJSON and area fractions are
retained; counts describe the entire reporting unit, not just its unambiguous
displayed area. Every output geometry is valid and no mapped overlap remains
above `1e-10` square degrees.

Corrected mapped snapshot:
`data/precinct-results/20261105-washington-03/`.
Complete ZIP `complete-washington-2026-precinct-maps-03.zip`,
**116,917,377 bytes**, SHA-256
`46f7a1a8e251bb740e51da255fcb31ee92a7b29fb1bfed79fcf4cff7d5ce4c9c`.
It retains the complete corrected count review, all **5,804** normalized
House rows (JSON and UI-compatible CSV), all originals, native boundaries,
unmatched records, geometry/count audits and the standalone build toolchain.
Independent verification checks every mapped candidate count and margin
against its actual source vector, every CSV value and geometry, preservation
of the entire count package and an **archive-only byte-identical mapped ZIP
rebuild**. Proof: `files/washington-2026-map-offline-reproduction-proof-03.json`.
All **398 collector tests** pass.

The corrected count archive-only proof also passes, including all original
inputs, all 78 workbook CRCs and every derived D-minus-R margin:
`files/washington-2026-offline-reproduction-proof-02.json`.

Both corrected packages are committed/pushed as Hans at
`4aaa45e0a40ee16c66922637f795fe6fa9fa4ff7` and published as immutable releases
`voter-precinct-washington-counts-20261105-02` and
`voter-precinct-washington-maps-20261105`. Both full remote ZIPs match their
recorded bytes/SHA-256, pass CRC checks and bind to that exact source commit.
Proof: `files/washington-2026-corrected-remote-release-proof.json`.

The registry now appends only the pinned Washington mapped supplement, with
its complete original-backed ZIP and all-5,804-row CSV. It explicitly declares
`participation_available:false`, avoiding an invented statistics download.
All **53 existing** download links remain unchanged; there are now **55**.
All **1,632** state/year cells remain incomplete, and only **WA/2026** changes
to `published_partial` after actual production verification.

The seven focused Node tests, normal build and Pages preparation pass.
Astro check has zero errors/warnings and the same five existing hints.
All **94** relocated bulk assets remain byte-verified; prepared site size is
**986,233,002 bytes**. `files/check-washington-2026-publication.py` passes on
the prepared local site for desktop/mobile x JS/no-JS: independently computed
D-minus-R signs, all **1,499** exact path fills/margins/counts, all55 download
links and unchanged prior53, actual selection-fit, zoom buttons, desktop wheel
and post-fit double-click, mobile real two-pointer pinch, year switches,
exact Nevada state fallback, honest excluded-strip/Pierce caveats, no inferred
participation, preserved 2026 defaults and no overflow or JS errors.
Proof: `files/washington-2026-local-browser-proof.json`.

UI commit `330751cc1b88242a6efa1aa54672f8224cdfa8fb` was pushed as Hans.
Its exact Pages run **41995134972** succeeded, including build and deploy.
The same full four-mode checker passes against unqueried production URLs:
all 1,499 exact colored paths, counts and independently derived signs,
all 55 complete download links with the previous 53 retained, selection-fit,
buttons, wheel, post-fit double-click, real mobile pinch, year changes,
defaults, fallback, no overflow/errors and no inferred participation.
Proofs: `files/washington-2026-exact-ui-deployment.json` and
`files/washington-2026-live-browser-proof.json`.
The registry now marks this supplement `live_verified_partial`.

The separate county-summary review now reconciles **all 39 counties**, using
both workbook Summary Results sheets and every native API candidate
ID/name/literal-party/count. Each complete county vector is accumulated only
after validation. Their roll-up exactly equals every state candidate vector:
**1,409,690 D + 805,088 R + 9,234 other = 2,224,012** House candidate votes.
This does not approve any new precinct joins or turnout fields. King's
unexplained contest-ballot gaps and Jefferson/Walla Walla's zero reported
ballots remain explicit accounting warnings, distinct from candidate-vector
reconciliation. Canonical session proof is
`files/washington-2026-county-summary-audit-02.json`; do not use audit-01.

## Nationwide 2026 county results: complete district originals acquired

The user explicitly permits counties instead of precincts, or both. Preserve
precinct priority where reviewed shapes exist; never label a county fill as
a precinct or mark precinct coverage complete because counties are available.

`scripts/acquire-house-county-results.py` follows the **435 actual declared
district election IDs** from the archived national House response, rather than
guessing endpoints. All 435 original responses and byte/status/URL/SHA receipts
are retained in `files/national-2026-county-breakdowns-20261105/`.
**418** pass strict production/election/state/district scope checks.
All **17 Pennsylvania** bodies explicitly set **`test_data:true`**; they
remain archived and withheld, not relaxed into production data.
The 406-test collector suite passes, including eight acquisition regressions.

The provider mixes geographic levels. Among accepted sources, 379 expose
County alone; the others include Town, independent City, Parish, Planning
Region, Township, Borough, House District, State and Overseas. These are not
additive layers. In particular use Connecticut's current planning regions
instead of obsolete counties, Virginia's independent cities as county
equivalents, and Alaska's explicit borough/census-area references without
pooling overlapping House districts or statewide totals. Preserve unallocated
overseas results; do not assign them to a guessed county.

The official 2026 Census directory explicitly declares the complete
`tl_2026_us_county.zip`. Full original/index/receipts are acquired in
`files/census-2026-county-reference/`: **83,378,454 bytes**, SHA-256
`b527c9ba7aeb8f17ef118f026eae5e5a938aa1d00b873bc32342d0dce59321c0`.
ZIP CRC and all seven native members pass. Its 3,235 native records include
all **nine Connecticut planning regions** and **30 Alaska county equivalents**.
Native projection is NAD83 geographic; explicitly transform to WGS84 for
display. This is a 2026 Census county reference, not certified election
precinct geometry; do not silently substitute the site's 2024 county shapes.

**Next executable actions:** implement strict literal candidate-vector and
county-identity reconciliation for each actual district; require all declared
state districts to pass before aggregating county fragments. Preserve missing
or ambiguous references, source timestamps, nested levels, unlocated votes,
all rejected responses and exact failure reasons. Acquire legitimate
Pennsylvania alternatives. Package complete originals, normalized full rows,
audits and reproducible tools before immutable release and county-layer
integration. Add 2026 geometry, correctly label House aggregate margins,
merge the supplement after current-results refresh, preserve red/blue signs,
precinct priority, state fallback, 2026 defaults, zoom and full JS/no-JS
downloads. Pursue the remaining Washington precinct crosswalks, Pierce rings,
King identities and Jefferson/Walla Walla accounting independently. Native
participation denominators remain a separate review; no final or demographic
turnout is inferred.

### Original county package: 47 states reconciled and live-verified

Canonical parser/builder: `scripts/review-house-county-results.py`.
Every accepted native county or explicit overseas row carries exactly the
district's full literal candidate/party inventory and explicit nonnegative
integer counts; none are filled from missing values. County plus explicit
unlocated vectors equal each district's own candidate vector. A state requires
every declared district to pass and every correct-year Census county equivalent
to be present before any county aggregation is promoted.

The review passes **406 districts / 47 states / 2,958 county equivalents**.
There are **2,953 nonzero colorable counties** and five explicit zero-vote rows.
Direct native FIPS joins are preferred. Missing FIPS permits only unique
Census short/long names after case folding and removing periods, not spelling
aliases, geographic allocation or guessing padded codes. This narrowly handles
Indiana's native `St Joseph` versus Census `St. Joseph`; `Saint Joseph` is not
silently substituted, and normalized-name collisions are rejected.
Connecticut uses all nine current planning regions, Virginia all 133 counties
and independent cities, and Alaska all 30 current county equivalents.

The **three withheld states in this original `house-01` snapshot** are
(Illinois is resolved in the separate `house-02` review below):

| State | Actual source defect | Next action |
|---|---|---|
| Illinois | Eleven district bodies label Chicago as a County with no FIPS, separately from Cook; direct county sums reconcile but Chicago is not a Census county identity. | Obtain a legitimate complete county aggregate or explicit reporting-authority crosswalk; do not casually merge Chicago into Cook or allocate city votes. |
| Maine | ME-02 counties report zero write-ins while its district explicitly reports 165; the complete candidate vector does not roll up. | Obtain official county write-in returns or a source-declared unlocated component, not a derived invented county assignment. |
| Pennsylvania | All 17 declared bodies explicitly have `test_data:true`. | Obtain production official county results; keep these original test bodies archived and withheld. |

D.C. is outside the national source's 435 voting House districts; preserve its
existing reviewed precinct layer and whole-state fallback, not an invented
county total. Explicit source overseas regions remain separately unlocated:
Alaska **128**, Rhode Island CD1 **447**, Rhode Island CD2 **308**.
No county receives those votes.

All **2,958** unsimplified native 2026 Census county shapes are valid after
the explicit native NAD83-to-WGS84 transform. No invalid-geometry exclusions,
repairs, coordinate simplification or cross-year substitution are needed.
Independent per-state spatial checks find **zero overlapping polygon pairs
above `1e-10` square degrees**. The complete original ZIP remains retained;
these are county reference shapes, not election-precinct boundaries.

Package: `data/county-results/20261105-house-01/`.
Full immutable ZIP: `complete-2026-house-county-results-01.zip`,
**138,508,764 bytes**, SHA-256
`abd1c5d6abab56652e16f507af25be2481e76e61b8d80c2aae08baa137bcf9f7`.
It includes every 435 original response/receipt (including withheld inputs),
the national declaration, complete original 2026 Census archive/index/receipts,
all normalized county rows and contributing district candidate vectors,
full CSV, 47 unsimplified geometry shards, UI margins, audits/checksums and
standalone tools. Largest geometry shard is only **3,922,482 bytes** compressed.
All **428 collector tests** pass, including 30 focused county cases.

Independent verification checks every original receipt and checksum, all
normalized candidate counts and CSV cells, all valid nonoverlapping geometries,
all 17 test-source exclusions and a **network-disabled, archive-only,
byte-identical complete ZIP rebuild**.
Every D/R/other county total in Washington also agrees exactly with the
separately reviewed official APIs and both workbook summaries for all39 counties.
Proof: `files/national-2026-county-package-proof-01.json`.

The source batch is committed/pushed as Hans at
`c9a4d78227693f5d0562aa9a280ceef36afc1d0e`. Immutable release
`voter-county-house-20261105` targets that exact commit. Independent complete
remote download, SHA-256, CRC and tag verification passed:
`files/national-2026-county-remote-release-proof-01.json`.

The UI now pins that source and release in `public/county-results.json`.
County rows merge after the latest-result refresh so the refresh cannot
silently remove them. Verified precincts retain priority; selecting a state
without a precinct layer falls back to its own county results. County colors
also sit beneath unmatched precinct areas when zoomed into a state.
The UI identifies House aggregates, 2026 Census county reference boundaries,
zero-vote rows, unallocated overseas returns and withheld states explicitly.
A failed optional county fetch does not block verified precinct results.

Local source-matched browser verification passed for **all 47 states / 2,953
actual county fills**, independently recalculated margins and candidate totals,
desktop and mobile, plus JavaScript/no-JavaScript downloads. The 58 complete
download links retain all 55 prior production links. Tests also cover all
39 Washington county backdrops below its 1,499 mapped precincts, fallback
states, county selection/zoom buttons/wheel/real touch pinch, 2024/2020
precinct isolation, unavailable historical geography, failed registry fetches
and failed optional county geometry. Proof:
`files/national-2026-county-local-browser-proof.json`.
Canonical check: `scripts/check-county-results-browser.py --output /path/to/proof.json`;
use `--base-url` for production and `--baseline-downloads` for the saved
pre-publication complete-link baseline.

Renderer syntax, seven focused Node tests, Astro check (zero errors),
normal build and Pages preparation pass. All 94 relocated assets remain
byte-identical; prepared Pages output is **986,242,205 bytes**.
The full county source package is not duplicated into the Pages artifact.
The general participation checker now accounts for count-only supplements
and verified 2026 county results instead of expecting absent county layers.

UI commit **`30e68d213c0567a015e8613424a9883a747690ed`** was committed and
pushed as Hans. Its exact Pages run **`41998429544`** succeeded.
The county checker passed against **unqueried production**, source-matching
the registry, renderer and worklist before testing every actual county fill,
counts/margins, precinct priority, zoom/wheel/real touch pinch, historical
isolation, all 58 complete download links with all 55 prior links retained,
desktop/mobile, JavaScript/no-JavaScript and failed-county-fetch fallbacks.
Proofs: `files/national-2026-county-ui-deployment.json` and
`files/national-2026-county-live-browser-proof.json`.
The county registry was marked **`live_verified_partial`** in status/source-only
commit **`afb769d841dd9ad114956200401a49c04e0c0963`**. Its exact Pages run
**`41999766700`** succeeded. Unqueried registry, renderer and worklist bytes
matched the checkout, all 58 complete download links retained all 55 prior
links, and the complete Maine/Pennsylvania original-source archive downloaded
from that immutable commit matched local bytes. Proof:
`files/county-status-publication-proof.json`.

**Next executable actions:** publish the separately verified Illinois-inclusive
`house-02` source/release and UI below. Continue Maine/Pennsylvania source
alternatives, remaining 2026 precinct scopes, then the historical queue.
The precinct worklist remains **1,632 incomplete cells**; county coverage is
not precinct completion.

### Maine / Pennsylvania official follow-up originals acquired during deployment

New complete source package:
`data/official-election-sources/20261105-maine-pennsylvania-01/`.
Its `complete-originals.tar.gz` contains **18 full HTTP responses / 16 PDFs /
92 PDF pages**, all source receipts, complete native indexes, extracted text,
acquisition inventory and portable acquisition/packaging tools. Archive:
**4,625,081 bytes**, SHA-256
`a76cd018b725f5ce2e533e3eeb09bc688d36ba0b5ac74083c9e55e98c6a47e34`.
Independent receipt/checksum verification and an **archive-only, offline,
byte-identical rebuild of all three package files** passed:
`files/official-county-followups-offline-proof-01.json`.

Lewiston's official index declares 14 complete PDFs for all 13 even years
**2002–2026**, including the separate 2026 declared-write-in report.
These are **city-only originals**, not statewide Maine or completed precinct
maps. Direct HTTP returned 404, but ordinary browser navigation and its normal
request context returned the actual index/PDF bytes with HTTP 200; no challenge
was solved or bypassed. All original native legacy HTTP document links and
resolved URLs remain in their receipts. The 2026 general report retains seven
wards and separate `C-V` central voting; its write-in report labels a separate
column `Absentees`. Do not assume those modes are interchangeable or allocate
central returns among wards. Raw text extraction concatenates some numeric
columns, so use PDF coordinates and original tables before normalizing counts.

Pennsylvania's official current-data index declares two complete 2026 PDFs:
the eight-page supplemental ballot-counting report and the two-page 12:01 mail
ballot receipt report. These provide administrative mail returns and precinct
reporting, **not House candidate votes, final turnout or precinct voter counts**.
They do not repair the 17 test-flagged candidate APIs or justify a red/blue
county layer. Next: reconcile actual county rows and report timestamps,
preserve incomplete/administrative reporting scope, and normalize source-defined
participation independently of the still-withheld candidate results.

### Illinois resolved without merging votes: new 48-state county source package

The actual eleven unmatched native `chicago` rows are **explicitly all zero**:
every literal candidate is present with integer zero votes, no county FIPS,
`name="Chicago"`, `type="County"` and zero reported percentage. Each affected
district independently supplies native `cook` / `Cook` / `County` / **17031**
and its own nonzero candidate vector. The previous failure was refusing to
map that separate unresolved zero row, not a missing or unassigned set of votes.

The canonical parser now narrowly retains only that exact Illinois placeholder
in **`unlocated_regions`**, including its literal candidates and native reporting
percentage. It is not discarded, mapped as a fake county/precinct, merged into
Cook, reclassified as overseas, or interpreted as zero participation.
Any nonzero Chicago count, missing candidate/count, wrong party, reporting
progress, mismatched name/FIPS/state or absent/invalid native Cook row remains
rejected. **41 focused county tests pass**, including eleven new scope/edge cases.
County candidates plus all explicit unlocated vectors still equal each district.

New immutable package: `data/county-results/20261105-house-02/`.
It passes **417 district reviews / 48 states / 3,060 county equivalents**,
including all **17 Illinois districts / 102 actual counties**.
All **3,050** nonzero county margins are colorable; **ten** explicit
zero-vote counties remain uncolored, including five in Illinois. The earlier
3,055/five-zero prose was a reporting-count error, not the package's actual
index or candidate counts. Maine's 165 write-in mismatch and all
17 Pennsylvania test-flagged sources remain withheld. D.C. remains outside
the 435-voting-district source. No precinct cell is marked complete.

Full ZIP: `complete-2026-house-county-results-02.zip`,
**139,681,390 bytes**, SHA-256
`eacd3f041bbd888f055bd8403b057b60d7605a6bc59e0b3c627a9ee8209bcae7`.
It contains all 435 original responses/receipts, complete original Census
archive, exact normalized counts and full CSV, candidate-vector audits,
48 unsimplified correct-year county geometry shards and portable tools.
Independent verification checks every original receipt/checksum and candidate
vector, every CSV value, all valid nonoverlapping geometries, the eleven retained
zero placeholders and a **network-disabled, archive-only byte-identical complete
ZIP rebuild**. Every pre-existing 47-state normalized row and geometry shard is
**unchanged**. All 39 Washington official county comparisons still agree.
Proof: `files/national-2026-county-package-proof-02.json`.

Independent ordinary-browser acquisition also preserves native Illinois authority
index and its All Election Authorities selection, the current Cook election page,
official county scope and the full election-night response in
`files/remaining-county-authorities-20261105/`, with original receipts.
The official page explicitly covers suburban Cook; never add those native
suburban totals to an already FIPS-identified provider Cook County aggregate.
The stale Cook `/elections/election-results` URL returns 404; the declared current
route is `/elections/results-and-election-data/election-results`.
The Pennsylvania root returns a blocked Incapsula document despite HTTP 200,
and Maine's state index returns 403 in both direct and ordinary browser access.
Those are access evidence, not result data; no challenge was solved or bypassed.

Source package and parser/tests are committed/pushed as Hans at
`6b6b96caed4fa4f7c66fd206a64bd709310a69f2`. New immutable release
`voter-county-house-20261105-02` targets that exact commit, without replacing
`house-01`. The UI update retains the original snapshot as download history,
preserving all 58 prior complete download links and adding three new ones.

Complete public release download, exact tag/source binding, SHA-256 and ZIP CRC
verification passed: `files/national-2026-county-remote-release-proof-02.json`.
Local source-matched browser checks passed for all **48 states / 3,050 actual
fills**, including Illinois's **102 county rows / 97 actual colors**.
Desktop/mobile and JavaScript/no-JavaScript retain **all 58** previous complete
downloads among **61** links. Precinct priority, county backdrops, selection,
button/wheel/real-touch zoom, historical isolation and fetch-failure fallbacks
all pass: `files/national-2026-county-local-browser-proof-02.json`.
Renderer syntax, seven Node tests, 41 focused collector cases, Astro check
(zero errors), normal build and canonical Pages preparation pass. All 94
relocated assets remain byte-identical; prepared output is **986,245,090 bytes**.

UI commit `bfaaf6be153f1d5f1fe37f18c33e2a015fac06b8` is now live after exact
successful Pages deployment **42002127989**. The full source-matched, unqueried
production suite passed all 48 states / 3,050 fills and all desktop/mobile,
JavaScript/no-JavaScript, precinct-priority, zoom and failure-fallback checks:
`files/national-2026-county-live-browser-proof-02.json`.
The pointer is eligible for `live_verified_partial`; this does not complete
any precinct state/year cell. Keep both full county snapshots and all 61 links.

### Maine / Pennsylvania participation normalized without manufacturing maps

Canonical coordinate-aware reviewer:
`scripts/review-maine-pennsylvania-participation.py`.
Reviewed package:
`data/participation-source-reviews/20261105-maine-pennsylvania-01/`.
It retains the complete prior original-source archive, source inventory and
receipts, portable reviewer, full CSV/JSON tables, audit and checksums.

The package has **185 observations**: **13 Lewiston city totals** for every
even year **2002–2026**, **105 native ward/precinct/central or city-mode counts**,
and **67 Pennsylvania county mail-return rows**. Rotated historical pages are
read using their actual displayed PDF word coordinates. The native columns
and every ward/central sum reconcile to the printed city total. C-V remains
unallocated Central Voting, never an inferred absentee count or a ward.
The 2020 report instead gives citywide Absentee/In Person counts; no missing
ward counts are invented. The 2002 report supplies no registered denominator,
so no rate is calculated. Twelve subsequent city totals have their own native
registered denominators; these are not Census/CPS rates or demographic estimates.
Missing printed percentages remain missing, separate from calculated fractions.
In particular, the 2004 referendum's **1% property-tax wording is not turnout**.

Lewiston 2026 explicitly reports **14,713 voters / 24,455 registered**,
with native printed **60%**. The calculated city fraction is about **60.16%**;
none of the ward rows borrows that city denominator. The city's seven ward
counts plus separate **6,583 C-V** voters reconcile exactly.
Original 2002 and 2026 voter tables were also rendered and directly reviewed.

Both independent Pennsylvania PDFs agree on every native county's returned-mail
count and their **1,163,183** statewide sum. The supplemental report's native
update is **November 4, 2026, 4:08:50 PM**; this is not an inferred timestamp for
the separate standalone report. Its **9,055 / 9,065 precincts reported** and
**9,052,695 registered** remain administrative context, not a turnout denominator
or inferred election-day voter count. Montour's zero recorded mail returns and
100% remaining-to-count field do not establish zero voter participation.
These observations do not overwrite or splice the older provider snapshot's
different mail-return total, repair Maine's county write-in mismatch, or replace
Pennsylvania's test-flagged House candidate data.

Seven new targeted regression cases pass, including missing counts, bad sums,
duplicate columns and unrelated referendum percentages. Independent source,
CSV and complete-original verification plus a **network-disabled, archive-only,
byte-identical ZIP rebuild** pass:
`files/me-pa-participation-review-proof-01.json`.
Complete ZIP: `complete-maine-pennsylvania-participation-review-01.zip`,
**4,648,075 bytes**, SHA-256
`9e614c145f6676d1d89ab01550c4dcc8056f0383a6f415c1d8c788087ffefe3c`.

Source commit `41fcfe00819fdf7593ae416e45ca93507bc419e4` is pushed as Hans.
Immutable release `voter-participation-maine-pennsylvania-20261105` targets that
exact commit. The entire public ZIP, byte count, SHA-256, CRC and exact tag binding
passed: `files/me-pa-participation-remote-release-proof-01.json`.

The separate `public/participation-source-reviews.json` registry adds four
complete downloads without altering any map registry. A native Methods
disclosure exposes all 13 city years, newest first, with each year's own voter
and registered counts and calculated rate. All 61 old links remain among 65.
The worklist carries 13 explicitly city-only Maine participation entries and
one Pennsylvania mail-return-only entry; no candidate, boundary, join,
validation, map-publication or completion field is promoted. Existing approved
counts cannot be downgraded by a limited city review.

Ten focused Python cases (including seven source-parser regressions and two
new ledger-scope cases), seven Node tests, Astro check (zero errors), normal
build and canonical Pages preparation pass. All 94 relocated assets remain
byte-identical; prepared output is **986,260,852 bytes**. The new focused browser
checker verifies every city count and displayed rate, three entire remote CSVs,
all 65 exact download URLs, disclosure interaction and no overflow in all four
desktop/mobile, JavaScript/no-JavaScript modes:
`files/me-pa-participation-local-browser-proof-01.json`.

UI commit **`96ac461ea4fa1c107a1e48a2776356e3a68c4d3a`** is live in exact
successful Pages deployment **42004537566**. The unqueried production checker
passed all four browser modes, every city row/rate, all 65 exact links, three
entire CSVs and unchanged renderer bytes:
`files/me-pa-participation-live-browser-proof-01.json`.
The county renderer and immutable maps are unchanged from their completed full
48-state live suite; do not repeat it instead of acquiring new data.

**Next executable actions:** continue remaining 2026 source gaps and actual-election
historical acquisition. Keep candidate geography, demographic coverage and
final-turnout approval withheld for this limited review, with all prior
complete downloads and all 1,632 incomplete precinct cells preserved.

### Wyoming 2026 / 2022 complete official originals

Acquired all advertised general-election originals from the Secretary of State's
`2026GeneralResults.aspx` and `2022GeneralResults.aspx` indexes: **108 complete
HTTP bodies, 20,023,241 original bytes**, including **105 PDFs / 1,154 pages**,
both HTML indexes and the native 2022 ZIP with all three Excel workbooks.
Both years include separate candidate and ballot reports for **all 23 counties**,
plus statewide summaries. No 2026 native workbook ZIP was advertised.

The immutable acquisition is
`data/precinct-source-acquisitions/20261105/WY-2026-2022/`. Reproduce offline with
its included `archive-wyoming-election-sources.py`, exact original receipts and
visual identity reviews. The complete archive is
`complete-wyoming-2026-2022-official-originals-01.zip`,
**14,727,543 bytes**, SHA-256
`39f78671041966c0939ce4bce439916aa04368ba413d58615e086f9e314e0d2c`.
All original bytes, receipts, internal checksums and ZIP CRC pass. A
network-disabled archive-only rebuild is byte-identical:
`files/wyoming-2026-2022-official-package-proof-01.json`.
Nine focused source-inventory, election-date and visual-proof regressions pass.

Source commit **`b46db3d20c8b16c002a3ebd6f78cb60b5177e110`** is pushed as Hans.
Immutable release **`voter-precinct-wyoming-originals-20261105`** targets that
exact commit. The entire public ZIP matches the local archive byte-for-byte;
its tag binding, CRC, package checksums and all 108 original receipts pass:
`files/wyoming-official-originals-remote-release-proof-01.json`.

Thirteen 2026 PDFs use glyph-encoded Type3 fonts with unreadable extracted
dates. Directly rendered and reviewed every affected original first-page header;
all explicitly say **November 3, 2026**. Each review is bound to the exact PDF
SHA-256 and cannot approve changed bytes or another election. This establishes
document identity, **not recovered numeric tables**. **Correction from a fresh
direct rendering and native glyph review:** both Park headers say Unofficial,
matching their red banners and the source index. The earlier description of
an Official header was a visual-review error, not a conflict in those documents.
The immutable acquisition package is unchanged; the recovery review includes
this explicit erratum. Individually dated original
captures are not a simultaneous, reconciled statewide result snapshot.

The independent 2022 workbook diagnostic now compares all **3,073 House
category cells and 439 separate precinct ballot counts across all 23 counties**
to the previously acquired CSV. All counts match; all candidate county and
statewide vectors reconcile. Thirty-five CSV precinct labels are serialized
Excel dates. Their actual native `mm-dd` / `m-d` display formats recover explicit
labels that match the separate ballot workbook; preserve this source-bound
crosswalk, not fuzzy names or date strings as geographic identifiers. The four
literal page-continuation markers have no counts and are explicitly excluded.
Native Selvig `(C)` and CSV `CTRY` party labels remain distinct.

The native Natrona precinct ballot rows sum to **22,955** and agree with the
statewide county value, but its county workbook and PDF print **22,957** as the
county total. Retain the two-ballot printed-total conflict without changing any
original or assigning two ballots to a precinct. Statewide native precinct
ballots total **198,198**; five candidate/write-in categories total **193,902**,
with overvotes and undervotes separate. Candidate counts are not turnout.
The diagnostic proof and full 35-label crosswalk are
`files/wyoming-2022-independent-native-reconciliation-proof-01.json`; ballot
approval and all maps remain withheld.

The pinned source batch adds one complete download while retaining every
previous link. Its two ledger cells remain original-acquired / review-pending,
not mapped, completed or approved turnout. The generic acquisition note now
claims archived-file integrity, not readable native text that the Type3 PDFs
do not provide. Ancillary UI/ledger integration commit
**`3c0bf71d387820ef7ec60ed3d6e534d5bc787842`** is live in exact successful
Pages deployment **42006922857**. The unqueried production checker passes
all four desktop/mobile, JavaScript/no-JavaScript modes, all **66** exact
complete-download links, all 13 city rows/rates, three entire CSV endpoints,
unchanged renderer bytes and no overflow:
`files/wyoming-source-ui-live-browser-proof-01.json`.
Thirteen focused collector/worklist cases, Astro check (zero errors/warnings),
the normal build and Pages preparation pass; **94** relocated downloads remain
byte-identical and the prepared site is **986,263,574 bytes**. Four-mode local
browser checks pass all **66** exact complete-download links, retain the
13-year city table and verify unmodified renderer bytes:
`files/wyoming-source-ui-local-browser-proof-01.json`.

### Wyoming 2026 native glyph recovery

The previously unreadable Type3 PDFs contain native vector glyph drawings.
Directly rendered and reviewed all **570 distinct drawing-stream SHA-256s** in
six labeled review sheets. An exact-source, exact-font-encoding, exact-drawing
review now recovers **all 13 affected documents / 224 pages**, not 239 pages.
The code adds only in-memory ToUnicode metadata and reopens that derived
document before extracting text and coordinates. Every page renders
**byte-identically** before and after recovery. Original PDF bytes are unchanged.
No OCR, numeric interpolation, guessed vote values or altered font widths are used.

The reproducible reviewer is `scripts/recover-wyoming-native-pdf-text.py`;
the complete review is
`data/precinct-source-reviews/20261105/WY-2026-native-text/`.
It includes all **108** original source bodies and receipts, complete
reviewed glyph inventory/catalog/transcriptions, six direct-review images,
full recovered text and word coordinates, portable code, per-page render
proofs, checksums and the explicit Park-header erratum. Eight new focused
regressions reject changed source, encoding, drawing, missing review, guessed
method, ambiguous character and missing font; all **17 Wyoming cases pass**.

Complete archive `complete-wyoming-native-glyph-recovery-01.zip` is
**19,481,350 bytes**, SHA-256
`efc289365c002a6c507d70de871c7931c9ca195390114966c21e6ff621f52bc7`.
A network-disabled rebuild is byte-identical and ZIP CRC passes:
`files/wyoming-native-text-package-proof-01.json`.
Recovery source commit **`d5d275d6b83b65cce0b948e0213949f109d15ec4`**
is pushed as Hans. Immutable release
**`voter-precinct-wyoming-native-text-20261105`** targets that commit.
The entire remotely downloaded archive, all 150 checked package members,
all 108 original-body receipts and ZIP CRC match:
`files/wyoming-native-text-remote-release-proof-01.json`.
Recovery does **not** approve the numeric tables, turnout, geography or maps.
The recovered statewide ballot summary prints **191,688**; reconcile it against
every separate county/precinct table before using it as a reviewed ballot total.

### Wyoming 2026 independently reconciled precinct ballot counts

The reusable `scripts/review-wyoming-precinct-results.py` now reads the native
physical table coordinates across all 23 counties, using source-hash-verified
recovered words only for the Type3 originals. Native identifiers are retained
exactly, including leading zeroes; every candidate header, election date,
continuation and printed total is checked. Numeric page footers are never
ballot records.

All **432 separate precinct ballot counts** match their seven-category House
accounting sums and reconcile to **191,688** at both county and statewide
levels. All **3,024** House cells reconcile to their native county printed
vectors. **22 of 23 counties / 427 precincts** also match the complete
statewide candidate vectors. Five Washakie precincts retain an explicit
candidate-category conflict: their state-hosted precinct PDF prints Johnson
130 / Haggit 194, while the statewide summary prints Johnson 194 / Haggit 130.
D/R, write-ins, overvotes, undervotes and total ballots agree. Do not silently
swap the five precincts' third-party columns.

Pursued the discrepancy with an independently acquired, complete **eight-page**
county-issued general-election PDF advertised by the live county election
index (DocumentCenter 632). Its directly reviewed first page explicitly says
November 3, 2026, Unofficial, ballots **2,819**, Johnson **194** and Haggit **130**.
It confirms the statewide county aggregate, not a basis for allocating or
repairing precinct candidate counts. Its literal `LIB` / `CST` party labels,
complete HTTP original, advertising index, receipts, source-bound visual
transcription and original rendered first page are retained.

The full immutable review is
`data/precinct-source-reviews/20261105/WY-2026-native-counts/`.
It includes every original from both preceding packages, the two additional
county originals (**110 complete HTTP originals total**), all 432 normalized
CSV rows, explicit native candidate categories, independent ballot counts,
per-row source SHA-256/page references, complete conflict vectors, review
code and every native glyph review. Registrations and rates are blank, not
zero or borrowed denominators; neither geography nor maps are approved.

Complete archive `complete-wyoming-2026-native-count-review-01.zip` is
**20,025,208 bytes**, SHA-256
`53b246106834a160662d9b66283a8298d0a64edcb9d2b56cf299628bbe42cae6`.
All **29 Wyoming focused tests** pass. All 159 checked package files and the
432-row CSV pass; a network-disabled rebuild is byte-identical and ZIP CRC
passes: `files/wyoming-2026-native-count-package-proof-01.json`.
Source commit **`6ff31fc2cf9a4be6757db120b8ab2df3a08f7cb5`** is pushed
as Hans. Immutable release **`voter-precinct-wyoming-counts-20261105`** targets
that commit. The entire remotely downloaded ZIP is byte-identical; its CRC,
all 159 checked package members and all **110** original-body receipts pass:
`files/wyoming-2026-native-count-remote-release-proof-01.json`.

Ancillary UI integration adds the complete count review as one new download,
preserving all 66 prior links. Its count-review metadata is separate from the
immutable source package. Only the **2026 WY** worklist row changes; boundaries
remain unreviewed and maps/joins withheld. All 1,632 precinct cells remain
incomplete. The browser checker derives complete links from registered source
reviews too, and verifies the entire pinned 432-row CSV alongside the three
participation CSVs. Exact deployment and production checks are pending.
All **34** focused collector/worklist tests pass, Astro check has zero
errors/warnings (five existing hints), the normal build and canonical Pages
preparation pass. All **94** relocated downloads remain byte-identical; prepared
site size is **986,264,292 bytes**. Four-mode local browser checks pass all
**67** exact complete-download links, every city row/rate and all four entire
CSV endpoints, including the **432-row / 118,060-byte** native count table:
`files/wyoming-native-count-ui-local-browser-proof-01.json`.
The renderer and pinned research export are unchanged.

Ancillary UI commit **`67598577278dbd7121403e70bcb2873835458db7`** is
pushed as Hans. Exact deployment **42010632843** succeeded and all four
production browser modes passed **67** exact complete-download links and all
four entire CSV endpoints, including the 432-row native table. Unqueried public
registry, county index, ledger and renderer bytes match the exact commit:
`files/wyoming-native-count-ui-deployment-01.json` and
`files/wyoming-native-count-ui-live-browser-proof-01.json`.
The local preview has been stopped; do not repeat this completed suite.

The official-linked LSO House web map
`7d70f77b3ba449e09f576a92deac27a5` returns an explicit HTTP/API 403 permission
error. This is not an acquired precinct layer; do not bypass it or label House
district geometry as precincts. Independently archived the SOS election index
and complete **35-page** `2026_Districts_and_Precincts_by_County.pdf` in session
`files/wyoming-2026-precinct-identity-reference-01/`. Its actual printed date is
**June 12, 2026**, not election day; the **76,830-byte** PDF SHA-256 is
`63edd0934157ae7b246a2ff25837e5719df89a35421725c781bb7e2ed05b3103`.
It is a potential identity reference, not November boundary approval.

**Next executable actions:** seek county-issued precinct
detail for Washakie's third-party conflict and actual 2026 geometry for all
432 native units; do not borrow 2022's 439-unit geometry. Acquire
actual-election geometry before mapping. Do not infer registrations or turnout rates.

### Wyoming 2022 independently reconciled native workbook counts

The reusable `scripts/review-wyoming-2022-native-results.py` now independently
reads the complete native SOS ZIP's three workbooks. All **439 precincts**
across **23 counties**, **3,073 House-category cells** and **439 separate
ballot cells** match the separately acquired immutable OpenElections CSV.
Precinct/county/state candidate vectors reconcile. Native precinct ballots and
the statewide table total **198,198**, separately from **193,902**
candidate/write-in votes. Neither number is inferred from the other.

Preserved **35** explicit source-bound Excel-format crosswalks for date-coerced
CSV identifiers, with native workbook/sheet/row occurrences. Native candidate
and ballot workbooks need not encode the same displayed precinct as the same
Excel type: Carbon's candidate identifiers are dates while its ballot
identifiers can be strings. Require exact independently displayed identifier
sets and unambiguous date-to-display mappings, not identical storage types.
Do not guess hyphens or discard leading zeroes.

Natrona's printed county ballot total remains **22,957**, versus **22,955**
in both its summed precinct counts and the statewide county value. No two
ballots are manufactured, moved or subtracted. Registrations and rates are
blank for every normalized row; geometry/maps and ballot approval remain
withheld. Native Selvig `(C)` and CSV `CTRY` remain distinct literal labels.

The complete review is
`data/precinct-source-reviews/20261105/WY-2022-native-counts/`: all **55**
advertised 2022 SOS originals and receipts, complete original acquired CSV
and documentation/provenance, all 439 normalized rows and source cell
references, full crosswalks/conflict, portable reviewer and checksums.
Nine new focused regressions pass. ZIP CRC, **63** checked package files,
all original receipts and the complete CSV pass; a portable offline rebuild
is byte-identical:
`files/wyoming-2022-native-count-package-proof-01.json`.
The complete archive `complete-wyoming-2022-native-count-review-01.zip` is
**4,885,475 bytes**, SHA-256
`5c160354623564d7584279a448e8662188058ffdcb47b75ecd31b0a2d24d1e7b`.
Source commit **`c29d5fe5f72096a4d0c7366c3611ddf3b8a040a8`** is
pushed as Hans. Immutable release
**`voter-precinct-wyoming-2022-counts-20261105`** targets that exact commit.
The entire remotely redownloaded ZIP, CRC, all 63 checked files and all 55
original-body receipts pass:
`files/wyoming-2022-native-count-remote-release-proof-01.json`.
Separate count-review metadata now registers this verified complete download;
the ancillary UI passes **43** Wyoming/coverage cases, Astro check (zero errors
and warnings; five existing hints), normal build/chart tests and canonical
Pages preparation. All **94** relocated downloads remain byte-identical;
the prepared site is **986,265,144 bytes**. Four source-matched local browser
modes pass **68** exact complete-download links and all **five** entire CSV
endpoints, including the 439-row / **101,411-byte** native table:
`files/wyoming-2022-native-count-ui-local-browser-proof-01.json`.
Only the WY2022 ledger row changes; all **1,632** cells remain incomplete.
The pinned research export and renderer are unchanged, including the 2026
default. Exact-live ancillary UI verification subsequently passed below.

Ancillary UI **`b9290a3d5edf3d6481ee35e360d38f4e7bfb55a6`** is pushed
as Hans and exact deployment **42012683301** succeeded. All four production
modes pass the 68 exact complete-download links and five whole CSV endpoints.
Unqueried public metadata matches that exact commit:
`files/wyoming-2022-native-count-ui-deployment-01.json` and
`files/wyoming-2022-native-count-ui-live-browser-proof-01.json`.
Do not repeat this completed suite.

**Next executable actions:** retain the bounded Wyoming geometry/count conflicts
and continue unreviewed 2026 jurisdictions. An independent county-issued alternative
is the advertised 18-page 2022 EL-45 summary, DocumentCenter **7601**, on
`https://www.natronacounty-wy.gov/659/Election-Results-Archive`; its native text
confirms **22,955** ballots. Acquire the complete advertised EL-45, EL-30
(DocumentCenter **7600**, 496 pages) and EL-52 (**7602**, 58 pages) originals
before formal follow-up. The current 2026 county index is
`https://www.natronacounty-wy.gov/918/Election-Results`, not that archive.
Its separate 2026 summary/statistics original (DocumentCenter **14007**) is
a concrete new participation lead, not a basis for borrowing county
registrations into precinct rates. Preserve snapshots rather than replacing
this already-built native review.

Direct requests to all four advertised county PDFs (2026 statistics **14007**;
2022 EL-45 **7601**, EL-30 **7600**, EL-52 **7602**) also returned **HTTP 403**.
The complete response bodies and receipts are preserved separately in session
`files/wyoming-natrona-2026-2022-official-followup-02/`; **zero PDF originals**
were acquired. Publicly indexed text is still a lead, not a byte-preserved
county-original acquisition or a basis for normalizing new participation rows.
Seek independently published originals or proceed to other 2026 jurisdictions;
do not bypass access restrictions or relabel these responses as election data.

## Virginia 2026 native precinct and demographic report review

The official Virginia results index explicitly links the
**2026 November General**, **November 3, 2026** public Enhanced Voting app.
Acquired its actual browser-observed JSON, official registration/turnout
definitions and all four advertised complete reports, not guessed export URLs:
Election Results, Election Turnout, Election Change Log and EnrAbsenteeRawCSV.
The native JSON identifies production, unofficial results, publish version
`e5af7981-c42c-45c0-9923-b33f316e79bd`, as of
**November 5, 2026, 02:19:25 UTC**. The official historical turnout page says
November turnout is published after certification; do not extend 2025 figures.

`scripts/review-virginia-2026-native-results.py` now preserves and independently
reviews all **32 HTTP originals**, complete receipts and all **46,418**
original result rows. Native results/change-log CSV bytes are CP1252, unlike
the UTF-8 demographic/turnout CSVs; originals are not transcoded. The native
`WriteInVote` column contains actual write-in **counts**, not booleans. Write-in
rows have a blank `TOTAL_VOTES`; use the explicit `wi-<OfficeId>` identity and
literal `WRITE IN VOTES` before reading that separate count column. Explicit
zeroes remain zeroes; genuinely missing totals remain missing.

The review retains **2,537** House district/reporting-unit vectors across
**133 counties and independent cities**, **10,471** candidate cells and a
separate **2,529-row** native precinct turnout table. Every original House
district vector differs from the state JSON: CSV candidate/write-in votes total
**2,912,898** versus **3,568,142** in the native summaries. All **11** conflicts
remain explicit; no missing votes are allocated. All **985** missing precinct
`TotalVoteTurnout` values remain missing. Its **1,375,326** known-vote subtotal
is not statewide turnout. The precinct active/inactive/total registration sums
independently match all 133 native locality registration vectors. Rates and
geometry/maps remain withheld; registration totals are not group denominators.

The complete **16,250-row** absentee demographic report *does* independently
reconcile all **nine** native application-type totals and all **five** native
returned-method totals: **1,777,541 applications**, separately from
**1,672,941 returned absentee ballots**. A complete **2,286-row** grouped table
retains native locality, congressional district, age range and gender, with
separate application/return counts and blank registration/rate fields. All
**5,003** blank receipt-type records remain explicit; they are not silently
classified as returned or converted to zero. Applications and returns are
overlapping measurements, never additive. Returned does not mean accepted or
counted; these are not all voting or final demographic turnout rates.

The complete package is
`data/precinct-source-reviews/20261105/VA-2026-native-counts/`, including all
32 original bodies, 40 checked files, the full original **335,814-row** change
log, all source CSVs, all four normalized tables, conflicts and portable code.
Twelve new regressions pass; the combined Virginia/Wyoming/coverage selector
passes **55** cases. ZIP CRC, every original receipt, complete table checks and
a byte-identical portable offline rebuild pass:
`files/virginia-2026-native-count-package-proof-01.json`.
The complete ZIP is **8,604,105 bytes**, SHA-256
`3c57c2878d77b2dcda0cfccd5fa7abe8f396dd361229a2ae3dd80162cec609cb`.
Source batch **`09deda073923c36a6fba557b5c4fcf03957af324`** is committed/pushed
as Hans. Immutable release **`voter-precinct-virginia-native-counts-20261105`**
is bound to that exact source commit. The whole remote ZIP was redownloaded;
its exact bytes/SHA/size, CRC, exact member set, all 40 file checksums and all
32 decompressed original receipts pass. Every remote member equals the pinned
source. Proof: `files/virginia-2026-native-count-remote-release-proof-01.json`.
Separate lightweight VA2026 metadata references this verified release;
ancillary UI/ledger publication is production-verified below. Do not mark the VA2026
worklist cell complete or claim new map coverage.

Ancillary UI local validation is complete: only the VA2026 ledger row changes;
all 1,632 cells remain incomplete and renderer/colors/default/zoom are unchanged.
All 55 focused tests pass. Astro reports zero errors/warnings and five existing
hints; the normal build and four chart tests pass. Pages preparation verifies
94 unchanged relocated assets and a **986,267,164-byte** site. All four local
browser modes pass **69 exact complete-download links and six whole CSV
endpoints**, including the **2,537-row**, **1,743,695-byte** Virginia count CSV,
SHA-256 `cd176fb55504293452cc6ac4d0d034f9d0ef777d5aa828e6c1819d03c9617b6e`.
Proof: `files/virginia-2026-native-count-ui-local-browser-proof-01.json`.
UI commit **`6542d09b0f85263ee38b7ac779532e37df0d8a89`** was pushed as Hans.
Its exact deployment **`42015027552`** succeeded. Unqueried production metadata
matches that commit; all four live browser modes pass the same **69 complete
links and six whole CSV endpoints**, with no overflow. Proofs:
`files/virginia-2026-native-count-ui-deployment-01.json` and
`files/virginia-2026-native-count-ui-live-browser-proof-01.json`.
Do not rerun this completed publication suite.

### Native locality/detail expansion and explicit vote-mode reconciliation

Actual public app navigation exposed the locality API and House detail endpoint.
Using only parent-declared locality slugs and county-declared public contest IDs,
acquired **279 byte-verified HTTP originals**: the parent snapshot, **133**
locality roots and **145** locality/House detail snapshots. The actual Accomack
county/detail browser responses were reused; no disabled or protected details
were requested. Original bytes, URLs, times, hashes and navigation/endpoint
derivation are in
`files/precinct-expansion-sources/VA-2026-native-localities-01/`.
The portable normalized package below now persists this complete acquisition.

An independent full-snapshot diagnostic establishes:

- All **133 locality candidate summaries exactly reconcile to all 11 parent
  House candidate vectors**, without adjustments or unlocated vote allocation.
- All **10,471 precinct candidate cells** exactly match the earlier CSV,
  using native locality code, literal precinct name, district and candidate ID;
  there are no unmatched identities or count differences.
- **69 of 145** locality/House scopes have incomplete precinct sums relative
  to their county summaries. Source-assigned **Early Voting** vectors differ
  in **58** scopes and **Mailed Absentee** vectors in **66**. The other three
  literal mode vectors reconcile. Do not describe this simply as a later
  snapshot discrepancy or presume every county reports Election-Day-only data.
- Native JSON provides **2,529 nonmissing precinct turnout counts**, summing
  to **2,798,626**, separately from **3,593,781** county-level ballots cast.
  The earlier CSV's 985 blank total cells remain blank in its immutable package.
  Do not substitute county counts, allocate the difference or claim statewide
  all-mode precinct turnout or rates.

Diagnostic: `files/virginia-native-locality-count-diagnostic-01.json`.
The subsequent portable reviewer below independently confirms these counts;
there is still no geometry or rate approval.

### Complete official current-reference geometry acquisition

The official current-boundary page explicitly links webmap
`f0a827c63440416a94c9557a537b6ed5`, which declares the independent public
`Districts_Union_Simplified/FeatureServer/0` layer. Its publisher item
`f3eb2c0a525d494da8e6190ff2b13182` is public and owned by the ELECT
organization `M3dium4ePYpmdT4B`; description, attribution and license fields
are blank, not an asserted open-data license. The separate precinct-vector-tile
item/data requests return inaccessible-item errors and were not bypassed.

Acquired the full native object-ID query and **all 7,426 polygon fragments**
in **38 exact-ID pages**. Every ID appears exactly once, with complete native
attributes and WGS84 GeoJSON; there is no transfer-limit truncation. Preserved
all original pages and receipts under
`files/precinct-expansion-sources/VA-2026-geometry-followup-01/`.
The layer reports a September 2026 data edit, while item metadata was modified
in 2025. It is the agency's current reference, **not certified election-day
geometry**. The official page itself cautions that recent local changes may
take weeks to appear. Do not infer shape vintage solely from either timestamp
or the `CD_2021` legislative-plan field.

There are **2,532 distinct county/precinct attribute pairs**, including blank
identities; **155 fragments** have a blank county or precinct component.
Fragments must be audited and dissolved by a supported identity before any
join. Blank identities, unmatched precincts, split contests and overlapping or
invalid shapes cannot be assigned aggregate votes.

### Portable locality/mode review and complete source package

`scripts/review-virginia-2026-locality-results.py` now independently verifies
all acquired originals, the exact election/locality/contest/candidate identities,
each candidate's five literal native method counts, every precinct total,
root/detail summaries and all 11 parent district vectors. All 10,471 earlier CSV
candidate cells match, as do each native precinct's registration count and the
earlier report's corresponding literal precinct identity. Positive and negative
mode residuals remain explicit, never allocated. Source reporting-status flags,
unreported provisional/post-election modes and original blank CSV totals remain
visible; current nonmissing JSON totals are a separate observation.

The full package is
`data/precinct-source-reviews/20261105/VA-2026-native-locality-counts/`.
It contains **357 original-response files** (279 locality/detail snapshots,
all 32 earlier report originals and all 46 current-reference acquisition
responses, retaining the reused parent in both source namespaces), **2,537**
normalized precinct vectors, **145** locality/House
summary/method vectors and **2,529** native precinct turnout rows. All earlier
full reports and demographic tables remain bundled. Full scope residuals,
versions and both portable reviewers are included; the complete geometry
fragments are retained as an **unapproved reference**, not mapped precincts.

Nine new focused regressions cover partial/complete mode coverage, negative
residuals, missing counts/methods, duplicate identities, wrong contests and
accounting conflicts. The combined Virginia/Wyoming/coverage selector passes
**64** cases. A portable rebuild using only bundled inputs produces a
**byte-identical ZIP**; CRC, exact members and all **381 file checksums** pass.
The ZIP is **73,948,518 bytes**, SHA-256
`c4c28d7f426cd878b3b50672f4e5858b415c44c0cdcf7347f0ac339bc9521f43`.
Proof: `files/virginia-native-locality-count-package-proof-01.json`.
This is a new immutable package; the earlier published package is unchanged.
Hans source commit/push and whole-archive remote release verification are next.

**Next executable actions:** publish the completed native locality/mode source
batch and verify the whole immutable remote archive. Independently audit
the complete reference geometry and exact election-specific joins. Approve only
explicitly supported scopes; do not repair the earlier export, allocate missing
county modes to precincts, borrow older geometry or mark the VA2026 cell complete.

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

- **North Dakota 2026 is acquired and live-verified; do not normalize it again.** The
  official archive links current results to `https://resultsnd.sos.nd.gov/`,
  while `https://results.sos.nd.gov/` defaults to the older 2024 election.
  The new public API identifies election **348**, `2026 General Election`,
  November 3, 2026, unofficial, source version `v75`. The advertised complete
  original has been acquired and reconciled (5,779,260 uncompressed bytes):
  `https://resultsnd.sos.nd.gov/results/north-dakota/348/FullDataFile.json`.
  It contains `ElectionData`, `TurnoutData`, and `ContestData`, including nested
  county and precinct rows. The committed count review and complete release are
  documented above. Cached sources and checksums are in the session's
  `files/precinct-expansion-sources/ND-2026/`; the initial count review is
  superseded for mapping by the live-verified partial supplement above. Public feeds:
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
- **Minnesota 2026 is already acquired and live-verified at `391c681` /
  `8652eee` above; do not redownload its boundaries or originals.** Official
  election ID `201` exposes federal results by precinct;
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
