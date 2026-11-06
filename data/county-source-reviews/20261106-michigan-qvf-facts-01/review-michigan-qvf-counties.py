"""Reproduce native Michigan QVF observations without inventing tabulator totals."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


ELECTION = "2026 November General Election - Tuesday, November 3, 2026"
DEFINITION = "https://www.michigan.gov/sos/elections/election-results-and-data/voter-participation-dashboard"
REPORT = "https://app.powerbigov.us/view?r=eyJrIjoiMTk3MjM4ZWQtMTlkZi00N2QxLTk5ZTktODdhYjk3YTVmMzk3IiwidCI6ImQ1ZmI3MDg3LTM3NzctNDJhZC05NjZhLTg5MmVmNDcyMjVkMSJ9"
FIELDS = (
    "Min(expr.Table.M_Voter_Turnout)",
    "Min(expr.COUNTY_AV_BALLOT_COUNT.M_TotalAVBallotsReturned)",
    "Min(expr.Table.M_Display_County)",
    "Min(expr.COUNTY_IN_PERSON_EV_VOTE_COUNT.M_Ballots_Cast_duringEV_SoFar)",
    "Min(expr.COUNTY_AV_APP_COUNT.M_PVBM)",
    "Min(expr.COUNTY_IN_PERSON_ED_VOTE_COUNT.M_Total_In_Person_ED_Votes)",
    "Min(expr.COUNTY_IN_PERSON_ED_VOTE_COUNT.M_Total_Ballots)",
)
PROPERTIES = (
    "M_Voter_Turnout", "M_TotalAVBallotsReturned", "M_Display_County",
    "M_Ballots_Cast_duringEV_SoFar", "M_PVBM", "M_Total_In_Person_ED_Votes",
    "M_Total_Ballots",
)
CLOCK = re.compile(r"Last updated: [A-Z][a-z]+ \d{2}, \d{4} \d{2}:\d{2}:\d{2} [AP]M")
PROGRAM = "review-michigan-qvf-counties.py"
TEST = "test_review_michigan_qvf_counties.py"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def packets(payload):
    for result in payload.get("results", []):
        data = result.get("result", {}).get("data")
        if data:
            yield data


def tree(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from tree(item)
    elif isinstance(value, list):
        for item in value:
            yield from tree(item)


def number(value):
    require(not isinstance(value, bool), "Boolean is not a native count")
    if isinstance(value, int):
        require(value >= 0, "Negative native count")
        return value
    require(isinstance(value, str), "Unexpected native count type")
    if re.fullmatch(r"[0-9]+L", value):
        return int(value[:-1])
    if re.fullmatch(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)", value):
        return int(value.replace(",", ""))
    return None


def display(value):
    numeric = number(value)
    return format(numeric, ",") if numeric is not None else value.strip("'")


def mode_status(value):
    if number(value) is not None:
        return "reported_numeric"
    return {"No data available": "source_no_data_available",
            "Less than 10": "source_suppressed_less_than_10"}.get(
                value.strip("'"), "other_source_non_numeric")


def original(root, ref):
    require(Path(ref["file"]).name == ref["file"], "Unexpected evidence path")
    body = (root / ref["file"]).read_bytes()
    require(len(body) == ref["bytes"] and sha(body) == ref["sha256"],
            "Changed entire native evidence")
    return dict(text=body.decode("utf-8"), bytes=len(body), sha256=sha(body))


def unpack(ref):
    body = ref["text"].encode("utf-8")
    require(len(body) == ref["bytes"] and sha(body) == ref["sha256"],
            "Changed entire native evidence")
    return json.loads(body)


def card(evidence, county):
    request, response = unpack(evidence["request"]), unpack(evidence["response"])
    queries = []
    for query in tree(request):
        selects = query.get("Select", [])
        if len(selects) == 1 and selects[0].get("Measure", {}).get("Property") in PROPERTIES:
            queries.append(query)
    require(len(queries) == 7 and
            {q["Select"][0]["Measure"]["Property"] for q in queries} == set(PROPERTIES),
            "Incomplete native measure queries")
    for query in queries:
        conditions = {}
        for where in query.get("Where", []):
            clause = where.get("Condition", {}).get("In", {})
            expressions = clause.get("Expressions", [])
            require(len(expressions) == 1 and "Column" in expressions[0],
                    "Unreviewed native filter")
            prop = expressions[0]["Column"]["Property"]
            require(prop not in conditions, "Duplicate native scope filter")
            conditions[prop] = [cell["Literal"]["Value"]
                                for row in clause["Values"] for cell in row]
        expected = {"ElectionName", "ELECTION_DATE"} | ({"COUNTY_NAME"} if county else set())
        require(set(conditions) == expected
                and conditions["ElectionName"] == ["'" + ELECTION + "'"]
                and "datetime'2026-11-03T00:00:00'" in conditions["ELECTION_DATE"]
                and (not county or conditions["COUNTY_NAME"] == ["'" + county + "'"]),
                "Wrong native election or single-county scope")
    data = list(packets(response))
    require(len(data) == 1, "Ambiguous native response")
    data = data[0]
    fields = {item["Value"]: item["Name"] for item in data["descriptor"]["Select"]}
    require(len(fields) == 7 and set(fields.values()) == set(FIELDS),
            "Changed native card measures")
    datasets = data["dsr"]["DS"]
    require(len(datasets) == 1 and datasets[0].get("IC") is True,
            "Incomplete native card response")
    rows = [row for group in datasets[0].get("PH", [])
            for rowset in group.values() for row in rowset]
    require(len(rows) == 1, "Ambiguous native card row")
    row = rows[0]
    require(len(row.get("S", [])) == len(row.get("C", [])) == 7
            and len({item["N"] for item in row["S"]}) == 7
            and "R" not in row and "N" not in row, "Unreviewed native row encoding")
    values = {fields[column["N"]]: cell for column, cell in zip(row["S"], row["C"])}
    require(values[FIELDS[2]] == (county + " County" if county else "Selected counties"),
            "Native response does not match requested county")
    return values


def native_inventory(evidence):
    data = list(packets(unpack(evidence)))
    require(len(data) == 1 and
            [item["Name"] for item in data[0]["descriptor"]["Select"]]
            == ["DIM_County.COUNTY_NAME"], "Changed native county inventory")
    datasets = data[0]["dsr"]["DS"]
    require(len(datasets) == 1 and datasets[0].get("IC") is True,
            "Incomplete native county inventory")
    counties = [row["G0"] for group in datasets[0]["PH"] for row in group["DM0"]]
    require(len(counties) == len(set(counties)) == 83, "Missing or duplicate native county")
    return counties


def acquire_facts(root):
    receipts = [root / "acquisition-receipt.json"] + sorted(
        root.glob("acquisition-resume-*-receipt.json"))
    receipt = json.loads(receipts[-1].read_text())
    require(receipt["ignore_https_errors"] is False and receipt["declared_url"] == REPORT
            and not receipt["page_errors"], "Unreviewed native acquisition")
    require(len(receipt["completed_counties"]) == 83, "Incomplete native county acquisition")
    inventory = (root / "native-county-inventory.json").read_bytes()
    inventory = dict(text=inventory.decode(), bytes=len(inventory), sha256=sha(inventory))
    statewide = []
    for record in receipt["native_query_responses"]:
        if record["phase"] != "initial-statewide" or record["status"] != 200:
            continue
        response = original(root, record["response"])
        if any(set(item["Name"] for item in data["descriptor"]["Select"]) == set(FIELDS)
               for data in packets(unpack(response))):
            statewide.append(dict(request=original(root, record["native_request"]),
                                  response=response))
    require(statewide, "No actual statewide native card")
    state_text = (root / "initial-statewide-visible-text.txt").read_text()
    clocks = CLOCK.findall(state_text)
    require(len(clocks) == 1, "Missing actual statewide clock")
    facts = dict(schema="michigan-qvf-2026-native-counties-v1", election_literal=ELECTION,
        definition_source=DEFINITION, declared_report=REPORT, native_timezone=None,
        native_clock_literal=clocks[0], inventory=inventory, statewide=statewide[0], counties=[])
    for selected in receipt["completed_counties"]:
        text = original(root, selected["visible_text"])["text"]
        clocks = CLOCK.findall(text)
        require(len(clocks) == 1 and ELECTION in text, "Missing native rendered election/clock")
        ref = selected["evidence"]
        require(ref["status"] == 200 and ref["phase"] == "county:" + selected["county"],
                "Changed native capture status or scope")
        evidence = dict(request=original(root, ref["native_request"]),
                        response=original(root, ref["response"]))
        values = card(evidence, selected["county"])
        _, found, section = text.partition(selected["county"] + " County")
        require(found, "No actual rendered county card")
        section = section.partition("Scroll up")[0]
        rendered = {}
        for field in FIELDS:
            literal = display(values[field])
            if field == FIELDS[2]:
                rendered[field] = literal
            else:
                match = re.search(r"(?<![0-9,])" + re.escape(literal) + r"(?![0-9,])", section)
                require(match is not None, "Native field not actually rendered: " + field)
                rendered[field] = match[0]
        facts["counties"].append(dict(
            county=selected["county"], received_at_utc=selected["received_at_utc"],
            native_clock_literal=clocks[0], rendered_native_fields=rendered, **evidence))
    review(facts)
    return facts


def review(facts):
    require(facts["schema"] == "michigan-qvf-2026-native-counties-v1"
            and facts["election_literal"] == ELECTION and facts["native_timezone"] is None
            and facts["definition_source"] == DEFINITION and facts["declared_report"] == REPORT,
            "Changed source definition or election")
    counties = native_inventory(facts["inventory"])
    require([row["county"] for row in facts["counties"]] == counties,
            "Missing, duplicate or reordered county scope")
    statewide = card(facts["statewide"], None)
    rows, totals, complete_modes, statuses = [], [], 0, []
    for selected in facts["counties"]:
        require(selected["native_clock_literal"] == facts["native_clock_literal"]
                and CLOCK.fullmatch(selected["native_clock_literal"]) is not None,
                "Mixed or missing native refresh clocks")
        values = card(selected, selected["county"])
        require(selected["rendered_native_fields"] == {
            field: display(values[field]) for field in FIELDS},
            "Native response and rendered numerical facts disagree")
        absentee, early, election_day = [number(values[FIELDS[index]]) for index in (1, 3, 5)]
        mode_states = [mode_status(values[FIELDS[index]]) for index in (1, 3, 5)]
        statuses.extend(mode_states)
        total, permanent = number(values[FIELDS[6]]), number(values[FIELDS[4]])
        all_modes = all(value is not None for value in (absentee, early, election_day))
        complete_modes += all_modes
        totals.append(total)
        rows.append([
            selected["county"], "", selected["native_clock_literal"], "", total,
            values[FIELDS[0]], "", absentee, early, election_day, permanent,
            values[FIELDS[1]], values[FIELDS[3]], values[FIELDS[5]],
            str(all_modes).lower(),
            str(sum((absentee, early, election_day)) == total).lower() if all_modes else "",
            "", "", "false", "false", *mode_states,
        ])
    headers = ("native_county_name", "native_fips", "native_update_clock", "native_timezone",
        "native_qvf_recorded_total", "native_active_registered_turnout_literal",
        "native_county_active_registration_denominator", "qvf_absentee_returned",
        "qvf_early_voting", "qvf_election_day", "permanent_vote_by_mail_voters",
        "native_absentee_literal", "native_early_voting_literal", "native_election_day_literal",
        "all_native_modes_numeric", "all_numeric_modes_reconcile", "tabulator_ballots",
        "generic_registration_fraction", "maps_approved", "rates_approved",
        "native_absentee_status", "native_early_voting_status", "native_election_day_status")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    state_total = number(statewide[FIELDS[6]])
    aggregate = sum(totals) if all(value is not None for value in totals) else None
    audit = dict(native_counties=len(rows), counties_with_three_numeric_native_modes=complete_modes,
        counties_with_unavailable_native_modes=len(rows) - complete_modes,
        native_mode_cells_no_data_available=statuses.count("source_no_data_available"),
        native_mode_cells_suppressed_less_than_10=statuses.count("source_suppressed_less_than_10"),
        statewide_native_qvf_total=state_total, complete_native_county_total_sum=aggregate,
        native_county_totals_match_statewide=aggregate == state_total if aggregate is not None else None,
        unallocated_statewide_minus_native_county_total=(
            state_total - aggregate if state_total is not None and aggregate is not None else None),
        reviewed_county_registration_denominators=0, approved_generic_rates=0,
        approved_tabulator_ballot_totals=0, approved_maps=0,
        scope="QVF voting history, not tabulator results. Source-native totals can exclude "
              "unavailable Election Day data; absentee returned does not mean accepted/tabulated. "
              "Three numeric modes do not establish finished clerk uploads, counting or certification. "
              "Printed active-registration percentages are preserved, never inverted into "
              "denominators or presented as CVAP/VAP/VEP/generic registration turnout. "
              "Unavailable or suppressed cells stay missing; no residual reconstruction. "
              "Permanent vote-by-mail enrollment is not participation. No candidate/party totals "
              "or demographic turnout are supplied. Native timezone and FIPS are absent.")
    return {"county-participation.csv": stream.getvalue().encode(), "audit.json": encoded(audit)}


def build(facts, output):
    files = {"native-facts.json": encoded(facts), **review(facts)}
    here = Path(__file__).resolve().parent
    for name in (PROGRAM, TEST, "acquire-michigan-qvf-counties.py"):
        files[name] = (here / name).read_bytes()
    files["METHODS.txt"] = (
        "Complete Michigan QVF county observation query; not tabulator results.\n"
        "Entire native single-county requests/responses and the complete 83-county "
        "inventory are in native-facts.json, with original-byte checksums.\n"
        "Reproduce offline: python3 review-michigan-qvf-counties.py --facts "
        "native-facts.json --output REPRODUCED\n"
        "Run: python3 test_review_michigan_qvf_counties.py\n"
        "Refresh privately using installed Playwright/Chromium: python3 "
        "acquire-michigan-qvf-counties.py --output PRIVATE_DIRECTORY\n"
        "Resume only unfinished counties: add --resume with that same directory.\n"
        "The native total can be a subtotal when a mode is unavailable. Printed rates "
        "do not supply exact county registration denominators. No generic rate, "
        "tabulator ballot count, FIPS or map is approved. Missing is not zero.\n"
        "Official definitions: " + DEFINITION + "\n").encode()
    files["manifest.json"] = encoded([
        dict(file=name, bytes=len(body), sha256=sha(body)) for name, body in sorted(files.items())])
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, body)
    files["complete-query.zip"] = archive.getvalue()
    output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (output / name).write_bytes(body)
    return json.loads(files["audit.json"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--originals", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = acquire_facts(args.originals) if args.originals else json.loads(args.facts.read_text())
    print(json.dumps(build(facts, args.output), indent=2))
