"""Freeze held CT native town counts and unchanged full 2024 contextual geometry."""

import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-connecticut-towns-01"
GEOMETRY = "public/participation-town-reports/20261110-connecticut-01/CT.geojson.gz"
SOURCE = "data/precinct-source-acquisitions/20261105/CT-2016-2026-02"


def key(value):
    return re.sub("[^a-z0-9]", "", unicodedata.normalize("NFKD", value).lower())


def build():
    if (ROOT / VERSION).exists() or (ROOT / GEOMETRY).exists():
        raise ValueError("Refuse to replace immutable CT source inputs")
    receipts = json.loads((ROOT / SOURCE / "sources.json").read_bytes())
    members, safe = {}, {}
    for target, name in [
        ("Elections", "Elections"), ("Version", "Version"), ("Version-after-reports", "Version-after-reports"),
        ("election_Electiondata", "election_Electiondata"), ("townStatus_Electiondata", "townStatus_Electiondata"),
        ("voterTurnout_Electiondata", "voterTurnout_Electiondata"),
        ("after-voterTurnout_Electiondata", "version-52338/voterTurnout_Electiondata"),
    ]:
        body = (ROOT / SOURCE / f"originals/2026/{name}.json.gz").read_bytes()
        decoded = gzip.decompress(body)
        receipt = receipts[f"2026/{name}.json"]
        if (receipt["status_code"] != 200 or len(decoded) != receipt["bytes"]
                or hashlib.sha256(decoded).hexdigest() != receipt["sha256"]):
            raise ValueError("Changed original CT source or receipt")
        members[f"{VERSION}/originals/{target}.json.gz"] = body
        safe[target] = {k: receipt[k] for k in ["url", "retrieved_at", "status_code", "bytes", "sha256"]}
    original_path = "data/participation-local/20261104T220000Z-identity-audit/geometry/2024/municipality-CT.geojson.gz"
    original = (ROOT / original_path).read_bytes()
    members[f"{VERSION}/originals/municipality-CT-2024.geojson.gz"] = original
    collection = json.loads(gzip.decompress(original))
    identities = {key(f["properties"]["name"]): f for f in collection["features"]}
    turnout = json.loads(gzip.decompress(members[f"{VERSION}/originals/voterTurnout_Electiondata.json.gz"]))
    towns = {id: row for id, row in turnout.items() if id != "170"}
    if (len(identities) != 169 or len(towns) != 169
            or {key(row["NM"]) for row in towns.values()} != set(identities)):
        raise ValueError("CT full contextual municipality identities do not match")
    features = []
    for id, row in towns.items():
        feature = identities[key(row["NM"])]
        identity = f"CT-TOWN-{id.zfill(3)}"
        features.append(dict(feature, properties=dict(feature["properties"], key=identity, name=row["NM"],
            source_administration_id=identity, source_town_id=id,
            reference_municipality_key=feature["properties"]["key"])))
    derived = (json.dumps(dict(type="FeatureCollection", features=features), separators=(",", ":")) + "\n").encode()
    members[GEOMETRY] = gzip.compress(derived, mtime=0)
    reference = dict(path=GEOMETRY, url="/" + GEOMETRY.removeprefix("public/"),
        sha256=hashlib.sha256(members[GEOMETRY]).hexdigest(),
        uncompressed_sha256=hashlib.sha256(derived).hexdigest(),
        boundary_year=2024, localities=169, geography_scope="native_town_reporting_area",
        identity_field="source_administration_id", review_id="connecticut-native-towns-20261110-01",
        certified_election_day_geography=False)
    inputs = dict(year=2026, state_code="CT", native_election_id="108", rates_approved=False,
        cast_ballot_count_qualified=False, unique_voter_count_qualified=False, precincts_approved=False,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-connecticut-native-towns-20261110-01/complete-analysis.zip",
        original_geometry_path=original_path, reference=reference, safe_source_receipts=safe,
        turnout_receipt=safe["voterTurnout_Electiondata"],
        files={name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
               for name, body in members.items()})
    for name, body in members.items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (ROOT / VERSION / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps(dict(native_towns=169, source_Total_separate=True, contextual_boundary_year=2024,
        derived_geometry_bytes=len(members[GEOMETRY]), original_sources_reacquired=False)))


if __name__ == "__main__":
    build()
