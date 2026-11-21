import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "wait_for_participation_source", Path(__file__).with_name("wait-for-participation-source.py"))
wait = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wait)
NOW = datetime(2026, 11, 18, 22, 18, tzinfo=timezone.utc)
RUN = {"id": 44408500380, "created_at": "2026-11-18T22:07:41Z",
       "status": "in_progress", "event": "schedule", "head_branch": "main"}


class TestWaitForSource(unittest.TestCase):
    def simulate(self, answers, **options):
        self.paths, self.elapsed = [], 0
        responses = iter(answers)

        def fetch(path):
            self.paths.append(path)
            result = next(responses)
            if isinstance(result, Exception):
                raise result
            return result

        def sleep(seconds):
            self.elapsed += seconds

        return wait.wait_for_collection(fetch, monotonic=lambda: self.elapsed, sleep=sleep,
                                        pending=options.pop("pending", lambda: None),
                                        now=options.pop("now", NOW), **options)

    def test_waits_for_exact_scheduled_run_before_handoff(self):
        for conclusion in ("success", "failure", "cancelled"):
            result = self.simulate([{"workflow_runs": [RUN]}, RUN,
                                    dict(RUN, status="completed", conclusion=conclusion)])
            self.assertEqual(result, {"status": "collection_completed", "run_id": RUN["id"],
                                      "conclusion": conclusion})
            self.assertEqual(self.paths, [wait.LATEST, f"/runs/{RUN['id']}", f"/runs/{RUN['id']}"])

    def test_wait_covers_observed_collector_publisher_timing(self):
        complete = dict(RUN, status="completed", conclusion="success")
        # A publisher starting at 22:18 UTC would still see the previous
        # packet until the collector finished at 22:45:16 UTC.
        delay = 27 * 60 + 16
        polls_before_completion = (delay - 1) // 90
        result = self.simulate([{"workflow_runs": [RUN]}] + [RUN] * polls_before_completion + [complete])
        self.assertEqual(result["status"], "collection_completed")
        self.assertGreaterEqual(self.elapsed, delay)
        self.assertLess(self.elapsed, 2400)

    def test_publishes_already_accepted_input_without_waiting_for_new_collection(self):
        self.assertEqual(self.simulate([{"workflow_runs": [RUN]}], pending=lambda: "a" * 64),
                         {"status": "accepted_checkpoint_ready", "input_results_version": "a" * 64})
        self.assertEqual(self.paths, [wait.LATEST])
        self.assertEqual(self.elapsed, 0)

    def test_only_known_newer_commit_pinned_input_skips_wait(self):
        source = {"contract": "participation.automatic_results_latest.v1",
                  "version": "a" * 64, "checked_at": "2026-11-18T22:04:00Z"}
        live = {"contract": "participation.automatic_runtime.v1",
                "version": "c" * 64, "input_results_version": "b" * 64,
                "checked_at": "2026-11-18T22:00:00Z"}
        refs = [{"object": {"type": "commit", "sha": ch * 40}} for ch in ("1", "2")]
        route = {
            f"https://api.github.com/repos/{wait.SOURCE}/git/ref/tags/results-data": refs[0],
            f"https://raw.githubusercontent.com/{wait.SOURCE}/{'1' * 40}/latest.json": source,
            f"https://api.github.com/repos/{wait.SITE}/git/ref/tags/participation-data": refs[1],
            f"https://raw.githubusercontent.com/{wait.SITE}/{'2' * 40}/automatic/latest.json": live,
        }
        self.assertEqual(wait.unconsumed_checkpoint(route.__getitem__), source["version"])
        for update in ({"input_results_version": source["version"]},
                       {"checked_at": source["checked_at"]},
                       {"checked_at": "2026-11-18T22:06:00Z"},
                       {"checked_at": "2026-11-18T22:00:00"},
                       {"contract": "invalid"}, {"input_results_version": "invalid"}):
            key = next(reversed(route))
            self.assertIsNone(wait.unconsumed_checkpoint({**route, key: {**live, **update}}.__getitem__))
        self.assertIsNone(wait.unconsumed_checkpoint({}.__getitem__))

    def test_prefers_running_scoped_collection_over_a_newer_queued_full_run(self):
        scoped = dict(RUN, id=1, event="workflow_dispatch", display_title="Run scoped election results update")
        full = dict(RUN, event="workflow_dispatch", display_title="Collect full election results")
        result = self.simulate([{"workflow_runs": [dict(full, status="queued"), scoped]},
                                dict(scoped, status="completed", conclusion="success")])
        self.assertEqual(result, {"status": "collection_completed", "run_id": scoped["id"],
                                  "conclusion": "success"})
        self.assertEqual(self.paths, [wait.LATEST, f"/runs/{scoped['id']}"])
        self.assertEqual(self.simulate([{"workflow_runs": [full]}, dict(scoped, id=full["id"])])["status"],
                         "collection_status_unavailable")

    def test_waits_for_weekly_archive_after_hourly_collection_ends(self):
        now = datetime(2027, 2, 1, 10, 31, tzinfo=timezone.utc)
        archive = dict(RUN, id=1, created_at="2027-02-01T10:19:00Z", display_title=wait.ARCHIVE_TITLE)
        finished = dict(archive, status="completed", conclusion="success")
        self.assertEqual(self.simulate([{"workflow_runs": [RUN, archive]}, finished], now=now),
                         {"status": "collection_completed", "run_id": archive["id"], "conclusion": "success"})

    def test_periodically_checks_for_an_accepted_checkpoint_during_the_wait(self):
        checkpoints = iter((None, "a" * 64))
        self.assertEqual(self.simulate([{"workflow_runs": [RUN]}] + [RUN] * 5, pending=lambda: next(checkpoints)),
                         {"status": "accepted_checkpoint_ready", "input_results_version": "a" * 64})
        self.assertEqual(self.elapsed, 450)

    def test_completed_missing_or_stale_run_does_not_hold_publication(self):
        for runs, expected in (([], "no_collection_in_progress"),
                               ([dict(RUN, status="completed")], "no_collection_in_progress"),
                               ([dict(RUN, created_at="2026-11-18T20:00:00Z")],
                                "no_recent_collection_in_progress")):
            self.assertEqual(self.simulate([{"workflow_runs": runs}])["status"], expected)
            self.assertEqual(self.elapsed, 0)
        outside = datetime(2026, 11, 2, tzinfo=timezone.utc)
        self.assertEqual(self.simulate([], now=outside)["status"], "outside_collection_window")
        self.assertEqual(self.paths, [])

    def test_timeout_and_unavailable_status_fall_back_to_existing_pointer_path(self):
        self.assertEqual(self.simulate([{"workflow_runs": [RUN]}, RUN], wait_seconds=91),
                         {"status": "wait_limit_reached", "run_id": RUN["id"]})
        self.assertEqual(self.elapsed, 91)
        for answers in ([OSError("network unavailable")],
                        [{"workflow_runs": [RUN]}, dict(RUN, id=1)],
                        [{"workflow_runs": [dict(RUN, event="workflow_dispatch")]}]):
            self.assertEqual(self.simulate(answers)["status"], "collection_status_unavailable")


if __name__ == "__main__":
    unittest.main()
