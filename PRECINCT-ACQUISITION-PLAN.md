# Nationwide county-first acquisition and publication plan

## Objective and priority

**November 6 priority: participation must be the primary display.** The user's
exact 2026 North Carolina link showed New Mexico's partial precinct layer, while
already-reviewed UF state turnout estimates were buried in Methods. The pending
fix makes participation the default map color and retains counties as default
detail. The regular state view now exposes all 51 state/D.C. UF VEP or VAP
estimates, keeps the national aggregate separate, and labels every value as a
source estimate. Official administrative counts and their native-electorate
ratios remain separately visible; missing denominators are gray, not invented
rates. A county button fits the selected state's verified county observations.
An unsupported NC precinct request never substitutes New Mexico. County/state
values are never painted onto precincts.

Local regression checks compare all 51 state colors/rates in both denominators
and all 100 NC county colors/rates with saved sources on desktop and mobile.
They retain the exact NM precinct values and suppression, historical CPS,
explicit candidate layers, early-count separation and UF display after an
official-feed failure. Seven participation tests, Astro check and build pass;
Pages preparation verifies 94 downloads at 987,378,512 bytes. Four display modes
retain the exact 288-URL / 291-anchor download multiset, all 52 UF rows, five
historical years and 255 scope cells. Production verification is still required
for this display change. No new demographic estimate, county acquisition,
map-source approval or completeness claim is created.

Next acquisition/integration priority is actual participation: surface existing
verified county ballots and compatible denominators before expanding candidate
download inventories. Retain the genuine Maine accounting gaps, separately
scoped D.C., and Philadelphia source-representation restrictions below.

**November 5 security escalation: rewritten history is live verified.** The
user explicitly requested fixing security and continuing acquisition. An isolated
`git-filter-repo --sensitive-data-removal` rewrite removed Google API key patterns
throughout all 297 commits, including older common history. All 4,777 rewritten
blobs (2,746,430,005 bytes) were scanned with zero matches; the current main tree
was byte-identical before download-link migration. All 69 original branch/tag
refs required new commit IDs. The 68 non-main refs were updated atomically
with exact old-SHA leases; main followed only after migrated UI validation.
The first full transfer exceeded GitHub's push-size limit; four verified ancestor
batches transferred clean history without dropping election data. No release
asset was replaced or deleted during this history rewrite.

All 133 migrated raw dataset downloads are publicly downloaded and byte-verified.
The complete 250-link set passes exact equality in desktop/mobile and
JavaScript/no-JavaScript local checks. A pre-existing Vermont participation
filename was corrected to the actual `municipal-participation.json.gz`; the full
native dataset, not metadata or a substitute summary, remains downloadable.
Six new source-secret tests cover plain/binary content, compressed/nested ZIPs
and keys removed from the current tree but retained in history. New push/PR CI
checks all reachable history; Pages also checks tracked source files before
building. Existing GitHub secret scanning and push protection are enabled.
Type-check, build, seven participation tests and 94-download Pages preparation
pass; the unrelated UK topic-card validator still fails 23 versus 16.
Local prepared size is 987,318,238 bytes. Main revision
`ab48cd71228be2354f2cc4a50cdc6a61c9fda0c5` passed Pages run `42127917576`
and full-history security run `42127917557`. Production registry bytes match,
and all four browser modes retain the exact 250 complete download URLs.
All 69 original public refs are verified clean; all 224 assets in 65 releases
are unchanged. The transfer-only staging branch was removed through the API
after Git transport rejected its deletion. See
`data/county-source-reviews/20261105-history-key-remediation-01/`.

**Do not push any old local branch or tag.** Only use rewritten publication
history. The recurring acquisition checkout now uses
`voter-participation-clean-counties-20261105`, based on verified main. Its known
old local refs were translated only after checked-out tree equality checks.
One unpublished branch needed a separate isolated rewrite: its sole tree
difference is credential text in the Bucks linking HTML; all other work remains.
The acquisition clone's 4,818 reachable blobs pass with zero Google key matches.
The earlier `security-remediated-worktree-01` remains a verified publication
reference, not the next acquisition checkout.
GitHub alerts #1/#2 remain open with unknown validity. Revocation still requires
the Google project owner; repository access cannot rotate these copied
county/vendor keys. Historical cached commit views require GitHub Support
follow-up; do not claim that a ref rewrite revoked credentials or erased caches.
The owner/support handoff is saved with the audit; it is not a submitted ticket.

**Dauphin downloads are live verified.** Nineteen full government HTML responses are
preserved in the reviewed public package with successful receipts: the index, eight contest summaries,
the native precinct-progress list, eight precinct/municipality reports and the
declared method-report parent. The House snapshot contains 114,641 candidate
votes (DEM 68,655; REP 45,507; native NONPARTISAN write-in 479), not ballots or
turnout. Precinct and municipality tables are parallel geographic summaries,
not two voting modes. All eight contests and 23 county candidate lines reconcile
separately with 1,597 precinct and 460 municipality observations, retaining
128 and 39 explicit zeros. All five state-House precinct scopes partition the
158 county precincts without overlap; split municipalities are not deduplicated.
The seven CSVs, all 19 screened originals, receipts and portable reviewer form
a 150,018-byte complete ZIP with 30 unique members. Packaged offline reproduction
is byte-identical; eight focused tests pass. The native mail-reporting zero is
commented-out HTML, not observed mail ballots. Ballots, registrations, turnout
and voting-method totals remain unavailable; absent REP rows in HD104/HD105
remain absent. No new map, demographic turnout or certification is approved.
Data/tools commit `171d62f4b5cb4ab776bc0ed504ce2f1d9d7047c8` and immutable
release `voter-county-pennsylvania-dauphin-20261105-01` are published. All eight
public downloads (the complete ZIP and seven CSVs) are byte-identical to reviewed
data, and the archive contains the same CSV bytes. Direct release creation
returned HTTP500; explicit tag creation, a draft release, asset upload and
publication through the update-release API succeeded without replacing assets.
The registry change adds those eight downloads while preserving all 250
existing links, with no map or coverage-ledger change. Type-check and build pass;
Pages preparation verifies all 94 bulk downloads and produces 987,326,060 bytes,
below the 1 GB limit. All four local desktop/mobile and JavaScript/no-JavaScript
modes pass the exact 258-link set, all 52 UF rows, five historical years and
255 historical scope cells. Unchanged map suites were not repeated.
UI revision `7c3a6a97cc34ca7a1afad604f3db538a6f7f3c54` passed Pages run
`42129773154` and full-history credential check `42129773151`. Production
registry and download-manifest bytes match the prepared artifact. All four
production modes independently pass the exact same 258-link set, all 52 UF
rows, five historical years and 255 scope cells. No map or coverage-ledger
change was made. See
`data/county-source-reviews/20261105-dauphin-reviewed-01/` and
`data/county-source-reviews/20261105-dauphin-publication-01/`.
Butler's actual index returned HTTP404; the response and receipt are
retained rather than treating a cached search page as a successful acquisition.

**Berks primary data and downloads are live verified.** The actual county Election
Results page links the reviewed 2026 General Election master dashboard despite
stale primary-election prose on the parent. Fifty-nine screened source responses
retain complete metadata, child dashboards, query inputs, native terms and
receipts. One declared item returned an API403 inside HTTP200; that denial is
preserved, not bypassed or counted as acquired data. Long GET query failures
were recovered using documented POST queries, with exact object-ID completeness.
All 202 separate participation rows reconcile to 143,855 ballots and 275,941
native registered voters; mail 27,931 plus Election Day 115,924 equals ballots.
Early-vote values are all null and the provisional field is absent, not zero.
This is an unofficial ballots/native-registration ratio, not eligible-population
or demographic turnout. All 2,216 full candidate rows match the separate joined
table and native server aggregates: 45 county candidate lines across 15 contests.
The 681 winner-only rows are independently checked against each named candidate's
own votes and contest maximum, never substituted for complete candidate data.
Literal parties and 332 explicit candidate zeros remain intact. Congressional
unit IDs 4310 and 7001 overlap district scopes; participation is counted once
per native unit, not from repeated candidate joins. Native header and separate
participation/candidate edit times remain distinct. Eight complete CSVs,
all sources, portable reviewer, audit and checksums form a deterministic
71-member, 699,994-byte ZIP, SHA256
`fae4bb7235154ada6d194e27891b0890cbb8acbfa242fd0e8e12303e760b87ff`.
Eleven focused tests and byte-identical packaged offline reproduction pass
after final reviewer changes. All 6,215 tracked files and 4,869 reachable
historical blobs pass credential screening; six scanner regressions pass.
No new map coverage, demographic turnout, certification or final counting is
approved. Data commit `1578e77f415c02e24d7c2d31ac6337cb80bdf460` and immutable
release `voter-county-pennsylvania-berks-20261105-01` are public. The ZIP and all
eight commit-pinned CSVs were downloaded and match reviewed bytes exactly.
The registry adds nine download links, preserving the existing 258; require
the exact 267-link set in four local and production display modes before
marking UI publication complete.
All four local modes now pass that exact set, retaining all 258 earlier links,
all 52 UF rows, five historical years and 255 historical scope cells.
Seven participation tests, Astro check (zero errors/warnings, five hints),
build and 94 byte-verified bulk downloads pass. Prepared Pages size is
987,335,410 bytes, below 1 GB. UI revision
`e106ccaa9f0866bcb331e50d34cfd32a051c2660` passed Pages run `42132560409`
and full-history credential run `42132560564`. Production registry and download
manifest bytes match the prepared artifact. All four production modes pass
the exact 267-link set, retaining all prior 258 links and unchanged coverage.
No unchanged map suite was repeated. See
`data/county-source-reviews/20261105-berks-publication-01/`.

**Provider overlap repair is published and live verified.** Scheduled refresh `42130717845`
acquired all 435 district originals and reconciled all 67 Pennsylvania counties,
but correctly stopped at the previous no-overlap guard. Exact failed-run inputs
reproduce that failure. Provider major-party totals match Monroe, Bucks and
Montgomery's reviewed official reports, while provider rows omit their 1,927
known write-ins. Never simply skip official supplements or append duplicate
county vectors. The repair preserves whole official vectors for those three
counties only after all county and district major-party vectors match, requires
the complete 67-county provider inventory, and rejects other mismatches.
Other provider county rows and provider-only state/district tables remain
unchanged; their scopes are explicitly distinguished from composite county
tables. No synthetic composite state total is created. Exact source replay
retains 3,127 unique county equivalents, 3,124 colorable, all 67 Pennsylvania
county identities, and the unchanged Maine all-district guard. Thirty-four
pipeline tests pass. The refresh also updates the Pennsylvania county ledger
without claiming final counting and verifies uploaded ZIP bytes while the
release is still draft. Raw provider caches and reviewed output are screened
for copied credentials before any release operation. Full controller replay
passes with the last-good pointer retained. The actual draft-first publisher
then published immutable release
`voter-county-2026-20261105-provider-overlap-01`, data revision
`7437b4399e5a425c6ec2b3080ca268418a59e73b` and pointer/main revision
`f231deae3d3c9e7ab4f96c676a4c97ad06b6d56d`.
All seven public data downloads match reviewed bytes. The 150,787,009-byte
complete ZIP has 140 unique members and SHA256
`62c57cffebeae0b2bb048c37dc852e1f040306857e351a0cd2e0282f24fa8cdb`.
All payload checksums, public table/archive equality and byte-identical packaged
offline reproduction pass. Astro check, build and Pages preparation pass;
the prepared artifact is 987,349,424 bytes with all 94 bulk downloads verified.
Exact Pages run `42134109124` and full-history credential run `42134109002`
succeeded. On November 6 UTC, all four local and production display modes
passed the exact 274-download set, retaining all prior 267 links, all 52 UF
rows, five historical years and 255 historical cells. The full changed-map
suite source-matched all 3,124 colorable counties and 49 state drilldowns,
including all 67 Pennsylvania counties, with zoom, precinct priority,
historical isolation and failure fallbacks intact. Production pointer,
overview, county ledger, participation registry and download-manifest bytes
match the prepared artifact; the source-precedence explanation is visible.
County identity coverage is not final counting, ballots, turnout, demographic
participation or statewide completion. The older three-county descriptions
below are historical records, superseded by this verified snapshot. Continue
primary county participation acquisition and the genuine Maine/D.C. scope gaps.
Do not repeat this completed map suite for subsequent download-only batches. See
`data/county-source-reviews/20261105-provider-overlap-review-01/`.

**November 6: Philadelphia native review is verified privately, not published.**
The complete county CSV was obtained with the site's declared ordinary export
form. All 23,906 observations reconcile with 80 native candidate/ballot-option
lines across **35**, not 34, contests. State-House HTML is paginated: preserve
the fresh form and the declared Next Page response containing the last six
districts; the first page alone is incomplete. All 1,703 separate division
participation rows reconcile to 497,111 ballots and 1,104,061 registrations.
Polling-place ballots are 390,506, mail 106,605 and provisional an explicit zero.
The native printed registered-voter rate is 45.03%, not eligible-population or
demographic turnout. House candidate votes are separate: 476,317 total,
DEM 418,545, REP 39,055, IND 17,361 and NON write-in 1,356. The 20,794-ballot
House residual stays unclassified. Preserve the 33 district-labelled zero rows;
they are not three additional divisions or inferred provisional votes.
Mahoney's visible candidate-name suffix is TIP, while both the CSV party code
and HTML party CSS class are IND; the visible HTML party label is Independent.
Retain all these native literals rather than silently recoding one representation.
Both native browser modes establish that the Testing in Progress template is
actually hidden (`display:none`), not an active warning. This does not approve
the separately guarded provider test snapshots or authorize any map override.

The official commissioners' result wrapper declares the acquired Azure-hosted
app; its separate government-domain mirror has matching captured participation.
Native update November 5 at 5:21:56 PM EST remains separate from the CSV's
7:15:35/7:15:36 PM export-generation literals. Nine synthetic-fixture tests pass
without committing the city's HTML as test fixtures. All eight complete private
tables, 16 source responses, receipts, audit and portable reviewer form a
28-member private ZIP; all checksums and byte-identical packaged offline replay
pass. See `scripts/review-philadelphia-county-results.py`,
`scripts/test-philadelphia-county-results.py` and
`data/county-source-reviews/20261106-philadelphia-private-review-01/`.

**Keep this Philadelphia source package private.** The city-linked website
terms contain restrictive republication language; the separate catalog-declared
data-license FAQ reserves rights and does not establish a grant to mirror the
original HTML. Do not equate public access with an HTML redistribution license,
claim CC0, publish the private ZIP, or add a metadata-only download to the UI.
The declared OpenDataPhilly Election Results API is a genuine consolidated
alternative, but its captured complete distinct election-date query has 31
elections from 2013 through 2024 and no 2026 records. Its 2013-present label
does not establish 2026 availability. Preserve that probe and exact terms
evidence privately; direct terms acquisition returned HTTP403 and was not
bypassed. Resolve source-specific redistribution or develop an explicitly
qualified complete facts-only package without mirroring restricted webpage
templates before any public release. The existing 274 download URLs and all
map vectors remain unchanged.

**November 6: Centre's complete primary review is verified privately.**
Normal browser navigation and same-origin acquisition of the two declared
PDFs returned HTTP200 without a challenge or bypass. Preserve the earlier
empty HTTP404 receipts; the successful HTML and actual two-page county and
87-page precinct reports are now captured. All 87 native precincts and 261
ArcGIS records reconcile: 57,125 ballots, 103,270 native registrations and
55.32% registered-voter participation. Election Day ballots are 43,125, mail
14,000 and provisional an explicit zero. House candidate votes are 56,804:
DEM 32,234, REP 24,503 and 67 write-ins with no inferred party. The 321-ballot
House residual stays unclassified, not inferred undervotes or overvotes.

The full primary PDFs establish state-House membership: 34 precincts in
district 77, 32 in 82 and 21 in 171. Do not infer membership from zero candidate
columns. ArcGIS `PRECINCT_CODE` differs from the printed report ID for **63**
precincts; join by the full native precinct label and retain both IDs. All
candidate/method observations, including explicit zeroes, match the PDFs.
Preserve null Mail/Provisional registrations rather than copying the
InPerson-only registration counts into every method.

The API has one retained provisional blank-ballot conflict: 240 blanks despite
zero provisional ballots; both PDFs independently report zero provisional
blanks. Keep the original API observation and mark it unusable as accounting,
separate from the primary PDF's valid six blanks (five Election Day, one mail).
Two native printed precinct percentages differ from the ratios of printed
counts by 0.01 percentage point. Preserve printed and calculated percentages,
without inferring the cause. The official index update (11/4 at 12:44 am),
PDF report stamps (11/4 at 12:40AM), API last edit and older schema/data-edit
timestamps remain separate; no PDF/index timezone is declared.

Pre-publication screening found one Google service key and one telemetry key
in the successful county linking HTML. Neither was published. Their values
are removed only from the screened working copy; retain the unscreened
response privately and preserve its original hash, size and explicit
redaction receipts. Every other response is byte-unchanged. The private
complete ZIP contains 13 full CSV tables, all 16 screened/source responses,
receipts, audit, portable reviewer and checksums, with 33 unique members.
All payload hashes and byte-identical packaged offline replay pass; all ZIP
members are clear of the service/telemetry patterns. Twelve synthetic tests
and six existing credential-scanner regressions pass.

See `scripts/review-centre-county-results.py`,
`scripts/test-centre-county-results.py` and
`data/county-source-reviews/20261106-centre-private-review-01/verification.json`.
Do not repeat acquisition or treat this private ZIP as a public download.
The next publication step is a complete qualified source/data release and
registry integration, not metadata-only links or an unreviewed map override.
Native status is still **0 complete**, **87 partially reported** and **86 of
87 absentee/early precincts reporting**. No Centre release, new map coverage
or final-counting claim is approved by this private review. Alerts 1/2 remain
open/unknown; external revocation and cached-object cleanup are unconfirmed.

**Centre facts-only publication and UI are live verified.**
The county's linked copyright notice reserves the county and CivicPlus
presentation rights. Keep the existing private web/PDF source package private;
do not infer a source-template redistribution license or attach that ZIP.
The portable reviewer now has a distinct `--facts-output` profile. It exports
all complete primary numerical observations, five unchanged native API data
responses, original capture receipt digests and complete source identities,
without copying website, app or PDF presentation templates. Derived facts are
explicitly identified as derived records, never as original HTTP body bytes.
The inaccessible child item's HTTP200/API400 remains nondata, not a bypassed
source. All 13 CSVs are byte-identical to the independently verified private
review, retaining all original accounting, identity, party and missingness
qualifications. The public profile replays those complete captured facts, not
the omitted PDF extraction bytes.

Sixteen synthetic tests pass, including exact private/public fact equality,
continued zero-option validation, rejection of added template files and an
output-profile guard against packaging the private sources as a public ZIP.
All 23 archive members and checksums pass, with byte-identical packaged offline
replay and no unredacted service/telemetry patterns. Candidate archive
`complete-centre-2026-native-facts-01.zip` is 91,415 bytes, SHA256
`7c32bc66a43932b95d2bc6f43cfd49419ceb7cba70df0b1c46930e6f31e9d39a`.
Complete data are committed at `ea4cb1dfbfd522f7706431ea8717250eae1e7a9c` under
`data/county-source-reviews/20261106-centre-facts-01/`; publication status is in
`data/county-source-reviews/20261106-centre-publication-01/verification.json`.
The immutable `voter-county-pennsylvania-centre-20261106-01` release now contains
the complete ZIP and all 13 CSVs. All draft assets were downloaded and byte-verified
before publication; all 14 public assets and 13 commit-pinned raw CSVs were then
independently downloaded and byte-verified. Keep the exact native CSV CRLFs and
API response whitespace rather than normalizing verified source bytes.
The registry now adds all 14 download links while preserving the existing 274.
Seven participation tests, Astro check (zero errors), build and Pages preparation
pass: 94 bulk downloads verified, prepared site 987,361,863 bytes. Four local modes
pass the exact 288-URL / 291-anchor multiset, preserving all 274 previous URLs and
their three intentional duplicates, 52 UF rows, five historical years and 255
historical scope cells. Exact UI revision
`0e7d687f418ddd045382d9d589ec12bb494a6406` passed Pages run `42140108699`
and credential runs `42140108433` / `42140104997`. All four production modes
pass the same exact multiset, 14 Centre links, 52 UF rows, five historical years
and 255 scope cells; public registry bytes match. Production receipts are saved
as `download-production-verification.json` in the publication audit. This was a
download-only batch: do not repeat completed unchanged map suites or alter
county/precinct coverage, map overrides or the Maine all-district guard.

**Earlier current-source cleanup (historical record).** On November 5,
GitHub reported Google API keys copied from public county linking HTML. The
affected current Bucks, Chester and Franklin pages are now explicitly sanitized,
with byte-original hashes retained privately. All 40 county parser/source tests
and 10 official-merge guards pass; election counts and geometry are unchanged.
The three affected complete ZIPs (Bucks, national county map, and unpublished
three-county batch) were withdrawn. Their replacements are published and
downloaded-back byte-verified in immutable release
`voter-county-source-redaction-20261105-01`, pinned to sanitized data commit
`28cdb2c434e01ab2fe45696970e95b4454900a08`. That commit descends directly
from the previous live main revision, not the exposed three-county commit.
Exact Pages run `42109764552` for revision
`142d4086f3977c52a73062e5cf08184ff712a36f` succeeded. Production registry
bytes and all four browser modes pass with exactly 225 complete download URLs.
The deployment replaces two unsafe ZIP URLs
and repins seven byte-unchanged Bucks CSVs to the sanitized source revision,
while retaining the other 216 complete download URLs. A nested party-download
reference was also repaired; the build now rejects all three retired archives.
All seven repinned public CSVs are byte-identical to reviewed election tables.
The broad site validator still fails an unrelated pre-existing UK topic-card
assertion (23 actual versus 16 expected); the participation checks, build,
94-download Pages preparation and focused production checks pass.
Do not republish old ZIPs or copy
unsanitized snapshots. Both county reviewers now reject Google/Mapbox and
telemetry key patterns in every HTML file, even with matching acquisition hashes.
GitHub alerts #1/#2 remain open with unknown key validity: the keys appear
county/vendor-owned, cannot be rotated from this repository, and historical
copies remained at that stage. No published-history rewrite had yet been authorized. See
`data/county-source-reviews/20261105-source-key-remediation-01/`.
The later explicit security escalation and rewrite above supersede that
authorization blocker. Do not merge any pre-rewrite local acquisition ancestry
back into the rewritten publication history.

**November 5, 2026: the latest user instruction is counties instead of further
precinct expansion.** Make counties the default map detail and primary acquisition
unit across all 50 states and D.C., newest elections first. Preserve existing
precinct datasets, but do not let additional precinct geometry block county work.
Never paint county totals as precinct results, allocate them into precincts, or
call candidate margins participation.

The national-scale coloring fix is live: all available county red/blue candidate
colors are visible without selecting a state or zooming. Commit `ad36234`,
successful Pages run `42058221971`, and the saved production browser proof
verify all 48 state drilldowns, national own-county colors, zoom and 121 complete
downloads. Do not repeat that completed fix. The existing
2026 release now has 49 state scopes, 3,063 county equivalents and 3,053 nonzero
candidate margins. Pennsylvania is only 3 of 67 counties; Maine and D.C. remain
county-map gaps, not completed cells.
State colors are fallback only in uncovered states; explicit zero-vote counties
have no candidate margin. The new lightweight overview uses the reviewed 2026
Census shapes; four counties retain unsimplified native geometry because display
simplification would produce invalid polygons. Full native shapes and complete
candidate/source downloads remain unchanged.

The published county-map batch independently joins the already reviewed official
Monroe, Bucks and Montgomery reports to their exact 2026 Census county identities
(42089, 42017 and 42091). The merged candidate snapshot retains all 3,060
previous county vectors and adds 753,168 candidate votes: 49 state scopes,
3,063 counties and 3,053 colorable counties. Pennsylvania remains only 3 of 67
counties; uncovered counties retain state fallback. Provider Pennsylvania test
data remains excluded, and D.C. delegate/RCV counts remain download-only.
Full literal-party and county/district candidate tables are extended without
inventing complete Pennsylvania state or district totals. Data/tools commit
`cbff6e4a4bcd8b4569f447b0d994a34ca79ca10f` and immutable release
`voter-county-official-pa-20261105-01` are byte-verified. All 23 hosted-refresh
tests pass; replay of all 435 saved district responses exactly reproduces the
complete archive and retains all 49 state scopes. The full local four-mode
map suite passed all 3,053 own-county colors, 49 state drilldowns, Pennsylvania
selection/fallback, historical isolation, zoom and 212 complete downloads,
including all previous 205. Exact Pages run `42100096558` for UI commit
`274845049f5a4b1da431cd1531755cc29ef1432f` succeeded. The full four-mode
production suite independently passed the same counts, all 49 state drilldowns,
partial Pennsylvania selection/fallback, historical isolation, zoom, existing
precinct priority and failure fallbacks. All 52 UF rows remain source-matched.
Review evidence is recorded under
`data/county-source-reviews/20261105-official-pa-map-01/`.

The next historical download batch adds 2016 from the same pinned consolidated
archive, not another state-by-state acquisition. Its review covers 11,728
candidate/party rows in 2,184 counties across 41 states. All 31 excluded rows
from seven county vectors remain downloadable: four native machine-QA flags
and Missouri's Clay, Jackson and Platte counties, which are undercounted because
the compiler omits the unallocatable Kansas City bucket. No votes are apportioned.
The five-year export preserves every earlier 2024/2022/2020/2018 table row
unchanged, all literal parties and explicit zeros, and 255 partial state/year
coverage cells. All 11 exporter tests, independent source/party reconciliation,
unique archive-member checks and packaged offline reproduction pass. Native
GA/KY party-fill provenance and FL/KY clean-rebuild residual limitations are
retained; no original ballot-party certification is claimed. Review evidence is
under `data/county-source-reviews/20261105-historical-house-04/`. Data/tools
commit `a5baf7cc829cedc6d379e83ae577ed61b2370731` and immutable release
`voter-county-house-history-20261105-04` are published; all 15 assets were
downloaded back and byte-verified, including the 1,346,170-byte complete ZIP.
The UI build, Astro check, seven participation tests and four included caucus
tests pass. Exact UI commit `a1b9e4f343af11c1a7352ea33637e5aa20c18351`
passed Pages run `42102383243`. The four-mode production table suite passed
all five years, 255 state/year scope cells, 225 complete-download links retaining
all previous 212, all 52 source-matched UF rows and the separate 4,896-cell
county candidate ledger. Public pointer/registry/renderer bytes match the
reviewed sources. The unchanged map suite was deliberately not repeated.
Deployment, production browser proof and final evidence checksums are saved
alongside the source/reproduction/release/local UI proofs. The five-year
download batch is live verified, not nationwide historical completion.

A fresh Maine alternative-source probe retained both complete Bangor Daily News
2026 House API responses, explicitly without demo parameters and with native
`test_data: false`. All 17 county/district fragments match the saved official
2026 Census identities, and their 34 named-candidate rows reconcile to all
municipal candidate rows. District 1 also reconciles to its topline; District 2
does not: county sums are short by 84 Republican and 46 Democratic votes.
Its separate 6,021 blanks and 125 write-ins cannot be allocated by county, and
municipal combined `other` is three below their district sum. Keep these gaps,
literal parties and noncandidate observations separate. Kennebec occurs in both
districts; never discard either fragment. Probe evidence is under
`data/county-source-reviews/20261105-maine-bdn-source-probe-01/`; complete originals
and all native county candidate lines remain in the persistent session artifacts.
No new public download or map is approved: publisher redistribution terms,
counting/round scope and the five District-1-only county vectors need separate
review. Do not weaken the all-district validation guard or claim Maine complete.
An independent official follow-up retained both complete accessible Secretary
of State pages and all 16 native federal/governor UOCAVA observations from the
November 4 announcement. Its District 2 named-candidate counts are 1,731 and
211, not the publisher's 46/84 gap; no county allocation or proof of inclusion
in the publisher totals is supplied. Do not add them to those totals.
District 1's missing write-in row remains missing, not zero. The advertised
PDF returned HTTP 403, with the complete denial body preserved; it is not an
acquired PDF. The accessible election-results index still declares June primary
and special-election results, not November general county returns.

The active 15-minute continuation prompt is now schedule **#5**, replacing
stale schedule #4. It follows current plan statuses, skips already-verified
coloring and unchanged map suites, and prioritizes these genuine 2026 gaps
before older historical expansion.

A consolidated Pennsylvania source directory now supplies exact result links
for all 67 counties, each independently matched to its official 2026 Census
identity. The county-owned Allegheny and Delaware pages independently declare
their directory links; both result landings return HTTP 403, with full bodies
retained rather than bypassed. The complete embedded factual snapshot is also
retained privately: 240 separate races, including 17 House districts with
417 compiler candidate slots in 73 fragments across 57 counties. All its
internal county sums reconcile, but independent anchors expose a material
limitation: Bucks and Monroe match, while all 711 Montgomery House write-ins
are omitted despite exact agreement on both major-party counts. Compiler party
labels also differ from the native literals. Do not replace the approved
Montgomery vector, infer explicit native zeroes from compiler zeroes, promote
the Philadelphia test source, or treat 66 governor counties as 66 House counties.
The full 67-county discovery queue and fail-closed review are under
`data/county-source-reviews/20261105-pa-county-source-directory-01/`; originals
and the complete factual snapshot remain in persistent session artifacts.
Next, follow these actual links for complete primary report exports, retaining
write-ins separately where vendor CSV/JSON omits printed PDF lines. The live
Pennsylvania map remains three counties, not all 67.

Following that directory, complete county-owned linking pages and vendor
snapshots now independently reconcile Chester, Franklin and Lehigh. The new
shared reviewer preserves all 104 county candidate/ballot-option rows across
38 contests, 327 candidate-mode observations, 36 office/literal-party totals,
461 native unit participation records and 6,362 native candidate observations,
including all 520 explicit unit zeroes. Their 438,869 actual reported ballots
remain separate from 437,079 House candidate votes and native registrations.
All 19 focused parser tests pass; independent native CSV/mode/party/Census
checks and byte-identical complete ZIP reproduction pass. Data and originals
are under `data/county-source-reviews/20261105-pa-three-county-01/`; publication
evidence is under `data/county-source-reviews/20261105-pa-three-county-publication-01/`.
Chester supplies no native result-status literal; do not invent one. Its 15
CSV contest-ballot zeroes conflict with positive unit ballot sums and remain
flagged and unused as real ballot counts. Franklin's House contest supplies
no district number; none is inferred. Lehigh still explicitly reports partial
mail and provisional counting. Native prefixes, CSV parties, accessible HTML
labels and accounting fields remain separate; ballot options never become
party totals. Franklin's 195 under/6 overvotes fully explain its House ballot
gap; Lehigh's 1,003 reported undervotes leave 46 unclassified ballots, not
inferred overvotes. Missing native accounting fields remain blank, not zero.
Data/tools commit `8293db8a8bda6ab561e139708495425fcea0c206` and immutable
release `voter-county-pennsylvania-three-county-20261105-01` were published,
but that release's complete ZIP has since been withdrawn for source-key
remediation; its seven count-only CSV assets are unaffected. The sanitized
replacement is now byte-verified in `voter-county-source-redaction-20261105-01`;
its three-county UI integration is now live alongside Northampton, with exact
local/production four-mode download verification. No new map, demographic turnout, certification, or statewide
completeness is approved.
After the security deployment, the exact Northampton government-to-vendor
link was reverified and both complete primary pages were freshly acquired.
The native report explicitly declares the 2026 general election and unofficial
results. All 631 native tables, including 630 candidate tables, are now extracted
without interpreting duplicated accessible labels, allocating counts or
promoting coverage. Complete HTML, extraction and receipts remain private in
`files/northampton-primary-refresh-20261105-01/`; the acquisition audit is
`data/county-source-reviews/20261105-northampton-primary-01/source-acquisition.json`.
Northampton's separate count review now passes 16 focused tests, independent
matching of all 31 county and 2,015 unit candidate rows against the complete
table extraction, and byte-identical offline ZIP reproduction using only its
packaged originals and reviewer. All 155 native units and four nonoverlapping
office partitions reconcile; all 220 explicit candidate zeroes remain.
County ballots are 129,290, registrations 234,834 and printed turnout 55.1%.
House candidate votes are 127,555: DEM 72,478, REP 54,763 and 314 write-ins
with a blank native party prefix, not inferred NON or independent affiliation.
The 1,735-ballot House residual stays unclassified. The native 38,593 mail
receipt notice is separate from 38,154 reported mail ballots; Election Day
and mail counting remain partial despite 155/155 reporting. Missing district
ballots, unit participation, candidate modes and under/overvotes stay absent.
Complete screened originals, seven CSVs, portable code and checksums are under
`data/county-source-reviews/20261105-northampton-reviewed-01/`; independent
proof is under `data/county-source-reviews/20261105-northampton-publication-01/`.
The 322,312-byte complete ZIP has SHA-256
`d5e29bb452d7a3b29801f70f1b7b6b1496ed9eeb3fdcd98193bdd66308029d9d`.
Release `voter-county-pennsylvania-northampton-20261105-01` is pinned to clean
data/tools commit `7f4d6dc4ed1a4e4637aa0f2f5772ef14fe81e990`. All eight
released assets were downloaded back and byte-verified. Both reviewers pass
35 combined tests. All 14 immutable Northampton/three-county CSV URLs are
also byte-verified; their combined website update preserves the previous
225 complete download URLs and adds exactly 16, for 241. Local and production
browser proofs pass exact 241-URL set equality on desktop/mobile with and
without JavaScript.
Astro check, participation tests, build and Pages preparation pass; 94 relocated
bulk files are byte-identical and the prepared site is 987,308,169 bytes.
The broad validator still reaches the unrelated UK topic-card assertion
(23 actual versus 16 expected); it is not reported as passing.
Production commit `fb05bd3745dc2a16d1e348ac75ae5924b8d415e2` passed exact Pages
run `42115185047` on attempt 2. Attempt 1 built/uploaded successfully but timed
out after ten minutes syncing files; retrying only the failed deploy job reused
the same artifact and succeeded. CI prepared 997,446,589 bytes and uploaded a
491,854,048-byte artifact, both recorded separately from local preparation.
Both production registry files are byte-identical to reviewed sources; map
data remain unchanged. No new map, demographic turnout, certification or
statewide completeness is approved. Pennsylvania's map remains 3/67 counties;
separately review county geometry/House identities before any four-county merge.
The publication directory records first-attempt failure, successful deployment,
production browser proof, final verification and checksums. Historical secret
alerts #1/#2 remain open with unknown validity; no owner rotation or authorized
history cleanup is claimed.

Lancaster's government-hosted application now supplies complete native election,
all-contest and turnout JSON plus all five explicitly linked PDFs (559 pages).
The new JSON/PDF reviewer reconciles all 43 ballot options in 14 contests,
129 option/method observations, 41 contest/literal-party totals and 241 native
unit participation records. All 13 explicit write-in zeroes retain blank native
parties; the two referendum options never enter candidate-party totals.
County ballots are 216,221, registrations 366,763 and printed turnout 58.95%;
House candidate votes are 214,875 (DEM 100,607, REP 114,268, blank-party
write-ins 0). PDF-only 947 undervotes and 36 overvotes leave 363 House ballots
unclassified; missing API accounting remains null rather than overwritten.
Native zero method-ballot fields conflict with positive method selections and
are flagged, not treated as actual zero ballots. Provisional remains Not
Reported; the source reports 0 fully/241 partially reported units. Five native
party-statistic series print zero ballots/registrations and blank rates; retain
all 15 fields without approving party-specific participation. Empty separate
registration/statistics endpoints do not erase the actual registrations in
turnout records. Native ballotItemCount metadata is 1 despite 14 acquired
contests; preserve it without using it as the contest inventory. State Senate
coverage is only 132 native units, not an asserted countywide partition.
All 12 analytical originals pass service/telemetry screening, with zero text
substitutions and original-hash receipts; the application bundle is not
redistributed. All 559 decoded PDF pages also pass screening. The complete
eight-table package is byte-identically reproducible offline and is under
`data/county-source-reviews/20261105-lancaster-reviewed-01/`; independent proof
is under `data/county-source-reviews/20261105-lancaster-publication-01/`.
Its ZIP is 763,713 bytes with SHA-256
`a9f2da2a21ba6d7ec9ae573872e3152c135c068217ab1a81692af78c7862e8a4`.
Sixteen new regressions and 35 existing county-parser regressions pass.
York's alternate government host timed out and its declared Clarity page
returned HTTP403; retain those bounded failures without bypassing the denial.
Release `voter-county-pennsylvania-lancaster-20261105-01` is pinned to publication
data/tools commit `3aabcede13986955f094d706015486ad7a7c3362`; all nine release
assets and all eight commit-pinned CSV URLs were downloaded and byte-verified.
The website update preserves all previous 241 complete download URLs and adds
exactly nine, for 250. Local four-mode browser proof passes exact set equality.
Astro check, participation tests, build and Pages preparation pass; 94 relocated
bulk files are byte-identical and the prepared local site is 987,318,167 bytes.
Broad validation still fails only the known unrelated UK topic-card assertion
(23 actual versus 16 expected); it is not reported as passing.
Registry-only publication commit `a48e3c21ddcfe101211f34693f3093cbe233637f`
passed exact Pages run `42122234060` on attempt 1. Production four-mode browser
proof passes exact 250-URL set equality, preserving all previous 241 URLs;
both production source-review/county registry files are byte-identical to the
reviewed sources. CI prepared 997,456,587 bytes and uploaded a 491,866,474-byte
artifact, recorded separately from local preparation. Complete deployment,
production browser/source verification and checksummed evidence are persisted
in the publication directory. No frontend or map changes follow that proof.
All 38 current tracked HTML files pass service/telemetry screening without
printing matching values. The newer exposed three-county commit is excluded
from this publication ancestry; older Bucks exposure `3d2be9` was already an
ancestor of existing main and is not claimed removed. Alerts #1/#2 remain
open with unknown validity, without confirmed owner rotation or revocation.
No new geometry, map, demographic turnout, certification or statewide
completion is approved.
Its separate county-parent linking page has not been independently acquired.

The reusable 2026 county-results and separate UF/state participation pipelines
are implemented and published. Both passed real acquisition and original-backed
release verification. Fresh county snapshot `20261105T155645Z` updates three
county totals, increasing aggregate candidate votes from 103,052,239 to
103,056,212 without losing any state or county. UF snapshot `20261105T155617Z`
activates a separate server-rendered table. Local four-mode browser proof
`files/county-uf-final-local-proof-01.json` verifies all 52 UF rows, all 48 county
states, 3,050 own-county colors and 132 complete download links, preserving the
original 116. Exact deployment `42060138011` for
`bdeed98e520708527588c4b3a183d4e81546273a` succeeded, and its production
four-mode proof passed the same counts, colors, links, zoom, historical
isolation and failure fallbacks. Persistent evidence is
`data/county-source-reviews/20261105-refresh-live-01/production-browser.json`,
with exact deployment and hosted-refresh run records alongside it. The current
county and UF pointers reference that proof; partial coverage and source estimates
remain explicitly labeled.

The historical-download/ledger page update in `d269eb1e1b12add3cd3c33d2c1ac09069026962b`
also passed exact Pages run `42062339000` and four-mode production checks.
All 134 complete download links are present, including the original historical
archive and the separate 4,896-cell county ledger; all 52 UF rows still match
their source values/statuses. Pointer, ledger and renderer public bytes match
the committed source. This focused check deliberately did not repeat unchanged
maps. Evidence is
`data/county-source-reviews/20261105-refresh-live-01/historical-downloads-production-browser.json`.

The six-hour/manual workflow `.github/workflows/refresh-2026-data.yml` has
actually passed hosted run `42060180039` (`source=uf`): all 13 focused tests
passed, the fresh official source was unchanged, and the previous public
pointer was retained without a duplicate release. Its saved status is
`files/uf-hosted-refresh-evidence-01/status.json`. Preparation remains the CLI
default; `--publish` verifies complete releases before immutable pointer updates.
County coverage regression, malformed UF rows and source failures fail closed.
Platform-only gzip headers do not create duplicate county snapshots. Unchanged
geometry is reused by verified content hashes instead of copied per refresh.

The consolidated historical county batch is now arithmetically reviewed:
all 420,503 candidate/party rows reconcile with all 120,191 county summaries.
120,190 county/office/year vectors have valid integer counts; one Montgomery
County, Alabama, 2010 House vector is withheld for the original fractional
`23334.16236` count. Do not round it. Final rounds across different districts
retain their stage labels; overlapping general/runoff counts within one district
are rejected. Literal parties, fusion labels, explicit zeroes and native quality
flags remain in the local derived tables. All 22 focused historical/party/refresh
tests passed. The portable reviewer is `scripts/review-historical-county-results.py`;
its persisted audit is `data/county-source-reviews/20261105-historical-bulk-01/audit.json`.

The distinct county candidate ledger is now `public/county-candidate-coverage.csv`:
4,896 cells cover all 51 jurisdictions, all even years 1964–2026 and House,
president and Senate separately, newest first. Unreviewed counts stay blank.
Presidential midterms are marked no regular presidential election. None of these
cells is declared fully complete; arithmetic is not map or reuse approval.
The original full 1990–2024 publisher archive is linked in Downloads, alongside
the county ledger. The four generated historical tables remain private in
`files/historical-county-reviewed-01/` until source-specific reuse terms are reviewed;
do not mirror them just because the compilation carries CC BY 4.0.

Historical provenance now has executable, fail-closed checks as well:
all 420,503 rows resolve to exactly 1,870 distinct
`source + office + state + year` records, and every declared source row count
matches. Do not join only on the shared source token. Missing/duplicate source
identities and declared count disagreements stop review. All 27 focused tests
passed. The new complete local review is `files/historical-county-reviewed-02/`;
its persisted audit and complete source-reference table are in
`data/county-source-reviews/20261105-historical-provenance-01/`.

Five license-status literals are not documented by the native dictionary:
Montana 2022 House says `believed_cc0`; Delaware House 1990/1992/1994/1996
says `downloaded by curl` with other provenance fields shifted. Preserve these
as native exceptions rather than silently repairing them or treating them as
permission. President 1992–1996 and Senate 1990–2014 name only major-party
nominees; native aggregate Other rows cannot recover unnamed parties/candidates.

Direct Harvard Dataverse pages/API were blocked. The DataCite DOI registry
alternative returned original metadata for all five cited House datasets,
confirming their titles and explicit CC0 declarations:
2024 `10.7910/DVN/USBYR4`, 2022 `10.7910/DVN/EOKNGW`,
2020 `10.7910/DVN/VLGF2M`, 2018 `10.7910/DVN/IVIXLK`,
2016 `10.7910/DVN/PSKDUJ`. Both failed direct responses and successful registry
responses, timestamps and checksums are retained in the provenance review.
This does not approve every compiler correction/name override, a different
office/source, all upstream terms, or historical county geography.

The provenance publication `e2f115732731645b6a0f7b996296a18cadffde08`
passed exact Pages run `42064163206`. A subsequent public-byte check matched
the county/UF pointers, county ledger and unchanged renderer, and retained all
134 complete download links.

The first scoped historical House export is release-verified, awaiting its exact
production-page check:
2024 has 11,776 reviewed candidate/party rows in 2,664 counties across 43 states;
2022 has 9,620 rows in 2,690 counties across 43 states. The complete scoped source
has 21,448 rows and 62 literal compiler party labels. All 52 rows from 12 flagged
county/year vectors are retained separately, never summed into reviewed exports.
The 53-record pinned QA file is not the 64 flags mentioned in stale correction
prose; Yazoo, MS, 2022 is an additional prose-only exclusion.
Both NJ 2022 and 2024 are already official-source replacements, outside this
MEDSL-only scope. The old NJ 2022 duplication warning does not invalidate the
current official replacement. Do not rely on stale correction prose without
checking the current scoped source record.

The exporter is `scripts/export-historical-house-counties.py`; its complete
tables are in `data/historical-house-counties/20261105-medsl-01/`.
Every state/year is listed in its separate 102-cell scope ledger, including
jurisdictions outside this source family. All completeness/map flags remain
false. State-party sums are reviewed-county sums, not certified full-state
results. Keep compiler literals, all 68 surname/initial flags and secondary
Oregon 2024 party-override provenance; the generated name-override CSV is absent
from the pinned tree. The full mixed-license original remains linked, not
mirrored under a blanket permission claim. Packaged tools reproduced all
nonarchive output bytes outside the repository. All 33 focused tests passed.
Originals, exact hashes and reproduction proof are in
`data/county-source-reviews/20261105-historical-house-01/`.
Data/tools commit `9c1590362994ee87c510ebe34a253cea6ba90217` is pushed.
All 13 assets of release `voter-county-house-history-20261105-01` were downloaded
back and byte/SHA256 matched before adding the public pointer. The complete ZIP
is 619,935 bytes, SHA256
`a797670e41bcb11ab6f2c0668810e5782dad9b25e8069c116aa29118585565bf`.
The new source-matched HTML coverage table works in desktop/mobile and
JavaScript/no-JavaScript modes; all 145 complete download links retain the
previous 134. All 52 UF rows remain source-matched. Astro check, seven
participation tests, build and four caucus tests passed. The prepared Pages
artifact is 987,231,960 bytes after 94 relocated downloads were verified.
The unchanged renderer/maps were deliberately not retested.
Exact Pages run `42067422722` for UI commit
`235e5a7497e1356b72213927bdf1e13878991c26` succeeded. Production proof
`data/county-source-reviews/20261105-historical-house-01/production-browser.json`
confirms all 145 complete download URLs, both historical years, 102 scope cells,
all 52 UF rows and unchanged source bytes in all four display modes.

The 2020 extension is released, integrated and production-verified.
It adds 10,974 reviewed candidate/party rows in 2,773 counties across 45 states;
23 raw rows from six additional flagged counties are withheld, not lost.
The three-year scope contains 32,445 source rows, 32,370 reviewed rows,
23,445 county-party totals, 565 reviewed-county state-party sums and 81 literal
compiler party labels. Its separate scope ledger has 153 state/year cells,
all incomplete and without map approval. Native auxiliary records include
two source coverage gaps and 55 no-ballot observations; these are not invented
zero-vote candidates. Maine's 2020 federal/UOCAVA 23000 bucket was excluded by
the upstream county release and is not allocated into counties here.
The old Indiana 2020 warning is superseded by a non-MEDSL official replacement,
outside the selected scope.

All previous 2024/2022 rows in all ten tables remain unchanged. The new
complete archive reproduced every nonarchive output byte outside the repository;
34 focused tests passed. Released data are
`data/historical-house-counties/20261105-medsl-02/`, proof is
`data/county-source-reviews/20261105-historical-house-02/reproduction.json`.
Data/tools commit `d14199b6510e32a9543014933747887c28bf0ca6` was pushed to the
work branch before creating release `voter-county-house-history-20261105-02`;
all 15 assets were downloaded back and matched byte/SHA256 before changing the
public pointer. The complete ZIP is 888,202 bytes, SHA256
`e10f905459c3550f799b17af58a4a7ed707f591b7995772f6c9f08c90085e17c`.
An independent aggregate reconciliation verifies every literal-party county/state
sum, every raw/reviewed/withheld partition, all 4,165 explicit zero rows and all
144 native identity-flag rows. The three-year HTML table and all 158 complete
download URLs passed four local display modes, retaining every previous 145 URL.
All 153 scope cells and 52 UF rows remain source-matched. Astro check, seven
participation tests, build and four caucus tests passed. The prepared site is
987,238,926 bytes after verification of all 94 relocated downloads.
The source renderer/maps are unchanged and were not redundantly retested.

UI commit `7f3afe35af3d9ab0d8c2003b62d4b9b145619e69` is live: exact Pages run
`42072656065` succeeded. Production proof
`data/county-source-reviews/20261105-historical-house-02/production-browser.json`
confirms all three year rows, all 153 scope cells, all 158 complete download
URLs (retaining every previous 145), all 52 UF rows and unchanged source
pointers/renderer bytes in four display modes. Deployment and aggregate proofs
are saved beside it. Keep the two-year immutable download links.

Next:
Continue 2016 source-specific quality review: its unresolved
party labels, Missouri noncounty buckets and Texas source undercoverage need
separate handling rather than a blanket extrapolation from the two newest years.
Historical maps still require election-year county crosswalks.
Acquire genuine 2026 Maine/Pennsylvania alternatives; D.C.'s separate
nonvoting-delegate counts and city participation are now published and
production-verified, as detailed below. Do not repeat their completed review.
Do not repeat the completed
county map or pipeline suites unless their counts/renderer actually change.
UF's currently published
2026 CSV labels all 52 rows as Initial Estimate, not final administrative ballots.
Do not silently replace measured participation or infer demographic turnout from
these state-level estimates. Recurring schedule #4 replaces obsolete precinct-first
schedule #3 and follows this county-first priority.

2018 consolidated House extension, released and production-verified:
`data/historical-house-counties/20261105-medsl-03/` adds 8,851 reviewed
candidate/party rows in 2,443 counties across 42 states. All 25 rows from
five flagged county vectors are retained separately: 01107, 12057, 12095,
12099 and 38079. Five New York House QA entries are outside the current
MEDSL subset because the compiler replaced that year's New York House
source; the Senate-only warnings also do not apply. Maine, Indiana and Texas
2018 official replacements remain outside this source-specific subset.
Compiler-filled party labels and all native surname/initial flags are
preserved, not independently certified as original ballot identities.

The four-year scope has 41,321 raw rows, 41,221 reviewed rows and 100 withheld
rows, with 204 honest state/year cells and no map/completeness approval.
It preserves all prior 2024/2022/2020 rows in every table, two native auxiliary
coverage gaps and 60 no-ballot records. Every nonarchive file reproduces
outside the repository and every raw/reviewed/withheld partition and literal
party county/state sum independently reconciles. The portable tool also now
handles macOS's symlinked temporary directory paths. All 51 focused tests
passed before that path-only fix; all eight exporter tests and actual
portable reproduction passed afterward. Proof is
`data/county-source-reviews/20261105-historical-house-03/`.
Data/tools commit `3a0bdb1e1603dc9de4d4934558ac4c53c4957adc` is pushed.
All 15 assets of release `voter-county-house-history-20261105-03` were
independently downloaded and matched byte/SHA256. The complete ZIP is
1,110,589 bytes, SHA256
`1dfb17d8dabdc818a9b2e0403fc8a9323cb169233f5806e3282edfe1ad121aee`.
The new public pointer retains both prior snapshots unchanged; the complete
tables include 30,778 county-party totals and 758 reviewed-county state-party
sums. Astro check, seven participation tests, build/four caucus tests and
Pages preparation pass; the prepared artifact is 987,252,117 bytes after
verification of all 94 relocated downloads. All 51 focused data tests pass.
The four local display modes source-match all four historical years, 204 scope
cells and 52 UF rows, with 178 complete download links retaining every previous
165. Proof is `local-browser.json` in the review directory. Renderer/maps
remain unchanged and were not redundantly retested.

UI commit `cbca780ecbcb0479db77d8cae90fe1c30a471172` is live: exact Pages
run `42078976258` succeeded. Production proof `production-browser.json`
in the same review directory confirms all four year rows, all 204 scope cells,
all 178 complete download URLs (retaining every previous 165), all 52 UF rows
and exact public pointer/registry/renderer bytes in four display modes.
The deployment receipt is saved beside it; both publication manifests verify.
Keep both previous immutable historical snapshots. Next historical work is
the separate 2016 source-specific review, not another completed 2018 check.

D.C. official follow-up:
`data/county-source-reviews/20261105-dc-official-01/` retains all seven native
JSON/CSV/XML/PDF data/report originals and exact HTTP/hash receipts. Its complete
CSV has 10,011 rows across 144 reporting precincts. Precinct registrations and
ballots reconcile to the separate citywide 457,371 registered / 185,086 ballots.
The four nonvoting-delegate candidate/write-in counts reconcile exactly between
CSV and citywide JSON (180,979 votes). This is not a voting House district, nor
the different shadow Representative/Senator contests. Do not merge it silently
into the current 435-district map or call the map gap filled.

Important next-source handling: JSON gives over/undervotes a spurious REP party
code; native CSV leaves it blank. Those are ballot-accounting rows, not
Republican candidate votes. The delegate candidate sum plus 602 overvotes and
3,181 undervotes is 324 below the separate ballot summary; retain the unresolved
difference. Native RCV flags do not independently establish a final round.
EarlyVotes is zero while ShowEarlyVotes is false, not evidence that no early
ballots were cast. These acquisition originals are not approved 2026 map
geometry. The scoped publication below supersedes their original
acquisition-only status; use the saved originals rather than repeating
app/API discovery.

The scoped D.C. count package is now published separately in
`data/county-source-reviews/20261105-dc-reviewed-01/`; it does not overwrite
those acquisition originals. All 10,011 native CSV rows reconcile with all
1,478 XML summary records across 363 contests. All 722 party-label differences
occur on over/undervotes, never candidate lines. Preserve both source literals.
Seven complete tables retain four delegate candidate lines, four delegate-party
totals, two accounting lines, the separate city participation record, all 144
native participation records, all 864 native delegate/candidate/accounting
records, and all 1,478 all-contest native summary records. The other offices
and ballot options retain their exact contest names; they are not pooled
with delegate votes or treated as single-vote ballot totals.

The delegate-party sums are DEM 157,979, REP 11,583, STG 10,275 and NPN 1,142.
The unresolved 324-ballot difference, native RCV flags, missing final-round
verification and hidden early-vote display remain explicit. All 34 focused
D.C./party/Monroe tests pass. Every one of the package's 18 files and the
complete ZIP reproduce byte-for-byte outside the repository. Archive size is
216,186 bytes, SHA256
`f63a0430c67f7f6baab1f60f37263618940e63cbed332899dde3a139d3338269`.
Reproduction proof is in
`data/county-source-reviews/20261105-dc-publication-01/`.
Data/tools commit `7e4262e73e021c3362ae510360513b0187cd95ee` is pushed.
Release `voter-county-dc-delegate-20261105-01` and every one of its seven pinned
full CSV endpoints were independently downloaded and matched byte-for-byte.
The source-review registry now links the complete package and all tables,
with no precinct-ledger coverage promotion. Retained-download integration
checks passed in all four local display modes: all 186 complete URLs retain
the previous 178; all four historical House years, 204 scope cells and 52 UF
rows remain source-matched. Astro check, seven participation tests, build/four
caucus tests and Pages preparation pass (987,259,532 bytes after verifying
94 relocated downloads). County pointers and renderer are unchanged, so their
completed map suites were not repeated.

UI commit `9d8e6e3afc898634699f79af8fb68a1cbb504bc4` is live: exact Pages
run `42083410340` succeeded. The saved `production-browser.json` verifies
all four display modes, all 186 complete URLs (retaining every previous 178),
all four historical House years/204 scope cells, all 52 UF rows and exact
pointer/registry/renderer bytes. Exact deployment and production evidence is
in the separate D.C. publication directory; its complete manifest and the
18-file immutable data manifest both verify. The temporary preview is stopped.
Do not mark the D.C. map gap or precinct ledger complete, and do not repeat
this completed publication or reinterpret the unresolved 324-ballot difference.
Next actionable work remains genuine 2026 Maine/Pennsylvania county sources,
followed by the scoped 2016 historical House export.

Montgomery County official 2026 alternative, released and production-verified:
Fresh actual HTTP acquisition found a newly declared General Election dashboard
and PDF on the county's official results index, despite an older web-search
cache still showing only the primary. Do not infer the available election from
the search cache. The alternative Chester results path returned 404 and Maine's
official results page returned 403; both receipts are preserved, not treated
as evidence that every alternative is unavailable.

`data/county-source-reviews/20261105-montgomery-reviewed-01/` retains six
complete unmodified originals: county index, native dashboard, vendor portion
CSV, native results JSON, eight-page county PDF and separate ballot-processing
TXT, with exact URL/time/hash receipts. No map-service token pattern was found.
All 3,634 native candidate rows and every voting-mode vector reconcile across
CSV and JSON, including six explicit zeroes; all 46 listed candidate/option
lines reconcile with the PDF. The PDF additionally supplies 25 separately
printed unresolved-write-in lines, including a vote-for-seven local commission
absent from JSON/CSV. Its 6,743 selections are not 6,743 ballots or voters.
Unresolved write-ins have no native party label; do not invent one.

House votes are 389,901: DEM 268,823, REP 120,367 and 711 unresolved write-ins
with a blank party. These are separate from 392,630 county ballots and 628,331
registrations (printed 62.49%). The PDF update is November 4, 2026, 2:07:10 PM,
timezone unestablished; native JSON export/generation UTC timestamps are
retained separately. Reporting 428/428 applies only to Election Day in-person
ballots, not completed counting. All results remain unofficial and updating.
Mail returned 109,191 differs from mail counted 107,547; all nine processing
observations remain separate from candidate votes and participation.

Three parent precincts have genuine split portions. All 431 exact
parent-plus-split identities are retained; parent-only deduplication would lose
ballots/registrations. Governor, House and state-House district partitions
independently cover the same portions. All 1,630 portion/contest accounting
records retain native under/overvotes and unclassified residuals; only county
residual sums reconcile to printed unresolved write-ins. Native Reporting_flag
zeroes are not used to override the county's reporting notice.

The ten complete tables contain 71 candidate/option/write-in lines, 213
candidate-mode observations, 16 office/literal-party/kind totals, 25 contest
totals, separate county participation, nine processing observations, 431 portion
participation rows, 1,630 accounting records and both complete 3,634-row native
candidate tables. All 20 package files and the ZIP reproduce byte-for-byte
outside the repository; independent native-CSV/PDF aggregation matches all 16
office/party vectors. All 68 focused county tests pass. Complete ZIP:
587,034 bytes, SHA256
`f40f5454fc6332e5828770f7d51eb313186d58f7ceb5c0dd2851de7eb24f32d3`.
Publication proofs are kept separately in
`data/county-source-reviews/20261105-montgomery-publication-01/`.
Data commit `ddb9e8c86c772b41431cd5c7e0d1fd4eeb615563` pins all ten complete
CSV links. Release `voter-county-pennsylvania-montgomery-20261105-01` contains
the complete ZIP; all eleven endpoints were downloaded and byte-matched.
The download-only registry entry leaves every prior review object unchanged.
Astro check, seven participation tests, build/four built-in tests and Pages
preparation pass. Four local desktop/mobile JS/no-JS checks retain all 194
previous URLs and expose all 205 complete downloads.

Useful UI commit `d9e2c2e0e5b697b8ce8653fdfc37c21982426977` is on main;
exact Pages run `42094445197` succeeded. All four production desktop/mobile
JS/no-JS checks pass against the exact registry, renderer and pointer bytes,
retain all 194 prior URLs and expose all 205 complete downloads. The 52 UF
rows, 204 historical state/year scope cells across 2024/2022/2020/2018 and
4,896 county candidate-ledger rows are unchanged. All 20 immutable package
files still match the pinned data commit and the package manifest. The
temporary preview is stopped; publication proof checksums are saved separately.
No new geometry, statewide Pennsylvania completion, demographic estimate,
county-map fill or precinct-ledger promotion is approved. Next actionable work
remains genuine 2026 Maine/Pennsylvania county alternatives, followed by the
scoped 2016 historical House export. Keep schedule #4 active; do not repeat
completed source reviews or unchanged map suites.

Bucks County official 2026 alternative, released and production-verified:
`data/county-source-reviews/20261105-bucks-reviewed-02/` retains the county's
declared native 2026 report with map-service tokens explicitly redacted, the
unmodified official linking page, three complete original CSV reports,
five-page original summary PDF and exact HTTP/hash receipts. The complete
unredacted native HTML remains in the private session acquisition cache;
the public receipt records both original and redacted bytes/hashes. No CSV,
PDF, candidate, party or participation data is removed. GitHub rejected the
first unpublished commit for an embedded map token. A clean branch based on
the last pushed revision avoids publishing that commit or bypassing protection.
The printed report update
is November 4, 2026, 4:15 PM; its timezone is not independently established.
All results are unofficial. Both Absentee and Mail-In and In-Person Ballots
explicitly remain Partially Reported despite the native 304 of 304 reporting
counter. Do not equate reported units with completed counting.

The reusable reviewer reconciles all 46 candidate lines and 138 candidate-mode
counts across summary CSV, accessible HTML and PDF; all 3,949 native unit
candidate observations, including 343 explicit zeroes, sum to those same
county vectors. All 15 contest ballot totals match their native unit sums.
The four office families separately partition the same 304 county units without
overlap. The seven complete tables also retain 15 office/literal-party totals,
15 contest totals, 304 native participation records and separate county
participation. All 17 package files and the complete ZIP reproduce byte-for-byte
outside the repository; 49 focused Bucks/D.C./party/Monroe tests pass. A second,
independent native-unit CSV aggregation matches every office/literal-party total.

House votes are 302,786: Dem 158,908, Rep 142,796 and Nonpart write-ins 1,082.
These are not the separate 305,485 county Ballots Counted or 487,385 Registered
Voters. The 2,699-ballot difference stays unclassified, not inferred undervotes
or overvotes. Preserve both CSV party literals and accessible-HTML labels,
including Fwi, Ind and Lib in other contests. Provisional candidate zeroes
do not establish zero provisional ballots. Native RegularCheckIns is labeled
VOTES CAST; its sum matches county ballots. Preserve all 61 differences between
native unit names and map keys without normalization or map approval.

The safe complete archive is 368,884 bytes, SHA256
`7f567f6acdd274df3ea444d1cfb60a21927c2a677e3f65c3cd1eb40209e356bb`.
Reproduction, independent reconciliation, token-only redaction proof and focused-test receipts are in
`data/county-source-reviews/20261105-bucks-publication-02/`. Allegheny's
county-declared Clarity report returned 403; preserve that receipt, use no
apparent counts and do not retry the blocked endpoint. This Bucks acquisition
is county counts only, not statewide Pennsylvania completion, a new map,
new precinct coverage or demographic turnout. Existing map coverage remains
48 states / 3,060 county equivalents. Safe source/tools commit
`3d2be9ada0d1022511815fd8edb9d96fc7666b54` is pushed, without the blocked
unpublished commit. Release `voter-county-pennsylvania-bucks-20261105-01`
and all seven pinned complete CSV endpoints were independently downloaded and
byte-verified; `release-verification.json` records all eight receipts.
The new registry entry preserves every prior review object unchanged and uses
`coverage: []`. Astro check, seven participation tests, build/four caucus tests
and Pages preparation pass; the prepared site is 987,267,961 bytes after
verifying all 94 relocated downloads. Four local display modes retain every
previous 186 complete URL among 194, all four historical House years/204 scope
cells and all 52 UF rows, with every registered review caveat source-matched.
The map renderer and pointers remain unchanged, so their completed suites were
not repeated.

UI commit `c7134b3dbd0bd921f8c6d38fc32c88336ff28c16` is live: exact Pages
run `42089332833` succeeded. Production verification passed on its first
attempt in all four display modes: 194 complete downloads retain every prior
186, all four historical House years/204 scope cells and all 52 UF rows remain
source-matched, and every review's full URLs/caveats and exact public
pointer/registry/renderer bytes match. Exact deployment and production proofs
are saved in the separate publication directory; both complete manifests
verify. The temporary preview is stopped.

The active local publication branch is
`voter-participation-bucks-publication-20261105`, tracking the safely
fast-forwarded remote `voter-participation-analysis`; the blocked unpublished
commit is not its ancestor and was never pushed or bypassed. Carry the final
production-proof commit to main with the next useful UI update, not a redundant
proof-only deployment. Do not repeat this completed Bucks, Monroe, D.C. or
2018 publication. Continue other genuine 2026 Maine/Pennsylvania county sources,
then the separate 2016 historical source review. Keep schedule #4 active;
national coverage and historical/map gaps remain unfinished.

Pennsylvania official county alternative, November 5 follow-up:
`data/county-source-reviews/20261105-monroe-official-01/` retains Monroe's
complete native all-contest workbook, seven declared contest pages, county
overview/export form, Act88 PDF and exact HTTP receipts. The reviewer
`scripts/review-monroe-2026-county-results.py` reconciles all 22 candidate rows,
66 candidate/mode rows and 715 native reporting-unit/candidate rows against
every printed contest total and every workbook row. House and state legislative
district partitions each cover the same 55 native county reporting units without
overlap; this establishes count scope, not geographic boundaries.

The six complete tables include seven contest totals, 13 county/office/literal
party totals and the separate county participation observation. Monroe's
60,481 House candidate votes comprise 35,157 DEMOCRATIC, 25,190 REPUBLICAN and
134 native Nonpartisan write-ins. Preserve the workbook's Nonpartisan label
and HTML's blank write-in label separately. These votes are not the county's
61,025 tabulated ballots or 118,818 eligible registered voters. The separate
Act88 report's 18,232 received mail ballots are not counted mail ballots or
candidate mail votes. The native result update is November 3, 2026, 11:04:59 PM;
all results remain unofficial.

Philadelphia's accessible official overview explicitly says
`*** Testing in Progress ***`. Its complete original and receipt are retained
as excluded evidence; none of its apparent counts is promoted. Do not retry
the previously blocked statewide portal or relax the national provider's
17 test-data exclusions. Continue other actual official county alternatives.
This is one county's reviewed counts, not statewide Pennsylvania completion,
an approved new map or new precinct coverage. Current map coverage remains
48 states / 3,060 county equivalents. The package reproduces all 33 files
and its complete ZIP byte-for-byte; all 29 focused tests pass.
Publication/reproduction receipts live separately in
`data/county-source-reviews/20261105-monroe-publication-01/`.
Source/tools commit `17c116bea04a42a364daee08bc028f3beca3737f` is pushed.
Release `voter-county-pennsylvania-monroe-20261105-01` and every one of its
six pinned full CSV endpoints were independently downloaded and matched.
The complete archive is 273,559 bytes, SHA256
`0cd09dde828b4d51949d96723ee9ca84627d6125c2db3e25ee2bcfd1b192def5`.
The registry/download-only integration passes Astro check, seven participation
tests, build/four caucus tests and Pages preparation (987,245,344 bytes).
All four local browser modes retain the previous 158 complete links among
165, verify every review's full URLs and caveats, all three historical House
years and all 52 UF rows. Existing county pointers and renderer are unchanged;
do not rerun their completed map suite. Exact Pages run `42077485666` for
`eaca35d1ba38596ab39ad7508394a01cc17adc5d` succeeded, and production checks
passed all four display modes with all 165 complete download links, retaining
the previous 158; all three historical House years, 153 scope cells and 52 UF
rows remain source-matched. Deployment and production browser proofs are saved
in the separate publication directory. Monroe's scoped counts are live; this
does not close the Pennsylvania statewide map gap.

The user supplied NYT's 2026 Senate precinct-map page and full coverage notes.
The source-lead audit is
`data/precinct-source-reviews/20261105-nyt-senate-01/acquisition.json`: eleven
states, 29,055 reported precincts out of 41,168 declared in those states.
These are real finer-resolution source leads, not acquired files or nationwide
completion. Prioritize public/native GA, SC and NE Senate data alongside county
coverage. Keep Senate separate from the current House county map, preserve
approximate-boundary caveats and all reported party labels, and never infer
votes from map colors or allocate county totals into precincts. Direct NYT
retrieval returned 403; public GitHub search found the known 2024 repository,
which is not proof that no 2026 release exists.

The latest additional request is complete party vote totals for later analysis.
`scripts/export-county-party-votes.py` now validates original district response
receipts, literal candidate vectors and county reconciliation before exporting
four complete party/candidate tables. The current reviewed source yields
9,608 county-party rows, 12,075 county/district candidate rows, 220 state-party
rows and 1,318 district-candidate rows, preserving 34 native party labels.
County coverage is 48 states / 3,060 equivalents. State-party coverage is 49
states / 418 valid House district sources; Pennsylvania's 17 district originals
explicitly say `test_data: true` and are excluded rather than promoted. Maine
has scoped district candidate totals but fails county-vector reconciliation.
The full party ZIP includes all original provider responses/receipts, including
excluded originals documented in the audit. New county-review archives regenerate
these exports automatically. Exports remain candidate votes, not participation.

Work in this order: **2026, 2024 gaps, 2022, 2020, 2018, 2016, then every earlier
even year through 1964**. Include midterms. Use consolidated national and
multi-state datasets first, validating each jurisdiction's scope independently;
use state and county acquisition for genuine gaps rather than rebuilding an
available compilation one county at a time. Do not add only one example state
per year. While a newer source downloads or
awaits publication, acquire independent historical batches rather than idling.
Record unresolved newer-state work and return to it; do not silently abandon it.

The existing precinct-only state/year checklist is `public/precinct-coverage.csv`, with
`PRECINCT-COVERAGE.md` as its readable counterpart. Both track all 1,632
state/election cells. This plan specifies the work, not a second completion ledger.
Track county coverage separately; county publication does not complete precinct
cells. Generate the precinct ledger with `scripts/build-precinct-coverage.py`; do not hand-edit
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
Hans source commit **`b2e53eb9e4a510bb19a8cf2e1cc5243c6eeff9ce`** is pushed.
Immutable release **`voter-precinct-virginia-locality-counts-20261105`** is bound
to that exact source commit. The whole archive was anonymously redownloaded:
HTTP 200, exact size/SHA/CRC/member set, all 381 file checksums and every one
of the 357 decompressed original-response receipts pass against the source.
Proof: `files/virginia-native-locality-count-remote-release-proof-01.json`.

The new lightweight source-review registration preserves the earlier download
and adds this complete package. Only the VA2026 worklist row changes; all
1,632 cells remain incomplete. Renderer/colors/default/zoom are byte-unchanged.
All 64 focused tests pass. Astro reports zero errors/warnings and five existing
hints; build/four chart tests pass. Pages preparation preserves 94 byte-identical
relocated assets and a **986,267,819-byte** site. Four source-matched local
browser modes pass **70 exact complete-download links and seven whole CSV
endpoints**, including the **2,537-row**, **6,061,645-byte** native-method CSV,
SHA-256 `d02d1f1a7e664a78c0b9b69f8d179c0134c4997d7a8f84c54849f05674465597`.
Proof: `files/virginia-native-locality-count-ui-local-browser-proof-01.json`.
Hans UI commit **`96a7f30cb2bf1a5d83c8d1673525e8ea1d6f92be`** is pushed.
Its exact production deployment **42018215942** succeeded; unqueried production
metadata matches the commit, and all four desktop/mobile by JavaScript/no-JavaScript
modes pass the 70 exact links and all seven whole CSV endpoints.
Proof: `files/virginia-native-locality-count-ui-live-browser-proof-01.json`.
Do not rerun this finished count-only production suite.

The independent full geometry diagnostic is complete in
`files/virginia-current-reference-geometry-audit-01.json`. It compares the
actual original report's numeric precinct IDs, preserving source strings and
documenting only whitespace removal/four-digit zero padding, not deriving IDs
from display names. All **2,529** result identities match; two geometry-only
identities (`059/0700`, `159/0502`) remain unassigned. There are **67**
null/invalid fragments across **63** identities, including **nine null
geometries**, which remain unmodified. Among 2,468 valid dissolved identities,
**692** material overlap pairs involve **764** identities; these are withheld.
Labels are 2,276 literal matches ignoring case/whitespace, nine number-only
reference labels and **244 unreviewed/conflicting literal labels**. No fuzzy
matching or invalid-shape repair is approved. There are **1,205** precincts
whose published method vectors exhaust their locality/House summary scopes;
**776** also pass the shape/overlap screening, before label, virtual-unit,
district-split and election-applicability review. This diagnostic is not yet a
portable tested mapped supplement or map approval.

The portable reviewer is now
`scripts/review-virginia-2026-reference-geometry.py`, with its full reproducible
output at `data/precinct-source-reviews/20261105/VA-2026-reference-geometry-audit-01.json`.
It verifies every input checksum and original receipt, the complete 7,426-ID
capture, whole-identity validity, material overlaps, numeric formatting and
literal labels. All 2,529 native units explicitly have `isVirtual:false`.
After literal-label, virtual-unit and single-House-part gates, **710** precincts
remain supported candidates, not 776 approved maps. Twelve new geometry cases
bring the focused Virginia/Wyoming/coverage selector to **76 passing cases**.
The audit itself does not approve maps or certify election-day boundaries.

The agency's archived current-boundary page explicitly links the captured
webmap, whose operational layer declares this exact public union layer.
The layer's actual data edit is **September 22, 2026, 12:45:01.678 UTC**,
distinct from its older item-creation/metadata dates. A provisional map builder
has been validated for the 710 supported precincts using that **2026 official
current reference**, explicitly not certified election-day shapes. It preserves
all withheld results, raw fragments, method residuals and separate native
turnout/registration observations, without inferred rates.

`scripts/build-virginia-2026-precinct-results.py` re-runs the complete geometry
audit and verifies this exact provenance chain before mapping. The complete
immutable output is `data/precinct-results/20261105-virginia-02/`.
There are **710 mapped/colored precincts across 57 localities**, with no material
mapped overlaps and every shape exactly equal to its supported native fragment
union. All **2,537** reporting vectors remain in complete JSON and CSV-gzip,
all **2,529** native participation observations remain separately downloadable,
and all **985** earlier blank totals are preserved. No final/group rates
or certified election-day shapes are asserted. All earlier source-review
bytes and **357** decompressed original-response receipts pass.

The archive-only offline rebuild is **byte-identical**, including exact ZIP
members/CRC and all **393 checksums**. The full ZIP has **83,374,714 bytes**,
SHA-256 `f829118617e54ff12f4680b4d2758cd03d2a08fd8162bb90597d902ab81fb788`.
Proof: `files/virginia-supported-precinct-package-proof-02.json`.
Twelve additional focused map/provenance cases bring the combined selector to
**88 passing cases**.

Hans source commit **`5b1665d31deb80c7c4d5a57b7f8c8d8bf93daedc`** is pushed.
Immutable release **`voter-precinct-virginia-maps-20261105-02`** resolves to that
exact commit. The whole archive was anonymously redownloaded: HTTP 200, exact
size/SHA/CRC/member set, all 393 checksums and every decompressed original
receipt match the source. Proof:
`files/virginia-supported-precinct-remote-release-proof-02.json`.

The public registry now appends this snapshot, preserving all earlier entries.
Only VA2026 changes in the 1,632-cell worklist; all cells remain incomplete,
and the new map's publication status is `snapshot_ready` pending live proof.
Renderer/default/red-blue palette/zoom code is byte-unchanged. Seven targeted
Node integration cases pass; Astro reports zero errors/warnings and five
existing hints; build/four chart cases pass. Pages preparation preserves all
94 byte-identical relocated assets and a **986,270,621-byte** site.
Four source-matched local browser modes pass all **73** complete-data links,
retaining all **70** previous links, all seven whole count CSV endpoints,
all 710 exact precinct counts/margins/fills, all 133 Virginia county background
fills, actual native ballot/registration details with rates withheld, selection
fit, buttons, wheel, post-fit double-click, mobile two-pointer pinch, year
switches, state fallback and no overflow. Proofs:
`files/virginia-supported-precinct-local-browser-proof-02.json`,
`files/virginia-supported-precinct-local-downloads-proof-02.json`.

Hans UI commit **`a92b2eef7f87bba5d1c10b90c44a86b4a0fe2714`** is pushed.
Its exact deployment **42020447353** succeeded; unqueried production metadata
matches the commit. All four desktop/mobile by JavaScript/no-JavaScript modes
pass **73 complete-data links and seven whole CSV endpoints**. The production
map suite independently passes all **710** exact precinct counts/margins/fills,
all **133** county background colors, the Pennsylvania state fallback, native
ballot/registration details with withheld rates, actual feature fit, buttons,
wheel, post-fit double-click, two-pointer mobile pinch and year switches.
Proofs: `files/virginia-supported-precinct-ui-02-deployment-01.json`,
`files/virginia-supported-precinct-ui-02-live-browser-proof-01.json`,
`files/virginia-supported-precinct-live-browser-proof-02.json`.
The registry now marks the mapped subset `live_verified_partial`; only VA2026
changes to `published_partial` in the worklist, with all 1,632 cells incomplete.
Hans metadata commit **`3e6052fe532775c780773d54e812458d37673164`** also passed
its exact deployment **42021398854**. Unqueried live registry, worklist, both
other source registries and unchanged renderer bytes match exactly; the already
finished map matrix was not repeated for this metadata-only change. Proof:
`files/virginia-live-flag-publication-proof-01.json`.
Do not rerun this finished map or count-only production suite as a substitute
for new acquisition.

**Next executable actions:** continue the next 2026 jurisdiction.
Preserve all source fragments, unmatched identities and exclusions. Approve only
explicitly supported scopes; do not repair the earlier export, allocate missing
county modes to precincts, borrow older geometry or mark the VA2026 cell complete.

## Oklahoma 2026: official export portal access observations

The official November 3 general-election page explicitly declares
`https://results.okelections.us/OKER/?elecDate=20261103`; do not substitute a
guessed hostname or guessed API. The complete **134,096-byte** agency page and
its navigation are preserved in session `files/precinct-expansion-sources/OK-2026-native-01/`.
The declared portal returned HTTP **403** to both ordinary HTTP (**118 bytes**)
and ordinary public Chromium (**520 bytes**). Both original response bodies,
URLs, statuses, sizes and decompressed SHA-256 receipts are retained; no access
challenge was bypassed. These are access observations, not proof that data do
not exist.

Followed the real Oklahoma County election-board page (**2,715,111 bytes**),
Tulsa County homepage (**26,390 bytes**), its declared election-board page
(**24,420 bytes**) and actual election-results page (**18,747 bytes**).
Oklahoma County's "Election Returns" points to the state elections homepage.
Tulsa's results page advertises the official state 2026, 2025 and 2024 indexes,
not an independent county precinct export. No new counts, turnout rates,
boundaries or mapped precincts are approved from these HTML/access receipts.
Preserve the prior county/state coloring and keep the OK2026 cell incomplete.

**Next executable actions:** seek independent official county statements or
an accessible agency-published export, without bypasses or invented endpoints.
Do not repeatedly request the denied portal; continue other 2026 jurisdictions
while this access gap remains.

## Alabama and Arkansas 2026: new native acquisitions in progress

Alabama's actual official results URL is
`https://www2.alabamavotes.gov/electionNight/statewideResultsByContest.aspx?ecode=1001305`.
Its **111,462-byte** original explicitly advertises an ASP.NET
`hlnkExportData` postback, not a guessed static file. Submitting that public form
returned the full **263,261-byte** `sosEnrExport.xlsx`, decompressed-original
SHA-256 `cdbde2527f3f232c82565e900b34d544bc81b3d553e4d8aac9c454057c4f3d60`.
`AllResults` has **5,613 county-level candidate rows across all 67 counties**,
all explicitly labeled election `1001305`, `2026 GENERAL ELECTION`.
The separate `Statistics` sheet has **67** nonempty county observations totaling
**1,693,621 ballots**, followed by formatted blank rows; these blanks are not
zero observations. It has no registered-voter column. All originals/receipts
are in `files/precinct-expansion-sources/AL-2026-native-01/`.
All **67 actual county-selector links** are now followed, retaining their complete
native summaries and receipts. Their separately reported ballots, registrations,
printed percentages and native update timestamps are independently reconciled
with the workbook and statewide page: **1,693,621 ballots** and **3,852,947
native registered voters**. The workbook itself has no registration column;
registrations and source-reported percentages come only from the actual county
HTML, not from candidate votes or another election. The statewide printed
percentage is **43.96%**, retained explicitly as a source-reported administrative
percentage; analysis rates remain withheld pending electorate definitions.
Native county codes are **not FIPS**: `"01"` is Jefferson and `"04"` is Autauga.
No padding or assumed crosswalk is allowed.

The stdlib-only portable reviewer is
`scripts/review-alabama-2026-native-results.py`; final complete package:
`data/precinct-source-reviews/20261105/AL-2026-native-counts/`.
It retains **all 5,613 native candidate rows**, **73 county-by-House vectors**
and **67 separate participation observations**. All **822** candidate cells in
the reviewed county summaries match the workbook, and all **10** first-page
state contests (including all seven House districts) independently reconcile.
All county ballots/registrations sum to statewide source totals; every native
county timestamp matches its workbook observation. The **5,547** wholly blank
formatted statistics rows are not observations and are never filled with zero.
No precinct geography, FIPS joins or analysis rates are approved.

Eighteen Alabama tests plus the existing Arkansas/coverage selector pass
(**39 total**). Independent verification uses a separate XLSX reader to match
every native candidate cell, checks all House margins against all candidates
(including write-ins), independently extracts every county's native participation
fields, verifies all **76 checksums** and **70 original receipts**, and reproduces
the complete archive byte-identically using only the extracted package.
ZIP: **1,726,378 bytes**, SHA-256
`447081ce84d9755e323aaae2b21016f9e77281157f3a4d38057ef6b9d65883f2`.
Proof: `files/alabama-native-count-package-proof-01.json`.
Hans source commit **`11401d43852bf1808babc38136ce5cd71452d2a0`** is pushed.
Immutable release **`voter-precinct-alabama-native-counts-20261105`** is pinned to
that exact commit. Its entire anonymous public download matches the local archive;
all 76 file checksums, 70 original receipts, exact archive members and CRC pass.
Remote proof: `files/alabama-native-count-remote-release-proof-01.json`.

The registered source review pins this exact source and release and adds four
complete downloads: the whole ZIP, all 73 county-by-House vectors, all 67 separate
native participation observations and the complete 5,613-row candidate table.
Only AL2026 changes in the 1,632-cell ledger; all cells remain incomplete.
All previous source entries and the renderer/map configuration remain unchanged.
Local source-matched checks pass **81 complete links**, retaining all **77**
older downloads, **13 whole CSV endpoints**, and all four desktop/mobile by
JavaScript/no-JavaScript modes, with no overflow and 2026 still the default.
Proof: `files/alabama-native-count-ui-local-browser-proof-01.json`.
Five focused coverage tests pass; the complete production build and Pages
preparer pass, verifying **94** byte-identical relocated downloads and a
**986,275,862-byte** artifact. This metadata-only integration does not repeat
unchanged renderer suites. The previously documented unrelated UK full-validator
failure remains outside this batch.
Hans UI commit **`686968e68cdd9d45ea41cc8783a0f7fce91cb3f9`** is pushed.
Its exact deployment **42024792976** succeeds. Unqueried production registries,
worklist and unchanged renderer bytes match this commit. All four actual
desktop/mobile by JavaScript/no-JavaScript production modes pass **81 complete
downloads**, retaining all 77 older links, and **13 whole CSV endpoints**.
Proofs: `files/alabama-native-count-ui-publication-proof-01.json`,
`files/alabama-native-count-ui-live-browser-proof-01.json`.
No new Alabama map, inferred rate or demographic estimate is approved.

Arkansas's official results index explicitly links the actual public application
`https://arkansas.tally-enr.com/#bucket=results&filter=Federal&contest=eafd140a-9378-43a2-bd6d-f8661524139b`.
Ordinary browser navigation confirms **November 3, 2026**, unofficial election
**`11b07106-031e-4d7c-911a-d01fb473d6dd`**, version **`v173`**. Actual browser
requests expose full election metadata, separate native turnout, federal contest
results, contest search, GIS manifest and county geometry. The actual Download
menu offers **Full Election**, **Current View**, **Selected Contest**, each in
CSV or JSON; acquire the full native election, not just the visible federal cards.
The GIS manifest declares precinct ID **`PPartID`** and label **`PPartName`**;
its March 9, 2026 generation date alone does not certify election-day geometry.
Complete captured originals and receipts are in
`files/precinct-expansion-sources/AR-2026-native-01/`.

The actual full-election downloads are now acquired: **55,645,416-byte JSON**
(SHA-256 `079518a65d5f66385ec1cb5cedcd93a02973d6ae24a0793427af8d08c9fe14bd`)
and **25,033,991-byte CSV**
(SHA-256 `782c094c5f4fbb928eb6819630f5a2eec504ee1e326401f21db195777b7aefab`),
covering **1,315 contests**. All **106,922** original CSV candidate rows match
their native JSON identities, labels, parties, totals and all three voting modes.
The JSON omits **5,401** candidate totals that CSV serializes as zero; the complete
originals retain both formats and the normalized counts preserve those omissions.
Native precinct IDs are not globally unique: use county + precinct ID, never a
statewide bare-ID join.

The portable offline reviewer is
`scripts/review-arkansas-2026-native-results.py`. The complete immutable count
package is `data/precinct-source-reviews/20261105/AR-2026-native-counts/`.
All four House districts' precinct/county/state candidate and voting-mode sums
reconcile. **2,769 House reporting vectors** preserve **83 omitted totals**;
**2,768 separate precinct participation observations** preserve **82 omitted
ballot totals** and every native registration omission. Observed precinct ballots
sum exactly to all 75 counties and **893,026** statewide ballots. The separately
captured version-`v173` API matches all 75 county ballot/registration scopes and
**431 federal summary candidate cells**. No source serialization default repairs
the normalized data; native reported percentages are kept separate from withheld
analysis rates. No maps, residential-mode allocation or electorate definition
is approved.

Sixteen focused Arkansas cases plus five coverage cases pass (**21** total).
Independent archive verification checks every normalized House vector and native
participation field, all **17 file checksums**, all **12 original response
receipts**, exact members/CRC, and the portable source code. Rebuilding using
only the extracted archive is **byte-identical**. The complete ZIP is
**11,101,053 bytes**, SHA-256
`2a48bbc62c55b074c877172c94da4b02de0546211322c576200818e5b16548a9`.
Proof: `files/arkansas-native-count-package-proof-02.json`.
No frontend/template application code is redistributed.

Hans source commit **`36fb8b109d0044a1d3cc7527a2810cdf70f3dc2d`** is pushed.
Immutable release **`voter-precinct-arkansas-native-counts-20261105`** is bound to
that exact commit; its entire public archive was anonymously redownloaded with
byte equality, member/CRC, all 17 checksum and all 12 original-receipt checks.
Remote proof: `files/arkansas-native-count-remote-release-proof-02.json`.

The registered count review pins this exact source and release. It adds the full
ZIP, every House reporting vector, separate native participation observations,
and the complete original 1,315-contest CSV-gzip as four real data downloads.
Only AR2026 changes in the 1,632-cell worklist; all cells remain incomplete.
The map renderer, every older source entry, colors, zoom and 2026 default are
unchanged. Optional per-review table links also work without JavaScript.

Local source-matched production checks pass all **77** complete downloads
(retaining all **73** older links), all **10** complete CSV endpoints including
the 106,922-row native original, and desktop/mobile with/without JavaScript.
Proof: `files/arkansas-native-count-ui-local-browser-proof-03.json`.
Astro check: **0 errors, 0 warnings**; production build succeeds; 21 focused
Arkansas/coverage tests and seven existing publication unit tests pass.
Pages verifies all **94** relocated bulk downloads byte-for-byte; prepared site
is **986,273,229 bytes**. The build validator's obsolete source-link count was
updated to registered reviews/tables, actual optional participation files and
county snapshots; all participation assertions pass. The full unrelated site
validator subsequently stops at the existing UK homepage topic-card assertion
(23 actual versus 16 expected, unrelated to this integration); do not alter
UK content or its assertion as part of this election-data work.

Hans UI commit **`9ce96c69f241dcee0eda3a3c010ec0a56727a520`** is pushed.
Its exact deployment **42023102253** succeeds; unqueried live registries,
worklist and unchanged renderer bytes match this commit. All four actual
desktop/mobile by JavaScript/no-JavaScript production modes pass **77 complete
downloads**, preserving all 73 previous links, and **10 whole CSV endpoints**.
Proofs: `files/arkansas-native-count-ui-publication-proof-03.json`,
`files/arkansas-native-count-ui-live-browser-proof-03.json`.
This count-only review does not acquire mapped Arkansas precinct coverage.

The public "View County Results" control is a paragraph, not a button; following
its actual visible text succeeds. Clicking the real "Arkansas - U.S. Senate
Results" button then selects Arkansas County and captures its actual
`GetContestResults?...&locationId=05001` response (**42,163 bytes**,
`native-public-response-017`). The page now explicitly offers "View Precinct
Results". Like the county control, follow its actual visible text rather than
assuming a button role; the guessed button-role locator times out.
The initial county-only observation did not capture precinct geometry. Completing
the actual precinct-list and McFall-leaf navigation now exposes the real browser
request to
`https://gis.tally-enr.com/gis/states/arkansas/counties-precincts/05001-precincts.json`,
which returns **HTTP 403**. Preserve this actual network evidence in
`files/precinct-expansion-sources/AR-2026-native-01/native-app-network-precinct-leaf.json`;
do not guess alternate Tally paths or repeatedly request the denied asset.
All new app originals remain separate from the released count package.

An independent official statewide reference is now completely acquired:
`https://gis.arkansas.gov/arcgis/rest/services/FEATURESERVICES/Boundaries/FeatureServer/11`.
The historical GIS-office Searcy update notice is present in search's archived
primary content, but its actual current request redirects to the new GIS Hub.
The captured current Hub declares organization **`PwY9ZuZRDiI5nXUB`**.
Its complete eight-item precinct search independently identifies the actual
service as item **`bf5b2828a59542478f903b62ec83fe48`**. Preserve this current
catalog/item declaration rather than claiming the redirected response still
contains the old notice. The official web-map item
**`ced6585f228c4d7e8fb406c65a5df7ec`** explicitly describes the precinct
boundaries as public-domain records; full licensing and attribution are retained.

All **2,928 native polygons** across **75 counties** are acquired in **15**
bounded pages respecting the service's **200-record** limit. Each page's actual
object IDs match its requested set, with no transfer-limit truncation. Complete
before/after object-ID sets match. All **23 original receipts** and native edit
dates are retained. The edit-date field includes 2026 changes through October 2;
that fact alone does not certify election-day applicability. Session collector:
`files/acquire-arkansas-2026-official-gis-01.py`; complete capture:
`files/precinct-expansion-sources/AR-2026-official-gis-01/`.

The tested offline reviewer is
`scripts/review-arkansas-2026-reference-geometry.py`; immutable package:
`data/precinct-source-reviews/20261105/AR-2026-reference-geometry/`.
It preserves every original polygon page, every native geometry attribute,
all **2,769** reviewed House vectors, all per-vector identity diagnostics and
the portable reviewer. Every source count remains pinned to the previously
released native-count review; no count package or existing map is modified.
Case/whitespace-only literal comparisons produce **427 unique name-only
unconfirmed** vectors, **142 ID-only unconfirmed** vectors, **six conflicting
ID/name** vectors and **2,194 unmatched** vectors. None is automatically joined.
The six conflicts include Garland and Lonoke: a native election location ID can
point to a different polygon than the actual literal name. Numeric equality is
not proof that the two systems use the same identifier namespace.

The complete geometry audit retains **18 invalid native polygons**, **two**
material overlap pairs and **32** subthreshold numerical overlap pairs.
Materiality uses the established Virginia criteria: both more than one square
meter and more than 0.0000001 of the smaller polygon in EPSG:5070.
Seven duplicate reference codes and seven duplicate reference names remain
explicit. Pulaski native location **276**, "Precinct 47", has two House contest
scopes and remains unresolved. No shape repair, vote allocation, fuzzy join,
election-day certification, new map or inferred rate is approved.

**14 focused tests pass**, covering false numeric-ID matches, ID/name conflicts,
county qualification and county-label conflicts, ambiguous reference identities,
split House scope, duplicate result identity, null/empty/nonpolygon/self-crossing
geometry and material overlaps. Independent verification checks all **29 file
checksums**, all **23 original receipts**, every vector classification, complete
native object IDs, all invalid-object identities, exact ZIP members and CRC.
An extracted-archive-only rebuild is **byte-identical**.
Complete ZIP: **27,742,134 bytes**, SHA-256
`fcac6aa268e557ab8264e0bf167b5a9e1947821fc8e2525b4e7acca81e1e8e3f`.
Proof: `files/arkansas-reference-geometry-package-proof-01.json`.

Hans source commit **`2913de35ea2cfb028579d559342ecaacd33f8c9d`** is pushed.
Immutable release **`voter-precinct-arkansas-reference-geometry-20261105`** pins
that exact commit. The whole anonymous remote archive passes byte equality,
all 29 checksums, all 23 original receipts, exact members and CRC.
Remote proof: `files/arkansas-reference-geometry-remote-release-proof-01.json`.
This is complete reference data, not additional approved precinct-map coverage.
The released source package and native count package remain immutable.

The public count-review registration now also declares this independent complete
reference ZIP without changing its existing count-source URL or tables.
Only AR2026 changes in the 1,632-cell worklist; all cells remain incomplete.
The additional download explicitly withholds election-day certification and map
joins. No map source registry, renderer, color, zoom, default year or analysis
rate changes. Local build and five coverage tests pass; Astro check reports
zero errors and zero warnings. Pages verifies all 94 relocated downloads and
prepares a **986,276,515-byte** site. Participation build assertions pass before
the known unrelated UK homepage topic-card mismatch (23 actual versus 16
expected); do not change unrelated UK content or its assertion.
All **19** focused reference/coverage cases pass. Actual local desktop/mobile
by JavaScript/no-JavaScript checks pass **82 complete downloads**, retaining
all **81** earlier links, and **13 entire CSV endpoints**. The new reference
ZIP is also fully redownloaded through its registered link and matches every
one of its **30 archive members** byte-for-byte, including all original pages
and diagnostics. No overflow; 2026 remains the default.
Proof: `files/arkansas-reference-geometry-ui-local-browser-proof-01.json`.
Hans UI commit **`eec343ede2c28a5109780dcec3cb5c3ed67f12de`** is pushed.
Exact deployment **42026945203** succeeds. Its unqueried public metadata and
renderer bytes match the source, and the full live four-mode browser matrix
passes **82 complete links**, all **13 entire CSV endpoints**, and all **30**
members of the independently released reference ZIP. All 81 older complete
links remain. Proof:
`files/arkansas-reference-geometry-ui-publication-proof-01.json`.
No additional Arkansas map joins or participation rates are approved.

**Next executable actions:** Alabama's exact live verification is complete;
do not repeat its successful matrix. Arkansas's complete-reference download
integration is also live-verified; do not repeat its successful matrix.
Obtain explicit county crosswalk/election-applicability evidence
and review source-declared label formats without fuzzy matching. Alabama's
native county-name/FIPS correspondence is another bounded map-enabling task;
never pad its non-FIPS native codes. Keep new map joins and analysis rates
withheld until their exact requirements pass. Do not repeat completed live
matrices as a substitute for acquisition.

### Arizona 2026: complete native candidate export and actual precinct participation

The actual native application's root response explicitly declares
`jurisdiction.mediaExportPath="Arizona/export-110326GeneralElection.json"`.
Complete media export acquired HTTP200, **72,592,544 bytes**:
`https://app.enhancedvoting.com/cdn/results/Arizona/export-110326GeneralElection.json`.
Root application API:
`https://app.enhancedvoting.com/results/public/api/elections/Arizona/110326GeneralElection/data`.
Election identity is **November 3, 2026**, `2026 General Election`, production,
unofficial; media created `2026-11-05T03:50:47.2427526Z`.
Direct `azsos.gov/press` returned HTTP403; that actual response is retained,
not described as acquired declaration HTML or retried. The independently acquired
native API declaration establishes the exact complete media export.

All **15** county pages and their actual API responses were acquired by following
the app's real county-navigation controls, not guessed routes. Complete factual
media/API originals and receipts are cached in
`files/precinct-expansion-sources/AZ-2026-native-01/`.
Frontend HTML, controls, incidental tokens and tracking URLs are discovery
artifacts, not redistributable election datasets.

The export contains **99** statewide contests, **415** county contest scopes,
**143,533** precinct option rows and **1,762** county-qualified precinct identities
with **1,762** complete House vectors. State/federal contests are present;
this is not all local county races. Native precinct/county/state candidate and
mode vectors reconcile. Preserve **282** party-description differences and literal
candidate-name spacing. County API candidate native IDs use a different namespace
from the statewide media IDs; independently compare unique literal county,
contest and candidate names and all counts/modes, retaining both source IDs.
Do not silently substitute one namespace for the other.

The county API inventory includes **1,763** precincts with **1,762** actual
ballot/registration observations. The extra Mohave virtual precinct,
`225_Non-Resident Property Owners`, UUID
`01000000-68b8-edcd-0283-08df2653ea59`, has no turnout observation:
keep its participation missing, not zero. Observed precinct counts reconcile
to every county's **2,248,900** total ballots and **4,374,827** total registrations.
The source's duplicate `voterTurnout` field is a count, not a percent.
The root statewide ballot field is **0**, contradicting positive county totals;
retain and flag it, do not call it zero turnout or silently replace it.
Native active/inactive registration components also fail to explain positive
totals. No rates, API-precinct/media-ID crosswalk or geometry joins approved.

The completed offline reviewer passes **23 focused tests**. All **145,556**
normalized state/county/precinct option rows, **1,762** House vectors, **1,763**
participation inventory rows, **15** county participation rows and **2,023**
independent API option comparisons are verified against actual originals.
The portable package includes all **66** factual media/API originals and receipts,
full options, county/precinct participation, explicit option-namespace diagnostics,
audit and the standalone reviewer. All **75** checksums and **76** archive members
pass; extraction and rebuilding from only the released-style archive reproduces
every file and the ZIP byte-for-byte. Independent proof:
`files/arizona-2026-native-package-proof-01.json`.
Complete ZIP: **15,695,907 bytes**, SHA-256
`8c8626b93899f8f9b935d1d7076a47b1bb75fd850c344f992066faa162ae0cc3`.
The generated source package is preserved at
`data/precinct-source-reviews/20261105/AZ-2026-native-counts/`.

Hans source commit **`7b764000e2feef1054d37d2468b447f43d9e9b71`** is pushed.
Immutable release **`voter-precinct-arizona-native-counts-20261105`** pins that
exact commit. The whole anonymous remote ZIP matches all local bytes, **75**
checksums, **66** receipts and **76** exact members, with valid CRC.
Proof: `files/arizona-2026-native-remote-release-proof-01.json`.
No released package bytes may be replaced or normalized.

The complete ZIP and all five complete CSVs are now registered alongside all
**82** earlier downloads. Only AZ2026 changes in the **1,632-cell** worklist;
all cells remain incomplete. The map renderer, county fallback, source map
snapshots, colors, zoom and 2026 default remain unchanged. All **28** focused
Arizona/coverage tests pass. Astro check: zero errors/warnings and five existing
hints; production build passes. All participation build assertions pass before
the unchanged unrelated UK topic-card mismatch (**23** actual versus **16**
expected); do not change unrelated UK content/assertions. Pages verifies all
**94** byte-identical relocated downloads and prepares **986,280,448 bytes**.
Actual source-matched desktop/mobile by JavaScript/no-JavaScript checks pass
**88 complete links** and **18 entire CSV endpoints**, including all five new
Arizona tables. No overflow; 2026 remains default.
Proof: `files/arizona-native-counts-ui-local-browser-proof-01.json`.

Hans UI commit **`18ec855708bbcf32f53ec4c3c2867cacdddd4b28`** is pushed.
Its exact deployment **42029690146** succeeds. Unqueried metadata/renderer bytes
match the exact source. Desktop/mobile by JavaScript/no-JavaScript production
checks pass **88 complete links** and **18 entire CSV endpoints**, preserving all
82 earlier links; the complete remote native ZIP matches all **76** members.
Proof: `files/arizona-native-counts-ui-publication-proof-01.json`.
No need to rerun this completed count-download matrix.

Complete Maricopa 2026 reference acquired in
`files/precinct-expansion-sources/AZ-MARICOPA-2026-geometry-01/`:
**956** features in four complete object-ID-bounded pages, with matching
before/after ID sets and unchanged layer edit version. All **14** original
responses and receipts are retained, including the actual denied approved-map
PDF response (HTTP403; not a successful PDF acquisition).
The public item `d54dad69d3954287849087b949fb561f`, owned by
`MaricopaElectionsGIS`, explicitly declares **956** precincts approved
**October 1, 2025**, effective **January 2, 2026**, for primary/general federal
results. The acquired official reprecincting page also says October 1, 2025;
earlier search-derived November 20 wording was incorrect and must not be used.
The item warns that numbers were reused rather than renumbered alphabetically.

All **956** native Maricopa House records match unique literal reference
`BdVal + " " + BdName` labels, with independently agreeing numeric `PctNum`.
No fuzzy matching, name trimming, case folding, zero-padding or UUID substitution
is used. Raw media IDs do not literally equal four-character `BdVal` strings;
keep both namespaces and this explicit correspondence.
All polygons are valid. Native-coordinate intersections projected to EPSG:5070
find **four** material overlap pairs affecting **seven** precincts, exceeding
both 1 square meter and 0.0000001 of the smaller precinct; another 37 positive
intersections are below that existing audit threshold. The seven affected
precincts must be withheld whole, not clipped or repaired. Initial independent
diagnostics are preserved in the acquisition cache; these alone are not map
approval or a published crosswalk.

The reproducible fail-closed builder and **21** new focused cases pass;
Arizona plus coverage now passes **49** tests. The final complete supplement is
`data/precinct-results/20261105-arizona-maricopa-02/`, retaining all **76**
byte-identical native count-package members, all **14** reference responses,
full statewide **1,762-row** CSV, explicit **956-row** correspondence, every
overlap/withheld unit, original metadata/license and portable builder.
All **949** mapped shapes are byte-semantically unchanged from their reference
coordinates. **936** have positive candidate counts; **13** explicit zero-vote
units retain null margins and remain uncolored. Positive counts are preserved
even where the native reporting-status label says "Not Reported".
No API participation UUIDs, denominators or rates are joined to map features.
Independent verification checks every feature/count/identity, all **96**
checksums and **97** ZIP members; archive-only rebuilding reproduces all files
and ZIP byte-for-byte. Proof:
`files/arizona-maricopa-2026-maps-package-proof-01.json`.
Complete ZIP: **18,768,461 bytes**, SHA-256
`f50a20f1daa0a1f418dacff60b1657694b7f544da6e771cf2dcde846f25f0c01`.

Hans source commit **`2f4deb6cbb4ea04cb74098f11d5208b08a675565`** is pushed.
Immutable release **`voter-precinct-arizona-maricopa-maps-20261105-02`** pins this
exact commit. The whole anonymous remote archive is byte-identical with all
**97** members; **96** checksums, **66** native original receipts and **14**
reference original receipts retained. Proof:
`files/arizona-maricopa-2026-maps-remote-release-proof-02.json`.
The pinned partial snapshot was initially registered as `snapshot_ready`, not
live-verified, with no mapped participation rates.

Only AZ2026 changes in the **1,632-cell** worklist; all cells remain incomplete.
Astro check has zero errors/warnings and five existing hints; production build
passes. Serial validation reaches only the known unrelated UK topic-card
mismatch (**23** actual versus **16** expected, line1096); participation
assertions pass. Pages then verifies **94** byte-identical relocated downloads
and prepares **986,282,394 bytes**; never run relocation concurrently with
validation.
Actual source-matched local desktop/mobile by JavaScript/no-JavaScript tests
pass **90 complete links**, preserving all **88** older links. Entire new
**1,762-row** CSV and **97-member** ZIP are redownloaded and byte-verified.
All **936** actual precinct fills/counts/margins, all **15** county background
fills, explicit county view, Pennsylvania state fallback, selected-precinct fit,
buttons, desktop wheel/post-fit double-click, real mobile two-pointer pinch and
2024/2026 switching pass. No overflow; 2026/precinct/margin defaults retained.
The map renderer itself is unchanged. Proof:
`files/arizona-maricopa-map-ui-local-browser-proof-02.json`.

Hans UI commit **`20c6c948ab8d90b1cc7153556f156809ac1f6af4`** is pushed.
Its exact deployment **42031647109** succeeds. Unqueried public metadata and
renderer bytes match the source, and the actual production four-mode matrix
passes all **936** precinct fills/counts/margins, all **15** county background
colors, county/state fallback, fit/buttons/wheel/post-fit double-click/real
mobile pinch, year switching and all **90** complete links retaining **88**.
The whole **1,762-row** CSV and **97-member** ZIP are byte-verified again through
their registered links. Proof:
`files/arizona-maricopa-map-ui-publication-proof-02.json`.
The partial snapshot's live flag may now be published. Do not rerun this passed
matrix as a substitute for subsequent acquisition.

### Pima County 2026: complete native CSV/participation and reference acquisition

The actual official county election page, `https://www.pima.gov/elections`,
declares the November 3, 2026 general-election complete CSV:
`https://content.civicplus.com/api/assets/az-pimacounty/07a8ea65-53fd-47a0-84cb-8784c21e2a18`.
Despite its "Summary Results" label, it contains **799** rows and **379** columns:
three header rows, **three unnamed component records for each of 265 precincts**,
and a county-total row. Preserve all original columns, including local contests,
overvotes, undervotes and source padding. Do not infer labels for unnamed
precinct components or triple-count their repeated registrations.
The companion official **21-page** Upload 5 PDF independently states **343,064**
ballots, **657,885** registrations and **100** blank ballots. Its county-mode
labels do not by themselves establish labels for each unnamed precinct row.
Three separate complete ballot-processing PDFs are also acquired, not spliced
into candidate votes or mislabeled as precinct turnout.

The county's actual `https://pima.vote/` hub redirects to
`https://www.pima.gov/pima-votes` and declares general dashboard election **7**:
`https://www.livevoterturnout.com/ENR/pimaazenr/7/en/Index_7.html`.
The dashboard explicitly says **November 3, 2026 General Election** and supplies
all **265** aggregate `precinctData` observations. Every literal precinct name
and four-character CSV/dashboard precinct code matches; every ballot and
registration count agrees. All **374** ballot/option columns sum to their county
total, registrations counted once per precinct. All **265** complete House
vectors independently match the existing native statewide media package by
unique literal county/precinct names; retain both the four-character county code
and opaque media ID. **339,732 House votes are not 343,064 ballots.**
Preserve the one `"Not Reported"` record and its actual counts. Native printed
percentages remain separate; no analysis rates or demographic estimates approved.

The dashboard itself declares `$.getJSON('../pimaazenr_7.txt')` and literal map
property `PRECINCT` matched against its `precinctData` object keys. The exact
resolved URL,
`https://www.livevoterturnout.com/ENR/pimaazenr/7/pimaazenr_7.txt`,
returns **HTTP404**, not acquired geometry. The actual failed body and receipt
are retained. The source document has no HTML base URL that would change this
resolution. Do not invent alternate filenames or substitute an older reference.

Complete independent GIS sources are also acquired by following actual
declarations, not guessed routes. The county library
`https://gis.pima.gov/data/contents/metadet.cfm?name=distvote`
declares its portal dataset; the portal identifies item
`29141abf69534ecc8f196516283e1e79` and actual service
`https://gisdata.pima.gov/arcgis1/rest/services/GISOpenData/Boundaries/MapServer/8`.
All **265** features, all native attributes, three bounded feature pages and
stable before/after inventories/layer metadata are preserved. Actual field
metadata declares integer **`PRECINCT`**, not the earlier search-derived
`DISTRICT` string. The library records changes approved **September 19, 2023**,
implemented January 2024. Current reference is not independently certified
November 3, 2026 geometry.
The actual official precinct locator is
`https://experience.arcgis.com/experience/21445fb10f884caea0aac1ecba764599/`.
Its declared Voting Precincts web map
`293fac439fd04a0695b46807118d6665` instead uses item
`ba56147f7d54454eab8775c145746676`, **Election Polygons App View**:
`https://services2.arcgis.com/UTBp78iglGpbqp1B/arcgis/rest/services/election_polys_20241004_view/FeatureServer/0`.
All **972** union polygons and attributes, five bounded pages, stable inventories
and unchanged edit versions are preserved. The view's source-data edit date
remains in 2024 despite newer schema metadata. Neither these union polygons nor
the 265 base precincts are approved replacements for the missing election map.
Diagnostic numeric precinct-label sets and congressional districts agree for
all 265 base precincts; this is not a literal GIS/media-code join or map approval.
All 265 base polygons are valid; no repairs or vote allocation performed.
Recorder district-map access returns actual HTTP403, preserved rather than
bypassed. The voter hub's Requests TLS failure was resolved using ordinary
certificate-verified curl; no certificate verification was disabled.

Capture cache:
`files/precinct-expansion-sources/AZ-PIMA-2026-reference-01/`.
All **46** actual responses remain there. The complete portable package retains
all **41 factual originals**, all original GIS metadata/licenses, both full
geometry datasets, exact raw county CSV, every normalized result/participation
row, literal name/code correspondence, missing-map response, extracted complete
dashboard aggregate JSON and provenance, and **76 unchanged members** of the
statewide native count package. The five successful frontend discovery documents
remain in the capture cache, not redistributed with incidental frontend tokens.
No metadata-only download or mapped-only subset.

The fail-closed reviewer has **18 new focused tests**; Arizona/coverage passes
**67 tests**. Independent proof verifies every record/source, **125 checksums**
and **126 archive members**, including every source-column sum and exact payload
slice against the retained dashboard original. Archive-only rebuilding reproduces
every file and ZIP byte-for-byte. Proof:
`files/arizona-pima-2026-package-proof-01.json`.
Complete ZIP: **20,538,473 bytes**, SHA-256
`e04858bd262a48276dfcbee83b14dbc5965978799181005b2319bb24efdff3d8`.

Hans source commit **`d39d1a1b35f571936a90bb08f8757822851811eb`** is pushed.
The new immutable release
`voter-precinct-arizona-pima-native-reference-20261105-01` targets that exact
source commit. Its entire anonymous remote ZIP independently passes all **126**
member comparisons, **125** checksums and the exact SHA/byte count above. Proof:
`files/arizona-pima-2026-remote-release-proof-01.json`.

The separate Pima participation-review registration now passes actual local
desktop/mobile by JavaScript/no-JavaScript checks: **94 complete links** retain
all **90** older URLs; both full **265-row** normalized CSVs, the entire
**799-row/379-column** source CSV and complete **126-member** ZIP are byte-exact.
County-only scope and the missing 2026 geometry are visible without JavaScript;
no inferred rates or new map joins. The existing renderer is unchanged;
2026/precinct/margin defaults, 936-color Arizona loading, selection and zoom
health remain intact. Proof:
`files/arizona-pima-ui-local-browser-proof-01.json`.
Seven scoped coverage/review tests and seven participation JavaScript tests pass;
Astro check has zero errors/warnings and the production build passes. Serial
validation reaches only the previously documented unrelated UK 23-versus-16 card
assertion. Subsequent Pages preparation verifies **94** byte-identical relocated
files and **986,289,171 bytes**. Only AZ2026 `publication` and `notes` change in
the **1,632-cell** ledger; statewide counts and every incomplete flag remain.

**Pima publication is now production-verified.** Hans UI commit
`354e26900b525164c207041c15299a5db3da5ffd` deployed successfully in exact Pages
run **42035355674**. All five unqueried public metadata/renderer files match
the committed bytes. Actual desktop/mobile by JavaScript/no-JavaScript checks
retain **94 complete downloads**, including every older **90** link. Both
265-record tables, the entire 799-row/379-column original and 126-member/
125-checksum ZIP pass complete remote checks. County scope, missing geometry,
2026 defaults, map health and no overflow pass; zero inferred rates or new
map approvals. Proofs:
`files/arizona-pima-ui-publication-proof-01.json` and
`files/arizona-pima-ui-live-browser-proof-01.json`. Do not repeat this finished
verification. The Maricopa live flag records its already completed exact
20c6/42031647109 proof, not another unverified map.

### Michigan 2026: native county sources and UI live-verified

The official state elections/results pages return actual **403** responses;
the indexed Muskegon route returns **404**. Their original bodies and receipts
are retained, without bypasses. Bay's official election-results index declares
the November 3, 2026 general-election summary and precinct PDFs. Resolve its
relative links against the actual HTML `base`, not the index path.
Complete originals: **11 pages / 68,279 bytes** summary and **222 pages /
818,675 bytes** precinct report. All **35** native statistics sections reconcile
to **87,721 registrations**, **50,246 ballots**, **28,269 Election Day**,
**17,349 Absentee Counting Board**, and **4,628 Early Voting**. All **35**
U.S. Representative 8th District sections reconcile all six candidate/write-in
vectors across all four columns to the independent summary: **49,556 votes**.
The native reporting counter **43 of 43** remains a separate observation,
not an invented count of geometric precincts or an explained discrepancy.
The new coordinate-based Bay reviewer passes the entire 233 pages and six
focused numeric-alignment/identity/reconciliation regressions. Its source-row
IDs are explicitly extraction identities, not invented native precinct codes.

Isabella's official general-election index explicitly declares the
`2026NovemberGeneral` Enhanced Voting dashboard. Ordinary browser traffic
provides the complete **329,254-byte** public election JSON: **28** UUID-keyed
participation rows, **26,288 ballots**, **44,217 registrations**. Four literal
neighboring-county names are explicitly **0 ballots / 0 registrations**; preserve
them and their identities rather than treating them as positive Isabella units.
The exact U.S. House contest is **Representative in Congress 2nd District**,
with **25,762 candidate/write-in votes** across **24** native units, separate
from ballots. The map is explicitly disabled and observed feature IDs are null.
The native `voterTurnout` field is a count, not a percentage; empty root
registration/statistics arrays are not zeros.

All four exact report anchors have now been acquired completely: party-detail
PDF **84,205 bytes**, contest-detail PDF **105,589 bytes**, summary PDF
**86,773 bytes**, and all-results XLSX **718,003 bytes**. The workbook contains
all four native sheets (summary, summary-by-group, precinct, precinct-by-group),
with observed worksheet dimensions **450 / 1,348 / 5,514 / 16,540 rows** and
78 columns including native blank formatting columns. No metadata-only exports.
Session originals, exact URLs/hashes and network receipts:
`files/precinct-expansion-sources/MI-2026-official-01/`.
The actual House control now supplies a complete **437,610-byte** public
breakdown response. All root fields match the captured general-data snapshot
exactly, apart from the populated breakdown. Native snapshot is
`013d1afb-8d84-4971-a037-34f9f6a8ffd0`, as of
`2026-11-04T20:27:07.3018019Z`. All **24** UUID/name-qualified House unit
vectors and voting modes agree with the workbook and summary.

The four complete workbook tables contain **449 / 1,347 / 5,513 / 16,539**
data rows; every summary/group/precinct aggregation reconciles for all contests,
not only House. All four CSV exports have been independently compared
cell-for-cell with the original workbook. Native House ballots **26,266**
remain separate from election participation **26,288**: **City of Clare,
Precinct 1** has **22** API election ballots but **0** native House-scope
ballots/candidate votes. Preserve this exact discrepancy, not an inferred cause.
The four neighboring-county zero rows absent from House remain in a separate
complete unmatched table; do not fabricate their House votes.

Standalone reviewer:
`scripts/review-michigan-2026-native-results.py`. The complete generated source
package is
`data/precinct-source-reviews/20261105/MI-2026-native-county-counts-01/`:
**63 participation rows**, **59 House vectors**, **4 unmatched rows**,
all four complete workbook tables, original workbook, **9 factual originals**,
source/network receipts, audit, portable reviewer and checksums. Six discovery
frontend/error originals remain separately preserved in the acquisition cache;
no vendor UI assets are redistributed. No separate open-data license was found
in the acquired declarations. No Michigan geometry, demographic rates or
analysis turnout rates are approved.

The **23-member / 22-checksum**, **4,952,650-byte** complete ZIP has SHA-256
`504aafb5bbba26a0982504388faa76469b70975e9c7783eb55d79492367dcd09`.
Archive-only offline rebuild is byte-identical; every committed package member,
checksum and full workbook export passes independent verification.
Proof: `files/michigan-2026-package-proof-01.json`.
**84** scoped Michigan/Arizona/coverage tests pass, including **20** focused
Michigan tests for PDF alignment, missing-vs-zero, duplicated identities,
voting modes, workbook columns, conflicting snapshots and complete reconciliation.

Source commit **93b8152e27a68c837ab03197b4fa401f10bc33b0** is pushed.
Immutable release **voter-precinct-michigan-native-counts-20261105-01**
contains `complete-michigan-2026-native-county-counts-01.zip`. Its entire
anonymous download is byte-identical to the reviewed archive, including all
**23 members / 22 checksums**. Proof:
`files/michigan-2026-remote-release-proof-01.json`.

The separate `MI-2026-native-counts-review.json` sidecar and participation-review
registration now expose all eight complete tables/original workbook plus ZIP,
full county-only caveats and scoped MI2026 ledger status. Only **MI2026**
changes among the **1,632** still-incomplete cells. The overlapping metadata
registrations share one complete ZIP link, not duplicate download anchors.
The map renderer and every older result snapshot remain unchanged.

Local desktop/mobile with and without JavaScript pass: **103 distinct complete
download links**, all **94 older URLs** retained, every new full CSV/workbook
endpoint and the entire ZIP verified, all caveats visible, latest-year /
precinct / red-blue defaults and existing zoom healthy, no overflow.
Proof: `files/michigan-ui-local-browser-proof-01.json`.
Two focused ledger tests, seven routing/renderer tests, Astro check and build
pass; build includes four existing caucus regressions. The serial full-site
validator passes the Michigan download assertions and reaches only the known
unrelated UK topic-card baseline (**23 versus 16**, now line 1097).
Pages preparation verifies **94** existing relocated bulk files and produces
a **986,299,926-byte** artifact.

UI commit **061fa034ed4607c2d3fc7d5f15fb7c8bf98528d2** is pushed as Hans,
without attribution trailers. Exact Pages run **42038698098** succeeded.
All five unqueried production metadata/renderer files match the committed bytes.
Desktop/mobile with and without JavaScript pass **103** complete downloads,
preserving all **94** older links; all eight entire Michigan tables/original
workbook and the full **23-member / 22-checksum** ZIP pass. Source-matched scope,
no overflow, unchanged default 2026/precinct/red-blue fallback and zoom pass.
Proofs: `files/michigan-ui-publication-proof-01.json` and
`files/michigan-ui-live-browser-proof-01.json`. Do not repeat this finished suite
or modify the immutable package. Continue remaining 2026 jurisdictions; retain
Pima's declared-map 404 as a bounded follow-up.

### Kentucky 2026: complete Daviess county source released; UI locally verified

The official 2026 index and statewide live-results/CountyMap routes return actual
**403** responses. The advertised Data route returns **404**. Ordinary Chromium
navigation also returns **403**, explicitly identifying a firewall bot/scraping
policy. All seven original responses and receipts remain in
`files/precinct-expansion-sources/KY-2026-official-01/`.
Do not bypass or keep retrying this portal; use independent county declarations.

Daviess's official `https://www.daviessky.org/election-results/` returns **200**
and declares the actual November general-election PDF:
`https://www.daviessky.org/wp-content/uploads/2026/11/Cumulative.pdf`.
The complete original has **13 pages / 258,815 bytes**, SHA-256
`a93197d2b4b3e92191d5612da2cce67f4c43a40ffb84ab7728576db1a4169433`.
Every page explicitly identifies the November 3, 2026 general election, Daviess
County, unofficial results, and native run **8:15 PM / November 3, 2026**.

All **36** native contest tables reconcile every option and printed Cast Votes
across the five literal columns: absentee mail-in, absentee walk-in, early voting,
Election Day voting, and total. The complete normalized table preserves **181**
rows / **905** numeric cells, independently compared with the original's text
sequence on every page. The county-surveyor table's unnamed explicit-zero row is
retained with an empty native name and separate extraction identity, not an
invented candidate. Printed multi-seat vote-opportunity totals are not ballots.

The repeated county header supplies **31,918 ballots**, counted once, and
**17 of 17 polling places**. This reporting counter is not a geographic precinct
inventory. Native House 2nd District options sum to **31,521 candidate votes**
(Republican **17,980**, Democratic **12,849**, independent **692**);
**386 undervotes + 11 overvotes** reconcile to county ballots. Registrations and
turnout rates remain missing. This is **one county only**, not statewide coverage,
and no new geometry, demographic estimate or map is approved.

Standalone reviewer: `scripts/review-kentucky-2026-native-results.py`.
Generated complete package:
`data/precinct-source-reviews/20261105/KY-2026-native-county-counts-01/`.
It contains all three complete CSVs, the entire original PDF, seven-source
receipt manifest, audit, portable reviewer and checksums. Six discovery/error
originals remain in the acquisition cache; no vendor frontend assets redistributed.
No separate open-data license was found in the acquired declarations.
The **8-member / 7-checksum**, **306,401-byte** full ZIP has SHA-256
`43ded14f7e7978d471f5554556ad024cb5353a7e9dcdca9a557f64d9eba45974`.
Executing only the extracted portable reviewer/originals reproduces the archive
byte-for-byte. All **11** focused parser/reconciliation/missingness/archive
regressions pass. Independent proof: `files/kentucky-2026-package-proof-01.json`.

Source commit **c3d3fb539eb392091b48e0c327d2be574d46f1f1** is pushed as Hans,
without attribution trailers. Immutable release
**voter-precinct-kentucky-native-counts-20261105-01** contains
`complete-kentucky-2026-native-county-counts-01.zip`. Its entire anonymous download
matches the reviewed ZIP, including all **8 members / 7 checksums**.
Proof: `files/kentucky-2026-remote-release-proof-01.json`.

The separate `KY-2026-native-counts-review.json` sidecar and fourth top-level
participation review expose all three full CSVs, entire original PDF and full
ZIP with one-county-only caveats. Only **KY2026** changes among **1,632**
still-incomplete worklist cells. Every older snapshot, renderer and link remains
unchanged. All **13** scoped collector/participation-ledger tests and **7**
renderer/routing tests pass; Astro check and production build pass, including
four existing caucus regressions. The serial full-site validator passes Kentucky
and reaches only the unrelated UK **23-versus-16** baseline at line 1097.
Pages preparation verifies **94** existing relocated files; artifact size
**986,307,426 bytes**.

Local desktop/mobile with and without JavaScript pass **108 distinct complete
download links**, preserving all **103** older URLs and verifying every complete
new CSV/PDF endpoint and full ZIP. County-only scope, missing rates/registrations,
no overflow, default 2026/precinct/red-blue map behavior and selection/zoom pass.
Proof: `files/kentucky-ui-local-browser-proof-01.json`.

UI commit **c2efd41608321f4d9cfb9102a96b529148c1cbe9** is pushed as Hans.
Its exact deployment **42040522420** succeeded. All five unqueried public files
match committed bytes, and desktop/mobile with and without JavaScript pass
**108** complete download links, preserving all **103** older URLs and verifying
every entire new CSV/PDF/ZIP. Default 2026/precinct/red-blue behavior, selection,
zoom and no overflow pass. Proofs: `files/kentucky-ui-publication-proof-01.json`
and `files/kentucky-ui-live-browser-proof-01.json`. Kentucky is live-verified;
do not repeat its finished suite. Do not retry its statewide bot-policy block.

### Iowa 2026: complete county originals acquired and native counts reviewed

All **13** actual source receipts are preserved in
`files/precinct-expansion-sources/IA-2026-official-01/`. State results/live
indexes, four declared general absentee PDFs, historical turnout PDF, and Linn
and Lee indexes return **403**. Preserve these bodies as errors, not PDFs; do
not bypass their challenges or guess unlinked statewide result filenames.

Independent official county declarations succeed. Linn's complete summary is
**36,494 bytes / 10 pages**, SHA-256
`a2d194adfef5761933857f2b57e719297d793b41d54dfd53e2f68015b800572d`;
its complete precinct report is **1,757,695 bytes / 511 pages**, SHA-256
`f9c01726731a42b144006c635fc5e99a105fb7c6521c6d8626f7579dc8ca5504`.
Both explicitly identify the November 3, 2026 general election and unofficial
results, with native report times **10:12–10:13 PM**. URLs:
`https://gis.linncountyiowa.gov/web-data/elections/year/2026/20261103GE/sum.pdf`
and `https://gis.linncountyiowa.gov/web-data/elections/year/2026/20261103GE/pct.pdf`.
All **94** actual precinct statistics/House tables independently reconcile to
**160,717 registrations**, **107,457 ballots** (**66,530 Election Day /
40,927 absentee**), **20 blank ballots** (**5 / 15**) and **105,838 House
votes** (**65,501 / 40,337**). All five candidate/write-in vectors reconcile
in every mode. Printed turnout uses native total registrations, not VEP or a
demographic denominator; no substitute denominator or geometry is approved.

Marion's official 2026 index declares the complete **481,505-byte / 9-page**
scanned report, SHA-256
`4627272fdf72d35b2c0d1a20b715efce5242d042ae5e00242cd7242f8d0ae002`.
The original URL is
`https://www.marioncountyiowa.gov/files/election_results/2026_general_election_2026_11_03_29798_.pdf`;
its ordinary redirect succeeds. Direct inspection of all nine native page
headers confirms the November 3 general election, unofficial status and
**9:34:08 PM CST**, with **25,041 registrations**, **16,373 ballots**,
**1 blank ballot** and printed **65.38%**. The first-page House contest has
**15,923 votes + 445 undervotes + 5 overvotes = 16,373 ballots**.
The PDF says **19 of 19 reporting**, while the index says **19/17**; preserve
the discrepancy and infer no geographic precinct inventory. Native header
contact sheet and full first-page evidence are retained under the cache's
`review/`. No OCR guesses or ballot-mode allocations have been made.

**Pending:** persist a portable, fail-closed reviewer and complete original/count
package, tests, archive-only rebuild, immutable release and UI registration.
These county checks are not a published map or statewide completion.

### Consolidated-source-first investigation requested November 5, 2026

The user requested correction of obsolete NC-focused page subtitles and a
search for already collated data instead of defaulting to county-by-county
reconstruction. The page metadata, introductory deck, coverage fallback and
Interactive analysis card now describe nationwide, presidential/midterm scope
without promising universal precinct coverage. Legitimate NC-only historical
participation labels and all map defaults/behavior are retained.

Useful current primary-provider declarations:

- UF Election Lab lists **2026 General Election Turnout Rates v0.2**, updated
  **November 4, 2026**, with a declared complete CSV and documentation:
  `https://election.lab.ufl.edu/dataset/2026-general-election-turnout-rates-v0-2/`.
  This is state-level participation, not precinct geometry or demographic
  turnout. Check actual ballot availability and preserve separate VAP/VEP
  definitions. The dataset documentation specifies CC BY 4.0, whereas the
  generic archive page lists a different default license; retain both declarations.
- `https://github.com/pushbuild/us-2026-election-results` has **40 state CSVs**
  plus README/license at immutable commit
  **feb85f414762b05c7c77f6450336405ef030fbfa**, committed November 4.
  The provider identifies an **unofficial November 4, 12:11 PM ET** snapshot,
  state/county candidate results and CC0. Some files contain candidate-list
  placeholders and no actual counts; some "county" units are potentially towns
  or districts. Acquire the entire pinned original and verify every Git blob,
  then reconcile scope/counts before promoting anything. Never treat blank
  votes as zeros, county labels as precincts, or candidate totals as turnout.
- `https://openamerica.io/elections/api/` documents a free, public **22-state**
  2026 results feed and a 2024 replay. These are race-level results and counts
  of reporting units, not geographic precinct returns, registration or ballots.
  It can cross-check complete race vectors but cannot supply precinct maps.
- Historical bulk alternatives remain **MIT Election Lab**, **OpenElections**,
  **Redistricting Data Hub**, and **UF/VEST**. MIT lists multi-state precinct
  returns including 2024 and earlier midterms. RDH lists all-state joined
  results/boundaries for 2016, 2018 and 2020 and separate later-year availability.
  Check each package's actual year, ballot-mode coverage, license and allocation
  methods: RDH explicitly describes some partners allocating centrally reported
  votes, which is not an observed geographic count. UF's 2022/2024 precinct
  maps/results require a paid subscription; do not bypass access restrictions.

Actual full downloads succeed, not merely catalog discovery:

- The pinned Pushbuild complete original archive is **2,404,302 bytes**, containing
  **42 files / 40 state CSVs / 129,414 rows**, including **104,033 native
  county-labelled rows**. Every original Git blob and byte length verifies.
  Illinois, Massachusetts, New York and Wyoming files contain only missing-vote
  candidate lists. Other files mix real counts and placeholders. Alaska's
  county-labelled rows include House districts; Connecticut uses towns.
  Preserve every original row, but promote none before scope reconciliation.
- UF's **6,019-byte CSV / 52 rows** covers all states, D.C. and the U.S.;
  **every SOURCE says `Initial Estimate`**. This is an explicitly estimated
  participation series, not 52 administrative ballot-count observations or
  demographic turnout. Keep it separate from Census CPS, official counts and
  registrations. The complete **6,942-byte** documentation is retained.
- Open America's actual **67,710-byte** 2026 House response contains **155 races
  across 15 states**, fewer than its 22 supported adapters. All nine Indiana
  races have candidate-sum versus reported-total conflicts, often exactly
  double; retain but withhold these vectors rather than accepting the API
  contract as validation.
- RDH's actual declared `dataset.csv` (**1,878 bytes / 50 rows**) has **no
  2026 general-election download links**. Louisiana alone is labelled
  `Primary Available`; this does not supply November general-election data.
  The map is a useful future availability check, not an acquired 2026 map set.

All entire original responses, source receipts, pinned inventory and row-level
acquisition audit remain in
`files/consolidated-election-sources-20261105-01/`. The source acquisition helper
is `files/acquire-consolidated-election-sources-01.py`. No new map, turnout
denominator or completed state/year cell is claimed from these downloads.
The complete CC0 Pushbuild archive (including all CSVs, README and license),
its pinned tree/acquisition audit, UF's entire CSV and CC BY documentation,
and RDH's entire availability CSV are also persisted in the repository at
`data/precinct-source-reviews/20261105-consolidated-01/`, with HTTP receipts and
SHA-256/byte-length inventory. Archive-only verification rechecks every one
of the **42** Git blobs and the exact **129,414 / 104,033** row counts.

The nationwide page deck, social description, default selection heading,
no-JavaScript scope note and Interactive analysis subtitle have been updated.
Astro check, seven participation regressions and the production build pass.
The serial validator passes the participation assertions and reaches only
the established unrelated UK card mismatch (**23 versus 16**, line 1097).
The Pages preparer passes and preserves complete download relocation.
Nationwide copy is **live verified** at Hans commit
**467a5fcb184d03b89ad813f3ec34aef42d476f26**, successful exact deployment
**42042763069**. Both unqueried public pages contain the new wording; all five
public metadata/renderer files still match. Desktop/mobile with and without
JavaScript pass the new deck, social descriptions, analysis preview,
**108 complete downloads**, no overflow and unchanged 2026/precinct/red-blue
defaults. Proofs: `files/nationwide-subtitles-publication-proof-01.json` and
`files/nationwide-subtitles-live-browser-proof-01.json`. Do not repeat this
finished live suite.

### Iowa 2026: statewide bulk county count review, not map approval

The consolidated source is now concretely processed rather than another
inventory. `scripts/review-iowa-2026-consolidated-results.py` replays the
pinned complete original archive, verifies its SHA-256 and Iowa Git blob,
and preserves **all 6,010 original Iowa rows**. Its **376 House candidate
rows** include **99 county contests and four statewide district contests**.
Every candidate/write-in county vector sums exactly to its statewide
district vector: **1,341,241 candidate votes**, not ballots or turnout.
All nine Linn/Marion candidate/write-in entries match the independently
reviewed native reports; the exact three complete official PDFs, native
visual evidence, original receipts and error bodies are included. Unknown
parties stay blank and all candidates/write-ins remain in margin denominators.

The independently declared
`https://results.enr.clarityelections.com/IA/127077/` returns **403**.
Its full body and receipt are preserved in `source-bulk/`; do not bypass,
guess result filenames or label provider arithmetic as primary verification
of all 99 counties. Native reporting counters remain untouched: their unit
semantics and reporting completion are not inferred from positive county
counts. No geometry, precinct map, turnout denominator, completed state/year
or new public layer is approved.

Complete immutable review:
`data/precinct-source-reviews/20261105-iowa-consolidated-01/`.
Its **5,149,438-byte** `complete-iowa-county-review.zip` contains **27
members**, including the full 40-state original archive and CC0 license,
all native Iowa originals, every derived table, **26** checksums and the
portable reviewer. ZIP SHA-256:
`c43cfd5ce7f0b37c9b6166feb962b17b59fe4f934b91ee1d6e7dc1802a88252b`.
Archive-only offline rebuild reproduces **every file, including the ZIP,
byte-for-byte**. Proof: `files/iowa-consolidated-archive-replay-proof-01.json`.
Five focused regressions pass for missing versus explicit zero, all-option
denominators, duplicate candidates, conflicting native totals and mismatched
county/state vectors.

To reproduce from the extracted complete ZIP, choose a new output directory:

```bash
python review-iowa-2026-consolidated-results.py \
  --bulk-originals source-bulk --native-originals source-native \
  --output /path/to/new-iowa-review
```

**Current executable priority:** use already acquired consolidated originals
for remaining 2026 state/county gap reviews, not new county-by-county rebuilding.
Iowa county-vector reconciliation and native Linn/Marion cross-checks are
finished. Next, complete its separately pending native **94-precinct** portable
review/participation package and independently establish county geometry/source
scope before map integration; do not treat this count review as that approval.
The all-40-state arithmetic screen is
`files/consolidated-election-sources-20261105-01/pushbuild-intake-arithmetic.json`:
261 native group differences in CT/LA/MD/NJ need source/selection-rule
interpretation, not automatic repair; missing-count placeholders remain missing.
Do not repeat the already acquired 25-state 2022 batch, successful nationwide
copy live suite or completed Kentucky production suite. Keep the acquisition
schedule active and all 1,632 state/year completion flags honest.

### Linn County, Iowa 2026: all 94 native precinct participation/House tables

The pending Linn native review is now reproducible:
`scripts/review-iowa-linn-2026-native-results.py` verifies both complete
original PDF hashes, every election/status header and all 521 sequential
pages. All **94 distinct contiguous native precincts** reconcile to the
independently printed county summary in every reported voting mode:
**160,717 registrations; 107,457 ballots (66,530 Election Day, 40,927
Absentee); 20 blank ballots; and separately 105,838 House candidate votes
(65,501 Election Day, 40,337 Absentee)**. Every candidate and write-in vector
also reconciles. Dave Bushaw's unprinted party stays missing, explicit zeros
remain zero, and missing mode-specific registrations remain missing.

The package has all 94 participation observations, 282 precinct House-mode
rows, separate county participation/House tables, all 1,425 county/precinct
candidate-mode rows, both entire all-contest originals, receipts, portable
code, audit and checksums. County rows must not be added to precinct rows;
native Total is the sum of Election Day and Absentee, not an additional mode.
Each reported registered-voter rate uses only that same unit's own native
registrations and is checked against its printed rate. It is not VEP, CPS,
demographic or mode-specific turnout. House margins instead use all candidate
and write-in votes; printed House percentages are retained separately.

Snapshot: `data/precinct-source-reviews/20261105/IA-LINN-2026-native-counts-01/`.
The complete **2,061,367-byte** ZIP has **11 members**, including **10**
checksums; SHA-256
`9fdf74ae6d8f48c5d89188e340d10e857fea56fc6ab49bd155320d91c0104362`.
Archive-only offline rebuild reproduces every file and ZIP byte-for-byte.
Proof: `files/iowa-linn-native-archive-replay-proof-01.json`.
Ten focused regressions cover missing versus explicit zero, separate percentage
columns, malformed/duplicate/unreviewed positions and inconsistent native
precinct/mode inventories. From the extracted ZIP, with PyMuPDF installed:

```bash
python review.py --source source --output /path/to/new-linn-review \
  --archive /path/to/new-linn-review.zip
```

This is **Linn County only**, unofficial November 3, 2026 results, not
statewide or demographic participation. No precinct geometry or new map is
approved and no state/year is complete. The immutable full ZIP is published
at release `voter-precinct-iowa-linn-native-counts-20261105-01`, pinned to
source commit `28e6592ebd1fbf449bd78cdb1b28dc83101ea746`; downloading that
release verifies every byte and all ten member checksums. The source and
participation registries now expose all five full CSVs and both entire PDFs.
Only Iowa 2026 changes in the regenerated 1,632-cell worklist; every
completion flag remains `no`. No renderer, map input or default changes.

Seventeen focused Python collector/worklist tests, seven participation Node
tests, production build and Pages preparer pass. Serial site validation
reaches only the established unrelated UK 23-versus-16 card-count assertion
at line 1097. Four source-matched local browser modes (desktop/mobile,
with/without JavaScript) verify **116 complete download links**, every one
of the **108 older links** unchanged, all seven new table/PDF endpoints and
the entire ZIP byte-for-byte, clear county scope, responsive layout and
unchanged latest-election/precinct/red-blue defaults and working zoom.
Proof: `files/iowa-linn-native-local-browser-proof-01.json`.
UI commit `8c2c4c0188300d04f8a5b91a650ec1f31f5cc497` build succeeded
in run `42048268675`, but Pages remained `updating_pages` until its
600,000-ms timeout. A deploy-only retry reused the successful artifact but
immediately returned `Deployment cancelled` for the same Pages build version.
No data/build failure was reported. Meaningful plan/CT findings commit
`62ebd86d5cc65986738a5dafc5316b362d5ed83b` obtained a fresh Pages build
version without changing the validated UI inputs or replacing the release.
Its exact run **42051043255 succeeded**, and Linn is **live verified**:
all five unqueried public files match, all four desktop/mobile and
JavaScript/no-JavaScript browser modes pass, **116 complete links** retain
all **108 older links**, and all seven new table/PDF endpoints and the ZIP
match their full original bytes. Latest-election, precinct, red-blue and
zoom behavior remain unchanged. Proofs:
`files/iowa-linn-native-publication-proof-01.json` and
`files/iowa-linn-native-live-browser-proof-01.json`. No further deployment
recovery is pending. Continue consolidated 2026 reviews, establishing
correct-election geography independently before any new map join.
Do not reacquire or re-review these finished 94 counts.

### Next consolidated review: Connecticut House scope and fusion lines

During Linn deployment, the already-acquired complete Connecticut CSV was
verified against original Git blob
`10c89b0f4052de9aff61c980b0b1f84379eb8b92` at pinned Pushbuild commit
`feb85f414762b05c7c77f6450336405ef030fbfa`. No new download was needed.
Its **7,400 original rows** include **698 House candidate/party-line rows**,
**169 native local names**, **174 local House groups** and **five district
groups**. Every local option vector and native total reconciles to its
statewide district vector: **1,152,033 candidate votes**, not participation.
The two CT intake conflicts instead group generic statewide `Board of
Education` and `Registrar of Voters` records; they do not invalidate these
five House contests.

Do not apply Iowa's contest/party/county assumptions. Exact federal labels
are `Representative in Congress 1` through `5`; major-party codes are
`D`/`R`. District 2's Republican candidate George Patrick Austin also has
**5,310 `IND` votes**, and District 5's Democratic candidate Jahana Hayes
also has **6,631 `WF` votes**. Candidate identity must aggregate these native
fusion lines for margins while preserving every original party-line row;
`IND`/`WF` must not all be classified as other. The source's `county`
field contains town names, not county geography. Do not infer completion
from the native 703/775 counters or manufacture precinct/ballot counts.

Evidence: `files/connecticut-bulk-house-arithmetic-01.json`.
**Next executable batch:** persist a portable, fail-closed CT-specific bulk
review and complete-original package with focused fusion/scope tests;
independently establish primary report identity and native town geography
before map approval. This arithmetic-only preflight makes no public map,
participation or completion-status change.

### Additional historical county bulk source verified November 5, 2026

The repeated request for consolidated sources led to an additional complete
historical source, **Paul Heideman's U.S. County Election Results**:
`https://github.com/pmheideman/us-county-election-results`.
Release **v1.0.0**, published September 26, 2026, resolves to commit
`155b35015f4b9801c07c05b800c380218c6462b3`. Its complete **9,500,264-byte**
ZIP was actually acquired and verified, not merely catalogued:
SHA-256 `e422fbfb1c56bed6787d08e59eed83d13b4ccf567510c69f94d2802a34b8e625`,
all **11 members**, all **10 publisher member checksums** and every CRC.
The complete download is
`https://github.com/pmheideman/us-county-election-results/releases/download/v1.0.0/us_county_election_results_v1.0.0.zip`.

The actual long table has **420,503 candidate rows**, across **48 states**
and all **18 even years, 1990-2024**, including midterms; presidential
coverage starts in 1992. Alaska, Hawaii and D.C. are excluded. There are
**200,171 House**, **126,220 Senate** and **94,112 presidential** rows;
**812 runoff rows** must remain separate from **419,691 general rows**.
The full ZIP also includes **120,191 county summaries**, **41 gap records**,
**524 no-ballot records**, **1,870 provenance rows**, **135 corrections**,
the data dictionary and Parquet counterpart. Coverage is not universally
complete, and unopposed races not on a ballot are not missing zero-vote races.

An actual count-type screen found one unflagged fractional native count:
**Alabama 2010 House, Montgomery County, District 02, Bobby Bright,
23,334.16236**, source `al_sos_file_2010`. Preserve this literal source row,
withhold it pending original-source review, and do not round or silently
repair it. Retain the publisher's flagged totals, aggregated other candidates
and placeholder identities; reconcile full candidate vectors and fusion
lines before new maps. These are candidate results, **not ballot counts,
eligible-voter turnout, demographic participation or precinct geography**.

The compilation license is CC BY 4.0 but expressly preserves upstream
per-source restrictions. Complete originals and pinned README, license,
citation and release metadata remain in
`files/historical-county-bulk-20261105-01/`; use the publisher's complete
ZIP link rather than an unreviewed public mirror. The durable acquisition
audit is
`data/precinct-source-reviews/20261105-historical-county-bulk-01/acquisition.json`.
No public map, denominator, source registry or state/year completion flag
changes from acquisition alone.

**Bulk-first execution remains mandatory:** finish actionable 2026
consolidated-source reviews first, then use this one complete original for
2024, 2022 and older county-result backfill rather than recollecting each
state. Use independently acquired precinct packages where they exist and
county returns where precinct coverage is unavailable. Individual state or
county collection is a gap-filling fallback, not the default. UF's
state-level turnout estimates and historical participation series remain
separate from these candidate-result sources.

The deployed nationwide subtitle was rechecked directly during this request:
**"Voter turnout across elections, places and demographic groups."**
The Interactive analysis preview also retains nationwide presidential/midterm
scope. The newly successful Linn deployment preserves that already-published
copy; no further subtitle change or duplicate browser suite is necessary.

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
