import datetime
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "nj_acquire", ROOT / "scripts/acquire-new-jersey-periodic-reports.py")
ACQUIRE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACQUIRE)


def link(county, date="11/05", suffix=""):
    slug = county.lower().replace(" ", "")
    return ('<a href="assets/pdf/periodic-report/2026/'
            + date.replace("/", "") + "-" + slug + suffix + '.pdf">'
            + county + " Report - " + date + "</a>")


def page(extra="", omitted=None):
    return ("<h3>2026 General Election</h3>"
            + "".join(link(county) for county in ACQUIRE.COUNTIES if county != omitted)
            + extra + "<h3>2026 Primary Election</h3>" + link("Atlantic", "11/06"))


class NewJerseyAcquisitionTests(unittest.TestCase):
    def parse(self, text):
        return ACQUIRE.catalog(text.encode(), datetime.date(2026, 11, 6))

    def test_selects_actual_latest_per_county_and_excludes_primary(self):
        election_night = link("Atlantic", "11/03").replace("Atlantic Report", "Atlantic Election Night Report")
        rows = self.parse(page(link("Atlantic", "11/06") + election_night))
        self.assertEqual(len(rows), 21)
        self.assertEqual(rows[0]["report_date"], "2026-11-06")
        self.assertEqual(rows[1]["report_date"], "2026-11-05")
        self.assertTrue(rows[0]["url"].endswith("1106-atlantic.pdf"))
        self.assertTrue(rows[1]["url"].endswith("1105-bergen.pdf"))

    def test_rejects_missing_county_ambiguous_same_day_and_future_reports(self):
        for html in (page(omitted="Bergen"), page(link("Atlantic", suffix="-different")),
                     page(link("Atlantic", "11/07")), page(link("Atlantic", "06/02"))):
            with self.assertRaises(ValueError):
                self.parse(html)

    def test_rejects_export_redirect_targets_and_repeated_county_urls(self):
        html = page()
        for replacement in ("https://example.com/atlantic.pdf", "javascript:alert(1)",
                            "assets/pdf/periodic-report/2026/1105-atlantic.pdf?token=x",
                            "assets/pdf/periodic-report/2026/1105-bergen.pdf"):
            changed = html.replace("assets/pdf/periodic-report/2026/1105-atlantic.pdf", replacement)
            with self.assertRaises(ValueError):
                self.parse(changed)

    def test_refuses_source_originals_in_repository_before_creating_directory(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            ACQUIRE.acquire(ROOT / "data/unreviewed-nj-originals")
        self.assertFalse((ROOT / "data/unreviewed-nj-originals").exists())


if __name__ == "__main__":
    unittest.main()
