import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


spec = importlib.util.spec_from_file_location("publication", Path(__file__).with_name("uk-publication.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UKPublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for path in module.FILES:
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("current " + path)
        self.expected = module.prepare(self.root, "1234", "a" * 40)
        self.manifest = (self.root / module.MANIFEST).read_bytes()

    def fetch(self, url):
        path = urlsplit(url).path.removeprefix("/uk_decline/")
        return (self.root / path).read_bytes()

    def test_build_identity_and_every_download_are_preserved(self):
        manifest = json.loads(self.manifest)
        self.assertEqual(manifest["uk_commit"], "a" * 40)
        self.assertEqual(manifest["run_id"], "1234")
        for path in module.FILES:
            self.assertEqual(manifest["files"][path], module.digest((self.root / path).read_bytes()))
        with patch.object(module, "fetch", side_effect=self.fetch):
            module.verify("https://example.org/uk_decline/", self.expected, timeout=0)

    def test_missing_source_cannot_replace_the_previous_manifest(self):
        (self.root / module.FILES[-1]).unlink()
        with self.assertRaises(FileNotFoundError):
            module.prepare(self.root, "1235", "b" * 40)
        self.assertEqual((self.root / module.MANIFEST).read_bytes(), self.manifest)

    def test_old_green_deployment_is_not_accepted(self):
        expected = module.prepare(self.root, "1235", "a" * 40)
        with patch.object(module, "fetch", return_value=self.manifest):
            with self.assertRaisesRegex(RuntimeError, "different publication"):
                module.verify("https://example.org/uk_decline/", expected, timeout=0)

    def test_correct_manifest_with_stale_download_is_not_accepted(self):
        (self.root / module.FILES[1]).write_text("stale polls")
        with patch.object(module, "fetch", side_effect=self.fetch):
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                module.verify("https://example.org/uk_decline/", self.expected, timeout=0)

    def test_cdn_propagation_and_transient_errors_recover(self):
        failures = [
            b"old publication",
            URLError("temporary connection failure"),
            HTTPError("https://example.org", 503, "unavailable", {}, None),
        ]
        for failure in failures:
            with self.subTest(failure=failure):
                def fetch(url):
                    if fetch.pending:
                        fetch.pending = False
                        if isinstance(failure, Exception):
                            raise failure
                        return failure
                    return self.fetch(url)
                fetch.pending = True
                with patch.object(module, "fetch", side_effect=fetch), patch.object(module.time, "sleep") as sleep:
                    module.verify("https://example.org/uk_decline/", self.expected, timeout=60)
                sleep.assert_called_once()

    def test_permanent_http_error_is_not_hidden_by_retries(self):
        error = HTTPError("https://example.org", 403, "forbidden", {}, None)
        with patch.object(module, "fetch", side_effect=error), patch.object(module.time, "sleep") as sleep:
            with self.assertRaises(HTTPError):
                module.verify("https://example.org/uk_decline/", self.expected)
        sleep.assert_not_called()

    def test_missing_fingerprint_fails_before_network_access(self):
        with patch.object(module, "fetch") as fetch:
            with self.assertRaises(ValueError):
                module.verify("https://example.org/uk_decline/", "")
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
