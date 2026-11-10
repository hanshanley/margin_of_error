"""Register existing approved references without rerunning geometry preparation."""

import gzip
import json

from .adapters import field
from .contract import IntakeError, pin


def register(description, bodies):
    assets, features = {}, {}
    for identity, asset in description["assets"].items():
        if identity not in bodies:
            raise IntakeError("geometry_original_missing", "Supply the entire approved reference: " + identity)
        body = bodies[identity]
        actual = pin(body)
        if actual["sha256"] != asset["sha256"] or not asset.get("approval_evidence"):
            raise IntakeError("geometry_unreviewed", "Reference pin and existing approval must both match")
        raw = gzip.decompress(body) if body.startswith(b"\x1f\x8b") else body
        data = json.loads(raw)
        if data.get("type") != "FeatureCollection" or len(data["features"]) != asset["expected_features"]:
            raise IntakeError("geometry_identity", "Approved full feature inventory differs")
        keys = [field(feature, asset["key_path"]) for feature in data["features"]]
        if any(not isinstance(key, str) or not key for key in keys) or len(set(keys)) != len(keys):
            raise IntakeError("geometry_identity", "Reference keys must be complete and unique")
        assets[identity] = dict(asset, **actual)
        features[identity] = data["features"]
    mapping = description["identities"]
    parent_mapping = description.get("parents")
    identities, parents = {}, {}
    for feature in features[mapping["asset"]]:
        parts = [field(feature, path) for path in mapping["source_key_paths"]]
        if any(part is None or part == "" for part in parts):
            raise IntakeError("geographic_join", "Reference lacks a declared native source identity")
        key = "|".join(str(part) for part in parts)
        parent_id = field(feature, mapping["parent_path"]) if mapping.get("parent_path") else None
        row = dict(id=field(feature, mapping["id_path"]), name=field(feature, mapping["name_path"]),
            parent_id=parent_id, reference_id=mapping["asset"],
            feature_key=field(feature, assets[mapping["asset"]]["key_path"]),
            evidence=assets[mapping["asset"]]["approval_evidence"])
        if key in identities:
            raise IntakeError("geographic_join", "Duplicate declared native source identity")
        identities[key] = row
        if parent_mapping:
            parent = dict(name=field(feature, parent_mapping["name_path"]),
                state_code=parent_mapping["state_code"], level=parent_mapping["level"],
                parent_id=parent_mapping.get("parent_id"), reference_id=parent_mapping["asset"],
                feature_key=field(feature, parent_mapping["feature_key_path"]),
                evidence=assets[parent_mapping["asset"]]["approval_evidence"])
            if not parent_id or parent_id in parents and parents[parent_id] != parent:
                raise IntakeError("parent_scope", "Native parent bindings are absent or inconsistent")
            parents[parent_id] = parent
    for parent in parents.values():
        asset = assets[parent["reference_id"]]
        keys = {field(feature, asset["key_path"]) for feature in features[parent["reference_id"]]}
        if parent["feature_key"] not in keys:
            raise IntakeError("geographic_join", "Declared native parent is absent from the approved county reference")
    return dict(assets=assets, identities=identities, parents=parents,
        registration="existing_approved_references", new_geometry_acquisitions=0,
        topology_recomputed=False, source_geometry_repaired=False)
