"""Reconcile Pima's complete 2026 general CSV and independent dashboard counts."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, urlsplit
import zipfile


SOURCE = "https://content.civicplus.com/api/assets/az-pimacounty/07a8ea65-53fd-47a0-84cb-8784c21e2a18"
GENERAL = "https://www.livevoterturnout.com/ENR/pimaazenr/7/en/Index_7.html"
DISCOVERY = {"official-voting-maps", "official-declared-dataset", "official-elections-2026-page",
             "official-pima-vote-hub", "official-declared-general-results-index"}
HOUSE = {
    "AZ-6": ["MENDOZA, JOANNA (DEM)", "CISCOMANI, JUAN (REP)",
             "PETERS, JEREME LANCE (LBT)", "SWING, GARY (GRN)", "Write-in",
             "OVER VOTES", "UNDER VOTES"],
    "AZ-7": ["GRIJALVA, ADELITA (DEM)", "BUTIEREZ SR., DANIEL FRANCIS (REP)",
             "Write-in", "OVER VOTES", "UNDER VOTES"],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]+", value),
            "Missing, negative or noninteger native count")
    return int(value)


def review_tables(table, dashboard, media):
    width = len(table[0])
    require(len(table) >= 5 and width > 6 and all(len(row) == width for row in table)
            and table[0][:6] == ["COUNTY NUMBER", "PRECINCT CODE", "PRECINCT NAME",
                "REGISTERED VOTERS TOTAL", "BALLOTS CAST TOTAL", "BALLOTS CAST BLANK"]
            and all(row[-1] == "" for row in table)
            and table[-1][:3] == ["", "ZZZ", "COUNTY TOTALS"],
            "Unexpected complete county CSV layout or total row")
    columns = {}
    for contest, candidates in HOUSE.items():
        title = "U.S. Representative in Congress Dist. " + contest[-1]
        indices = [i for i, name in enumerate(table[0]) if name == title]
        require([table[2][i] for i in indices] == candidates,
                "Unexpected House contest/candidate declaration")
        columns[contest] = indices
    require(len(media) == len({row["precinct"] for row in media})
            == len({row["precinct_code"] for row in media}),
            "Duplicate native media identity")
    media_by_name = {row["precinct"]: row for row in media}
    groups, codes = {}, {}
    for ordinal, row in enumerate(table[3:-1], 4):
        require(row[0] == "" and re.fullmatch(r"[0-9]{4}", row[1])
                and row[2] in dashboard, "Unexpected county/precinct identity")
        require(row[1] not in codes or codes[row[1]] == row[2],
                "Reused county precinct code")
        codes[row[1]] = row[2]
        groups.setdefault(row[2], []).append((ordinal, row, [number(x) for x in row[3:-1]]))
    require(bool(groups) and groups.keys() == dashboard.keys() == media_by_name.keys()
            and len(codes) == len(groups), "Incomplete literal precinct identity sets")
    results, participation = [], []
    for name in sorted(groups):
        components, obs, old = groups[name], dashboard[name], media_by_name[name]
        require(len(components) == 3, "Incomplete or duplicate unnamed CSV component rows")
        require(obs["ElectionID"] == "7" and obs["PrecinctName"] == name
                and all(row[1] == obs["PrecinctCode"] for _, row, _ in components)
                and obs["StatusValue"] in {"Reported", "Not Reported"},
                "Dashboard election, identity or reporting status differs")
        require(old["year"] == "2026" and old["state_code"] == "AZ"
                and old["county_code"] == "pima" and old["county"] == "Pima County"
                and old["contest_id"] in HOUSE and old["native_virtual_precinct"] == "False",
                "Unreviewed media election/county/House scope")
        registrations = {counts[0] for _, _, counts in components}
        require(len(registrations) == 1, "Conflicting repeated registration counts")
        registered = next(iter(registrations))
        sums = {i: sum(number(row[i]) for _, row, _ in components) for i in range(4, width - 1)}
        ballots, blank = sums[4], sums[5]
        require(registered == number(obs["VoterCount"])
                and ballots == number(obs["RegularCheckIns"]) and blank <= ballots,
                "Independent ballot/registration observations differ")
        require(isinstance(obs["RegularTurnout"], str)
                and re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", obs["RegularTurnout"]),
                "Missing or malformed native turnout display")
        require((registered == 0 and float(obs["RegularTurnout"]) == 0) or
                (registered > 0 and math.isclose(float(obs["RegularTurnout"]),
                    100 * ballots / registered, rel_tol=0, abs_tol=.005000001)),
                "Native turnout display differs from its counts")
        contest = old["contest_id"]
        counts = [sums[i] for i in columns[contest]]
        democratic, republican, other = counts[0], counts[1], sum(counts[2:-2])
        total = democratic + republican + other
        require([total, democratic, republican, other] ==
                [number(old[field]) for field in
                 ["total_votes", "democratic_votes", "republican_votes", "other_votes"]],
                "Independent complete House vectors differ")
        require(all(sums[i] == 0 for key, indices in columns.items()
                    if key != contest for i in indices), "Unexpected second House scope")
        common = dict(year=2026, state_code="AZ", county_code="pima", county="Pima County",
            precinct_code=obs["PrecinctCode"], precinct=name,
            native_media_precinct_code=old["precinct_code"],
            source_csv_rows=json.dumps([n for n, _, _ in components]),
            native_reporting_status=obs["StatusValue"], maps_approved=False)
        results.append(dict(common, contest_id=contest, total_votes=total,
            democratic_votes=democratic, republican_votes=republican, other_votes=other,
            over_votes=counts[-2], under_votes=counts[-1],
            candidates=json.dumps(dict(zip(HOUSE[contest][:-2], counts[:-2])),
                                  separators=(",", ":"))))
        participation.append(dict(common, registered_voters_total=registered,
            ballots_cast_total=ballots, ballots_cast_blank=blank,
            native_regular_turnout_percent=obs["RegularTurnout"], turnout_rate="",
            quality_flags=json.dumps(["provisional", "registration_components_not_defined"]
                + (["not_reported"] if obs["StatusValue"] != "Reported" else [])
                + (["ballots_exceed_registration"] if ballots > registered else [])),
            component_modes="Three unnamed source rows; no voting-mode labels inferred"))
    require(sum(row["registered_voters_total"] for row in participation) == number(table[-1][3]),
            "Unique precinct registrations do not reconcile to county")
    for i in range(4, width - 1):
        require(sum(number(row[i]) for row in table[3:-1]) == number(table[-1][i]),
                "Complete option/ballot column does not reconcile to county")
    audit = dict(year=2026, state_code="AZ", county="Pima County", election_id="7",
        source_url=SOURCE, source_csv_rows=len(table), source_csv_columns=width,
        precincts=len(groups), unnamed_components_per_precinct=3,
        ballot_and_option_columns_reconciled=width - 5,
        ballots=sum(row["ballots_cast_total"] for row in participation),
        registered_voters=sum(row["registered_voters_total"] for row in participation),
        blank_ballots=sum(row["ballots_cast_blank"] for row in participation),
        house_votes=sum(row["total_votes"] for row in results),
        literal_precinct_names_and_dashboard_codes_agree=True,
        complete_independent_house_vectors_agree=True,
        native_reporting_statuses={status: sum(row["native_reporting_status"] == status
            for row in participation) for status in sorted({r["native_reporting_status"] for r in participation})},
        registration_counted_once_per_precinct=True, voting_mode_labels_inferred=False,
        maps_approved=False, rates_available=False,
        next_action="Restore the dashboard-declared 2026 geometry or acquire an explicit "
            "same-election crosswalk; do not substitute the 2024 GIS reference. "
            "Clarify active/inactive registration definitions before analysis rates.")
    return results, participation, audit


def build(count_review, source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable snapshot overwrite")
    for name, receipt in json.loads((count_review / "checksums.json").read_text()).items():
        raw = (count_review / name).read_bytes()
        require(len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Immutable count-review checksum mismatch")
    receipts = json.loads((source / "sources.json").read_text())

    def original(key):
        receipt = receipts[key]
        raw = gzip.decompress((source / receipt["file"]).read_bytes())
        require(len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Original source checksum mismatch")
        return raw

    require(receipts["official-general-summary-csv"]["url"] == SOURCE
            and receipts["official-general-summary-csv"]["status"] == 200,
            "Unreviewed county CSV source")
    for key in receipts:
        if key not in DISCOVERY:
            original(key)
    for label, count, prefix in [("base", 265, "official-base-"),
                                 ("app", 972, "official-app-")]:
        inventory_prefix = prefix if label == "base" else prefix + "full-"
        before = json.loads(original(inventory_prefix + "ids-before"))
        after = json.loads(original(inventory_prefix + "ids-after"))
        ids = before["objectIds"]
        require(before == after and len(ids) == len(set(ids)) == count,
                "Unstable or duplicate reference inventory")
        require(json.loads(original(inventory_prefix + "layer-before")) ==
                json.loads(original(inventory_prefix + "layer-after")),
                "Reference layer changed during feature acquisition")
        seen = set()
        for key in sorted(k for k in receipts if k.startswith(prefix + "features-")):
            page = json.loads(original(key))
            query = parse_qs(urlsplit(receipts[key]["url"]).query)
            expected = [int(value) for value in query["objectIds"][0].split(",")]
            actual = [f["properties"][before["objectIdFieldName"]] for f in page["features"]]
            require(page["type"] == "FeatureCollection"
                    and not page.get("exceededTransferLimit")
                    and not page.get("properties", {}).get("exceededTransferLimit")
                    and query["outFields"] == ["*"] and query["outSR"] == ["4326"]
                    and query["returnGeometry"] == ["true"] and query["f"] == ["geojson"]
                    and len(actual) == len(set(actual)) == len(expected)
                    and set(actual) == set(expected) and not seen.intersection(actual),
                    "Incomplete or conflicting bounded reference page")
            seen.update(actual)
        require(seen == set(ids), "Incomplete reference feature inventory")
    declaration = json.loads((source / "derived/official-general-declaration.json").read_text())
    payload = (source / "derived/official-general-precinctData.json").read_bytes()
    require(declaration["election"] == "November 3, 2026 General Election"
            and declaration["election_id"] == "7"
            and declaration["parent_sha256"] ==
                receipts["official-declared-general-results-index"]["sha256"]
            and len(payload) == declaration["aggregate_payload"]["bytes"]
            and hashlib.sha256(payload).hexdigest() == declaration["aggregate_payload"]["sha256"]
            and receipts["official-declared-general-results-index"]["url"] == GENERAL,
            "Unreviewed election or extracted factual aggregate payload")
    table = list(csv.reader(io.StringIO(original("official-general-summary-csv").decode("utf-8-sig"))))
    media = [row for row in csv.DictReader((count_review / "precinct-counts.csv").open())
             if row["county_code"] == "pima"]
    results, participation, audit = review_tables(table, json.loads(payload), media)
    require(audit["precincts"] == 265 and audit["source_csv_columns"] == 379,
            "Complete acquired Pima inventory differs")
    audit.update(discovery_frontend_originals_retained_separately=True,
        factual_originals=len(receipts) - len(DISCOVERY),
        general_geometry_download_status=receipts["official-general-declared-geometry"]["status"],
        complete_original_csv_retained=True,
        reference_features_acquired=265, app_union_features_acquired=972)
    output.mkdir(parents=True)
    shutil.copytree(count_review, output / "count-review")
    (output / "source/originals").mkdir(parents=True)
    for key, receipt in receipts.items():
        if key not in DISCOVERY:
            shutil.copyfile(source / receipt["file"], output / "source" / receipt["file"])
    (output / "source/sources.json").write_text(json.dumps(receipts, indent=2) + "\n")
    shutil.copytree(source / "derived", output / "source/derived")
    shutil.copyfile(__file__, output / "review.py")
    (output / "original-county-results.csv.gz").write_bytes(
        gzip.compress(original("official-general-summary-csv"), mtime=0))
    for name, rows in [("precinct-results.csv", results), ("precinct-participation.csv", participation)]:
        with (output / name).open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            checksums[path.relative_to(output).as_posix()] = dict(
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(output).as_posix(), (2026, 11, 5, 0, 0, 0))
                entry.external_attr = 0o100644 << 16
                target.writestr(entry, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count-review", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.count_review, args.source, args.output, args.archive), indent=2))
