import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference", ROOT/"scripts/manchester-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
inputs = json.loads((ROOT/core.VERSION/"inputs.json").read_bytes())


def fixture():
    def read(name):
        return json.loads((ROOT/core.VERSION/name).read_bytes())
    return [copy.deepcopy(inputs), json.loads(gzip.decompress(
        (ROOT/inputs["complete_count_query_path"]).read_bytes())),
        read("manchester-wards2022-full-aggregate-original.geojson"),
        read("manchester-wards2022-native-projection-original.json"),
        read("manchester-wards2022-native-ids.json"),read("manchester-wards2022-native-count.json"),
        read("manchester-official-actual-ward-layer.json"),read("manchester-official-mapserver-layers.json"),
        read("manchester-current-ward-lines-safe-declaration.json"),
        read("manchester-native-projection-overlap-check-01.json")]


class WardReferenceTests(unittest.TestCase):
    def test_complete_source_identity_and_all_other_city_rows_are_retained(self):
        result = core.load()
        self.assertEqual(result["summary"]["mapped_wards"],12)
        self.assertEqual(result["summary"]["mapped_raw_ward_total_sum"],38562)
        self.assertEqual(len(result["retained_city_source_queries"]),242)
        self.assertEqual(len(result["retained_ward_source_rows"]),37)
        held = [row for row in result["complete_ward_disposition_queries"] if row["city"] != "Manchester"]
        self.assertEqual(len(held),25)
        self.assertEqual({f["properties"]["native_object_id"] for f in result["geojson"]["features"]},
                         set(range(25,37)))
        self.assertEqual({f["properties"]["native_ward_number"] for f in result["geojson"]["features"]},
                         set(range(1,13)))

    def test_source_disagreement_federal_cells_and_missing_denominators_are_not_repaired(self):
        result = core.review(*fixture())
        ward7 = next(f["properties"] for f in result["geojson"]["features"] if f["properties"]["unit"]=="Ward 7")
        self.assertEqual(ward7["ballots"],2712)
        self.assertEqual(ward7["native_record"]["election_day"]+ward7["native_record"]["absentee"],2797)
        self.assertEqual(sum(f["properties"]["native_record"]["federal_only"]
                             for f in result["geojson"]["features"]),76)
        self.assertTrue(all(f["properties"]["denominator"] is None and
                            f["properties"]["reported_pct"] is None for f in result["geojson"]["features"]))

    def test_every_vertex_and_all_native_boundary_overlaps_are_preserved(self):
        source = fixture()
        result = core.review(*source)
        self.assertEqual(result["summary"]["native_vertices_verified"],3789)
        self.assertEqual(len(result["native_overlap_queries"]),6)
        self.assertEqual([f["geometry"] for f in result["geojson"]["features"]],
                         [f["geometry"] for f in source[2]["features"]])
        self.assertTrue(all(f["properties"]["reference_geometry"]["certified_legal_boundaries"] is False
                            for f in result["geojson"]["features"]))

    def test_changed_election_layer_rates_identity_or_coordinates_are_rejected(self):
        changes = [
            lambda x:x[0].update(source_count_election_date="2024-11-05"),
            lambda x:x[0].update(reference_boundary_vintage=2026),
            lambda x:x[0].update(source_geometry_repaired=True),
            lambda x:x[6].update(name="Historic Sites"),
            lambda x:x[2]["features"][0]["properties"].update(WardNumber=25),
            lambda x:x[1]["ward_rows"][0].update(reported_pct=100),
            lambda x:x[1]["ward_rows"][0].update(source_count=None),
            lambda x:x[2]["features"][0]["geometry"]["coordinates"][0][1].__setitem__(0,-71.0),
        ]
        for change in changes:
            data = fixture()
            change(data)
            with self.assertRaises((ValueError,KeyError,TypeError)):
                core.review(*data)


if __name__ == "__main__":
    unittest.main()
