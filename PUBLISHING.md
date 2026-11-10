# Publishing an article across the websites

Use this runbook when bringing a new piece from Substack or a project repository into
The Margin of Error and the personal articles index. Preserve the author's prose, subtitle,
citations, captions, and footnotes, incorporating any edits explicitly requested by the author.
Do not replace the article with a generated summary.

## Repositories and destinations

| Repository | Branch | Responsibility |
|---|---|---|
| `margin_of_error` | `main` | Article, local images, homepage, archive, RSS, and publication deployment |
| `hanshanley.github.io` | `master` | Personal site's `/articles/` index, driven by `_data/writing.yml` |
| Project repository, when applicable | Check its current branch | Analysis code, datasets, figures, and interactive tools |

The publication is at `https://www.themarginoferror.com/`; the personal index is at
`https://www.hanshanley.com/articles/`. For the congressional-language project,
the code lives in `congressional_record` and the existing interactive dashboard is at
`https://www.themarginoferror.com/congressional_profanity/`.

The UK evidence project lives in `hanshanley/uk_decline` and is published at
`https://www.themarginoferror.com/uk_decline/`. Deployment checks out its `master`
branch, installs its small `requirements-site.txt`, and builds the saved figures,
downloads, and methodology directly into `public/uk_decline/`. The topic pages
embed their charts directly, without an iframe or a dependency on the personal site.
The UK project refreshes supported sources weekly; this publication picks up
successful saved updates during its twice-daily deployments.

The collective U.S.–China analysis is staged at `/china-us-relations/` from
`hanshanley/china-us-relation-change`. Deployment runs its offline
`scripts/build_exchange_publication.py` against the committed public snapshots.
It includes students, travel, immigration, goods/services trade, language, business and public
Weibo research aggregates, never raw posts or source PDFs/workbooks. For local
validation, stage the same export before `npm test`:

```bash
../china-us-relation-change/.venv/bin/python \
  ../china-us-relation-change/scripts/build_exchange_publication.py \
  --output public/china-us-relations
```

The public manifest records the source revision and complete-data checksums.
Travel keeps historical all-mode arrivals separate from recent NTTO air-survey
estimates; the 2026 air estimates cover January-June only. Immigration keeps UN
resident-stock benchmarks separate from fiscal-year permanent-resident grants,
and birthplace separate from nationality. Language defaults to actual
Chinese/Japanese/Korean college course enrollments, not global AP participation.
School enrollment estimates and reported high-school program availability are
separate dated snapshots, never a combined national learner count.
The exchange explorer has geography, direction, measure and display controls;
Travel & tourism has its own direct visitor-arrival view. Immigration has a
separate page for fiscal-year permanent-resident grants, not visas or visitor
trips; birthplace histories and the FY2025 nationality snapshot are not spliced.
The remaining topic pages have indicator selectors. Charts redraw for the screen rather
than requiring horizontal scrolling. Annual 2025 data and separate 2026
partial-year observations retain their actual periods; older series are not
extended artificially. Definitions, source restrictions and full tables remain
available, including without JavaScript. The website recolours
previews, while links marked `data-original-chart` retain the original Substack
and Margin of Error download backgrounds. Generated `.website.png` copies use
PNG deflate compression level 9 without quantization, resizing or changes to
decoded pixels; original image files and download URLs remain unchanged.
Adding an analysis tool does not
create an article or require a personal-site writing-index entry.
Prepend new Interactive analysis entries; only the first preview loads eagerly.

The voter-participation integration is at `/voter-participation/`, with native Astro
markup rather than an iframe. Its project source is `hanshanley/voter-participation`,
pinned to the reviewed revision in `scripts/stage-voter-participation.mjs` and
the deployment workflow. Stage its committed export locally before checking/building:

```bash
node scripts/stage-voter-participation.mjs ../voter-participation
```

The destination `public/voter-participation/` must be empty or absent. The offline
export copies all saved observations and the complete-analysis ZIP byte-for-byte,
records their checksums and source revision, and retains an adapted legacy renderer
for export compatibility. The native page uses the website-owned
`public/scripts/participation-explorer.js` for state histories, national demographic
trends and county/precinct search, selection, zoom and pan. It creates a data-derived preview;
it does not rerun or download source research. Stage a fresh export after changing
the pinned source revision, updating both the script and workflow together.

The author-supplied editorial thumbnail is stored byte-for-byte at
`public/artifacts/voter-participation/voter-participation-editorial.png`.
Use it for the Interactive analysis preview and the explorer's social image,
not as an in-page chart. Keep it outside chart recoloring and the pinned research export.

Resident context uses the independent `participation-data` catalog through
`participation-dataset.js`, not new embedded source tables. Its immutable index
and state shards are byte/hash checked before decoding. The default-closed
disclosure stays below the map, never as another long sidebar list. Native
2024 Census county context remains distinct from election-year boundaries;
conditional local profiles require the exact loaded reference-file hash.
Income-bin intervals are not averaged medians or confidence intervals, and
resident counts never become voter characteristics or turnout denominators.
Keep old values cleared during failures and selection/year changes. Local
fixture proofs are not evidence of publication; separately verify the actual
catalog promotion and production reader without a new site build.

Keep the Methods tab a short overview of the estimation process, not a
source inventory: weighted rates, matched denominators, historical checks
and supported geography. Link directly to the research repository's
`METHODOLOGY.md`; its README, data catalog and reproduction guide organize
the technical details. The
legacy detail/archive markup remains only for existing direct anchors and
download compatibility; normal Methods navigation must not expose it.
Resetting a legacy fragment on tab navigation must also hide the archive.
Check desktop/mobile round trips, legacy links, source-failure behavior and
the short default overview without JavaScript.

The page separates citizen/resident CPS denominators from NC registered-voter
participation. National/state series are not nationwide precinct data. NC has seven
election-year boundary snapshots; missing geometry never borrows a different year.
Additional precinct sources are identified explicitly rather than inferred. A server-rendered 2024
national table, methods, sources, and complete downloads work without JavaScript.
This is an analysis tool, not a new essay, so it needs no personal-site writing entry.
Publication was explicitly approved on November 4, 2026. Publish the reviewed
integration to `main`; pushing `main` deploys the site automatically. Source
updates remain pinned to reviewed snapshots rather than following live research changes.

The live additional-participation reader explicitly enables `nativeCountyParents`.
Local early/returned views require an explicitly qualified matching source frame.
Nevada's native follow-up shows four distinct unofficial county snapshots,
with thirteen unknown county counts on the unchanged seventeen-county context.
Keep Washoe's earlier count and native clock separate from the three new reports.
Do not sum those different clocks into a state result, replace an unknown with
zero, or use contest Times Cast as a county denominator. All analysis rates
remain withheld. Its existing provider early/returned frames are separate and
unchanged; native counting groups are not newly approved precincts or modes.
Never reuse all-method ballots, town VV, TOTAL TURNOUT, Cards Cast or another
unqualified measure for an unsupported mode. Keep Available/official defaults,
all native inputs and every legitimate provider/West Virginia mode unchanged.
The sidebar must explain missing mode qualification, not imply no data was
ingested or show an unrelated full-election count. Alaska/DC use a shared
loader and separately mode-gated precinct paths, not separate county exports.
Its default remains the frozen legacy source frame so old county-context exports
reproduce unchanged. `scripts/native-county-parents.mjs` verifies Idaho's 44 and
The separately explicit `minnesotaCompleteNative` live opt-in advances only
Minnesota to the November10 native snapshot: all87 counties/all4105 rows,
including26 newly reported rows and32 observed zeros. Preserve all60 component
conflicts/six electorate excesses, qualify only73 source-registration fractions,
and keep every precinct analysis rate null. The full coordinate arrays and
prior13619 pair decisions are reused exactly; new properties are not geometry
repairs or certified legal precincts. Retain the prior Minnesota reader,
references and downloads. Publish the entire new scientific packet and large
native reference externally before activation; do not copy it into the
already-near-limit Pages payload or infer counts from Estimated Voters. `scripts/native-county-parents.mjs` verifies Idaho's 44 and
North Dakota's 53 native county parents, independent ballot totals and complete
2026 Census county identities. Twin Falls' conflicting registration frame and
all North Dakota rates remain withheld. The browser verifies the compressed
geometry hash before using these new joins; other county layers retain their
separate original reviews. The versioned complete download under
`participation-county-parents/20261109-01/` includes every query/hold, sufficient
originals, reference geometry and a dependency-free offline Node reproduction.
Its packaging command refuses to overwrite an existing version.

Alabama's live opt-in joins all67 already-held native county Ballots Cast by
literal county names to the full checksum-verified2026 Census county reference.
Native county codes are election ordinals:01 Jefferson is FIPS01073, not01001.
Keep old county IDs, native registrations, printed percentages and clocks;
all analysis rates remain null and source timezone unknown. Reporting is not
certification, independently deduplicated people or new precinct coverage.
The default legacy reader and existing early/returned frames must remain unchanged;
without a provider frame, never reuse the new all-method counts under those modes.
The new complete analysis must include the full native workbook, selected
county/state factual fields, all sufficient inputs, queries, code and tests;
exclude acquisition headers and publisher application code.

Minnesota's current opt-in uses the separately frozen November7 follow-up,
not the older75-county export or the page's Estimated Voters figure. All87
county decisions and4105 native unit rows remain:84 complete counts, three
partial subtotals and26 unreported statistics. The explicit `available` frame
must supersede retained older records without modifying their frozen hashes.
Use the same snapshot in county and unit selectors and the precinct count map.
The separately checked native September18,2026 reference preserves all4105
full polygons and joins by native countycode/pctcode and separate VTD/FIPS
fields, not guessed abbreviations. All full native shapes are valid with no
positive overlap;16 invalid older generalizations are not reused or repaired.
The1,723 differing source/reference names remain literal and separate.
All4079 reported counts/26 unknowns retain null precinct analysis rates.
Keep the separately qualified provider early/returned frames distinct.
Native county IDs are not FIPS: join case-insensitive names with only the Census
`County` suffix removed, preserving both names and the full checksum-verified2026
county context. Source-registration fractions require complete native data and
zero component conflicts/electorate excesses;71 pass. Retain all other source
fields, zero/unknown distinctions, the results-page clock/timezone gap and the
separate November2 registered-only snapshot. No exact statewide count, repair,
normalized ballot modes, unique-person count or demographic allocation is inferred.
Keep the full9.2MB reference external through the immutable version tag; the
public index verifies its bytes/SHA before rendering. Local loopback tests may
stage only that exact unpublished artifact explicitly; production never overrides
its reference request. Remember States zoom as well as controls across tabs so
returning from Precincts redraws the previously selected county layer.

New Hampshire keeps four native city sources and all 37 ward rows distinct.
The Precincts tab maps Manchester's 12, Concord's 10, Nashua's nine and Dover's six ward counts on
current official municipal context, not newly certified 2026 legal precincts.
Manchester uses 2022 GIS / lines effective December 21, 2021. Concord's city
approval is November 8, 2021; its `PubWebGIS2020` service name is not a boundary
vintage. Independent coordinate checks use the server-declared inverse
Esri108190 datum operation, not a null-offset approximation. Retain all six
Manchester and fourteen Concord native overlap pairs without repairs.
Nashua uses the independently city-published adopted/effective December28,2021
Ward polygon layer7, not proposed boundaries, polling points, blocks or parcels.
Its current complete map separately prints October2026. Preserve all source
amendments, Ward3/4/8 component disagreements +1/-2/-1 and separate federal-only92.
The six Dover rows use the separately qualified state reference below. The default state view retains
the four-city municipality context, with other areas unknown. Preserve native
boundary overlaps, Ward 7's 85-ballot source conflict and separate federal-only
counts; no source repair, allocation or turnout rate is enabled. The complete
ward release includes every prior city original, full ward-reference inputs,
all mapped/held decisions and exact offline reproduction.

The Dover extension retains all31 earlier ward features and adds six direct
state-published2022 NHGRANIT references, not private named-map or parcel geometry.
Use literal district labels, not FID-as-ward or nativeFIPS17010-as-county.
Native3437/inverseESRI108190, all1987 vertices/cyclic edges and15 native pairs
remain checked at strict1e-9degree tolerance. All37 native ward count rows now have references; source registers, printed
fractions, disagreements and separate
federal-only counts remain unchanged. No source repair, allocation or new rate.

Massachusetts adds Boston/Somerville source counts, not statewide/county totals
or unique-person turnout. Boston's 185,569 native Times Cast is separate from
summary Voters Cast 556,369 / registered 0 / N/A. Somerville's printed 64,597
ballots and 56,008 registrations remain literal; its page/PDF status labels
disagree. All 307 reporting rows now join direct references: Boston275 and
32 original city-declared Somerville polygons, without clipping remainders.
The earlier303-reference release stays intact. Somerville's2023 metadata
revision/2020 Census basis is not a certified2026 boundary vintage. Preserve
the exact native US-survey-feet WKT, not rounded EPSG2249, and the declared
inverseESRI108190 operation. Duplicate native IDs require literal Ward/Precinct
identities; they must not erase the separately reported A units.
The municipal frame retains all 351 source decisions and displays 350 valid
originals; invalid Wayland is held, not repaired. Per-product datum operations
and full numerical queries reproduce offline. Keep all analysis rates null,
source modes separate, existing routes intact and Methods short.

The live opt-in additionally reads Michigan's explicit Bay and Isabella county
parents through `scripts/michigan-county-parents.mjs`. It preserves all 63
reporting-unit rows, Bay's 43-versus-35 reporting counter and Isabella's 22-ballot
election/House-scope difference; both rates and analysis denominators stay held.
The partial join names exactly two observed FIPS within the full checksum-verified
83-county 2026 reference. Other counties remain missing, not zero. Selecting one
clears the previous county's counts rather than displaying stale detail.
This explicit Michigan-only partial scope does not relax Idaho/North Dakota's
complete-inventory checks or the default legacy reader. Version02's complete
two-query archive retains all sufficient originals, full tables, reference
geometry and offline code; version01's 97-query archive remains unchanged.

The same live opt-in exposes Maryland's complete 24-county-equivalent **Cards
Cast** report through `scripts/maryland-county-cards.mjs`. These are source card
counts, not qualified cast ballots or unique voters; every analysis denominator
and rate stays null. Native Eligible Voters, printed percentages, reporting
counters and the November 8, 7:44 p.m. clock remain unchanged. Counters do not
become precinct records. Baltimore city stays separate from Baltimore County;
Saint Mary's / St. Mary's has one explicit reviewed alias. The full 2026 Census
reference is checksum-verified, not certified election-precinct geography.
`participation-county-cards/20261109-01/complete-analysis.zip` retains all 25 native
county/state queries, the full original PDF, accepted independent grid, complete
reference, code and exact network-free reproduction. Neither this integration
nor county contest-count fallbacks establish nationwide voter participation.

D.C.'s 144 precinct observations use the already-reviewed official 2026 app
reference and distinct native ballots/registration, not Council-chair votes.
The participation view checks each identity and exact source fraction before
drawing. These are provisional election-night fractions, not final, population
or demographic turnout. Retain the 2019-named reference attribution and withheld
overlapping strips: counts describe whole precincts, not clipped-area allocations.
The existing complete D.C. original-source ZIP stays directly available.

Virginia's 710 existing current-reference joins expose literal `ballotsCast`
counts only. All 710 values independently match the native locality field;
260 differ from the distinct `voterTurnout` field, which is not substituted.
The browser verifies the compressed map checksum before decoding and checks
native precinct identities and held rates. Native registrations are not rate
denominators. Preserve all 1,819 exclusions, separate source clocks, original
ZIP and the warning that current references are not certified election-day
boundaries. Do not regenerate or replace this already-qualified source.

`public/participation-reporting-units.json` separately enables Alaska's523,
Hawaii's496, Arizona's1763, Arkansas's2768 and Wyoming's432 already-reviewed
reporting-unit observations. The precinct view
checks the pinned compressed data hash, retains every native unit/key/count
and exposes selection, search and complete originals without drawing geometry.
Pooled/federal/overseas/VSC units, source zeros and the Hawaii source discrepancy
remain distinct; no participation rates or boundary joins are enabled.
The versioned `participation-reporting-units/20261109-02/` inputs preserve all
4963 native CSV records and fields, including 83 missing ballot totals. Missing
counts display as not supplied, never zero; actual native zeros remain zeros.
`scripts/build-reporting-unit-counts.py` verifies the original checksums and
refuses to overwrite a generated version. Complete original query ZIPs remain
linked alongside the full browser JSON; observed unit sums are not presented
as statewide or all-mode totals.

The complete site exceeds GitHub Pages' 1 GB limit when bulk participation downloads
are duplicated in its artifact. `scripts/prepare-participation-pages.mjs` verifies
CSV/ZIP downloads and jurisdiction-detail JSON against the version-pinned
`voter-participation-data-20261104` GitHub release before removing only their build-output
copies. Original staged exports remain unchanged. Interactive JSON stays on the website.
The publishing step rewrites static download links, including no-JavaScript fallbacks;
the native renderer also routes dynamically created links. `/participation-downloads.json`
records every relocated path, complete file size, SHA-256 and download URL.
Refresh the generated participation export after changing shared download routing,
even when the pinned research revision is unchanged: its compatibility `app.js`
embeds the router. A stale local export must not become an artifact-check exception.
New research snapshots require a new release tag and byte-verified assets, not replacements
of existing release files. Run the preparer after the normal build to reproduce the
Pages artifact; `--upload` adds missing assets to the pre-created release without
overwriting existing files. Publication fails on any missing or changed release asset,
or if the resulting site exceeds 1 GB.
The cap applies to both file contents and the actual uncompressed tar artifact,
including headers and block padding. Preparation streams a GNU-format tar through
a byte counter before upload; passing the summed-file check alone is insufficient.

Context09's fifteen redundant geometry copies also use their complete originals at
fixed revision `2f839e94dcbef8f35786bc7f8184f2b844ebaaf4`. Full byte/hash verification
precedes removing only build-output copies. Together with the existing relocations,
the download manifest originally contained 432 complete files; no archive or source export
is reduced or replaced.

Four archived nationwide `snapshot.json` files from November 4, 2026
(`20261104T143957Z`, `20261104T144145Z`, `20261104T144402Z`, `20261104T152630Z`)
now use their complete originals at the same pinned research revision. Preparation
verifies all 16,260,811 bytes before removing only redundant build-output copies;
their sources, complete archives, other snapshots and current interactive inputs
remain unchanged. The shared router and standalone compatibility renderer both
retain the exact pinned URLs. The complete relocation manifest now contains
436 files. Do not broaden this rule to unverified snapshots or change the source pin.

New releases have server-enforced immutability. Create each as a draft, attach
and byte-verify every complete query asset, then publish the draft; assets and
its tag cannot be changed afterward. This applies only to future releases:
the existing bulk release and previous complete downloads stay unchanged.
Record the actual release `immutable` flag rather than calling older mutable
releases server-locked.

The twenty-two reviewed November 6 county-context ZIPs likewise use their complete,
version-specific published release assets. Preparation downloads and verifies every
entire archive against its original staged bytes before removing only the redundant
build-output ZIPs. Context review JSON, source records and interactive geometry stay
local; all historical downloads remain available. Unreviewed context versions are
not relocated automatically.
Context10 through context22 have respectively 16, 16, 16, 17, 17, 18, 18, 18, 18, 18, 18, 18 and 18
redundant geometry copies that use their complete originals at the respective
fixed context-source revisions. Preparation verifies every full file before removing
only those build-output copies; the original interactive geometry, current review JSON
and all other historical geometry copies stay local and unchanged. Each complete
historical query archive also retains its entire original geometry inventory.
Context10/11 relocation saves 11,271,562 redundant build-output bytes while keeping
the current interactive geometry and every complete historical query unchanged.
Identically named files at distinct commit-pinned paths are verified
separately; assets within the shared bulk release must still have unique names.

Historical NC year-table JSON uses the complete originals in the same pinned
research commit instead of duplicating them in Pages. Both the native and adapted
legacy readers use the shared download routing. Preparation verifies every remote
table's full byte count and SHA-256 before removing only its build-output copy;
geometry and other interactive JSON remain local. These relocations are included
in the existing download manifest. Pages deployment has an enforced ten-minute
maximum; requesting a longer timeout does not extend it.

After `npm run build`, serve `dist/` with `npm run preview -- --host 127.0.0.1
--port 4321`. Run the source-matched interaction checks with the existing research
Python environment (Playwright/Chromium required):

```bash
../voter-participation/.venv/bin/python scripts/check-participation-browser.py
```

For county-context checks reading explicit `.json.gz` downloads, use
`python3 -m http.server 4321 --bind 127.0.0.1 --directory dist` instead.
This matches Pages' `application/gzip` response without `Content-Encoding`.
Astro preview adds `Content-Encoding: gzip`, causing browser auto-decompression
before the reader's explicit gzip decoder and a preview-only fetch failure.

The check covers state time-series values, map orientation, selection, zoom/pan,
precinct counts, deep links, minimum-registration suppression, unavailable
boundary years, current reporting, complete-download endpoints, mobile overflow,
and no-JavaScript/failed-fetch fallbacks. Optional `--screenshots /path/to/output`
captures the desktop and mobile views.
The map accepts ordinary wheel/trackpad scrolling and two-pointer pinch gestures,
alongside buttons and keyboard navigation. A double-click after a feature fit
zooms around the fitted view instead of reusing stale screen coordinates.
Browser checks exercise wheel, touch pinch and actual chart-path continuity.

The regular explorer uses one year selector for presidential and midterm elections,
including 1994 even when a selected demographic series has no estimate. An explicit
gap message links back to available overall participation rather than hiding that year.
It includes a `2026 · Provisional` year option in States and
Demographics. State views explicitly select official administrative ballots,
in-person early voting or returned mail, without pooling them. Map shading shows
coverage when participation coloring is selected, rather than implying comparable turnout rates. Demographic counts select
a state and voting mode, retain source dates and never enter CPS turnout-rate lines.
Source-coverage tables and complete-download links live in a Methods disclosure.
Historical chart ranges and tick labels use only actual nonmissing plotted observations;
demographic groups use directly labeled panels instead of overlapping group lines.
Alaska and Hawaii have separately fitted conic projections; state labels use geographic
anchors and Northeast callouts rather than bounding-box centers.
Citizen-turnout chart lines break before 1994, not between 1994 and 1996:
the Census voting FAQ dates consistent CPS citizenship measurement to 1994.
The display corrects the older pinned export's overbroad pre-1996 warning without
rewriting that immutable export.
Adjacent observed years at survey-definition boundaries have dashed, labeled
connectors rather than unexplained holes. Solid lines still stop at those boundaries;
genuinely missing election years remain unconnected.

Zooming into North Carolina in Auto detail reveals election-year precinct shapes.
Selecting one replaces the state-history panel with the selected precinct's counts
and 2002–2024 history. The Precincts view also supports group-specific histories,
count tables, suppression and year selection without dropping the precinct ID.
`scripts/build-precinct-histories.mjs` verifies the original per-year export checksums
and builds small, county-sharded indexes during `npm run build`.
Histories match the official county + precinct identifier, not constant geography
or a stable electorate; no boundary crosswalk is claimed. Missing years and
small/inconsistent rates are not filled. Historical precinct participation outside
NC remains unavailable; county/district context is not labeled as precinct turnout.

The nationwide local supplement contains 67,525 EAC reporting-unit observations for
all 50 states and D.C., every even election year from 2004 through 2024. These are
county, municipal and statewide administrative units, not nationwide precincts.
Early rows without a source jurisdiction ID retain election-specific archived CSV
row identities, not name-only cross-election matches. Duplicate display names remain
separately selectable with their election and source row; their counts are never merged.
The map uses matching election-year Census boundaries; Wisconsin and New England
use county subdivisions where available. Selection exposes participation,
registrations and the complete available unit history. Registration matches now
include 2008 A1 and separate 2010/2012 NVRA sources, including the revised 2010
Texas and Illinois files. Source-specific active/inactive definitions and comments
are retained; unmatched or invalid denominators remain missing.
Alaska's statewide office is never allocated into boroughs. Illinois county offices
and Jackson County, Missouri, are not painted onto entire counties because separately
administered cities can change the reporting area. Unmatched and ambiguous units
remain in the complete dataset and sidebar, not silently discarded.

`scripts/build-local-participation.py` verifies original EAC checksums, joins
registrations only on exact source identity, and records Census-source checksums.
The committed compressed state and geometry shards are under
`data/participation-local/20261104T220000Z/`; `checksums.json` covers every output.
`public/participation-local.json` pins the runtime to their immutable Git commit on
raw GitHub, whose browser CORS is verified in interaction checks. This avoids
duplicating another 74 MB in the size-limited Pages artifact. Browsers decompress
the gzip JSON shards; a failed fetch/decompression leaves an explicit error and
the complete CSV-gzip download available. No original staged research export changes.
The CSV contains every observation, source note, reporting basis and missingness
flag, not merely coverage metadata. `coverage.json` includes every state and
historical election-year combination, including unsupported years and provisional
2026. A history key standardizes source names alongside the reporting ID, but
does not establish stable boundaries. National precinct ingestion remains unfinished.

The 2004/2006 extension uses the EAC's September 2026 V2 jurisdiction-level series,
not the county-collapsed file that equally allocates some cross-county jurisdictions.
The original 136 MB workbook is preserved in the immutable
`participation-sources-20261104-late` release. Its URL, size and SHA-256 are in the
local index; the unmodified guide and all 2004/2006 source columns are in `originals/`.
No election-year geometry is verified for these two years, so only counts,
source-method detail and reporting-unit histories are exposed. These years count
ballots counted; the 2008–2018 EAC question counts cast ballots whether counted
or not. Dashed chart connectors identify definition transitions.

The current 2026 supplement is separately pinned by
`public/participation-current/latest.json`. Refresh it with the existing research
environment and `scripts/collect-current-participation.py --output
public/participation-current/NEW_UTC_TIMESTAMP --previous
public/participation-current/PREVIOUS_TIMESTAMP`. The collector refreshes all
50 states/DC, retains complete previous source datasets after failed/regressed
sources, and only publishes its pointer after all local audits pass.
The saved local coverage is 292 counties (NC, NE, NM, SD) and 4,290 source rows
(NE, NM, SD), not nationwide precinct coverage. County sums reconcile to the
same-capture state totals; individual fractions additionally require both ballot
and electorate row sums to reconcile. Nebraska rows fail that allocation test;
South Dakota vote centers and special rows are counts only. Duplicate source
names retain distinct snapshot-local row ordinals, not invented stable IDs.
New Mexico's electorate retains its source label, "Eligible Voters"; it is not
silently treated as registration or Census CVAP. County shading uses explicitly
contextual 2024 Census geometry with unique state/name matches when that detail
level is explicitly selected. No longitudinal precinct crosswalks are claimed.
Complete ZIPs include all normalized datasets, county/precinct CSVs and raw source captures; the smaller
browser JSON omits only duplicated bulk datasets.
The current browser JSON and complete downloads are served from their pinned
`c65c8b262cb421fc094578885c0c20f6d120d776` raw-GitHub revision.
`participation-downloads.js` centralizes that exact snapshot route.
The Pages preparer fetches and byte-verifies every current file before removing
only its build-output copy; the staged originals stay intact. This reserves
space for the other analyses' CI-generated assets, which can exceed local copies.
New snapshots require first publishing their immutable data revision, then
updating the route and validation together. Missing, truncated or changed remote
data must stop publication, not fall back to metadata or drop observations.

The default color layer is red/blue election results, including with precinct detail selected.
Where a verified local candidate-return join is missing, retain the whole-state result color;
never substitute participation shading, force gray, or disable result colors. The separate
Participation option retains the audited precinct-rate map and neutral unsupported areas.
The 2026 result snapshot in `public/participation-results/` covers all 50 states and
435 voting House districts. District party votes reconcile exactly to national totals.
State colors use D-minus-R divided by all contest votes, not statewide winners, House seats
or turnout. DC has no voting House district in this source. Refresh separately with
`python scripts/collect-participation-context.py --results-only`; invalid identity,
missing/duplicate districts or failed reconciliation must leave the previous pointer intact.
Its complete CSV/ZIP downloads retain every state/district result and the original source.
`scripts/build-precinct-results.py` builds separately audited candidate-result layers, newest first.
It retains complete source captures and candidate tables (including unmapped and administrative rows).
The 2026 NM joins require county-scoped unique precinct sets and exact candidate/county reconciliation;
suppressed counts are missing, never zero, and suppress the corresponding county's map.
The 2026 NC residential reporting units exclude separately reported early/mail/provisional units;
label that partial ballot scope explicitly, and do not allocate administrative counts into polygons.
The NYT 2024 release adds precinct/municipal reporting areas across 49 states and DC, not Alaska.
Map only geometry identities whose candidate counts reconcile exactly to the complete national CSV.
Retain mismatches in the audits and full downloads. Approximate boundaries are marked per feature,
New England includes townships, and the complete original state caveats and NYT C-UDA terms must
accompany redistribution. Attribute The New York Times in the visible UI and retain downstream terms.
`public/precinct-results.json` pins the immutable data revision and complete GitHub release ZIP;
bulk geometry lives under `data/precinct-results/`, not in the size-limited Pages artifact.
`PRECINCT-COVERAGE.md` and `public/precinct-coverage.csv` track all 1,632 state/election cells,
2026 first through 1964. Regenerate with `python scripts/build-precinct-coverage.py`.
Partial coverage is not completion. Do not mark a cell complete without validated live coverage.
After the full live browser check passes for the pinned snapshot, set its pointer's
`publication` to `live_verified_partial` and regenerate the worklist. New snapshots must
omit that flag until their own live checks pass; acquired data alone is `snapshot_ready`.
The pointer's separate `source_reviews` preserve acquired, reconciled but unmappable data.
Delaware's 2026 review includes all 530 House reporting districts and complete originals in its
own full ZIP. Its official boundary-service metadata dates the shapes to November 2023,
with reporting-only/boundary-only IDs, so no shapes are relabeled or mapped as 2026 precincts.
`scripts/build-current-precincts.py` joins the RGIS July 2026 NM release to the
saved election-night source using county + explicit `VTD_NUM` (Voting District Number).
Eight updated Sandoval shapes retain older Census VTD/GEOCODE values; those older
fields are preserved but never used as the new precinct numbers. Whole county
precinct sets must match uniquely and source ballot/electorate totals must reconcile.
The audited map contains 2,177 shapes, with 1,202 colored precincts across 30 counties.
Bernalillo, San Juan and Santa Fe remain entirely neutral because their reporting
sets differ; six additional matched precincts have small or unavailable rates.
These are July reference boundaries, not certified election-night geography, and
matching IDs do not establish boundary stability across elections. No county or
state values are allocated into precincts. Other states are not claimed as covered.

The complete geometry, joined rates, county-set audit, checksums and original GIS
ZIP/metadata live in `data/participation-precincts/20261104T230000Z/`.
`public/participation-precincts.json` pins that data's immutable Git revision.
Complete existing 2026 reporting downloads retain every unmatched source row.
Browser checks compare all 50 default state result colors with the actual saved party
margins, verify state fallback under every unsupported detail selection, and compare
every explicitly selected participation rate with the audited GeoJSON. They assert
neutral unsupported participation fills, exercise matched and mismatched selections,
and verify desktop/mobile behavior, historical NC coverage and failed-fetch fallbacks.

The reviewed supplements live in `public/participation-context/` and
`public/participation-methods/`; neither modifies the pinned historical export.
Their `latest.json` pointers select immutable, checksummed snapshots. The context
supplement contains the expanded seven-feed official 2026 snapshot (48 jurisdictions
with observations, 47 with early/mail observations, 11 with nonzero demographic
breakdowns), attributed partisan context and Census geometry. Party colors are
D-minus-R shares of all source-reported contest votes, not participation; House
aggregates are not statewide winner margins. The 1994 Clerk transcription reconciles
exactly to all three national sums; Louisiana's untabulated votes stay missing.
The 2024 House parser must reconcile to all 50 state recaps and national party/total
sums, including source-specific treatment of fusion labels and write-ins.
The FEC parser handles the separate state-name/code columns in 2010 and requires
all 50 voting states in each House summary. Presidential derivations reconcile
state by state; New York in 2000 remains missing because its party residual is
negative, without discarding the other 50 reconciled jurisdictions.
County joins require complete one-to-one geographic identity and provider-total
reconciliation; rejected collections remain uncolored. California currently passes.
The 119th-Congress districts are used only for 2024 results, never 2026 redistricting.
Zoom reveals supported county/district detail and NC precinct participation; gray
outlines without matched results are explicitly geographic context, not zero votes.

Voting-method history covers national CPS observations for every election in
1996–2024 and state EAVS reports in 2008–2024. National subgroup method estimates
cover 2018–2024 and use a separate source-matched group selector. These shares are
among reported voters or matched administrative units, never the eligible population.
CPS histories break at the 2004 questionnaire and 2018 universe changes; EAVS uses
unconnected points because coverage and definitions vary. State percentages match
each method numerator to reporting units with valid positive participation totals;
unavailable flags override contradictory numbers. Preserve missing codes, source
comments, F2 participation bases, ward identities and statewide/local exclusions.
Provisional and early in-person are distinct F1e/F1f fields; 2008 F1g is Other.
Never sum overlapping mail, absentee, military/overseas and provisional categories.
Earlier unsupported observations remain missing. The national history and complete
downloads are server-rendered for no-JavaScript use.
The compact methods panel shows reported categories first and retains missing
categories in a disclosure. Its history axis starts at zero and adapts to the
observed range; a new state's default method prefers an actually reported share.

To collect a new draft without replacing a completed snapshot, use the existing
research Python environment and a fresh snapshot ID. `--source-snapshot-id` copies
an earlier raw cache while preserving original source timestamps and checksums:

```bash
../voter-participation/.venv/bin/python scripts/collect-voting-methods.py --export
../voter-participation/.venv/bin/python scripts/collect-participation-context.py
../voter-participation/.venv/bin/python -m pytest -q scripts/test-participation-collectors.py
```

The complete-methods ZIP contains every normalized national/state/jurisdiction
observation, registered original, instrument/codebook, manifest and collector.
The context ZIP includes all geometry, returns, the actual seven-feed nationwide
snapshot and originals. These are complete datasets, not metadata-only downloads.
Rebuild before browser checks so the preview actually serves the current source.
Review newly collected drafts before updating the published snapshot pointers;
collection alone does not approve a new deployment input.

The 2026 NC source-audit panel uses an immutable preliminary snapshot from the same
pinned project revision. It renders statewide reporting and race counts without
JavaScript; the shared `current.js` adds county, race/ethnicity/sex and request-type
filters. Election-night reported ballots/registrations are explicitly incomplete.
The earlier absentee demographic counts overlap that feed and are never added to
it or presented as group turnout rates. Historical series still end in 2024.
For frequent updates, refresh the research source with
`python -m scripts.current --update-downloads`, which rebundles saved historical
data without downloading or recomputing it. Research GitHub Actions also collects
and commits validated snapshots every 15 minutes during November 4–5 UTC, 2026;
see the project's README for the exact window and manual trigger. Website exports
remain pinned: after checking a new source commit, update both source pins and
stage a new export. Collection does not deploy this website. The page shows a saved
snapshot, not an automatically refreshing live feed.
Each complete snapshot ZIP includes all observations, original public
aggregate files, timestamps and checksums; no individual voter records are used.

The pinned export retains `nationwide.js` and `data/nationwide/` byte-for-byte, but
the native page's website-owned renderer controls the source-audit panel and uses
the supplemental nationwide snapshot when present. It checks all 50 states and DC against civicAPI's public
aggregate early-vote feed and exposes only reported state/mode demographic
breakdowns, not requested ballots or party preferences. Verified state-office
ballot feeds remain separate, with explicit denominator definitions.
The complete 51-jurisdiction coverage table, source dates, initial Georgia race
chart and all five full-download links are server-rendered, including without
JavaScript. Missing provider coverage is not a claim of universal unavailability.
The NYT reference is methodological only. Do not ingest, republish or train on its
modeled figures or supplied article tables.
The research workflow requests nationwide and NC captures independently every
15 minutes November 4–5 UTC, then hourly November 6–19 UTC; GitHub can delay starts.
A source failure retains its last valid observations with their original dates
and an explicit retained/failure status. Every full nationwide source ZIP also
includes original bytes for any retained observations. Collection commits new
research data but does not deploy this website; reviewed website pins remain
intentional.

The independent-method disclosure stages `model.js` and `data/model/`. Its
participation-only historical experiment uses public Census citizen-denominator
rates, with prior-year-only, same-election-type training and a carry-forward
comparison. It is not a 2026 demographic turnout estimator: the first candidate
fails its historical screen, and all 2026 modeled rates remain withheld.
The server-rendered summary and per-year validation table, explicit limitations,
full method, every prediction/error, inputs and ZIP downloads work without
JavaScript. A category selector adds age/race/sex/education error diagnostics;
neither website staging nor election-night collection trains on incomplete 2026
feeds. The richer public-microdata model in the protocol is not yet fitted.

The separate input-audit disclosure stages `cps.js` and `data/cps/`. It exposes
independently parsed 2022 and 2024 public Census voting-survey inputs, not NYT
estimates. The overall survey counts, reported-voting rates, unknown-outcome
shares and published-table reconciliation are server-rendered; the selector adds
age, exclusive race/Hispanic origin, sex and education diagnostics. Unknowns
(including supplement noninterviews) remain separate from reported nonvoters.
Reported voting uses all included civilian adult citizens, not only known
yes/no respondents. These self-reports are not validated turnout, and published
table agreement audits parsing rather than predictive performance.
Every observed joint cell, every projected marginal, all comparisons and a
complete ZIP with anonymized public survey originals, documentation and source
hashes are downloadable. Fine cells are sparse research inputs, not precise
subgroup estimates. Replicate-weight uncertainty, compatible population inputs
and a frozen confirmation specification remain outstanding. Keep all 2026
modeled turnout withheld; this input stage does not reverse the failed baseline.

The national Democratic/Republican/DSA comparison lives at `/party-platforms/`.
Deployment pins `hanshanley/dsa` to a verified source commit and runs its
offline exporter with the source package and its numerical/image audit dependencies.
It validates the reviewed topic replay, complete claim/source
accounting, and ZIP contents before staging original figures and full-text downloads.
No extraction, fitting, model downloads, or Libertarian partial results run during
publication. For local checks, use a clean checkout of the workflow's pinned revision:

```bash
PYTHONPATH=../dsa/src ../dsa/.venv/bin/python \
  ../dsa/scripts/build_platform_publication.py --output public/party-platforms
```

The output must be absent or empty; do not overwrite a stale export in place.
The Astro page reads `analysis.json` at build time. Its manifest records the exact
source revision and original-file hashes; website-only recolored PNGs do not replace
the originals or their checksums. Dedicated project-generated Margin of Error
variants are used when present; both those originals and the Substack figures
remain byte-preserved. The existing website export maps their registered paper
colours to the current publication paper. Topic search covers representative packets, not
the entire downloaded corpus. This is an analysis tool, not a new authored essay.
The comparison combines broad subject views, source-linked KDE maps, party
overviews, and individual overall/over-time subject charts. Broad views show
absolute shares, distinctive emphasis, and pairwise differences across three
pages. The six expanded density maps retain the artist's numbered examples;
their complete texts and source links come from exported `density_regions`,
not manually reconstructed captions. The primary KDE display is an interactive
canvas: hover previews a reviewed issue, click/tap pins it, and keyboard issue
selection and arrow keys provide equivalent access. Both compared groups show
reviewed source-bound group summaries and paired differences, with their supporting
claims and excerpts. These summaries synthesize selected documents, not independently
certified or exhaustive party positions.
`density-map.json` joins every frozen expanded KDE point to pooled issue
assignments by claim ID, retaining original coordinates, log densities, global
axis limits and common color bound. Pair displays include only those two groups.
All 24 issue labels remain available on the map; the three identity clusters
still stay out of subject rankings. Original annotated maps and numbered evidence
remain in native disclosures, including when JavaScript or the map fetch fails.
Mobile maps use the same responsive canvas, with positions stacked underneath;
archived images retain their original map crop. Mobile overview
charts render the same ordered subjects, weighted shares and unsmoothed differences
as readable bars and values, with a full-chart link retaining sensitivity markers.
Only the expanded analysis is presented: do not render adopted-only controls,
strict charts or strict share columns. There are 21 displayed substantive subjects;
three identity clusters remain in denominators but not charts or rankings.
Each displayed subject shows its two expanded chart modes and written summary.
The original export retains all four PNG chart modes
for research reproducibility; retired dense timeline panels are not publication inputs.
All displayed subjects and chart modes remain available through native disclosures without
JavaScript. Draft local fixtures must set `preview_only: true` in both the
analysis and manifest: the page identifies them, and production validation
rejects them. Replace a draft with a fresh verified export before release.

The bottom of the comparison includes a separate thirteen-caucus snapshot.
After the national export, run `scripts/build_caucus_publication.py --output
public/party-platforms/caucuses` from the same pinned DSA checkout. This offline
export checks the current numerical hashes, reviewed labels, exact ratios, and
source excerpts. Caucus themes are learned separately, not national-party topic
IDs or a timeline. Show one theme at a time, with all thirteen groups ranked by
attention share beside a selected source-backed statement. Bars share an explicitly
labeled scale within each theme, not across themes. On mobile, give each bar its
own line and let readers move between the chart and selected statement. Keep
native theme and statement disclosures without JavaScript. Zero attention is not
opposition. The build tests rendered shares, ratios, ordering, bar scales and
original source excerpts against the verified export.

The reader-facing title is **DSA in Context: Party Platforms and Caucuses**.
Keep `/party-platforms/` and its existing fragments stable. Small copy-link
controls target sections, organization summaries, individual issues, timelines,
ratio tables, and caucus statements/evidence. Map links restore both the comparison
and pinned issue, even before the lazy-loaded map has fetched its data. Native
links remain usable without clipboard access; deep links open the relevant
disclosures. Explicit issue/caucus/map selections update the address without
adding a history entry for every selection; map hover does not rewrite it.

The author-supplied Three Platform Booklets illustration is the
Interactive analysis preview and social image, not an image inside the analysis
pages. Keep it under
`public/artifacts/party-platforms/`, separate from the generated chart export;
preserve its original bytes and do not register it for chart recoloring.
The comparison page leads with a broad view and its interpretation, followed
by party overviews, KDE comparisons, and subject exploration. Party overviews
distinguish pooled attention from stated positions and cite representative claims.
Representative
claim packets are available on `/party-platforms/sources/`, linked from the
selected chart rather than appended to the comparison. Do not add period-discovery
sections, technical diagnostics, or download inventories to these pages.
Use one bottom link to the pinned GitHub source for code, full data and methods;
the Interactive analysis listing shows only Open analysis and Read the essay. Complete local
export assets remain byte-preserved for existing direct links and audits.
Legacy evidence fragments open claim packets; retired methods, downloads and
period fragments go to the pinned GitHub source. All issue selections and
representative packets remain available without JavaScript.

Read each repository's instructions before editing. Work from the repository root unless a
command says otherwise. In this repository, `CLAUDE.md` is a symlink to `AGENTS.md`;
edit the shared instructions once, not through both filenames.

## 1. Establish the source and preserve existing work

In each repository being changed:

```bash
git status --short
git fetch origin
git branch --show-current
```

Inspect local edits and remote changes before proceeding. Do not discard another editor's work,
include unrelated changes in a commit, or force-push. If edits overlap, resolve them explicitly
and preserve the author's latest choices. Never resurrect text the author removed remotely.

Get the actual article from the author: a published URL, a reader-accessible preview link,
or an HTML/Markdown export. Record its title, subtitle, publication date, body, image order,
captions, source links, and footnotes.

Some Substack previews initially show only a loading silhouette. That alone does **not** mean
the article is inaccessible. Try the supplied link in an ordinary anonymous browser with
JavaScript enabled. The preview may also include its full article in `window._preloads.post`.
With the dependencies already installed in this repository, this reads that embedded data
without evaluating scripts:

```bash
node --input-type=module - "SUBSTACK_READER_URL" <<'JS'
const response = await fetch(process.argv[2]);
if (!response.ok) throw new Error(`Source request failed: ${response.status}`);
const html = await response.text();
const { load } = await import('cheerio');
const embedded = load(html)('script#preloads-json[type="application/json"]').text();
const match = html.match(/window\._preloads\s*=\s*JSON\.parse\(("(?:[^"\\]|\\.)*")\)/);
if (!embedded && !match) throw new Error("No embedded preview data; use the browser or an author export.");
const { post } = embedded ? JSON.parse(embedded) : JSON.parse(JSON.parse(match[1]));
if (!post?.body_html) throw new Error("No article body; request an accessible source.");
console.log(JSON.stringify({
  title: post.title,
  subtitle: post.subtitle,
  date: post.post_date,
  isDraft: post.is_draft,
  body: post.body_html,
}, null, 2));
JS
```

Keep temporary source snapshots outside the repository. Do not persist the entire preload
object, cookies, login credentials, or unrelated account information. Do not bypass a login
or paywall. If the author-provided preview still has no body, request an export rather than
inventing the article.

A draft's `post_date` is not necessarily its final publication date. Confirm the intended
date from the author or the published edition, and do not label a preview as published on
Substack just because the independent website is being published.

## 2. Use the right figures

Prefer the project's existing corrected figures when the article uses project graphs.
For the congressional article, the three source images mapped to:

```text
congressional_record/outputs/figures/profanity_per_1k_last50.png
congressional_record/outputs/figures/slurs_per_1k.png
congressional_record/outputs/figures/formal_courtesy_per_1k_last50.png
```

Their local publication copies are under `public/artifacts/congressional-record/`.
Preserve image bytes when copying; measure real width and height with the existing `sharp`
dependency. Supply meaningful alt text, dimensions, `loading="lazy"` for inline figures,
and `decoding="async"`. A homepage thumbnail can reuse an inline graph.

The build generates website-only chart versions in `dist/`, matching the `--paper` colour
in `src/styles/global.css`. Original images in `public/` and the source projects remain
unchanged for Substack and research use. The export replaces only registered, exact
background colours; it preserves dimensions, plotted colours, transparency, and chart data.
Charts get lossless `.website.png` copies, and built pages link to those copies.
Original image URLs remain available with their original bytes.
Register new authored article charts in `src/data/website-chart-images.json`; do not add
photographs, screenshots, or third-party graphics. Staged UK and congressional chart
directories are handled automatically, and their pages use the publication background.

If an image is not available in the project, copy the author's image into a suitable
`public/artifacts/` directory. Do not leave dependencies on Substack image-CDN URLs or
placeholder images. Keep figure order and captions intact.

For congressional charts, check that:

- The data use the current word lists and any necessary historical rescoring has finished.
- Numeric rate axes start at zero.
- Year labels do not extend into the future.
- The final year follows actual recorded coverage, not the machine's clock.
- The latest Congress point is a Congress-to-date aggregate, not an invented annual total.

Do not reconstruct unavailable counts from a screenshot or substitute member-level counts
for the distinct historical series. Do not launch expensive backfills merely to copy images.
Article images are committed publication snapshots; they do not update themselves when the
project's figures change.

## 3. Add the article to Margin of Error

Create `src/content/posts/<slug>.mdx` using the schema in `src/content.config.ts` and an
existing post as a formatting reference. Use a stable, readable slug rather than the
Substack preview's UUID.

Important fields:

| Field | Rule |
|---|---|
| `title`, `subtitle` | Preserve the author's wording |
| `description` | Use the author's subtitle when there is one; do not add an invented promotional summary |
| `publishedAt` | Use the confirmed date in ISO format |
| `sortOrder` | Integer Unix seconds derived from the intended publication date; this controls newest-first ordering |
| `legacyPath` | `/<slug>`, matching the article's public route |
| `originalUrl` | The supplied reader URL or actual published source, not the editor URL |
| `thumbnail` | Local image path, useful alt text, and real dimensions; set `fit: "contain"` for charts that must not be cropped in previews |
| `draft` | `false` only when the author has authorized publication |

Compute the ordering value rather than guessing it:

```bash
node -e 'console.log(Math.floor(new Date("CONFIRMED_ISO_DATE").valueOf() / 1000))'
```

`featured` does not determine the homepage lead. Published entries are ordered by
`sortOrder`, alongside external articles.

Remove Substack subscription widgets, share buttons, image controls, and tracking clutter,
not the author's prose or citations. Keep profanity masking as supplied; never unmask an
already-censored quotation.

Use the existing footnote style with a `footnotes` section, stable note IDs, and working
reference/back links. Long source URLs must wrap on mobile.

Use `artifacts.code` and `artifacts.data` for the source repository and interactive
dashboard. Do not embed a second copy of the dashboard inside the article or introduce
an application server. Keep links to existing tools working.

The current templates intentionally:

- Show the original subtitle without an extra generated homepage summary.
- Omit a duplicate article-header description when it equals the subtitle.
- Avoid repeating that same description in archive and recent-post previews.
- Provide **View archive** after the homepage's recent pieces.

Add a migration record to `src/data/migration-manifest.json` with the source URL, title,
target route, platform, status, and a brief note on locally hosted images.

## 4. Validate the publication before pushing

Use the existing checks:

```bash
npm run check
npm test
git diff --check
```

`npm test` builds the site and runs `scripts/validate-build.mjs`. Update the assertions
for the new latest article rather than removing them: homepage lead/date/thumbnail,
archive order, RSS first item, AI index, article route, local figures, and footnotes.
The homepage keeps one lead story and four recent pieces.

Compare rendered article paragraphs against the source after whitespace normalization.
Confirm every citation and caption survived. Separately verify figure copies against the
project originals.

Check the homepage, article, archive navigation, and footnotes at desktop and mobile widths
(1360 and 390 pixels are the current test sizes). Verify that lazy-loaded images finish
loading, there is no horizontal overflow or JavaScript error, and keyboard navigation works.
Stop temporary preview servers after verification.

## 5. Commit and deploy Margin of Error

Stage only the intended files. Manual commits must be authored as `hanshanley`, with no
Copilot co-author or session trailers:

```bash
git add <intended-files>
git diff --cached --check
git -c user.name=hanshanley -c user.email=hwahhanley@gmail.com commit -m "Publish article title"
git push origin HEAD:main
```

A push to `main` automatically runs `.github/workflows/deploy.yml`. It also stages the
latest congressional dashboard from `hanshanley/congressional_record/site/`.
Do not dispatch a duplicate deploy while the push-triggered run is active.

The congressional and UK projects render their own publication mastheads. Navigation
changes must also update both projects' page generators and tests; regenerate the
committed congressional HTML before publishing. Updating Astro's header alone is not enough.

```bash
gh run list --repo hanshanley/margin_of_error --workflow deploy.yml \
  --limit 5 --json databaseId,headSha,status,conclusion,url
gh run watch RUN_ID --repo hanshanley/margin_of_error --exit-status
```

Match the deployment's `headSha` to the commit being published. On failure, inspect the
failed logs and fix the actual problem. Never force-push to solve concurrent edits, and
never overwrite a newer page with stale generated output.

After success, fetch the live homepage, article route, archive, RSS, images, and dashboard
destination. Verify real content and figure bytes, not just HTTP 200. Search or fetch tools
can serve stale cached pages; use a normal request with a commit-specific query parameter
when checking a just-deployed page.

## 6. Update the personal website

Only after the article's canonical Margin of Error URL works, edit the other repository:

```text
hanshanley.github.io/_data/writing.yml
```

Add the new entry at the top; `_pages/articles.md` groups entries by year and retains their
order within a year:

```yaml
- year: 2026
  date: "11 October 2026"
  short: "11 Oct"
  title: "Floor-Letter Words: The Rise of Congressional Profanity"
  blurb: "The author's original subtitle or approved description."
  url: "https://www.themarginoferror.com/floor-letter-words-the-rise-of-congressional-profanity/"
```

Use the new article's actual date, title, subtitle, and canonical URL. Do not link the
personal index to an opaque Substack draft link. Do not replace existing articles or
manually duplicate the listing in `_pages/articles.md`.

Consult `MAINTAINING.md` in that repository. Its local Jekyll command uses Homebrew Ruby
and bypasses the old Bundler setup:

```bash
export PATH="/opt/homebrew/lib/ruby/gems/4.0.0/bin:/opt/homebrew/opt/ruby/bin:$PATH"
export JEKYLL_NO_BUNDLER_REQUIRE=true
jekyll build --destination /tmp/personal-site-check
scripts/lint-style.sh /tmp/personal-site-check
```

Use a task-specific output directory, not one another process is using. If Jekyll is
unavailable, use the repository's documented installation path when practical. For a
data-only listing update, an alternative is to validate the YAML entry, its ordering,
and preservation of every existing entry, then verify the actual GitHub Pages build
and live rendered page after pushing. Do not claim a local Jekyll build ran when it did
not. `scripts/build-preview.py` only refreshes static preview styling and is **not** a
substitute for building the data-driven articles page.

Verify the built `/articles/` page places the new article first in its year, displays
the right date, and links to the live publication. Then commit only the intended update:

```bash
git add _data/writing.yml
git -c user.name=hanshanley -c user.email=hwahhanley@gmail.com commit -m "Add article to writing index"
git push origin HEAD:master
```

This repository currently uses GitHub Pages' legacy build from `master`, not Margin of
Error's Astro workflow. Confirm its actual configuration when publishing:

```bash
gh api repos/hanshanley/hanshanley.github.io/pages \
  --jq '{status,cname,build_type,source}'
gh run list --repo hanshanley/hanshanley.github.io \
  --limit 5 --json databaseId,headSha,status,conclusion,url
gh run watch RUN_ID --repo hanshanley/hanshanley.github.io --exit-status
```

Verify the live `https://www.hanshanley.com/articles/` listing after deployment. Leave
both worktrees clean except for pre-existing edits, remove only task-created temporary
files, and report completion only after both requested updates are persistent and live.
