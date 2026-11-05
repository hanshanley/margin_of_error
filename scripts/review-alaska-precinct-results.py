"""Reconcile Alaska 2026 House originals without allocating pooled ballots."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

SOURCE = "https://www.elections.alaska.gov/enr/26GENR/"
OFFICE = "U.S. Representative"
ORIGINALS = (
    "statewide-original.json", "precincts-original.json", "full-precinct-results.csv",
    "full-statewide-summary.pdf", "official-district-shapes.json", "official-precinct-shapes.json",
)
RELEASE = ("https://github.com/hanshanley/margin_of_error/releases/download/"
           "voter-precinct-alaska-20261105/complete-alaska-2026-source-review.zip")
MODES = ("Election Day", "Absentee", "Early Voting", "Question", "Remote")


def count(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError("Missing or invalid Alaska count; not zero")


def candidate_totals(record, names):
    result = {}
    for candidate in record["c"]:
        index = candidate["n"]
        if type(index) is not int or not 0 <= index < len(names) or names[index] in result:
            raise ValueError("Ambiguous Alaska native candidate identity")
        result[names[index]] = count(candidate["t"])
    if not result or sum(result.values()) != count(record["t"]):
        raise ValueError("Alaska native candidate sum disagrees with contest total")
    return result


def house(records, contest):
    matches = [r for r in records if r["n"] == contest]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate Alaska House contest")
    return matches[0]


def review(rows, statewide, precincts, shapes):
    for data in (statewide, precincts):
        if (data["name"] != "Alaska 2026 General Election"
                or type(data["certified"]) is not bool
                or data["format"] != "2024"
                or data["contestNames"].count(OFFICE) != 1):
            raise ValueError("Wrong Alaska election, statistics format or House identity")
    for field in ("name", "certified", "updated", "format", "candidateNames", "contestNames", "totals"):
        if statewide[field] != precincts[field]:
            raise ValueError("Alaska statewide and precinct snapshots differ: " + field)
    names = precincts["candidateNames"]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate Alaska native candidate name")
    contest = precincts["contestNames"].index(OFFICE)
    total = house(precincts["totals"], contest)
    expected = candidate_totals(total, names)
    native = {}
    for precinct in precincts["precincts"]:
        number = precinct["number"]
        if number in native:
            raise ValueError("Duplicate Alaska geographic precinct ID")
        record = house(precinct["contests"], contest)
        candidate_totals(record, names)
        native[number] = (precinct, record)
    shape_ids = [s["number"] for s in shapes]
    if (not native or len(shape_ids) != len(set(shape_ids)) or set(shape_ids) != set(native)):
        raise ValueError("Alaska complete original shape-ID and geographic-result sets differ")
    districts = [str(d["number"]) for d in precincts["districts"]]
    if not districts or len(districts) != len(set(districts)):
        raise ValueError("Missing or duplicate Alaska district identities")
    units = defaultdict(list)
    for number, row in enumerate(rows, 2):
        if row["Contest_title"] == OFFICE:
            units[row["Pct_seq_nbr"]].append((number, row))
    results, statistics, seen, pooled = [], [], set(), set()
    sums = Counter()
    for sequence, records in units.items():
        count(sequence)
        row_numbers, values = zip(*records)
        first = values[0]
        for field in ("Pct_Id", "Precinct_name", "Reg_voters", "total_ballots",
                      "total_under_votes", "total_over_votes", "Contest_Id", "Selectable_Options"):
            if len({r[field] for r in values}) != 1:
                raise ValueError("Conflicting Alaska repeated reporting-unit field: " + field)
        if (first["Selectable_Options"] != "1" or not first["Precinct_name"]
                or len({r["candidate_id"] for r in values}) != len(values)
                or any(not r["candidate_id"] for r in values)):
            raise ValueError("Ambiguous Alaska reporting unit or candidate identity")
        votes, parties = {}, {}
        for row in values:
            party = row["Party_Code"]
            if party not in {"REP", "DEM", "NON", "LIB", "IND", ""}:
                raise ValueError("Unknown Alaska source candidate party")
            name = row["candidate_name"] + (f" ({party})" if party else "")
            if not row["candidate_name"] or name in votes:
                raise ValueError("Duplicate or missing Alaska candidate name")
            votes[name], parties[name] = count(row["total_votes"]), party
            if votes[name] != sum(count(row[mode + "_votes"]) for mode in MODES):
                raise ValueError("Alaska candidate total differs from its ballot-mode columns")
        if set(votes) != set(expected):
            raise ValueError("Alaska CSV and native candidate identities differ")
        ballots, registered = count(first["total_ballots"]), count(first["Reg_voters"])
        under, over = count(first["total_under_votes"]), count(first["total_over_votes"])
        identifier, label = first["Pct_Id"], first["Precinct_name"]
        flags = []
        if identifier in native:
            precinct, record = native[identifier]
            if (identifier in seen or label != identifier + " " + precinct["name"]
                    or votes != candidate_totals(record, names)
                    or ballots != count(record["b"]) or registered != count(record["v"])):
                raise ValueError("Alaska CSV does not match the literal geographic JSON record")
            seen.add(identifier)
            kind = "geographic_precinct"
            flags.append("pooled_district_ballots_not_allocated_to_residential_precincts")
        elif identifier == "99-999" and label == "HD99 Fed Overseas Absentee":
            kind = "federal_overseas"
            flags.append("federal_overseas_reporting_unit_not_residential_precinct")
        else:
            match = re.fullmatch(r"District ([0-9]+)\s+-\s+(Absentee|Early Voting|Question)", label)
            if match is None or match[1] not in districts or (match[1], match[2]) in pooled:
                raise ValueError("Unknown or duplicate Alaska pooled reporting unit")
            pooled.add((match[1], match[2]))
            kind = "pooled_district_" + match[2].lower().replace(" ", "_")
            flags.append("pooled_district_reporting_unit_not_residential_precinct")
        if registered < 25:
            flags.append("missing_or_small_source_registration_denominator")
        if ballots > registered:
            flags.append("ballots_exceed_source_registration")
        candidate_sum = sum(votes.values())
        if candidate_sum + under + over != ballots:
            flags.append("candidate_votes_plus_source_under_over_disagree_with_ballots")
        if candidate_sum > ballots:
            flags.append("candidate_votes_exceed_reported_ballots")
        key = "AK|source-unit-" + sequence
        democratic = sum(v for n, v in votes.items() if parties[n] == "DEM")
        republican = sum(v for n, v in votes.items() if parties[n] == "REP")
        base = dict(key=key, year=2026, state_code="AK", precinct=label,
            source_precinct_id=identifier, source_sequence=sequence, reporting_unit_kind=kind,
            source_url=SOURCE, source_file="full-precinct-results.csv",
            source_rows=json.dumps(row_numbers, separators=(",", ":")))
        results.append(dict(base, office="U.S. House", source_office=OFFICE,
            democratic_votes=democratic, republican_votes=republican,
            other_votes=candidate_sum - democratic - republican, contest_votes=candidate_sum,
            candidate_votes=json.dumps(votes, separators=(",", ":"), sort_keys=True),
            margin_pp=100 * (democratic - republican) / candidate_sum if candidate_sum else None,
            ballot_scope="Unofficial reported candidate counts, not a final ranked-choice outcome. "
                "Pooled district ballots remain separate and are never allocated to geographic precincts.",
            quality_flags=";".join(flags)))
        statistics.append(dict(base, ballots=ballots, registered=registered,
            source_under_votes=under, source_over_votes=over, reported_pct=None,
            denominator_scope="source_reporting_unit_registration",
            basis="Rates withheld: geographic units omit separately pooled ballot modes, and pooled "
                "and federal units are not residential precincts. Not final or demographic turnout.",
            quality_flags=flags))
        sums.update(votes)
    if (seen != set(native) or dict(sums) != expected
            or pooled != {(d, mode) for d in districts for mode in ("Absentee", "Early Voting", "Question")}
            or Counter(r["reporting_unit_kind"] for r in results)["federal_overseas"] != 1
            or sum(r["ballots"] for r in statistics) != count(total["b"])
            or sum(r["registered"] for r in statistics) != count(total["v"])
            or count(total["p"]) != len(native) + 1
            or count(total["r"]) > count(total["p"])):
        raise ValueError("Alaska complete unit scope, statewide candidates, ballots or registrations differ")
    return results, statistics, dict(geographic_precincts=len(native), pooled_reporting_units=len(pooled),
        federal_overseas_units=1, original_shape_ids=len(shape_ids),
        precincts_reported=total["r"], precincts_expected=total["p"],
        candidate_totals_by_name=expected,
        quality_flag_counts=dict(Counter(flag for r in statistics for flag in r["quality_flags"])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Alaska review")
    receipts = json.loads((args.cache_directory / "sources.json").read_text())
    originals = {}
    for name in ORIGINALS:
        raw = (args.cache_directory / name).read_bytes()
        if len(raw) != receipts[name]["bytes"] or hashlib.sha256(raw).hexdigest() != receipts[name]["sha256"]:
            raise ValueError("Alaska original source checksum mismatch: " + name)
        originals[name] = raw
    statewide = json.loads(originals["statewide-original.json"])
    precincts = json.loads(originals["precincts-original.json"])
    source_rows = list(csv.DictReader(io.StringIO(originals["full-precinct-results.csv"].decode("utf-8-sig"))))
    results, statistics, reconciliation = review(source_rows, statewide, precincts,
        json.loads(originals["official-precinct-shapes.json"]))
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    for name, raw in originals.items():
        path = args.output / "originals" / (name + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
    save("sources.json", {name: receipts[name] for name in ORIGINALS})
    save("participation.json.gz", statistics)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(buffer.getvalue().encode(), mtime=0))
    audit = dict(year=2026, state_code="AK", complete="no", reporting_units=len(results),
        candidate_results="acquired_reconciled", participation="acquired_reporting_unit_counts_rates_withheld",
        boundaries="correct_election_reference_acquired_review_pending", join="withheld",
        validation="counts_passed_map_withheld", publication="full_counts_download_only",
        source_url=SOURCE, boundary_source=SOURCE, source_election=precincts["name"],
        source_updated=precincts["updated"], source_certified=precincts["certified"],
        complete_original_csv_rows=len(source_rows), native_original_sources=len(originals),
        native_original_bytes=sum(map(len, originals.values())),
        candidate_totals={field: sum(r[field] for r in results) for field in
            ("democratic_votes", "republican_votes", "other_votes", "contest_votes")},
        ballots=sum(r["ballots"] for r in statistics), registrations=sum(r["registered"] for r in statistics),
        rates_available=0, rates_withheld=len(statistics), reconciliation=reconciliation,
        complete_download_url=RELEASE,
        notes="All 523 original House reporting units reconcile by candidate name/party to statewide "
            "native totals; every geographic row also matches its literal precinct JSON identity, "
            "candidate counts, ballots and registrations. Complete all-contest CSV, both native result "
            "responses, summary PDF and both advertised shape originals are retained. The source's "
            "403 expected reporting precincts include federal overseas ballots; 402 geographic units "
            "exclude 120 pooled district absentee/early/question units and federal overseas ballots. "
            "Preserve all units, including blank native IDs, zero counts, third-party candidates and "
            "every ballot-accounting discrepancy. Candidate votes are not ballots. Rates are withheld, "
            "not repaired, and these unofficial counts do not establish final ranked-choice outcomes "
            "or demographic participation. Shape identity-set agreement is not a validated geometry "
            "join; encoded ring roles, topology and precise election vintage remain unreviewed. "
            "Frontend/template code is not redistributed. Other original contests remain unreviewed.",
        next_action="Decode the official delta-encoded map shapes according to their native public "
            "format; independently audit ring roles, antimeridian handling, topology and election "
            "vintage before a new mapped supplement. Do not map federal or pooled district ballots "
            "onto residential precincts, sum ranked-choice rounds or infer turnout rates.")
    save("audit.json", audit)
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps({k: audit[k] for k in ("reporting_units", "candidate_totals", "ballots",
        "registrations", "rates_available", "rates_withheld", "reconciliation")}, indent=2))


if __name__ == "__main__":
    main()
