import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/new-hampshire-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class WardReferenceTests(unittest.TestCase):
    def setUp(self):
        version = ROOT/core.VERSION
        inputs = json.loads((version/"inputs.json").read_bytes())
        self.base = json.loads(gzip.decompress((ROOT/inputs["previous_ward_query_path"]).read_bytes()))
        names = ["concord-full-aggregate-original.geojson","concord-native-projection-original.json",
            "concord-native-count.json","concord-native-ids.json","concord-actual-ward-layer-original.json",
            "concord-current-ward-safe-declaration.json","concord-esri108190-independent-projection-operation.json",
            "concord-native-datum-transformations-original.json","concord-all10-native-ward-reference-review-01.json"]
        self.arguments = [self.base,*[json.loads((version/name).read_bytes()) for name in names]]

    def test_retains_every_old_source_row_and_geometry_with_ten_direct_new_ward_joins(self):
        data = core.load()
        self.assertEqual(data["retained_city_source_queries"],self.base["retained_city_source_queries"])
        self.assertEqual(data["retained_ward_source_rows"],self.base["retained_ward_source_rows"])
        self.assertEqual(data["geojson"]["features"][:12],self.base["geojson"]["features"])
        self.assertEqual(data["summary"]["mapped_wards"],22)
        self.assertEqual(data["summary"]["held_table_only_ward_rows"],15)
        self.assertEqual(data["summary"]["native_vertices_verified"],7936)
        concord = data["geojson"]["features"][12:]
        self.assertEqual(sum(f["properties"]["ballots"] for f in concord),19234)
        self.assertTrue(all(f["properties"]["denominator"] is None and f["properties"]["reported_pct"] is None for f in concord))

    def test_rejects_object_id_as_ward_identity_and_population_fields(self):
        for change in [
            lambda geo:geo["features"][0]["properties"].update(Ward=3),
            lambda geo:geo["features"][0]["properties"].update(Population=1),
        ]:
            arguments = copy.deepcopy(self.arguments)
            change(arguments[1])
            with self.assertRaises(ValueError):
                core.review(*arguments)

    def test_rejects_default_null_datum_and_false_current_legal_claims(self):
        for index,key,value in [(7,"direction","forward"),(6,"certified_legal2026_precinct_boundaries",True)]:
            arguments = copy.deepcopy(self.arguments)
            arguments[index][key] = value
            with self.assertRaises(ValueError):
                core.review(*arguments)

    def test_rejects_repaired_source_counts_inferred_rates_and_changed_overlap_decisions(self):
        for change in [
            lambda args:args[0]["retained_ward_source_rows"][12].update(source_count=1),
            lambda args:args[0]["retained_ward_source_rows"][12].update(reported_pct=100),
            lambda args:next(row for row in args[-1]["complete_pairwise_queries"]
                if row["native_projected_US_survey_feet_squared"] > 0).update(native_projected_US_survey_feet_squared=0),
        ]:
            arguments = copy.deepcopy(self.arguments)
            change(arguments)
            with self.assertRaises(ValueError):
                core.review(*arguments)


if __name__ == "__main__":
    unittest.main()
