import copy
from pathlib import Path
import tempfile
import unittest

from participation_intake.acs_context import TABLES, cell, county_record, parse_table
from participation_intake.contract import IntakeError
from participation_intake.resident import add_precinct_context, compile_counties, name_key
from participation_intake.small_area import block_group_rows, build_block_group_index
from participation_intake.precinct_context import estimate_context


def fixture():
    tables = {table: {f"{index:03d}": cell("0", "0") for index in range(1, count+1)}
              for table, count in TABLES.items()}
    tables["B19013"]["001"] = cell("50000", "1000", median=True)
    for table in ("B03002", "B01001"):
        tables[table]["001"] = cell("100", "-555555555")
    for index, value in [(3, 60), (4, 10), (6, 5), (9, 5), (12, 20)]:
        tables["B03002"][f"{index:03d}"] = cell(str(value), "1")
    for index, value in [(3, 10), (7, 20), (20, 30), (31, 40)]:
        tables["B01001"][f"{index:03d}"] = cell(str(value), "1")
    tables["B15003"]["001"] = cell("70", "3")
    for index, value in [(22, 20), (23, 5), (25, 3)]:
        tables["B15003"][f"{index:03d}"] = cell(str(value), "1")
    tables["B19001"]["001"] = cell("50", "2")
    tables["B19001"]["002"] = cell("10", "1")
    tables["B19001"]["013"] = cell("40", "1")
    return tables


class ResidentContextTests(unittest.TestCase):
    def test_native_zero_unknown_and_controlled_moe_remain_distinct(self):
        self.assertEqual(cell("0", "0")["estimate"], 0)
        unknown = cell("-666666666", "-222222222")
        self.assertIsNone(unknown["estimate"])
        self.assertEqual(unknown["native_estimate_literal"], "-666666666")
        controlled = cell("100", "-555555555")
        self.assertEqual(controlled["estimate"], 100)
        self.assertIsNone(controlled["margin_of_error"])
        self.assertEqual(controlled["moe_status"], "controlled_estimate_no_sampling_moe")

    def test_open_ended_income_is_not_an_exact_currency_value(self):
        low = cell("2499", "-333333333", median=True)
        high = cell("250001", "-333333333", median=True)
        self.assertIsNone(low["estimate"])
        self.assertEqual(low["upper_bound"], 2500)
        self.assertEqual(high["lower_bound"], 250000)
        self.assertEqual(high["native_estimate_literal"], "250001")
        self.assertIsNone(high["margin_of_error"])

    def test_exclusive_race_origins_and_correct_age_education_universes(self):
        row = county_record("01001", fixture())
        self.assertEqual(sum(group["estimate"] for group in row["race_ethnicity"]["groups"]), 100)
        self.assertEqual(len(row["race_ethnicity"]["groups"]), 8)
        self.assertEqual({group["id"]: group["estimate"] for group in row["age"]["groups"]},
                         {"under18": 10, "18_64": 60, "65plus": 30})
        self.assertEqual(row["education"]["bachelors_or_higher_pct"], 40)
        self.assertEqual(row["education"]["source_total"], 70)
        self.assertIsNone(row["voter_participation_rate"])

    def test_source_age_partition_disagreement_is_retained_not_repaired(self):
        tables = fixture()
        tables["B01001"]["007"] = cell("21", "1")
        row = county_record("01001", tables)
        self.assertEqual(row["age"]["groups"][1]["estimate"], 61)
        self.assertEqual(row["age"]["source_total"], 100)
        self.assertEqual(next(value for value in row["conflicts"]
            if value["code"] == "published_age_partition_residual")["residual"], 1)

    def test_native_geography_filter_and_duplicate_identity_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "table.dat"
            body = "GEO_ID|B19013_E001|B19013_M001\n0500000US01001|50000|1000\n0500000US72001|0|0\n"
            path.write_text(body)
            rows, inventory = parse_table(path, "B19013")
            self.assertEqual(list(rows), ["01001"])
            self.assertEqual(inventory["territory_county_rows_excluded"], 1)
            path.write_text(body + "0500000US01001|50000|1000\n")
            with self.assertRaises(IntakeError):
                parse_table(path, "B19013")

    def test_exact_native_county_join_does_not_pad_election_ordinals_into_fips(self):
        native = dict(contract="geographic.resident_context.v1", source_period="2020-2024",
            income_dollar_year=2024, records=[county_record("01073", fixture())], limitations=[])
        labels = [dict(USPS="AL", GEOID="01073", NAME="Jefferson County")]
        geometry = dict(AL=dict(features=[dict(properties=dict(
            key="01073", state_code="AL", boundary_year=2024, aliases=["Jefferson"]))]))
        files = compile_counties(native, labels, geometry)
        import gzip, json
        row = json.loads(gzip.decompress(files["states/AL.json.gz"]))["counties"][0]
        self.assertEqual(row["map_join"]["feature_key"], "01073")
        self.assertNotEqual(row["map_join"]["feature_key"], "01001")
        self.assertIn(name_key("Jefferson"), row["name_keys"])
        geometry["AL"]["features"][0]["properties"]["key"] = "01001"
        with self.assertRaises(IntakeError):
            compile_counties(native, labels, geometry)

    def test_native_block_group_zero_unknown_and_duplicate_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "table.dat"
            path.write_text("GEO_ID|B19013_E001|B19013_M001\n"
                "1500000US010010201001|0|0\n"
                "1500000US010010201002|-666666666|-222222222\n"
                "0500000US01001|50000|1000\n")
            rows = list(block_group_rows(path, "B19013"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], ("010010201001", [["0", "0"]]))
            self.assertEqual(rows[1][1][0][0], "-666666666")
            path.write_text("GEO_ID|B19013_E001|B19013_M001|B19013_E001\n")
            with self.assertRaises(IntakeError):
                list(block_group_rows(path, "B19013"))

    def test_complete_block_group_index_requires_all_native_table_identities(self):
        import json
        from participation_intake.contract import pin
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "objects").mkdir()
            for table, count in TABLES.items():
                fields = ["GEO_ID"] + [f"{table}_{kind}{i:03d}"
                    for i in range(1, count+1) for kind in ("E", "M")]
                text = "|".join(fields) + "\n"
                text += "|".join(["1500000US010010201001"] + ["0", "0"]*count) + "\n"
                if table == "B19013":
                    text += "|".join(["1500000US010010201002"] + ["0", "0"]*count) + "\n"
                body = text.encode()
                receipt = pin(body)
                (root / "objects" / receipt["sha256"]).write_bytes(body)
                (root / (table+"-receipt.json")).write_text(json.dumps(receipt))
            with self.assertRaises(IntakeError):
                build_block_group_index(root, root / "index")
            self.assertFalse((root / "index/summary.json").exists())

    def test_population_proxy_context_uses_income_bins_never_averaged_medians(self):
        import json, sqlite3
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cells.sqlite3"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE cells(geoid TEXT,table_id TEXT,native_pairs TEXT)")
            for table, values in fixture().items():
                pairs = [[value["native_estimate_literal"], value["native_moe_literal"]]
                    for _, value in sorted(values.items())]
                db.execute("INSERT INTO cells VALUES(?,?,?)",
                    ("010010201001", table, json.dumps(pairs)))
            db.commit(); db.close()
            crosswalk = dict(state_code="AL", limitations=[], links=[dict(reference_key="native-unit-01",
                census_2020_block_group="010010201001", population_fraction="1/2",
                housing_proxy_fraction="1/2", assigned_population=50, assigned_housing_units=25)])
            row = estimate_context(crosswalk, path)["records"][0]
            self.assertEqual(row["resident_population"]["estimate"], 50)
            self.assertEqual(row["education"]["bachelors_or_higher_pct"], 40)
            self.assertIsNone(row["median_household_income"]["estimate"])
            self.assertEqual(row["modeled_income_median_band"]["lower_bound"], 75000)
            self.assertEqual(row["modeled_income_median_band"]["upper_bound"], 100000)
            self.assertFalse(row["income_medians_averaged"])
            self.assertIsNone(row["voter_participation_rate"])
            self.assertIsNone(row["resident_population"]["margin_of_error"])

    def test_missing_source_block_group_withholds_instead_of_zero_filling(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cells.sqlite3"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE cells(geoid TEXT,table_id TEXT,native_pairs TEXT)")
            db.commit(); db.close()
            crosswalk = dict(state_code="AL", limitations=[], links=[dict(reference_key="native-unit-01",
                census_2020_block_group="010010201001", population_fraction="1",
                housing_proxy_fraction="1", assigned_population=50, assigned_housing_units=25)])
            row = estimate_context(crosswalk, path)["records"][0]
            self.assertIsNone(row["resident_population"]["estimate"])
            self.assertEqual(row["missing_2024_block_groups"], ["010010201001"])
            self.assertIsNone(row["modeled_income_median_band"])
            crosswalk["reference_keys"] = ["native-unit-01", "native-unit-without-proxy"]
            rows = estimate_context(crosswalk, path)["records"]
            self.assertEqual(len(rows), 2)
            held = next(value for value in rows if value["geography"]["reference_key"] == "native-unit-without-proxy")
            self.assertIsNone(held["resident_population"]["estimate"])
            self.assertFalse(held["population_proxy_available"])

    def test_complete_county_packet_reproduces_and_rejects_changed_original(self):
        import json, zipfile
        from participation_intake.acs_context import build_county_context
        from participation_intake.context_package import package_county_context, reproduce_county_package
        from participation_intake.contract import digest, encoded, pin
        from participation_intake.resident import compressed
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store, references, runtime = [root / name for name in ("source", "references", "runtime")]
            (store / "objects").mkdir(parents=True)
            (references / "geometry").mkdir(parents=True)
            runtime.mkdir()
            for table, count in TABLES.items():
                fields = ["GEO_ID"] + [f"{table}_{kind}{i:03d}"
                    for i in range(1, count+1) for kind in ("E", "M")]
                values = [value for cell in fixture()[table].values()
                    for value in (cell["native_estimate_literal"], cell["native_moe_literal"])]
                body = ("|".join(fields) + "\n" +
                    "|".join(["0500000US01001", *values]) + "\n").encode()
                receipt = pin(body)
                (store / "objects" / receipt["sha256"]).write_bytes(body)
                (store / (table+"-receipt.json")).write_bytes(encoded(receipt))
            native = build_county_context(store)
            query = root / "county-native-context.json.gz"
            query.write_bytes(compressed(encoded(native)))
            identities = [dict(USPS="AL", GEOID="01001", NAME="Autauga County")]
            identity = references / "complete-2024-county-identities.json.gz"
            identity.write_bytes(compressed(encoded(identities)))
            original = references / "gazetteer-2024-national-counties.zip"
            with zipfile.ZipFile(original, "w") as archive:
                archive.writestr("counties.txt", "USPS\tGEOID\tNAME\nAL\t01001\tAutauga County\n")
            geometry = dict(features=[dict(properties=dict(
                key="01001", state_code="AL", boundary_year=2024))])
            geometry_file = references / "geometry/county-AL.geojson"
            geometry_file.write_bytes(encoded(geometry))
            files = compile_counties(native, identities, {"AL": geometry})
            for name, body in files.items():
                path = runtime / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            pins = {name: pin(body) for name, body in files.items()}
            description = dict(files=pins, record_contract="geographic.resident_context.v1",
                version=digest(encoded(dict(files=pins, contract="geographic.resident_context.v1"))))
            (runtime / "dataset.json").write_bytes(encoded(description))
            (runtime / "compilation.json").write_bytes(encoded(dict(
                native_query=pin(query.read_bytes()), county_identity_original=pin(identity.read_bytes()),
                approved_geometry={"geometry/county-AL.geojson": pin(geometry_file.read_bytes())})))
            output = root / "complete.zip"
            report = package_county_context(store, query, references, runtime, output)
            self.assertFalse(report["metadata_only"])
            extracted = root / "extracted"
            with zipfile.ZipFile(output) as archive:
                archive.extractall(extracted)
            proof = reproduce_county_package(extracted)
            self.assertEqual(proof["counties"], 1)
            self.assertEqual(proof["complete_originals"], 6)
            held_original = next((extracted / "source-store/objects").iterdir())
            held_original.write_bytes(b"changed")
            with self.assertRaises(IntakeError):
                reproduce_county_package(extracted)
            prior = output.read_bytes()
            with self.assertRaises(IntakeError):
                package_county_context(store, query, references, runtime, output)
            self.assertEqual(output.read_bytes(), prior)

    def test_precinct_packet_rejects_metadata_only_or_unverified_frames(self):
        from participation_intake.precinct_package import package_precinct_context
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "summary.json").write_text('{"reference_registry":{"states":{}},"states":{}}')
            proof = root / "proof.json"
            proof.write_text('{"status":"awaiting_verification","records":0}')
            with self.assertRaises(IntakeError) as error:
                package_precinct_context(root, root, root, root / "absent.sqlite3",
                    root / "absent.zip", proof, proof, root / "absent.py", root / "complete.zip")
            self.assertEqual(error.exception.code, "context_verification")
            self.assertFalse((root / "complete.zip").exists())

    def test_runtime_extension_preserves_counties_zeros_missingness_and_held_reference(self):
        import gzip, json
        native = dict(contract="geographic.resident_context.v1", source_period="2020-2024",
            income_dollar_year=2024, records=[county_record("01001", fixture())], limitations=[])
        county_reference = dict(AL=dict(features=[dict(properties=dict(
            key="01001", state_code="AL", boundary_year=2024))]))
        files = compile_counties(native, [dict(USPS="AL", GEOID="01001", NAME="Autauga County")], county_reference)
        original_counties = json.loads(gzip.decompress(files["states/AL.json.gz"]))["counties"]
        profile = dict(geography=dict(reference_key="native-1", state_code="AL"),
            resident_population=dict(estimate=0), modeled_income_median_band=None,
            source_block_groups=["010010201001"], exact_weighted_source_cells={"large": "audit"},
            resident_composition_is_not_voter_composition=True)
        context = dict(state_code="AL", source_period="2020-2024", weight_year=2020,
            limitations=[], source_reference=dict(sha256="a"*64), records=[profile])
        reference = dict(features=[dict(properties=dict(key=key, state_code="AL", unit=key))
            for key in ("native-1", "native-held")])
        held = dict(held_references=[dict(key="native-held", reason="invalid_native_reference")])
        extended = add_precinct_context(files, {"AL": context}, {"AL": reference}, {"AL": held})
        actual = json.loads(gzip.decompress(extended["states/AL.json.gz"]))
        self.assertEqual(actual["counties"], original_counties)
        self.assertEqual(actual["precincts"][0]["resident_population"]["estimate"], 0)
        self.assertIsNone(actual["precincts"][0]["modeled_income_median_band"])
        self.assertNotIn("exact_weighted_source_cells", actual["precincts"][0])
        self.assertEqual(actual["precinct_reference_holds"], held["held_references"])
        self.assertEqual(json.loads(extended["index.json"])["states"]["AL"]["population_profiles"], 1)
        context["records"].append(profile)
        with self.assertRaises(IntakeError):
            add_precinct_context(files, {"AL": context}, {"AL": reference}, {"AL": held})


if __name__ == "__main__":
    unittest.main()
