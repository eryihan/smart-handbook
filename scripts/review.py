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
    return {"status": "pending", "answer": "", "evidence": [], "locations": []}


def pending(record):
    record["source_reviewed_at"] = None
    record["source_review"] = {"status": "pending", "isolation": "unavailable",
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
    questions = [{"id": c["id"], "question": c["question"]} for c in record["scenarios"] if c["id"] in chosen]
    (session / "reader/questions.json").write_text(encode(questions), encoding="utf-8")
    # The reviewer needs facts and locators, not duplicated grading history or the whole original record.
    task = {"root": str(root), "record_path": relative, "target": record["target"],
            "pages": sorted(record["pages"]), "sources": sorted(record["sources"]),
            "entrypoints": [{k: v for k, v in book.entries[e].items()
                             if k in ("id", "path", "symbol", "line", "trigger", "claims")}
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
              "source_task_fingerprint": hb.fingerprint(session / "source-task.json"),
              "entry_claims": {e: book.entries[e]["claims"] for e in scope}}
    (session / "packet.json").write_text(encode(packet), encoding="utf-8")
    source_template = {"status": "pending", "isolation": "unavailable", "description": "Awaiting actual source feedback",
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
    return book, packet


def seal(root, session, feedback):
    book, packet = load_current(root, session)
    if (session / "source.json").exists():
        raise ValueError("Source feedback already sealed; prepare a new revision")
    required = {"status", "isolation", "description", "findings", "retained"}
    if set(feedback) != required:
        raise ValueError("Source feedback requires status, isolation, description, findings, retained")
    proof = {k: feedback[k] for k in required - {"retained"}}
    proof["input_fingerprint"] = hb.review_input_fingerprint(packet["record"])
    checked(proof, book.review_schema["properties"]["source_review"] | {"$defs": book.review_schema["$defs"]})
    if proof["status"] == "passed" and (proof["isolation"] != "independent" or proof["findings"]):
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
    if set(raw) != {"reader", "scenarios"}:
        raise ValueError("Reader output requires reader and scenarios")
    checked(raw["reader"], book.review_schema["properties"]["reader"] | {"$defs": book.review_schema["$defs"]})
    if not isinstance(raw["scenarios"], list) or any(not isinstance(c, dict) or set(c) != {"id", "reading"}
                                                   for c in raw["scenarios"]):
        raise ValueError("Reader answers require id and original reading")
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
                case["assessment"] = ("Previous " + prior["verdict"] + " at " + str(prior["reviewed_at"])
                                      + ": " + prior["assessment"] + "\nRecheck: " + case["assessment"])
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
        if args.phase in ("draft", "plan"):
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
