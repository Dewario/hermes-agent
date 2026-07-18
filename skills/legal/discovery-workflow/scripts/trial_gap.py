#!/usr/bin/env python3
"""Slice G1: trial_gap_assessment — recommend additional plaintiff discovery (synthetic-only).

Emits trial_gap_items + suggested B1–B3 issue-brief lines. Does not draft serve-ready
sets or objections. Live use needs SPEC §9.5 sign-off.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"
LOAD_PACK_SCRIPT = WORKFLOW_ROOT / "jurisdiction" / "load_pack.py"

THEMES_REL = Path("01_discovery_outgoing") / "gap_themes.md"
ITEMS_REL = Path("02_outputs") / "trial_gap_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "trial_gap_report.md"
META_REL = Path("02_outputs") / "trial_gap_meta.json"
EXPORT_RFP = Path("01_discovery_outgoing") / "gap_suggested_rfp_issue_brief.md"
EXPORT_ROG = Path("01_discovery_outgoing") / "gap_suggested_rog_issue_brief.md"
EXPORT_RFA = Path("01_discovery_outgoing") / "gap_suggested_rfa_issue_brief.md"
EXISTING_BRIEFS = (
    Path("01_discovery_outgoing") / "rfp_issue_brief.md",
    Path("01_discovery_outgoing") / "rog_issue_brief.md",
    Path("01_discovery_outgoing") / "rfa_issue_brief.md",
)
PROFILE_REL = Path("03_attorney") / "matter_profile.yaml"

SCHEMA_VERSION = 1
MODE = "trial_gap_assessment"
REQUEST_TYPE_MULTI = "multi"

ISSUE_TAGS = {
    "liability",
    "notice",
    "causation",
    "damages",
    "medical",
    "wage_loss",
    "impeachment",
    "authenticity",
    "admissibility",
    "jury_theme",
}
PRIORITIES = {"must_before_cutoff", "should", "optional", "defer_to_attorney"}
REQUEST_TYPES = {"rfp", "rog", "rfa"}

THEME_LINE_RE = re.compile(
    r"^\s*-\s*\[(?P<tags>[^\]]+)\]\s+(?P<body>.+?)"
    r"(?:\s*\|\s*prefer:\s*(?P<prefer>rfp|rog|rfa))?"
    r"(?:\s*\|\s*priority:\s*(?P<priority>[a-z_]+))?"
    r"(?:\s*\|\s*Jury:\s*(?P<jury>[^|]+))?"
    r"\s*$",
    re.IGNORECASE,
)
BRIEF_TAG_RE = re.compile(r"^\s*-\s*\[(?P<tags>[^\]]+)\]\s+(?P<body>.+)$", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "all", "about", "for", "from", "the", "that", "this", "with",
    "of", "to", "in", "on", "or", "any", "after", "before", "plaintiff", "defendant",
}


class UsageError(RuntimeError):
    """Bad input state."""


def _load_module(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cg = _load_module(CASEGRAPH_SCRIPT, "legal_casegraph_trial_gap")
jp = _load_module(LOAD_PACK_SCRIPT, "jurisdiction_load_pack_g1")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeError:
            continue
    return data.decode("utf-8", errors="replace")


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise UsageError(f"missing JSONL file: {path}")
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise UsageError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def matter_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise UsageError(f"matter directory not found: {root}")
    return root


def contained(root: Path, rel_or_abs: str | Path) -> Path:
    path = Path(rel_or_abs)
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UsageError(f"path escapes matter dir: {resolved}") from exc
    return resolved


def output_path(root: Path, rel: Path) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def refresh_casegraph_index(root: Path) -> int:
    if not (root / ".casegraph" / "manifest.json").is_file():
        return 0
    return cg.main(["build", str(root)])


def _matter_id(root: Path) -> str:
    try:
        return str(cg.load_manifest(root).get("matter_id") or root.name)
    except Exception:
        return root.name


def load_matter_profile(root: Path) -> dict[str, Any]:
    path = root / PROFILE_REL
    if not path.is_file():
        raise UsageError(
            f"missing {PROFILE_REL.as_posix()} — required for trial_gap_assessment "
            "(jurisdiction_pack, optional case_overlay / discovery_cutoff)"
        )
    try:
        import yaml
    except ImportError as exc:
        raise UsageError("PyYAML required to read matter_profile.yaml") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise UsageError(f"invalid matter_profile.yaml: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError("matter_profile.yaml must be a mapping")
    pack = str(data.get("jurisdiction_pack") or "").strip()
    if not pack:
        raise UsageError("matter_profile.yaml must set jurisdiction_pack")
    overlay = data.get("case_overlay")
    overlay_id = str(overlay).strip() if overlay else None
    return {
        "matter_id": data.get("matter_id") or _matter_id(root),
        "court": data.get("court"),
        "jurisdiction_pack": pack,
        "case_overlay": overlay_id or None,
        "discovery_cutoff": data.get("discovery_cutoff"),
        "expert_cutoff": data.get("expert_cutoff"),
        "limits_used": data.get("limits_used") or {},
        "raw": data,
    }


def parse_issue_tags(raw: str) -> list[str]:
    tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
    unknown = [t for t in tags if t not in ISSUE_TAGS]
    if unknown:
        raise UsageError(f"unknown issue tag(s): {', '.join(unknown)}")
    if not tags:
        raise UsageError("each theme line needs at least one issue tag")
    return tags


def parse_gap_themes(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        match = THEME_LINE_RE.match(line)
        if not match:
            raise UsageError(
                f"theme line {lineno}: expected "
                "'- [tag, ...] theme text [| prefer: rfp|rog|rfa] [| priority: …] [| Jury: …]'"
            )
        tags = parse_issue_tags(match.group("tags"))
        body = match.group("body").strip()
        prefer = (match.group("prefer") or "").strip().lower() or None
        priority = (match.group("priority") or "").strip().lower() or "should"
        jury = (match.group("jury") or "").strip() or None
        if prefer and prefer not in REQUEST_TYPES:
            raise UsageError(f"theme line {lineno}: invalid prefer={prefer!r}")
        if priority not in PRIORITIES:
            raise UsageError(f"theme line {lineno}: invalid priority={priority!r}")
        if "jury_theme" in tags and not jury:
            raise UsageError(f"theme line {lineno}: jury_theme requires '| Jury: …'")
        rows.append({
            "theme_id": f"TH-{len(rows) + 1}",
            "issue_tags": tags,
            "element_or_theme": body,
            "prefer": prefer,
            "priority": priority,
            "jury_note": jury,
            "source_line": lineno,
        })
    if not rows:
        raise UsageError("zero gap themes parsed")
    return rows


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9]{3,}", text.lower())
        if t not in STOPWORDS
    }


def _load_existing_brief_coverage(root: Path) -> list[dict[str, Any]]:
    covered: list[dict[str, Any]] = []
    for rel in EXISTING_BRIEFS:
        path = root / rel
        if not path.is_file():
            continue
        for raw in read_text(path).splitlines():
            match = BRIEF_TAG_RE.match(raw.strip())
            if not match:
                continue
            try:
                tags = parse_issue_tags(match.group("tags"))
            except UsageError:
                continue
            covered.append({
                "tags": set(tags),
                "tokens": _tokens(match.group("body")),
                "relpath": rel.as_posix(),
            })
    return covered


def _index_token_blob(root: Path) -> str:
    docs_path = root / ".casegraph" / "documents.jsonl"
    chunks: list[str] = []
    if docs_path.is_file():
        for line in docs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rel = row.get("relpath") or row.get("path") or ""
            if not rel:
                continue
            candidate = root / rel
            if candidate.is_file():
                try:
                    chunks.append(read_text(candidate).lower())
                except OSError:
                    continue
    return "\n".join(chunks)


def _default_prefer(tags: list[str]) -> str:
    if "authenticity" in tags or "admissibility" in tags:
        return "rfa"
    if "medical" in tags or "wage_loss" in tags:
        return "rog"
    return "rfp"


def _rule_ids_for_theme(
    tags: list[str],
    prefer: str,
    available: set[str],
    rules: list[dict[str, Any]],
) -> list[str]:
    selected: set[str] = set()
    # Procedural baselines by recommended type
    baselines = {
        "rfp": ["FRCP-34-a", "FRCP-26-b-1"],
        "rog": ["FRCP-33-a-1", "FRCP-26-b-1"],
        "rfa": ["FRCP-36-a-1", "FRCP-26-b-1"],
    }
    for rid in baselines.get(prefer, ["FRCP-26-b-1"]):
        if rid in available:
            selected.add(rid)
    tag_set = set(tags)
    for rule in rules:
        rid = str(rule.get("id") or "")
        if rid not in available:
            continue
        hints = [str(h).lower() for h in (rule.get("check_hints") or [])]
        applies = [str(a).lower() for a in (rule.get("applies_to") or [])]
        if applies and prefer not in applies and "all" not in applies:
            continue
        for tag in tag_set:
            if tag in hints or f"issue_tag:{tag}" in hints:
                selected.add(rid)
                break
        # FELA theme ids by naming convention
        if rid.startswith("FELA-THEME-"):
            for tag in tag_set:
                if tag in rid.lower() or tag.replace("_", "") in rid.lower().replace("-", ""):
                    selected.add(rid)
            if "notice" in tag_set and "NOTICE" in rid:
                selected.add(rid)
            if "liability" in tag_set and "DUTY" in rid:
                selected.add(rid)
            if ("medical" in tag_set or "wage_loss" in tag_set) and "MEDICAL" in rid:
                selected.add(rid)
            if "liability" in tag_set and "RAIL" in rid:
                selected.add(rid)
    if not selected and "FRCP-26-b-1" in available:
        selected.add("FRCP-26-b-1")
    return sorted(selected)


def _suggested_brief_line(
    *,
    tags: list[str],
    theme: str,
    prefer: str,
    jury: str | None,
    already_covered: bool,
) -> str:
    tag_s = ", ".join(tags)
    theme_clean = " ".join(theme.split()).strip(" .")
    if prefer == "rfa":
        body = f"Admit that {theme_clean}."
    elif prefer == "rog":
        if theme_clean.lower().startswith(("state ", "identify ", "describe ", "list ", "explain ")):
            body = theme_clean[0].upper() + theme_clean[1:]
            if not body.endswith("."):
                body += "."
        else:
            body = f"Identify all facts and witnesses concerning {theme_clean}."
    else:
        if theme_clean.lower().startswith(("produce ", "provide ")):
            body = theme_clean[0].upper() + theme_clean[1:]
            if not body.endswith("."):
                body += "."
        else:
            body = f"Produce all documents concerning {theme_clean}."
    already = "covered" if already_covered else "gap"
    parts = [f"- [{tag_s}] {body}"]
    if jury:
        parts.append(f"Jury: {jury}")
    parts.append(f"Already: {already}")
    return " | ".join(parts)


def assess_themes(
    themes: list[dict[str, Any]],
    *,
    profile: dict[str, Any],
    loaded_pack: dict[str, Any],
    existing: list[dict[str, Any]],
    index_blob: str,
) -> list[dict[str, Any]]:
    available = set(loaded_pack["rule_ids"])
    rules = list(loaded_pack.get("rules") or [])
    cutoff = profile.get("discovery_cutoff")
    items: list[dict[str, Any]] = []
    for i, theme in enumerate(themes, 1):
        tags = list(theme["issue_tags"])
        prefer = theme.get("prefer") or _default_prefer(tags)
        priority = theme["priority"]
        notes: list[str] = []
        needs_attorney = True
        theme_tokens = _tokens(theme["element_or_theme"])
        already = False
        for cov in existing:
            overlap_tags = cov["tags"] & set(tags)
            overlap_tok = theme_tokens & cov["tokens"]
            if overlap_tags and len(overlap_tok) >= 2:
                already = True
                notes.append(f"Overlaps existing brief {cov['relpath']}.")
                break
        record_hits = [t for t in theme_tokens if t in index_blob]
        if record_hits:
            notes.append(
                "Indexed production mentions theme keywords "
                f"({', '.join(sorted(record_hits)[:6])}); attorney must confirm sufficiency."
            )
        if priority == "must_before_cutoff" and not cutoff:
            priority = "defer_to_attorney"
            notes.append(
                "Priority was must_before_cutoff but discovery_cutoff is unset — "
                "deferred for attorney cutoff confirmation."
            )
        rule_ids = _rule_ids_for_theme(tags, prefer, available, rules)
        if not rule_ids:
            notes.append("No pack rule_ids resolved — needs_attorney_rule_confirm.")
        brief = _suggested_brief_line(
            tags=tags,
            theme=theme["element_or_theme"],
            prefer=prefer,
            jury=theme.get("jury_note"),
            already_covered=already,
        )
        items.append({
            "gap_id": f"TG-{i}",
            "theme_id": theme["theme_id"],
            "issue_tags": tags,
            "element_or_theme": theme["element_or_theme"],
            "recommended_request_type": prefer,
            "priority": priority,
            "rule_ids": rule_ids,
            "already_covered": already,
            "suggested_brief_line": brief,
            "jury_note": theme.get("jury_note"),
            "needs_attorney_decision": needs_attorney,
            "needs_attorney_rule_confirm": any("needs_attorney_rule_confirm" in n for n in notes),
            "notes": " ".join(notes) if notes else "Attorney must decide whether to propound.",
            "mode": MODE,
            "request_type": REQUEST_TYPE_MULTI,
        })
    return items


def cmd_parse_gap_themes(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    source = contained(root, args.source or THEMES_REL)
    if not source.is_file():
        print(f"ERROR: gap themes not found: {source}", file=sys.stderr)
        return 2
    try:
        rows = parse_gap_themes(read_text(source))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    # stash parsed themes beside meta for assess step
    themes_out = output_path(root, Path("02_outputs") / "gap_themes_parsed.jsonl")
    write_jsonl(themes_out, rows)
    write_json(
        output_path(root, META_REL),
        {
            "schema_version": SCHEMA_VERSION,
            "mode": MODE,
            "request_type": REQUEST_TYPE_MULTI,
            "source": {
                "relpath": source.relative_to(root).as_posix(),
                "sha256": sha256_file(source),
            },
            "parsed_at": utcnow(),
            "theme_count": len(rows),
        },
    )
    refresh_casegraph_index(root)
    print(f"parsed {len(rows)} gap themes -> {themes_out}")
    return 0


def cmd_assess_trial_gaps(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    themes_path = root / "02_outputs" / "gap_themes_parsed.jsonl"
    try:
        profile = load_matter_profile(root)
        loaded = jp.load_pack(
            profile["jurisdiction_pack"],
            overlay_id=profile.get("case_overlay"),
            allow_stub=bool(args.allow_stub_pack),
        )
        if not themes_path.is_file():
            raise UsageError("missing gap_themes_parsed.jsonl — run parse-gap-themes first")
        themes = read_jsonl(themes_path)
    except (UsageError, jp.PackError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    existing = _load_existing_brief_coverage(root)
    index_blob = _index_token_blob(root)
    items = assess_themes(
        themes,
        profile=profile,
        loaded_pack=loaded,
        existing=existing,
        index_blob=index_blob,
    )
    write_jsonl(output_path(root, ITEMS_REL), items)
    meta_path = root / META_REL
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    meta.update({
        "assessed_at": utcnow(),
        "jurisdiction_pack": profile["jurisdiction_pack"],
        "case_overlay": profile.get("case_overlay"),
        "discovery_cutoff": profile.get("discovery_cutoff"),
        "gap_count": len(items),
        "open_gap_count": sum(1 for i in items if not i.get("already_covered")),
    })
    write_json(output_path(root, META_REL), meta)
    refresh_casegraph_index(root)
    print(f"assessed {len(items)} trial gaps -> {root / ITEMS_REL}")
    return 0


def cmd_export_issue_briefs(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    items = read_jsonl(root / ITEMS_REL)
    by_type: dict[str, list[str]] = {"rfp": [], "rog": [], "rfa": []}
    for item in items:
        if item.get("already_covered") and not args.include_covered:
            continue
        rtype = str(item.get("recommended_request_type") or "")
        line = str(item.get("suggested_brief_line") or "").strip()
        if rtype in by_type and line:
            by_type[rtype].append(line)
    header = (
        "<!-- synthetic / non-client / test only -->\n"
        "# Gap-suggested issue brief (DRAFT — attorney review required)\n"
        "# Generated by trial_gap export-issue-briefs. Not serve-ready.\n\n"
    )
    mapping = {
        "rfp": EXPORT_RFP,
        "rog": EXPORT_ROG,
        "rfa": EXPORT_RFA,
    }
    for rtype, rel in mapping.items():
        path = output_path(root, rel)
        body = "\n".join(by_type[rtype]) + ("\n" if by_type[rtype] else "")
        path.write_text(header + body, encoding="utf-8", newline="\n")
        print(f"wrote {len(by_type[rtype])} {rtype} suggested lines -> {path}")
    refresh_casegraph_index(root)
    return 0


def validate_items(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not items:
        errors.append("no trial gap items")
    ids = [i.get("gap_id") for i in items]
    if len(set(ids)) != len(ids):
        errors.append("duplicate gap_ids")
    for item in items:
        gid = item.get("gap_id")
        if item.get("mode") != MODE:
            errors.append(f"{gid}: wrong mode")
        if item.get("priority") not in PRIORITIES:
            errors.append(f"{gid}: invalid priority")
        if item.get("recommended_request_type") not in REQUEST_TYPES:
            errors.append(f"{gid}: invalid recommended_request_type")
        if not item.get("rule_ids") and not item.get("needs_attorney_rule_confirm"):
            errors.append(f"{gid}: must have rule_ids or needs_attorney_rule_confirm")
        tags = item.get("issue_tags") or []
        unknown = [t for t in tags if t not in ISSUE_TAGS]
        if unknown:
            errors.append(f"{gid}: unknown tags {unknown}")
        line = str(item.get("suggested_brief_line") or "")
        if not line.startswith("- ["):
            errors.append(f"{gid}: suggested_brief_line must be brief-shaped")
        if re.search(r"\b(?:RFP|ROG|RFA)-0\d{2,}\b", line):
            errors.append(f"{gid}: Bates-like request id in suggested_brief_line")
    return errors


def build_package(root: Path, items: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    matter_id = _matter_id(root)
    lines = [
        "<!-- synthetic / non-client / test only -->",
        "",
        "# Trial Gap Assessment - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Mode:** {MODE}",
        f"**Jurisdiction pack:** {meta.get('jurisdiction_pack') or '—'}",
        f"**Case overlay:** {meta.get('case_overlay') or '—'}",
        f"**Discovery cutoff:** {meta.get('discovery_cutoff') or 'unset'}",
        f"**Source sha256:** {(meta.get('source') or {}).get('sha256') or '—'}",
        "**Casegraph status:** fresh",
        "**Single-matter invocation:** confirmed",
        "",
        "> Draft recommendations only. Does not authorize service of discovery.",
        "> Feed open gaps into B1–B3 issue briefs after attorney edit.",
        "> No invented Bates or transcript locators.",
        "",
        "## Gaps",
        "",
    ]
    for item in items:
        tags = ", ".join(item.get("issue_tags") or []) or "—"
        rules = ", ".join(item.get("rule_ids") or []) or "—"
        covered = "yes" if item.get("already_covered") else "no"
        lines.extend([
            f"### Gap {item.get('gap_id')}",
            "",
            f"**Theme:** {item.get('element_or_theme')}",
            f"**Tags:** {tags}",
            f"**Recommend:** {item.get('recommended_request_type')}",
            f"**Priority:** {item.get('priority')}",
            f"**Already covered:** {covered}",
            f"**Rule ids:** {rules}",
            "",
            f"`{item.get('suggested_brief_line')}`",
            "",
            f"_Notes:_ {item.get('notes') or '—'}",
            "",
        ])
    open_items = [i for i in items if not i.get("already_covered")]
    lines.extend(["## Open attorney priorities", ""])
    if open_items:
        for item in open_items:
            lines.append(
                f"- {item.get('gap_id')} [{item.get('priority')}] "
                f"→ {item.get('recommended_request_type')}: {item.get('element_or_theme')}"
            )
    else:
        lines.append("- No open gaps (attorney should still confirm sufficiency before trial).")
    lines.extend([
        "",
        "## Attorney checklist",
        "",
        "- [ ] Priorities reviewed against docket / cutoff",
        "- [ ] Suggested brief lines edited before B1–B3 draft runs",
        "- [ ] No foreign or invented Bates in exports",
        "- [ ] Gate commands for Slice G1 exit 0",
        "- [ ] Owner §9.5 sign-off before any live matter use",
        "",
    ])
    return "\n".join(lines)


def cmd_package(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_items(items)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    meta = {}
    if (root / META_REL).is_file():
        meta = json.loads((root / META_REL).read_text(encoding="utf-8"))
    path = output_path(root, PACKAGE_REL)
    path.write_text(build_package(root, items, meta), encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote trial gap package -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    items = read_jsonl(root / ITEMS_REL)
    errors = validate_items(items)
    package = root / PACKAGE_REL
    if not package.is_file():
        errors.append(f"missing package: {package}")
    else:
        text = package.read_text(encoding="utf-8")
        if re.search(r"\b(?:RFP|ROG|RFA)-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding RFP/ROG/RFA-00N tokens")
    for rel in (EXPORT_RFP, EXPORT_ROG, EXPORT_RFA):
        path = root / rel
        if path.is_file():
            body = path.read_text(encoding="utf-8")
            if re.search(r"\b(?:RFP|ROG|RFA)-0\d{2,}\b", body):
                errors.append(f"{rel.as_posix()}: Bates-like request ids forbidden")
    try:
        profile = load_matter_profile(root)
        jp.load_pack(
            profile["jurisdiction_pack"],
            overlay_id=profile.get("case_overlay"),
            allow_stub=bool(args.allow_stub_pack),
        )
    except (UsageError, jp.PackError) as exc:
        errors.append(str(exc))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    gates = [
        [sys.executable, str(CASEGRAPH_SCRIPT), "status", str(root)],
        [sys.executable, str(CASEGRAPH_SCRIPT), "verify-cites", str(root), str(package), "--allow-empty"],
        [sys.executable, str(CASEGRAPH_SCRIPT), "check-isolation", str(root), str(package), "--strict"],
    ]
    if not args.skip_live_preflight:
        synthetic = bool(args.synthetic) or (root / ".synthetic").is_file()
        preflight = [
            sys.executable, str(LIVE_PREFLIGHT_SCRIPT),
            "--matter-dir", str(root),
        ]
        if synthetic:
            preflight.append("--skip-ocr-queue")
        gates.append(preflight)
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print("PASS: trial gap validation")
    return 0


def _write_profile(root: Path, matter_id: str, *, cutoff: str | None = None) -> None:
    (root / "03_attorney").mkdir(parents=True, exist_ok=True)
    cutoff_line = f'"{cutoff}"' if cutoff else "null"
    (root / PROFILE_REL).write_text(
        f"matter_id: {matter_id}\n"
        "court: \"U.S. District Court (synthetic)\"\n"
        "jurisdiction_pack: frcp_generic\n"
        "case_overlay: fela\n"
        f"discovery_cutoff: {cutoff_line}\n"
        "expert_cutoff: null\n"
        "limits_used:\n"
        "  rog: 0\n"
        "  rfp: null\n"
        "  rfa: 0\n",
        encoding="utf-8",
    )


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "01_discovery_outgoing").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-17\n", encoding="utf-8",
    )
    _write_profile(root, matter_id)
    (root / THEMES_REL).write_text(
        "<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->\n\n"
        "# Gap themes\n\n"
        "- [notice] prior notice of ladder defect | prefer: rfp | priority: must_before_cutoff | Jury: prior notice\n"
        "- [medical, wage_loss] post-incident treatment and earnings proof | prefer: rog | priority: should\n"
        "- [authenticity] photograph exhibit authenticity | prefer: rfa | priority: optional | Jury: exhibit authenticity\n"
        "- [liability] inspection history for the ladder | prefer: rfp | priority: should\n",
        encoding="utf-8",
    )
    # Existing brief covering liability inspection — should mark that theme covered
    (root / "01_discovery_outgoing" / "rfp_issue_brief.md").write_text(
        "- [liability] Produce all inspection reports for the ladder.\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000010\n\n"
        "Complaint log notes a written complaint about the ladder on May 1, 2024.\n",
        encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", prefix])
    cg.main(["build", str(root)])


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="trial-gap-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYNTHETIC_client_a"
        b = root / "SYNTHETIC_client_b"
        _create_synthetic_matter(a, "SYN-TG-A", "THORN-PROD")
        _create_synthetic_matter(b, "SYN-TG-B", "RIVER-PROD")
        for matter in (a, b):
            for command in (
                ["parse-gap-themes", str(matter)],
                ["assess-trial-gaps", str(matter)],
                ["export-issue-briefs", str(matter)],
                ["package-trial-gap", str(matter)],
                ["validate-trial-gap", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        a_items = read_jsonl(a / ITEMS_REL)
        if not any(i.get("already_covered") for i in a_items):
            print("selftest failed: expected already_covered liability theme", file=sys.stderr)
            return 1
        if not any(
            i.get("priority") == "defer_to_attorney" and "notice" in (i.get("issue_tags") or [])
            for i in a_items
        ):
            print("selftest failed: expected cutoff deferral on notice theme", file=sys.stderr)
            return 1
        if not all(i.get("rule_ids") for i in a_items):
            print("selftest failed: every gap needs rule_ids", file=sys.stderr)
            return 1
        export = (a / EXPORT_RFP).read_text(encoding="utf-8")
        if "Produce all documents concerning prior notice" not in export and "prior notice" not in export:
            print("selftest failed: expected open notice line in RFP export", file=sys.stderr)
            return 1
        if "inspection reports" in export.lower() and "Already: covered" in export:
            # covered items should not be exported by default
            print("selftest failed: covered liability line leaked into export", file=sys.stderr)
            return 1
        a_pkg = (a / PACKAGE_REL).read_text(encoding="utf-8")
        b_pkg = (b / PACKAGE_REL).read_text(encoding="utf-8")
        if "RIVER-PROD" in a_pkg or "THORN-PROD" in b_pkg:
            print("selftest failed: cross-matter Bates leaked", file=sys.stderr)
            return 1
        if re.search(r"\bRFP-0\d{2,}\b", a_pkg):
            print("selftest failed: Bates-like RFP-00N in package", file=sys.stderr)
            return 1
        print("PASS: trial-gap selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-gap-themes", help="parse attorney gap theme brief")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path)
    p.set_defaults(fn=cmd_parse_gap_themes)

    p = sub.add_parser("assess-trial-gaps", help="assess gaps against pack + briefs + index")
    p.add_argument("matter_dir")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_assess_trial_gaps)

    p = sub.add_parser("export-issue-briefs", help="write suggested B1–B3 brief lines")
    p.add_argument("matter_dir")
    p.add_argument("--include-covered", action="store_true")
    p.set_defaults(fn=cmd_export_issue_briefs)

    p = sub.add_parser("package-trial-gap", help="write trial_gap_report.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package)

    p = sub.add_parser("validate-trial-gap", help="run Slice G1 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("selftest", help="offline synthetic G1 E2E")
    p.set_defaults(fn=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
