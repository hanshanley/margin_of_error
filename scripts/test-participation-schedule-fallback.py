import base64
import hashlib
import json
import runpy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


code = runpy.run_path(str(Path(__file__).with_name("participation-schedule-fallback.py")))
tick = code["tick"]
NOW = datetime(2026, 11, 19, 0, 10, tzinfo=timezone.utc)


def ago(minutes):
    return (NOW - timedelta(minutes=minutes)).isoformat()


def run(created, updated, *, status="completed", conclusion="success"):
    return {"id": 101, "head_branch": "main", "status": status, "conclusion": conclusion,
            "created_at": ago(created), "updated_at": ago(updated), "head_sha": "d" * 40}


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.runs = {stage: [run(35, 10)] for stage in code["WORKFLOWS"]}
        self.source = {"contract": "participation.automatic_results_latest.v1",
                       "version": "a" * 64, "checked_at": ago(15)}
        self.live = {"contract": "participation.automatic_runtime.v1", "version": "c" * 64,
                     "input_results_version": "a" * 64, "checked_at": ago(15)}
        self.effects = []
        self.journal = {}
        self.fail_dispatch = False
        self.main = "d" * 40
        self.source_main = "d" * 40
        self.diff = None
        self.previous_source = None
        self.pins = {"d" * 40: "e" * 40, "f" * 40: "e" * 40}

    def request(self, path, *, raw=False, dispatch=False):
        for stage in self.runs:
            if path == code["workflow_path"](stage) + "/runs?branch=main&per_page=20":
                return {"workflow_runs": self.runs[stage]}
            if path == code["workflow_path"](stage) + "/dispatches":
                self.assertTrue(dispatch)
                self.effects.append(("dispatch", stage))
                if self.fail_dispatch:
                    raise TimeoutError("Response lost")
                return {"workflow_run_id": 102}
        if "/git/ref/tags/" in path:
            return {"object": {"type": "commit", "sha": "d" * 40}}
        if "/git/ref/heads/" in path:
            return {"object": {"type": "commit", "sha": self.source_main
                               if code["SOURCE"] in path else self.main}}
        if path.endswith("/git/commits/" + "1" * 40):
            return {"sha": "1" * 40, "parents": [{"sha": "2" * 40}]}
        if path.endswith("/contents/latest.json?ref=" + "2" * 40):
            self.assertTrue(raw)
            return self.previous_source
        if "/compare/" in path:
            return self.diff
        if "/contents/.github/workflows/automatic-runtime.yml?" in path:
            ref = path.split("?ref=")[-1]
            pin = self.pins.get(self.main if ref == "main" else ref)
            body = (f"  repository: {code['SOURCE']}\n  ref: {pin}\n  path: research-source\n").encode()
            return {"path": ".github/workflows/automatic-runtime.yml", "encoding": "base64",
                    "size": len(body), "content": base64.b64encode(body).decode()}
        self.assertTrue(raw)
        self.assertTrue(path.endswith("?ref=" + "d" * 40))
        return self.live if "/automatic/latest.json?" in path else self.source

    def result(self, *, apply=True, now=NOW):
        return tick(now, self.request, self.journal,
                    lambda data: self.effects.append(("journal", dict(data))), apply=apply)["decision"]

    def backlog(self):
        self.live.update(input_results_version="b" * 64, checked_at=ago(70))
        self.runs["publication"] = [run(66, 60)]

    def test_consumed_unchanged_input_skips_publisher(self):
        self.assertEqual(self.result(), "no_dispatch")
        self.assertEqual(self.effects, [])

    def test_catches_up_to_accepted_input_before_recollecting(self):
        self.backlog()
        self.runs["collection"] = [run(130, 110)]
        self.assertEqual(self.result(apply=False), "would_dispatch_publication")
        self.assertEqual(self.effects, [])
        report = tick(NOW, self.request, self.journal,
                      lambda data: self.effects.append(("journal", dict(data))), apply=True)
        self.assertEqual((report["decision"], report["run_id"]), ("dispatched_publication", 102))
        self.assertEqual(self.effects, [("journal", {"publication": NOW.isoformat()}),
                                        ("dispatch", "publication")])

    def test_new_reviewed_producer_republishes_the_same_source_once(self):
        self.main = "f" * 40
        self.runs["publication"] = [run(45, 35)]
        self.assertEqual(self.result(), "no_dispatch")  # Site-only changes do not need a publication.
        self.pins[self.main] = None
        self.assertEqual(self.result(), "no_dispatch")
        self.pins[self.main] = "1" * 40
        report = tick(NOW, self.request, self.journal, lambda data: None, apply=True)
        self.assertEqual(report["decision"], "dispatched_publication")
        self.assertEqual(report["publication_reason"], "reviewed_producer_changed")
        self.assertEqual(self.result(), "no_dispatch")
        self.runs["publication"] = [{**run(45, 35), "head_sha": self.main}]
        self.journal.clear()
        self.assertEqual(self.result(), "no_dispatch")

    def test_already_running_collectors_and_publishers_are_not_duplicated(self):
        self.backlog()
        for stage in ("collection", "publication"):
            self.runs[stage].append(run(71, 66, status="waiting", conclusion=None))
            self.assertEqual(self.result(), "no_dispatch")
            self.runs[stage].pop()
        self.assertEqual(self.effects, [])

    def test_pinned_source_changes_collect_before_analysis_only_republish(self):
        self.main, self.source_main = "f" * 40, "1" * 40
        self.pins[self.main] = self.source_main
        self.runs["publication"] = [run(45, 35)]
        self.runs["collection"] = [{**run(55, 40), "display_title": "Collect full election results"}]
        self.diff = {"status": "ahead", "merge_base_commit": {"sha": "d" * 40},
                     "files": [{"filename": "scripts/results_granular.py"}]}
        report = tick(NOW, self.request, self.journal, lambda data: None, apply=True)
        self.assertEqual(report["decision"], "dispatched_collection")
        self.assertEqual(report["collection_reason"], "reviewed_collector_changed")
        self.runs["collection"].insert(0, run(1, 0, status="queued", conclusion=None))
        self.assertEqual(self.result(), "no_dispatch")

    def test_analysis_only_change_and_unreviewed_pin_do_not_collect_early(self):
        self.main, self.source_main = "f" * 40, "1" * 40
        self.runs["publication"] = [run(45, 35)]
        self.runs["collection"] = [{**run(55, 40), "display_title": "Collect full election results"}]
        self.diff = {"status": "ahead", "merge_base_commit": {"sha": "d" * 40},
                     "files": [{"filename": "scripts/results_granular.py"}]}
        self.assertEqual(self.result(apply=False), "no_dispatch")
        self.pins[self.main] = self.source_main
        self.diff["files"] = [{"filename": "scripts/automatic_runtime.py"}]
        self.assertEqual(self.result(apply=False), "would_dispatch_publication")
        self.diff["files"] = [{"filename": "scripts/results_granular.py"}]
        self.backlog()
        self.assertEqual(self.result(apply=False), "would_dispatch_publication")

    def test_successful_stale_collection_or_cooled_failure_gets_recovery(self):
        self.runs["collection"] = [run(110, 12, conclusion="failure")]
        self.assertEqual(self.result(), "no_dispatch")
        self.runs["collection"] = [run(62, 33, conclusion="failure")]
        self.assertEqual(self.result(), "dispatched_collection")
        self.journal.clear()
        self.runs["collection"] = [run(90, 62)]
        self.assertEqual(self.result(), "dispatched_collection")

    def test_lost_dispatch_response_does_not_duplicate(self):
        self.backlog()
        self.fail_dispatch = True
        with self.assertRaises(TimeoutError):
            self.result()
        self.assertEqual(self.result(), "no_dispatch")
        self.assertEqual([effect for effect in self.effects if effect[0] == "dispatch"],
                         [("dispatch", "publication")])

    def test_health_is_checked_even_while_collection_is_active(self):
        self.runs["health"] = []
        self.runs["collection"] = [run(5, 1, status="in_progress", conclusion=None)]
        self.assertEqual(self.result(), "dispatched_health")

    def test_invalid_or_reversed_pointer_never_triggers_a_write(self):
        self.backlog()
        self.source["checked_at"] = ago(70)
        with self.assertRaisesRegex(ValueError, "older or ambiguous"):
            self.result()
        self.source["contract"] = "wrong"
        with self.assertRaisesRegex(ValueError, "pointer contract"):
            self.result()
        self.assertEqual(self.effects, [])

    def test_same_time_reprojection_requires_the_exact_consumed_predecessor(self):
        self.backlog()
        self.source.update(checked_at=self.live["checked_at"], results_commit="1" * 40)
        self.previous_source = {**self.source, "version": self.live["input_results_version"]}
        body = (json.dumps(self.previous_source, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.live["input_results_pointer"] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        self.assertEqual(self.result(apply=False), "would_dispatch_publication")
        self.previous_source["base_url"] = "https://example.test/changed"
        with self.assertRaisesRegex(ValueError, "older or ambiguous"):
            self.result()
        self.assertEqual(self.effects, [])

    def test_no_remote_call_after_close(self):
        def unexpected(*args, **kwargs):
            self.fail("Outside the election window")
        self.assertEqual(tick(code["WINDOW"][1], unexpected, {}, None, apply=True),
                         {"decision": "outside_election_window"})


if __name__ == "__main__":
    unittest.main()
