"""Freeze a complete factual county-context query without overwriting an asset."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("directory", type=Path)
args = parser.parse_args()
directory = args.directory.resolve()
archive = directory / "complete-county-participation-context-01.zip"
assert not archive.exists() and not (directory / "checksums.json").exists()
checksums = {
    str(path.relative_to(directory)): {
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    for path in sorted(directory.rglob("*")) if path.is_file()
}
(directory / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
    for file in sorted([*checksums, "checksums.json"]):
        member = zipfile.ZipInfo(file, date_time=(2026, 11, 6, 0, 0, 0))
        member.compress_type = zipfile.ZIP_DEFLATED
        member.external_attr = 0o100644 << 16
        target.writestr(member, (directory / file).read_bytes(), compresslevel=9)
print(json.dumps({
    "file": archive.name, "bytes": archive.stat().st_size,
    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "complete_members": len(checksums) + 1,
}, indent=2))
