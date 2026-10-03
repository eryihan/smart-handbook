import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_handbook as fixtures

SKILL, hb = fixtures.SKILL, fixtures.hb

sys.modules["handbook"] = hb
spec = importlib.util.spec_from_file_location("review", SKILL / "scripts/review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewToolTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.HandbookTest("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.session = Path(self.temporary.name) / "session"
        self.relative = self.fixture.review_path

    def prepare(self, selected=None):
        return review.prepare(self.root, self.relative, self.session, selected)

    def seal(self, **changes):
        value = {"status": "passed", "isolation": "independent", "description": "synthetic source feedback",
                 "findings": [], "retained": {}}
        value.update(changes)
        return review.seal(self.root, self.session, value)

    def feedback(self, failed=False):
        case = self.fixture.record["scenarios"][0]
        return {"reader": self.fixture.record["reader"], "scenarios": [{
            "id": case["id"], "reading": copy.deepcopy(case["reading"]),
            "verdict": "failed" if failed else "passed", "assessment": "Actual feedback fixture"}]}

    def project_bytes(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_prepare_and_seal_are_read_only_and_reader_packet_hides_answers(self):
        before = self.project_bytes()
        result = self.prepare()
        self.seal()
        self.assertEqual(before, self.project_bytes())
        files = list((self.session / "reader").rglob("*"))
        self.assertFalse(any(p.name.startswith(".") and p.is_file() for p in files))
        questions = review.read(self.session / "reader/questions.json")
        self.assertEqual(set(questions[0]), {"id", "question"})
        self.assertNotIn("expected", json.dumps(questions))
        self.assertEqual(result["questions"], 1)

    def test_finish_preserves_page_objects_observations_other_pages_and_baseline(self):
        f = self.fixture
        f.state["baseline"] = {"commit": "old-whole-project-baseline"}
        f.state["pages"][f.flow] = {"sources": {f.source: "sha256:" + "a" * 64}}
        f.save_state()
        old = copy.deepcopy(f.state)
        self.prepare()
        self.seal()
        result = review.finish(self.root, self.session, self.feedback())
        state = review.read(self.root / hb.STATE_PATH)
        record = review.read(self.root / self.relative)
        self.assertEqual(state["baseline"], old["baseline"])
        self.assertEqual(state["pages"][f.flow], old["pages"][f.flow])
        self.assertEqual(state["pages"][f.module]["verification"], old["pages"][f.module]["verification"])
        self.assertIsInstance(state["pages"][f.module], dict)
        self.assertLessEqual(record["prepared_at"], record["source_reviewed_at"])
        self.assertLessEqual(record["source_reviewed_at"], record["scenarios"][0]["reviewed_at"])
        self.assertEqual(result["failed"], 0)
        self.assertFalse([i for i in hb.Handbook(self.root).check()["issues"] if i["level"] == "error"])

    def test_failed_source_feedback_cannot_start_or_save_reading(self):
        self.prepare()
        result = self.seal(status="failed", findings=["Wrong synchronous conclusion"])
        self.assertFalse(result["reader_allowed"])
        before = self.project_bytes()
        with self.assertRaisesRegex(ValueError, "Source review did not pass"):
            review.finish(self.root, self.session, self.feedback())
        self.assertEqual(before, self.project_bytes())

    def test_unavailable_or_unresolved_source_review_cannot_pass(self):
        self.prepare()
        for kwargs in ({"isolation": "unavailable"}, {"findings": ["still unresolved"]}):
            with self.assertRaises(ValueError):
                self.seal(**kwargs)

    def test_failed_reader_feedback_is_saved_as_failed_not_passed(self):
        self.prepare()
        self.seal()
        review.finish(self.root, self.session, self.feedback(failed=True))
        record = review.read(self.root / self.relative)
        self.assertEqual(record["scenarios"][0]["verdict"], "failed")
        self.assertFalse(hb.Handbook(self.root).check()["inventory"]["ready_to_complete"])

    def test_missing_topics_are_rejected_before_any_reader_work(self):
        self.fixture.record["not_applicable"] = {}
        self.fixture.inventory["units"][0]["entrypoints"][0]["status"] = "needs-review"
        self.fixture.save_review()
        self.fixture.save_inventory()
        with self.assertRaisesRegex(ValueError, "all six topics"):
            self.prepare()
        self.assertFalse(self.session.exists())

    def test_code_or_page_change_after_preparation_blocks_seal(self):
        self.prepare()
        for relative in (self.fixture.source, self.fixture.module):
            path = self.root / relative
            old = path.read_bytes()
            path.write_bytes(old + b"\n")
            with self.assertRaisesRegex(ValueError, "version changed"):
                self.seal()
            path.write_bytes(old)

    def test_changed_expectation_or_snapshot_blocks_finish(self):
        self.prepare()
        self.seal()
        self.fixture.record["scenarios"][0]["expected"]["answer"] = "Unreviewed new answer"
        self.fixture.save_review()
        with self.assertRaisesRegex(ValueError, "Draft record changed"):
            review.finish(self.root, self.session, self.feedback())

    def test_reader_snapshot_cannot_be_edited_during_reading(self):
        self.prepare()
        self.seal()
        path = self.session / "reader" / self.fixture.module
        path.write_text(path.read_text() + "\nnew text")
        with self.assertRaisesRegex(ValueError, "Reader snapshot changed"):
            review.finish(self.root, self.session, self.feedback())

    def test_source_proof_does_not_survive_changing_an_expected_answer(self):
        self.fixture.record["scenarios"][0]["expected"]["answer"] = "Made-up answer"
        self.fixture.save_review(refresh_proof=False)
        self.assertIn("review-invalid", self.fixture.codes(self.fixture.check()))

    def test_source_timestamp_cannot_predate_actual_preparation(self):
        self.fixture.record["prepared_at"] = "2026-10-01T10:00:30Z"
        self.fixture.save_review()
        self.assertIn("review-invalid", self.fixture.codes(self.fixture.check()))

    def test_entry_evidence_is_not_required_to_be_duplicated_in_unit_sources(self):
        self.fixture.inventory["units"][0]["sources"] = []
        self.fixture.save_inventory()
        result = self.fixture.check()
        self.assertEqual(result["inventory"]["units"]["business-approval"]["status"], "accepted")

    def test_partial_retry_requires_explicit_assessment_of_retained_answers(self):
        extra = copy.deepcopy(self.fixture.record["scenarios"][0])
        extra["id"] = "approve-second"
        self.fixture.record["scenarios"].append(extra)
        self.fixture.save_review()
        self.prepare(["approve-normal"])
        with self.assertRaisesRegex(ValueError, "unselected answer"):
            self.seal()
        self.seal(retained={"approve-second": "Diff is a typo outside the cited rule; answer and method unchanged"})
        review.finish(self.root, self.session, self.feedback())
        record = review.read(self.root / self.relative)
        self.assertEqual(len(record["scenarios"]), 2)
        self.assertIn("Retained reading", record["scenarios"][1]["assessment"])
        self.assertEqual(record["scenarios"][1]["reading"], extra["reading"])

    def test_duplicate_or_omitted_feedback_does_not_write_any_project_file(self):
        self.prepare()
        self.seal()
        before = self.project_bytes()
        bad = self.feedback()
        bad["scenarios"].append(copy.deepcopy(bad["scenarios"][0]))
        with self.assertRaises(ValueError):
            review.finish(self.root, self.session, bad)
        self.assertEqual(before, self.project_bytes())

    def test_state_write_failure_rolls_back_review(self):
        self.prepare()
        self.seal()
        before = self.project_bytes()
        real_replace = review.os.replace

        def fail_state(source, target):
            if str(target).endswith(".state.json"):
                raise OSError("synthetic disk failure")
            return real_replace(source, target)

        with patch.object(review.os, "replace", side_effect=fail_state):
            with self.assertRaises(OSError):
                review.finish(self.root, self.session, self.feedback())
        self.assertEqual(before, self.project_bytes())

    def test_next_batch_navigation_progress_does_not_invalidate_business_review(self):
        self.prepare()
        self.seal()
        review.finish(self.root, self.session, self.feedback())
        readme = self.root / ".smart-handbook/README.md"
        readme.write_text(readme.read_text() + "\nNext batch progress.\n")
        result = self.fixture.check()
        self.assertEqual(result["inventory"]["entries"]["approve"]["status"], "accepted")
        entry = self.fixture.inventory["units"][0]["entrypoints"][0]
        new_entry = dict(entry, id="new-entry", status="pending", claims=[], reviews=[])
        self.fixture.inventory["units"][0]["entrypoints"].append(new_entry)
        self.fixture.save_inventory()
        self.assertEqual(self.fixture.check()["inventory"]["next_entries"], ["new-entry"])

    def test_cli_prepares_seals_and_saves_with_actual_clock(self):
        arguments = [sys.executable, str(SKILL / "scripts/review.py"), "prepare", "--root", str(self.root),
                     "--record", self.relative, "--session", str(self.session)]
        result = subprocess.run(arguments, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source_file = Path(self.temporary.name) / "source-feedback.json"
        source_file.write_text(json.dumps({"status": "passed", "isolation": "independent",
                                          "description": "synthetic CLI feedback", "findings": [], "retained": {}}))
        graded_file = Path(self.temporary.name) / "graded-feedback.json"
        graded_file.write_text(json.dumps(self.feedback()))
        for phase, feedback_file in (("seal", source_file), ("finish", graded_file)):
            result = subprocess.run([sys.executable, str(SKILL / "scripts/review.py"), phase,
                                     "--root", str(self.root), "--session", str(self.session),
                                     "--result", str(feedback_file)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(review.read(self.session / "finished.json")["saved"])

    def test_old_v2_review_is_rejected(self):
        self.fixture.record["schema_version"] = 2
        self.fixture.save_review()
        self.assertIn("review-invalid", self.fixture.codes(self.fixture.check()))

    def test_handbook_output_cannot_be_inventoried_even_as_excluded_source(self):
        self.fixture.inventory["files"].append({"path": hb.INVENTORY_PATH, "fingerprint": None,
                                              "role": "output", "units": [], "disposition": "excluded",
                                              "reason": "not business"})
        self.fixture.save_inventory()
        self.assertIn("inventory-invalid", self.fixture.codes(self.fixture.check()))

    def test_failed_question_cannot_be_omitted_from_partial_retry(self):
        extra = copy.deepcopy(self.fixture.record["scenarios"][0])
        extra.update(id="approve-failed", verdict="failed")
        self.fixture.record["scenarios"].append(extra)
        self.fixture.save_review()
        with self.assertRaisesRegex(ValueError, "failed or pending"):
            self.prepare(["approve-normal"])

    def test_new_session_must_be_outside_project_and_not_overwrite_old_session(self):
        before = self.project_bytes()
        with self.assertRaisesRegex(ValueError, "outside"):
            review.prepare(self.root, self.relative, self.root / "session")
        self.prepare()
        with self.assertRaisesRegex(ValueError, "new session"):
            self.prepare()
        self.assertEqual(before, self.project_bytes())

    def test_writes_cannot_follow_state_symlink_into_business_directory(self):
        state = self.root / hb.STATE_PATH
        external = self.root / "src/state.json"
        external.write_bytes(state.read_bytes())
        state.unlink()
        state.symlink_to(external)
        self.prepare()
        self.seal()
        before = self.project_bytes()
        with self.assertRaisesRegex(ValueError, "State symlink"):
            review.finish(self.root, self.session, self.feedback())
        self.assertEqual(before, self.project_bytes())

    def test_retaining_unavailable_reading_cannot_be_relabelled_independent(self):
        extra = copy.deepcopy(self.fixture.record["scenarios"][0])
        extra["id"] = "approve-second"
        self.fixture.record["scenarios"].append(extra)
        self.fixture.record["reader"]["isolation"] = "unavailable"
        self.fixture.save_review()
        with self.assertRaisesRegex(ValueError, "independent reading evidence"):
            self.prepare(["approve-normal"])

    def test_pure_format_update_retains_all_actual_answers_after_explicit_review(self):
        page = self.root / self.fixture.module
        page.write_text(page.read_text() + "\n")
        review.prepare(self.root, self.relative, self.session, retain_all=True)
        result = self.seal(retained={"approve-normal": "One trailing newline; rule, H2 and method unchanged"})
        self.assertFalse(result["reader_required"])
        review.finish(self.root, self.session, {"reader": self.fixture.record["reader"], "scenarios": []})
        record = review.read(self.root / self.relative)
        self.assertEqual(record["scenarios"][0]["reading"], self.fixture.record["scenarios"][0]["reading"])
        self.assertIn("Retained reading at 2026-10-01T10:01:00Z", record["scenarios"][0]["assessment"])
        self.assertEqual(self.fixture.check()["inventory"]["entries"]["approve"]["status"], "accepted")

    def test_another_pending_draft_does_not_block_current_review_preparation(self):
        f = self.fixture
        draft = copy.deepcopy(f.record)
        review.pending(draft)
        draft.update(id="review-second", prepared_at=None, sources={}, pages={})
        draft["scenarios"][0].update(id="second-normal", entrypoints=["second-entry"])
        draft["not_applicable"] = {"second-entry": draft["not_applicable"].pop("approve")}
        relative = ".smart-handbook/.reviews/second.json"
        (self.root / relative).write_text(json.dumps(draft))
        f.inventory["units"][0]["entrypoints"].append({
            "id": "second-entry", "path": f.source, "line": 2, "trigger": "second fixture action",
            "status": "needs-review", "claims": ["approval-01"], "gaps": [], "reviews": [relative]})
        f.save_inventory()
        self.assertFalse([i for i in f.check()["issues"] if i["level"] == "error"])
        self.prepare()
        self.seal()
        review.finish(self.root, self.session, self.feedback())
        self.assertEqual(f.check()["inventory"]["next_entries"], ["second-entry"])


if __name__ == "__main__":
    unittest.main()
