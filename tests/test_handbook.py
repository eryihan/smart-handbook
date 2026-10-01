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
        self.state = {"schema_version": 1, "pages": {self.module: {
            "sources": {self.source: hb.fingerprint(self.root / self.source)},
            "review": {"status": "reviewed_by_ai", "reviewed_at": "2026-10-01T10:00:00Z"},
            "verification": {"status": "not-run", "conditions": "fixture only", "method": "none", "observed": "not executed"}}}}
        self.save_state()

    def change_meta(self, rel, **updates):
        path = self.root / rel
        text = path.read_text()
        match = hb.META_RE.search(text)
        meta = json.loads(match[1])
        meta.update(updates)
        path.write_text(text[:match.start()] + "<!-- handbook-meta\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n-->" + text[match.end():])

    def save_state(self):
        (self.root / ".smart-handbook/.state.json").write_text(json.dumps(self.state))

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
        self.state["schema_version"] = 2
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))
        self.state["schema_version"] = 1
        self.state["pages"][self.module]["sources"][self.source] = "sha256:abc"
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))

    def test_bad_metadata_json(self):
        path = self.root / self.module
        path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version":'))
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_duplicate_json_keys(self):
        path = self.root / self.module
        path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        self.assertIn("metadata-invalid", self.codes(self.check()))

    def test_unsupported_metadata_schema(self):
        self.change_meta(self.module, schema_version=2)
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
        del self.state["pages"][self.module]["review"]["reviewed_at"]
        self.save_state()
        self.assertIn("state-invalid", self.codes(self.check()))

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
        result = hb.impact(hb.Handbook(self.root))
        self.assertEqual(result["baseline_status"], "baseline-unavailable")
        self.assertEqual(result["changed_files"], [])

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
