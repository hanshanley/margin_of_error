"""Reproduce all 36 Oregon county participation observations from a frozen official snapshot."""

import argparse
import csv
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile

SOURCES = {
    "official-index.html": ("https://results.oregonvotes.gov/", 36904,
        "5dad5831e4e7448702f10c6e7b8b8be035a7910ed77634bd60860815e1fa5311"),
    "official-turnout.html": ("https://results.oregonvotes.gov/VoterTurnoutDetails.aspx", 92717,
        "4acfcafd768e575412f37d625b16f73fab347fe5d37baa7b7c7cd54e2c4c3680"),
    "official-current-election.html": ("https://sos.oregon.gov/elections/pages/current-election.aspx", 112384,
        "6800e6736144b1af3c2fb2e76d3d11fdb15e9a15a0df28e73d976d1d043f0c25"),
    "TurnoutCharts.js": ("https://orresultswebservices.azureedge.us//Scripts/TurnoutCharts.js", 3723,
        "b604aca73b1d9855ca91656009730980706f6ebff09dc71f09219d3a7220eaa9"),
    "county-turnout.json": ("https://orresultswebservices.azureedge.us/ResultsAjax.svc/GetVoterTurnoutData?", 12999,
        "ac93c89355f4529dc29325a91f9a9467c860f3daadcc09bc2ba952ea6a8079e6"),
}
QUALIFICATION = (
    "Unofficial ballots counted, not final turnout or ballots received. Denominator is native active "
    "registrations, not CVAP/VEP or demographic registration. Preserve IsReported false and ancillary "
    "zero fields; they do not erase positive counted ballots. Native county IDs are not FIPS. "
    "County timestamps have no stated timezone; statewide update explicitly says PT. "
    "No new map, demographic rate or statewide completion approval."
)
HEADER_FIELDS = ("source_file", "election_date", "election_type", "source_status_literal",
    "ballots_counted", "active_registered_voters", "native_hidden_ballots", "native_hidden_remainder",
    "native_reported_percent", "source_updated_at")


def integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Invalid native Oregon count")
    return value


def reconcile(facts):
    records = json.loads(facts["original_county_response"])["d"]
    cards = facts["county_cards"]
    headers = [{field: row[field] for field in HEADER_FIELDS} for row in facts["statewide_headers"]]
    if len(records) != 36 or len(cards) != 36 or len(headers) != 2:
        raise ValueError("Incomplete Oregon counties or independent headers")
    by_id = {row["CountyID"]: row for row in records}
    card_ids = {row["native_county_id"]: row for row in cards}
    if (len(by_id) != 36 or len(card_ids) != 36 or by_id.keys() != card_ids.keys()
            or len({row["CountyName"] for row in records}) != 36):
        raise ValueError("Duplicated or unmatched Oregon county identity")
    rows = []
    for record in records:
        card = card_ids[record["CountyID"]]
        ballots, registered = integer(record["calcVoterTurnout"]), integer(record["Voters"])
        if (not re.fullmatch(r"\d{2}", record["CountyID"])
                or record["CountyName"] != card["county"] or record["PrecinctName"] != "Countywide"
                or registered == 0 or ballots > registered
                or f"{100 * ballots / registered:.2f}%" != card["native_reported_percent"]):
            raise ValueError("Oregon county scope, identity or independent printed fraction differs")
        datetime.datetime.strptime(record["CurrentDateTime"], "%m/%d/%Y %I:%M:%S %p")
        rows.append(dict(year=2026, state_code="OR", county=record["CountyName"],
            native_county_id=record["CountyID"], ballots_counted=ballots,
            active_registered_voters=registered, native_reported_percent=card["native_reported_percent"],
            source_status_literal="Unofficial", source_updated_at=record["CurrentDateTime"],
            native_record_json=json.dumps(record, sort_keys=True, separators=(",", ":")),
            qualification=QUALIFICATION))
    ballots = sum(row["ballots_counted"] for row in rows)
    registered = sum(row["active_registered_voters"] for row in rows)
    if {row["source_file"] for row in headers} != {"official-index.html", "official-turnout.html"}:
        raise ValueError("Missing or repeated Oregon independent header")
    for header in headers:
        if (header["election_date"] != "11/3/2026" or header["election_type"] != "General"
                or header["source_status_literal"] != "Unofficial"
                or header["ballots_counted"] != ballots or header["active_registered_voters"] != registered
                or header["native_hidden_ballots"] != ballots
                or integer(header["native_hidden_remainder"]) + ballots != registered
                or header["native_reported_percent"] != f"{100 * ballots / registered:.2f}%"
                or not header["source_updated_at"].endswith(" PT")):
            raise ValueError("Oregon election, county rollup or independent statewide header differs")
    audit = dict(year=2026, state_code="OR", county_observations=36, ballots_counted=ballots,
        active_registered_voters=registered, independent_county_fractions=36,
        independent_statewide_headers=2, false_native_reporting_flags=sum(
            row["IsReported"] is False for row in records),
        native_fields_preserved=True, maps_approved=False, demographic_rates_approved=False,
        statewide_completion_approved=False, qualification=QUALIFICATION)
    return rows, headers, audit


def acquire_facts(directory):
    from bs4 import BeautifulSoup

    bodies, receipts = {}, []
    for name, (url, size, digest) in SOURCES.items():
        raw = (directory / name).read_bytes()
        receipt = json.loads((directory / (name + ".receipt.json")).read_text())
        if (len(raw) != size or hashlib.sha256(raw).hexdigest() != digest
                or receipt["url"] != url or receipt["status"] != 200
                or receipt["bytes"] != size or receipt["sha256"] != digest):
            raise ValueError("Oregon original or HTTP receipt mismatch: " + name)
        bodies[name] = raw.decode("utf-8-sig")
        receipts.append(dict(file=name, **receipt))
    chart = bodies["TurnoutCharts.js"]
    governing = BeautifulSoup(bodies["official-current-election.html"], "html.parser")
    if ('GetVoterTurnoutData?' not in chart or 'county.calcVoterTurnout' not in chart
            or 'county.Voters' not in chart or 'Ballots Counted<span>' not in chart
            or 'Active Registered Voters<span>' not in chart
            or not any(urlsplit(link.get("href", "")).hostname == "results.oregonvotes.gov"
                       for link in governing.find_all("a"))):
        raise ValueError("Official Oregon data declaration or field meaning changed")
    headers = []
    for name in ("official-index.html", "official-turnout.html"):
        soup = BeautifulSoup(bodies[name], "html.parser")
        text = soup.get_text(" ", strip=True)
        counts = [integer(int(span.get_text(strip=True).replace(",", "")))
                  for span in soup.select(".vt-number")]
        if len(counts) != 2 or not re.search(r">\s*Unofficial\s*<", bodies[name]):
            raise ValueError("Missing Oregon native ballot/registration header or status")
        updated = re.findall(r"Results last updated:\s*(\d+/\d+/\d+ \| [\d:]+ [AP]M PT)", text)
        fraction = re.findall(r"Statewide Voter Turnout\s*\(details\)\s*(\d+)\s*(\.\d+%)", text)
        if len(updated) != 1 or not fraction:
            raise ValueError("Missing Oregon literal statewide timestamp or fraction")
        headers.append(dict(source_file=name, election_date=soup.select_one("#hidElectionDate")["value"],
            election_type=soup.select_one("#hidElectionType")["value"], source_status_literal="Unofficial",
            ballots_counted=counts[0], active_registered_voters=counts[1],
            native_hidden_ballots=int(soup.select_one("#hidVoterTurnout")["value"]),
            native_hidden_remainder=int(soup.select_one("#hidVoterTotal")["value"]),
            native_reported_percent="".join(fraction[0]), source_updated_at=updated[0]))
    soup = BeautifulSoup(bodies["official-turnout.html"], "html.parser")
    cards = []
    for link in soup.select('a[id*="lnkCountyName"]'):
        card = link.find_parent("div", class_="section")
        cards.append(dict(native_county_id=re.search(r"cty=(\d+)", link["href"]).group(1),
            county=link.get_text(strip=True),
            native_reported_percent=card.select_one(".dough-inner").get_text("", strip=True)))
    return dict(original_county_response=bodies["county-turnout.json"], county_cards=cards,
        statewide_headers=headers, source_receipts=receipts)


def build(facts, output):
    raw = facts["original_county_response"].encode()
    _, size, digest = SOURCES["county-turnout.json"]
    receipts = {row["file"]: row for row in facts["source_receipts"]}
    if (len(raw) != size or hashlib.sha256(raw).hexdigest() != digest
            or len(receipts) != len(SOURCES)):
        raise ValueError("Frozen complete Oregon records or receipt inventory changed")
    for name, (url, size, digest) in SOURCES.items():
        row = receipts[name]
        if (row["url"] != url or row["bytes"] != size or row["sha256"] != digest or row["status"] != 200):
            raise ValueError("Frozen Oregon provenance changed")
    rows, headers, audit = reconcile(facts)
    if output.exists():
        raise ValueError("Refusing to overwrite Oregon participation output")
    output.mkdir(parents=True)
    for name, records in (("county-participation.csv", rows), ("statewide-observations.csv", headers)):
        with (output / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, separators=(",", ":")) + "\n").encode(), mtime=0))
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(output / "complete-oregon-county-participation-01.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.suffix != ".zip":
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-directory", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = acquire_facts(args.source_directory) if args.source_directory else json.loads(
        gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()
