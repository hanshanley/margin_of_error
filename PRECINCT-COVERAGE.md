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
`acquired_originals_review_pending` = complete original file saved, contest/ballot scope unverified;
`full_originals_download_only` = complete source download, not validated maps or inferred turnout;
`reference_acquired` = reference geometry, not certified election-day boundaries;
`validated_partial` = audited subset only; `snapshot_ready` = data built, not yet verified live;
`published_partial` = the acquired layer passed live browser checks, not complete statewide coverage.
`reviewed_city_only_voter_counts` = limited municipal participation, not statewide or demographic coverage;
`reviewed_county_mail_returns_only` = administrative mail returns, not all-mode ballots or final turnout.
Checkmarks are reserved for verified, complete live coverage.

## 2026

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | acquired_reconciled | correct_election_reference_acquired_review_pending | withheld | counts_passed_map_withheld | full_counts_download_only | acquired_reporting_unit_counts_rates_withheld |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | acquired_reconciled_native_precinct_counts | official_portal_reference_acquired_review_pending | withheld_pending_county_qualified_geometry_review | native_json_csv_and_independent_api_counts_passed | full_counts_download_only | native_precinct_ballot_counts_acquired_rates_withheld |
| [ ] | Arizona | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | acquired_originals_review_pending | not_reviewed | pending | complete_source_bytes_and_candidate_registry_section_structure_verified | full_originals_download_only | not_reconciled |
| [ ] | District of Columbia | acquired | reference_acquired | validated_partial | passed | published_partial | acquired_precinct_counts_and_registration |
| [ ] | Delaware | acquired_reconciled | older_reference_withheld | withheld | counts_passed_map_withheld | full_counts_download_only | not_acquired |
| [ ] | Florida | acquired_reconciled | election_year_reference_pending | withheld | all_office_native_candidate_totals_passed_suppressed_modes_retained | full_counts_download_only | county_counts_only_precinct_denominators_not_acquired |
| [ ] | Georgia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | acquired_reconciled | reviewed_official_page_exact_year_reference_pending | withheld | native_candidate_counts_passed_ballot_differences_retained | full_counts_download_only | acquired_reporting_unit_counts_rates_withheld |
| [ ] | Iowa | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | acquired | reference_acquired | validated_partial | passed | published_partial | acquired_precinct_counts_and_provisional_rates |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | acquired | reference_acquired | validated_partial | passed | published_partial | central_tabulation_ballot_counts_only_no_registration_or_rates |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
| [ ] | Michigan | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Minnesota | acquired | reference_acquired | validated_partial | passed | published_partial | acquired_precinct_counts_and_registration |
| [ ] | Missouri | acquired_reconciled | election_year_reference_pending | withheld | house_vectors_and_native_participation_independently_reconciled | full_counts_download_only | native_reporting_unit_counts_centralized_absentee_unallocated |
| [ ] | Mississippi | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | North Dakota | acquired | reference_acquired | validated_partial | passed | published_partial | acquired_precinct_ballot_counts |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | acquired | reference_acquired | validated_partial | passed | published_partial | published_partial_reference_map |
| [ ] | Nevada | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New York | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Pennsylvania | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_county_mail_returns_only |
| [ ] | Rhode Island | acquired | reference_acquired | validated_partial | passed | published_partial | acquired_locality_counts_rates_withheld |
| [ ] | South Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | South Dakota | acquired_reconciled | correct_election_reference_pending | withheld | counts_passed_map_withheld | full_counts_download_only | acquired_precinct_counts_and_provisional_rates |
| [ ] | Tennessee | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Texas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Utah | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Virginia | acquired | reference_acquired | validated_partial | passed | published_partial | native_precinct_counts_and_registration_rates_withheld |
| [ ] | Vermont | acquired | reference_acquired | validated_partial | passed | published_partial | acquired_municipal_counts_and_provisional_rates |
| [ ] | Washington | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Wisconsin | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | West Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wyoming | acquired_candidate_category_conflict | not_reviewed | withheld | ballot_counts_passed_candidate_category_conflict_map_withheld | full_counts_download_only | acquired_precinct_ballot_counts_rates_withheld |

## 2024

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | absent_from_reviewed_release | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Arkansas | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Arizona | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | California | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Colorado | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Connecticut | acquired | reference_acquired | validated_partial | passed | published_partial | not_reconciled |
| [ ] | District of Columbia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Delaware | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Florida | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Georgia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Hawaii | acquired | reference_acquired | validated_partial | passed | published_partial | not_reconciled |
| [ ] | Iowa | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Idaho | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Illinois | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Indiana | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Kansas | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Kentucky | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Louisiana | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Massachusetts | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Maryland | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Maine | acquired | reference_acquired | validated_partial | passed | published_partial | reviewed_city_only_voter_counts |
| [ ] | Michigan | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Minnesota | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Missouri | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Mississippi | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Montana | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | North Carolina | acquired | reference_acquired | validated_partial | passed | published_partial | published_counts_and_reference_map |
| [ ] | North Dakota | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Nebraska | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New Hampshire | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New Jersey | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New Mexico | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Nevada | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New York | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Ohio | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Oklahoma | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Oregon | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Pennsylvania | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Rhode Island | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | South Carolina | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | South Dakota | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Tennessee | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Texas | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Utah | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Virginia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Vermont | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Washington | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Wisconsin | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | West Virginia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Wyoming | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |

## 2022

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | California | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Connecticut | acquired_originals_review_pending | not_reviewed | pending | complete_source_bytes_and_candidate_registry_section_structure_verified | full_originals_download_only | not_reconciled |
| [ ] | District of Columbia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Georgia | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Hawaii | acquired_originals_review_pending | not_reviewed | pending | complete_source_bytes_and_native_record_structure_verified | full_originals_download_only | not_reconciled |
| [ ] | Iowa | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Idaho | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Massachusetts | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
| [ ] | Michigan | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Minnesota | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Missouri | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Mississippi | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Montana | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | North Carolina | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | published_counts_and_reference_map |
| [ ] | North Dakota | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Nebraska | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Hampshire | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Jersey | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | New Mexico | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Nevada | acquired_originals_review_pending | not_reviewed | pending | county_only_source_bytes_election_identity_and_native_structure_verified | full_originals_download_only | not_reconciled |
| [ ] | New York | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Ohio | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oklahoma | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Oregon | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Pennsylvania | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Rhode Island | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | South Carolina | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | South Dakota | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Tennessee | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Texas | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Utah | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Washington | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Wisconsin | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | West Virginia | acquired_originals_review_pending | not_reviewed | pending | source_bytes_verified_scope_pending | full_originals_download_only | not_inferred_from_candidate_votes |
| [ ] | Wyoming | acquired_candidate_counts_reconciled | not_reviewed | withheld | candidate_counts_passed_printed_ballot_total_conflict_map_withheld | full_counts_download_only | acquired_precinct_ballot_counts_printed_total_conflict |

## 2020

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Arizona | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | California | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Colorado | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Connecticut | acquired | reference_acquired | validated_partial | passed | published_partial | not_reconciled |
| [ ] | District of Columbia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Delaware | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Florida | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Georgia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Hawaii | acquired | reference_acquired | validated_partial | passed | published_partial | not_reconciled |
| [ ] | Iowa | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Idaho | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Illinois | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Indiana | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Kansas | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Kentucky | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Maryland | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Maine | acquired | reference_acquired | validated_partial | passed | published_partial | reviewed_city_only_voter_counts |
| [ ] | Michigan | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Minnesota | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Missouri | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Mississippi | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Montana | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | North Carolina | acquired | reference_acquired | validated_partial | passed | published_partial | published_counts_and_reference_map |
| [ ] | North Dakota | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Nebraska | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New Hampshire | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New Jersey | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New Mexico | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Nevada | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | New York | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Ohio | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Oklahoma | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Oregon | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Pennsylvania | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Rhode Island | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | South Carolina | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | South Dakota | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Tennessee | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Texas | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Utah | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Virginia | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Vermont | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Washington | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Wisconsin | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | West Virginia | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |
| [ ] | Wyoming | acquired | reference_acquired | validated_partial | passed | published_partial | not_acquired |

## 2018

| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |
|---|---|---|---|---|---|---|---|
| [ ] | Alaska | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Alabama | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arkansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Arizona | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | California | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Colorado | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Connecticut | acquired_originals_review_pending | not_reviewed | pending | complete_source_bytes_and_candidate_registry_section_structure_verified | full_originals_download_only | not_reconciled |
| [ ] | District of Columbia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Delaware | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Florida | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Georgia | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Hawaii | acquired_originals_review_pending | not_reviewed | pending | complete_source_bytes_and_native_record_structure_verified | full_originals_download_only | not_reconciled |
| [ ] | Iowa | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Idaho | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Illinois | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Indiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kansas | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Kentucky | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Louisiana | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Massachusetts | source_identified | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maryland | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | not_acquired |
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Connecticut | acquired_originals_review_pending | not_reviewed | pending | complete_source_bytes_and_candidate_registry_section_structure_verified | full_originals_download_only | not_reconciled |
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
| [ ] | Maine | source_identified | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
| [ ] | Maine | reviewed_archive_no_match | not_reviewed | pending | pending | not_published | reviewed_city_only_voter_counts |
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
