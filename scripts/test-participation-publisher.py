import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from participation_intake.contract import IntakeError, encoded, pin, digest
from participation_intake.publisher import GitPublisher, validate_dataset


class LocalPublisher(GitPublisher):
    def verify_files(self, commit, files):
        for name, expected in files.items():
            body = subprocess.check_output(["git", "-C", str(self.repository), "show", f"{commit}:{name}"])
            if pin(body) != expected:
                raise IntakeError("publication_integrity", "Staged bytes differ")
        return list(files)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo, self.remote = self.root / "source", self.root / "remote.git"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        (self.repo / "unchanged.txt").write_text("protected source\n")
        self.git("add", "unchanged.txt")
        self.git("-c", "user.name=Hans Hanley", "-c", "user.email=hans@hanshanley.com",
            "commit", "-q", "-m", "Fixture source")
        self.git("remote", "add", "origin", str(self.remote))
        self.publisher = LocalPublisher(self.repo)

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args]).decode().strip()

    def dataset(self, name, value):
        root = self.root / name
        root.mkdir()
        body = encoded(dict(contract="geographic.resident_context.v1", fixture_value=value))
        (root / "index.json").write_bytes(body)
        files = {"index.json": pin(body)}
        description = dict(contract="participation.dataset.v1", id="resident-context",
            version=digest(encoded(dict(files=files, contract="geographic.resident_context.v1"))),
            record_contract="geographic.resident_context.v1", files=files,
            index=dict(file="index.json", **pin(body)), status="awaiting_publication",
            complete_download=dict(url="https://github.com/example/data/releases/download/frozen/complete-analysis.zip",
                verified_anonymously=True, sha256="0"*64, bytes=1))
        (root / "dataset.json").write_bytes(encoded(description))
        return root

    def test_publication_and_changed_data_leave_source_head_and_real_index_untouched(self):
        head = self.git("rev-parse", "HEAD")
        index = (self.repo / ".git/index").read_bytes()
        first = self.publisher.publish(self.dataset("one", 0))
        second = self.publisher.publish(self.dataset("two", None))
        self.assertNotEqual(first["version"], second["version"])
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual(second["website_builds_started"], 0)
        self.assertEqual(self.publisher.catalog(second["catalog_commit"])["datasets"]["resident-context"]["version"],
            second["version"])

    def test_unchanged_dataset_is_a_true_noop(self):
        root = self.dataset("one", 0)
        first = self.publisher.publish(root)
        second = self.publisher.publish(root)
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["data_commit"], first["catalog_commit"])

    def test_changed_bytes_and_metadata_only_downloads_cannot_activate(self):
        root = self.dataset("one", 0)
        (root / "index.json").write_text("{}")
        with self.assertRaises(IntakeError):
            validate_dataset(root)
        root = self.dataset("two", 0)
        description = json.loads((root / "dataset.json").read_bytes())
        description["complete_download"] = None
        (root / "dataset.json").write_bytes(encoded(description))
        with self.assertRaises(IntakeError):
            self.publisher.publish(root)
        self.assertIsNone(self.publisher.remote_head())


if __name__ == "__main__":
    unittest.main()
