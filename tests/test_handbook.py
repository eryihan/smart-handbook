import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO
spec = importlib.util.spec_from_file_location("handbook", SKILL / "scripts" / "handbook.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)


class HandbookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".smart-handbook/modules").mkdir(parents=True)
        (self.root / ".smart-handbook/flows").mkdir()
        (self.root / "src").mkdir()
        (self.root / "config").mkdir()
        self.source = "src/ApprovalService.java"
        (self.root / self.source).write_text("class ApprovalService {\n public void approve(String request) {}\n}\n")
        (self.root / "config/application.yml").write_text("approval: true\n")
        for source in (SKILL / "assets/handbook").glob("*-template.md"):
            stem = source.name.replace("-template", "")
            if stem == "module.md":
                dest = self.root / ".smart-handbook/modules/approval.md"
            elif stem == "flow.md":
                dest = self.root / ".smart-handbook/flows/approval.md"
            else:
                dest = self.root / ".smart-handbook" / stem
            dest.write_text(source.read_text())
        self.module = ".smart-handbook/modules/approval.md"
        self.flow = ".smart-handbook/flows/approval.md"
        self.change_meta(self.module, id="module-approval", coverage="documented",
                         source_ranges=["src"], config_ranges=["config"], claims=[{
                             "id": "approval-01", "section": "当前行为与关键约束",
                             "sources": [{"path": self.source, "symbol": "ApprovalService#approve(String)"}]}])
        self.change_meta(self.flow, id="flow-approval", modules=["module-approval"])
        self.change_meta(".smart-handbook/map.md", modules=[{
            "id": "module-approval", "page": self.module, "keywords": ["审批", "数据未生效"],
            "source_ranges": ["src"], "config_ranges": ["config"]}])
        self.state = {"schema_version": 3, "pages": {self.module: {
            "sources": {self.source: hb.fingerprint(self.root / self.source)},
            "verification": {"status": "not-run", "conditions": "fixture only", "method": "none", "observed": "not executed"}}}}
        self.save_state()
        self.inventory = {
            "schema_version": 3, "mode": "full", "status": "in-progress",
            "target": {"commit": None, "worktree": "fixture", "recorded_at": "2026-10-02T10:00:00+08:00"},
            "scope": {"include": ["src", "config"], "exclude": []},
            "discovery": {"checked": ["src", "config"], "methods": ["fixture declarations"], "remaining": []},
            "files": [{"path": path, "fingerprint": hb.fingerprint(self.root / path),
                       "role": "fixture implementation", "units": ["business-approval"],
                       "disposition": "assigned", "reason": ""}
                      for path in (self.source, "config/application.yml")],
            "units": [{"id": "business-approval", "name": "审批",
                       "entrypoints": [{"id": "approve", "path": self.source, "symbol": "ApprovalService#approve(String)",
                                        "trigger": "fixture API", "kind": "action", "status": "accepted", "claims": ["approval-01"],
                                        "gaps": [], "reviews": [".smart-handbook/.reviews/approval.json"]}],
                       "pages": [self.module, self.flow], "sources": [self.source],
                       "depends_on": [], "gaps": []}]}
        self.save_inventory()
        self.review_path = ".smart-handbook/.reviews/approval.json"
        self.record = {
            "schema_version": 3, "id": "review-approval", "target": {"commit": None, "worktree": "synthetic fixture"},
            "sources": {self.source: hb.fingerprint(self.root / self.source)},
            "pages": {self.module: hb.fingerprint(self.root / self.module)},
            "prepared_at": "2026-10-01T09:59:00Z",
            "source_review": {"status": "passed", "isolation": "independent", "context": "fresh", "description": "synthetic source-review fixture",
                              "input_fingerprint": None, "findings": []},
            "source_reviewed_at": "2026-10-01T10:00:00Z",
            "reader": {"isolation": "independent", "description": "synthetic record, no real AI reading"},
            "scenarios": [{"id": "approve-normal", "entrypoints": ["approve"], "topics": ["normal"],
                "question": "What does approve do?",
                "expected": {"answer": "Returns without changes", "sources": [{"path": self.source, "symbol": "ApprovalService#approve(String)"}]},
                "reading": {"status": "answered", "answer": "Returns without changes", "unanswered": [],
                    "evidence": [{"page": self.module, "section": "当前行为与关键约束"}],
                    "locations": [{"path": self.source, "symbol": "ApprovalService#approve(String)"}]},
                "verdict": "passed", "assessment": "Synthetic fixture only", "reviewed_at": "2026-10-01T10:01:00Z"}],
            "not_applicable": {"approve": {topic: {"reason": "The fixture method is empty", "sources": [{"path": self.source}]}
                for topic in hb.REVIEW_TOPICS - {"normal"}}}}
        self.save_review()

    def save_review(self, refresh_proof=True):
        # Synthetic fixtures explicitly simulate a new source review; this is not AI acceptance.
        if refresh_proof:
            self.record["source_review"]["input_fingerprint"] = hb.review_input_fingerprint(self.record)
        path = self.root / self.review_path
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(self.record))

    def refresh_review_snapshots(self):
        meta = json.loads(hb.META_RE.search((self.root / self.module).read_text())[1])
        sources = {s["path"] for c in meta["claims"] for s in c["sources"]}
        self.record["sources"] = {p: hb.fingerprint(self.root / p) for p in sources}
        self.record["pages"][self.module] = hb.fingerprint(self.root / self.module)
        self.save_review()

    def test_class_inventory_cannot_certify_all_handlers(self):
        self.inventory["units"][0]["entrypoints"][0]["symbol"] = "ApprovalService"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def test_unconfirmed_action_granularity_blocks_completion_without_resetting_reviews(self):
        self.inventory["status"] = "complete"
        entry = self.inventory["units"][0]["entrypoints"][0]
        entry.pop("kind")
        self.save_inventory()
        before = (self.root / self.review_path).read_bytes()
        result = self.check()
        self.assertEqual(result["inventory"]["action_candidates"], ["approve"])
        self.assertEqual(result["inventory"]["next_entries"], [])
        self.assertFalse(result["inventory"]["ready_to_complete"])
        self.assertEqual(result["inventory"]["entries"]["approve"]["status"], "accepted")
        self.assertEqual(before, (self.root / self.review_path).read_bytes())
        entry["kind"] = "action"  # Fixture simulates confirming the actual handler, not rereading business.
        self.save_inventory()
        self.assertTrue(self.check()["inventory"]["ready_to_complete"])

    def test_legacy_evidence_limits_are_scoped_candidates_not_automatic_reading_failures(self):
        self.record["source_review"].pop("context")
        self.record["scenarios"][0]["reading"].pop("unanswered")
        self.save_review()
        result = self.check()
        attention = result["inventory"]["review_attention"]
        self.assertTrue(any("source-context-unconfirmed" in r["reasons"] for r in attention))
        self.assertTrue(any("original-reading-unbound" in r["reasons"] for r in attention))
        self.assertTrue(all(r["entrypoints"] == ["approve"] for r in attention))
        self.assertEqual(result["inventory"]["next_entries"], [])
        self.assertNotIn("review-invalid", self.codes(result))

    def test_explicit_unanswered_business_question_cannot_be_passed(self):
        self.record["scenarios"][0]["reading"]["unanswered"] = ["Cannot locate the save handler"]
        self.save_review()
        result = self.check()
        self.assertIn("review-invalid", self.codes(result))
        self.assertFalse(result["inventory"]["ready_to_complete"])

    def test_authoring_context_cannot_certify_independent_source_review(self):
        self.record["source_review"]["context"] = "authoring"
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))

    def test_text_check_preview_is_bounded_without_truncating_json_queues(self):
        result = self.check()
        result["inventory"]["action_candidates"] = ["action-" + str(i) for i in range(20)]
        text = hb.render(result)
        self.assertIn("action_candidates: 20; first 10:", text)
        self.assertNotIn('"action-19"', text)
        self.assertEqual(len(result["inventory"]["action_candidates"]), 20)

    def test_accepted_entry_requires_an_existing_handler_location(self):
        entry = self.inventory["units"][0]["entrypoints"][0]
        entry["symbol"] = "ApprovalService#missing()"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        del entry["symbol"]
        entry["line"] = 9999
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def test_review_locations_must_exist_in_unchanged_sources(self):
        scenario = self.record["scenarios"][0]
        scenario["reading"]["locations"] = [{"path": self.source, "symbol": "ApprovalService"}]
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        scenario["reading"]["locations"] = [{"path": self.source, "symbol": "ApprovalService#missing()"}]
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        scenario["reading"]["locations"] = [{"path": self.source, "line": 9999}]
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        scenario["reading"]["locations"] = [{"path": self.source, "line": 2}]
        self.save_review()
        self.assertNotIn("review-invalid", self.codes(self.check()))
        scenario["reading"]["locations"] = [{"path": self.source, "line": 9999}]
        self.save_review()
        (self.root / self.source).write_text("// changed source\n")
        result = self.check()
        self.assertNotIn("review-invalid", self.codes(result))
        self.assertIn("review-snapshot-changed", self.codes(result))

    def test_full_completion_rejects_a_navigation_entry_on_documented_page(self):
        unit = self.inventory["units"][0]
        unit["entrypoints"].append({"id": "reject", "path": self.source, "symbol": "ApprovalService#reject()",
            "trigger": "another API", "status": "pending", "claims": [], "gaps": [], "reviews": []})
        self.inventory["status"] = "complete"
        self.save_inventory()
        result = self.check()
        self.assertIn("inventory-invalid", self.codes(result))
        self.assertEqual(result["pages"][self.module]["coverage"], "documented")

    def test_unit_status_and_page_review_cannot_be_manually_duplicated(self):
        self.inventory["units"][0]["status"] = "accepted"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        del self.inventory["units"][0]["status"]
        self.save_inventory()
        self.state["pages"][self.module]["review"] = {"status": "reviewed_by_ai", "reviewed_at": "2026-10-01T10:00:00Z"}
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))

    def test_failed_reading_case_blocks_completion_even_after_page_repair(self):
        failed = json.loads(json.dumps(self.record["scenarios"][0]))
        failed.update(id="approve-missing-table", verdict="failed", assessment="Reader omitted a table")
        self.record["scenarios"].append(failed)
        self.save_review()
        self.inventory["status"] = "complete"
        self.save_inventory()
        result = self.check()
        self.assertIn("entry-review-incomplete", self.codes(result))
        self.assertEqual(result["inventory"]["status"], "incomplete")
        (self.root / self.module).write_text((self.root / self.module).read_text() + "\n补齐表名\n")
        self.refresh_review_snapshots()
        self.assertEqual(self.check()["inventory"]["status"], "incomplete")

    def test_unavailable_or_unanswered_reading_cannot_pass(self):
        for field, value in (("status", "unavailable"), ("answer", ""), ("evidence", []), ("locations", [])):
            with self.subTest(field=field):
                old = self.record["scenarios"][0]["reading"][field]
                self.record["scenarios"][0]["reading"][field] = value
                self.save_review()
                self.assertIn("review-invalid", self.codes(self.check()))
                self.record["scenarios"][0]["reading"][field] = old

    def test_review_of_another_entry_does_not_certify_requested_entry(self):
        self.record["scenarios"][0]["entrypoints"] = ["some-other-business"]
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        self.assertIn("entry-review-incomplete", self.codes(self.check()))

    def test_review_topics_require_scenarios_or_source_backed_reasons(self):
        del self.record["not_applicable"]["approve"]["repeat"]
        self.save_review()
        self.assertIn("entry-review-incomplete", self.codes(self.check()))
        self.record["not_applicable"]["approve"]["repeat"] = {"reason": "No writes", "sources": []}
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))

    def test_topic_cannot_be_both_tested_and_not_applicable(self):
        self.record["not_applicable"]["approve"]["normal"] = {"reason": "No behavior", "sources": [{"path": self.source}]}
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))

    def test_unknown_claim_duplicate_entry_and_missing_review_are_rejected(self):
        entry = self.inventory["units"][0]["entrypoints"][0]
        entry["claims"] = ["unknown-claim"]
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        entry["claims"] = ["approval-01"]
        self.inventory["units"][0]["entrypoints"].append(dict(entry))
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        self.inventory["units"][0]["entrypoints"].pop()
        self.save_inventory()
        (self.root / self.review_path).unlink()
        self.assertIn("review-invalid", self.codes(self.check()))

    def test_future_and_reversed_review_times_are_rejected(self):
        self.record["source_reviewed_at"] = "2999-01-01T10:00:00Z"
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        self.record["source_reviewed_at"] = "2026-10-01T10:02:00Z"
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        self.inventory["target"]["recorded_at"] = "2999-01-01T10:00:00Z"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def test_database_claim_requires_mapping_evidence(self):
        source = {"path": self.source, "roles": ["implementation"]}
        self.change_meta(self.module, claims=[{"id": "approval-01", "section": "当前行为与关键约束",
            "resource_types": ["database"], "sources": [source]}])
        self.assertIn("claim-evidence-incomplete", self.codes(self.check()))
        source["roles"].append("persistence")  # SQL annotations may share the implementation file.
        self.change_meta(self.module, claims=[{"id": "approval-01", "section": "当前行为与关键约束",
            "resource_types": ["database"], "sources": [source]}])
        self.refresh_review_snapshots()
        self.assertFalse(self.check()["issues"])

    def test_middleware_and_async_claims_require_config_and_receiver_evidence(self):
        for kind, role in (("mq", "configuration"), ("redis", "configuration"), ("async", "handoff")):
            with self.subTest(kind=kind):
                source = {"path": self.source, "roles": ["implementation"]}
                self.change_meta(self.module, claims=[{"id": "approval-01", "section": "当前行为与关键约束",
                    "resource_types": [kind], "sources": [source]}])
                self.assertIn("claim-evidence-incomplete", self.codes(self.check()))
                source["roles"].append(role)
                self.change_meta(self.module, claims=[{"id": "approval-01", "section": "当前行为与关键约束",
                    "resource_types": [kind], "sources": [source]}])
                self.refresh_review_snapshots()
                self.assertFalse(self.check()["issues"])

    def test_review_source_and_page_changes_invalidate_recorded_completion(self):
        self.inventory["status"] = "complete"
        self.save_inventory()
        for rel in (self.source, self.module):
            with self.subTest(path=rel):
                path = self.root / rel
                old = path.read_bytes()
                path.write_bytes(old + b"\nchanged\n")
                result = self.check()
                self.assertIn("review-snapshot-changed", self.codes(result))
                self.assertEqual(result["inventory"]["entries"]["approve"]["status"], "needs-review")
                self.assertEqual(result["inventory"]["status"], "incomplete")
                path.write_bytes(old)

    def test_advancing_baseline_cannot_overwrite_old_review_proof(self):
        (self.root / self.source).write_text("class ApprovalService { public void approve(String request) { throw new RuntimeException(); } }\n")
        self.inventory["files"][0]["fingerprint"] = hb.fingerprint(self.root / self.source)
        self.state["pages"][self.module]["sources"][self.source] = hb.fingerprint(self.root / self.source)
        self.save_inventory()
        self.save_state()
        result = self.check()
        self.assertEqual(result["pages"][self.module]["source_state"], "unchanged")
        self.assertEqual(result["pages"][self.module]["review"], "needs_review")
        self.assertIn("review-snapshot-changed", self.codes(result))

    def test_handbook_only_edit_is_a_review_candidate_without_code_diff(self):
        (self.root / self.module).write_text((self.root / self.module).read_text() + "\n状态改为立即生效\n")
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["review_candidates"], [{"id": "approve", "reviews": [self.review_path]}])

    def test_shared_unit_is_certified_only_by_linked_entry_evidence(self):
        shared = {"id": "shared-rule", "name": "公共规则", "entrypoints": [], "pages": [self.module],
                  "sources": [self.source], "depends_on": [], "gaps": []}
        self.inventory["units"].append(shared)
        self.inventory["files"][0]["units"].append("shared-rule")
        self.inventory["status"] = "complete"
        self.save_inventory()
        self.assertEqual(self.check()["inventory"]["units"]["shared-rule"]["status"], "accepted")
        shared["sources"] = ["config/application.yml"]
        self.inventory["files"][1]["units"].append("shared-rule")
        self.save_inventory()
        result = self.check()
        self.assertIn("inventory-completion-conflict", self.codes(result))
        self.assertEqual(result["inventory"]["status"], "incomplete")

    def test_shared_unit_without_sources_uses_its_page_claims(self):
        self.inventory["units"].append({"id": "shared-rule", "name": "shared fixture",
            "entrypoints": [], "pages": [self.module], "sources": [], "depends_on": [], "gaps": []})
        self.save_inventory()
        result = self.check()["inventory"]
        self.assertEqual(result["units"]["shared-rule"]["status"], "accepted")
        self.assertEqual(result["units"]["shared-rule"]["unverified_sources"], [])

    def test_shared_page_fingerprints_alone_do_not_certify_unused_source(self):
        self.change_meta(self.flow, claims=[{"id": "shared-config", "section": "正常路径与模块交接",
                                            "sources": [{"path": "config/application.yml"}]}])
        self.inventory["units"].append({"id": "shared-rule", "name": "shared fixture",
            "entrypoints": [], "pages": [self.flow], "sources": [], "depends_on": [], "gaps": []})
        self.save_inventory()
        self.record["sources"]["config/application.yml"] = hb.fingerprint(self.root / "config/application.yml")
        self.record["pages"][self.flow] = hb.fingerprint(self.root / self.flow)
        self.save_review()
        result = self.check()["inventory"]
        self.assertEqual(result["units"]["shared-rule"]["status"], "needs-review")
        self.assertEqual(result["units"]["shared-rule"]["unverified_sources"], ["config/application.yml"])
        self.assertFalse(result["ready_to_complete"])

    def test_reader_cited_shared_source_can_supply_its_verified_usage_evidence(self):
        self.change_meta(self.flow, claims=[{"id": "shared-config", "section": "正常路径与模块交接",
                                            "sources": [{"path": "config/application.yml"}]}])
        self.inventory["units"].append({"id": "shared-rule", "name": "shared fixture",
            "entrypoints": [], "pages": [self.flow], "sources": [], "depends_on": [], "gaps": []})
        self.save_inventory()
        self.record["sources"]["config/application.yml"] = hb.fingerprint(self.root / "config/application.yml")
        self.record["pages"][self.flow] = hb.fingerprint(self.root / self.flow)
        self.record["scenarios"][0]["reading"]["locations"].append({"path": "config/application.yml", "line": 1})
        self.save_review()
        result = self.check()["inventory"]
        self.assertEqual(result["units"]["shared-rule"]["status"], "accepted")
        self.record["scenarios"][0]["verdict"] = "failed"
        self.save_review()
        result = self.check()["inventory"]
        self.assertEqual(result["units"]["shared-rule"]["status"], "needs-review")

    def test_review_paths_and_expected_answers_cannot_escape_repository(self):
        self.inventory["units"][0]["entrypoints"][0]["reviews"] = ["../outside.json"]
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        self.inventory["units"][0]["entrypoints"][0]["reviews"] = [self.review_path]
        self.save_inventory()
        self.record["scenarios"][0]["expected"]["sources"] = [{"path": "../outside.java"}]
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))

    def test_full_completion_preserves_unresolved_local_gap(self):
        self.inventory["units"][0]["gaps"] = ["local receiver has not been traced"]
        self.inventory["status"] = "complete"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def test_v1_inventory_is_rejected_without_migration(self):
        self.inventory["schema_version"] = 1
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def change_meta(self, rel, **updates):
        path = self.root / rel
        text = path.read_text()
        match = hb.META_RE.search(text)
        meta = json.loads(match[1])
        if "claims" in updates:
            for claim in updates["claims"]:
                claim.setdefault("resource_types", [])
                for source in claim["sources"]:
                    source.setdefault("roles", ["implementation"])
        meta.update(updates)
        path.write_text(text[:match.start()] + "<!-- handbook-meta\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n-->" + text[match.end():])

    def save_state(self):
        (self.root / ".smart-handbook/.state.json").write_text(json.dumps(self.state))

    def save_inventory(self):
        (self.root / ".smart-handbook/.inventory.json").write_text(json.dumps(self.inventory))

    def test_inventory_is_required_and_invalid_json_is_read_only(self):
        path = self.root / ".smart-handbook/.inventory.json"
        path.unlink()
        self.assertIn("inventory-missing", self.codes(self.check()))
        path.write_text("{broken")
        before = (self.root / self.module).read_bytes()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        self.assertEqual(path.read_text(), "{broken")
        self.assertEqual((self.root / self.module).read_bytes(), before)

    def test_inventory_completion_requires_entry_reviews(self):
        self.inventory["status"] = "complete"
        entry = self.inventory["units"][0]["entrypoints"][0]
        entry["status"] = "needs-review"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        entry["status"] = "accepted"
        self.save_inventory()
        self.assertFalse(self.check()["issues"])
        self.record["reader"]["isolation"] = "unavailable"
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))
        self.assertEqual(self.check()["inventory"]["status"], "incomplete")

    def test_inventory_rejects_pending_discovery_and_unknown_owners(self):
        self.inventory["mode"] = "navigation"
        self.inventory["status"] = "complete"
        self.inventory["discovery"]["remaining"] = ["dynamic registration not read"]
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        self.inventory["status"] = "in-progress"
        self.inventory["files"][0]["units"] = ["missing-unit"]
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def test_inventory_allows_agent_roles_and_project_extensions(self):
        self.inventory["files"][0]["role"] = "project-specific generated dispatcher"
        self.inventory["units"][0]["project_note"] = "Agent decides domain boundaries"
        self.save_inventory()
        self.assertFalse(self.check()["issues"])

    def test_inventory_changed_shared_config_finds_transitive_units_with_cycle(self):
        shared = json.loads(json.dumps(self.inventory["units"][0]))
        shared.update(id="shared-policy", name="公共规则", entrypoints=[], pages=[self.module],
                      sources=["config/application.yml"], depends_on=["business-approval"])
        self.inventory["units"].append(shared)
        self.inventory["units"][0]["depends_on"] = ["shared-policy"]
        self.inventory["files"][1]["units"].append("shared-policy")
        self.save_inventory()
        before = (self.root / ".smart-handbook/.inventory.json").read_bytes()
        (self.root / "config/application.yml").write_text("approval: false\n")
        result = self.check()
        self.assertIn("inventory-source-changed", self.codes(result))
        self.assertEqual(result["pages"][self.module]["source_state"], "unchanged")
        self.assertEqual(result["pages"][self.module]["review"], "needs_review")
        self.assertEqual({unit["id"] for unit in result["inventory"]["related_units"]},
                         {"business-approval", "shared-policy"})
        impact = hb.impact(hb.Handbook(self.root))
        self.assertIn("config/application.yml", impact["changed_files"])
        self.assertEqual({unit["id"] for unit in impact["related_units"]},
                         {"business-approval", "shared-policy"})
        self.assertEqual(before, (self.root / ".smart-handbook/.inventory.json").read_bytes())

    def test_inventory_scope_and_entries_cannot_escape_repository(self):
        self.inventory["scope"]["include"] = ["../outside"]
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))
        self.inventory["scope"]["include"] = ["src"]
        self.inventory["units"][0]["entrypoints"][0]["path"] = "/etc/hosts"
        self.save_inventory()
        self.assertIn("inventory-invalid", self.codes(self.check()))

    def test_completed_inventory_becomes_incomplete_when_source_changes(self):
        self.inventory["status"] = "complete"
        self.save_inventory()
        path = self.root / ".smart-handbook/.inventory.json"
        before = path.read_bytes()
        (self.root / "config/application.yml").write_text("approval: false\n")
        result = self.check()
        self.assertEqual(result["inventory"]["recorded_status"], "complete")
        self.assertEqual(result["inventory"]["status"], "incomplete")
        self.assertEqual(result["pages"][self.module]["review"], "needs_review")
        self.assertEqual(before, path.read_bytes())

    def check(self):
        return hb.Handbook(self.root).check()

    def codes(self, result):
        return {issue["code"] for issue in result["issues"]}

    def run_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE).decode().strip()

    def git_baseline(self):
        self.run_git("init", "-b", "main")
        self.run_git("add", ".")
        self.run_git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "baseline")
        return self.run_git("rev-parse", "HEAD")

    def test_clean_fixture_and_no_state_mutation(self):
        before = (self.root / ".smart-handbook/.state.json").read_bytes()
        result = self.check()
        self.assertFalse(result["issues"], result["issues"])
        page = result["pages"][self.module]
        self.assertEqual(page["source_state"], "unchanged")
        self.assertEqual(page["review"], "reviewed_by_ai")
        self.assertEqual(page["recorded_verification"]["status"], "not-run")
        self.assertEqual(before, (self.root / ".smart-handbook/.state.json").read_bytes())

    def test_documented_module_without_claims_requires_content_review(self):
        self.change_meta(self.module, claims=[])
        before = (self.root / ".smart-handbook/.state.json").read_bytes()
        result = self.check()
        self.assertIn("documented-without-claims", self.codes(result))
        self.assertEqual(result["pages"][self.module]["review"], "needs_review")
        self.assertEqual(before, (self.root / ".smart-handbook/.state.json").read_bytes())

    def test_documented_flow_without_claims_warns_but_navigation_does_not(self):
        self.change_meta(self.flow, coverage="documented")
        warnings = [issue for issue in self.check()["issues"]
                    if issue["code"] == "documented-without-claims"]
        self.assertEqual([issue["path"] for issue in warnings], [self.flow])
        self.change_meta(self.flow, coverage="navigation-only")
        self.assertNotIn("documented-without-claims", self.codes(self.check()))

    def test_documented_working_guide_does_not_need_behavior_claims(self):
        self.change_meta(".smart-handbook/working-guide.md", coverage="documented")
        self.assertNotIn("documented-without-claims", self.codes(self.check()))

    def test_hidden_directory_is_required_no_legacy_fallback(self):
        for old_name in ("handbook", ".smart_handbook"):
            with self.subTest(directory=old_name):
                directory = self.root / ".smart-handbook"
                old = self.root / old_name
                directory.rename(old)
                try:
                    result = self.check()
                    self.assertIn("handbook-missing", self.codes(result))
                    self.assertEqual(result["pages"], {})
                finally:
                    old.rename(directory)

    def test_legacy_state_page_path_is_rejected(self):
        record = self.state["pages"].pop(self.module)
        for old_path in ("handbook/modules/approval.md", ".smart_handbook/modules/approval.md"):
            with self.subTest(path=old_path):
                self.state["pages"] = {old_path: record}
                self.save_state()
                self.assertIn("state-invalid", self.codes(self.check()))

    def test_behavior_change_with_same_symbol_requires_review(self):
        with (self.root / self.source).open("a") as file:
            file.write("// implementation changed\n")
        page = self.check()["pages"][self.module]
        self.assertEqual(page["source_state"], "changed")
        self.assertEqual(page["review"], "needs_review")

    def test_implementation_sql_and_config_changes_without_interface_change(self):
        implementation = "src/ApprovalServiceImpl.java"
        sql = "src/ApprovalMapper.xml"
        config = "config/application.yml"
        (self.root / implementation).write_text("class ApprovalServiceImpl {}\n")
        (self.root / sql).write_text("<mapper><update id='approve'>UPDATE approval SET status=1</update></mapper>\n")
        self.change_meta(self.module, claims=[{
            "id": "approval-01", "section": "当前行为与关键约束",
            "sources": [{"path": path} for path in (self.source, implementation, sql, config)]}])
        self.state["pages"][self.module]["sources"] = {
            path: hb.fingerprint(self.root / path) for path in (self.source, implementation, sql, config)}
        self.save_state()
        interface_before = (self.root / self.source).read_bytes()
        for dependency in (implementation, sql, config):
            with self.subTest(dependency=dependency):
                target = self.root / dependency
                before = target.read_bytes()
                target.write_bytes(before + b"\nchanged\n")
                try:
                    page = self.check()["pages"][self.module]
                    self.assertEqual(page["source_state"], "changed")
                    self.assertEqual(page["review"], "needs_review")
                    self.assertEqual(page["sources"][self.source]["status"], "unchanged")
                    impact = hb.impact(hb.Handbook(self.root))
                    self.assertEqual(impact["changed_files"], [dependency])
                    self.assertEqual(impact["related_modules"], [{"id": "module-approval", "page": self.module}])
                    self.assertEqual(impact["related_flows"], [{"id": "flow-approval", "page": self.flow}])
                finally:
                    target.write_bytes(before)
        self.assertEqual(interface_before, (self.root / self.source).read_bytes())

    def test_file_deleted(self):
        (self.root / self.source).unlink()
        result = self.check()
        self.assertIn("source-broken", self.codes(result))
        self.assertEqual(result["pages"][self.module]["source_state"], "broken")

    def test_file_renamed(self):
        (self.root / self.source).rename(self.root / "src/Renamed.java")
        self.assertIn("source-broken", self.codes(self.check()))

    def test_missing_baseline_is_not_unchanged(self):
        (self.root / ".smart-handbook/.state.json").unlink()
        result = self.check()
        self.assertEqual(result["pages"][self.module]["source_state"], "baseline-unavailable")

    def test_damaged_state_preserves_markdown(self):
        before = (self.root / self.module).read_bytes()
        (self.root / ".smart-handbook/.state.json").write_text("{oops")
        self.assertIn("state-invalid", self.codes(self.check()))
        self.assertEqual(before, (self.root / self.module).read_bytes())

    def test_state_schema_version_and_digest(self):
        self.state["schema_version"] = 4
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))
        self.state["schema_version"] = 3
        self.state["pages"][self.module]["sources"][self.source] = "sha256:abc"
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))

    def test_bad_metadata_json(self):
        path = self.root / self.module
        path.write_text(path.read_text().replace('"schema_version": 3', '"schema_version":'))
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_duplicate_json_keys(self):
        path = self.root / self.module
        path.write_text(path.read_text().replace('"schema_version": 3', '"schema_version": 3, "schema_version": 3'))
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_unsupported_metadata_schema(self):
        self.change_meta(self.module, schema_version=4)
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_bool_is_not_schema_version(self):
        self.change_meta(self.module, schema_version=True)
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_metadata_wrong_location(self):
        path = self.root / self.module
        text = path.read_text()
        block = hb.META_RE.search(text)[0]
        path.write_text(text.replace(block, "") + "\n" + block)
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_duplicate_metadata_and_code_example_ignored(self):
        path = self.root / self.module
        block = hb.META_RE.search(path.read_text())[0]
        path.write_text(path.read_text() + "\n```markdown\n" + block + "\n```\n")
        self.assertNotIn("metadata-invalid", self.codes(self.check()))
        path.write_text(path.read_text() + "\n" + block)
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_duplicate_page_id(self):
        self.change_meta(self.flow, id="module-approval")
        self.assertIn("page-id-duplicate", self.codes(self.check()))

    def test_duplicate_claim_id(self):
        self.change_meta(self.flow, claims=[{"id": "approval-01", "section": "正常路径与模块交接", "sources": [{"path": self.source}]}])
        self.assertIn("claim-id-duplicate", self.codes(self.check()))

    def test_missing_claim_section(self):
        self.change_meta(self.module, claims=[{"id": "approval-01", "section": "不存在", "sources": [{"path": self.source}]}])
        self.assertIn("claim-section-missing", self.codes(self.check()))

    def test_required_sections(self):
        path = self.root / self.module
        path.write_text(path.read_text().replace("## 排障与维护操作", "## other"))
        self.assertIn("section-missing", self.codes(self.check()))

    def test_page_kind_layout(self):
        self.change_meta(self.module, kind="system")
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_map_missing_module(self):
        self.change_meta(".smart-handbook/map.md", modules=[])
        self.assertIn("map-module-missing", self.codes(self.check()))

    def test_map_scope_mismatch(self):
        self.change_meta(self.module, source_ranges=[self.source])
        self.assertIn("map-range-mismatch", self.codes(self.check()))

    def test_flow_module_not_found(self):
        self.change_meta(self.flow, modules=["module-missing"])
        self.assertIn("module-reference-broken", self.codes(self.check()))

    def test_local_links_reference_links_and_anchors(self):
        path = self.root / self.module
        path.write_text(path.read_text() + "\n[系统](../system.md#系统职责与边界)\n[坏链接][bad]\n[bad]: ../missing.md\n")
        errors = [i for i in self.check()["issues"] if i["code"] == "link-broken"]
        self.assertEqual(len(errors), 1, errors)
        path.write_text(path.read_text() + "\n[未知](../system.md#missing)\n")
        self.assertEqual(sum(i["code"] == "link-broken" for i in self.check()["issues"]), 2)

    def test_link_examples_and_external_urls(self):
        path = self.root / self.module
        path.write_text(path.read_text() + "\n`[example](missing.md)`\n```md\n[x](missing.md)\n```\n[远端](https://example.invalid/x)\n")
        self.assertNotIn("link-broken", self.codes(self.check()))

    def test_path_traversal(self):
        self.change_meta(self.module, claims=[{"id": "approval-01", "section": "当前行为与关键约束", "sources": [{"path": "../outside.java"}]}])
        self.assertIn("source-broken", self.codes(self.check()))

    def test_symlink_outside_root(self):
        (self.root / self.source).unlink()
        (self.root / self.source).symlink_to("/etc/hosts")
        self.assertIn("source-broken", self.codes(self.check()))

    def test_java_symbol_location_and_unknown_languages(self):
        self.assertEqual(hb.locate_symbol(self.root / self.source, "ApprovalService#approve(String)"), "located")
        self.assertEqual(hb.locate_symbol(self.root / self.source, "MissingType"), "broken")
        self.assertEqual(hb.locate_symbol(self.root / self.source, "ApprovalService#missing(String)"), "broken")
        self.assertEqual(hb.locate_symbol(self.root / "config/application.yml", "anything"), "unknown")

    def test_malformed_url_reports_error_without_crashing(self):
        path = self.root / self.module
        path.write_text(path.read_text() + "\n[坏链接](https://[broken)\n")
        self.assertIn("link-broken", self.codes(self.check()))

    def test_unclosed_metadata_is_reported(self):
        path = self.root / self.module
        path.write_text(path.read_text().replace("-->", "", 1))
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_unsupported_symbol_is_unknown(self):
        self.change_meta(self.module, claims=[{"id": "approval-01", "section": "当前行为与关键约束", "sources": [{"path": self.source, "symbol": "ApprovalService#approve(List<String>)"}]}])
        result = self.check()
        self.assertIn("symbol-unverified", self.codes(result))
        self.assertEqual(result["pages"][self.module]["source_state"], "unknown")

    def test_deleted_page_retains_old_impact_association(self):
        (self.root / self.module).unlink()
        (self.root / self.source).unlink()
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["previous_pages"], [{"page": self.module, "files": [self.source]}])

    def test_java_overloads_use_parameter_type(self):
        path = self.root / self.source
        path.write_text("class ApprovalService {\n public void approve(int request) {}\n public void approve(String request) {}\n}\n")
        self.assertEqual(hb.locate_symbol(path, "ApprovalService#approve(String)"), "located")
        self.assertEqual(hb.locate_symbol(path, "ApprovalService#approve(int)"), "located")
        self.assertEqual(hb.locate_symbol(path, "ApprovalService#approve(long)"), "unknown")

    def test_review_timestamp_required(self):
        self.record["source_reviewed_at"] = None
        self.save_review()
        self.assertIn("review-invalid", self.codes(self.check()))

    def test_verified_requires_observation(self):
        self.state["pages"][self.module]["verification"] = {"status": "verified"}
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))

    def test_removed_reference_invalidates_review(self):
        self.change_meta(self.module, claims=[])
        page = self.check()["pages"][self.module]
        self.assertEqual(page["source_state"], "changed")
        self.assertEqual(page["review"], "needs_review")

    def test_fingerprint_impact_no_git(self):
        (self.root / self.source).write_text("class ApprovalService {}")
        with patch.object(hb, "git", side_effect=ValueError("Git unavailable")):
            result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["mode"], "fingerprint")
        self.assertEqual(result["changed_files"], [self.source])
        self.assertEqual(result["related_modules"], [{"id": "module-approval", "page": self.module}])
        self.assertEqual(result["related_flows"], [{"id": "flow-approval", "page": self.flow}])

    def test_no_git_no_baseline(self):
        (self.root / ".smart-handbook/.state.json").unlink()
        for item in self.inventory["files"]:
            item.update(fingerprint=None, reason="No historical fingerprint")
        self.save_inventory()
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["baseline_status"], "baseline-unavailable")
        self.assertEqual(result["changed_files"], [])

    def test_inventory_fingerprints_remain_available_without_page_state(self):
        (self.root / ".smart-handbook/.state.json").unlink()
        self.change_meta(self.module, config_ranges=[])
        (self.root / "config/application.yml").write_text("approval: false\n")
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["baseline_status"], "available")
        self.assertEqual(result["changed_files"], ["config/application.yml"])
        self.assertEqual(result["unowned_changes"], [])
        self.assertEqual(result["related_units"], [{"id": "business-approval", "pages": [self.module, self.flow]}])

    def test_old_state_locates_removed_claim(self):
        self.change_meta(self.module, claims=[], source_ranges=[])
        (self.root / self.source).unlink()
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["direct_claims"], [])
        self.assertEqual(result["previous_pages"], [{"page": self.module, "files": [self.source]}])
        self.assertTrue(result["related_modules"])

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_git_dirty_worktree_and_config_ownership(self):
        base = self.git_baseline()
        (self.root / self.source).write_text("class ApprovalService {}")
        (self.root / "config/application.yml").write_text("approval: false")
        (self.root / "unrelated.txt").write_text("new")
        result = hb.impact(hb.Handbook(self.root), base)
        self.assertEqual(result["mode"], "git")
        self.assertEqual(result["unowned_changes"], ["unrelated.txt"])
        self.assertIn("config/application.yml", result["changed_files"])
        self.assertTrue(result["related_flows"])

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_hidden_handbook_edits_do_not_count_as_source_changes(self):
        base = self.git_baseline()
        path = self.root / self.module
        path.write_text(path.read_text() + "\n知识更新\n")
        (self.root / ".smart-handbook/extra.md").write_text("new knowledge file")
        result = hb.impact(hb.Handbook(self.root), base)
        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["unowned_changes"], [])

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_git_staged_rename_includes_both_paths(self):
        base = self.git_baseline()
        self.run_git("mv", self.source, "src/Renamed.java")
        result = hb.impact(hb.Handbook(self.root), base)
        self.assertEqual(result["changed_files"], [self.source, "src/Renamed.java"])
        self.assertEqual(len(result["renames"]), 1)

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_target_ref_excludes_worktree_and_untracked_files(self):
        base = self.git_baseline()
        (self.root / self.source).write_text("changed only in worktree")
        (self.root / "untracked.txt").write_text("untracked")
        result = hb.impact(hb.Handbook(self.root), base, base)
        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["target"], base)

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_invalid_ref_is_error_not_silent_fallback(self):
        self.git_baseline()
        result = hb.impact(hb.Handbook(self.root), "missing-ref")
        self.assertIn("git-diff-unavailable", self.codes(result))
        self.assertEqual(result["mode"], "unavailable")

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_state_commit_used_as_default_git_base(self):
        base = self.git_baseline()
        self.state["baseline"] = {"commit": base}
        self.save_state()
        (self.root / self.source).unlink()
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["mode"], "git")
        self.assertEqual(result["changed_files"], [self.source])

    def test_cli_machine_output_and_error_exit(self):
        script = SKILL / "scripts/handbook.py"
        run = subprocess.run([sys_executable(), str(script), "check", "--root", str(self.root), "--format", "json"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["command"], "check")
        (self.root / self.source).unlink()
        run = subprocess.run([sys_executable(), str(script), "check", "--root", str(self.root), "--format", "json"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertIn("source-broken", self.codes(json.loads(run.stdout)))


def sys_executable():
    import sys
    return sys.executable


if __name__ == "__main__":
    unittest.main()
