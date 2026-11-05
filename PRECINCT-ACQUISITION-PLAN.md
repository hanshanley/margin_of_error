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
CRCs and every archived byte match. Website registration is now being
verified; do not claim this download linked live yet.

Registration passes seven participation regression tests, Astro check
(zero errors/warnings, five existing hints), the production build and four
caucus tests. Pages preparation verifies **94 byte-identical relocated
originals** and a **986,201,012-byte** artifact. Focused production-preview
checks pass on desktop/mobile with and without JavaScript: all **37**
complete-download links, full AK ZIP length/hash, actual 1,632-cell ledger,
honest AK whole-state red/blue fallback without fabricated precincts,
latest 2026 default, zoom and failed-registry-fetch fallback. Idaho's final
partial-live and SD count-only metadata remain correct. Exact live
deployment verification is the remaining publication gate.

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
