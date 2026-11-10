#!/usr/bin/env python3
"""Acquire one declared Minnesota participation original and build a public-safe query."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html.parser
import io
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile


HERE = Path(__file__).resolve().parent
SESSION_FILES = HERE.parent
PRIOR_ORIGINALS = SESSION_FILES / "minnesota-participation-originals-01"
PRIOR_REVIEW = (
    SESSION_FILES
    / "2026-evidence-build-01"
    / "data"
    / "county-source-reviews"
    / "20261106-minnesota-facts-01"
)
ORIGINALS = HERE / "originals"
REUSED = HERE / "reused-frozen-originals"
CURRENT = ORIGINALS / "pctstats.txt"
RECEIPT = ORIGINALS / "pctstats.txt.receipt.json"
ARCHIVE = HERE / "complete-minnesota-participation-query.zip"
COUNTY_PAGE = (
    "https://electionresults.sos.mn.gov/Results/"
    "CountyStatisticsStatewide/Index?ersElectionId=201"
)
MEDIA_PAGE = "https://electionresults.sos.mn.gov/Select/MediaFiles/Index?ersElectionId=201"
TURNOUT_PAGE = "https://electionresults.sos.mn.gov/Select/VoterTurnOut/Index?ersElectionId=201"
HISTORY_ENTRY_PAGE = (
    "https://www.sos.mn.gov/election-administration-campaigns/"
    "data-maps/county-entry-of-voting-history/"
)
VOTER_LIST_PAGE = (
    "https://www.sos.mn.gov/election-administration-campaigns/"
    "data-maps/registered-voter-list-requests/"
)
HISTORICAL_PAGE = (
    "https://www.sos.mn.gov/election-administration-campaigns/"
    "data-maps/historical-voter-turnout-statistics/"
)
WEB_OBSERVED_AT = "2026-11-07T18:40:19.159-05:00"
WEB_UPDATE_CLOCK = "11/07/26 5:18 PM"
WEB_UPDATE_TIMEZONE = None


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href = None
        self.current_href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.current_href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.current_href:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href:
            if " ".join("".join(self.text).split()) == "Precinct Reporting Statistics":
                if self.href is not None:
                    raise ValueError("Duplicate declared Precinct Reporting Statistics link")
                self.href = self.current_href
            self.current_href = None
            self.text = []


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def csv_bytes(headers, rows) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def read_native(path: Path):
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")), delimiter=";"))


def copy_reused_originals() -> None:
    REUSED.mkdir(exist_ok=False)
    names = (
        "media-index.html",
        "media-index.html.receipt.json",
        "layout.txt",
        "layout.txt.receipt.json",
        "counties.txt",
        "counties.txt.receipt.json",
        "precincts.txt",
        "precincts.txt.receipt.json",
    )
    for name in names:
        shutil.copyfile(PRIOR_ORIGINALS / name, REUSED / name)
    shutil.copyfile(
        PRIOR_REVIEW / "county-participation.csv",
        HERE / "previous-county-participation-20261106.csv",
    )


def declared_pctstats_url() -> str:
    parser = LinkParser()
    parser.feed((REUSED / "media-index.html").read_text(encoding="utf-8"))
    if not parser.href or not parser.href.startswith("https://electionresultsfiles.sos.mn.gov/"):
        raise ValueError("No permitted official pctstats link in reused frozen media index")
    return parser.href


def acquire() -> None:
    if ORIGINALS.exists() or REUSED.exists() or CURRENT.exists():
        raise FileExistsError("Acquisition output already exists; refusing a repeat request")
    ORIGINALS.mkdir()
    copy_reused_originals()
    url = declared_pctstats_url()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Minnesota participation evidence verifier/1.0"},
    )
    started = dt.datetime.now(dt.timezone.utc)
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read()
        status = response.status
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type")
    finished = dt.datetime.now(dt.timezone.utc)
    CURRENT.write_bytes(body)
    receipt = {
        "declared_by_reused_original": "reused-frozen-originals/media-index.html",
        "declared_link_text": "Precinct Reporting Statistics",
        "url": url,
        "final_url": final_url,
        "status": status,
        "content_type": content_type,
        "bytes": len(body),
        "sha256": sha256(body),
        "request_started_at_utc": started.isoformat(),
        "receipt_finished_at_utc": finished.isoformat(),
        "attempts": 1,
    }
    write_json(RECEIPT, receipt)
    if status != 200 or final_url != url:
        raise ValueError("Official source returned a denial, redirect, or non-200 response")


def integer(value: str) -> int:
    if not value.isascii() or not value.isdecimal():
        raise ValueError(f"Expected unsigned native integer, got {value!r}")
    return int(value)


def previous_rows():
    with (HERE / "previous-county-participation-20261106.csv").open(newline="") as source:
        return {row["native_county_id"]: row for row in csv.DictReader(source)}


def build() -> dict:
    receipt = json.loads(RECEIPT.read_text())
    body = CURRENT.read_bytes()
    if (
        receipt["status"] != 200
        or receipt["final_url"] != receipt["url"]
        or receipt["bytes"] != len(body)
        or receipt["sha256"] != sha256(body)
        or receipt["attempts"] != 1
    ):
        raise ValueError("Current original does not match its one-request receipt")

    counties = read_native(REUSED / "counties.txt")
    precincts = read_native(REUSED / "precincts.txt")
    statistics = read_native(CURRENT)
    if len(counties) != 87 or len(precincts) != 4105 or len(statistics) != 4105:
        raise ValueError("Changed Minnesota native universe")
    if any(len(row) != 12 or row[0] != "MN" or row[4] not in ("0", "1") for row in statistics):
        raise ValueError("Changed Minnesota precinct-statistics schema")
    for row in statistics:
        for value in row[5:]:
            integer(value)
    reference_keys = {(row[0], row[1]) for row in precincts}
    statistic_keys = {(row[1], row[2]) for row in statistics}
    if len(reference_keys) != 4105 or reference_keys != statistic_keys:
        raise ValueError("Current statistics do not match the reused 4,105-precinct reference")

    previous = previous_rows()
    current_rows = []
    mode_rows = []
    comparison_rows = []
    newly_complete = []
    changed_complete = []
    quality_rows = []
    statewide = {
        "registered_7am": 0,
        "registered_election_day": 0,
        "roster_signatures": 0,
        "regular_military_overseas_absentee": 0,
        "federal_only_absentee": 0,
        "president_only_absentee": 0,
        "total_number_voted": 0,
    }
    for county_id, county_name, declared_count in counties:
        selected = [row for row in statistics if row[1] == county_id]
        if len(selected) != integer(declared_count):
            raise ValueError(f"Changed precinct count for {county_name}")
        reported = [row for row in selected if row[4] == "1"]
        complete = len(reported) == len(selected)
        sums = {
            "registered_7am": sum(integer(row[5]) for row in reported),
            "registered_election_day": sum(integer(row[6]) for row in reported),
            "roster_signatures": sum(integer(row[7]) for row in reported),
            "regular_military_overseas_absentee": sum(integer(row[8]) for row in reported),
            "federal_only_absentee": sum(integer(row[9]) for row in reported),
            "president_only_absentee": sum(integer(row[10]) for row in reported),
            "total_number_voted": sum(integer(row[11]) for row in reported),
        }
        for key in statewide:
            statewide[key] += sums[key]
        denominator = sums["registered_7am"] + sums["registered_election_day"]
        component_sum = (
            sums["roster_signatures"]
            + sums["regular_military_overseas_absentee"]
            + sums["federal_only_absentee"]
            + sums["president_only_absentee"]
        )
        conflicts = 0
        excesses = 0
        for row in reported:
            row_component_sum = sum(integer(value) for value in row[7:11])
            residual = integer(row[11]) - row_component_sum
            excess = integer(row[11]) - integer(row[5]) - integer(row[6])
            if residual:
                conflicts += 1
                quality_rows.append(
                    [
                        county_id,
                        county_name,
                        row[2],
                        row[3],
                        "native_component_residual",
                        residual,
                    ]
                )
            if excess > 0:
                excesses += 1
                quality_rows.append(
                    [
                        county_id,
                        county_name,
                        row[2],
                        row[3],
                        "voted_exceeds_7am_plus_election_day_registration",
                        excess,
                    ]
                )
        rate_eligible = complete and denominator > 0 and conflicts == 0 and excesses == 0
        rate = sums["total_number_voted"] / denominator if rate_eligible else None
        count_status = "approved_unofficial_complete_count" if complete else "approved_partial_subtotal_only"
        current_rows.append(
            [
                county_id,
                county_name,
                declared_count,
                len(reported),
                len(selected) - len(reported),
                str(complete).lower(),
                sums["total_number_voted"],
                sums["total_number_voted"] if complete else "",
                sums["registered_7am"] if complete else "",
                sums["registered_election_day"] if complete else "",
                denominator if complete else "",
                f"{rate:.8f}" if rate is not None else "",
                conflicts,
                excesses,
                str(rate_eligible).lower(),
                "Total Number Voted",
                "Unofficial Results",
                WEB_UPDATE_CLOCK,
                "",
                "all native precinct-statistics rows with has_reported_statistics=1",
                "no separate native provisional field",
                count_status,
                "approved_registration_fraction" if rate_eligible else "withheld_registration_fraction",
            ]
        )
        mode_rows.append(
            [
                county_id,
                county_name,
                sums["roster_signatures"],
                sums["regular_military_overseas_absentee"],
                sums["federal_only_absentee"],
                sums["president_only_absentee"],
                component_sum,
                sums["total_number_voted"],
                sums["total_number_voted"] - component_sum,
                "literal native components; not normalized ballot modes",
            ]
        )
        old = previous[county_id]
        old_complete = old["all_statistics_reported"] == "true"
        old_observed = integer(old["reported_total_number_voted_subtotal"])
        current_total = sums["total_number_voted"]
        comparison = [
            county_id,
            county_name,
            old["reported_statistics"],
            old["missing_statistics"],
            str(old_complete).lower(),
            old_observed,
            len(reported),
            len(selected) - len(reported),
            str(complete).lower(),
            current_total,
            current_total - old_observed,
            "newly_complete"
            if not old_complete and complete
            else (
                "still_partial_newer_subtotal"
                if not complete and current_total != old_observed
                else (
                    "revised_complete_total"
                    if old_complete and current_total != old_observed
                    else "unchanged"
                )
            ),
        ]
        comparison_rows.append(comparison)
        if not old_complete and complete:
            newly_complete.append(comparison)
        if old_complete and current_total != old_observed:
            changed_complete.append(comparison)

    statewide_denominator = statewide["registered_7am"] + statewide["registered_election_day"]
    old_observed_statewide = sum(
        integer(row["reported_total_number_voted_subtotal"]) for row in previous.values()
    )
    old_complete_only = sum(
        integer(row["complete_total_number_voted"])
        for row in previous.values()
        if row["complete_total_number_voted"]
    )

    headers = [
        "native_county_id",
        "county_name",
        "reference_precincts",
        "reported_statistics",
        "missing_statistics",
        "all_statistics_reported",
        "reported_total_number_voted_subtotal",
        "complete_total_number_voted",
        "complete_registered_7am",
        "complete_registered_election_day",
        "complete_derived_7am_plus_election_day_registration",
        "approved_registration_fraction",
        "precinct_component_conflicts",
        "precinct_electorate_excesses",
        "registration_fraction_eligible",
        "native_numerator_label",
        "native_status",
        "native_update_clock",
        "native_update_timezone",
        "counting_scope",
        "provisional_scope",
        "count_publication_status",
        "rate_publication_status",
    ]
    (HERE / "county-participation-current.csv").write_bytes(csv_bytes(headers, current_rows))
    comparison_headers = [
        "native_county_id",
        "county_name",
        "prior_reported_statistics",
        "prior_missing_statistics",
        "prior_complete",
        "prior_observed_total_number_voted",
        "current_reported_statistics",
        "current_missing_statistics",
        "current_complete",
        "current_total_number_voted",
        "current_minus_prior_observed",
        "disposition",
    ]
    (HERE / "county-comparison-to-20261106.csv").write_bytes(
        csv_bytes(comparison_headers, comparison_rows)
    )
    (HERE / "newly-complete-counties.csv").write_bytes(
        csv_bytes(comparison_headers, newly_complete)
    )
    (HERE / "revised-previously-complete-counties.csv").write_bytes(
        csv_bytes(comparison_headers, changed_complete)
    )
    (HERE / "county-native-components.csv").write_bytes(
        csv_bytes(
            [
                "native_county_id",
                "county_name",
                "roster_signatures",
                "regular_military_overseas_absentee",
                "federal_only_absentee",
                "president_only_absentee",
                "native_component_sum",
                "total_number_voted",
                "total_minus_native_components",
                "scope_caution",
            ],
            mode_rows,
        )
    )
    (HERE / "precinct-quality-exceptions.csv").write_bytes(
        csv_bytes(
            [
                "native_county_id",
                "county_name",
                "precinct_id",
                "precinct_name",
                "exception",
                "residual",
            ],
            quality_rows,
        )
    )
    official_estimates = {"23": 10481, "29": 11883, "86": 76143}
    page_conflicts = []
    for row in current_rows:
        county_id = row[0]
        if county_id in official_estimates:
            page_conflicts.append(
                [
                    county_id,
                    row[1],
                    row[3],
                    row[4],
                    row[6],
                    official_estimates[county_id],
                    official_estimates[county_id] - int(row[6]),
                    "Estimated Voters",
                    "not approved as exact Total Number Voted",
                ]
            )
    (HERE / "official-page-estimates-vs-native.csv").write_bytes(
        csv_bytes(
            [
                "native_county_id",
                "county_name",
                "native_reported_statistics",
                "native_missing_statistics",
                "native_reported_total_number_voted_subtotal",
                "official_page_estimated_voters",
                "estimate_minus_native_subtotal",
                "official_page_label",
                "publication_status",
            ],
            page_conflicts,
        )
    )

    summary = {
        "election_date": "2026-11-03",
        "native_status": "Unofficial Results",
        "native_update_clock": WEB_UPDATE_CLOCK,
        "native_update_timezone": WEB_UPDATE_TIMEZONE,
        "fetch_receipt_clock_utc": receipt["receipt_finished_at_utc"],
        "native_counties": 87,
        "native_precincts": 4105,
        "reported_precinct_statistics": sum(row[4] == "1" for row in statistics),
        "missing_precinct_statistics": sum(row[4] == "0" for row in statistics),
        "counties_complete": sum(row[5] == "true" for row in current_rows),
        "counties_partial": sum(row[5] != "true" for row in current_rows),
        "previous_counties_complete": 75,
        "newly_complete_counties": len(newly_complete),
        "previous_reported_precinct_statistics": 3671,
        "newly_reported_precinct_statistics": len(
            [row for row in statistics if row[4] == "1"]
        )
        - 3671,
        "current_reported_total_number_voted_subtotal": statewide["total_number_voted"],
        "current_exact_statewide_total_number_voted": None,
        "official_web_page_estimated_voters": 2852528,
        "previous_observed_total_number_voted_across_reported_precincts": old_observed_statewide,
        "current_reported_subtotal_minus_previous_observed": statewide["total_number_voted"]
        - old_observed_statewide,
        "previous_complete_counties_total_number_voted": old_complete_only,
        "current_reported_subtotal_minus_previous_complete_counties_only": statewide["total_number_voted"]
        - old_complete_only,
        "reported_rows_registered_7am_subtotal": statewide["registered_7am"],
        "reported_rows_registered_election_day_subtotal": statewide[
            "registered_election_day"
        ],
        "reported_rows_7am_plus_election_day_registration_subtotal": statewide_denominator,
        "statewide_registration_frame_fraction": None,
        "eligible_population_from_current_official_web_page": 4404656,
        "official_web_page_estimated_turnout_fraction": 2852528 / 4404656,
        "native_components": {
            "roster_signatures": statewide["roster_signatures"],
            "regular_military_overseas_absentee": statewide[
                "regular_military_overseas_absentee"
            ],
            "federal_only_absentee": statewide["federal_only_absentee"],
            "president_only_absentee": statewide["president_only_absentee"],
        },
        "precinct_component_conflicts": sum(
            row[4] == "native_component_residual" for row in quality_rows
        ),
        "precinct_electorate_excesses": sum(
            row[4] == "voted_exceeds_7am_plus_election_day_registration"
            for row in quality_rows
        ),
        "scope": {
            "numerator": "Native Total Number Voted, not candidate votes.",
            "registration_frame": "Native 7AM registration plus Election Day registrations.",
            "modes": (
                "Roster signatures and three absentee fields are preserved literally and are not "
                "renamed as normalized ballot modes."
            ),
            "provisionals": "No separate provisional field is supplied in pctstats.txt.",
            "clock": "The official page prints a clock but no timezone; timezone remains unknown.",
            "certification": "All figures remain unofficial.",
        },
        "publication_approval": {
            "complete_county_participation_counts": "84_APPROVED_WITH_UNOFFICIAL_STATUS_AND_SCOPE",
            "partial_county_subtotals": "3_APPROVED_ONLY_AS_PARTIAL_SUBTOTALS",
            "all_87_exact_county_counts": "BLOCKED_BY_26_NATIVE_UNREPORTED_PRECINCT_STATISTICS",
            "statewide_total_number_voted": "BLOCKED_NOT_EXACT_IN_NATIVE_DOWNLOAD",
            "official_page_estimated_voters": "APPROVED_ONLY_AS_ESTIMATE_NOT_EXACT_BALLOT_COUNT",
            "county_registration_fractions": (
                "ROW_LEVEL_ONLY_WHERE registration_fraction_eligible=true"
            ),
            "native_component_counts": "APPROVED_AS_LITERAL_COUNTS_NOT_NORMALIZED_MODES",
            "candidate_behavior": "NOT_IN_SCOPE",
            "repeat_participation": "UNKNOWN_NOT_RELEASED_AS_PUBLIC_AGGREGATE",
        },
    }
    write_json(HERE / "state-summary.json", summary)

    web_observation = {
        "observed_at_local": WEB_OBSERVED_AT,
        "source_url": COUNTY_PAGE,
        "official_values": {
            "eligible_population": 4404656,
            "estimated_voters": 2852528,
            "estimated_turnout_percent": 64.76,
            "counties_reporting": 87,
            "counties_complete": 87,
            "precincts_reporting": 4105,
            "precincts_total": 4105,
            "last_updated": WEB_UPDATE_CLOCK,
            "last_updated_timezone": None,
            "voters_registered_at_7am": 3927715,
        },
        "native_download_conflict": {
            "reported_precinct_statistics": 4079,
            "missing_precinct_statistics": 26,
            "complete_counties": 84,
            "partial_counties": ["Fillmore", "Hubbard", "Wright"],
            "interpretation": (
                "The statewide page's 87 complete and Estimated Voters display is not treated as "
                "proof that all native Total Number Voted fields are complete."
            ),
        },
        "qualification": (
            "Current primary-source browser observation. The downloadable pctstats original is the "
            "byte-frozen source of county totals; this page supplies the displayed status and clock."
        ),
    }
    write_json(HERE / "current-official-web-observation.json", web_observation)

    history = {
        "assessment_date": "2026-11-07",
        "current_2026_general_linked_history_aggregate": "UNKNOWN_NOT_NORMALLY_RELEASED_YET",
        "official_current_page_state": (
            "The county-entry page still reports the August 11, 2026 State Primary and does not "
            "supply November 3 General Election linked-history completion or repeat-participation."
        ),
        "normal_timing": {
            "rule": (
                "Counties complete Election Day registration and voting-history entry within 42 "
                "days, with a possible 28-day extension after notice."
            ),
            "calculated_initial_general_deadline": "2026-12-15",
            "calculated_extended_general_deadline": "2027-01-12",
        },
        "individual_history_route": {
            "availability": "restricted_order_only",
            "action_taken": "none",
            "reason": (
                "Official detailed history requires a paid request by a registered Minnesota voter "
                "for election, political, or law-enforcement purposes. No identifiable voter file "
                "was acquired and no request was submitted."
            ),
            "frame": (
                "Reports are point-in-time current-registration files; detailed history links only "
                "currently registered voters and may lag after a general election."
            ),
        },
        "interpretation_limits": [
            "A positive history match is within the current-registration frame, not original-cohort retention.",
            "Absent history is UNKNOWN and is not proof of nonvoting.",
            "Recent registration is not first-ever registration.",
            "No administrative party field is interpreted as candidate choice.",
            "No repeat-participation or first-time-voter count is approved from this follow-up.",
        ],
        "official_pages": [HISTORY_ENTRY_PAGE, VOTER_LIST_PAGE, HISTORICAL_PAGE],
        "next_concrete_public_input": (
            "A Secretary of State public aggregate that explicitly reports November 3, 2026 voting-"
            "history entry or repeat-participation after the statutory entry period."
        ),
    }
    write_json(HERE / "linked-history-availability.json", history)
    return summary


def build_readme(summary: dict) -> None:
    text = f"""# Minnesota 2026 participation follow-up

## Useful new official evidence

The official `pctstats.txt` declared by the Minnesota Secretary of State media-files page
now has **4,079/4,105 reported precinct statistics and 84/87 complete counties**. The retained
November 6 observation had 3,671 reported precincts, 434 missing precincts, 75 complete counties,
and 12 partial counties. This is a genuine gain of **408 precinct statistics** and **9 newly
complete counties**.

The 9 newly complete counties are listed in `newly-complete-counties.csv`. Exact revisions to
previously complete counties are in `revised-previously-complete-counties.csv`; all 87 comparisons
are in `county-comparison-to-20261106.csv`.

The official statewide page separately displays 87 complete counties and 2,852,528
**Estimated Voters**, but the byte-frozen native download still has 26 unreported rows in Fillmore,
Hubbard, and Wright. Those estimates are preserved in `official-page-estimates-vs-native.csv` but
are not relabeled as exact native `Total Number Voted`.

## Native qualifications

- Status: **Unofficial Results**.
- Official page clock: **{WEB_UPDATE_CLOCK}**; the page does not state a timezone.
- Receipt time: `{summary['fetch_receipt_clock_utc']}` UTC.
- Numerator: native **Total Number Voted**, not candidate votes.
- Registration frame: registered at 7AM plus Election Day registrations.
- Counting scope: 4,079 native rows where `has_reported_statistics=1`; 26 rows remain
  explicitly unreported.
- Provisionals: no separate provisional field appears in the native statistics layout.
- Components: roster signatures plus three native absentee fields are preserved literally, not
  relabeled as normalized voting modes.
- County fractions remain withheld where native component conflicts or electorate excesses occur.

## Linked-history disposition

No public November 2026 aggregate repeat-participation release was found. The official county-entry
page still covers the August 2026 primary. Individual detailed history is a restricted, paid,
purpose-limited current-registration report; no order or identifiable voter-file acquisition was
made. See `linked-history-availability.json`.

## Publication approval

**Approved with qualifiers:** 84 complete county `Total Number Voted` counts and partial subtotals
for Fillmore, Hubbard, and Wright, clearly labeled unofficial. Literal component counts may be
published only under their native labels. County registration fractions are approved only where
the CSV marks them eligible.
An exact all-87-county/native statewide total remains blocked by the 26 native unreported rows.
Repeat-participation, first-time-voter, nonvoter, candidate-cohort, and normalized mode claims are
not approved.

## Primary official routes

- `{MEDIA_PAGE}`
- `{COUNTY_PAGE}`
- `{TURNOUT_PAGE}`
- `{HISTORY_ENTRY_PAGE}`
- `{VOTER_LIST_PAGE}`

## Reproduce and verify

The live original was acquired exactly once. Verification is offline:

```sh
python3 build_minnesota_followup.py verify
```
"""
    (HERE / "README.md").write_text(text)


def make_archive() -> None:
    included = [
        path
        for path in HERE.rglob("*")
        if path.is_file()
        and path != ARCHIVE
        and path.name not in {"checksums.sha256", "verification-results.json"}
    ]
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for path in sorted(included):
            info = zipfile.ZipInfo(
                path.relative_to(HERE).as_posix(), date_time=(2026, 11, 7, 18, 40, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            target.writestr(info, path.read_bytes(), compresslevel=9)


def write_checksums() -> None:
    files = sorted(
        path for path in HERE.rglob("*") if path.is_file() and path.name != "checksums.sha256"
    )
    lines = [
        f"{sha256(path.read_bytes())}  {path.relative_to(HERE).as_posix()}\n" for path in files
    ]
    (HERE / "checksums.sha256").write_text("".join(lines))


def verify() -> dict:
    checks = []
    receipt = json.loads(RECEIPT.read_text())
    checks.append(("receipt_status_200", receipt["status"] == 200))
    checks.append(("receipt_attempts_one", receipt["attempts"] == 1))
    checks.append(("receipt_bytes", receipt["bytes"] == CURRENT.stat().st_size))
    checks.append(("receipt_sha256", receipt["sha256"] == sha256(CURRENT.read_bytes())))
    rows = list(csv.DictReader((HERE / "county-participation-current.csv").open()))
    checks.append(("county_rows_87", len(rows) == 87))
    checks.append(
        (
            "complete_84_partial_3",
            sum(row["all_statistics_reported"] == "true" for row in rows) == 84
            and sum(row["all_statistics_reported"] == "false" for row in rows) == 3,
        )
    )
    checks.append(
        (
            "publication_statuses_qualified",
            sum(
                row["count_publication_status"] == "approved_unofficial_complete_count"
                for row in rows
            )
            == 84
            and sum(
                row["count_publication_status"] == "approved_partial_subtotal_only"
                for row in rows
            )
            == 3,
        )
    )
    new_rows = list(csv.DictReader((HERE / "newly-complete-counties.csv").open()))
    checks.append(("newly_complete_9", len(new_rows) == 9))
    summary = json.loads((HERE / "state-summary.json").read_text())
    checks.append(
        (
            "reported_subtotal_matches_counties",
            sum(integer(row["reported_total_number_voted_subtotal"]) for row in rows)
            == summary["current_reported_total_number_voted_subtotal"],
        )
    )
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = archive.namelist()
        checks.append(("archive_has_current_original", "originals/pctstats.txt" in names))
        checks.append(("archive_has_county_query", "county-participation-current.csv" in names))
        checks.append(("archive_has_reused_references", "reused-frozen-originals/precincts.txt" in names))
        bad = archive.testzip()
        checks.append(("archive_crc", bad is None))
    result = {
        "verified_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": "python3 build_minnesota_followup.py verify",
        "checks": [{"name": name, "passed": passed} for name, passed in checks],
        "passed": all(passed for _, passed in checks),
    }
    write_json(HERE / "verification-results.json", result)
    if not result["passed"]:
        raise SystemExit(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("acquire-build", "build-existing", "verify"))
    args = parser.parse_args()
    if args.command == "acquire-build":
        acquire()
        summary = build()
        build_readme(summary)
        make_archive()
        write_checksums()
        result = verify()
        write_checksums()
        print(
            json.dumps(
                {
                    "output": str(HERE),
                    "reported_total_number_voted_subtotal": summary[
                        "current_reported_total_number_voted_subtotal"
                    ],
                    "counties_complete": summary["counties_complete"],
                    "newly_complete_counties": summary["newly_complete_counties"],
                    "archive_bytes": ARCHIVE.stat().st_size,
                    "archive_sha256": sha256(ARCHIVE.read_bytes()),
                    "verified": result["passed"],
                },
                indent=2,
            )
        )
    elif args.command == "build-existing":
        summary = build()
        build_readme(summary)
        make_archive()
        write_checksums()
        result = verify()
        write_checksums()
        print(
            json.dumps(
                {
                    "output": str(HERE),
                    "reported_total_number_voted_subtotal": summary[
                        "current_reported_total_number_voted_subtotal"
                    ],
                    "counties_complete": summary["counties_complete"],
                    "newly_complete_counties": summary["newly_complete_counties"],
                    "archive_bytes": ARCHIVE.stat().st_size,
                    "archive_sha256": sha256(ARCHIVE.read_bytes()),
                    "verified": result["passed"],
                },
                indent=2,
            )
        )
    else:
        result = verify()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
