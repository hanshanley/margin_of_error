"""Refresh 2026 participation and audit official county/precinct count allocations."""

import argparse
import copy
import hashlib
import html
import json
import re
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests


PORTALS = {
    "NE": ("https://electionresults.nebraska.gov/VoterTurnoutDetails.aspx?map=PREC",
           "https://neresultswebservice.azurewebsites.us/ResultsAjax.svc/GetVoterTurnoutData?", 93),
    "NM": ("https://electionresults.sos.nm.gov/VoterTurnoutDetails.aspx?map=PREC",
           "https://nmresultswebservice.azurewebsites.us/NMResultsAjax.svc/GetVoterTurnoutData?", 33),
    "SD": ("https://electionresults.sd.gov/VoterTurnoutDetails.aspx?map=PREC",
           "https://sdresws.azurewebsites.us/ResultsAjax.svc/GetVoterTurnoutData?", 66),
}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def integer(value):
    text = str(value).replace(",", "").strip()
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"Invalid administrative count: {value!r}")
    return int(text)


def text(value):
    return " ".join(html.unescape(re.sub("<[^>]+>", "", value)).split())


def ratio(ballots, denominator):
    return 100 * ballots / denominator if denominator and 0 < ballots <= denominator else None


def parse_portal(page, payload, code, official, provenance):
    for field, value in [("hidElectionDate", "11/3/2026"), ("hidElectionType", "General")]:
        if not re.search(r'id="' + field + r'"\s+value="' + re.escape(value) + '"', page):
            raise ValueError(f"{code}: wrong or unverified election identity")
    values = payload.get("d") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or len(values) != PORTALS[code][2]:
        raise ValueError(f"{code}: incomplete county collection")
    counties, precincts, by_id = [], [], {}
    for value in values:
        county_id, name = str(value["CountyID"]), value["CountyName"]
        if county_id in by_id:
            raise ValueError(f"{code}: duplicate county identity {county_id}")
        ballots, denominator = integer(value["calcVoterTurnout"]), integer(value["Voters"])
        reported, total = integer(value["PrecinctsReporting"]), integer(value["TotalPrecincts"])
        if reported > total:
            raise ValueError(f"{code}: invalid reporting progress")
        pct = ratio(ballots, denominator)
        published = float(value["CountyPercent"]) * 100
        quality = [] if pct is not None and abs(pct - published) <= .015 else [
            "Published percentage or denominator is inconsistent; rate withheld."]
        if reported < total:
            quality.append("Incomplete precinct reporting; not final turnout.")
        row = {
            "year": 2026, "state_code": code, "county_id": county_id, "county": name,
            "ballots": ballots, "denominator": denominator,
            "denominator_basis": official["denominator_basis"],
            "reported_pct": pct if not quality or pct is not None and abs(pct - published) <= .015 else None,
            "reported_units": reported, "total_units": total,
            "source_update_label": value.get("CurrentDateTime") or official["source_update_label"],
            **provenance, "quality": quality,
        }
        counties.append(row)
        by_id[county_id] = row
    if (sum(r["ballots"] for r in counties) != official["ballots"]
            or sum(r["denominator"] for r in counties) != official["denominator"]):
        raise ValueError(f"{code}: county counts do not reconcile to same-page statewide totals")
    seen_counties = set()
    for block in page.split('<div class="provisional-results-wrapper">'):
        identity = re.search(r'id="countyturnout([^"]+)"', block)
        if not identity:
            continue
        county_id = identity[1]
        heading = re.search(r"<h1>(.*?)</h1>", block, re.S)
        if (county_id not in by_id or not heading
                or text(heading[1]).replace(" (", "(") != by_id[county_id]["county"].replace(" (", "(")):
            raise ValueError(f"{code}: precinct/county identity disagreement")
        if county_id in seen_counties:
            raise ValueError(f"{code}: repeated county precinct block")
        seen_counties.add(county_id)
        county = by_id[county_id]
        cells = re.findall(
            r'<div class="county-precinct">(.*?)</div>\s*'
            r'<div class="county-cast">\s*<span>([\d,]+)</span>\s*</div>\s*'
            r'<div class="county-counted">\s*<span>([\d,]+)</span>', block, re.S)
        if len(cells) != block.count('<div class="county-precinct">') or not cells:
            raise ValueError(f"{code}: unrecognized precinct table schema")
        units, names = [], Counter(text(cell[0]) for cell in cells)
        for ordinal, (label, ballots, denominator) in enumerate(cells, 1):
            name = text(label)
            if not name:
                raise ValueError(f"{code}: missing precinct name")
            special = bool(re.search(r"\b(countywide|absentee|early|provisional)\b", name, re.I))
            vote_center = "vote center" in (county["county"] + " " + name).lower()
            kind = "countywide" if name.lower() == "countywide" else (
                "vote_center" if vote_center else "special_reporting_unit" if special else "precinct")
            if names[name] > 1 and kind == "precinct":
                kind = "ambiguous_source_row"
            units.append({
                **{k: v for k, v in county.items() if k not in (
                    "quality", "reported_pct", "reported_units", "total_units")},
                "unit": name, "unit_key": county_id + "|" + str(ordinal), "unit_kind": kind,
                "ballots": integer(ballots), "denominator": integer(denominator), "reported_pct": None,
                "quality": ["Duplicate source label; row ordinal distinguishes reporting locations."]
                if names[name] > 1 else [],
            })
        ballot_difference = sum(r["ballots"] for r in units) - county["ballots"]
        denominator_difference = sum(r["denominator"] for r in units) - county["denominator"]
        reconciled = ballot_difference == 0 and denominator_difference == 0
        county.update(source_rows=len(units), precinct_rows=sum(r["unit_kind"] == "precinct" for r in units),
                      rows_reconcile=reconciled, ballot_difference=ballot_difference,
                      denominator_difference=denominator_difference)
        if not reconciled:
            county["quality"].append(
                "Source-row counts/electorates do not reconcile to county totals; individual rates withheld.")
        for row in units:
            if not reconciled:
                row["quality"].append("County allocation does not reconcile; individual rate withheld.")
            if row["unit_kind"] != "precinct":
                row["quality"].append("Reporting location or special unit, not a residential precinct; rate withheld.")
            if reconciled and row["unit_kind"] == "precinct":
                row["reported_pct"] = ratio(row["ballots"], row["denominator"])
            if row["reported_pct"] is None and not row["quality"]:
                row["quality"].append("Missing/zero electorate, no reported ballots, or ballots exceed electorate.")
        precincts.extend(units)
    if seen_counties != set(by_id):
        raise ValueError(f"{code}: precinct tables omit counties")
    return counties, precincts


def collect(output, research, previous):
    sys.path.insert(0, str(research.resolve()))
    from scripts import nationwide
    from scripts.current import reporting_counts, write_csv

    now = datetime.now(timezone.utc)
    output.mkdir(parents=True, exist_ok=False)
    sources, originals = [], {}

    def fetch(name, url):
        response = requests.get(url, timeout=(15, 90))
        content = response.content
        source = {"file": name, "url": url, "http_status": response.status_code,
                  "retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "bytes": len(content), "sha256": digest(content)}
        sources.append(source)
        originals[name] = content
        response.raise_for_status()
        return content, source

    with tempfile.TemporaryDirectory(prefix="participation-current-") as directory:
        root = Path(directory)
        prior = json.loads((previous / "snapshot.json").read_text())
        with zipfile.ZipFile(previous / "complete-snapshot.zip") as archive:
            if "full-normalized-snapshot.json" in archive.namelist():
                prior = json.loads(archive.read("full-normalized-snapshot.json"))
        if not prior.get("datasets"):
            raise ValueError("Previous complete snapshot has no normalized source datasets for safe retention")
        public = root / "public/data/nationwide"
        (public / prior["snapshot_id"]).mkdir(parents=True)
        (public / prior["snapshot_id"] / "snapshot.json").write_text(json.dumps(prior))
        (public / "latest.json").write_text(json.dumps({"snapshot_id": prior["snapshot_id"]}))
        with zipfile.ZipFile(previous / "complete-snapshot.zip") as archive:
            for name in archive.namelist():
                parts = Path(name).parts
                if len(parts) == 3 and parts[0] == "sources" and all(p not in (".", "..") for p in parts):
                    target = root / "data/raw/nationwide" / parts[1] / parts[2]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
        snapshot = nationwide.refresh(root=root, now=now)
        saved = public / snapshot["snapshot_id"]
        counties, precincts, failures = [], [], []
        for code, (url, service, _) in PORTALS.items():
            try:
                body, source = fetch(code + "-precincts.html", url)
                payload, api_source = fetch(code + "-counties.json", service)
                official = nationwide.parse_official(body, code)
                provenance = {"source_url": url, "county_source_url": service,
                              "source_retrieved_at": source["retrieved_at"],
                              "source_sha256": source["sha256"], "county_source_sha256": api_source["sha256"]}
                county_rows, precinct_rows = parse_portal(
                    body.decode("utf-8"), json.loads(payload), code, official, provenance)
                counties.extend(county_rows)
                precincts.extend(precinct_rows)
                snapshot["datasets"][f"{code}-official"] = {
                    "state": code, "kind": "official", "status": "reported", "data": official,
                    "source": {**source, "snapshot_id": snapshot["snapshot_id"]},
                    "error": None, "attempt_url": url,
                }
            except Exception as error:
                failures.append({"state_code": code, "error": str(error)})
        try:
            body, source = fetch("NC-counties.json", nationwide.OFFICIAL["NC"])
            values, _ = reporting_counts(json.loads(body))
            for value in values:
                if value["county_id"] == "0":
                    continue
                counties.append({
                    "year": 2026, "state_code": "NC", "county_id": value["county_id"],
                    "county": value["county"], "ballots": value["ballots_cast"],
                    "denominator": value["registered_voters"],
                    "denominator_basis": "active_and_inactive_registered_voters",
                    "reported_pct": value["reported_ballot_fraction_pct"],
                    "reported_units": value["precincts_reporting"], "total_units": value["precincts_total"],
                    "source_update_label": value["source_update_label"],
                    "source_url": source["url"], "source_retrieved_at": source["retrieved_at"],
                    "source_sha256": source["sha256"], "quality": value["quality"],
                    "source_rows": 0, "precinct_rows": 0, "rows_reconcile": None,
                    "ballot_difference": None, "denominator_difference": None,
                })
            snapshot["datasets"]["NC-official"].update(
                data=nationwide.parse_official(body, "NC"),
                source={**source, "snapshot_id": snapshot["snapshot_id"]}, status="reported", error=None)
        except Exception as error:
            failures.append({"state_code": "NC", "error": str(error)})
        refreshed = nationwide.assemble(snapshot["datasets"], snapshot["snapshot_id"], now.isoformat())
        refreshed["sources"] = snapshot["sources"] + sources
        for name in ("early_voting", "demographics", "reporting", "coverage"):
            write_csv(output / (name + ".csv"), refreshed[name])
        local = {"election_date": nationwide.ELECTION, "counties": counties, "precincts": precincts,
                 "failures": failures, "sources": sources}
        write_csv(output / "counties.csv", counties)
        write_csv(output / "precincts.csv", precincts)
        local["audit"] = [{
            "state_code": code, "counties": sum(r["state_code"] == code for r in counties),
            "source_rows": sum(r["state_code"] == code for r in precincts),
            "precinct_rows": sum(r["state_code"] == code and r["unit_kind"] == "precinct" for r in precincts),
            "rows_with_rate": sum(r["state_code"] == code and r["reported_pct"] is not None for r in precincts),
        } for code in sorted({r["state_code"] for r in counties})]
        (output / "local.json").write_text(json.dumps(local, separators=(",", ":")) + "\n")
        refreshed["local_file"] = "local.json"
        refreshed["local_audit"] = local["audit"]
        refreshed["local_failures"] = failures
        refreshed["collector_sha256"] = digest(Path(__file__).read_bytes())
        refreshed["research_collectors"] = {
            name: digest((research / "scripts" / name).read_bytes())
            for name in ("nationwide.py", "current.py", "download.py")}
        full = copy.deepcopy(refreshed)
        del refreshed["datasets"]
        (output / "snapshot.json").write_text(json.dumps(refreshed, separators=(",", ":")) + "\n")
        with zipfile.ZipFile(output / "complete-snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            with zipfile.ZipFile(saved / "complete-snapshot.zip") as old:
                for name in old.namelist():
                    if name.startswith("sources/"):
                        archive.writestr(name, old.read(name))
            for name, content in originals.items():
                archive.writestr("local-sources/" + name, content)
            archive.writestr("full-normalized-snapshot.json", json.dumps(full))
            for path in output.iterdir():
                if path.name != "complete-snapshot.zip":
                    archive.write(path, path.name)
    checksums = {p.name: {"bytes": p.stat().st_size, "sha256": digest(p.read_bytes())}
                 for p in output.iterdir()}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    print(json.dumps({"audit": refreshed["audit"], "local": local["audit"], "failures": failures}, indent=2))
    if failures:
        raise ValueError("Local source audit failed; pointer not published")
    (output.parent / "latest.json").write_text(json.dumps({
        "snapshot_id": output.name, "election_date": nationwide.ELECTION,
        "retrieved_at": refreshed["retrieved_at"],
    }, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research", type=Path, default=Path("../voter-participation"))
    parser.add_argument("--previous", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output, args.research, args.previous)
