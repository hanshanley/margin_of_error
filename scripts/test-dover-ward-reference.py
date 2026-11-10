import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dover", ROOT / "scripts/dover-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class DoverWardTests(unittest.TestCase):
    def setUp(self):
        source = ROOT / core.VERSION
        inputs = json.loads((source / "inputs.json").read_bytes())
        self.base = json.loads(gzip.decompress((ROOT / inputs["previous_ward_query_path"]).read_bytes()))
        names = [
            "granit-dover2022-full-geographic-original.geojson",
            "granit-dover2022-full-native-projected-original.json",
            "granit-dover2022-native-count.json", "granit-dover2022-native-ids.json",
            "granit-2022-voting-ward-layer11.json", "dover-granit-safe-source-declaration.json",
            "complete-native-ward-reference-review.json", "granit-declared-3437-4326-transformations.json"]
        self.arguments = [self.base, *[json.loads((source / name).read_bytes()) for name in names]]

    def test_six_direct_joins_preserve_every_old_source_and31_features(self):
        result = core.load()
        self.assertEqual(result["geojson"]["features"][:31], self.base["geojson"]["features"])
        self.assertEqual(result["retained_city_source_queries"], self.base["retained_city_source_queries"])
        self.assertEqual(result["retained_ward_source_rows"], self.base["retained_ward_source_rows"])
        self.assertEqual(result["summary"]["mapped_wards"], 37)
        self.assertEqual(result["summary"]["held_table_only_ward_rows"], 0)
        self.assertEqual(sum(f["properties"]["ballots"] for f in result["geojson"]["features"][31:]), 15941)

    def test_rejects_old_layer_false_legal_claims_or_wrong_datum(self):
        for change in [
            lambda args: args[5].update(id=5),
            lambda args: args[6].update(certified_legal2026_precinct_boundaries=True),
            lambda args: args[6].update(source_reference_vintage=2020),
            lambda args: args[8]["transformations"][0]["geoTransforms"][0].update(wkid=1188),
        ]:
            arguments = copy.deepcopy(self.arguments)
            change(arguments)
            with self.assertRaises(ValueError):
                core.review(*arguments)

    def test_rejects_fid_as_ward_identity_extra_population_fields_and_changed_edges(self):
        for change in [
            lambda args: args[1]["features"][0]["properties"].update(district="Dover Ward 280"),
            lambda args: args[1]["features"][0]["properties"].update(Pop2020=1),
            lambda args: args[1]["features"][0]["geometry"]["coordinates"][0].pop(2),
        ]:
            arguments = copy.deepcopy(self.arguments)
            change(arguments)
            with self.assertRaises(ValueError):
                core.review(*arguments)

    def test_rejects_repaired_counts_inferred_rates_and_changed_pair_decisions(self):
        for change in [
            lambda args: next(row for row in args[0]["retained_ward_source_rows"]
                              if row["city"] == "Dover").update(source_count=1),
            lambda args: next(row for row in args[0]["retained_ward_source_rows"]
                              if row["city"] == "Dover").update(reported_pct=100),
            lambda args: args[7]["all_native_pair_decisions"][0].update(native_overlap_area=1),
        ]:
            arguments = copy.deepcopy(self.arguments)
            change(arguments)
            with self.assertRaises(ValueError):
                core.review(*arguments)


if __name__ == "__main__":
    unittest.main()
