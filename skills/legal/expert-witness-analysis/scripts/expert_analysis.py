#!/usr/bin/env python3
"""Expert witness recommendation for plaintiff trial litigation.

Deterministic, data-driven: maps case-fact patterns to expert disciplines and
cites the admissibility standard keyed to the matter's jurisdiction pack.
Does NOT retain experts, draft reports, or render legal conclusions.
Synthetic-only until owner Section 9.5.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve()
SKILL_ROOT = SCRIPT.parent.parent
LEGAL_ROOT = SKILL_ROOT.parent
REPO_ROOT = LEGAL_ROOT.parent.parent
TAXONOMY = SKILL_ROOT / "references" / "expert_taxonomy.yaml"
CASEGRAPH = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT = LEGAL_ROOT / "scripts" / "live_preflight.py"
REQUEST_TYPE = "expert"
MODE = "expert_needs_assessment"
SLICE_ID = "E1"

_ms_path = LEGAL_ROOT / "scripts" / "matter_safety.py"
_spec = importlib.util.spec_from_file_location("matter_safety_ewa", _ms_path)
assert _spec and _spec.loader
_ms = importlib.util.module_from_spec(_spec)
sys.modules["matter_safety_ewa"] = _ms
_spec.loader.exec_module(_ms)

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


JURISDICTION_STANDARD = {
    "frcp_generic": "federal",
    "fela": "federal",
    "ca_ccp": "ca",
    "ca_san_bernardino": "ca",
    "wa_state": "wa",
    "wa_king_county": "wa",
    "wa_pierce_county": "wa",
}

CASE_FACT_SOURCES = (
    Path("01_case_facts") / "case_facts.md",
    Path("01_case_facts") / "cast_context.md",
)
DISCOVERY_FEEDER_SOURCES = (
    Path("03_attorney") / "matter_profile.yaml",
    Path("00_intake") / "case_context.md",
    Path("00_intake") / "intake_package.md",
    Path("01_discovery_outgoing") / "gap_themes.md",
    Path("02_outputs") / "trial_gap_report.md",
    Path("02_outputs") / "trial_gap_items.jsonl",
)
DISCOVERY_FEEDER_GLOBS = (
    "01_discovery_outgoing/*_issue_brief.md",
    "01_discovery_outgoing/gap_suggested_*_issue_brief.md",
)


def _load_taxonomy() -> dict[str, Any]:
    if yaml is None:
        raise SystemExit("PyYAML is required to load expert_taxonomy.yaml")
    data = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("expert_taxonomy.yaml root must be a mapping")
    return data


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").lower()


def _combined_case_text(root: Path) -> tuple[str, list[str]]:
    parts: list[str] = []
    sources: list[str] = []
    seen: set[Path] = set()
    candidates = [root / rel for rel in CASE_FACT_SOURCES + DISCOVERY_FEEDER_SOURCES]
    for pattern in DISCOVERY_FEEDER_GLOBS:
        candidates.extend(sorted(root.glob(pattern)))
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        text = _read_text(resolved)
        if not text.strip():
            continue
        parts.append(text)
        try:
            sources.append(resolved.relative_to(root).as_posix())
        except ValueError:
            sources.append(str(resolved))
    return "\n".join(parts), sources


def _matter_profile(root: Path) -> dict[str, Any]:
    profile = root / "03_attorney" / "matter_profile.yaml"
    if not profile.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _standard_for(profile: dict[str, Any]) -> str:
    pack = str(profile.get("jurisdiction_pack") or "").strip()
    overlay = str(profile.get("case_overlay") or "").strip()
    for key in (overlay, pack):
        if key in JURISDICTION_STANDARD:
            return JURISDICTION_STANDARD[key]
    return "federal"


def _match_experts(text: str, experts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for exp in experts:
        kws = [str(k).lower() for k in exp.get("trigger_keywords") or []]
        hits = [kw for kw in kws if kw in text]
        if hits:
            matched.append({"expert": exp, "hits": hits})
    return matched


def _recommendation(
    exp: dict[str, Any],
    standard: str,
    hits: list[str],
    *,
    matter_id: str,
    slice_id: str,
) -> dict[str, Any]:
    notes = exp.get("admissibility_notes") or {}
    return {
        "item_id": f"{slice_id}-{exp['id']}",
        "expert_id": exp["id"],
        "discipline": exp.get("discipline"),
        "role": exp.get("role"),
        "request_type": "expert",
        "mode": slice_id,
        "matter_id": matter_id,
        "trigger_hits": hits,
        "admissibility_standard": standard,
        "admissibility_notes": notes.get(standard) or notes.get("federal"),
        "foundation_gaps": exp.get("foundation_gaps") or [],
        "needs_attorney_decision": True,
        "objection_draft": None,
    }


def parse_case_facts(matter_dir: Path) -> int:
    root = matter_dir.expanduser().resolve()
    text, sources = _combined_case_text(root)
    if not text:
        print(f"ERROR: no case facts, cast context, intake, or trial-gap sources under {root}")
        return 1
    out_dir = root / "02_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "matter_id": _ms.resolve_matter_id(root),
        "case_facts_path": str(root / "01_case_facts" / "case_facts.md"),
        "cast_context_path": str(root / "01_case_facts" / "cast_context.md"),
        "input_sources": sources,
        "combined_text_length": len(text),
    }
    (out_dir / "parsed_case_facts.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(f"parsed case facts -> {out_dir / 'parsed_case_facts.json'}")
    return 0


def _assess(matter_dir: Path, slice_id: str) -> int:
    root = matter_dir.expanduser().resolve()
    taxonomy = _load_taxonomy()
    profile = _matter_profile(root)
    standard = _standard_for(profile)
    text, _sources = _combined_case_text(root)
    key = "liability" if slice_id == "E1" else "damages"
    matched = _match_experts(text, taxonomy.get(key) or [])
    matter_id = _ms.resolve_matter_id(root)
    recs = [_recommendation(m["expert"], standard, m["hits"], matter_id=matter_id, slice_id=slice_id)
            for m in matched]
    out_dir = root / "02_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = "expert_liability_recommendations.jsonl" if slice_id == "E1" else "expert_damages_recommendations.jsonl"
    out = out_dir / fname
    out.write_text("\n".join(json.dumps(r) for r in recs) + ("\n" if recs else ""),
                   encoding="utf-8")
    print(f"assessed {len(recs)} {key} experts (standard={standard}) -> {out}")
    return 0


def package_analysis(matter_dir: Path) -> int:
    root = matter_dir.expanduser().resolve()
    out_dir = root / "02_outputs"
    liab = out_dir / "expert_liability_recommendations.jsonl"
    dmg = out_dir / "expert_damages_recommendations.jsonl"
    liab_recs = [json.loads(l) for l in liab.read_text(encoding="utf-8").splitlines()] if liab.is_file() else []
    dmg_recs = [json.loads(l) for l in dmg.read_text(encoding="utf-8").splitlines()] if dmg.is_file() else []
    matter_id = _ms.resolve_matter_id(root)
    profile = _matter_profile(root)
    standard = _standard_for(profile)
    lines = [
        f"# Expert Witness Analysis - {matter_id}",
        "",
        "**ATTORNEY REVIEW REQUIRED.** Recommendations are preliminary; the attorney selects, retains, and discloses experts per the scheduling order cutoff.",
        "",
        f"- Jurisdiction standard: `{standard}`",
        f"- Jurisdiction pack: `{profile.get('jurisdiction_pack')}`",
        f"- Case overlay: `{profile.get('case_overlay')}`",
        "",
        "## Liability Experts (E1)",
        "",
    ]
    if not liab_recs:
        lines.append("_No liability experts matched from case facts. Attorney to review._")
    for r in liab_recs:
        lines.append(f"### {r['discipline']} (`{r['expert_id']}`)")
        lines.append(f"- Role: {r['role']}")
        lines.append(f"- Trigger hits: {', '.join(r['trigger_hits'])}")
        lines.append(f"- Admissibility ({r['admissibility_standard']}): {r['admissibility_notes']}")
        lines.append("- Foundation gaps:")
        for g in r["foundation_gaps"]:
            lines.append(f"  - {g}")
        lines.append("- needs_attorney_decision: yes")
        lines.append("")
    lines.append("## Damages Experts (E2)")
    lines.append("")
    if not dmg_recs:
        lines.append("_No damages experts matched from case facts. Attorney to review._")
    for r in dmg_recs:
        lines.append(f"### {r['discipline']} (`{r['expert_id']}`)")
        lines.append(f"- Role: {r['role']}")
        lines.append(f"- Trigger hits: {', '.join(r['trigger_hits'])}")
        lines.append(f"- Admissibility ({r['admissibility_standard']}): {r['admissibility_notes']}")
        lines.append("- Foundation gaps:")
        for g in r["foundation_gaps"]:
            lines.append(f"  - {g}")
        lines.append("- needs_attorney_decision: yes")
        lines.append("")
    lines.extend([
        "## Attorney Review Checklist",
        "",
        "- [ ] Confirm expert disclosure cutoff from the scheduling order",
        "- [ ] Confirm admissibility standard for the trial jurisdiction",
        "- [ ] Retain qualified experts in each recommended discipline",
        "- [ ] Obtain expert CVs and disclosure statements",
        "- [ ] Address each foundation gap before expert forms final opinion",
        "- [ ] No expert report drafted by this skill; attorney/expert owns the report",
        "",
    ])
    out = out_dir / "expert_analysis_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    refresh_casegraph_index(root)
    print(f"wrote expert analysis package -> {out}")
    return 0


def refresh_casegraph_index(root: Path) -> int:
    """Rebuild the casegraph index after writing outputs so validate-analysis
    sees a current index (mirrors rog_request_audit.refresh_casegraph_index)."""
    if not (root / ".casegraph" / "manifest.json").is_file():
        return 0
    return subprocess_run([sys.executable, str(CASEGRAPH), "build", str(root)])


def validate_analysis(matter_dir: Path) -> int:
    root = matter_dir.expanduser().resolve()
    out = root / "02_outputs" / "expert_analysis_report.md"
    if not out.is_file():
        print(f"ERROR: missing {out}; run package-expert-analysis first")
        return 1
    rc = 0
    # The expert report is a recommendation document, not a record-citing
    # discovery response: it intentionally cites no Bates/production locators,
    # so verify-cites uses --allow-empty and check-isolation runs non-strict
    # (FAIL-level cross-matter leakage still fires; label WARNs do not).
    gates = [
        [sys.executable, str(CASEGRAPH), "status", str(root)],
        [sys.executable, str(CASEGRAPH), "verify-cites", str(root), str(out), "--allow-empty"],
        [sys.executable, str(CASEGRAPH), "check-isolation", str(root), str(out)],
    ]
    _ms.append_live_preflight_gate(
        gates,
        root,
        live_preflight_script=LIVE_PREFLIGHT,
        skip_live_preflight=False,
        synthetic_flag=(root / ".synthetic").is_file(),
        request_type=REQUEST_TYPE,
        mode=MODE,
        slice_id=SLICE_ID,
    )
    for cmd in gates:
        print("+", " ".join(cmd))
        code = subprocess_run(cmd)
        if code != 0:
            rc = code
    return rc


def subprocess_run(cmd: list[str]) -> int:
    import subprocess
    return subprocess.run(cmd, text=True, check=False).returncode


def selftest() -> int:
    """Smoke test the taxonomy loader and matcher against synthetic text."""
    taxonomy = _load_taxonomy()
    assert "liability" in taxonomy and "damages" in taxonomy, "taxonomy missing keys"
    text = "train collision at the crossing; FRA hours of service violation; TBI; wage loss"
    liab = _match_experts(text.lower(), taxonomy["liability"])
    dmg = _match_experts(text.lower(), taxonomy["damages"])
    assert any(e["expert"]["id"] == "EXP-L-ACC-RECON" for e in liab), "accident recon should match"
    assert any(e["expert"]["id"] == "EXP-L-REGULATORY" for e in liab), "regulatory should match FRA"
    assert any(e["expert"]["id"] == "EXP-D-NEUROPSYCH" for e in dmg), "neuropsych should match TBI"
    assert any(e["expert"]["id"] == "EXP-D-FORENSIC-ECON" for e in dmg), "forensic econ should match wage loss"
    print("PASS: expert taxonomy selftest")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("parse-case-facts"); p1.add_argument("matter_dir", type=Path)
    p2 = sub.add_parser("assess-liability-experts"); p2.add_argument("matter_dir", type=Path)
    p3 = sub.add_parser("assess-damages-experts"); p3.add_argument("matter_dir", type=Path)
    p4 = sub.add_parser("package-expert-analysis"); p4.add_argument("matter_dir", type=Path)
    p5 = sub.add_parser("validate-expert-analysis"); p5.add_argument("matter_dir", type=Path)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.cmd == "parse-case-facts":
        return parse_case_facts(args.matter_dir)
    if args.cmd == "assess-liability-experts":
        return _assess(args.matter_dir, "E1")
    if args.cmd == "assess-damages-experts":
        return _assess(args.matter_dir, "E2")
    if args.cmd == "package-expert-analysis":
        return package_analysis(args.matter_dir)
    if args.cmd == "validate-expert-analysis":
        return validate_analysis(args.matter_dir)
    if args.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
