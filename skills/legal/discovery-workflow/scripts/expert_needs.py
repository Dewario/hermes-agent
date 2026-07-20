#!/usr/bin/env python3
"""Slice E1: expert_needs_assessment for plaintiff-side trial planning.

Builds a deterministic attorney-review packet identifying expert categories to
consider for liability and damages. It does not select experts, retain experts,
or make final legal/strategic conclusions. Live use still requires owner 9.5.
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
MATTER_SAFETY = LEGAL_ROOT / "scripts" / "matter_safety.py"
LOAD_PACK_SCRIPT = WORKFLOW_ROOT / "jurisdiction" / "load_pack.py"

PROFILE_REL = Path("03_attorney") / "matter_profile.yaml"
ITEMS_REL = Path("02_outputs") / "expert_needs_items.jsonl"
PACKAGE_REL = Path("02_outputs") / "expert_needs_assessment.md"
META_REL = Path("02_outputs") / "expert_needs_meta.json"

MODE = "expert_needs_assessment"
REQUEST_TYPE = "expert"
SLICE_ID = "E1"
SCHEMA_VERSION = 1

DEFAULT_SOURCES = (
    PROFILE_REL,
    Path("00_intake") / "case_context.md",
    Path("00_intake") / "intake_package.md",
    Path("01_discovery_outgoing") / "gap_themes.md",
    Path("02_outputs") / "trial_gap_report.md",
    Path("02_outputs") / "trial_gap_items.jsonl",
)
SOURCE_GLOBS = (
    "01_discovery_outgoing/*_issue_brief.md",
    "01_discovery_outgoing/gap_suggested_*_issue_brief.md",
)

PRIORITIES = {"must_consider", "should_consider", "attorney_confirm"}
TRACKS = {"liability", "damages"}
STOPWORDS = {
    "about", "after", "also", "and", "any", "are", "case", "client",
    "defendant", "discovery", "for", "from", "has", "have", "into",
    "matter", "plaintiff", "that", "the", "this", "with",
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


cg = _load_module(CASEGRAPH_SCRIPT, "legal_casegraph_expert_needs")
_ms = _load_module(MATTER_SAFETY, "matter_safety_expert_needs")
jp = _load_module(LOAD_PACK_SCRIPT, "jurisdiction_load_pack_e1")


EXPERT_PROFILES: list[dict[str, Any]] = [
    {
        "expert_type": "premises_safety",
        "track": "liability",
        "keywords": {
            "premises", "property", "inspection", "maintenance", "stairs",
            "ladder", "floor", "fall", "slip", "trip", "code", "lighting",
            "handrail", "warning", "hazard", "notice",
        },
        "strong_terms": {"notice", "inspection", "maintenance", "code", "hazard"},
        "why_needed": "Evaluate notice, hazard control, inspection practice, and safer-condition proof.",
        "plaintiff_value": "Supports breach, foreseeability, and practical safety alternatives.",
        "discovery_followups": [
            "maintenance and inspection logs",
            "prior incident/complaint evidence",
            "site photographs, measurements, and policies",
        ],
    },
    {
        "expert_type": "accident_reconstruction",
        "track": "liability",
        "keywords": {
            "collision", "crash", "impact", "vehicle", "speed", "braking",
            "visibility", "intersection", "trajectory", "fall", "mechanism",
            "scene", "photographs", "measurements",
        },
        "strong_terms": {"collision", "crash", "impact", "speed", "mechanism"},
        "why_needed": "Reconstruct event mechanics where the fact record leaves causation or fault contested.",
        "plaintiff_value": "Turns physical facts into a coherent liability explanation for trial.",
        "discovery_followups": [
            "scene measurements and photographs",
            "vehicle or object inspection evidence",
            "witness timing and visibility facts",
        ],
    },
    {
        "expert_type": "human_factors",
        "track": "liability",
        "keywords": {
            "warning", "visibility", "perception", "reaction", "attention",
            "lighting", "signage", "distraction", "foreseeable", "avoid",
            "hazard", "user", "ergonomic",
        },
        "strong_terms": {"warning", "visibility", "perception", "reaction"},
        "why_needed": "Assess perception, warnings, attention, and whether the hazard was reasonably avoidable.",
        "plaintiff_value": "Helps answer defense themes that the plaintiff should have seen or avoided the condition.",
        "discovery_followups": [
            "warning/signage evidence",
            "lighting and sightline evidence",
            "photographs from plaintiff viewpoint",
        ],
    },
    {
        "expert_type": "industry_standard_or_operations",
        "track": "liability",
        "keywords": {
            "standard", "policy", "procedure", "training", "supervision",
            "osha", "ansi", "railroad", "truck", "dispatch", "safety rule",
            "audit", "compliance", "operations",
        },
        "strong_terms": {"standard", "policy", "training", "railroad", "osha", "ansi"},
        "why_needed": "Map defendant conduct against industry, safety, training, or operational standards.",
        "plaintiff_value": "Anchors breach proof in practices a jury can compare against defendant choices.",
        "discovery_followups": [
            "training materials and policies",
            "safety audits and incident reports",
            "discipline and rule-compliance records",
        ],
    },
    {
        "expert_type": "medical_causation_and_prognosis",
        "track": "damages",
        "keywords": {
            "injury", "treatment", "surgery", "orthopedic", "neurology",
            "pain", "causation", "prognosis", "permanent", "future care",
            "impairment", "diagnosis", "therapy", "spine", "fracture",
        },
        "strong_terms": {"surgery", "permanent", "future care", "causation", "impairment"},
        "why_needed": "Connect incident facts to injuries, treatment necessity, prognosis, and future medical needs.",
        "plaintiff_value": "Strengthens medical causation and guards against defense apportionment themes.",
        "discovery_followups": [
            "complete medical records and bills",
            "prior-injury and baseline records",
            "treating-provider opinion availability",
        ],
    },
    {
        "expert_type": "life_care_planner",
        "track": "damages",
        "keywords": {
            "future care", "life care", "home care", "attendant", "therapy",
            "medical equipment", "surgery", "permanent", "chronic", "medication",
            "rehabilitation", "assistive", "impairment",
        },
        "strong_terms": {"future care", "life care", "home care", "permanent", "chronic"},
        "why_needed": "Translate future treatment and functional needs into a medically grounded care plan.",
        "plaintiff_value": "Makes future damages concrete and easier for an economist and jury to use.",
        "discovery_followups": [
            "future treatment recommendations",
            "functional-capacity and ADL evidence",
            "payer and cost-source documentation",
        ],
    },
    {
        "expert_type": "vocational_rehabilitation",
        "track": "damages",
        "keywords": {
            "work", "job", "occupation", "restrictions", "limitations",
            "wage loss", "earning capacity", "vocational", "return to work",
            "accommodation", "disability",
        },
        "strong_terms": {"wage loss", "earning capacity", "restrictions", "vocational"},
        "why_needed": "Evaluate employability, restrictions, job access, and reduced earning capacity.",
        "plaintiff_value": "Bridges medical limitations to labor-market and work-life losses.",
        "discovery_followups": [
            "employment file and wage history",
            "job description and physical demands",
            "medical restrictions and functional capacity evidence",
        ],
    },
    {
        "expert_type": "economist",
        "track": "damages",
        "keywords": {
            "wage loss", "earning capacity", "lost earnings", "future loss",
            "benefits", "retirement", "inflation", "present value", "life care",
            "medical cost", "economic",
        },
        "strong_terms": {"wage loss", "earning capacity", "present value", "future loss"},
        "why_needed": "Calculate past and future economic losses, present value, and related benefits losses.",
        "plaintiff_value": "Gives the damages presentation a transparent numerical backbone.",
        "discovery_followups": [
            "tax, payroll, and benefits records",
            "vocational assumptions",
            "future-care cost assumptions",
        ],
    },
    {
        "expert_type": "neuropsychology_or_neurology",
        "track": "damages",
        "keywords": {
            "tbi", "concussion", "head injury", "memory", "cognition",
            "brain", "neuro", "dizziness", "headache", "executive function",
            "post-concussive",
        },
        "strong_terms": {"tbi", "concussion", "brain", "memory", "cognition"},
        "why_needed": "Assess neurological or cognitive injury, functional impact, and testing support.",
        "plaintiff_value": "Makes invisible cognitive damages concrete and testable.",
        "discovery_followups": [
            "neuro records and imaging",
            "school/work performance records if relevant",
            "family/coworker functional observations",
        ],
    },
    {
        "expert_type": "mental_health",
        "track": "damages",
        "keywords": {
            "ptsd", "anxiety", "depression", "trauma", "sleep", "fear",
            "emotional distress", "therapy", "counseling", "nightmares",
        },
        "strong_terms": {"ptsd", "depression", "anxiety", "therapy"},
        "why_needed": "Evaluate emotional distress, trauma symptoms, treatment, and prognosis.",
        "plaintiff_value": "Supports a disciplined non-economic damages presentation.",
        "discovery_followups": [
            "mental-health treatment records",
            "symptom timeline",
            "pre-incident mental-health baseline if at issue",
        ],
    },
    {
        "expert_type": "medical_billing_reasonableness",
        "track": "damages",
        "keywords": {
            "billing", "bills", "charges", "medical cost", "lien", "reasonable",
            "customary", "paid", "writeoff", "provider charge",
        },
        "strong_terms": {"billing", "bills", "charges", "reasonable"},
        "why_needed": "Assess billed charges and reasonable value where medical-cost proof is contested.",
        "plaintiff_value": "Prepares damages proof for disputes over reasonableness and charge foundation.",
        "discovery_followups": [
            "itemized bills and liens",
            "payment/writeoff data where discoverable",
            "provider charge foundation",
        ],
    },
]


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
            f"missing {PROFILE_REL.as_posix()} - required for {MODE} "
            "(jurisdiction_pack, optional case_overlay, discovery/expert cutoffs)"
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
    return {
        "matter_id": data.get("matter_id") or _matter_id(root),
        "court": data.get("court"),
        "jurisdiction_pack": pack,
        "case_overlay": str(overlay).strip() if overlay else None,
        "discovery_cutoff": data.get("discovery_cutoff"),
        "expert_cutoff": data.get("expert_cutoff"),
        "case_type": data.get("case_type"),
        "liability_theory": data.get("liability_theory"),
        "injuries": data.get("injuries"),
        "damages_theory": data.get("damages_theory"),
        "raw": data,
    }


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower())
        if t not in STOPWORDS
    }


def _term_pattern(term: str) -> re.Pattern[str]:
    pieces = [re.escape(p) for p in term.lower().split()]
    return re.compile(r"\b" + r"\s+".join(pieces) + r"\b", re.IGNORECASE)


def _matches_term(text: str, term: str) -> bool:
    if " " in term:
        return _term_pattern(term).search(text) is not None
    return term.lower() in _tokens(text)


def _jsonl_text(path: Path) -> str:
    lines: list[str] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            lines.append(f"line {lineno}: {line}")
            continue
        parts: list[str] = []
        for key in (
            "gap_id", "theme_id", "issue_tags", "element_or_theme",
            "recommended_request_type", "priority", "suggested_brief_line",
            "notes",
        ):
            val = row.get(key)
            if val:
                parts.append(f"{key}: {val}")
        lines.append(f"line {lineno}: " + " | ".join(parts))
    return "\n".join(lines)


def collect_sources(root: Path, explicit_sources: list[Path]) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    if explicit_sources:
        candidates.extend(contained(root, p) for p in explicit_sources)
    else:
        candidates.extend(root / rel for rel in DEFAULT_SOURCES)
        for pattern in SOURCE_GLOBS:
            candidates.extend(sorted(root.glob(pattern)))

    seen: set[Path] = set()
    docs: list[dict[str, Any]] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved in seen or not resolved.is_file():
            continue
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise UsageError(f"path escapes matter dir: {resolved}") from exc
        seen.add(resolved)
        text = _jsonl_text(resolved) if resolved.suffix.lower() == ".jsonl" else read_text(resolved)
        if not text.strip():
            continue
        docs.append({
            "path": resolved,
            "relpath": resolved.relative_to(root).as_posix(),
            "sha256": sha256_file(resolved),
            "text": text,
            "lines": text.splitlines(),
        })
    if not docs:
        raise UsageError("no source documents found; provide --source or intake/gap files")
    return docs


def _source_hits(
    docs: list[dict[str, Any]],
    terms: set[str],
    *,
    max_hits: int = 6,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for doc in docs:
        for lineno, line in enumerate(doc["lines"], 1):
            matched = sorted(term for term in terms if _matches_term(line, term))
            if not matched:
                continue
            hits.append({
                "relpath": doc["relpath"],
                "line": lineno,
                "matched_terms": matched[:8],
                "excerpt": " ".join(line.strip().split())[:240],
            })
            if len(hits) >= max_hits:
                return hits
    return hits


def _rule_ids_for_expert_need(
    profile: dict[str, Any],
    loaded_pack: dict[str, Any],
) -> list[str]:
    available = set(loaded_pack.get("rule_ids") or [])
    preferred = [
        "EVID-720", "EVID-801", "CCP-2034-210", "CCP-2034-260",
        "CCP-2034-280", "CCP-2034-300", "SBC-LR-411-2",
        "WA-ER-702", "WA-ER-703", "WA-CR-26-B5", "WA-CR-26-B7",
        "KING-LCR-26-WITNESS", "PIERCE-PCLR-26-WITNESS",
    ]
    selected = [rid for rid in preferred if rid in available]
    track = str(profile.get("track") or "")
    hints = {"expert", "expert_disclosure", "expert_qualification", f"{track}_expert"}
    for rule in jp.rules_for_type(loaded_pack, "expert"):
        rid = str(rule.get("id") or "")
        if rid in selected:
            continue
        rule_hints = {str(h).lower() for h in (rule.get("check_hints") or [])}
        if hints & rule_hints:
            selected.append(rid)
    return selected[:8]


def _priority(profile: dict[str, Any], hits: list[dict[str, Any]], text_blob: str) -> str:
    strong = {str(t).lower() for t in (profile.get("strong_terms") or set())}
    matched = {
        term.lower()
        for hit in hits
        for term in (hit.get("matched_terms") or [])
    }
    if strong & matched:
        return "must_consider"
    if profile["track"] == "damages" and any(
        phrase in text_blob
        for phrase in ("surgery", "permanent", "future care", "wage loss", "earning capacity")
    ):
        return "must_consider"
    return "should_consider" if len(hits) >= 2 else "attorney_confirm"


def assess_expert_needs(
    docs: list[dict[str, Any]],
    *,
    profile: dict[str, Any],
    loaded_pack: dict[str, Any],
) -> list[dict[str, Any]]:
    text_blob = "\n".join(doc["text"].lower() for doc in docs)
    items: list[dict[str, Any]] = []
    for spec in EXPERT_PROFILES:
        terms = {str(t).lower() for t in spec["keywords"]}
        if not any(_matches_term(text_blob, term) for term in terms):
            continue
        hits = _source_hits(docs, terms)
        if not hits:
            continue
        rule_ids = _rule_ids_for_expert_need(spec, loaded_pack)
        item_id = f"EN-{len(items) + 1:02d}"
        context = "; ".join(hit["excerpt"] for hit in hits[:2])
        items.append({
            "expert_need_id": item_id,
            "track": spec["track"],
            "expert_type": spec["expert_type"],
            "priority": _priority(spec, hits, text_blob),
            "source_anchors": hits,
            "case_context": context,
            "why_needed": spec["why_needed"],
            "plaintiff_value": spec["plaintiff_value"],
            "rule_ids": rule_ids,
            "needs_attorney_decision": True,
            "needs_attorney_rule_confirm": not bool(rule_ids),
            "attorney_decisions": [
                "confirm whether this expert category is needed",
                "confirm retained/nonretained/treating status",
                "confirm disclosure and deposition deadlines",
            ],
            "discovery_followups": list(spec["discovery_followups"]),
            "mode": MODE,
            "request_type": REQUEST_TYPE,
        })

    if not items:
        rule_ids = []
        for rule in jp.rules_for_type(loaded_pack, "expert"):
            rid = str(rule.get("id") or "")
            if rid:
                rule_ids.append(rid)
        first_doc = docs[0]
        items.append({
            "expert_need_id": "EN-01",
            "track": "liability",
            "expert_type": "attorney_triage_required",
            "priority": "attorney_confirm",
            "source_anchors": [{
                "relpath": first_doc["relpath"],
                "line": 1,
                "matched_terms": ["source_available"],
                "excerpt": "No deterministic expert category was triggered; attorney must triage facts.",
            }],
            "case_context": "Insufficient deterministic triggers for expert category selection.",
            "why_needed": "Attorney review is required before concluding no expert is needed.",
            "plaintiff_value": "Prevents a silent false negative in expert planning.",
            "rule_ids": rule_ids[:6],
            "needs_attorney_decision": True,
            "needs_attorney_rule_confirm": not bool(rule_ids),
            "attorney_decisions": [
                "add case facts if available",
                "decide whether liability and damages experts are needed",
                "confirm court schedule and disclosure deadlines",
            ],
            "discovery_followups": ["supply case context and trial-gap materials"],
            "mode": MODE,
            "request_type": REQUEST_TYPE,
        })
    return items


def validate_items(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not items:
        errors.append("no expert need items")
    ids = [i.get("expert_need_id") for i in items]
    if len(set(ids)) != len(ids):
        errors.append("duplicate expert_need_ids")
    for item in items:
        eid = item.get("expert_need_id")
        if item.get("mode") != MODE:
            errors.append(f"{eid}: wrong mode")
        if item.get("request_type") != REQUEST_TYPE:
            errors.append(f"{eid}: wrong request_type")
        if item.get("track") not in TRACKS:
            errors.append(f"{eid}: invalid track")
        if item.get("priority") not in PRIORITIES:
            errors.append(f"{eid}: invalid priority")
        if not item.get("expert_type"):
            errors.append(f"{eid}: missing expert_type")
        if item.get("expert_name"):
            errors.append(f"{eid}: expert_name forbidden")
        if item.get("needs_attorney_decision") is not True:
            errors.append(f"{eid}: needs_attorney_decision must be true")
        if not item.get("source_anchors"):
            errors.append(f"{eid}: missing source_anchors")
        if not item.get("rule_ids") and not item.get("needs_attorney_rule_confirm"):
            errors.append(f"{eid}: must have rule_ids or needs_attorney_rule_confirm")
        for anchor in item.get("source_anchors") or []:
            if not anchor.get("relpath") or not anchor.get("line"):
                errors.append(f"{eid}: malformed source anchor")
    return errors


def build_package(root: Path, items: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    matter_id = _matter_id(root)
    by_track = {
        "liability": [i for i in items if i.get("track") == "liability"],
        "damages": [i for i in items if i.get("track") == "damages"],
    }
    lines = [
        "# Expert Needs Assessment - DRAFT FOR ATTORNEY REVIEW",
        "",
        f"**Matter ID:** {matter_id}",
        f"**Mode:** {MODE}",
        f"**Jurisdiction pack:** {meta.get('jurisdiction_pack') or '-'}",
        f"**Case overlay:** {meta.get('case_overlay') or '-'}",
        f"**Discovery cutoff:** {meta.get('discovery_cutoff') or 'unset'}",
        f"**Expert cutoff:** {meta.get('expert_cutoff') or 'unset'}",
        "**Single-matter invocation:** confirmed",
        "",
        "> Attorney-review package only. It identifies expert categories to consider; it does not retain, designate, or finally approve any expert.",
        "> rule ids come from the loaded jurisdiction pack and must be checked against case-specific orders before live use.",
        "",
    ]
    for track, track_items in by_track.items():
        lines.extend([f"## {track.title()} Experts", ""])
        if not track_items:
            lines.append("- No deterministic candidate triggered; attorney must still confirm.")
            lines.append("")
            continue
        lines.append("| Priority | Expert category | Why it matters | Source anchors | rule ids |")
        lines.append("|---|---|---|---|---|")
        for item in track_items:
            anchors = "; ".join(
                f"{a.get('relpath')}:{a.get('line')}"
                for a in (item.get("source_anchors") or [])[:4]
            )
            rules = ", ".join(item.get("rule_ids") or []) or "ATTORNEY_CONFIRM"
            lines.append(
                f"| {item.get('priority')} | {item.get('expert_type')} | "
                f"{item.get('plaintiff_value')} | {anchors} | {rules} |"
            )
        lines.append("")

    lines.extend(["## Detail", ""])
    for item in items:
        anchors = item.get("source_anchors") or []
        lines.extend([
            f"### {item.get('expert_need_id')} - {item.get('expert_type')}",
            "",
            f"**Track:** {item.get('track')}",
            f"**Priority:** {item.get('priority')}",
            f"**Why needed:** {item.get('why_needed')}",
            f"**Plaintiff value:** {item.get('plaintiff_value')}",
            f"**Case context:** {item.get('case_context')}",
            f"**rule ids:** {', '.join(item.get('rule_ids') or []) or 'ATTORNEY_CONFIRM'}",
            "",
            "**Source anchors:**",
        ])
        for anchor in anchors[:6]:
            lines.append(
                f"- `{anchor.get('relpath')}:{anchor.get('line')}` "
                f"({', '.join(anchor.get('matched_terms') or [])}) - {anchor.get('excerpt')}"
            )
        lines.extend(["", "**Discovery follow-ups:**"])
        for followup in item.get("discovery_followups") or []:
            lines.append(f"- {followup}")
        lines.extend(["", "**Attorney decisions:**"])
        for decision in item.get("attorney_decisions") or []:
            lines.append(f"- [ ] {decision}")
        lines.append("")

    lines.extend([
        "## Attorney Checklist",
        "",
        "- [ ] Liability expert categories confirmed or rejected on the record.",
        "- [ ] Damages expert categories confirmed or rejected on the record.",
        "- [ ] Retained / nonretained / treating status confirmed for each candidate category.",
        "- [ ] Disclosure, exchange, and deposition deadlines confirmed against docket and local orders.",
        "- [ ] Source anchors checked against the matter record.",
        "- [ ] Owner 9.5 sign-off before any live matter use.",
        "",
    ])
    return "\n".join(lines)


def cmd_assess(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    try:
        profile = load_matter_profile(root)
        loaded = jp.load_pack(
            profile["jurisdiction_pack"],
            overlay_id=profile.get("case_overlay"),
            allow_stub=bool(args.allow_stub_pack),
        )
        docs = collect_sources(root, list(args.source or []))
    except (UsageError, jp.PackError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    items = assess_expert_needs(docs, profile=profile, loaded_pack=loaded)
    write_jsonl(output_path(root, ITEMS_REL), items)
    write_json(
        output_path(root, META_REL),
        {
            "schema_version": SCHEMA_VERSION,
            "mode": MODE,
            "request_type": REQUEST_TYPE,
            "assessed_at": utcnow(),
            "matter_id": profile["matter_id"],
            "jurisdiction_pack": profile["jurisdiction_pack"],
            "case_overlay": profile.get("case_overlay"),
            "discovery_cutoff": profile.get("discovery_cutoff"),
            "expert_cutoff": profile.get("expert_cutoff"),
            "source_count": len(docs),
            "sources": [
                {"relpath": d["relpath"], "sha256": d["sha256"]}
                for d in docs
            ],
            "expert_need_count": len(items),
        },
    )
    refresh_casegraph_index(root)
    print(f"assessed {len(items)} expert needs -> {root / ITEMS_REL}")
    return 0


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
    print(f"wrote expert needs package -> {path}")
    return 0


def run_command(command: list[str]) -> int:
    return subprocess.run(command, text=True, check=False).returncode


def cmd_validate(args: argparse.Namespace) -> int:
    root = matter_root(args.matter_dir)
    errors = validate_items(read_jsonl(root / ITEMS_REL))
    package = root / PACKAGE_REL
    if not package.is_file():
        errors.append(f"missing package: {package}")
    else:
        text = package.read_text(encoding="utf-8")
        if re.search(r"\b(?:RFP|ROG|RFA|EN)-0\d{2,}\b", text):
            errors.append("package contains Bates-colliding request/expert ids")
        if re.search(r"(?i)\bretain\s+(?:dr\.|mr\.|ms\.|mrs\.)\s+[A-Z]", text):
            errors.append("package appears to name a retained expert")
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
    _ms.append_live_preflight_gate(
        gates,
        root,
        live_preflight_script=LIVE_PREFLIGHT_SCRIPT,
        skip_live_preflight=bool(args.skip_live_preflight),
        synthetic_flag=bool(getattr(args, "synthetic", False)),
        request_type=REQUEST_TYPE,
        mode=MODE,
        slice_id=SLICE_ID,
    )
    for command in gates:
        code = run_command(command)
        if code != 0:
            print(f"FAIL: gate exited {code}: {' '.join(command)}")
            return 1
    print("PASS: expert needs validation")
    return 0


def _write_profile(root: Path, matter_id: str) -> None:
    (root / "03_attorney").mkdir(parents=True, exist_ok=True)
    (root / PROFILE_REL).write_text(
        f"matter_id: {matter_id}\n"
        "court: \"San Bernardino Superior Court (synthetic)\"\n"
        "jurisdiction_pack: ca_ccp\n"
        "case_overlay: ca_san_bernardino\n"
        "case_type: premises liability\n"
        "liability_theory: prior notice of unsafe ladder and failed inspection\n"
        "injuries: lumbar surgery, chronic pain, permanent work restrictions\n"
        "damages_theory: future care, wage loss, and reduced earning capacity\n"
        "discovery_cutoff: null\n"
        "expert_cutoff: null\n"
        "limits_used:\n"
        "  rog: 0\n"
        "  rfp: null\n"
        "  rfa: 0\n",
        encoding="utf-8",
    )


def _create_synthetic_matter(root: Path, matter_id: str, prefix: str) -> None:
    (root / "00_intake").mkdir(parents=True)
    (root / "01_discovery_outgoing").mkdir(parents=True)
    (root / "01_production" / "raw").mkdir(parents=True)
    (root / "03_attorney").mkdir(parents=True)
    (root / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    (root / "03_attorney" / "PROVIDER_AUTH.md").write_text(
        "- Attorney initials: JD  Date: 2026-07-20\n", encoding="utf-8",
    )
    _write_profile(root, matter_id)
    (root / "00_intake" / "case_context.md").write_text(
        "# Synthetic case context\n\n"
        "Plaintiff fell from a defective ladder after prior notice and missed inspection.\n"
        "The incident caused lumbar surgery, chronic pain, future care needs, and permanent work restrictions.\n"
        "Claim includes wage loss, reduced earning capacity, and future medical costs.\n",
        encoding="utf-8",
    )
    (root / "01_discovery_outgoing" / "gap_themes.md").write_text(
        "- [notice] prior notice of ladder defect | prefer: rfp | priority: must_before_cutoff\n"
        "- [medical, wage_loss] future care, surgery, work restrictions, and earning capacity\n",
        encoding="utf-8",
    )
    (root / "01_production" / "raw" / f"{prefix}-000010.md").write_text(
        f"**Bates Range:** {prefix}-000010 - {prefix}-000010\n\n"
        "Complaint log notes a ladder complaint before the fall.\n",
        encoding="utf-8",
    )
    cg.main(["init", str(root), "--matter-id", matter_id, "--bates-prefix", prefix])
    cg.main(["build", str(root)])


def cmd_selftest(_args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="expert-needs-selftest-") as tmp:
        root = Path(tmp)
        a = root / "SYN-EXPERT-A"
        b = root / "SYN-EXPERT-B"
        _create_synthetic_matter(a, "SYN-EXPERT-A", "EXPERTA-PROD")
        _create_synthetic_matter(b, "SYN-EXPERT-B", "EXPERTB-PROD")
        for matter in (a, b):
            for command in (
                ["assess-expert-needs", str(matter)],
                ["package-expert-needs", str(matter)],
                ["validate-expert-needs", str(matter)],
            ):
                code = main(command)
                if code != 0:
                    print(f"selftest failed for {matter.name}: {' '.join(command)}", file=sys.stderr)
                    return code
        a_items = read_jsonl(a / ITEMS_REL)
        if not any(i.get("track") == "liability" for i in a_items):
            print("selftest failed: expected liability expert candidate", file=sys.stderr)
            return 1
        if not any(i.get("track") == "damages" for i in a_items):
            print("selftest failed: expected damages expert candidate", file=sys.stderr)
            return 1
        if not all(i.get("rule_ids") for i in a_items):
            print("selftest failed: every expert need should resolve rule_ids", file=sys.stderr)
            return 1
        a_pkg = (a / PACKAGE_REL).read_text(encoding="utf-8")
        b_pkg = (b / PACKAGE_REL).read_text(encoding="utf-8")
        if "EXPERTB-PROD" in a_pkg or "EXPERTA-PROD" in b_pkg:
            print("selftest failed: cross-matter Bates leaked", file=sys.stderr)
            return 1
        if "Expert Needs Assessment" not in a_pkg:
            print("selftest failed: package heading missing", file=sys.stderr)
            return 1
        print("PASS: expert-needs selftest")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("assess-expert-needs", help="assess expert categories from matter context")
    p.add_argument("matter_dir")
    p.add_argument("--source", type=Path, action="append", help="matter-relative or absolute source")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_assess)

    p = sub.add_parser("package-expert-needs", help="write expert_needs_assessment.md")
    p.add_argument("matter_dir")
    p.set_defaults(fn=cmd_package)

    p = sub.add_parser("validate-expert-needs", help="run Slice E1 validators and gates")
    p.add_argument("matter_dir")
    p.add_argument("--skip-live-preflight", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--allow-stub-pack", action="store_true")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("selftest", help="offline synthetic E1 E2E")
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
