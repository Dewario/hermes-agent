#!/usr/bin/env python3
"""Synthetic preparation ladder — L1 baseline, L2 stress, L3 isolation.

Materializes graduated SYN-* matters under TEMP (default), runs counsel-pack
gates, and writes a preparation report. Never touches live client directories.

Hard bans: Allen / Client A / Client B / non-SYN matter IDs / C:\\Matters\\*
except explicit SYN-* rehearsal paths when --allow-matters-synth is set.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCRIPT_PATH = Path(__file__).resolve()
WORKFLOW_SCRIPTS = SCRIPT_PATH.parent
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
FIXTURES = WORKFLOW_ROOT / "fixtures"
LADDER = FIXTURES / "ladder"
SMOKE_SEED = FIXTURES / "smoke_matter" / "seed"
L2_SEED = LADDER / "L2_stress" / "seed"
L3A_SEED = LADDER / "L3_isolation" / "matter_a" / "seed"
L3B_SEED = LADDER / "L3_isolation" / "matter_b" / "seed"
CASEGRAPH = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT = LEGAL_ROOT / "scripts" / "live_preflight.py"

LIVE_ID_BLOCKLIST = re.compile(
    r"(?:^|[/\\_\s-])(allen|client[\s_-]?[ab]|prod-client|live-client)"
    r"(?:[/\\_\s-]|$)",
    re.IGNORECASE,
)
SYN_ID_RE = re.compile(r"^SYN-[A-Z0-9][A-Z0-9_-]*$", re.IGNORECASE)


def _load_main(path: Path, name: str) -> Callable[[list[str] | None], int]:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeError(f"{path} has no callable main()")
    return main  # type: ignore[return-value]


cg_main = _load_main(CASEGRAPH, "ladder_cg")
smoke_main = _load_main(WORKFLOW_SCRIPTS / "smoke_counsel_pack.py", "ladder_smoke")
d1 = _load_main(WORKFLOW_SCRIPTS / "rfp_request_audit.py", "ladder_d1")
d2 = _load_main(WORKFLOW_SCRIPTS / "rfa_request_audit.py", "ladder_d2")
d3 = _load_main(WORKFLOW_SCRIPTS / "rog_request_audit.py", "ladder_d3")
g1 = _load_main(WORKFLOW_SCRIPTS / "trial_gap.py", "ladder_g1")
a2 = _load_main(WORKFLOW_SCRIPTS / "rfa_audit.py", "ladder_a2")
b1 = _load_main(WORKFLOW_SCRIPTS / "rfa_outgoing.py", "ladder_b1")
b2 = _load_main(WORKFLOW_SCRIPTS / "rog_outgoing.py", "ladder_b2")
b3 = _load_main(WORKFLOW_SCRIPTS / "rfp_outgoing.py", "ladder_b3")
c1 = _load_main(WORKFLOW_SCRIPTS / "rfp_response_draft.py", "ladder_c1")
c2 = _load_main(WORKFLOW_SCRIPTS / "rfa_response_draft.py", "ladder_c2")
c3 = _load_main(WORKFLOW_SCRIPTS / "rog_response_draft.py", "ladder_c3")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def refuse_live_path(path: Path, *, allow_matters_synth: bool) -> None:
    text = str(path.resolve())
    if LIVE_ID_BLOCKLIST.search(text):
        raise SystemExit(f"ERROR: refused live-looking path: {path}")
    lowered = text.lower().replace("/", "\\")
    if "\\matters\\" in lowered:
        if not allow_matters_synth:
            raise SystemExit(
                "ERROR: C:\\Matters\\ paths refused by default for preparation. "
                "Use TEMP, or pass --allow-matters-synth only for SYN-* rehearsal dirs."
            )
        name = path.name
        if not SYN_ID_RE.match(name):
            raise SystemExit(
                f"ERROR: Matters path must be SYN-* matter id, got {name!r}"
            )


def materialize(seed: Path, dest: Path, matter_id: str) -> Path:
    if not seed.is_dir():
        raise SystemExit(f"ERROR: missing seed: {seed}")
    if not SYN_ID_RE.match(matter_id):
        raise SystemExit(f"ERROR: matter_id must be SYN-*: {matter_id}")
    if LIVE_ID_BLOCKLIST.search(matter_id):
        raise SystemExit(f"ERROR: refused live-looking matter_id: {matter_id}")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(seed, dest)
    if not (dest / ".synthetic").is_file():
        raise SystemExit(f"ERROR: seed missing .synthetic marker: {seed}")
    return dest.resolve()


def init_casegraph(matter: Path, matter_id: str, bates_prefix: str) -> int:
    code = cg_main([
        "init", str(matter),
        "--matter-id", matter_id,
        "--bates-prefix", bates_prefix,
    ])
    if code != 0:
        return code
    return cg_main(["build", str(matter)])


def run_steps(
    label: str,
    matter: Path,
    steps: list[tuple[str, Callable[[list[str] | None], int], list[str]]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step_label, fn, argv in steps:
        cmd, *rest = argv
        full = [cmd, str(matter), *rest]
        print(f"-- [{label}] {step_label}: {' '.join(full)}")
        code = int(fn(full))
        ok = code == 0
        results.append({"step": step_label, "exit": code, "ok": ok})
        if not ok:
            print(f"FAIL: [{label}] {step_label} exited {code}", file=sys.stderr)
            break
        print(f"PASS: [{label}] {step_label}")
    return results


def clear_ocr_for_rehearsal(matter: Path) -> int:
    """Mirror raw → text and rebuild until OCR queue empty (TEMP rehearsal)."""
    text_dir = matter / "01_production" / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    raw = matter / "01_production" / "raw"
    if raw.is_dir():
        for path in raw.iterdir():
            if path.is_file():
                (text_dir / path.name).write_bytes(path.read_bytes())
    for _ in range(6):
        if cg_main(["build", str(matter)]) != 0:
            return 1
        proc_code = cg_main(["export-ocr-queue", str(matter)])
        if proc_code == 0:
            return 0
        # Mirror any md under 01_* that might help; jsonl is now text-extractable
        for folder in ("01_discovery_served", "01_discovery_proposed", "01_discovery_outgoing"):
            src = matter / folder
            if not src.is_dir():
                continue
            for path in src.rglob("*.md"):
                rel = path.relative_to(matter)
                dest = text_dir / rel.as_posix().replace("/", "__")
                dest.write_bytes(path.read_bytes())
    return 1


def assert_jsonl_flags(path: Path, required: set[str]) -> list[str]:
    """Require every flag in `required` to appear on at least one audit item."""
    if not path.is_file():
        return [f"missing {path}"]
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for flag in row.get("flags") or []:
            seen.add(str(flag))
    missing = sorted(required - seen)
    if missing:
        return [f"{path.name}: missing flags {missing}; saw {sorted(seen)}"]
    return []


def level1_baseline(workspace: Path) -> dict[str, Any]:
    matter = workspace / "L1" / "SYN-SMOKE-COUNSEL"
    print("=== L1 baseline (smoke) ===")
    code = smoke_main(["--matter-dir", str(matter)])
    return {
        "level": "L1",
        "matter_id": "SYN-SMOKE-COUNSEL",
        "path": str(matter),
        "ok": code == 0,
        "exit": code,
        "notes": (
            "Full counsel-pack smoke including C1–C3"
            if code == 0
            else f"smoke exited {code}"
        ),
    }


def level2_stress(workspace: Path) -> dict[str, Any]:
    matter_id = "SYN-LADDER-STRESS"
    matter = materialize(L2_SEED, workspace / "L2" / matter_id, matter_id)
    print(f"=== L2 stress ({matter_id}, ca_ccp) ===")
    if init_casegraph(matter, matter_id, "STRESS-PROD") != 0:
        return {"level": "L2", "matter_id": matter_id, "ok": False, "exit": 1, "notes": "casegraph init failed"}

    steps: list[tuple[str, Callable[[list[str] | None], int], list[str]]] = [
        ("D1 parse", d1, ["parse-served-rfp"]),
        ("D1 audit", d1, ["audit-incoming-rfp"]),
        ("D1 package", d1, ["package-incoming-rfp-audit"]),
        ("D1 validate", d1, ["validate-incoming-rfp-audit"]),
        ("D2 parse", d2, ["parse-served-rfa"]),
        ("D2 audit", d2, ["audit-incoming-rfa"]),
        ("D2 package", d2, ["package-incoming-rfa-audit"]),
        ("D2 validate", d2, ["validate-incoming-rfa-audit"]),
        ("D3 parse", d3, ["parse-served-rog"]),
        ("D3 audit", d3, ["audit-incoming-rog"]),
        ("D3 package", d3, ["package-incoming-rog-audit"]),
        ("D3 validate", d3, ["validate-incoming-rog-audit"]),
        ("G1 parse", g1, ["parse-gap-themes"]),
        ("G1 assess", g1, ["assess-trial-gaps"]),
        ("G1 export", g1, ["export-issue-briefs"]),
        ("G1 package", g1, ["package-trial-gap"]),
        ("G1 validate", g1, ["validate-trial-gap"]),
        (
            "A2 parse served",
            a2,
            ["parse-rfa", "--source", "01_discovery_served/rfa_set_for_response_audit.md"],
        ),
        ("A2 parse proposed", a2, ["parse-proposed-rfa"]),
        ("A2 audit", a2, ["audit-rfa"]),
        ("A2 package", a2, ["package-rfa-audit"]),
        ("A2 validate", a2, ["validate-rfa-audit"]),
        ("B1 parse", b1, ["parse-issue-brief"]),
        ("B1 draft", b1, ["draft-outgoing-rfa"]),
        ("B1 package", b1, ["package-outgoing-rfa"]),
        ("B1 validate", b1, ["validate-outgoing-rfa"]),
        ("B2 parse", b2, ["parse-issue-brief"]),
        ("B2 draft", b2, ["draft-outgoing-rog"]),
        ("B2 package", b2, ["package-outgoing-rog"]),
        ("B2 validate", b2, ["validate-outgoing-rog"]),
        ("B3 parse", b3, ["parse-issue-brief"]),
        ("B3 draft", b3, ["draft-outgoing-rfp"]),
        ("B3 package", b3, ["package-outgoing-rfp"]),
        ("B3 validate", b3, ["validate-outgoing-rfp"]),
        ("C1 parse served", c1, ["parse-served-rfp"]),
        ("C1 parse brief", c1, ["parse-answer-brief"]),
        ("C1 draft", c1, ["draft-rfp-responses"]),
        ("C1 package", c1, ["package-rfp-response-draft"]),
        ("C1 validate", c1, ["validate-rfp-response-draft"]),
        ("C2 parse served", c2, ["parse-served-rfa"]),
        ("C2 parse brief", c2, ["parse-answer-brief"]),
        ("C2 draft", c2, ["draft-rfa-responses"]),
        ("C2 package", c2, ["package-rfa-response-draft"]),
        ("C2 validate", c2, ["validate-rfa-response-draft"]),
        ("C3 parse served", c3, ["parse-served-rog"]),
        ("C3 parse brief", c3, ["parse-answer-brief"]),
        ("C3 draft", c3, ["draft-rog-answers"]),
        ("C3 package", c3, ["package-rog-response-draft"]),
        ("C3 validate", c3, ["validate-rog-response-draft"]),
    ]
    results = run_steps("L2", matter, steps)
    ok = all(r["ok"] for r in results) and len(results) == len(steps)

    expectations: list[str] = []
    if ok:
        expectations.extend(
            assert_jsonl_flags(
                matter / "02_outputs" / "incoming_rfp_request_audit_items.jsonl",
                {"lacks_particularity", "privilege_boundary", "unbounded_temporal_scope"},
            )
        )
        expectations.extend(
            assert_jsonl_flags(
                matter / "02_outputs" / "incoming_rfa_request_audit_items.jsonl",
                {"not_separately_stated", "privilege_boundary", "legal_conclusion"},
            )
        )
        # G1 must still emit at least one open RFP suggestion (notice theme).
        gap_rfp = matter / "01_discovery_outgoing" / "gap_suggested_rfp_issue_brief.md"
        if not gap_rfp.is_file() or "prior notice" not in gap_rfp.read_text(encoding="utf-8").lower():
            expectations.append("G1 export missing open RFP notice suggestion")
        # ca_ccp baselines should populate rule_ids on gap items
        gap_items = matter / "02_outputs" / "trial_gap_items.jsonl"
        if gap_items.is_file():
            empty_rules = 0
            for line in gap_items.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if not row.get("rule_ids"):
                    empty_rules += 1
            if empty_rules:
                expectations.append(f"G1 items with empty rule_ids under ca_ccp: {empty_rules}")
        # OCR-cleared TEMP rehearsal (keeps .synthetic; no skip on export)
        synth = matter / ".synthetic"
        synth_text = synth.read_text(encoding="utf-8") if synth.is_file() else ""
        synth.unlink(missing_ok=True)
        ocr_code = clear_ocr_for_rehearsal(matter)
        package = matter / "02_outputs" / "incoming_rfp_request_audit_report.md"
        gates = [
            [sys.executable, str(CASEGRAPH), "status", str(matter)],
            [
                sys.executable, str(CASEGRAPH), "verify-cites",
                str(matter), str(package), "--allow-empty",
            ],
            [
                sys.executable, str(CASEGRAPH), "check-isolation",
                str(matter), str(package), "--strict",
            ],
            [sys.executable, str(CASEGRAPH), "export-ocr-queue", str(matter)],
            [sys.executable, str(LIVE_PREFLIGHT), "--matter-dir", str(matter)],
        ]
        gate_results = []
        for cmd in gates:
            print("+", " ".join(cmd))
            code = subprocess.run(cmd, text=True, check=False).returncode
            gate_results.append({"cmd": cmd[-1] if cmd else "?", "exit": code, "ok": code == 0})
            if code != 0:
                ok = False
                break
        # restore synthetic marker for leftover workspace inspection
        synth.write_text(synth_text or "SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
        if ocr_code != 0:
            expectations.append("OCR queue did not clear in TEMP rehearsal")
            ok = False
        results.extend({"step": f"live-shaped:{g['cmd']}", **g} for g in gate_results)

    if expectations:
        ok = False
        for err in expectations:
            print(f"FAIL: L2 expectation: {err}", file=sys.stderr)

    return {
        "level": "L2",
        "matter_id": matter_id,
        "path": str(matter),
        "ok": ok,
        "exit": 0 if ok else 1,
        "steps": results,
        "expectation_errors": expectations,
        "notes": "ca_ccp pack; denser D*/C*; TEMP OCR-cleared rehearsal",
    }


def level3_isolation(workspace: Path) -> dict[str, Any]:
    print("=== L3 isolation (ISO-A vs ISO-B) ===")
    a = materialize(L3A_SEED, workspace / "L3" / "SYN-LADDER-ISO-A", "SYN-LADDER-ISO-A")
    b = materialize(L3B_SEED, workspace / "L3" / "SYN-LADDER-ISO-B", "SYN-LADDER-ISO-B")
    if init_casegraph(a, "SYN-LADDER-ISO-A", "THORN-PROD") != 0:
        return {"level": "L3", "ok": False, "exit": 1, "notes": "ISO-A init failed"}
    if init_casegraph(b, "SYN-LADDER-ISO-B", "RIVER-PROD") != 0:
        return {"level": "L3", "ok": False, "exit": 1, "notes": "ISO-B init failed"}

    steps_a = [
        ("D1 parse", d1, ["parse-served-rfp"]),
        ("D1 audit", d1, ["audit-incoming-rfp"]),
        ("D1 package", d1, ["package-incoming-rfp-audit"]),
        ("D1 validate", d1, ["validate-incoming-rfp-audit"]),
    ]
    ra = run_steps("L3-A", a, steps_a)
    rb = run_steps("L3-B", b, steps_a)
    ok = all(r["ok"] for r in ra) and all(r["ok"] for r in rb) and len(ra) == 4 and len(rb) == 4
    errors: list[str] = []
    if ok:
        pkg_a = (a / "02_outputs" / "incoming_rfp_request_audit_report.md").read_text(encoding="utf-8")
        pkg_b = (b / "02_outputs" / "incoming_rfp_request_audit_report.md").read_text(encoding="utf-8")
        if "RIVER-PROD" in pkg_a:
            errors.append("ISO-A package contains RIVER-PROD")
        if "THORN-PROD" in pkg_b:
            errors.append("ISO-B package contains THORN-PROD")
        if "Bravo dock" in pkg_a:
            errors.append("ISO-A package contains Bravo dock facts")
        if "Alpha yard" in pkg_b:
            errors.append("ISO-B package contains Alpha yard facts")
        # strict isolation gate each way
        for matter, pkg in (
            (a, a / "02_outputs" / "incoming_rfp_request_audit_report.md"),
            (b, b / "02_outputs" / "incoming_rfp_request_audit_report.md"),
        ):
            code = subprocess.run(
                [
                    sys.executable, str(CASEGRAPH), "check-isolation",
                    str(matter), str(pkg), "--strict",
                ],
                text=True, check=False,
            ).returncode
            if code != 0:
                errors.append(f"check-isolation failed for {matter.name}")
    if errors:
        ok = False
        for err in errors:
            print(f"FAIL: L3 isolation: {err}", file=sys.stderr)

    return {
        "level": "L3",
        "matter_ids": ["SYN-LADDER-ISO-A", "SYN-LADDER-ISO-B"],
        "paths": [str(a), str(b)],
        "ok": ok,
        "exit": 0 if ok else 1,
        "steps_a": ra,
        "steps_b": rb,
        "isolation_errors": errors,
        "notes": "Cross-matter Bates/fact bleed check",
    }


def write_report(path: Path, levels: list[dict[str, Any]]) -> None:
    lines = [
        "<!-- SYNTHETIC / NON-CLIENT / TEST ONLY -->",
        "",
        "# Synthetic preparation ladder report",
        "",
        f"**Generated:** {utcnow()}",
        "**Live client files engaged:** none",
        "",
        "| Level | Result | Notes |",
        "|-------|--------|-------|",
    ]
    for row in levels:
        mark = "PASS" if row.get("ok") else "FAIL"
        notes = row.get("notes") or ""
        mid = row.get("matter_id") or ", ".join(row.get("matter_ids") or [])
        lines.append(f"| {row.get('level')} ({mid}) | {mark} | {notes} |")
    lines.extend(["", "## Paths", ""])
    for row in levels:
        if row.get("path"):
            lines.append(f"- {row['level']}: `{row['path']}`")
        for p in row.get("paths") or []:
            lines.append(f"- {row['level']}: `{p}`")
    lines.extend([
        "",
        "## Next (owner / live)",
        "",
        "- This report does **not** authorize any real client matter.",
        "- When ready for a live matter, fill `OWNER_LIVE_GATE.md` **outside** the repo",
        "  per matter × request_type × mode, then run live_preflight without `--skip-ocr-queue`.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote report -> {path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--workspace",
        type=Path,
        help="persist ladder matters here (default: TEMP dir)",
    )
    p.add_argument(
        "--report",
        type=Path,
        help="write markdown report path (default: <workspace>/PREPARATION_REPORT.md)",
    )
    p.add_argument(
        "--levels",
        default="L1,L2,L3",
        help="comma list of levels to run (default: L1,L2,L3)",
    )
    p.add_argument(
        "--keep",
        action="store_true",
        help="keep TEMP workspace (print path)",
    )
    p.add_argument(
        "--allow-matters-synth",
        action="store_true",
        help="allow C:\\Matters\\SYN-* rehearsal paths only",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="stop after the first failing level (still writes report)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    levels_wanted = {x.strip().upper() for x in args.levels.split(",") if x.strip()}

    tmp_holder: str | None = None
    if args.workspace is not None:
        workspace = args.workspace.expanduser().resolve()
        refuse_live_path(workspace, allow_matters_synth=bool(args.allow_matters_synth))
        workspace.mkdir(parents=True, exist_ok=True)
    else:
        tmp_holder = tempfile.mkdtemp(prefix="discovery-ladder-")
        workspace = Path(tmp_holder)

    print(f"workspace: {workspace}")
    print("hard ban: no live client files")

    results: list[dict[str, Any]] = []
    try:
        runners: list[tuple[str, Callable[[Path], dict[str, Any]]]] = []
        if "L1" in levels_wanted:
            runners.append(("L1", level1_baseline))
        if "L2" in levels_wanted:
            runners.append(("L2", level2_stress))
        if "L3" in levels_wanted:
            runners.append(("L3", level3_isolation))
        if not runners:
            print("ERROR: no levels selected", file=sys.stderr)
            return 2

        for _label, runner in runners:
            row = runner(workspace)
            results.append(row)
            if args.fail_fast and not row.get("ok"):
                print(f"FAIL-FAST: stopping after {row.get('level')}", file=sys.stderr)
                break

        report = args.report
        if report is None:
            report = workspace / "PREPARATION_REPORT.md"
        else:
            report = report.expanduser().resolve()
            refuse_live_path(report.parent, allow_matters_synth=bool(args.allow_matters_synth))
        write_report(report, results)

        failed = [r for r in results if not r.get("ok")]
        if failed:
            print(f"FAIL: preparation ladder ({len(failed)} level(s))", file=sys.stderr)
            return 1
        print(f"PASS: preparation ladder ({', '.join(r['level'] for r in results)})")
        return 0
    finally:
        if tmp_holder and not args.keep and args.workspace is None:
            shutil.rmtree(tmp_holder, ignore_errors=True)
        elif tmp_holder and args.keep:
            print(f"kept workspace: {workspace}")


if __name__ == "__main__":
    raise SystemExit(main())
