"""Focused failures for the new native-reference join, not another candidate reduction."""

import gzip
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alaska_display", ROOT / "scripts/alaska-native-display.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def fixture():
    base = ROOT / core.VERSION
    def read(name):
        body = (base / name).read_bytes()
        return json.loads(gzip.decompress(body) if name.endswith(".gz") else body)
    return [read("originals/official-precinct-shapes.json.gz"),
        read("qualified-source-count-queries.json.gz"), read("originals/precincts-original.json.gz"),
        read("held-topology-queries.json"), read("independent-integer-coordinates.json"),
        read("native-display-format-facts.json")]


class AlaskaDisplayTests(unittest.TestCase):
    def test_all_queries_preserve_geographic_pooled_and_federal_scopes(self):
        data = core.load()
        self.assertEqual(len(data["complete_shape_queries"]), 402)
        self.assertEqual(len(data["complete_count_queries"]), 523)
        self.assertEqual(sum(r["map_approved"] for r in data["complete_shape_queries"]), 81)
        self.assertEqual(data["summary"]["geometry_holds"], 321)
        self.assertEqual(data["summary"]["source_ballots"], 215906)
        self.assertTrue(all(f["properties"]["denominator"] is None
                            and f["properties"]["reported_pct"] is None
                            for f in data["geojson"]["features"]))

    def test_source_zero_survives_without_becoming_missing(self):
        f = fixture()
        row = next(r for r in f[1] if r["source_precinct_id"] == "08-035")
        contest = f[2]["contestNames"].index("U.S. Representative")
        unit = next(r for r in f[2]["precincts"] if r["number"] == row["source_precinct_id"])
        record = next(r for r in unit["contests"] if r["n"] == contest)
        other = next(r for r in f[1] if r["reporting_unit_kind"] == "federal_overseas")
        other["ballots"] += row["ballots"]
        row["ballots"] = record["b"] = 0
        result = core.review(*f)
        p = next(g["properties"] for g in result["geojson"]["features"]
                 if g["properties"]["native_precinct_id"] == "08-035")
        self.assertEqual(p["ballots"], 0)
        self.assertIsNone(p["reported_pct"])

    def test_missing_counts_wrong_election_and_pool_promotion_reject(self):
        for mutate in [
            lambda f: f[1][0].update(ballots=None),
            lambda f: f[1][0].update(reported_pct=50),
            lambda f: f[1][0].update(reporting_unit_kind="pooled_district_absentee"),
            lambda f: f[2].update(name="Alaska 2024 General Election"),
            lambda f: f[2]["precincts"][0].update(number=f[2]["precincts"][1]["number"]),
            lambda f: f[5]["contract"].update(coordinate_pair_order="latitude longitude"),
        ]:
            with self.subTest(mutate=mutate):
                f = fixture()
                mutate(f)
                with self.assertRaises(ValueError):
                    core.review(*f)

    def test_new_ring_roles_coordinate_edits_and_false_approvals_reject(self):
        for change in ("extra_path", "coordinate", "promote_hold"):
            f = fixture()
            shape = next(r for r in f[0] if r["number"] == "08-035")
            if change == "extra_path":
                shape["coords"][0].append(shape["coords"][0][0])
            elif change == "coordinate":
                shape["coords"][0][0] = shape["coords"][0][0].replace("-149", "-148", 1)
                if shape["coords"][0][0] == next(
                        r for r in fixture()[0] if r["number"] == "08-035")["coords"][0][0]:
                    shape["coords"][0][0] = "0 0 " + shape["coords"][0][0]
            else:
                next(r for r in f[3]["queries"] if not r["topology_valid_without_repairs"])[
                    "topology_valid_without_repairs"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                core.review(*f)


if __name__ == "__main__":
    unittest.main()
