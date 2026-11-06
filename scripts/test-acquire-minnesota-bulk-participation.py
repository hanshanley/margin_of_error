import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "minnesota_acquire", Path(__file__).with_name("acquire-minnesota-bulk-participation.py"))
ACQUIRE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACQUIRE)


def parent():
    links = []
    for index, (label, name) in enumerate(ACQUIRE.SOURCES.items()):
        url = ("/Results/MediaFileLayout/Index?erselectionId=201" if name == "layout.txt"
               else f"https://electionresultsfiles.sos.mn.gov/20261103/table{index}.txt")
        links.append(f'<a href="{url}"><span>{label}</span></a>')
    return (ACQUIRE.IDENTITY + "".join(links)).encode()


class MinnesotaAcquisitionTests(unittest.TestCase):
    def test_requires_actual_unique_election_specific_declarations(self):
        self.assertEqual(len(ACQUIRE.declared_sources(parent())), 7)
        for body in (
            parent().replace(b"November 3, 2026", b"August 11, 2026"),
            parent().replace(b"Precinct Reporting Statistics", b"Other Statistics"),
            parent() + b'<a href="/other">Counties</a>',
            parent().replace(b"/20261103/", b"/20260811/"),
            parent().replace(b"electionresultsfiles.sos.mn.gov", b"unrelated.example"),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                ACQUIRE.declared_sources(body)

    def test_unreported_zero_and_nonzero_placeholders_do_not_become_ballots(self):
        body = (b"MN;01;0005;REPORTED;1;100;2;40;12;0;0;52\n"
                b"MN;01;0010;MISSING;0;150;0;0;0;0;0;0\n"
                b"MN;02;0005;ESTIMATE;0;200;0;0;0;0;0;99\n")
        result = ACQUIRE.statistic_inventory(body)
        self.assertEqual(result["reported_total_number_voted_subtotal"], 52)
        self.assertEqual(result["reported_statistic_rows"], 1)
        self.assertEqual(result["unreported_statistic_rows"], 2)
        self.assertEqual(result["unreported_native_nonzero_totals"], [
            {"county_id": "02", "precinct_id": "0005", "native_total_number_voted": "99"}])

    def test_reported_true_zero_survives_and_county_is_part_of_precinct_identity(self):
        result = ACQUIRE.statistic_inventory(
            b"MN;01;0005;ZERO;1;0;0;0;0;0;0;0\nMN;02;0005;OTHER;1;10;0;1;0;0;0;1\n")
        self.assertEqual(result["reported_statistic_rows"], 2)
        self.assertEqual(result["reported_total_number_voted_subtotal"], 1)

    def test_duplicate_identity_wrong_schema_flags_or_numbers_fail_closed(self):
        row = b"MN;01;0005;NAME;1;100;2;40;12;0;0;52\n"
        for body in (b"", row + row, row.replace(b";1;100", b";2;100"),
                     row.replace(b";52\n", b";-1\n"), row.replace(b";0;52\n", b";52\n")):
            with self.subTest(body=body), self.assertRaises(ValueError):
                ACQUIRE.statistic_inventory(body)


if __name__ == "__main__":
    unittest.main()
