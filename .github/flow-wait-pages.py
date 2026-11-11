import concurrent.futures, hashlib, json, os, pathlib, re, tarfile, time, urllib.request
root = pathlib.Path.cwd()
expected = json.loads((root / ".github/flow-artifact-expected.json").read_text())
run_id = 43117213469
commit = "156bfa8bddf0aabd810ffcea1ede3fbbe7ccf1e3"
headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"}
for attempt in range(120):
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/hanshanley/margin_of_error/actions/runs/" + str(run_id), headers=headers), timeout=60) as response:
        run = json.load(response)
    assert run["head_sha"] == commit and run["head_branch"] == "main"
    if run["status"] == "completed":
        assert run["conclusion"] == "success", run["conclusion"]
        break
    time.sleep(15)
else:
    raise RuntimeError("Existing Pages run did not finish")
print("Accepted successful unchanged CI run", run_id, flush=True)
