#!/usr/bin/env python3
"""Draft, check, freeze and save actual review evidence; never generate facts or verdicts."""

import argparse
import copy
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import handbook as hb


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return hb.parse_json(Path(path).read_text(encoding="utf-8"))


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def checked(value, schema):
    errors = hb.validate(value, schema, schema)
    if errors:
        raise ValueError("; ".join(errors))


class PlanError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(i["message"] for i in issues))


def plan_report(book, relative, record):
    """Report all schema and entry/topic problems before relation checks or writes."""
    issues, matrix = [], {}

    def issue(code, path, message):
        issues.append({"code": code, "path": path, "message": message})

    for error in hb.validate(record, book.review_schema, book.review_schema):
        issue("plan-schema", relative, error)
    if issues:
        return {"valid": False, "entries": matrix, "issues": issues}
    scope = {e for c in record["scenarios"] for e in c["entrypoints"]} | set(record["not_applicable"])
    if not scope or not record["scenarios"]:
        issue("plan-empty", relative, "A review requires actual scenarios and entries")
    seen = set()
    for case in record["scenarios"]:
        path = relative + "/scenarios/" + case["id"]
        if case["id"] in seen:
            issue("plan-duplicate", path, "Duplicate scenario ID: " + case["id"])
        seen.add(case["id"])
        if not case["expected"]["answer"].strip() or not case["expected"]["sources"]:
            issue("plan-answer", path, "Source questions require answers and evidence: " + case["id"])
        expected = {s["path"] for s in case["expected"]["sources"]}
        for entry_id in case["entrypoints"]:
            if entry_id not in book.entries:
                continue
            own = {s["path"] for c in book.entries[entry_id]["claims"] if c in book.claims
                   for s in book.claims[c][1]["sources"] if "implementation" in s["roles"]}
            if not own & expected:
                issue("plan-evidence", path, "Question must cite its entry implementation: " + entry_id)
    for entry_id in sorted(scope):
        path = relative + "/entries/" + entry_id
        if entry_id not in book.entries:
            issue("plan-entry", path, "Unknown entry: " + entry_id)
            continue
        entry = book.entries[entry_id]
        if entry.get("kind") != "action":
            issue("plan-action", path, "Confirm or expand the concrete action before review: " + entry_id)
        tested = {t for c in record["scenarios"] if entry_id in c["entrypoints"] for t in c["topics"]}
        excluded = set(record["not_applicable"].get(entry_id, {}))
        missing, conflict = hb.REVIEW_TOPICS - (tested | excluded), tested & excluded
        matrix[entry_id] = {"tested": sorted(tested), "not_applicable": sorted(excluded),
                            "missing": sorted(missing), "conflicts": sorted(conflict)}
        if relative not in entry["reviews"]:
            issue("plan-link", path, "Review scope is not linked to entry: " + entry_id)
        if missing or not entry["claims"]:
            issue("plan-coverage", path, "Plan requires all six topics and documented claims: " + entry_id
                  + "; missing=" + ",".join(sorted(missing)))
        if excluded - hb.REVIEW_TOPICS or "normal" in excluded:
            issue("plan-topic", path, "Unknown or inapplicable normal review topic: " + entry_id)
        if conflict:
            issue("plan-conflict", path, "Topic cannot be both tested and not applicable: " + entry_id
                  + "; conflicts=" + ",".join(sorted(conflict)))
        for claim in entry["claims"]:
            if claim not in book.claims or book.pages[book.claims[claim][0]]["metadata"]["coverage"] != "documented":
                issue("plan-claim", path, "Review plan requires documented scope: " + entry_id)
    if not issues:
        try:
            book.validate_review_relations(relative, record)
        except (ValueError, OSError) as exc:
            issue("plan-relation", relative, str(exc))
    return {"valid": not issues, "entries": matrix, "issues": issues}


def record_path(root, relative):
    path = hb.safe_path(root, relative)
    if not relative.startswith(hb.REVIEW_DIR) or not relative.endswith(".json"):
        raise ValueError("Record must be a .smart-handbook/.reviews/ JSON path")
    if not path.is_relative_to(root / hb.HANDBOOK_DIR):
        raise ValueError("Record symlink escapes handbook output directory")
    return path


def empty_reading():
    return {"status": "pending", "answer": "", "unanswered": [], "evidence": [], "locations": []}


def pending(record):
    record["source_reviewed_at"] = None
    record["source_review"] = {"status": "pending", "isolation": "unavailable",
                               "context": "unavailable",
                               "description": "Awaiting independent source review",
                               "input_fingerprint": None, "findings": []}
    record["reader"] = {"isolation": "unavailable", "description": "Awaiting independent reading"}
    for case in record["scenarios"]:
        case.update(reading=empty_reading(), verdict="pending", assessment="", reviewed_at=None)
        case.pop("reading_fingerprint", None)


def plan_check(book, relative, record):
    report = plan_report(book, relative, record)
    if report["issues"]:
        raise PlanError(report["issues"])
    scope = {e for c in record["scenarios"] for e in c["entrypoints"]} | set(record["not_applicable"])
    return scope


def plan(root, relative):
    book = hb.Handbook(root)
    record = read(record_path(root, relative))
    # Report malformed input without indexing its fields or rewriting old evidence.
    if hb.validate(record, book.review_schema, book.review_schema):
        return plan_report(book, relative, record)
    pending(record)
    record.update(prepared_at=None, sources={}, pages={})
    report = plan_report(book, relative, record)
    report["record"] = relative
    return report


def draft(root, relative, value):
    """Create a new batch record and link explicit Agent-supplied claims; never overwrite history."""
    inventory_path = hb.safe_path(root, hb.INVENTORY_PATH)
    if not inventory_path.is_relative_to(root / hb.HANDBOOK_DIR):
        raise ValueError("Inventory symlink escapes handbook output directory")
    original_digest = hb.fingerprint(inventory_path)
    book = hb.Handbook(root)
    if book.inventory is None:
        raise ValueError("A valid inventory is required before drafting")
    path = record_path(root, relative)
    if path.exists():
        raise ValueError("Draft requires a new record path; keep existing review history")
    fields = ("id", "entrypoints", "topics", "question", "expected")
    scenario = book.review_schema["$defs"]["scenario"]
    schema = {"type": "object", "additionalProperties": False,
              "required": ["id", "target", "entries", "scenarios", "not_applicable"],
              "$defs": book.review_schema["$defs"], "properties": {
                  **{k: book.review_schema["properties"][k] for k in ("id", "target", "not_applicable")},
                  "entries": {"type": "object", "additionalProperties": {
                      "type": "array", "minItems": 1, "items": {"$ref": "#/$defs/id"}}},
                  "scenarios": {"type": "array", "minItems": 1, "items": {
                      "type": "object", "additionalProperties": False, "required": list(fields),
                      "properties": {k: scenario["properties"][k] for k in fields}}}}}
    checked(value, schema)
    if any(r["id"] == value["id"] for r in book.reviews.values()):
        raise ValueError("Draft requires a unique review ID")
    scope = {e for c in value["scenarios"] for e in c["entrypoints"]} | set(value["not_applicable"])
    if scope != set(value["entries"]) or not scope <= book.entries.keys():
        raise ValueError("Draft entries must match the actual scenario and exclusion scope")
    if any(c not in book.claims for claims in value["entries"].values() for c in claims):
        raise ValueError("Draft claims must already exist in handbook pages")
    inventory = copy.deepcopy(book.inventory)
    if inventory["status"] == "complete":
        inventory["status"] = "incomplete"
    for unit in inventory["units"]:
        for entry in unit["entrypoints"]:
            if entry["id"] in scope:
                entry["claims"] = sorted(set(entry["claims"]) | set(value["entries"][entry["id"]]))
                entry["reviews"] = sorted(set(entry["reviews"]) | {relative})
                entry["status"] = "needs-review"
    checked(inventory, book.inventory_schema)
    book.validate_inventory_relations(inventory)
    book.inventory = inventory
    book.entries = {e["id"]: e for u in inventory["units"] for e in u["entrypoints"]}
    record = read(hb.ASSETS / "review-template.json")
    record.update({k: copy.deepcopy(value[k]) for k in ("id", "target", "scenarios", "not_applicable")})
    pending(record)
    plan_check(book, relative, record)
    if path.exists() or hb.fingerprint(inventory_path) != original_digest:
        raise ValueError("Draft target changed; reload before saving")
    replace_files({path: record, inventory_path: inventory})
    return {"record": relative, "saved": True, "entries": sorted(scope),
            "next": "prepare; draft is pending and does not certify any business"}


def prepare(root, relative, session=None, selected=None, pages=None, retain_all=False):
    book = hb.Handbook(root)
    scope_record = read(record_path(root, relative))
    report = plan_report(book, relative, scope_record)
    if any(i["code"] == "plan-schema" for i in report["issues"]):
        raise PlanError(report["issues"])
    scope = {e for c in scope_record["scenarios"] for e in c["entrypoints"]} | set(scope_record["not_applicable"])
    probe = copy.deepcopy(scope_record)
    pending(probe)
    probe.update(prepared_at=None, sources={}, pages={})
    plan_check(book, relative, probe)
    relevant_pages = set(scope_record["pages"]) | set(pages or [])
    relevant_pages.update(book.claims[c][0] for e in scope for c in book.entries[e]["claims"])
    if not relevant_pages <= book.pages.keys():
        raise ValueError("Unknown authoritative page")
    related_entries = scope | {e for e, entry in book.entries.items()
                               if any(book.claims[c][0] in relevant_pages for c in entry["claims"])}
    related_reviews = {r for e in related_entries for r in book.entries[e]["reviews"]}
    result = book.check()
    # Global identity/path/state failures remain blocking; unrelated work stays visible for final check.
    global_codes = {"unsafe-path", "handbook-missing", "page-missing", "state-invalid",
                    "inventory-missing", "inventory-invalid", "page-id-duplicate", "claim-id-duplicate"}
    errors, deferred = [], []
    for issue in result["issues"]:
        if issue["level"] != "error":
            continue
        code, path = issue["code"], issue["path"]
        entry_id = issue["message"].split(":", 1)[0]
        if ((code == "review-invalid" and path == relative)
                or (code == "entry-review-incomplete" and entry_id in scope)):
            continue  # This revision is repairing its previous feedback.
        blocking = (code in global_codes or path in relevant_pages
                    or (code == "review-invalid" and path in related_reviews)
                    or (code == "entry-review-incomplete" and entry_id in related_entries))
        (errors if blocking else deferred).append(issue)
    if errors or book.inventory is None:
        raise ValueError("Fix handbook structure before review: " + encode(errors))
    record = copy.deepcopy(scope_record)
    pending(record)
    record["prepared_at"] = now()
    sources = {s["path"] for c in record["scenarios"] for s in c["expected"]["sources"]}
    sources.update(s["path"] for exclusions in record["not_applicable"].values()
                   for exclusion in exclusions.values() for s in exclusion["sources"])
    for entry_id in scope:
        entry = book.entries[entry_id]
        sources.add(entry["path"])
        sources.update(s["path"] for c in entry["claims"] for s in book.claims[c][1]["sources"])
    sources.update(s["path"] for p in relevant_pages for c in book.pages[p]["metadata"]["claims"]
                   for s in c["sources"])
    record["sources"] = {p: book.file_digest(p) for p in sorted(sources)}
    record["pages"] = {p: book.file_digest(p) for p in sorted(relevant_pages)}
    frozen_pages = dict(record["pages"])
    plan_check(book, relative, record)
    ids = {c["id"] for c in record["scenarios"]}
    if retain_all and selected:
        raise ValueError("retain-all cannot select new reading questions")
    chosen = set() if retain_all else (set(selected) if selected else ids)
    if (not chosen and not retain_all) or not chosen <= ids:
        raise ValueError("Unknown or empty scenario selection")
    original = {c["id"]: c for c in scope_record["scenarios"]}
    omitted = ids - chosen
    if any(original[i]["verdict"] != "passed" for i in omitted):
        raise ValueError("All failed or pending questions must be selected for reading")
    for case_id in omitted:
        case = original[case_id]
        tagged = [s for s in case["reading"]["locations"] if "entrypoints" in s]
        if (case["reading"].get("unanswered")
                or ("reading_fingerprint" in case and case["reading_fingerprint"] != hb.reading_fingerprint(case["reading"]))
                or (tagged and {e for s in tagged for e in s["entrypoints"]} != set(case["entrypoints"]))):
            raise ValueError("Unselected answer has conflicting reading evidence; select it for reading: " + case_id)
    if omitted and (scope_record["reader"]["isolation"] != "independent"
                    or any(original[i]["reading"]["status"] != "answered"
                           or not original[i]["reading"]["answer"].strip()
                           or not original[i]["reading"]["evidence"]
                           or not original[i]["reading"]["locations"]
                           or not original[i]["reviewed_at"] for i in omitted)):
        raise ValueError("Unselected questions require actual independent reading evidence")
    if session is None:
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if temporary_root == root or root in temporary_root.parents:
            raise ValueError("Temporary session directory must be outside the target repository")
        session = Path(tempfile.mkdtemp(prefix="handbook-review-", dir=temporary_root)).resolve()
    else:
        session = session.resolve()
        if session == root or root in session.parents:
            raise ValueError("Session must be outside the target repository")
        if session.exists():
            raise ValueError("Use a new session directory for every revision")
        session.mkdir(parents=True)
    for page in frozen_pages:
        dest = session / "reader" / page
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(hb.safe_path(root, page).read_bytes())
        if hb.fingerprint(dest) != frozen_pages[page]:
            raise ValueError("Page changed during snapshot: " + page)
    questions = [{"id": c["id"], "question": c["question"], "entrypoints": c["entrypoints"]}
                 for c in record["scenarios"] if c["id"] in chosen]
    (session / "reader/questions.json").write_text(encode(questions), encoding="utf-8")
    guide = ("# 独立阅读任务\n\n只读本目录的手册快照与问题，不读源码、预期答案或生成历史。"
             "直接填写 answers.json，保留模板字段；不能自己访问源项目补答案。\n\n"
             "逐题回答问题关联的每个业务动作。answer 写实际理解；问题中不能回答的条件、数据、"
             "生效、失败或代码定位写入 unanswered，不因忠实反映手册缺失而视作通过。"
             "部署值、远端内部实现等不影响题目作答的未知可在 answer 中说明，不混入 unanswered。\n\n"
             "evidence 只含 page 和 section，section 使用以下真实 H2，不用 H3，不添加 note。"
             "locations 使用 path 加 symbol（Java 为类型#方法）或行号；合并题的每个定位加 entrypoints，"
             "逐一对应问题中的动作 ID，共用实现可关联多个动作，但代表方法不能证明其他动作。"
             "说明缺失时如实记录，不猜测或补造定位。格式反馈只按原快照自行修正。\n\n")
    guide += "\n".join("- " + p + ": " + "；".join(book.pages[p]["sections"]) for p in sorted(frozen_pages)) + "\n"
    (session / "reader/guide.md").write_text(guide, encoding="utf-8")
    # The reviewer needs facts and locators, not duplicated grading history or the whole original record.
    task = {"root": str(root), "record_path": relative, "target": record["target"],
            "instructions": ("使用未继承生成历史的新上下文，先独立复述实际实现，再比对本任务。"
                             "independent 是相对生成者隔离，不是仅与读者不同；生成者自查使用 context=authoring，"
                             "不得 passed。逐动作检查资源、条件、结果和定位；保留题逐题核对具体 diff 与历史回答，"
                             "已知错误、无法回答或定位被补写的题不能保留。"),
            "pages": sorted(record["pages"]), "sources": sorted(record["sources"]),
            "entrypoints": [{k: v for k, v in book.entries[e].items()
                             if k in ("id", "kind", "path", "symbol", "line", "trigger", "claims")}
                            for e in sorted(scope)],
            "selected": [], "retained": [], "not_applicable": record["not_applicable"]}
    for case in record["scenarios"]:
        item = {k: case[k] for k in ("id", "entrypoints", "topics", "question", "expected")}
        if case["id"] in chosen:
            task["selected"].append(item)
        else:
            item["previous_reading"] = original[case["id"]]["reading"]
            task["retained"].append(item)
    (session / "source-task.json").write_text(encode(task), encoding="utf-8")
    packet = {"root": str(root), "record_path": relative, "record": record,
              "original": scope_record, "selected": sorted(chosen),
              "frozen_pages": frozen_pages,
              "draft_fingerprint": hb.fingerprint(record_path(root, relative)),
              "questions_fingerprint": hb.fingerprint(session / "reader/questions.json"),
              "reader_guide_fingerprint": hb.fingerprint(session / "reader/guide.md"),
              "source_task_fingerprint": hb.fingerprint(session / "source-task.json"),
              "entry_actions": {entry["id"]: entry for entry in task["entrypoints"]},
              "entry_claims": {e: book.entries[e]["claims"] for e in scope}}
    (session / "packet.json").write_text(encode(packet), encoding="utf-8")
    source_template = {"status": "pending", "isolation": "unavailable", "context": "unavailable",
                       "description": "Actual reviewer and isolation from the author; not merely from the reader",
                       "findings": [], "retained": {i: "" for i in sorted(omitted)}}
    reader_template = {"reader": {"isolation": "unavailable", "description": "Awaiting actual independent reader"},
                       "scenarios": [{"id": i, "reading": empty_reading()} for i in sorted(chosen)]}
    (session / "reader/answers.json").write_text(encode(reader_template), encoding="utf-8")
    graded_template = {"scenarios": [{"id": i, "verdict": "pending", "assessment": ""}
                                     for i in sorted(chosen)]}
    for name, value in (("source-feedback.json", source_template), ("graded-feedback.json", graded_template)):
        (session / name).write_text(encode(value), encoding="utf-8")
    return {"session": str(session), "source_packet": str(session / "packet.json"),
            "source_task": str(session / "source-task.json"),
            "reader_directory": str(session / "reader"), "questions": len(questions),
            "reader_guide": str(session / "reader/guide.md"),
            "reader_feedback": str(session / "reader/answers.json"),
            "source_feedback": str(session / "source-feedback.json"),
            "graded_feedback": str(session / "graded-feedback.json"),
            "deferred_issues": deferred,
            "next": "Independent source review; do not start the reader before seal passes"}


def load_current(root, session):
    if session == root or root in session.parents:
        raise ValueError("Session must be outside the target repository")
    packet = read(session / "packet.json")
    if packet["root"] != str(root):
        raise ValueError("Session belongs to another repository")
    record = packet["record"]
    book = hb.Handbook(root)
    if hb.fingerprint(record_path(root, packet["record_path"])) != packet["draft_fingerprint"]:
        raise ValueError("Draft record changed; prepare again")
    for group in ("sources", "pages"):
        for path, digest in record[group].items():
            if book.file_digest(path) != digest:
                raise ValueError("Review version changed; prepare again: " + path)
    for path, digest in packet["frozen_pages"].items():
        if hb.fingerprint(session / "reader" / path) != digest:
            raise ValueError("Reader snapshot changed; prepare again: " + path)
    if hb.fingerprint(session / "reader/questions.json") != packet["questions_fingerprint"]:
        raise ValueError("Reader questions changed; prepare again")
    if packet.get("reader_guide_fingerprint") and hb.fingerprint(session / "reader/guide.md") != packet["reader_guide_fingerprint"]:
        raise ValueError("Reader guide changed; prepare again")
    if packet.get("source_task_fingerprint") and hb.fingerprint(session / "source-task.json") != packet["source_task_fingerprint"]:
        raise ValueError("Source task changed; prepare again")
    current = read(record_path(root, packet["record_path"]))
    # Feedback and draft may have different hashes, but questions/scope must not change in flight.
    current["sources"], current["pages"] = record["sources"], record["pages"]
    if hb.review_input_fingerprint(current) != hb.review_input_fingerprint(record):
        raise ValueError("Questions or expected answers changed; prepare again")
    for entry_id, claims in packet["entry_claims"].items():
        if entry_id not in book.entries or book.entries[entry_id]["claims"] != claims:
            raise ValueError("Entry evidence changed; prepare again: " + entry_id)
    for entry_id, action in packet.get("entry_actions", {}).items():
        current = {k: v for k, v in book.entries[entry_id].items()
                   if k in ("id", "kind", "path", "symbol", "line", "trigger", "claims")}
        if current != action:
            raise ValueError("Entry action changed; prepare again: " + entry_id)
    return book, packet


def seal(root, session, feedback):
    book, packet = load_current(root, session)
    if (session / "source.json").exists():
        raise ValueError("Source feedback already sealed; prepare a new revision")
    required = {"status", "isolation", "context", "description", "findings", "retained"}
    if set(feedback) != required:
        raise ValueError("Source feedback requires status, isolation, context, description, findings, retained")
    proof = {k: feedback[k] for k in required - {"retained"}}
    proof["input_fingerprint"] = hb.review_input_fingerprint(packet["record"])
    checked(proof, book.review_schema["properties"]["source_review"] | {"$defs": book.review_schema["$defs"]})
    if proof["status"] == "passed" and (proof["isolation"] != "independent" or proof["context"] != "fresh" or proof["findings"]):
        raise ValueError("Unresolved or unavailable source review cannot pass")
    if proof["status"] == "pending":
        raise ValueError("Seal actual completed feedback, not pending work")
    omitted = {c["id"] for c in packet["record"]["scenarios"]} - set(packet["selected"])
    retained = feedback["retained"]
    if (not isinstance(retained, dict) or set(retained) != omitted
            or any(not isinstance(v, str) or not v.strip() for v in retained.values())):
        raise ValueError("Each unselected answer needs an explicit source/diff assessment")
    result = {"source_review": proof, "source_reviewed_at": now(), "retained": retained}
    (session / "source.json").write_text(encode(result), encoding="utf-8")
    return {"status": proof["status"], "reader_allowed": proof["status"] == "passed",
            "reader_required": bool(packet["selected"])}


def reading_report(book, packet, raw, passing):
    """Collect feedback problems once; never repair or grade the reader's answers."""
    issues = []

    def issue(code, path, message):
        issues.append({"code": code, "path": path, "message": message})

    reading_schema = copy.deepcopy(book.review_schema["$defs"]["scenario"]["properties"]["reading"])
    reading_schema["required"].append("unanswered")
    schema = {"type": "object", "additionalProperties": False, "required": ["reader", "scenarios"],
              "$defs": book.review_schema["$defs"], "properties": {
                  "reader": book.review_schema["properties"]["reader"],
                  "scenarios": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                      "required": ["id", "reading"], "properties": {
                          "id": {"$ref": "#/$defs/id"}, "reading": reading_schema}}}}}
    for error in hb.validate(raw, schema, schema):
        issue("reading-format", "reader/answers.json", error)
    if not isinstance(raw, dict) or not isinstance(raw.get("scenarios"), list):
        return {"valid": False, "issues": issues}
    cases = {c["id"]: c for c in packet["record"]["scenarios"]}
    selected, seen = set(packet["selected"]), []
    for value in raw["scenarios"]:
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            continue
        case_id = value["id"]
        seen.append(case_id)
        reading = value.get("reading")
        if case_id not in selected or not isinstance(reading, dict):
            continue
        path = "reader/answers.json/scenarios/" + case_id
        passed = case_id in passing
        if passed:
            reader = raw.get("reader", {})
            if (not isinstance(reader, dict) or reader.get("isolation") != "independent"
                    or reading.get("status") != "answered" or not isinstance(reading.get("answer"), str)
                    or not reading.get("answer", "").strip()):
                issue("reading-unavailable", path, "Passed scenario requires an actual independent answer")
            if reading.get("unanswered"):
                issue("reading-unanswered", path, "Business questions remain unanswered; save failed and repair")
            for field in ("evidence", "locations"):
                if not reading.get(field):
                    issue("reading-missing", path, "Passed scenario requires evidence and code location: " + field)
        covered = set()
        for locator in reading.get("locations", []) if isinstance(reading.get("locations"), list) else []:
            if not isinstance(locator, dict) or not isinstance(locator.get("path"), str):
                continue
            try:
                hb.safe_path(book.root, locator["path"])
            except ValueError as exc:
                issue("reading-path", path, str(exc))
            if not passed:
                continue  # Preserve failed answers, including their wrong or missing locations.
            if locator["path"] not in packet["record"]["sources"]:
                issue("reading-location", path, "Reading location is outside fingerprinted sources: " + locator["path"])
            if not locator.get("symbol") and not locator.get("line"):
                issue("reading-location", path, "Reading location requires symbol or line")
            symbol = locator.get("symbol", "")
            if (locator["path"].endswith(".java") and isinstance(symbol, str)
                    and "#" not in symbol and "line" not in locator):
                issue("reading-location", path, "Reading location must identify a handler, not just a Java class")
            tags = locator.get("entrypoints", [])
            if isinstance(tags, list) and all(isinstance(e, str) for e in tags):
                covered.update(tags)
        if passed and (len(cases[case_id]["entrypoints"]) > 1 or covered):
            if covered != set(cases[case_id]["entrypoints"]):
                issue("reading-actions", path, "Reading locations must cover exactly the scoped actions with entrypoints tags")
        for evidence in reading.get("evidence", []) if isinstance(reading.get("evidence"), list) else []:
            if not isinstance(evidence, dict) or not isinstance(evidence.get("page"), str):
                continue
            page = evidence["page"]
            try:
                hb.safe_path(book.root, page)
            except ValueError as exc:
                issue("reading-path", path, str(exc))
            if passed and (page not in packet["record"]["pages"]
                           or evidence.get("section") not in book.pages.get(page, {}).get("sections", [])):
                issue("reading-evidence", path, "Reading evidence requires a fingerprinted page and real H2: " + page)
    if set(seen) != selected or len(seen) != len(set(seen)):
        issue("reading-scope", "reader/answers.json", "Reader output must cover exactly the selected questions without duplicates")
    return {"valid": not issues, "issues": issues}


def reading_plan(root, session):
    book, packet = load_current(root, session)
    report = reading_report(book, packet, read(session / "reader/answers.json"), set(packet["selected"]))
    report.update(session=str(session), read_only=True,
                  limits=["Format, scope and explicit unanswered items only; this does not grade business semantics."])
    return report


def replace_files(updates):
    """Stage valid JSON, replace each file, roll back completed replacements on I/O failure."""
    backups, staged, done = {}, {}, []
    try:
        for path, value in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            backups[path] = path.read_bytes() if path.exists() else None
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
                staged[path] = Path(out.name)
                out.write(encode(value).encode("utf-8"))
        for path, temporary in staged.items():
            os.replace(temporary, path)
            done.append(path)
    except OSError:
        for path in reversed(done):
            if backups[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(backups[path])
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def finish(root, session, feedback):
    if (session / "finished.json").exists():
        raise ValueError("Session already saved; prepare a new revision")
    book, packet = load_current(root, session)
    source = read(session / "source.json")
    if source["source_review"]["status"] != "passed":
        raise ValueError("Source review did not pass; repair before independent reading")
    if set(feedback) != {"scenarios"}:
        raise ValueError("Grading requires only scenarios; reader answers must stay in reader/answers.json")
    supplied = feedback["scenarios"]
    if not isinstance(supplied, list) or any(not isinstance(c, dict) or set(c) != {"id", "verdict", "assessment"} for c in supplied):
        raise ValueError("Each grade requires id, verdict and assessment; grading cannot replace reading")
    answers = {c["id"]: c for c in supplied}
    if len(answers) != len(supplied) or set(answers) != set(packet["selected"]):
        raise ValueError("Reading feedback must cover exactly the selected questions")
    raw = read(session / "reader/answers.json")
    report = reading_report(book, packet, raw, {i for i, a in answers.items() if a["verdict"] == "passed"})
    if report["issues"]:
        raise PlanError(report["issues"])
    readings = {c["id"]: c["reading"] for c in raw["scenarios"]}
    if len(readings) != len(raw["scenarios"]) or set(readings) != set(packet["selected"]):
        raise ValueError("Reader output must cover exactly the selected questions")
    record = packet["record"]
    record.update({k: source[k] for k in ("source_review", "source_reviewed_at")})
    record["reader"] = copy.deepcopy(raw["reader"] if packet["selected"] else packet["original"]["reader"])
    if source["retained"] and packet["original"]["reader"] != record["reader"]:
        record["reader"]["description"] += "; retained answers: " + packet["original"]["reader"]["description"]
    original = {c["id"]: c for c in packet["original"]["scenarios"]}
    timestamp = now()
    for case in record["scenarios"]:
        prior = original[case["id"]]
        if case["id"] in answers:
            answer = answers[case["id"]]
            case.update({k: answer[k] for k in ("verdict", "assessment")})
            case["reading"] = copy.deepcopy(readings[case["id"]])
            case["reading_fingerprint"] = hb.reading_fingerprint(case["reading"])
            if case["verdict"] not in ("passed", "failed"):
                raise ValueError("Finish requires actual grading")
            if prior["verdict"] != "pending":
                previous = {k: copy.deepcopy(prior[k]) for k in
                            ("reading", "verdict", "assessment", "reviewed_at")}
                if "reading_fingerprint" in prior:
                    previous["reading_fingerprint"] = prior["reading_fingerprint"]
                case.setdefault("history", []).append(previous)
        else:
            case.update({k: prior[k] for k in ("reading", "verdict")})
            if "reading_fingerprint" in prior:
                case["reading_fingerprint"] = prior["reading_fingerprint"]
            case["assessment"] = (prior["assessment"] + "\nRetained reading at " + str(prior["reviewed_at"])
                                  + "; confirmed at " + timestamp + ": " + source["retained"][case["id"]])
        case["reviewed_at"] = timestamp
    checked(record, book.review_schema)
    book.validate_review_relations(packet["record_path"], record)
    state = copy.deepcopy(book.state)
    # Only the source-reviewed claims of this batch advance. Preserve baseline and runtime observations.
    reviewed_pages = {book.claims[c][0] for claims in packet["entry_claims"].values() for c in claims}
    for page in reviewed_pages:
        sources = book.current_sources(book.pages[page])
        if sources <= record["sources"].keys():
            item = state["pages"].setdefault(page, {})
            item.update(sources={p: record["sources"][p] for p in sorted(sources)},
                        source_state="unchanged", source_checked_at=source["source_reviewed_at"])
    checked(state, book.state_schema)
    state_path = hb.safe_path(root, hb.STATE_PATH)
    if not state_path.is_relative_to(root / hb.HANDBOOK_DIR):
        raise ValueError("State symlink escapes handbook output directory")
    replace_files({record_path(root, packet["record_path"]): record,
                   state_path: state})
    result = {"record": packet["record_path"], "saved": True,
              "passed": sum(c["verdict"] == "passed" for c in record["scenarios"]),
              "failed": sum(c["verdict"] == "failed" for c in record["scenarios"]),
              "next": "Agent reconciles entry status, runs check and continues the next init batch"}
    (session / "finished.json").write_text(encode(result), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("draft", "plan", "prepare", "seal", "finish"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--session", type=Path)
    parser.add_argument("--record")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--page", action="append")
    parser.add_argument("--retain-all", action="store_true")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        session = args.session.resolve() if args.session else None
        if args.phase == "plan" and args.session:
            if args.record or args.scenario or args.page or args.retain_all or args.result or args.input:
                parser.error("reading plan requires only --session")
            result = reading_plan(root, session)
        elif args.phase in ("draft", "plan"):
            if (not args.record or args.session or args.scenario or args.page or args.retain_all or args.result
                    or (args.phase == "draft") != bool(args.input)):
                parser.error("draft requires --record and --input; plan requires only --record")
            result = draft(root, args.record, read(args.input)) if args.phase == "draft" else plan(root, args.record)
        elif args.phase == "prepare":
            if not args.record or args.result or args.input:
                parser.error("prepare requires --record; --session is optional")
            result = prepare(root, args.record, session, args.scenario, args.page, args.retain_all)
        else:
            if not args.session or not args.result or args.record or args.scenario or args.page or args.retain_all or args.input:
                parser.error("seal/finish require --session and --result")
            result = (seal if args.phase == "seal" else finish)(root, session, read(args.result))
        print(encode(result), end="")
        return 1 if result.get("valid") is False else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {"error": str(exc)}
        if isinstance(exc, PlanError):
            result["issues"] = exc.issues
        print(encode(result), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
