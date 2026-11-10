import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/nashua-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class NashuaWardTests(unittest.TestCase):
    def setUp(self):
        version = ROOT/core.VERSION
        inputs = json.loads((version/"inputs.json").read_bytes())
        self.base = json.loads(gzip.decompress((ROOT/inputs["previous_ward_query_path"]).read_bytes()))
        names = ["nashua-adopted2021-full-aggregate-original.geojson",
            "nashua-adopted2021-native-projection-original.json","nashua-adopted2021-native-count.json",
            "nashua-adopted2021-native-ids.json","adopted-ward-layer7-original.json",
            "nashua-independent-adopted-ward-safe-declaration.json",
            "nashua-all9-adopted-native-ward-reference-review-01.json"]
        self.arguments = [self.base,*[json.loads((version/name).read_bytes()) for name in names]]

    def test_retains_every_old_source_and_feature_with_nine_literal_adopted_ward_joins(self):
        data = core.load()
        self.assertEqual(data["geojson"]["features"][:22],self.base["geojson"]["features"])
        self.assertEqual(data["retained_city_source_queries"],self.base["retained_city_source_queries"])
        self.assertEqual(data["retained_ward_source_rows"],self.base["retained_ward_source_rows"])
        self.assertEqual(data["summary"]["mapped_wards"],31)
        self.assertEqual(data["summary"]["held_table_only_ward_rows"],6)
        self.assertEqual(data["summary"]["native_vertices_verified"],16192)
        new = data["geojson"]["features"][22:]
        self.assertEqual(sum(f["properties"]["ballots"] for f in new),33849)
        self.assertEqual(sum(f["properties"]["native_record"]["federal_only"] for f in new),92)

    def test_rejects_proposed_point_and_parcel_roles_or_false_legal_claims(self):
        for index,key,value in [(5,"id",6),(5,"name","Proposed Ward Boundaries"),
                                (6,"certified_legal2026_precinct_boundaries",True)]:
            args = copy.deepcopy(self.arguments)
            args[index][key] = value
            with self.assertRaises(ValueError):
                core.review(*args)

    def test_rejects_object_id_as_ward_identity_and_population_fields(self):
        for change in [
            lambda geo:geo["features"][0]["properties"].update(Ward=1,Wardtxt="1"),
            lambda geo:geo["features"][0]["properties"].update(Pop2020=1),
        ]:
            args = copy.deepcopy(self.arguments)
            change(args[1])
            with self.assertRaises(ValueError):
                core.review(*args)

    def test_rejects_repaired_raw_counts_inferred_rates_and_changed_pair_decisions(self):
        for change in [
            lambda args:next(r for r in args[0]["retained_ward_source_rows"]
                if r["city"]=="Nashua" and r["native_ward"]==3).update(source_count=3573),
            lambda args:next(r for r in args[0]["retained_ward_source_rows"]
                if r["city"]=="Nashua").update(reported_pct=100),
            lambda args:args[-1]["complete_pairwise_queries"][0].update(native_projected_square_meters=1),
        ]:
            args = copy.deepcopy(self.arguments)
            change(args)
            with self.assertRaises(ValueError):
                core.review(*args)


if __name__ == "__main__":
    unittest.main()
