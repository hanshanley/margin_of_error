"""Package complete selected six-election ND ballot facts and comparison code."""

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-nd-long-history/{VERSION}"
PUBLIC = f"public/participation-nd-long-history/{VERSION}"
PINS = {
    "selected-observations.json": "34a2678b828ab3f77b2fe3913f9adb556f5b9afdb684194246233c189cc0bba8",
    "methodology-review.json": "e616f07fddd41e8a763c8ef1a79499bb2ddf67cf0b53c6e7e4d03f159c5b9881",
    "native-source-consistency.json": "3bed5631e36aa84ea7c9b37b23851e3b09177d7ae6c1ea3ba28aeaca998a281a",
}
CODE = tuple("scripts/" + name for name in (
    "review-north-dakota-long-ballot-history.py",
    "test-review-north-dakota-long-ballot-history.py",
    "package-north-dakota-long-ballot-history.py",
    "test-package-north-dakota-long-ballot-history.py",
))
spec = importlib.util.spec_from_file_location("nd_long_history", ROOT / CODE[0])
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def review(snapshot, methods):
    if (set(snapshot) != {"observations", "source_receipts", "prior_selected_sha256"}
            or snapshot["prior_selected_sha256"] != history.PRIOR_SHA256
            or methods["status"] != "qualified_descriptive_reported_ballot_count_changes"
            or methods["state_code"] != "ND" or methods["years"] != list(history.DATES)
            or methods["measure"] != "source_reported_general_election_ballots_not_candidate_votes"
            or methods["county_matching"] !=
            "exact_source_names_not_fixed_people_or_precinct_boundaries"
            or methods["named_native_units"] != list(history.ELECTION_IDS)
            or methods["native_numeric_unit_ids"] != [2022, 2024, 2026]
            or methods["current_snapshot"] != {
                "official": False, "election_id": "348", "house_context_contest_id": "22055",
                "source_version": "v75", "updated_utc": "2026-11-05T01:30:08.5674284Z"}
            or any(methods[key] is not False for key in (
                "precinct_longitudinal_comparison_qualified", "individual_transitions_qualified",
                "demographic_turnout_rates_qualified", "geographic_overlay_qualified",
                "personal_records_included", "original_native_markup_redistributed"))):
        raise ValueError("Selected source scope or descriptive-only qualification changed")
    result = history.compare(snapshot["observations"])
    urls = {
        "2022": "https://results.sos.nd.gov/VoterTurnoutDetails.aspx?eid=vxUYQ0lrpP4.",
        "2024": "https://results.sos.nd.gov/VoterTurnoutDetails.aspx",
        "election.json": "https://api.resultsnd.sos.nd.gov/Election/GetElectionInfo?cId=north-dakota",
        "full-results.json": "https://resultsnd.sos.nd.gov/results/north-dakota/348/FullDataFile.json",
        "terminology_and_archive": "https://www.sos.nd.gov/elections/election-results",
    }
    for year, election_id in history.ELECTION_IDS.items():
        urls[f"{year}-landing"] = f"https://results.sos.nd.gov/Default.aspx?map=Cty&eid={election_id}"
        urls[f"{year}-turnout"] = f"https://results.sos.nd.gov/VoterTurnoutDetails.aspx?eid={election_id}"
    receipts = snapshot["source_receipts"]
    if set(receipts) != set(urls):
        raise ValueError("Missing or unexpected used-source receipt")
    for name, receipt in receipts.items():
        older = name.endswith(("-landing", "-turnout"))
        allowed = (
            {"url", "final_url", "status", "bytes", "sha256", "acquired_at", "declared_by"}
            if older else {"url", "bytes", "sha256", "retrieved_at", "content_type",
                           "etag", "final_url", "last_modified"})
        if (not set(receipt) <= allowed or receipt["url"] != urls[name]
                or type(receipt["bytes"]) is not int or receipt["bytes"] <= 0
                or not re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"])):
            raise ValueError("Used-source receipt or permitted public fields changed")
        if older:
            year, kind = name.split("-")
            parent = "terminology_and_archive" if kind == "landing" else f"{year}-landing"
            declaration = {
                "url": urls[parent], "sha256": receipts[parent]["sha256"],
            }
            if kind == "landing":
                declaration["link_text"] = "General Election - " + history.DATES[int(year)]
            if receipt["status"] != 200 or receipt["declared_by"] != declaration:
                raise ValueError("Frozen declared-link acquisition chain changed")
    result.update(
        version=VERSION, methodology=methods, source_receipts=receipts,
        prior_selected_sha256=snapshot["prior_selected_sha256"],
        native_source_consistency_sha256=PINS["native-source-consistency.json"])
    return result


def unit_csv(observations):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["year", "native_county_id", "county_name",
                     "native_unit_field", "native_unit_value", "ballots"])
    for observation in observations:
        for county in observation["counties"]:
            for unit in county["precincts"]:
                field = "precinct_label" if "precinct_label" in unit else "precinct_id"
                writer.writerow([
                    observation["year"], county["native_county_id"], county["county_name"],
                    field, unit[field], unit["ballots"],
                ])
    return stream.getvalue().encode()


def archive_bytes(contents):
    inventory = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                 for name, raw in sorted(contents.items())}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, raw in sorted({**contents, "checksums.json": encoded(inventory)}.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def package(root=ROOT):
    inputs = {}
    for name, digest in PINS.items():
        raw = (root / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Reviewed six-election input or source proof changed")
        inputs[name] = json.loads(raw)
    snapshot = inputs["selected-observations.json"]
    result = review(snapshot, inputs["methodology-review.json"])
    proof = inputs["native-source-consistency.json"]
    if (proof["status"] != "independent_native_named_unit_verification_passed"
            or proof["new_native_reporting_units"] != 1278
            or proof["all_selected_reporting_units"] != 2419
            or proof["previously_qualified_observations_unchanged"] is not True
            or proof["previously_qualified_receipts_unchanged"] is not True
            or proof["network_blocked"] is not True or proof["reviewer_imported"] is not False):
        raise ValueError("Require completed independent native qualification")
    raw_summary = encoded(result)
    contents = {
        path: (root / path).read_bytes()
        for path in [*(f"{DATA}/{name}" for name in PINS), *CODE]
    }
    contents.update({
        f"{PUBLIC}/history.json": raw_summary,
        "results/reporting-unit-ballots.csv": unit_csv(snapshot["observations"]),
        "REPRODUCTION.txt": (
            "Python>=3.9, standard library only. Extract preserving all paths.\n"
            "Verify every file against checksums.json, then run:\n"
            "python3 scripts/test-review-north-dakota-long-ballot-history.py\n"
            "python3 scripts/test-package-north-dakota-long-ballot-history.py\n"
            "python3 scripts/package-north-dakota-long-ballot-history.py\n"
            "Complete selected facts, six-election comparison, ZIP and metadata reproduce OFFLINE.\n"
            "Includes all 2419 used unit ballot observations, all 318 county observations,\n"
            "265 signed county count changes, state controls, 11 used-source receipts, native\n"
            "election/date/status/clocks/denominator definitions, methods, exact code and tests.\n"
            "Sources: North Dakota Secretary of State and county election officials.\n"
            "2016/2018/2020 units are native LABELS, not invented numeric precinct IDs.\n"
            "2022/2024 use legacy numeric unit IDs; 2026 IDs are local within counties.\n"
            "Import CSV county/unit identifier columns as text to preserve leading zeros.\n"
            "No fixed people, analytical area overlay or cross-year precinct match is established.\n"
            "County totals are complete native-unit sums, not independent published controls.\n"
            "Native historical Eligible Voters are estimated adult residents, NOT registration\n"
            "or a fixed eligible cohort; no turnout rate is calculated from these denominators.\n"
            "Official historical counts are compared with the UNOFFICIAL frozen 2026 v75 count.\n"
            "2026 is not final turnout. Differences are not staying home, returning identity,\n"
            "candidate switching, demographic turnout, or causal persuasion.\n"
            "No personal records, fine demographic cells, unrelated contests or native HTML.\n"
            "Initial native extraction requires the hash-pinned originals; selected-fact\n"
            "reproduction does not reverify original HTML bytes or rerun native extraction.\n"
            "The original independent HTMLParser consistency receipt is included unchanged;\n"
            "it records a completed check, not one rerun during packaging or independent\n"
            "outcome evidence. Previously accepted 2022/2024/2026 inputs remain unchanged.\n"
            "Original complete three-election package remains available at\n"
            "/participation-nd-ballot-history/20261107-01/complete-analysis.zip.\n"
            "This analysis is not endorsed by the source.\n"
        ).encode(),
    })
    raw_zip = archive_bytes(contents)
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw_zip),
        "sha256": hashlib.sha256(raw_zip).hexdigest(), "members": len(contents) + 1,
        "complete_selected_ballot_inputs_and_code": True,
        "selected_reporting_unit_observations": 2419, "county_election_observations": 318,
        "county_comparisons": 53, "elections": 6, "source_receipts": 11,
        "personal_records_included": False, "source_page_markup_redistributed": False,
        "individual_transitions_released": False, "precinct_crosswalk_released": False,
    }
    outputs = {"history.json": raw_summary, "complete-analysis.zip": raw_zip,
               "download.json": encoded(metadata)}
    out = root / PUBLIC
    for name, raw in outputs.items():
        if (out / name).exists() and (out / name).read_bytes() != raw:
            raise ValueError("Frozen six-election output differs; create a new version")
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        if not (out / name).exists():
            (out / name).write_bytes(raw)
    return metadata


if __name__ == "__main__":
    print(json.dumps(package()))
