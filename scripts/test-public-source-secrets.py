import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location(
    "source_secrets", Path(__file__).with_name("check-public-source-secrets.py"),
)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)
CANARY = b"AI" + b"za" + b"x" * 35


def archive_bytes(members):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return output.getvalue()


class PublicSourceSecretsTests(unittest.TestCase):
    def test_plaintext_reports_location_not_value(self):
        self.assertEqual(scanner.findings(b"header\nkey=" + CANARY, "source.html"), [("source.html", 2)])

    def test_binary_content_does_not_hide_key(self):
        self.assertEqual(scanner.findings(b"\0" + CANARY, "binary"), [("binary", 1)])

    def test_compressed_original_is_checked(self):
        archive = archive_bytes({"originals/page.html": b"key=" + CANARY, "counts.csv": b"votes\n123\n"})
        self.assertEqual(scanner.findings(archive, "complete.zip"), [("complete.zip!originals/page.html", 1)])

    def test_nested_archive_is_checked(self):
        archive = archive_bytes({"inner.zip": archive_bytes({"page.html": CANARY})})
        self.assertEqual(scanner.findings(archive, "outer.zip"), [("outer.zip!inner.zip!page.html", 1)])

    def test_sanitized_original_and_counts_pass_unchanged(self):
        content = b'key="[REDACTED_PUBLIC_SERVICE_KEY]"\nvotes,party\n123,DEM\n'
        self.assertEqual(scanner.findings(content, "page.html"), [])
        self.assertEqual(scanner.findings(archive_bytes({"page.html": content}), "complete.zip"), [])

    def test_removed_key_remains_detectable_in_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = ["git", "-c", "user.name=Source scanner test", "-c", "user.email=scanner@example.invalid"]
            subprocess.run(git + ["init", "-q", directory], check=True)
            path = root / "source.html"
            for content in [CANARY, b"[REDACTED_PUBLIC_SERVICE_KEY]"]:
                path.write_bytes(content)
                subprocess.run(git + ["add", "source.html"], cwd=root, check=True)
                subprocess.run(git + ["commit", "-qm", "Test source snapshot"], cwd=root, check=True)
            matches, blobs = scanner.history_findings(root)
            self.assertEqual(len(matches), 1)
            self.assertTrue(matches[0][0].startswith("git-blob:"))
            self.assertEqual(blobs, 2)


if __name__ == "__main__":
    unittest.main()
