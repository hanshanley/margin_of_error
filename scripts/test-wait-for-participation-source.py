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

    def test_waits_for_full_dispatch_but_ignores_scoped_collection(self):
        scoped = dict(RUN, id=1, event="workflow_dispatch", display_title="Run scoped election results update")
        full = dict(RUN, event="workflow_dispatch", display_title="Collect full election results")
        self.assertEqual(self.simulate([{"workflow_runs": [scoped]}])["status"], "no_collection_in_progress")
        result = self.simulate([{"workflow_runs": [scoped, full]},
                                dict(full, status="completed", conclusion="success")])
        self.assertEqual(result, {"status": "collection_completed", "run_id": RUN["id"],
                                  "conclusion": "success"})
        self.assertEqual(self.paths, [wait.LATEST, f"/runs/{RUN['id']}"])
        self.assertEqual(self.simulate([{"workflow_runs": [full]}, scoped])["status"],
                         "collection_status_unavailable")

    def test_weekly_archive_check_does_not_delay_hourly_publication(self):
        archive = dict(RUN, id=1, display_title="Check late participation archives")
        finished = dict(RUN, status="completed", conclusion="success")
        self.assertEqual(self.simulate([{"workflow_runs": [archive, RUN]}, finished]),
                         {"status": "collection_completed", "run_id": RUN["id"], "conclusion": "success"})

    def test_completed_missing_or_stale_run_does_not_hold_publication(self):
        for runs, expected in (([], "no_collection_in_progress"),
                               ([dict(RUN, status="completed")], "no_collection_in_progress"),
                               ([dict(RUN, created_at="2026-11-18T20:00:00Z")],
                                "no_recent_collection_in_progress")):
            self.assertEqual(self.simulate([{"workflow_runs": runs}])["status"], expected)
            self.assertEqual(self.elapsed, 0)
        outside = datetime(2027, 2, 1, tzinfo=timezone.utc)
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
