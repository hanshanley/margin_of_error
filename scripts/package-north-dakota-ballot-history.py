"""Package complete selected ballot facts and descriptive county comparisons."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-nd-ballot-history/{VERSION}"
PUBLIC = f"public/participation-nd-ballot-history/{VERSION}"
PINS = {
    "selected-observations.json": "d837369711d2f09a91b6db6bfdef4f518d1f39b737cc4000f65c3a6ae9e8a701",
    "methodology-review.json": "c68d54273f360c2cf10cca46ca6ea4bf6992c3314d9b8f7212f5e8ce82ae7480",
}
spec = importlib.util.spec_from_file_location(
    "nd_history", Path(__file__).with_name("review-north-dakota-ballot-history.py"))
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def review(snapshot, methods):
    flags = ("precinct_longitudinal_comparison_qualified", "individual_transitions_qualified",
             "demographic_turnout_rates_qualified", "geographic_overlay_qualified")
    current = {
        "election_id": "348", "house_context_contest_id": "22055", "source_version": "v75",
        "official": False, "updated_utc": "2026-11-05T01:30:08.5674284Z",
    }
    if (set(snapshot) != {"observations", "source_receipts"}
            or methods["status"] != "qualified_descriptive_reported_ballot_count_changes"
            or methods["state_code"] != "ND"
            or methods["measure"] != "source_reported_general_election_ballots_not_candidate_votes"
            or methods["current_snapshot"] != current
            or methods["county_matching"] != "exact_source_names_not_fixed_people_or_precinct_boundaries"
            or methods["historical_county_totals"] !=
            "derived_sums_of_complete_native_precinct_rows_not_independent_county_controls"
            or any(methods[key] is not False for key in flags)):
        raise ValueError("Selected scope or descriptive-only qualification changed")
    observations = snapshot["observations"]
    if sorted(row["year"] for row in observations) != [2022, 2024, 2026]:
        raise ValueError("Require one selected observation per election")
    for observation in observations:
        year = observation["year"]
        keys = {"year", "election_date", "official", "source_updated_native",
                "source_clock_timezone", "ballots", "reported_precincts",
                "native_eligible_voters", "native_denominator_definition", "counties"}
        if year == 2026:
            keys.add("source_version")
            identity_ok = (
                observation["official"] is False
                and observation["election_date"] == "2026-11-03T00:00:00"
                and observation["source_version"] == current["source_version"]
                and observation["source_updated_native"] == current["updated_utc"]
                and observation["source_clock_timezone"] == "UTC"
                and observation["native_eligible_voters"] is None
                and observation["native_denominator_definition"] is None)
        else:
            identity_ok = (
                observation["official"] is True and observation["election_date"] == history.DATES[year]
                and observation["source_clock_timezone"] is None
                and type(observation["native_eligible_voters"]) is int
                and observation["native_eligible_voters"] > 0
                and observation["native_denominator_definition"] ==
                "Source defines eligible voters as estimated residents aged 18+.")
        if (set(observation) != keys or not identity_ok
                or not observation["source_updated_native"]
                or type(observation["reported_precincts"]) is not int):
            raise ValueError("Election identity, status, clock or native denominator changed")
        county_ids, precinct_count = set(), 0
        for county in observation["counties"]:
            code = county["native_county_id"]
            system = ("current_portal_location_id" if year == 2026
                      else "legacy_portal_ordinal_not_FIPS")
            if (set(county) != {"county_name", "native_county_id", "county_identifier_system",
                               "ballots", "precincts"}
                    or not isinstance(code, str) or code in county_ids
                    or not re.fullmatch(r"\d{5}" if year == 2026 else r"\d{2}", code)
                    or county["county_identifier_system"] != system or not county["precincts"]):
                raise ValueError("County identity or complete selected fields changed")
            county_ids.add(code)
            precinct_ids, total = set(), 0
            for precinct in county["precincts"]:
                identity, value = precinct["precinct_id"], precinct["ballots"]
                if (set(precinct) != {"precinct_id", "ballots"}
                        or not isinstance(identity, str) or not re.fullmatch(r"\d+", identity)
                        or identity in precinct_ids or type(value) is not int or value < 0
                        or (year != 2026 and (len(identity) != 6 or not identity.startswith(code)))):
                    raise ValueError("Missing, duplicate, malformed or misplaced precinct ballot fact")
                precinct_ids.add(identity)
                total += value
                precinct_count += 1
            if type(county["ballots"]) is not int or total != county["ballots"]:
                raise ValueError("Selected precincts do not reconcile to county sum")
        if (precinct_count != observation["reported_precincts"]
                or (year != 2026 and county_ids != {f"{number:02}" for number in range(1, 54)})):
            raise ValueError("Complete reporting-unit or historical county controls changed")
    receipts = snapshot["source_receipts"]
    urls = {
        **{str(year): url for year, url in history.HISTORICAL_URLS.items()},
        "election.json": "https://api.resultsnd.sos.nd.gov/Election/GetElectionInfo?cId=north-dakota",
        "full-results.json": "https://resultsnd.sos.nd.gov/results/north-dakota/348/FullDataFile.json",
        "terminology_and_archive": "https://www.sos.nd.gov/elections/election-results",
    }
    if set(receipts) != set(urls):
        raise ValueError("Missing selected native source receipt")
    for name, receipt in receipts.items():
        if (receipt["url"] != urls[name] or type(receipt["bytes"]) is not int
                or receipt["bytes"] <= 0 or not re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"])
                or not set(receipt) <= {"url", "bytes", "sha256", "retrieved_at", "content_type",
                                       "etag", "final_url", "last_modified"}):
            raise ValueError("Native source receipt or public fields changed")
    result = history.compare(observations)
    del result["observations"]
    result.update(
        version=VERSION, source_observations=[
            {key: value for key, value in row.items() if key != "counties"}
            for row in sorted(observations, key=lambda row: row["year"])],
        source_receipts=receipts, methodology=methods)
    return result


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def frozen_write(path, raw):
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("Frozen ballot-history output differs; create a new version")
    path.write_bytes(raw)


def package():
    inputs = {}
    for name, digest in PINS.items():
        raw = (ROOT / DATA / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Reviewed ballot-history input changed")
        inputs[name] = json.loads(raw)
    analysis = review(inputs["selected-observations.json"], inputs["methodology-review.json"])
    out = ROOT / PUBLIC
    out.mkdir(parents=True, exist_ok=True)
    frozen_write(out / "history.json", encoded(analysis))
    paths = [f"{DATA}/{name}" for name in PINS] + [f"{PUBLIC}/history.json"]
    paths += ["scripts/" + name for name in (
        "review-north-dakota-ballot-history.py", "test-review-north-dakota-ballot-history.py",
        "package-north-dakota-ballot-history.py", "test-package-north-dakota-ballot-history.py")]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Extract preserving all paths.\n"
        "Verify every file against checksums.json, then run:\n"
        "python3 scripts/test-review-north-dakota-ballot-history.py\n"
        "python3 scripts/test-package-north-dakota-ballot-history.py\n"
        "python3 scripts/package-north-dakota-ballot-history.py\n"
        "All complete selected ballot facts, exact summary, ZIP and metadata reproduce OFFLINE.\n"
        "Includes every used precinct count (398/385/358), all 53 counties in each year,\n"
        "native state controls, election/status/clocks, historical native denominator definitions,\n"
        "full used-source receipts, methods, exact comparison code and tests. No personal data.\n"
        "Historical counties are derived precinct sums, NOT independent published county controls.\n"
        "Current precinct IDs are county-local, NOT globally unique or longitudinal crosswalks.\n"
        "Sources: North Dakota Secretary of State; exact native URLs/bytes/SHA256 in selected inputs.\n"
        "Offline reproduction starts from selected facts, not copyrighted page markup or unrelated\n"
        "native contests. Original acquisition hashes cannot be reverified from selected facts alone.\n"
        "The included historical extractor documents initial conversion; repeating initial native\n"
        "extraction separately requires the pinned originals and full modern ND reviewer/dependencies\n"
        "from the repository, not a network request during this selected-fact reproduction.\n"
        "Official 2022/2024 are compared to an UNOFFICIAL frozen 2026 reported count, not final turnout.\n"
        "No physical prior-voter dropoff, returning identity, switching, demographic rate, analytical\n"
        "boundary overlay or longitudinal precinct qualification. Native adult estimates are NOT\n"
        "registration denominators and are not used to calculate rates. Analysis is not endorsed.\n"
    ).encode()
    contents["checksums.json"] = encoded({
        path: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for path, raw in sorted(contents.items())})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, raw in sorted(contents.items()):
            member = zipfile.ZipInfo(path, date_time=(2026, 11, 7, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    raw = buffer.getvalue()
    frozen_write(out / "complete-analysis.zip", raw)
    metadata = {
        "file": "complete-analysis.zip", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(contents), "complete_selected_ballot_inputs_and_code": True,
        "selected_precinct_observations": 1141, "county_comparisons": 53,
        "personal_records_included": False, "source_page_markup_redistributed": False,
        "individual_transitions_released": False, "precinct_crosswalk_released": False,
    }
    frozen_write(out / "download.json", encoded(metadata))
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()
