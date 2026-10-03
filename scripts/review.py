#!/usr/bin/env python3
"""Prepare, seal and save actual review feedback; never generate answers or verdicts."""

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


def plan_check(book, relative, record):
    checked(record, book.review_schema)
    book.validate_review_relations(relative, record)
    scope = {e for c in record["scenarios"] for e in c["entrypoints"]} | set(record["not_applicable"])
    if not scope or not record["scenarios"]:
        raise ValueError("A review requires actual scenarios and entries")
    for entry_id in scope:
        entry = book.entries[entry_id]
        topics = {t for c in record["scenarios"] if entry_id in c["entrypoints"] for t in c["topics"]}
        topics.update(record["not_applicable"].get(entry_id, {}))
        if topics != hb.REVIEW_TOPICS or not entry["claims"]:
            raise ValueError("Plan requires all six topics and documented claims: " + entry_id)
        if any(book.pages[book.claims[c][0]]["metadata"]["coverage"] != "documented" for c in entry["claims"]):
            raise ValueError("Review plan requires documented scope: " + entry_id)
    for case in record["scenarios"]:
        if not case["expected"]["answer"].strip() or not case["expected"]["sources"]:
            raise ValueError("Source questions require answers and evidence: " + case["id"])
        for entry_id in case["entrypoints"]:
            own = {s["path"] for c in book.entries[entry_id]["claims"]
                   for s in book.claims[c][1]["sources"] if "implementation" in s["roles"]}
            if not own & {s["path"] for s in case["expected"]["sources"]}:
                raise ValueError("Question must cite its entry implementation: " + entry_id)
    return scope


def prepare(root, relative, session, selected=None, pages=None, retain_all=False):
    book = hb.Handbook(root)
    result = book.check()
    scope_record = read(record_path(root, relative))
    scope = {e for c in scope_record["scenarios"] for e in c["entrypoints"]} | set(scope_record["not_applicable"])
    # Old feedback may be invalidated by this revision; unrelated structural errors still block preparation.
    errors = [i for i in result["issues"] if i["level"] == "error"
              and not (i["code"] == "review-invalid" and i["path"] == relative)
              and not (i["code"] == "entry-review-incomplete" and i["message"].split(":", 1)[0] in scope)]
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
    record["sources"] = {p: book.file_digest(p) for p in sorted(sources)}
    # Bind only authoritative context; navigation progress changes must not invalidate every batch.
    relevant_pages = set(scope_record["pages"]) | set(pages or [])
    relevant_pages.update(book.claims[c][0] for e in scope for c in book.entries[e]["claims"])
    if not relevant_pages <= book.pages.keys():
        raise ValueError("Unknown authoritative page")
    record["pages"] = {p: book.file_digest(p) for p in sorted(relevant_pages)}
    frozen_pages = {p: book.file_digest(p) for p in sorted(book.pages)}
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
    packet = {"root": str(root), "record_path": relative, "record": record,
              "original": scope_record, "selected": sorted(chosen),
              "frozen_pages": frozen_pages,
              "draft_fingerprint": hb.fingerprint(record_path(root, relative)),
              "questions_fingerprint": hb.fingerprint(session / "reader/questions.json"),
              "entry_claims": {e: book.entries[e]["claims"] for e in scope}}
    (session / "packet.json").write_text(encode(packet), encoding="utf-8")
    return {"session": str(session), "source_packet": str(session / "packet.json"),
            "reader_directory": str(session / "reader"), "questions": len(questions),
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
    if set(feedback) != {"reader", "scenarios"}:
        raise ValueError("Reading feedback requires reader and scenarios")
    supplied = feedback["scenarios"]
    if not isinstance(supplied, list) or any(not isinstance(c, dict) or set(c) != {"id", "reading", "verdict", "assessment"} for c in supplied):
        raise ValueError("Each graded answer requires id, reading, verdict and assessment")
    answers = {c["id"]: c for c in supplied}
    if len(answers) != len(supplied) or set(answers) != set(packet["selected"]):
        raise ValueError("Reading feedback must cover exactly the selected questions")
    record = packet["record"]
    record.update({k: source[k] for k in ("source_review", "source_reviewed_at")})
    record["reader"] = copy.deepcopy(feedback["reader"])
    if source["retained"] and packet["original"]["reader"] != feedback["reader"]:
        record["reader"]["description"] += "; retained answers: " + packet["original"]["reader"]["description"]
    original = {c["id"]: c for c in packet["original"]["scenarios"]}
    timestamp = now()
    for case in record["scenarios"]:
        prior = original[case["id"]]
        if case["id"] in answers:
            answer = answers[case["id"]]
            case.update({k: answer[k] for k in ("reading", "verdict", "assessment")})
            if case["verdict"] not in ("passed", "failed"):
                raise ValueError("Finish requires actual grading")
            if prior["verdict"] != "pending":
                case["assessment"] = ("Previous " + prior["verdict"] + " at " + str(prior["reviewed_at"])
                                      + ": " + prior["assessment"] + "\nRecheck: " + case["assessment"])
        else:
            case.update({k: prior[k] for k in ("reading", "verdict")})
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
    parser.add_argument("phase", choices=("prepare", "seal", "finish"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--record")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--page", action="append")
    parser.add_argument("--retain-all", action="store_true")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        root, session = args.root.resolve(), args.session.resolve()
        if args.phase == "prepare":
            if not args.record or args.result:
                parser.error("prepare requires --record and accepts --scenario")
            result = prepare(root, args.record, session, args.scenario, args.page, args.retain_all)
        else:
            if not args.result or args.record or args.scenario or args.page or args.retain_all:
                parser.error("seal/finish require --result")
            result = (seal if args.phase == "seal" else finish)(root, session, read(args.result))
        print(encode(result), end="")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(encode({"error": str(exc)}), end="", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
