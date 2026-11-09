"""Preserve original WV mode workbooks and independently reviewed whole-county reports."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-west-virginia-modes-01"
DOWNLOAD = ("https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-county-west-virginia-modes-20261109-01/complete-analysis.zip")
WORKBOOK_HASHES = {
    "early-in-person-cast": "232a085c9c2a7ea578fa65f43ed27a7bce2b0f709a49dd84efa66e372e6519e5",
    "absentee-requested": "86645bc2d66237944c7af1e8826676f754032033adedc31ca18cbd034f86f1ee",
    "absentee-returned": "972926a8e7075213fecc69fae75130110e22d5369917090a459f121522a3d71b",
}


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def build(source):
    output = ROOT / VERSION
    if output.exists():
        raise ValueError("Refuse to replace native WV inputs")
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    reference = index["coverage"]["WV"]
    path = "data/" + reference["file"].split("/data/", 1)[1]
    original_reference = (ROOT / path).read_bytes()
    decoded_reference = gzip.decompress(original_reference)
    if (reference["counties"] != 55 or index["boundary_reference_year"] != 2026
            or hashlib.sha256(original_reference).hexdigest() != reference["sha256"]
            or hashlib.sha256(decoded_reference).hexdigest() != reference["uncompressed_sha256"]):
        raise ValueError("Wrong full WV 2026 Census county reference")
    geometry = json.loads(decoded_reference)
    identities = {row["properties"]["key"]: row["properties"]["name"] for row in geometry["features"]}
    if (len(identities) != 55 or any(row["properties"]["state_code"] != "WV"
                                  or row["properties"]["boundary_year"] != 2026
                                  for row in geometry["features"])):
        raise ValueError("Incomplete WV source-reference identity frame")
    directory = source / "official-early-mode-workbooks-05"
    module = runpy.run_path(str(ROOT / "scripts/west-virginia-workbooks.py"))
    modes = module["review_workbooks"](directory, identities)
    receipts = {row["product"]: row for row in json.loads(
        (directory / "complete-acquisition.json").read_bytes())}
    members = {}
    for product, digest in WORKBOOK_HASHES.items():
        name = product + "-original.xlsx"
        body = (directory / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("Changed original WV workbook")
        members[name] = body
    parents = []
    for fips, review_path, original_path, count_key, original_sha in [
        ("54107", "54107-Wood-source-review.json", "54107-Wood-original.pdf",
         "ballots_cast", "0092dcb588bce3e6c6fe75d603cb64a355959991b311dda625a6b9114c47746f"),
        ("54039", "54039-Kanawha-source-review.json", "county-report-pass-01/54039/04-private-original.pdf",
         "ballots_cast", "be50e9aac7eff9835c17cc6203aef3102f18cbc94404e870bf2eabcf842750ca"),
        ("54061", "54061-Monongalia-source-review.json",
         "54061-Monongalia-browser-normalized-03/private-decoded-report.html",
         None, "a39a691de544fb7340e76e7e743dc312e09b620cb2c6d0372386d2414913231c"),
    ]:
        review = json.loads((source / review_path).read_bytes())
        body = (source / original_path).read_bytes()
        if hashlib.sha256(body).hexdigest() != original_sha:
            raise ValueError("Changed independently reviewed county original")
        filename = f"originals/{fips}" + Path(original_path).suffix
        members[filename] = body
        value = review[count_key] if count_key else int(review["native_values"]["ballots"].replace(",", ""))
        clock = review.get("source_clock_literal") or "11/03/2026 10:00PM"
        parents.append(dict(year=2026, state_code="WV", county_fips=fips,
            county=identities[fips], source_count=value, measure_literal="Ballots Cast - Total",
            denominator=None, reported_pct=None, unique_voters_certified=False,
            source_clock_literal=clock, timezone_as_printed=None,
            source_status_literal="UNOFFICIAL RESULTS",
            source_url=review["source_url"], original_path=VERSION + "/" + filename,
            original_sha256=original_sha, original_bytes=len(body),
            native_record=review, whole_county_parent_explicit=True,
            reporting_note=("43 of 43 reported; 0 complete and 43 partially reported."
                if fips == "54061" else
                "69 of 69 Election Day and absentee/early reporting; not a certification claim."
                if fips == "54107" else
                "183 of 183 Election Day and absentee/early reporting; not a certification claim.")))
    members["native-mode-queries.json.gz"] = gzip.compress(encoded(modes), mtime=0)
    members["native-county-parents.json"] = encoded(parents)
    members["publisher-definitions.json"] = encoded(dict(
        source_url="https://sos.wv.gov/article/secretary-warner-reports-increase-early-voter-turnout-24-higher-turnout-last-midterm",
        publication_date="2026-11-02", source_period_start="2026-10-21", source_period_end="2026-10-31",
        source_clock=None, timezone=None, original_workbook_receipts=receipts,
        mode_meanings=dict(in_person_early="Early in-person period cast count, source TOTAL VOTERS",
            mail_returned="Absentee returned, not qualified cast or accepted ballots",
            absentee_requested="Absentee requested, not cast or returned"),
        native_combined_figure=169350,
        combined_figure_qualified_as_cast=False,
        party_scope="Native party categories; operational affiliation definition unqualified, never vote choice.",
        no_mode_addition=True, no_rates=True, no_candidate_allocation=True))
    files = {f"{VERSION}/{name}": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
             for name, body in members.items()}
    files[path] = dict(bytes=len(original_reference), sha256=reference["sha256"])
    inputs = dict(version=VERSION, year=2026, state_code="WV", files=files,
        reference=dict(path=path, url=reference["file"], counties=55, boundary_year=2026,
            sha256=reference["sha256"], uncompressed_sha256=reference["uncompressed_sha256"],
            review_id="west-virginia-native-modes-20261109-01"),
        complete_download_url=DOWNLOAD, all_method_county_queries=55, selected_all_method_counts=3,
        mode_county_queries=165, analysis_rates_approved=False, precincts_approved=False,
        statewide_full_election_parent_qualified=False)
    output.mkdir(parents=True)
    for name, body in members.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (output / "inputs.json").write_bytes(encoded(inputs))
    print(json.dumps(dict(all_method_county_queries=55, all_method_counts=3, mode_county_queries=165,
        native_state_mode_parents=3, source_party_categories=7, all_rates_withheld=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    build(parser.parse_args().source)
