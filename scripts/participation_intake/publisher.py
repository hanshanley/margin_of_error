"""Hash-addressed data publication; never touches a website worktree or build."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import urllib.request

from .contract import IntakeError, encoded, pin, digest


CATALOG_CONTRACT = "participation.dataset_catalog.v1"


def validate_dataset(root):
    root = Path(root)
    description = json.loads((root / "dataset.json").read_bytes())
    if description.get("contract") != "participation.dataset.v1":
        raise IntakeError("dataset_contract", "Unknown canonical dataset contract")
    for key in ("id", "version"):
        value = description.get(key)
        if not isinstance(value, str) or not value or any(char not in
                "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
            raise IntakeError("dataset_identity", "Unsafe dataset identity/version")
    for name, expected in description["files"].items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name:
            raise IntakeError("dataset_path", "Unsafe immutable dataset path")
        if pin((root / name).read_bytes()) != expected:
            raise IntakeError("dataset_integrity", "Changed canonical dataset file: " + name)
    if description["version"] != digest(encoded(dict(files=description["files"],
            contract=description.get("record_contract")))):
        raise IntakeError("dataset_integrity", "Dataset version is not its content-addressed identity")
    index = description["index"]
    if index["file"] not in description["files"] or description["files"][index["file"]] != {
            key: index[key] for key in ("bytes", "sha256")}:
        raise IntakeError("dataset_integrity", "Index is not one of the pinned dataset files")
    complete = description.get("complete_download")
    if not complete or not complete.get("verified_anonymously") or not complete.get("sha256"):
        raise IntakeError("incomplete_download", "Publish the complete verified scientific package before activation")
    if not complete.get("url", "").startswith("https://github.com/"):
        raise IntakeError("incomplete_download", "Complete package URL must be a public immutable release")
    return description


class GitPublisher:
    def __init__(self, repository, remote="origin", ref="participation-data",
                 github_repository="hanshanley/margin_of_error"):
        self.repository = Path(repository)
        self.remote, self.ref, self.github_repository = remote, ref, github_repository

    def git(self, *args, body=None, env=None, check=True):
        return subprocess.run(["git", "-C", str(self.repository), *args],
            input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, check=check).stdout.decode().strip()

    def remote_head(self):
        output = self.git("ls-remote", self.remote, "refs/heads/" + self.ref)
        return output.split()[0] if output else None

    def tree(self, parent, files):
        with tempfile.TemporaryDirectory(prefix="participation-data-index-") as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
            self.git("read-tree", parent or "--empty", env=env)
            lines = []
            for name, body in sorted(files.items()):
                blob = self.git("hash-object", "-w", "--stdin", body=body)
                lines.append(f"100644 {blob}\t{name}\n")
            self.git("update-index", "--index-info", body="".join(lines).encode(), env=env)
            return self.git("write-tree", env=env)

    def commit(self, tree, parent, message):
        env = dict(os.environ, GIT_AUTHOR_NAME="Hans Hanley", GIT_COMMITTER_NAME="Hans Hanley",
            GIT_AUTHOR_EMAIL="hans@hanshanley.com", GIT_COMMITTER_EMAIL="hans@hanshanley.com")
        args = ["commit-tree", tree]
        if parent:
            args.extend(["-p", parent])
        return self.git(*args, body=(message + "\n").encode(), env=env)

    def promote(self, commit, expected):
        if self.remote_head() != expected:
            raise IntakeError("publication_conflict", "Data catalog advanced; staged bytes are retained without overwriting it")
        self.git("push", self.remote, commit + ":refs/heads/" + self.ref)

    def fetch_parent(self, parent):
        if parent:
            self.git("fetch", "--no-tags", self.remote, "refs/heads/" + self.ref)

    def catalog(self, parent):
        if not parent:
            return dict(contract=CATALOG_CONTRACT, datasets={})
        body = self.git("show", parent + ":catalog.json", check=False)
        if not body:
            return dict(contract=CATALOG_CONTRACT, datasets={})
        result = json.loads(body)
        if result.get("contract") != CATALOG_CONTRACT:
            raise IntakeError("catalog_contract", "The remote catalog uses an unknown contract")
        return result

    def verify_files(self, commit, files):
        base = f"https://raw.githubusercontent.com/{self.github_repository}/{commit}/"
        def verify(item):
            name, expected = item
            with urllib.request.urlopen(base + name, timeout=90) as response:
                body = response.read()
            if pin(body) != expected:
                raise IntakeError("publication_integrity", "Anonymous immutable data verification failed: " + name)
            return name
        with ThreadPoolExecutor(max_workers=4) as pool:
            return list(pool.map(verify, sorted(files.items())))

    def publish(self, root):
        root = Path(root)
        description = validate_dataset(root)
        parent = self.remote_head()
        self.fetch_parent(parent)
        catalog = self.catalog(parent)
        current = catalog["datasets"].get(description["id"])
        if current and current["version"] == description["version"]:
            if current["files"] != description["files"] or current["complete_download"] != description["complete_download"]:
                raise IntakeError("immutable_version_conflict", "An existing immutable version cannot change")
            return dict(status="unchanged", data_commit=parent, website_builds_started=0)
        prefix = f"datasets/{description['id']}/{description['version']}/"
        bodies = {prefix + name: (root / name).read_bytes() for name in description["files"]}
        bodies[prefix + "dataset.json"] = encoded(description)
        staged = self.commit(self.tree(parent, bodies), parent,
            f"Stage {description['id']} dataset {description['version'][:12]}")
        self.promote(staged, parent)
        verified = self.verify_files(staged, {name: pin(body) for name, body in bodies.items()})
        entry = dict(description, status="loaded",
            base_url=f"https://raw.githubusercontent.com/{self.github_repository}/{staged}/{prefix}",
            staged_commit=staged)
        catalog["datasets"][description["id"]] = entry
        tree = self.tree(staged, {"catalog.json": encoded(catalog)})
        promoted = self.commit(tree, staged, f"Activate verified {description['id']} dataset")
        self.promote(promoted, staged)
        self.verify_files(promoted, {"catalog.json": pin(encoded(catalog))})
        return dict(status="published", id=description["id"], version=description["version"],
            staged_commit=staged, catalog_commit=promoted, anonymous_verified_files=len(verified),
            catalog_url=f"https://raw.githubusercontent.com/{self.github_repository}/{self.ref}/catalog.json",
            website_builds_started=0, worktree_head_or_index_changed=False)
