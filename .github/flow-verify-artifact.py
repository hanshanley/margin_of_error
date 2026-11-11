import concurrent.futures, hashlib, json, pathlib, re, tarfile, time, urllib.request
root = pathlib.Path.cwd()
expected = json.loads((root / ".github/flow-artifact-expected.json").read_text())
archive = root / "pages-artifact/artifact.tar"
assert archive.stat().st_size < 1000000000
found, payload, files, html = {}, 0, 0, None
with tarfile.open(archive, "r|") as tar:
    for item in tar:
        path = pathlib.PurePosixPath(item.name)
        assert not path.is_absolute() and ".." not in path.parts
        name = "/".join(p for p in path.parts if p != ".")
        if not item.isfile():
            continue
        payload += item.size
        files += 1
        if name in expected or name == "voter-participation/index.html":
            body = tar.extractfile(item).read()
            if name in expected:
                digest = hashlib.sha256(body).hexdigest()
                assert digest == expected[name], name
                found[name] = dict(bytes=len(body), sha256=digest)
            if name == "voter-participation/index.html":
                html = body
assert payload < 1000000000 and archive.stat().st_size >= payload + 1024
assert set(found) == set(expected)
assert html.count(b"data-saved-switching-bounds=") == html.count(b"data-saved-calibrated=") == html.count(b"data-saved-driver=") == 113
match = re.search(rb"<script[^>]*data-driver-data[^>]*>(.*?)</script>", html, re.S)
payload_data = json.loads(match[1])
for key, path in [("data", "20261110-02/viewer-data.json"), ("calibration", "20261111-03/return-constrained-viewer.json")]:
    assert payload_data[key] == json.loads((root / "data/participation-return-attribution" / path).read_bytes())
def check(item):
    path, pin = item
    for attempt in range(10):
        with urllib.request.urlopen("https://www.themarginoferror.com/" + path, timeout=120) as response:
            body = response.read()
        if len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"]:
            return path
        time.sleep(20)
    raise ValueError("Unqueried production differs: " + path)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    assert set(pool.map(check, found.items())) == set(found)
with urllib.request.urlopen("https://www.themarginoferror.com/participation-downloads.json", timeout=120) as response:
    downloads = json.load(response)
assert len(downloads["files"]) == 436
with urllib.request.urlopen("https://www.themarginoferror.com/voter-participation/", timeout=120) as response:
    assert response.read() == html
proof = dict(status="passed_actual_native_tar_and_exact_unqueried_production", website_commit="156bfa8bddf0aabd810ffcea1ede3fbbe7ccf1e3", pages_run_id=43117213469, actual_payload_bytes=payload, actual_tar_bytes=archive.stat().st_size, files=files, exact_assets=found, unchanged_complete_downloads=436, all113_original_models_and_calibrated_decisions_preserved=True, all113_server_rendered_bounds_and_holds_preserved=True, exact_unqueried_html_sha256=hashlib.sha256(html).hexdigest(), source_models_or_geometries_changed=False)
(root / "artifact-proof").mkdir()
(root / "artifact-proof/publication.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "
")
print(json.dumps({k:v for k,v in proof.items() if k != "exact_assets"}), flush=True)
