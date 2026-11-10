import copy
import unittest

from participation_intake.contract import IntakeError
from participation_intake.crosswalk import population_weights


def polygon(key, left, right):
    return dict(type="Feature", properties=dict(key=key, state_code="DC"),
        geometry=dict(type="Polygon", coordinates=[[
            [left, 38.8], [right, 38.8], [right, 38.9], [left, 38.9], [left, 38.8]]]))


def blocks():
    return [dict(GEOID="110010001001"+suffix, STATE="11", POP100=pop, HU100=housing,
        INTPTLON=str(lon), INTPTLAT=str(lat)) for suffix, pop, housing, lon, lat in [
            ("000", 75, 30, -77.09, 38.85), ("001", 25, 10, -77.01, 38.85),
            ("002", 0, 0, -77.08, 38.83)]]


class CrosswalkTests(unittest.TestCase):
    def test_population_and_housing_fractions_use_full_block_group_denominators(self):
        source = [polygon("A", -77.1, -77.05), polygon("B", -77.05, -77.0)]
        before = copy.deepcopy(source)
        result = population_weights(source, blocks(), "DC", "11")
        self.assertEqual(source, before)
        self.assertEqual({row["reference_key"]: row["population_fraction"] for row in result["links"]},
            {"A": "3/4", "B": "1/4"})
        self.assertEqual(result["complete_population"], 100)
        self.assertEqual(result["point_decisions"]["unique_reference"], 3)
        self.assertEqual(result["point_decisions"]["unique_reference_population"], 100)

    def test_overlapping_reference_points_remain_unallocated(self):
        result = population_weights([polygon("A", -77.1, -77.0), polygon("B", -77.1, -77.0)],
            blocks(), "DC", "11")
        self.assertEqual(result["links"], [])
        self.assertEqual(result["point_decisions"]["ambiguous_reference_population"], 100)
        self.assertFalse(result["ambiguous_points_allocated"])

    def test_exact_native_shared_edge_stays_ambiguous_without_projected_chord_assignment(self):
        source = [polygon("south", -77.1, -77.0), polygon("north", -77.1, -77.0)]
        source[0]["geometry"]["coordinates"] = [[
            [-77.1, 38.8], [-77.0, 38.8], [-77.0, 38.85], [-77.1, 38.85], [-77.1, 38.8]]]
        source[1]["geometry"]["coordinates"] = [[
            [-77.1, 38.85], [-77.0, 38.85], [-77.0, 38.9], [-77.1, 38.9], [-77.1, 38.85]]]
        rows = [dict(GEOID="110010001001000", STATE="11", POP100=10, HU100=4,
            INTPTLON="-77.05", INTPTLAT="38.85")]
        decisions = []
        result = population_weights(source, rows, "DC", "11", point_query_writer=decisions.append)
        self.assertEqual(result["links"], [])
        self.assertEqual(result["point_decisions"]["ambiguous_reference_population"], 10)
        self.assertEqual(decisions, [dict(census_2020_block="110010001001000",
            status="ambiguous_reference", reference_keys=["north", "south"])])

    def test_unknown_weights_are_not_observed_zeros_or_cross_state_inputs(self):
        source = [polygon("A", -77.1, -77.0)]
        rows = blocks()
        rows[0]["POP100"] = None
        with self.assertRaises(IntakeError):
            population_weights(source, rows, "DC", "11")
        with self.assertRaises(IntakeError):
            population_weights(source, blocks(), "DC", "27")


if __name__ == "__main__":
    unittest.main()
