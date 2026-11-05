"""Review county-scoped Michigan 2026 native participation and House observations."""

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
from urllib.parse import unquote, urlsplit
import zipfile


BAY_HOUSE = "U.S. Representative 8th District"
BAY_CANDIDATES = ["DEM Kristen McDonald Rivet", "REP Thomas J. Smith",
                  "LIB C. Mia Pettus", "GRN Jim Casha", "WCP Kathy Goodwin",
                  "Write-In Totals"]
EDGES = [198, 238, 278, 318]
ISABELLA_HOUSE = "Representative in Congress 2nd District"
ISABELLA_CONTEST_ID = "01000000-c639-6905-0576-08df1d7ec4a8"
MODES = ["Election Day", "AV Counting Boards", "Early Voting"]
SHEETS = {
    "Summary Results": ["Office Name", "Contest ID", "Ballot Name", "Choice ID", "Party", "Total"],
    "Summary Results by Group": ["Office Name", "Contest ID", "Ballot Name", "Choice ID",
                                 "Party", "Group", "Total"],
    "Precinct Results": ["Precinct", "Office Name", "Contest ID", "Ballot Name", "Choice ID",
                         "Party", "Total"],
    "Precinct Results by Group": ["Precinct", "Office Name", "Contest ID", "Ballot Name",
                                  "Choice ID", "Party", "Group", "Total"],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(isinstance(value, str) and
            re.fullmatch(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)", value),
            "Missing, negative or malformed native integer")
    return int(value.replace(",", ""))


def pdf_cells(words, box):
    same_row = [word for word in words
                if abs((word[1] + word[3] - box[1] - box[3]) / 2) < 3
                and word[0] > 150]
    cells = []
    for edge in EDGES:
        values = [word[4] for word in same_row if abs(word[2] - edge) < 1]
        require(len(values) <= 1, "Duplicate native PDF numeric column")
        cells.append(number(values[0]) if values else None)
    require(len(same_row) == sum(value is not None for value in cells),
            "Unrecognized native PDF numeric position")
    return cells


def pdf_row(page, label):
    boxes = page.search_for(label)
    require(len(boxes) == 1, "Missing or ambiguous native PDF row: " + label)
    return pdf_cells(page.get_text("words"), boxes[0])


def bay_pdf_tables(raw, summary=False):
    import fitz

    participation, house = [], []
    current = None
    with fitz.open(stream=raw, filetype="pdf") as document:
        for ordinal, page in enumerate(document, 1):
            text = page.get_text()
            require(all(label in text for label in [
                "UNOFFICIAL RESULTS", "2026 General Election", "Bay County",
                "November 3, 2026"]), "Unreviewed Bay election identity")
            name = "Bay County" if summary else text.splitlines()[0]
            if "\nStatistics\n" in text:
                require(name not in {row["precinct"] for row in participation},
                        "Duplicate complete Bay native unit")
                current = name
                registered = pdf_row(page, "Registered Voters - Total")
                ballots = pdf_row(page, "Ballots Cast - Total")
                require(registered[0] is not None and registered[1:] == [None] * 3,
                        "Unexpected Bay registration columns")
                require(None not in ballots and ballots[0] == sum(ballots[1:]),
                        "Incomplete or inconsistent native ballot modes")
                printed = pdf_row(page, "Ballots Cast - Blank") if not summary else None
                if printed is not None:
                    require(None not in printed and printed[0] == sum(printed[1:])
                            and all(a <= b for a, b in zip(printed, ballots)),
                            "Inconsistent blank-ballot columns")
                rates = re.findall(r"Voter Turnout - Total\n([0-9]+\.[0-9]{2})%", text)
                require(len(rates) == 1 and registered[0] > 0 and
                        math.isclose(float(rates[0]), 100 * ballots[0] / registered[0],
                                     rel_tol=0, abs_tol=.005000001),
                        "Native printed participation percentage differs")
                participation.append(dict(precinct=name, source_pdf_page=ordinal,
                    registered_voters_total=registered[0], ballots=ballots, blank=printed,
                    native_turnout_percent=rates[0]))
            require(current == name, "Orphan or reordered Bay report page")
            titles = page.search_for(BAY_HOUSE)
            if not titles:
                continue
            require(len(titles) == 1 and name not in {r["precinct"] for r in house},
                    "Duplicate Bay House section")
            endings = [box for box in page.search_for("Write-In Totals")
                       if box.y0 > titles[0].y1]
            require(bool(endings), "Missing House write-in row")
            end = min(endings, key=lambda box: box.y0)
            words = page.get_text("words")
            left = sorted((word for word in words if word[0] < 150
                           and word[1] > titles[0].y1 and word[1] <= end.y1),
                          key=lambda word: (word[1], word[0]))
            labels = []
            for word in left:
                if not labels or abs(word[1] - labels[-1][0]) >= 1:
                    labels.append((word[1], [word]))
                else:
                    labels[-1][1].append(word)
            require([" ".join(w[4] for w in group) for _, group in labels]
                    == ["Vote For 1"] + BAY_CANDIDATES,
                    "Unexpected complete House candidate inventory")
            counts = {}
            for label, (_, group) in zip(BAY_CANDIDATES, labels[1:]):
                box = (min(w[0] for w in group), min(w[1] for w in group),
                       max(w[2] for w in group), max(w[3] for w in group))
                values = pdf_cells(words, box)
                require(None not in values and values[0] == sum(values[1:]),
                        "Incomplete or inconsistent House candidate modes")
                counts[label] = values
            house.append(dict(precinct=name, source_pdf_page=ordinal, candidates=counts))
    require(len(participation) == len(house) > 0
            and {r["precinct"] for r in participation} == {r["precinct"] for r in house},
            "Incomplete Bay participation/House unit inventory")
    return participation, house


def review_bay(summary, detail):
    summary_participation, summary_house = summary
    participation, house = detail
    require(len(summary_participation) == len(summary_house) == 1,
            "Unexpected county summary inventory")
    require(len(participation) == len(house)
            == len({row["precinct"] for row in participation})
            == len({row["precinct"] for row in house}) > 0,
            "Duplicate or incomplete native precinct inventory")
    require({r["precinct"] for r in participation} == {r["precinct"] for r in house},
            "Bay literal unit identities differ")
    county, total_house = summary_participation[0], summary_house[0]["candidates"]
    require(sum(r["registered_voters_total"] for r in participation)
            == county["registered_voters_total"], "Bay county registrations differ")
    require([sum(r["ballots"][i] for r in participation) for i in range(4)]
            == county["ballots"], "Bay county ballot modes differ")
    require(all(set(r["candidates"]) == set(total_house) for r in house),
            "Bay candidate inventories differ")
    for candidate in total_house:
        require([sum(r["candidates"][candidate][i] for r in house) for i in range(4)]
                == total_house[candidate], "Bay county candidate modes differ")
    counts, results = [], []
    by_name = {r["precinct"]: r for r in house}
    for row in participation:
        name = row["precinct"]
        common = dict(year=2026, state_code="MI", county_code="bay", county="Bay County",
            precinct=name, source_row_id="bay:pdf:" + str(row["source_pdf_page"]),
            native_precinct_id="", native_reporting_status="UNOFFICIAL RESULTS",
            maps_approved=False)
        counts.append(dict(common, source_pdf_page=row["source_pdf_page"],
            registered_voters_total=row["registered_voters_total"],
            ballots_cast_total=row["ballots"][0], ballots_cast_election_day=row["ballots"][1],
            ballots_cast_absentee_counting_board=row["ballots"][2],
            ballots_cast_early_voting=row["ballots"][3], ballots_cast_blank=row["blank"][0],
            native_turnout_percent=row["native_turnout_percent"], turnout_rate="",
            quality_flags=json.dumps(["provisional", "native_unit_scope_not_reconciled",
                                      "registration_components_not_defined"])))
        candidates = by_name[name]["candidates"]
        total = sum(v[0] for v in candidates.values())
        require(total <= row["ballots"][0], "House votes exceed native ballots")
        results.append(dict(common, source_pdf_page=by_name[name]["source_pdf_page"],
            contest_id="MI-8", contest=BAY_HOUSE, total_votes=total,
            democratic_votes=candidates[BAY_CANDIDATES[0]][0],
            republican_votes=candidates[BAY_CANDIDATES[1]][0],
            other_votes=sum(candidates[c][0] for c in BAY_CANDIDATES[2:]),
            candidates_by_native_mode=json.dumps(candidates, separators=(",", ":"))))
    return counts, results


def integer(value):
    require(type(value) in (int, float) and math.isfinite(value)
            and value >= 0 and value == int(value), "Missing or nonintegral native count")
    return int(value)


def english(values):
    texts = [row["text"] for row in values if row["languageId"] == "en"]
    require(len(texts) == 1 and isinstance(texts[0], str), "Ambiguous native English name")
    return texts[0]


def workbook_tables(raw):
    import openpyxl

    tables = {}
    workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        require(workbook.sheetnames == list(SHEETS), "Unexpected complete workbook sheets")
        for name, headers in SHEETS.items():
            native = list(workbook[name].values)
            require(list(native[0][:len(headers)]) == headers
                    and all(all(v is None for v in row[len(headers):]) for row in native),
                    "Unreviewed workbook columns")
            rows = {tuple(row[:len(headers) - 1]): integer(row[len(headers) - 1])
                    for row in native[1:]}
            require(len(rows) == len(native) - 1, "Duplicate workbook observation key")
            tables[name] = rows
    finally:
        workbook.close()
    for source, target, grouped in [
        ("Summary Results by Group", "Summary Results", True),
        ("Precinct Results by Group", "Precinct Results", True),
        ("Precinct Results", "Summary Results", False),
    ]:
        totals, modes = {}, {}
        for key, value in tables[source].items():
            parent = key[:-1] if grouped else key[1:]
            totals[parent] = totals.get(parent, 0) + value
            if grouped:
                modes.setdefault(parent, set()).add(key[-1])
        require(totals == tables[target] and
                (not grouped or all(group == set(MODES) for group in modes.values())),
                "Incomplete workbook unit/mode/county reconciliation")
    return tables


def option_vectors(options, groups):
    output = {}
    for option in options:
        key = (english(option["name"]), option["nativeId"], english(option["party"]["name"]))
        require(option["id"] not in output and
                key not in [row["key"] for row in output.values()], "Duplicate candidate identity")
        by_group = {}
        for group in option["groupResults"]:
            group_id = group["groupId"]
            require(group_id in groups and group_id not in by_group
                    and english(group["groupName"]) == groups[group_id],
                    "Unreviewed or duplicate candidate voting mode")
            by_group[group_id] = integer(group["voteCount"])
        require(by_group.keys() == groups.keys(), "Incomplete candidate voting modes")
        total = integer(option["voteCount"])
        require(sum(by_group.values()) == total, "Candidate voting modes differ from total")
        output[option["id"]] = dict(key=key, party=option["party"]["abbreviation"],
            counts=[total] + [by_group[next(k for k, v in groups.items() if v == mode)]
                              for mode in MODES])
    return output


def review_isabella(data, full, tables):
    election = data["election"]
    require(election["electionDate"] == "2026-11-03"
            and english(election["name"]) == "2026 Isabella County November General Election"
            and election["id"] == "01000000-85aa-a19e-3fe4-08df1d7ec163"
            and election["jurisdictionId"] == data["jurisdiction"]["id"]
                == "01000000-3685-de5b-d9aa-08dc7c0a200b"
            and election["isOfficialResults"] is False
            and election["isProduction"] is True
            and data["ballotItemWithBreakdown"] is None
            and all(full[key] == value for key, value in data.items()
                    if key != "ballotItemWithBreakdown"),
            "Unreviewed or inconsistent election/publication snapshots")
    precincts = {row["id"]: row for row in data["precincts"]}
    turnout = {row["id"]: row for row in data["voterTurnout"]}
    require(len(precincts) == len(data["precincts"]) == len(turnout)
            == len(data["voterTurnout"]) > 0 and precincts.keys() == turnout.keys()
            and len({english(row["name"]) for row in precincts.values()}) == len(precincts),
            "Duplicate or incomplete native precinct identities")
    require(election["map"]["enabled"] is False and
            all(row["mapFeatureId"] is None and row["isVirtual"] is False
                and row["reportingStatus"] == 4 for row in precincts.values()),
            "Unreviewed native geometry, virtual scope or reporting statuses")
    groups = {row["groupId"]: english(row["groupName"]) for row in election["countGroups"]}
    require(len(groups) == len(election["countGroups"]) == 3
            and set(groups.values()) == set(MODES), "Unreviewed native count groups")
    matches = [row for row in data["ballotItems"] if row["id"] == ISABELLA_CONTEST_ID]
    require(len(matches) == 1 and english(matches[0]["name"]) == ISABELLA_HOUSE
            and english(matches[0]["voteFor"]) == "Vote for 1", "Unreviewed exact House contest")
    summary = matches[0]
    breakdown = full["ballotItemWithBreakdown"]
    require(breakdown["id"] == summary["id"] and
            all(breakdown[key] == summary[key] for key in
                ["name", "voteFor", "voteTotal", "summaryResults", "reportingStatus"]),
            "House summary and breakdown snapshots differ")
    expected = option_vectors(summary["summaryResults"]["ballotOptions"], groups)
    require(sum(v["counts"][0] for v in expected.values()) == integer(summary["voteTotal"]),
            "House summary options differ from vote total")
    details = breakdown["breakdownResults"]
    require(len(details) == integer(breakdown["breakdownResultCount"])
            == integer(summary["reportingStatus"]["totalUnits"])
            == integer(summary["reportingStatus"]["reportingUnits"])
            == len({row["precinct"]["id"] for row in details}), "Incomplete native House units")
    house_rows = {}
    for row in details:
        code = row["precinct"]["id"]
        require(code in precincts and row["precinct"] == precincts[code]
                and row["parentBallotItemId"] == ISABELLA_CONTEST_ID,
                "Conflicting native House unit identity")
        vectors = option_vectors(row["ballotOptions"], groups)
        require(vectors.keys() == expected.keys() and
                all(vectors[key]["key"] == expected[key]["key"] for key in expected)
                and sum(v["counts"][0] for v in vectors.values()) == integer(row["voteTotal"]),
                "Incomplete native precinct candidate vectors")
        house_rows[code] = vectors
    for candidate, option in expected.items():
        require([sum(rows[candidate]["counts"][i] for rows in house_rows.values())
                 for i in range(4)] == option["counts"], "House unit/mode totals differ")
    book_summary = tables["Summary Results"]
    book_groups = tables["Summary Results by Group"]
    book_precincts = tables["Precinct Results"]
    book_detail = tables["Precinct Results by Group"]
    house_keys = {(key[2], key[3], key[4]) for key in book_summary
                  if key[:2] == (ISABELLA_HOUSE, "6")}
    candidate_keys = {option["key"] for option in expected.values()}
    extra_keys = {("Ballots Cast", "", None), ("Over Votes", "", None), ("Under Votes", "", None)}
    require(house_keys == candidate_keys | extra_keys
            and {key[0] for key in book_precincts if key[1:3] == (ISABELLA_HOUSE, "6")}
                == {english(precincts[code]["name"]) for code in house_rows},
            "Workbook House candidate/unit inventory differs")
    for code, vectors in [(None, expected)] + list(house_rows.items()):
        prefix = () if code is None else (english(precincts[code]["name"]),)
        totals, modes = (book_summary, book_groups) if code is None else (book_precincts, book_detail)
        for option in vectors.values():
            key = prefix + (ISABELLA_HOUSE, "6") + option["key"]
            require(totals[key] == option["counts"][0] and
                    [modes[key + (mode,)] for mode in MODES] == option["counts"][1:],
                    "Complete workbook/API House vectors differ")
        ballot_key = prefix + (ISABELLA_HOUSE, "6", "Ballots Cast", "", None)
        invalid = [prefix + (ISABELLA_HOUSE, "6", name, "", None)
                   for name in ["Over Votes", "Under Votes"]]
        for mode in [None] + MODES:
            values = totals if mode is None else modes
            suffix = () if mode is None else (mode,)
            candidate_total = sum(values[prefix + (ISABELLA_HOUSE, "6") + option["key"] + suffix]
                                  for option in vectors.values())
            require(candidate_total + sum(values[key + suffix] for key in invalid)
                    == values[ballot_key + suffix], "Workbook House ballot accounting differs")
    participation, results, unmatched, differences = [], [], [], []
    for code, native in precincts.items():
        observation = turnout[code]
        name = english(native["name"])
        require(observation["precinctName"] == name, "Native participation UUID/name differs")
        ballots = integer(observation["ballotsCast"])
        registered = integer(observation["voterRegistration"])
        require(integer(observation["voterTurnout"]) == ballots,
                "Unreviewed native turnout count field")
        common = dict(year=2026, state_code="MI", county_code="isabella", county="Isabella County",
            precinct=name, source_row_id="isabella:uuid:" + code, native_precinct_id=code,
            native_reporting_status=native["reportingStatus"], maps_approved=False)
        flags = ["provisional", "registration_components_not_defined"]
        if registered == 0:
            flags.append("zero_native_registration")
        if code not in house_rows:
            flags.append("absent_from_house_scope")
            unmatched.append(dict(common, ballots_cast_total=ballots, registered_voters_total=registered))
        else:
            vectors = house_rows[code]
            candidates = {english(o["name"]): vectors[o["id"]]["counts"]
                          for o in summary["summaryResults"]["ballotOptions"]}
            prefix = (name, ISABELLA_HOUSE, "6")
            house_ballots = book_precincts[prefix + ("Ballots Cast", "", None)]
            if house_ballots != ballots:
                flags.append("house_ballots_differ_from_election_participation")
                differences.append(dict(native_precinct_id=code, precinct=name,
                    election_ballots=ballots, house_scope_ballots=house_ballots))
            results.append(dict(common, contest_id="MI-2", contest=ISABELLA_HOUSE,
                total_votes=sum(option["counts"][0] for option in vectors.values()),
                democratic_votes=sum(o["counts"][0] for o in vectors.values() if o["party"] == "DEM"),
                republican_votes=sum(o["counts"][0] for o in vectors.values() if o["party"] == "REP"),
                other_votes=sum(o["counts"][0] for o in vectors.values()
                                if o["party"] not in {"DEM", "REP"}),
                house_scope_ballots=house_ballots,
                over_votes=book_precincts[prefix + ("Over Votes", "", None)],
                under_votes=book_precincts[prefix + ("Under Votes", "", None)],
                candidates_by_native_mode=json.dumps(candidates, separators=(",", ":"))))
        participation.append(dict(common, registered_voters_total=registered,
            ballots_cast_total=ballots, native_voter_turnout_count=observation["voterTurnout"],
            turnout_rate="", quality_flags=json.dumps(flags)))
    require(sum(row["registered_voters_total"] for row in participation)
                == integer(election["totalVoters"])
            and sum(row["ballots_cast_total"] for row in participation)
                == integer(election["ballotsCast"]), "Native election participation totals differ")
    audit = dict(precincts=len(precincts), house_units=len(house_rows),
        house_votes=integer(summary["voteTotal"]),
        house_scope_ballots=book_summary[(ISABELLA_HOUSE, "6", "Ballots Cast", "", None)],
        ballots=integer(election["ballotsCast"]), registered_voters=integer(election["totalVoters"]),
        native_as_of=election["asOf"], native_publish_version_id=election["publishVersionId"],
        workbook_rows={name: len(rows) for name, rows in tables.items()},
        all_workbook_options_units_and_modes_reconcile=True,
        complete_api_house_vectors_and_workbook_agree=True,
        house_ballot_scope_differences=differences, absent_from_house_scope=unmatched,
        native_map_enabled=False, maps_approved=False, rates_available=False)
    return participation, results, unmatched, audit


def build(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable snapshot overwrite")
    receipts = json.loads((source / "sources.json").read_text())
    factual = ["official-bay-general-summary-pdf", "official-bay-general-precinct-pdf",
               "official-isabella-summary-party-pdf", "official-isabella-summary-contest-pdf",
               "official-isabella-summary-pdf", "official-isabella-all-results-xlsx"]

    def original(receipt, parent=source):
        raw = gzip.decompress((parent / receipt["file"]).read_bytes())
        require(receipt["status"] == 200 and len(raw) == receipt["bytes"]
                and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Original source byte/hash/status mismatch")
        return raw

    originals = {key: original(receipts[key]) for key in factual}
    payloads = {}
    for folder in ["dashboard-network", "dashboard-followup-network"]:
        network = json.loads((source / folder / "responses.json").read_text())
        for receipt in network:
            require(receipt["url"].startswith(
                "https://app.enhancedvoting.com/results/public/api/elections/"
                "isabella-county-mi/2026NovemberGeneral/"), "Unreviewed native API URL")
            require(receipt["url"] not in payloads, "Duplicate native API snapshot URL")
            payloads[receipt["url"]] = json.loads(original(receipt, source / folder))
    api = ("https://app.enhancedvoting.com/results/public/api/elections/"
           "isabella-county-mi/2026NovemberGeneral/data")
    data, full = payloads[api], payloads[api + "/ballot-item/" + ISABELLA_CONTEST_ID]
    declarations = data["election"]["publicReportCategories"]
    filenames = {value for category in declarations for report in category["reports"]
                 for value in report.values() if isinstance(value, str)
                 and value.lower().endswith((".pdf", ".xlsx"))}
    require(len(filenames) == 4 and
            {unquote(urlsplit(receipts[key]["url"]).path.rsplit("/", 1)[-1])
             for key in factual[2:]} == filenames,
            "Report originals do not match actual native declarations")
    summary = bay_pdf_tables(originals[factual[0]], True)
    detail = bay_pdf_tables(originals[factual[1]])
    bay_counts, bay_results = review_bay(summary, detail)
    tables = workbook_tables(originals[factual[-1]])
    mi_counts, mi_results, unmatched, isabella = review_isabella(data, full, tables)
    require(len(bay_counts) == 35 and len(mi_counts) == 28 and len(mi_results) == 24,
            "Complete acquired county inventory differs")
    import fitz
    with fitz.open(stream=originals[factual[0]], filetype="pdf") as document:
        counters = re.findall(r"Election Day Precincts Reporting\n([0-9]+ of [0-9]+)\n",
                              document[0].get_text())
    require(counters == ["43 of 43"], "Unreviewed native Bay reporting counter")
    audit = dict(year=2026, state_code="MI", scope="Bay and Isabella county sources only",
        participation_rows=len(bay_counts) + len(mi_counts),
        house_rows=len(bay_results) + len(mi_results), maps_approved=False, rates_available=False,
        bay=dict(statistics_sections=len(bay_counts), house_sections=len(bay_results),
            native_election_day_reporting=counters[0], reporting_counter_scope_reconciled=False,
            registered_voters=sum(row["registered_voters_total"] for row in bay_counts),
            ballots=sum(row["ballots_cast_total"] for row in bay_counts),
            house_votes=sum(row["total_votes"] for row in bay_results),
            all_ballot_and_house_candidate_modes_reconcile_to_independent_summary=True),
        isabella=isabella, factual_originals=len(factual) + len(payloads),
        discovery_originals_retained_separately=len(receipts) - len(factual),
        license_note="Official public aggregate election records; no separate open-data license "
            "was found in the acquired declarations. Native vendor/UI assets are not redistributed.",
        next_action="Acquire exact-election boundaries and explicit native crosswalks, clarify "
            "Bay's 43 reporting counter versus 35 report sections, Isabella's 22-ballot scope "
            "difference, and registration definitions. Continue remaining Michigan counties "
            "and other 2026 jurisdictions; do not infer missing returns, geometry or rates.")
    output.mkdir(parents=True)
    (output / "source/originals").mkdir(parents=True)
    for key in factual:
        shutil.copyfile(source / receipts[key]["file"], output / "source" / receipts[key]["file"])
    shutil.copyfile(source / "sources.json", output / "source/sources.json")
    for folder in ["dashboard-network", "dashboard-followup-network"]:
        shutil.copytree(source / folder, output / "source" / folder)
    shutil.copyfile(__file__, output / "review.py")
    for name, rows in [("precinct-participation.csv", bay_counts + mi_counts),
                       ("precinct-results.csv", bay_results + mi_results),
                       ("unmatched-precincts.csv", unmatched)]:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with (output / name).open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    for name, rows in tables.items():
        filename = "isabella-" + name.lower().replace(" ", "-") + ".csv"
        with (output / filename).open("w", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(SHEETS[name])
            writer.writerows([*key, value] for key, value in rows.items())
    shutil.copyfile(source / receipts[factual[-1]]["file"], output / "original-isabella-results.xlsx.gz")
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
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.archive), indent=2))
