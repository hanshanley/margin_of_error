from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from local_reference_staging import stage_local_minnesota_reference


class LocalReferenceStaging(unittest.TestCase):
    @contextmanager
    def frozen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index = root / "public/participation-precincts/20261110-minnesota-followup-02/index.json"
            body = b"exactly pinned fixture"
            source = root / "data/county-source-reviews/20261110-minnesota-followup-02/MN.geojson.gz"
            index.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            source.write_bytes(body)
            index.write_text(json.dumps(dict(states={"MN": "https://example.invalid/MN.geojson.gz"},
                state_metadata={"MN": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())})))
            yield root, source

    def test_production_never_checks_or_overrides_a_reference(self):
        with patch("local_reference_staging.urlopen") as opened:
            context = Mock()
            self.assertFalse(stage_local_minnesota_reference(context, "https://www.themarginoferror.com"))
            opened.assert_not_called()
            context.route.assert_not_called()

    def test_published_reference_is_not_locally_overridden(self):
        with self.frozen() as (root, source):
            source.unlink()
            context = Mock()
            with patch("local_reference_staging.urlopen") as opened:
                opened.return_value.__enter__.return_value.status = 200
                self.assertFalse(stage_local_minnesota_reference(context, "http://127.0.0.1:4387", root))
            context.route.assert_not_called()

    def test_only_unpublished_404_reference_can_use_the_exact_frozen_body(self):
        with self.frozen() as (root, _):
            context = Mock()
            error = HTTPError("https://example.invalid", 404, "unpublished", {}, None)
            with patch("local_reference_staging.urlopen", side_effect=error):
                self.assertTrue(stage_local_minnesota_reference(context, "http://127.0.0.1:4387", root))
            context.route.assert_called_once()

    def test_denial_and_mismatched_frozen_body_do_not_get_a_local_fallback(self):
        with self.frozen() as (root, source):
            context = Mock()
            with patch("local_reference_staging.urlopen", side_effect=HTTPError(
                    "https://example.invalid", 403, "denied", {}, None)):
                with self.assertRaises(HTTPError):
                    stage_local_minnesota_reference(context, "http://127.0.0.1:4387", root)
            source.write_bytes(b"not the pinned body")
            with patch("local_reference_staging.urlopen", side_effect=HTTPError(
                    "https://example.invalid", 404, "unpublished", {}, None)):
                with self.assertRaises(ValueError):
                    stage_local_minnesota_reference(context, "http://127.0.0.1:4387", root)
            context.route.assert_not_called()


if __name__ == "__main__":
    unittest.main()
