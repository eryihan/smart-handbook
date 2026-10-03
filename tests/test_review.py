import copy
import importlib.util
import json
import shutil
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

    def draft_value(self):
        case = self.fixture.record["scenarios"][0]
        return {"id": "review-new-batch", "target": copy.deepcopy(self.fixture.record["target"]),
                "entries": {"approve": ["approval-01"]},
                "scenarios": [{k: copy.deepcopy(case[k]) for k in
                               ("id", "entrypoints", "topics", "question", "expected")}],
                "not_applicable": copy.deepcopy(self.fixture.record["not_applicable"])}

    def test_plan_reports_all_entry_gaps_and_conflicts_without_writing(self):
        f = self.fixture
        second = copy.deepcopy(f.inventory["units"][0]["entrypoints"][0])
        second.update(id="approve-second", status="needs-review")
        f.inventory["units"][0]["entrypoints"].append(second)
        f.inventory["units"][0]["entrypoints"][0]["status"] = "needs-review"
        f.record["scenarios"][0]["entrypoints"].append("approve-second")
        f.record["not_applicable"] = {"approve": {"normal": {
            "reason": "Synthetic invalid conflict", "sources": [{"path": f.source}]}}}
        f.save_inventory()
        f.save_review()
        before = self.project_bytes()
        result = review.plan(self.root, self.relative)
        self.assertFalse(result["valid"])
        self.assertEqual(set(result["entries"]), {"approve", "approve-second"})
        self.assertEqual(result["entries"]["approve"]["conflicts"], ["normal"])
        self.assertTrue(all(e["missing"] for e in result["entries"].values()))
        with self.assertRaises(review.PlanError) as error:
            self.prepare()
        self.assertEqual(len(error.exception.issues), len(result["issues"]))
        self.assertEqual(before, self.project_bytes())
        self.assertFalse(self.session.exists())

    def test_malformed_exclusion_has_field_errors_before_relation_code(self):
        self.fixture.record["not_applicable"]["approve"]["async"] = "Wrong object shape"
        self.fixture.save_review()
        before = self.project_bytes()
        report = review.plan(self.root, self.relative)
        self.assertTrue(report["issues"])
        self.assertTrue(all(i["code"] == "plan-schema" for i in report["issues"]))
        self.assertIn("not_applicable.approve.async", report["issues"][0]["message"])
        with self.assertRaises(review.PlanError):
            self.prepare()
        self.assertEqual(before, self.project_bytes())

    def test_draft_links_pending_record_preserving_history_state_and_gaps(self):
        f = self.fixture
        f.inventory["status"] = "complete"
        f.save_inventory()
        before = self.project_bytes()
        relative = ".smart-handbook/.reviews/new-batch.json"
        result = review.draft(self.root, relative, self.draft_value())
        record = review.read(self.root / relative)
        inventory = review.read(self.root / hb.INVENTORY_PATH)
        entry = inventory["units"][0]["entrypoints"][0]
        self.assertTrue(result["saved"])
        self.assertEqual(inventory["status"], "incomplete")
        self.assertEqual(entry["status"], "needs-review")
        self.assertEqual(set(entry["reviews"]), {self.relative, relative})
        self.assertEqual(entry["gaps"], f.inventory["units"][0]["entrypoints"][0]["gaps"])
        self.assertEqual(record["scenarios"][0]["verdict"], "pending")
        self.assertEqual(record["source_review"]["status"], "pending")
        self.assertIsNone(record["prepared_at"])
        for path, data in before.items():
            if path != hb.INVENTORY_PATH:
                self.assertEqual((self.root / path).read_bytes(), data)
        self.assertTrue(review.plan(self.root, relative)["valid"])
        self.assertFalse(hb.Handbook(self.root).check()["inventory"]["ready_to_complete"])

    def test_invalid_draft_reports_plan_problems_without_partial_files(self):
        value = self.draft_value()
        value["not_applicable"] = {}
        before = self.project_bytes()
        with self.assertRaises(review.PlanError):
            review.draft(self.root, ".smart-handbook/.reviews/new.json", value)
        self.assertEqual(before, self.project_bytes())

    def test_draft_rejects_overwriting_record_or_duplicate_id(self):
        before = self.project_bytes()
        with self.assertRaisesRegex(ValueError, "new record path"):
            review.draft(self.root, self.relative, self.draft_value())
        value = self.draft_value()
        value["id"] = self.fixture.record["id"]
        with self.assertRaisesRegex(ValueError, "unique review ID"):
            review.draft(self.root, ".smart-handbook/.reviews/new.json", value)
        self.assertEqual(before, self.project_bytes())

    def test_draft_rejects_unknown_claims_and_mismatched_scope(self):
        before = self.project_bytes()
        for value in (dict(self.draft_value(), entries={"approve": ["unknown-claim"]}),
                      dict(self.draft_value(), entries={"other-entry": ["approval-01"]})):
            with self.assertRaises(ValueError):
                review.draft(self.root, ".smart-handbook/.reviews/new.json", value)
        self.assertEqual(before, self.project_bytes())

    def test_draft_failure_rolls_back_new_record_and_inventory(self):
        before = self.project_bytes()
        real_replace = review.os.replace

        def fail_inventory(source, target):
            if str(target).endswith(".inventory.json"):
                raise OSError("synthetic inventory write failure")
            return real_replace(source, target)

        with patch.object(review.os, "replace", side_effect=fail_inventory):
            with self.assertRaises(OSError):
                review.draft(self.root, ".smart-handbook/.reviews/new.json", self.draft_value())
        self.assertEqual(before, self.project_bytes())

    def test_draft_cannot_follow_inventory_symlink_into_business_directory(self):
        path = self.root / hb.INVENTORY_PATH
        external = self.root / "src/inventory.json"
        external.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(external)
        before = self.project_bytes()
        with self.assertRaisesRegex(ValueError, "Inventory symlink"):
            review.draft(self.root, ".smart-handbook/.reviews/new.json", self.draft_value())
        self.assertEqual(before, self.project_bytes())

    def test_automatic_sessions_are_unique_and_feedback_templates_cannot_pass(self):
        before = self.project_bytes()
        sessions = []
        for _ in range(2):
            result = review.prepare(self.root, self.relative)
            session = Path(result["session"])
            self.addCleanup(shutil.rmtree, session)
            sessions.append(session)
            source = review.read(Path(result["source_feedback"]))
            self.assertEqual(source["status"], "pending")
            with self.assertRaisesRegex(ValueError, "not pending"):
                review.seal(self.root, session, source)
            review.seal(self.root, session, {"status": "passed", "isolation": "independent",
                "description": "synthetic actual feedback", "findings": [], "retained": {}})
            with self.assertRaisesRegex(ValueError, "actual grading"):
                review.finish(self.root, session, review.read(Path(result["graded_feedback"])))
            self.assertFalse(any(p.name in ("source-feedback.json", "graded-feedback.json")
                                 for p in (session / "reader").rglob("*")))
        self.assertNotEqual(*sessions)
        self.assertEqual(before, self.project_bytes())

    def test_feedback_template_lists_retained_ids_without_invented_assessments(self):
        extra = copy.deepcopy(self.fixture.record["scenarios"][0])
        extra["id"] = "approve-second"
        self.fixture.record["scenarios"].append(extra)
        self.fixture.save_review()
        result = self.prepare(["approve-normal"])
        source = review.read(Path(result["source_feedback"]))
        graded = review.read(Path(result["graded_feedback"]))
        self.assertEqual(source["retained"], {"approve-second": ""})
        self.assertEqual([c["id"] for c in graded["scenarios"]], ["approve-normal"])
        source.update(status="passed", isolation="independent")
        with self.assertRaisesRegex(ValueError, "explicit source/diff"):
            review.seal(self.root, self.session, source)

    def test_source_task_keeps_facts_and_retained_reading_without_duplicate_history(self):
        extra = copy.deepcopy(self.fixture.record["scenarios"][0])
        extra["id"] = "approve-second"
        self.fixture.record["scenarios"].append(extra)
        self.fixture.save_review()
        result = self.prepare(["approve-normal"])
        task = review.read(Path(result["source_task"]))
        self.assertEqual(task["selected"][0]["expected"], self.fixture.record["scenarios"][0]["expected"])
        self.assertEqual(task["retained"][0]["previous_reading"], extra["reading"])
        self.assertNotIn("assessment", task["selected"][0])
        self.assertNotIn("original", task)
        self.assertFalse((self.session / "reader/source-task.json").exists())
        Path(result["source_task"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source task changed"):
            self.seal(retained={"approve-second": "Synthetic unchanged facts"})

    def test_draft_preserves_recorded_gap_and_cannot_make_it_complete(self):
        entry = self.fixture.inventory["units"][0]["entrypoints"][0]
        entry.update(status="known-gap", gaps=["Synthetic unresolved local receiver"])
        self.fixture.save_inventory()
        review.draft(self.root, ".smart-handbook/.reviews/new.json", self.draft_value())
        inventory = review.read(self.root / hb.INVENTORY_PATH)
        self.assertEqual(inventory["units"][0]["entrypoints"][0]["gaps"], entry["gaps"])
        self.assertFalse(self.fixture.check()["inventory"]["ready_to_complete"])

    def test_cli_draft_auto_prepare_seal_finish_keeps_agent_acceptance_explicit(self):
        value = self.draft_value()
        plan_file = Path(self.temporary.name) / "plan.json"
        plan_file.write_text(json.dumps(value), encoding="utf-8")
        relative = ".smart-handbook/.reviews/new.json"
        base = [sys.executable, str(SKILL / "scripts/review.py")]

        def invoke(phase, *args):
            result = subprocess.run(base + [phase, "--root", str(self.root), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

        invoke("draft", "--record", relative, "--input", str(plan_file))
        invoke("plan", "--record", relative)
        prepared = invoke("prepare", "--record", relative)
        session = Path(prepared["session"])
        self.addCleanup(shutil.rmtree, session)
        source = {"status": "passed", "isolation": "independent", "description": "synthetic CLI feedback",
                  "findings": [], "retained": {}}
        Path(prepared["source_feedback"]).write_text(json.dumps(source), encoding="utf-8")
        invoke("seal", "--session", str(session), "--result", prepared["source_feedback"])
        Path(prepared["graded_feedback"]).write_text(json.dumps(self.feedback()), encoding="utf-8")
        invoke("finish", "--session", str(session), "--result", prepared["graded_feedback"])
        inventory = review.read(self.root / hb.INVENTORY_PATH)
        self.assertEqual(inventory["units"][0]["entrypoints"][0]["status"], "needs-review")
        inventory["units"][0]["entrypoints"][0]["status"] = "accepted"
        (self.root / hb.INVENTORY_PATH).write_text(json.dumps(inventory), encoding="utf-8")
        self.assertFalse([i for i in self.fixture.check()["issues"] if i["level"] == "error"])

    def test_unrelated_live_page_update_during_reading_keeps_frozen_batch_valid(self):
        self.prepare()
        self.seal()
        unrelated = self.root / self.fixture.flow
        unrelated.write_text(unrelated.read_text() + "\nNext independent batch note.\n")
        review.finish(self.root, self.session, self.feedback())
        self.assertEqual(self.fixture.check()["inventory"]["entries"]["approve"]["status"], "accepted")

    def test_cli_plan_reports_invalid_input_as_json_and_draft_accepts_plain_json(self):
        value = self.draft_value()
        plan_file = Path(self.temporary.name) / "plan.json"
        plan_file.write_text(json.dumps(value), encoding="utf-8")
        relative = ".smart-handbook/.reviews/new.json"
        base = [sys.executable, str(SKILL / "scripts/review.py")]
        result = subprocess.run(base + ["draft", "--root", str(self.root), "--record", relative,
                                       "--input", str(plan_file)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = review.read(self.root / relative)
        record["not_applicable"] = {}
        (self.root / relative).write_text(json.dumps(record), encoding="utf-8")
        before = self.project_bytes()
        result = subprocess.run(base + ["plan", "--root", str(self.root), "--record", relative],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["valid"])
        self.assertEqual(before, self.project_bytes())

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
