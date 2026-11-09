"""Extract two explicit Michigan county parents from held, checksum-verified originals."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import runpy

import fitz


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "data/precinct-source-reviews/20261105/MI-2026-native-county-counts-01"
VERSION = "data/county-source-reviews/20261109-michigan-native-parents-01"


def build(output):
    if output.exists():
        raise ValueError("Refuse to replace an immutable Michigan county-parent input")
    checksums = json.loads((ROOT / SOURCE / "checksums.json").read_bytes())
    verified = {}

    def original(name):
        body = (ROOT / SOURCE / name).read_bytes()
        receipt = checksums[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed Michigan source input: " + name)
        verified[f"{SOURCE}/{name}"] = receipt
        return body

    review = runpy.run_path(str(ROOT / SOURCE / "review.py"))
    original("review.py")
    pdf_file = "source/originals/official-bay-general-summary-pdf.gz"
    pdf = gzip.decompress(original(pdf_file))
    with fitz.open(stream=pdf, filetype="pdf") as document:
        page = document[0]
        text = page.get_text()
        if not all(label in text for label in [
                "UNOFFICIAL RESULTS", "2026 General Election", "Bay County", "November 3, 2026"]):
            raise ValueError("Incorrect Bay county parent election")
        counters = re.findall(r"Election Day Precincts Reporting\n([0-9]+ of [0-9]+)\n", text)
        clocks = re.findall(r"Election Summary - [^\n]+", text)
        percentages = re.findall(r"Voter Turnout - Total\n([0-9]+\.[0-9]{2})%", text)
        if len(counters) != 1 or len(clocks) != 1 or len(percentages) != 1:
            raise ValueError("Ambiguous native Bay source labels")
        bay = {
            "year": 2026, "state_code": "MI", "county_code": "bay", "county": "Bay County",
            "source_file": f"{SOURCE}/{pdf_file}", "source_pdf_page": 1,
            "source_pdf_bytes": len(pdf), "source_pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            "native_status": "UNOFFICIAL RESULTS", "native_generated_label": clocks[0],
            "native_pdf_creation_date": document.metadata["creationDate"],
            "native_election_day_reporting": counters[0],
            "native_registered_voters_columns": review["pdf_row"](page, "Registered Voters - Total"),
            "native_ballots_cast_columns": review["pdf_row"](page, "Ballots Cast - Total"),
            "native_turnout_percent": percentages[0],
        }
    units = list(csv.DictReader(io.StringIO(original("precinct-participation.csv").decode("utf-8-sig"))))
    if len(units) != 63 or any(row["year"] != "2026" or row["state_code"] != "MI" for row in units):
        raise ValueError("Incomplete Michigan unit inputs")
    api_file = "source/dashboard-network/response-002.json.gz"
    data = json.loads(gzip.decompress(original(api_file)))
    election = data["election"]
    if (election["electionDate"] != "2026-11-03" or election["isPrimary"] is not False
            or election["isOfficialResults"] is not False or election["isProduction"] is not True):
        raise ValueError("Incorrect Isabella native county parent")
    raw_pointer = (ROOT / "public/county-results.json").read_bytes()
    pointer = json.loads(raw_pointer)
    index_file = pointer["data_directory"] + "/index.json"
    index_raw = (ROOT / index_file).read_bytes()
    index = json.loads(index_raw)
    if index["year"] != 2026 or index["boundary_reference_year"] != 2026:
        raise ValueError("Incorrect Michigan county-reference year")
    geometry = index["coverage"]["MI"]
    from urllib.parse import urlsplit
    url = urlsplit(geometry["file"])
    if url.hostname != "raw.githubusercontent.com" or not re.fullmatch(
            r"/hanshanley/margin_of_error/[0-9a-f]{40}/data/county-results/.+", url.path):
        raise ValueError("Unpinned Michigan county reference")
    geometry_file = "/".join(url.path.split("/")[4:])
    raw_geometry = (ROOT / geometry_file).read_bytes()
    if (hashlib.sha256(raw_geometry).hexdigest() != geometry["sha256"]
            or hashlib.sha256(gzip.decompress(raw_geometry)).hexdigest() != geometry["uncompressed_sha256"]):
        raise ValueError("Changed Michigan reference geometry")
    members = {
        "bay-native-parent.json": (json.dumps(bay, indent=2) + "\n").encode(),
        "native-unit-inputs.json.gz": gzip.compress(
            json.dumps(units, separators=(",", ":"), ensure_ascii=True).encode(), mtime=0),
    }
    for name, body in members.items():
        verified[f"{VERSION}/{name}"] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    verified[geometry_file] = {"bytes": len(raw_geometry), "sha256": hashlib.sha256(raw_geometry).hexdigest()}
    for name, body in [("public/county-results.json", raw_pointer), (index_file, index_raw)]:
        verified[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    inputs = {
        "version": VERSION, "year": 2026, "state_code": "MI", "source_directory": SOURCE,
        "bay_parent": f"{VERSION}/bay-native-parent.json", "isabella_parent": f"{SOURCE}/{api_file}",
        "units": f"{VERSION}/native-unit-inputs.json.gz", "files": verified,
        "reference": {"path": geometry_file, "url": geometry["file"], "sha256": geometry["sha256"],
                      "uncompressed_sha256": geometry["uncompressed_sha256"],
                      "boundary_year": 2026, "counties": geometry["counties"],
                      "partial_county_fips": ["26017", "26073"],
                      "review_id": "native-michigan-county-parents-20261109-02"},
    }
    output.mkdir(parents=True)
    for name, body in members.items():
        (output / name).write_bytes(body)
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps({"county_parents": 2, "unit_rows": len(units), "reference_counties": geometry["counties"],
                      "bay_native_ballots": bay["native_ballots_cast_columns"][0],
                      "isabella_native_ballots": election["ballotsCast"], "rates_enabled": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / VERSION)
    build(parser.parse_args().output)
