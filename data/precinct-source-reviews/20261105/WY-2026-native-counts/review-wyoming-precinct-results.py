"""Reconcile 2026 Wyoming native House precinct categories and separate ballots."""

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import fitz


COUNTIES = ["Albany", "Big Horn", "Campbell", "Carbon", "Converse", "Crook", "Fremont",
            "Goshen", "Hot Springs", "Johnson", "Laramie", "Lincoln", "Natrona",
            "Niobrara", "Park", "Platte", "Sheridan", "Sublette", "Sweetwater",
            "Teton", "Uinta", "Washakie", "Weston"]
CANONICAL = {name.replace(" ", ""): name for name in COUNTIES}
CATEGORIES = ["Chuck Gray (R)", "Lisa Kinney (D)", "Shawn Johnson (L)",
              "Jeffrey Haggit (C)", "Write-Ins", "Overvotes", "Undervotes"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compact(value):
    return "".join(value.split())


def rows_for(package, sources, name):
    raw = gzip.decompress((package / "source-package/originals/2026" / (name + ".gz")).read_bytes())
    require(hashlib.sha256(raw).hexdigest() == sources["2026/" + name]["sha256"], "Source hash mismatch")
    cache = package / "recovered-text" / (name + ".words.json.gz")
    cached = json.loads(gzip.decompress(cache.read_bytes())) if cache.exists() else None
    result = []
    with fitz.open(stream=raw, filetype="pdf") as document:
        require(cached is None or len(cached) == len(document), "Incomplete recovered page set")
        for index, page in enumerate(document):
            words = cached[index]["words"] if cached else page.get_text("words")
            if cached:
                require(cached[index]["rotation"] == page.rotation, "Cached source rotation mismatch")
            rows = {}
            for word in words:
                box = fitz.Rect(word[:4]) * page.rotation_matrix
                y = (box.y0 + box.y1) / 2
                key = next((key for key in rows if abs(key - y) < 2), y)
                rows.setdefault(key, []).append((box.x0, word[4]))
            result.append([" ".join(text for _, text in sorted(row))
                           for _, row in sorted(rows.items())])
    return result


def numeric_tail(row, size):
    parts = row.split()
    if len(parts) < size or not all(re.fullmatch(r"(?:\d+|[1-9]\d{0,2}(?:,\d{3})+)", item)
                                     for item in parts[-size:]):
        return None
    return " ".join(parts[:-size]), [int(item.replace(",", "")) for item in parts[-size:]]


def validate_header(rows, name, house):
    joined = compact(" ".join(rows))
    require("November3,2026" in joined, name + " wrong election")
    if house:
        require(all(text in joined for text in [
            "UnitedStatesRepresentative", "ChuckLisaShawnJeffrey",
            "Gray(R)Kinney(D)Johnson(L)Haggit(C)", "Write-InsOvervotesUndervotes"]),
            name + " unexpected House categories")
    else:
        require("TotalBallotsCast" in joined, name + " wrong ballot table")


def parse_precinct_pages(pages, name, house):
    found, totals, source_pages = {}, [], []
    for number, rows in enumerate(pages, 1):
        if house and not any("UnitedStatesRepresentative" in compact(row) for row in rows):
            continue
        validate_header(rows, name, house)
        starts = [index for index, row in enumerate(rows)
                  if row == "Precinct" or row.startswith("Precinct ")]
        require(len(starts) == 1, name + " ambiguous precinct header")
        for row in rows[starts[0] + 1:]:
            if compact(row) in {"PrecinctsContinue", "onNextPage"} or re.fullmatch(r"Page\d+of\d+", compact(row)):
                continue
            parsed = numeric_tail(row, 7 if house else 1)
            require(parsed is not None, name + " unrecognized native table row: " + row)
            label, values = parsed
            require(label, name + " missing native precinct label")
            if label == "Total":
                totals.append(values)
            else:
                require(label not in found and not totals, name + " duplicate/out-of-order precinct " + label)
                found[label] = dict(values=values, page=number)
        source_pages.append(number)
    require(found and len(totals) == 1, name + " incomplete native table")
    return found, totals[0], source_pages


def parse_statewide_pages(pages, name, house):
    found, totals = {}, []
    for number, rows in enumerate(pages, 1):
        if house and not any("UnitedStatesRepresentative" in compact(row) for row in rows):
            continue
        validate_header(rows, name, house)
        require("CountiesReporting:23of23" in compact(" ".join(rows)), "Incomplete county reporting")
        for index, row in enumerate(rows):
            parsed = numeric_tail(row, 7 if house else 1)
            if not parsed:
                continue
            label, values = parsed
            if compact(label) in CANONICAL:
                county = CANONICAL[compact(label)]
                require(county not in found, "Duplicate statewide county")
                found[county] = dict(values=values, page=number, native_label=label)
            elif label == "Total" or (not label and index and rows[index - 1] == "Total"):
                totals.append(values)
    require(set(found) == set(COUNTIES) and len(totals) == 1, "Incomplete statewide table")
    require([sum(item["values"][i] for item in found.values()) for i in range(len(totals[0]))]
            == totals[0], "Statewide county/category totals do not reconcile")
    return found, totals[0]


def reconcile(package):
    checks = json.loads((package / "checksums.json").read_text())
    require({p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
            == set(checks) | {"checksums.json"}, "Incomplete recovery package")
    for name, receipt in checks.items():
        raw = (package / name).read_bytes()
        require(len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Changed recovery package: " + name)
    sources = json.loads((package / "source-package/sources.json").read_text())
    state_name = "2026_General_Statewide_Candidates_Summary.pdf"
    ballot_name = "2026_General_Statewide_Total_Ballots_Cast_Summary.pdf"
    statewide, state_vector = parse_statewide_pages(rows_for(package, sources, state_name), state_name, True)
    ballots, state_ballots = parse_statewide_pages(rows_for(package, sources, ballot_name), ballot_name, False)
    require(sum(state_vector) == state_ballots[0], "Statewide categories and ballots differ")
    proof, normalized, conflicts, candidate_conflicts = [], [], [], []
    for county in COUNTIES:
        name = "2026_" + county.replace(" ", "_") + "_County_General_PbP.pdf"
        ballot_name = name.replace(".pdf", "_TBC.pdf")
        candidate, vector, pages = parse_precinct_pages(rows_for(package, sources, name), name, True)
        separate, ballot_total, ballot_pages = parse_precinct_pages(
            rows_for(package, sources, ballot_name), ballot_name, False)
        require(candidate.keys() == separate.keys(), county + " precinct identifier sets differ")
        summed = [sum(item["values"][i] for item in candidate.values()) for i in range(7)]
        require(summed == vector, county + " precinct/county candidate totals differ")
        if vector != statewide[county]["values"]:
            candidate_conflicts.append(dict(county=county, precinct_and_printed_county_vector=vector,
                statewide_county_vector=statewide[county]["values"],
                delta_precinct_minus_state=[a-b for a, b in zip(vector, statewide[county]["values"])]))
        native_ballot_sum = sum(item["values"][0] for item in separate.values())
        require(native_ballot_sum == sum(vector) == ballots[county]["values"][0],
                county + " precinct/state ballot totals differ")
        if native_ballot_sum != ballot_total[0]:
            conflicts.append(dict(county=county, precinct_sum=native_ballot_sum,
                                  printed_county_total=ballot_total[0]))
        for precinct, item in candidate.items():
            require(sum(item["values"]) == separate[precinct]["values"][0],
                    county + " " + precinct + " category sum differs from separate ballots")
            normalized.append(dict(year=2026, state_code="WY", county=county, precinct=precinct,
                **dict(zip(CATEGORIES, item["values"])), ballots=separate[precinct]["values"][0],
                registered_voters=None, turnout_rate=None,
                candidate_vector_matches_statewide_county=vector == statewide[county]["values"],
                candidate_source="2026/" + name, candidate_source_sha256=sources["2026/"+name]["sha256"],
                candidate_page=item["page"], ballot_source="2026/" + ballot_name,
                ballot_source_sha256=sources["2026/"+ballot_name]["sha256"],
                ballot_page=separate[precinct]["page"]))
        proof.append(dict(county=county, precincts=len(candidate), candidate_pages=pages,
            ballot_pages=ballot_pages, category_vector=vector, precinct_ballots=native_ballot_sum,
            printed_county_ballots=ballot_total[0], statewide_county_vector=statewide[county]["values"],
            candidate_vectors_match_state=vector == statewide[county]["values"],
            all_precinct_category_vectors_equal_separate_ballots=True))
    result = dict(state_code="WY", year=2026, counties=proof, units=len(normalized),
        statewide_category_vector=state_vector, category_labels=CATEGORIES,
        statewide_ballots=state_ballots[0], candidate_write_in_votes=sum(state_vector[:5]),
        printed_ballot_conflicts=conflicts, candidate_county_state_conflicts=candidate_conflicts,
        geometry_approved=False, maps_approved=False, turnout_rates_available=False,
        method="Native physical PDF rows; source-bound glyph recovery where required; exact native "
               "precinct labels; seven House categories independently match separate ballot counts. "
               "County/state candidate conflicts are preserved, not repaired or geographically allocated.")
    return result, normalized


def review_followup(followup, result):
    sources = json.loads((followup / "sources.json").read_text())
    for name, receipt in sources.items():
        raw = gzip.decompress((followup / (name + ".gz")).read_bytes())
        require(len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Changed independent county original")
    review = json.loads((followup / "visual-review.json").read_text())
    require(review["method"] == "direct_rendered_page_review"
            and review["source_sha256"] == sources[review["source"]]["sha256"]
            and review["literal_election_date"] == "November 3, 2026"
            and review["literal_county"] == "Washakie County, WY"
            and review["literal_office"] == "UNITED STATES REPRESENTATIVE"
            and review["page"] == 1, "Missing exact independent county visual review")
    native = next(county for county in result["counties"] if county["county"] == "Washakie")
    require(review["category_vector"] == native["statewide_county_vector"]
            and review["ballots_cast"] == native["precinct_ballots"]
            and sum(review["category_vector"]) == review["ballots_cast"],
            "Independent county summary does not match statewide/ballot counts")
    return dict(visual_review=review, county_summary_confirms_statewide=True,
                precinct_category_conflict_still_unresolved=True)


def build_review(package, followup, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable review overwrite")
    result, rows = reconcile(package)
    result["washakie_independent_followup"] = review_followup(followup, result)
    output.mkdir(parents=True)
    shutil.copytree(package, output / "native-text-review")
    shutil.copytree(followup, output / "independent-washakie-followup")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "counts-review.json").write_text(json.dumps(result, indent=2) + "\n")
    with (output / "precinct-counts.csv").open("w") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(output).as_posix())
                item.external_attr = 0o644 << 16
                target.writestr(item, path.read_bytes())
    return dict(units=result["units"], statewide_ballots=result["statewide_ballots"],
        candidate_county_state_conflicts=result["candidate_county_state_conflicts"],
        archive_bytes=archive.stat().st_size, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["recovery", "followup", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_review(args.recovery, args.followup, args.output, args.archive), indent=2))
