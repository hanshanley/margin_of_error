# Precinct coverage: state-by-state, election-by-election

Priority: **2026, 2024, 2022, 2020, then every earlier even year through 1964**.
All 50 states and DC appear in every election: **1,632 tracked state/election cells**.
Canonical machine-readable worklist: `public/precinct-coverage.csv`.
Regenerate with `python scripts/build-precinct-coverage.py`.

No state/year is complete until its actual candidate returns, correct-election reference
boundaries, unique joins, count reconciliation, browser checks and live publication
are verified. Partial coverage is not completion. Participation inputs are tracked separately;
candidate votes are never demographic participation or turnout denominators.
An unreviewed archive is not an unavailable archive. Do not borrow another election's
boundaries, silently allocate county early/mail votes, or extrapolate state colors into precinct results.
Full source downloads, state caveats, licenses and unmapped rows must remain available.

Status key: `not_reviewed` = still to investigate; `acquired` = source saved, not yet mapped;
`reference_acquired` = reference geometry, not certified election-day boundaries;
`validated_partial` = audited subset only; `snapshot_ready` = data built, not yet verified live;
`published_partial` = the acquired layer passed live browser checks, not complete statewide coverage.
Checkmarks are reserved for verified, complete live coverage.

## 2026

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | acquired | reference_acquired | validated_partial | passed | snapshot_ready | published_partial_reference_map |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 2024

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | absent_from_reviewed_release | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Arkansas | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Arizona | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | California | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Colorado | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Connecticut | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | District of Columbia | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Delaware | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Florida | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Georgia | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Hawaii | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Iowa | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Idaho | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Illinois | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Indiana | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Kansas | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Kentucky | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Louisiana | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Massachusetts | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Maryland | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Maine | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Michigan | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Minnesota | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Missouri | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Mississippi | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Montana | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | North Carolina | acquired | reference_acquired | validated_partial | passed | snapshot_ready | published_counts_and_reference_map |
| [ ] | North Dakota | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Nebraska | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | New Hampshire | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | New Jersey | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | New Mexico | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Nevada | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | New York | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Ohio | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Oklahoma | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Oregon | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Pennsylvania | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Rhode Island | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | South Carolina | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | South Dakota | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Tennessee | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Texas | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Utah | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Virginia | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Vermont | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Washington | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Wisconsin | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | West Virginia | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |
| [ ] | Wyoming | acquired | reference_acquired | validated_partial | passed | snapshot_ready | not_acquired |

## 2022

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2020

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2018

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2016

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2014

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2012

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2010

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2008

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2006

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 2004

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts |
| [ ] | North Dakota | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2002

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 2000

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | source_identified | not_reviewed | pending | pending | not_published | not_acquired |

## 1998

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1996

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1994

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1992

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1990

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1988

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1986

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1984

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1982

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1980

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1978

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1976

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1974

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1972

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1970

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1968

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1966

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |

## 1964

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Rhode Island | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
