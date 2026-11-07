"""Reproduce selected Columbia County native counts without redistributing native documents."""

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261107-01"
DATA = f"data/participation-columbia-wisconsin-history/{VERSION}"
CODE = ("scripts/package-columbia-wisconsin-history.py", "scripts/test-package-columbia-wisconsin-history.py")
PINS = {
    "selected-observations.json": "567eb835105dca350f71a5579eceee5cea38bddd9200b4284286201cc214e1c6",
    "methodology-review.json": "0a71f27cc5c82abc61de2f052509d965d16a2be6564af17aa95cf0dd42cda409",
    "native-source-consistency.json": "093e447f97deb87f26db34829065613710b07bcbeda852d7c2dd310c365cf11e",
}
YEARS = (2024, 2026)
TOTALS = (35035, 27310)
CLOCKS = (("11/06/2024 12:25AM", "11/06/2024 12:29AM"),
          ("11/03/2026 10:26PM", "11/03/2026 11:00PM"))
HOUSE = "Representative in Congress District 6"
PRESIDENT = "President / Vice President"
UNSUPPORTED = (
    "qualified_precinct_geometry", "qualified_longitudinal_units", "qualified_unique_person_population",
    "qualified_individual_transitions", "qualified_demographic_turnout", "qualified_final_counts",
    "native_documents_redistributed", "personal_records_included",
)


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys), "Missing or unexpected selected fields")


def count(value):
    require(type(value) is int and value >= 0, "Invalid native count")
    return value


def review(snapshot, methods):
    exact(snapshot, ("elections",))
    require(methods["status"] == "qualified_selected_government_factual_counts_only"
            and all(methods[key] is False for key in UNSUPPORTED), "Unsupported qualification")
    require(len(snapshot["elections"]) == 2, "Incomplete two-election selection")
    summaries, contexts, ballot_rows, answer_rows = [], [], [], []
    for selected, year, total, clocks, pages, contest_count in zip(
        snapshot["elections"], YEARS, TOTALS, CLOCKS, ((75, 4), (81, 4)), (23, 21)
    ):
        exact(selected, ("scope", "observations", "source_receipts"))
        require(selected["scope"] == {
            "state_code": "WI", "county_name": "Columbia", "county_fips": "55021",
            "election_date": f"{year}-11-{'05' if year == 2024 else '03'}", "election_stage": "general",
        }, "Election/county scope changed")
        require(len(selected["observations"]) == 2 and len(selected["source_receipts"]) == 3,
                "Missing report or used-source provenance")
        receipts = selected["source_receipts"]
        require([r["file"] for r in receipts] == ["index.html", "precinct-summary.pdf", "election-summary.pdf"],
                "Missing source receipt")
        for receipt in receipts:
            common = {"file", "requested_url", "final_url", "observed_at_utc", "status", "bytes", "sha256", "headers"}
            extra = {"declared_report_links"} if receipt["file"] == "index.html" else {"declared_link"}
            exact(receipt, common | extra)
            require(receipt["status"] == 200 and count(receipt["bytes"]) > 0
                    and re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"]), "Invalid native source receipt")
            require(all(receipt[k].startswith("https://www.co.columbia.wi.us/columbiacounty/")
                        for k in ("requested_url", "final_url")), "Native source host changed")
            require(set(receipt["headers"]) <= {"Date", "Content-Type", "Content-Length", "Last-Modified", "ETag"},
                    "Private session or unexpected source headers")
        expected_labels = (["Precinct Summary Report", "Election Summary - Unofficial Results"] if year == 2024
                           else ["Precinct Summary", "Election Summary - Unofficial Results",
                                 "Outstanding Provisional Ballots Report"])
        links = receipts[0]["declared_report_links"]
        for link in links:
            exact(link, ("href", "text", "url"))
            require(isinstance(link["href"], str) and link["href"].startswith("/columbiacounty/")
                    and link["url"] == "https://www.co.columbia.wi.us" + link["href"],
                    "Changed declared source URL")
        require([link["text"] for link in links] == expected_labels
                and len({link["url"] for link in links}) == len(links),
                "Incomplete declared source chain")
        for receipt, declaration in zip(receipts[1:], links[:2]):
            require(receipt["declared_link"] == declaration
                    and receipt["requested_url"] == receipt["declared_link"]["url"],
                    "Changed declared source link")
        local, county = selected["observations"]
        for observation, clock, page_count, report, n_units in zip(
            (local, county), clocks, pages, ("precinct-summary.pdf", "election-summary.pdf"), (37, 1)
        ):
            exact(observation, ("source_report_clock_literal", "source_timezone", "status",
                                "page_count", "units", "receipt_key"))
            require(observation["status"] == "UNOFFICIAL RESULTS" and observation["source_timezone"] is None
                    and observation["source_report_clock_literal"] == clock
                    and observation["page_count"] == page_count and observation["receipt_key"] == report,
                    "Native clock/status/report scope changed")
            require(len(observation["units"]) == n_units
                    and len({u["native_label"] for u in observation["units"]}) == n_units, "Missing or duplicate native unit")
            for unit in observation["units"]:
                exact(unit, ("native_label", "ballots", "ballot_source_page", "contests"))
                require(isinstance(unit["native_label"], str)
                        and ((n_units == 1 and unit["native_label"] == "Columbia County")
                             or (n_units == 37 and unit["native_label"].startswith(("Town of ", "Village of ", "City of ")))),
                        "Unexpected reporting-unit identity")
                count(unit["ballots"])
                require(type(unit["ballot_source_page"]) is int and 1 <= unit["ballot_source_page"] <= page_count,
                        "Invalid native ballot page")
                ballot_rows.append({"year": year, "report": report, "native_unit": unit["native_label"],
                                    "ballots": unit["ballots"], "source_page": unit["ballot_source_page"],
                                    "source_clock": clock, "status": observation["status"]})
                require(unit["contests"], "Missing native contest vectors")
                for title, contest in unit["contests"].items():
                    exact(contest, ("native_title", "vote_for", "source_page", "answers", "native_reporting_units"))
                    require(title == contest["native_title"] and type(contest["vote_for"]) is int
                            and contest["vote_for"] == 1, "Changed contest title or vote-for scope")
                    require(type(contest["source_page"]) is int and 1 <= contest["source_page"] <= page_count,
                            "Invalid native contest page")
                    answers = contest["answers"]
                    require(answers and len({a["native_label"] for a in answers}) == len(answers),
                            "Missing or duplicate native candidate/answer")
                    for answer in answers:
                        exact(answer, ("native_label", "votes", "source_page"))
                        count(answer["votes"])
                        require(isinstance(answer["native_label"], str) and answer["native_label"]
                                and type(answer["source_page"]) is int and 1 <= answer["source_page"] <= page_count,
                                "Invalid native candidate/answer label or page")
                        answer_rows.append({"year": year, "report": report, "native_unit": unit["native_label"],
                                            "native_contest": title, "native_answer": answer["native_label"],
                                            "votes": answer["votes"], "source_page": answer["source_page"]})
                    require(sum(a["votes"] for a in answers) <= unit["ballots"], "Contest votes exceed ballots")
                    require((contest["native_reporting_units"] is None) is (n_units == 37),
                            "Native reporting control missing or invented")
        parent = county["units"][0]
        require(sum(u["ballots"] for u in local["units"]) == parent["ballots"] == total,
                "Native ballot control does not reconcile")
        require(len(parent["contests"]) == contest_count, "Missing county contests")
        vectors, members = {}, Counter()
        for unit in local["units"]:
            for title, contest in unit["contests"].items():
                require(title in parent["contests"], "Unknown local contest")
                require({a["native_label"] for a in contest["answers"]}
                        == {a["native_label"] for a in parent["contests"][title]["answers"]},
                        "Missing literal local candidate/answer, including zero votes")
                members[title] += 1
                vectors.setdefault(title, Counter()).update({a["native_label"]: a["votes"] for a in contest["answers"]})
        require(set(vectors) == set(parent["contests"]), "Incomplete local contest coverage")
        for title, contest in parent["contests"].items():
            require(dict(vectors[title]) == {a["native_label"]: a["votes"] for a in contest["answers"]},
                    "Local candidate/answer vector differs from county control")
            require(contest["native_reporting_units"] == {"reported": members[title], "total": members[title]},
                    "Native reporting membership does not reconcile")
        for title in ((PRESIDENT, HOUSE) if year == 2024 else (HOUSE,)):
            require(members[title] == 37, "Partial-county race cannot use a whole-county comparison")
            candidates = parent["contests"][title]["answers"]
            major = [[a["votes"] for a in candidates if a["native_label"].startswith(party + " ")]
                     for party in ("DEM", "REP")]
            require(all(len(x) == 1 for x in major), "Nonunique literal major-party comparison")
            d, r = (x[0] for x in major)
            require(d + r > 0, "Empty two-party denominator")
            contexts.append({
                "year": year, "native_contest": title, "county_ballots": total,
                "candidate_votes": sum(a["votes"] for a in candidates),
                "unclassified_ballot_minus_contest_votes": total - sum(a["votes"] for a in candidates),
                "candidates": candidates, "two_party_margin_pp": float(100 * Decimal(d - r) / Decimal(d + r)),
            })
        summaries.append({
            "year": year, "ballots": total, "native_local_reporting_units": 37,
            "native_contests": contest_count, "native_unit_contest_vectors": sum(members.values()),
            "local_report_clock": clocks[0], "county_report_clock": clocks[1],
            "source_timezone": None, "status": "UNOFFICIAL RESULTS",
        })
    current_margin = contexts[-1]["two_party_margin_pp"]
    summary = {
        "version": VERSION, "county_fips": "55021", "county_name": "Columbia", "state_code": "WI",
        "elections": summaries, "reported_ballot_count_change_2026_minus_2024": TOTALS[1] - TOTALS[0],
        "contest_context": contexts,
        "descriptive_comparisons": [
            {"baseline_contest": c["native_contest"], "baseline_year": 2024,
             "current_contest": HOUSE, "current_year": 2026,
             "two_party_margin_change_pp": current_margin - c["two_party_margin_pp"]}
            for c in contexts[:-1]
        ],
        "unsupported_estimates": {key: None for key in (
            "individual_switchers", "measured_staying_home", "original_coalition_absence",
            "new_or_returning_voter_identity", "demographic_turnout", "unique_person_N26",
            "precinct_cross_year_flows", "design_confidence_interval")},
        "methodology": methods,
    }
    return summary, ballot_rows, answer_rows


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def package(root=ROOT, output=None):
    inputs = {name: (root / DATA / name).read_bytes() for name in PINS}
    require(all(hashlib.sha256(inputs[name]).hexdigest() == digest for name, digest in PINS.items()),
            "Reviewed source changed; create a new immutable version")
    summary, ballots, answers = review(json.loads(inputs["selected-observations.json"]),
                                       json.loads(inputs["methodology-review.json"]))
    proofs = json.loads(inputs["native-source-consistency.json"])["reviews"]
    require(len(proofs) == 2 and [p["year"] for p in proofs] == list(YEARS), "Incomplete native qualification")
    require(all(p["status"] == "passed" and p["network_blocked_and_probed"] is True
                and p["reviewer_imported"] is False and p["pdfplumber_imported"] is False
                and p["all_observations_and_review_fields_match"] is True
                and p["source_receipts_verified"] == 3 and p["tamper_refusals"] == 7 for p in proofs),
            "Independent native qualification missing")
    require(sum(p["native_ballot_cells_verified"] for p in proofs) == len(ballots)
            and sum(p["native_candidate_answer_cells_verified"] for p in proofs) == len(answers),
            "Selected factual cells do not match native qualification")
    members = {f"{DATA}/{name}": raw for name, raw in inputs.items()}
    members.update({name: (root / name).read_bytes() for name in CODE})
    members.update({
        "results/history.json": encoded(summary), "results/native-ballots.csv": csv_bytes(ballots),
        "results/native-contest-vectors.csv": csv_bytes(answers),
        "REPRODUCTION.txt": (
            "Python >=3.9; standard library only. Extract preserving all paths.\n"
            "python3 scripts/test-package-columbia-wisconsin-history.py\n"
            "python3 scripts/package-columbia-wisconsin-history.py --output reproduced\n"
            "Every selected native ballot/candidate/answer and all six used-source receipts are included.\n"
            "This reproduces selected governmental facts, not fresh extraction of private native PDFs.\n\n"
            + "\n\n".join(summary["methodology"]["limits"]) + "\n"
        ).encode(),
    })
    inventory = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                 for name, raw in sorted(members.items())}
    members["checksums.json"] = encoded(inventory)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw, compresslevel=9)
    raw = stream.getvalue()
    metadata = {"version": VERSION, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "members": len(members), "native_ballot_cells": len(ballots),
                "native_candidate_answer_cells": len(answers)}
    outputs = {"history.json": members["results/history.json"],
               "native-ballots.csv": members["results/native-ballots.csv"],
               "native-contest-vectors.csv": members["results/native-contest-vectors.csv"],
               "complete-analysis.zip": raw, "archive.json": encoded(metadata)}
    destination = Path(output) if output else root / DATA / "output"
    for name, content in outputs.items():
        path = destination / name
        require(not path.exists() or path.read_bytes() == content, "Frozen output changed")
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        path = destination / name
        if not path.exists():
            path.write_bytes(content)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.root, args.output), indent=2))
