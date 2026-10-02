#!/usr/bin/env python3
"""Read-only, standard-library checks and candidate impact for Handbook V1."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


ASSETS = Path(__file__).resolve().parent.parent / "assets"
HANDBOOK_DIR = ".smart-handbook"
STATE_PATH = HANDBOOK_DIR + "/.state.json"
INVENTORY_PATH = HANDBOOK_DIR + "/.inventory.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
META_RE = re.compile(r"<!--\s*handbook-meta\b([\s\S]*?)-->")
ROOT_KINDS = {"README.md": "readme", "system.md": "system", "map.md": "map",
              "working-guide.md": "working-guide"}
SECTIONS = {
    "module": ["职责与边界", "关键概念、数据与状态", "入口与核心实现路径",
               "当前行为与关键约束", "修改位置与影响范围", "验证方法与覆盖边界",
               "排障与维护操作", "证据与已知缺口"],
    "flow": ["触发条件与适用范围", "关键编号与状态变化", "正常路径与模块交接",
             "事务、异步与外部副作用", "失败分支、重试与补偿",
             "修改影响与验证判据", "排障路径与证据缺口"],
}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key: " + key)
        value[key] = item
    return value


def parse_json(text):
    def invalid_constant(value):
        raise ValueError("non-JSON constant: " + value)
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def validate(value, schema, document, location="$", errors=None):
    """Validate the subset of JSON Schema used by the bundled schemas."""
    if errors is None:
        errors = []
    if "$ref" in schema:
        target = document
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return validate(value, target, document, location, errors)
    expected = schema.get("type")
    types = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": type(value) is int}
    if expected and not types.get(expected, False):
        errors.append(location + ": expected " + expected)
        return errors
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        errors.append(location + ": unsupported value " + repr(value))
    if "enum" in schema and value not in schema["enum"]:
        errors.append(location + ": unexpected value " + repr(value))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(location + ": missing " + key)
        properties = schema.get("properties", {})
        for key, item in value.items():
            child = properties.get(key, schema.get("additionalProperties", {}))
            if child is False:
                errors.append(location + ": unknown field " + key)
            elif isinstance(child, dict):
                validate(item, child, document, location + "." + key, errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(location + ": too few items")
        for index, item in enumerate(value):
            validate(item, schema.get("items", {}), document,
                     location + "[" + str(index) + "]", errors)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(location + ": empty string")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(location + ": invalid format")
        if schema.get("format") == "date-time":
            try:
                if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError:
                errors.append(location + ": timestamp with timezone required")
    if type(value) is int and "minimum" in schema and value < schema["minimum"]:
        errors.append(location + ": below minimum")
    for child in schema.get("allOf", []):
        validate(value, child, document, location, errors)
    if "oneOf" in schema:
        matches = sum(not validate(value, child, document, location, [])
                      for child in schema["oneOf"])
        if matches != 1:
            errors.append(location + ": must match exactly one allowed shape")
    if "if" in schema and not validate(value, schema["if"], document, location, []):
        validate(value, schema.get("then", {}), document, location, errors)
    return errors


def masked_markdown(text):
    """Mask fenced blocks while retaining offsets; no general Markdown parser."""
    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                if not line[marker.end():].strip():
                    fence = None
            lines.append(" " * len(line.rstrip("\r\n")) + ("\n" if line.endswith("\n") else ""))
        elif marker:
            fence = marker[1]
            lines.append(" " * len(line.rstrip("\r\n")) + ("\n" if line.endswith("\n") else ""))
        else:
            lines.append(line)
    return "".join(lines)


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("non-empty POSIX repository-relative path required")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or relative.startswith("./"):
        raise ValueError("absolute or traversing path is not allowed: " + relative)
    if relative in (".", "") or any(part == ".git" for part in path.parts):
        raise ValueError("invalid repository path: " + relative)
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError("path escapes repository: " + relative)
    return resolved


def fingerprint(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def headings(text):
    return [(len(m[1]), m[2].strip(), m.start())
            for m in re.finditer(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$", text, re.M)]


def anchor_ids(text):
    counts, result = {}, set()
    for _, title, _ in headings(masked_markdown(text)):
        title = re.sub(r"<[^>]*>", "", title).lower()
        slug = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        result.add(slug + ("-" + str(number) if number else ""))
    return result


def links(text):
    """Common inline and reference links; mask comments, fences and inline code."""
    text = masked_markdown(text)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"(`+).*?\1", "", text)
    definitions = {}
    for match in re.finditer(r'^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)', text, re.M):
        definitions[match[1].strip().casefold()] = match[2].strip("<>")
    text = re.sub(r'^ {0,3}\[[^\]]+\]:.*$', "", text, flags=re.M)
    targets = [m[1].strip("<>") for m in re.finditer(
        r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\s*\)', text)]
    text = re.sub(r'!?\[[^\]\n]*\]\([^\n]*?\)', "", text)
    for match in re.finditer(r'!?\[([^\]\n]+)\](?:\[([^\]\n]*)\])?', text):
        label = (match[2] if match[2] else match[1]).strip().casefold()
        if label in definitions:
            targets.append(definitions[label])
        elif match[2] is not None:
            targets.append("missing-reference:" + label)
    return targets


def locate_symbol(path, symbol):
    """Conservative Java text locator, deliberately not an AST/call graph."""
    if path.suffix != ".java":
        return "unknown"
    match = re.fullmatch(r"([\w.]+)(?:#(\w+)\(([^()]*)\))?", symbol)
    if not match:
        return "unknown"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"', " ", text)
    owner = match[1].split(".")[-1]
    owners = re.findall(r"\b(?:class|interface|enum|record)\s+(\w+)", text)
    if owner not in owners:
        return "broken"
    if not match[2]:
        return "located"
    # Multiple types and overloads need AI inspection; do not guess ownership.
    if len(owners) != 1:
        return "unknown"
    name, params = match[2], match[3]
    if params and not re.fullmatch(r"[\w.\[\] ,]+", params):
        return "unknown"
    requested = [x.strip().split(".")[-1] for x in params.split(",") if x.strip()]
    candidates = re.findall(
        r"(?:^|[;{}])\s*(?:@[\w.]+(?:\([^)]*\))?\s*)*"
        r"(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)*"
        r"[\w.\[\]<>?,]+\s+" + re.escape(name) +
        r"\s*\(([^()]*)\)\s*(?:throws\s+[\w.,\s]+)?[;{]", text, re.M)
    for candidate in candidates:
        if "<" in candidate or "@" in candidate or "..." in candidate:
            return "unknown"
        actual = []
        for param in candidate.split(",") if candidate.strip() else []:
            bits = param.strip().removeprefix("final ").split()
            if len(bits) != 2:
                return "unknown"
            actual.append(bits[0].split(".")[-1])
        if actual == requested:
            return "located"
    if not re.search(r"\b" + re.escape(name) + r"\s*\(", text):
        return "broken"
    # Signature/ownership beyond this subset needs AI inspection.
    return "unknown"


class Handbook:
    def __init__(self, root):
        self.root = root.resolve()
        self.issues, self.pages = [], {}
        self.state = {"schema_version": 1, "pages": {}}
        self.state_available = False
        self.inventory = None
        self.metadata_schema = parse_json((ASSETS / "metadata-schema.json").read_text())
        self.state_schema = parse_json((ASSETS / "state-schema.json").read_text())
        self.inventory_schema = parse_json((ASSETS / "inventory-schema.json").read_text())
        self.load()

    def issue(self, level, code, path, message):
        self.issues.append({"level": level, "code": code, "path": path, "message": message})

    def load(self):
        directory = self.root / HANDBOOK_DIR
        if not directory.is_dir() or not self.root.is_dir():
            self.issue("error", "handbook-missing", HANDBOOK_DIR, "Handbook directory is missing")
            return
        try:
            safe_path(self.root, HANDBOOK_DIR)
        except ValueError as exc:
            self.issue("error", "unsafe-path", HANDBOOK_DIR, str(exc))
            return
        for name in ROOT_KINDS:
            if not (directory / name).is_file():
                self.issue("error", "page-missing", HANDBOOK_DIR + "/" + name, "Required page is missing")
        for path in sorted(directory.rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            try:
                safe_path(self.root, rel)
                text = path.read_text(encoding="utf-8")
                visible = masked_markdown(text)
                matches = list(META_RE.finditer(visible))
                markers = list(re.finditer(r"<!--\s*handbook-meta\b", visible))
                if len(matches) != 1 or len(markers) != 1:
                    raise ValueError("Exactly one closed handbook-meta block is required outside code fences")
                hs = headings(re.sub(r"<!--[\s\S]*?-->", lambda m: " " * len(m[0]), visible))
                h1 = [h for h in hs if h[0] == 1]
                h2 = [h for h in hs if h[0] == 2]
                if len(h1) != 1 or not h2 or not (h1[0][2] < matches[0].start() < h2[0][2]):
                    raise ValueError("metadata must follow one H1 and precede the first H2")
                metadata = parse_json(matches[0][1])
                errors = validate(metadata, self.metadata_schema, self.metadata_schema)
                if errors:
                    raise ValueError("; ".join(errors))
                local = path.relative_to(directory)
                expected = ROOT_KINDS.get(local.as_posix())
                if len(local.parts) == 2 and local.parts[0] in ("modules", "flows"):
                    expected = "module" if local.parts[0] == "modules" else "flow"
                if expected is None or metadata["kind"] != expected:
                    raise ValueError("page path does not match Handbook layout / metadata kind")
                titles = [h[1] for h in h2]
                for title in SECTIONS.get(expected, []):
                    if title not in titles:
                        self.issue("error", "section-missing", rel, title)
                self.pages[rel] = {"metadata": metadata, "text": text, "sections": titles}
            except (OSError, UnicodeError, ValueError) as exc:
                self.issue("error", "metadata-invalid", rel, str(exc))
        state_path = directory / ".state.json"
        if not state_path.exists():
            self.issue("warning", "baseline-unavailable", STATE_PATH, "No recorded state")
        else:
            try:
                safe_path(self.root, STATE_PATH)
                state = parse_json(state_path.read_text(encoding="utf-8"))
                errors = validate(state, self.state_schema, self.state_schema)
                if errors:
                    raise ValueError("; ".join(errors))
                for page, record in state["pages"].items():
                    safe_path(self.root, page)
                    if not page.startswith(HANDBOOK_DIR + "/") or not page.endswith(".md"):
                        raise ValueError("state page must be a " + HANDBOOK_DIR + " Markdown path: " + page)
                    for source in record["sources"]:
                        safe_path(self.root, source)
                self.state, self.state_available = state, True
            except (OSError, UnicodeError, ValueError) as exc:
                self.issue("error", "state-invalid", STATE_PATH, str(exc))
        try:
            inventory_path = safe_path(self.root, INVENTORY_PATH)
            if not inventory_path.is_file():
                self.issue("error", "inventory-missing", INVENTORY_PATH, "Agent-authored inventory is required")
            else:
                inventory = parse_json(inventory_path.read_text(encoding="utf-8"))
                errors = validate(inventory, self.inventory_schema, self.inventory_schema)
                if errors:
                    raise ValueError("; ".join(errors))
                self.validate_inventory_relations(inventory)
                self.inventory = inventory
        except (OSError, UnicodeError, ValueError) as exc:
            self.issue("error", "inventory-invalid", INVENTORY_PATH, str(exc))

    def validate_inventory_relations(self, inventory):
        """Check Agent-recorded structure, never discover or classify source code."""
        files = {item["path"]: item for item in inventory["files"]}
        units = {item["id"]: item for item in inventory["units"]}
        if len(files) != len(inventory["files"]) or len(units) != len(inventory["units"]):
            raise ValueError("Duplicate inventory file path or unit ID")
        for scope in inventory["scope"]["include"]:
            if scope != ".":
                safe_path(self.root, scope)
        for item in inventory["scope"]["exclude"]:
            relative = item["path"]
            if (PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts
                    or "\\" in relative or relative.startswith("./")):
                raise ValueError("Invalid excluded path: " + relative)
        for item in files.values():
            safe_path(self.root, item["path"])
            if set(item["units"]) - units.keys():
                raise ValueError("Unknown file owner: " + item["path"])
            if item["fingerprint"] is None and not item["reason"].strip():
                raise ValueError("Missing fingerprint requires a reason: " + item["path"])
        for unit in units.values():
            if set(unit["depends_on"]) - units.keys():
                raise ValueError("Unknown unit dependency: " + unit["id"])
            for source in unit["sources"] + [entry["path"] for entry in unit["entrypoints"]]:
                safe_path(self.root, source)
                if source not in files or unit["id"] not in files[source]["units"]:
                    raise ValueError("Source or entry is not assigned to unit: " + unit["id"] + ": " + source)
            for page in unit["pages"]:
                safe_path(self.root, page)
                if page not in self.pages:
                    raise ValueError("Unknown unit page: " + unit["id"] + ": " + page)
            if unit["status"] == "accepted" and (unit["gaps"] or not unit["pages"] or not unit["sources"]
                    or any(unit["review"][kind]["status"] != "passed" for kind in ("source", "reading"))):
                raise ValueError("Accepted unit requires sources, pages, no gaps and both reviews: " + unit["id"])
            if unit["status"] == "accepted" and not any(
                    self.pages[page]["metadata"]["kind"] in ("module", "flow")
                    and self.pages[page]["metadata"]["coverage"] == "documented"
                    and self.pages[page]["metadata"]["claims"] for page in unit["pages"]):
                raise ValueError("Accepted unit requires a documented module/flow with claims: " + unit["id"])
        if inventory["status"] == "complete":
            if not inventory["discovery"]["checked"] or not inventory["discovery"]["methods"]:
                raise ValueError("Complete inventory requires discovery records")
            if inventory["discovery"]["remaining"] or any(item["disposition"] == "pending" for item in files.values()):
                raise ValueError("Complete inventory has pending discovery or files")
            if inventory["mode"] == "full" and any(unit["status"] != "accepted" for unit in units.values()):
                raise ValueError("Full completion requires every unit to be accepted")

    def inventory_candidates(self, changed):
        """Follow only dependencies recorded by the Agent; return review candidates."""
        if self.inventory is None:
            return []
        units = self.inventory["units"]
        affected = {unit["id"] for unit in units if set(unit["sources"]) & changed}
        for item in self.inventory["files"]:
            if item["path"] in changed:
                affected.update(item["units"])
        while True:
            expanded = affected | {unit["id"] for unit in units if set(unit["depends_on"]) & affected}
            if expanded == affected:
                break
            affected = expanded
        return [{"id": unit["id"], "pages": unit["pages"]} for unit in units if unit["id"] in affected]

    def check_inventory_sources(self):
        if self.inventory is None:
            return {"status": "unavailable"}
        changed, unknown = set(), set()
        for item in self.inventory["files"]:
            if item["disposition"] == "excluded":
                continue
            try:
                path = safe_path(self.root, item["path"])
                if not path.is_file() or (item["fingerprint"] is not None and fingerprint(path) != item["fingerprint"]):
                    changed.add(item["path"])
                elif item["fingerprint"] is None:
                    unknown.add(item["path"])
            except (OSError, ValueError):
                unknown.add(item["path"])
        for code, paths in (("inventory-source-changed", changed), ("inventory-source-unknown", unknown)):
            for path in sorted(paths):
                self.issue("warning", code, INVENTORY_PATH, path)
        recorded = self.inventory["status"]
        return {"mode": self.inventory["mode"], "recorded_status": recorded,
                "status": "incomplete" if (changed or unknown) and recorded == "complete" else recorded,
                "changed_files": sorted(changed), "unknown_files": sorted(unknown),
                "related_units": self.inventory_candidates(changed | unknown)}

    def current_sources(self, page):
        return {source["path"] for claim in page["metadata"]["claims"] for source in claim["sources"]}

    def check_links(self, rel, page):
        for target in links(page["text"]):
            if target.startswith("missing-reference:"):
                self.issue("error", "link-broken", rel, target)
                continue
            try:
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                # Links can use ../ within the repository, unlike source paths.
                linked = (self.root / rel).parent / unquote(url.path) if url.path else self.root / rel
                linked = linked.resolve()
                linked.relative_to(self.root)
                if not linked.exists():
                    raise ValueError("Missing link target: " + target)
                if url.fragment and linked.suffix in (".md", ".mdx"):
                    if unquote(url.fragment) not in anchor_ids(linked.read_text(encoding="utf-8")):
                        raise ValueError("Missing heading anchor: " + target)
            except (OSError, UnicodeError, ValueError) as exc:
                self.issue("error", "link-broken", rel, str(exc))

    def check_relations(self):
        ids, claims, modules = {}, {}, {}
        for rel, page in self.pages.items():
            meta = page["metadata"]
            if meta["id"] in ids:
                self.issue("error", "page-id-duplicate", rel, meta["id"])
            ids[meta["id"]] = rel
            if meta["kind"] == "module":
                modules[meta["id"]] = rel
            for claim in meta["claims"]:
                if claim["id"] in claims:
                    self.issue("error", "claim-id-duplicate", rel, claim["id"])
                claims[claim["id"]] = rel
                if claim["section"] not in page["sections"]:
                    self.issue("error", "claim-section-missing", rel, claim["section"])
            for scope in meta.get("source_ranges", []) + meta.get("config_ranges", []):
                self.check_range(rel, scope)
        for rel, page in self.pages.items():
            meta = page["metadata"]
            if meta["kind"] == "flow":
                if not meta["modules"]:
                    self.issue("warning", "flow-modules-empty", rel, "Flow participants are not recorded")
                for module in meta["modules"]:
                    if module not in modules:
                        self.issue("error", "module-reference-broken", rel, module)
            if meta["kind"] == "map":
                mapped = set()
                for module in meta["modules"]:
                    if module["id"] in mapped:
                        self.issue("error", "map-id-duplicate", rel, module["id"])
                    mapped.add(module["id"])
                    if modules.get(module["id"]) != module["page"]:
                        self.issue("error", "map-module-broken", rel, module["id"] + " -> " + module["page"])
                    for scope in module["source_ranges"] + module["config_ranges"]:
                        self.check_range(rel, scope)
                    if module["page"] in self.pages:
                        actual = self.pages[module["page"]]["metadata"]
                        for field in ("source_ranges", "config_ranges"):
                            if sorted(module[field]) != sorted(actual.get(field, [])):
                                self.issue("error", "map-range-mismatch", rel, module["id"] + ": " + field)
                for module in modules.keys() - mapped:
                    self.issue("error", "map-module-missing", rel, module)
                for entry in meta["unowned_entries"]:
                    self.issue("warning", "unowned-entry", rel, entry)

    def check_range(self, rel, scope):
        try:
            if not safe_path(self.root, scope).exists():
                raise ValueError("Missing owned path: " + scope)
        except (OSError, ValueError) as exc:
            self.issue("error", "range-broken", rel, str(exc))

    def check(self):
        self.check_relations()
        inventory = self.check_inventory_sources()
        affected_pages = {page for unit in inventory.get("related_units", []) for page in unit["pages"]}
        states = {}
        for rel, page in self.pages.items():
            self.check_links(rel, page)
            undocumented = (page["metadata"]["kind"] in ("module", "flow")
                            and page["metadata"]["coverage"] == "documented"
                            and not page["metadata"]["claims"])
            if undocumented:
                self.issue("warning", "documented-without-claims", rel,
                           "Documented module/flow has no implementation claims; content review is required")
            current = self.current_sources(page)
            recorded = self.state["pages"].get(rel, {})
            previous = recorded.get("sources", {})
            source_results, broken, unknown = {}, False, False
            for claim in page["metadata"]["claims"]:
                for source in claim["sources"]:
                    path = source["path"]
                    try:
                        full = safe_path(self.root, path)
                        if not full.is_file():
                            raise ValueError("Source file is missing: " + path)
                        digest = fingerprint(full)
                        status = "baseline-unavailable" if path not in previous else (
                            "unchanged" if previous[path] == digest else "changed")
                        source_results[path] = {"status": status, "fingerprint": digest}
                        if source.get("symbol"):
                            located = locate_symbol(full, source["symbol"])
                            if located == "broken":
                                broken = True
                                self.issue("error", "symbol-broken", rel, path + ": " + source["symbol"])
                            elif located == "unknown":
                                unknown = True
                                self.issue("warning", "symbol-unverified", rel, path + ": " + source["symbol"])
                    except (OSError, UnicodeError, ValueError) as exc:
                        broken = True
                        source_results[path] = {"status": "broken"}
                        self.issue("error", "source-broken", rel, str(exc))
            stale = sorted(set(previous) - current)
            statuses = {entry["status"] for entry in source_results.values()}
            if broken:
                state = "broken"
            elif stale or "changed" in statuses:
                state = "changed"
            elif "baseline-unavailable" in statuses:
                state = "baseline-unavailable"
            elif unknown or not current:
                state = "unknown"
            else:
                state = "unchanged"
            review = recorded.get("review", {}).get("status", "needs_review")
            if state != "unchanged" or undocumented or rel in affected_pages:
                review = "needs_review"
            states[rel] = {"id": page["metadata"]["id"], "coverage": page["metadata"]["coverage"],
                           "source_state": state, "sources": source_results,
                           "removed_source_references": stale, "review": review,
                           "recorded_verification": recorded.get("verification", {"status": "not-run"})}
        for rel in sorted(self.state["pages"].keys() - self.pages.keys()):
            self.issue("warning", "state-page-stale", rel, "Recorded page is missing or invalid; retain state for impact review")
        return {"command": "check", "pages": states, "inventory": inventory, "issues": self.issues,
                "read_only": True,
                "limits": ["No business semantics or runtime verification is performed.",
                           "Unchanged fingerprints cover directly recorded files only.",
                           "Java symbol location is a conservative textual check; unsupported syntax remains unverified.",
                           "Inventory discovery, ownership and review truth require Agent assessment; no source scan is performed."]}


def git(root, *arguments):
    try:
        result = subprocess.run(["git", "-C", str(root), *arguments],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise ValueError("Git unavailable: " + str(exc))
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def git_commit(root, ref):
    return git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()


def diff_files(raw):
    fields = raw.decode("utf-8", errors="surrogateescape").split("\0")
    changed, renames = set(), []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index]
        index += 1
        old = fields[index]
        changed.add(old)
        index += 1
        if status.startswith(("R", "C")):
            new = fields[index]
            changed.add(new)
            renames.append({"status": status, "old_path": old, "new_path": new})
            index += 1
    return changed, renames


def impact(book, base=None, target=None):
    result = {"command": "impact", "candidate_only": True, "read_only": True,
              "changed_files": [], "renames": [], "direct_claims": [],
              "previous_pages": [], "related_modules": [], "related_flows": [],
              "unowned_changes": [], "related_units": [], "issues": book.issues,
              "metadata_version": "current-worktree",
              "limits": ["Candidates need AI source review; indirect dependencies can require wider analysis."]}
    changed, available = set(), False
    baseline = base or book.state.get("baseline", {}).get("commit")
    try:
        top = Path(git(book.root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        available = top == book.root
    except ValueError:
        pass
    if available and baseline:
        try:
            resolved_base = git_commit(book.root, baseline)
            args = ["diff", "--name-status", "-z", "--find-renames", resolved_base]
            resolved_target = git_commit(book.root, target) if target and target != "worktree" else None
            if resolved_target:
                args.append(resolved_target)
            args.extend(["--", "."])
            changed, result["renames"] = diff_files(git(book.root, *args))
            if resolved_target is None:
                changed.update(p for p in git(book.root, "ls-files", "--others", "--exclude-standard", "-z")
                               .decode("utf-8", errors="surrogateescape").split("\0") if p)
            result.update({"mode": "git", "base": resolved_base,
                           "target": resolved_target or "worktree", "baseline_status": "available"})
        except ValueError as exc:
            book.issue("error", "git-diff-unavailable", STATE_PATH, str(exc))
            result.update({"mode": "unavailable", "baseline_status": "baseline-unavailable"})
            return result
    elif base or (target and target != "worktree"):
        book.issue("error", "git-diff-unavailable", STATE_PATH, "Requested refs require a Git repository and a base")
        result.update({"mode": "unavailable", "baseline_status": "baseline-unavailable"})
        return result
    else:
        count = 0
        for record in book.state["pages"].values():
            for source, old in record["sources"].items():
                count += 1
                try:
                    path = safe_path(book.root, source)
                    if not path.is_file() or fingerprint(path) != old:
                        changed.add(source)
                except (OSError, ValueError):
                    changed.add(source)
        if book.inventory is not None:
            for item in book.inventory["files"]:
                if item["disposition"] == "excluded" or item["fingerprint"] is None:
                    continue
                count += 1
                try:
                    path = safe_path(book.root, item["path"])
                    if not path.is_file() or fingerprint(path) != item["fingerprint"]:
                        changed.add(item["path"])
                except (OSError, ValueError):
                    changed.add(item["path"])
        result.update({"mode": "fingerprint", "baseline_status": "available" if count else "baseline-unavailable"})
        result["limits"].append("Fingerprint mode cannot discover unrecorded files, renames, or unrecorded dependencies.")
        if not count:
            book.issue("warning", "baseline-unavailable", STATE_PATH, "No historical source fingerprints")
    # Handbook edits are not implementation changes; state retains old associations.
    changed = {p for p in changed if not p.startswith(HANDBOOK_DIR + "/")}
    covered, touched_modules, touched_flows = set(), set(), set()
    for rel, page in book.pages.items():
        meta = page["metadata"]
        for claim in meta["claims"]:
            matched = sorted(changed & {source["path"] for source in claim["sources"]})
            if matched:
                result["direct_claims"].append({"page": rel, "claim": claim["id"], "files": matched})
                covered.update(matched)
                if meta["kind"] == "module":
                    touched_modules.add(meta["id"])
                elif meta["kind"] == "flow":
                    touched_flows.add(meta["id"])
        if meta["kind"] == "module":
            for scope in meta["source_ranges"] + meta["config_ranges"]:
                try:
                    safe_path(book.root, scope)
                except ValueError as exc:
                    book.issue("error", "unsafe-range", rel, str(exc))
                    continue
                matched = {p for p in changed if p == scope.rstrip("/") or p.startswith(scope.rstrip("/") + "/")}
                if matched:
                    covered.update(matched)
                    touched_modules.add(meta["id"])
        prior = book.state["pages"].get(rel, {}).get("sources", {})
        matched = sorted(changed & set(prior))
        if matched:
            result["previous_pages"].append({"page": rel, "files": matched})
            covered.update(matched)
            if meta["kind"] == "module":
                touched_modules.add(meta["id"])
            elif meta["kind"] == "flow":
                touched_flows.add(meta["id"])
    for rel in sorted(book.state["pages"].keys() - book.pages.keys()):
        matched = sorted(changed & set(book.state["pages"][rel]["sources"]))
        if matched:
            result["previous_pages"].append({"page": rel, "files": matched})
            covered.update(matched)
    for rel, page in book.pages.items():
        meta = page["metadata"]
        if meta["kind"] == "flow" and (meta["id"] in touched_flows or set(meta["modules"]) & touched_modules):
            touched_flows.add(meta["id"])
            result["related_flows"].append({"id": meta["id"], "page": rel})
        if meta["kind"] == "module" and meta["id"] in touched_modules:
            result["related_modules"].append({"id": meta["id"], "page": rel})
    result["changed_files"] = sorted(changed)
    if book.inventory is not None:
        covered.update(item["path"] for item in book.inventory["files"]
                       if item["disposition"] in ("assigned", "excluded"))
    result["unowned_changes"] = sorted(changed - covered)
    result["related_units"] = book.inventory_candidates(changed)
    return result


def render(result):
    rows = [result["command"] + (" (candidate impact only)" if result["command"] == "impact" else " (mechanical checks only)")]
    if result["command"] == "check":
        rows.append("Inventory: " + json.dumps(result["inventory"], ensure_ascii=False))
        for path, page in result["pages"].items():
            rows.append(path + ": " + page["coverage"] + " / " + page["source_state"] + " / " + page["review"])
    else:
        rows.append("Mode: " + result["mode"] + "; baseline: " + result["baseline_status"])
        for key in ("changed_files", "direct_claims", "previous_pages", "related_modules", "related_flows", "related_units", "unowned_changes"):
            rows.append(key + ": " + json.dumps(result[key], ensure_ascii=False))
    for issue in result["issues"]:
        rows.append(issue["level"] + " " + issue["code"] + " " + issue["path"] + ": " + issue["message"])
    rows.extend("Limit: " + limit for limit in result["limits"])
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "impact"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, default=Path("."))
        command.add_argument("--format", choices=("text", "json"), default="text")
        if name == "impact":
            command.add_argument("--base", help="base Git commit/ref; otherwise state baseline or fingerprints")
            command.add_argument("--target", help="target Git commit/ref, or worktree (default)")
    args = parser.parse_args(argv)
    book = Handbook(args.root)
    result = book.check() if args.command == "check" else impact(book, args.base, args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == "json" else render(result))
    return 1 if any(issue["level"] == "error" for issue in result["issues"]) else 0


if __name__ == "__main__":
    sys.exit(main())
