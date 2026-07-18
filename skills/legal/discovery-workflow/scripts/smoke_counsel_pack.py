#!/usr/bin/env python3
"""Counsel-pack synthetic smoke: one matter × D1–D3 + G1 + A2 + B1–B3 + C1–C3.

Materializes fixtures/smoke_matter/seed into a temp (or --matter-dir) workspace,
indexes casegraph, and runs validate gates. Synthetic-only — not §9.5 live.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable


SCRIPT_PATH = Path(__file__).resolve()
WORKFLOW_SCRIPTS = SCRIPT_PATH.parent
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
SEED_DIR = WORKFLOW_ROOT / "fixtures" / "smoke_matter" / "seed"
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"

MATTER_ID = "SYN-SMOKE-COUNSEL"
BATES_PREFIX = "SMOKE-PROD"


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


cg_main = _load_main(CASEGRAPH_SCRIPT, "smoke_casegraph")
d1 = _load_main(WORKFLOW_SCRIPTS / "rfp_request_audit.py", "smoke_d1")
d2 = _load_main(WORKFLOW_SCRIPTS / "rfa_request_audit.py", "smoke_d2")
d3 = _load_main(WORKFLOW_SCRIPTS / "rog_request_audit.py", "smoke_d3")
g1 = _load_main(WORKFLOW_SCRIPTS / "trial_gap.py", "smoke_g1")
a2 = _load_main(WORKFLOW_SCRIPTS / "rfa_audit.py", "smoke_a2")
b1 = _load_main(WORKFLOW_SCRIPTS / "rfa_outgoing.py", "smoke_b1")
b2 = _load_main(WORKFLOW_SCRIPTS / "rog_outgoing.py", "smoke_b2")
b3 = _load_main(WORKFLOW_SCRIPTS / "rfp_outgoing.py", "smoke_b3")
c1 = _load_main(WORKFLOW_SCRIPTS / "rfp_response_draft.py", "smoke_c1")
c2 = _load_main(WORKFLOW_SCRIPTS / "rfa_response_draft.py", "smoke_c2")
c3 = _load_main(WORKFLOW_SCRIPTS / "rog_response_draft.py", "smoke_c3")


STEPS: list[tuple[str, Callable[[list[str] | None], int], list[str]]] = [
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
    ("G1 parse themes", g1, ["parse-gap-themes"]),
    ("G1 assess", g1, ["assess-trial-gaps"]),
    ("G1 export briefs", g1, ["export-issue-briefs"]),
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
    ("B1 parse brief", b1, ["parse-issue-brief"]),
    ("B1 draft", b1, ["draft-outgoing-rfa"]),
    ("B1 package", b1, ["package-outgoing-rfa"]),
    ("B1 validate", b1, ["validate-outgoing-rfa"]),
    ("B2 parse brief", b2, ["parse-issue-brief"]),
    ("B2 draft", b2, ["draft-outgoing-rog"]),
    ("B2 package", b2, ["package-outgoing-rog"]),
    ("B2 validate", b2, ["validate-outgoing-rog"]),
    ("B3 parse brief", b3, ["parse-issue-brief"]),
    ("B3 draft", b3, ["draft-outgoing-rfp"]),
    ("B3 package", b3, ["package-outgoing-rfp"]),
    ("B3 validate", b3, ["validate-outgoing-rfp"]),
    ("C1 parse served", c1, ["parse-served-rfp"]),
    ("C1 parse brief", c1, ["parse-answer-brief"]),
    ("C1 draft", c1, ["draft-rfp-responses"]),
    ("C1 package", c1, ["package-rfp-response-draft"]),
    ("C1 validate", c1, ["validate-rfp-response-draft"]),
    (
        "C2 parse served",
        c2,
        ["parse-served-rfa", "--source", "01_discovery_served/rfa_set_for_response_audit.md"],
    ),
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


REQUIRED_SEED = [
    ".synthetic",
    "03_attorney/matter_profile.yaml",
    "03_attorney/PROVIDER_AUTH.md",
    "01_discovery_served/rfp_set.md",
    "01_discovery_served/rfa_set.md",
    "01_discovery_served/rog_set.md",
    "01_discovery_served/rfa_set_for_response_audit.md",
    "01_discovery_proposed/proposed_rfa_responses.md",
    "01_discovery_proposed/rfp_answer_brief.md",
    "01_discovery_proposed/rfa_answer_brief.md",
    "01_discovery_proposed/rog_answer_brief.md",
    "01_discovery_outgoing/gap_themes.md",
    "01_discovery_outgoing/rfp_issue_brief.md",
    "01_discovery_outgoing/rog_issue_brief.md",
    "01_discovery_outgoing/rfa_issue_brief.md",
    "01_production/raw/SMOKE-PROD-000010.md",
    "01_production/raw/SMOKE-PROD-000020.md",
    "01_production/raw/SMOKE-PROD-000030.md",
]


def materialize_matter(dest: Path) -> Path:
    if not SEED_DIR.is_dir():
        raise SystemExit(f"ERROR: smoke seed missing: {SEED_DIR}")
    missing = [rel for rel in REQUIRED_SEED if not (SEED_DIR / rel).is_file()]
    if missing:
        raise SystemExit(f"ERROR: smoke seed incomplete: {', '.join(missing)}")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SEED_DIR, dest)
    return dest.resolve()


def init_casegraph(matter: Path) -> int:
    code = cg_main([
        "init", str(matter),
        "--matter-id", MATTER_ID,
        "--bates-prefix", BATES_PREFIX,
    ])
    if code != 0:
        return code
    return cg_main(["build", str(matter)])


def _inject_matter(argv: list[str], matter: Path) -> list[str]:
    """Insert matter_dir after subcommand; keep flags after."""
    if not argv:
        return argv
    cmd, *rest = argv
    # Flags that take a value may appear before matter_dir in some CLIs;
    # our convention: subcommand, then matter_dir, then remaining args.
    return [cmd, str(matter), *rest]


def run_smoke(matter: Path) -> int:
    print(f"=== counsel-pack smoke matter: {matter} ===")
    code = init_casegraph(matter)
    if code != 0:
        print(f"FAIL: casegraph init/build exited {code}", file=sys.stderr)
        return code
    failed = 0
    for label, fn, argv in STEPS:
        full = _inject_matter(list(argv), matter)
        print(f"-- {label}: {' '.join(full)}")
        code = fn(full)
        if code != 0:
            print(f"FAIL: {label} exited {code}", file=sys.stderr)
            failed += 1
            break
        print(f"PASS: {label}")
    if failed:
        print(f"FAIL: counsel-pack smoke ({failed} step failure)", file=sys.stderr)
        return 1
    # Spot-check key artifacts exist
    expected = [
        "02_outputs/incoming_rfp_request_audit_report.md",
        "02_outputs/incoming_rfa_request_audit_report.md",
        "02_outputs/incoming_rog_request_audit_report.md",
        "02_outputs/trial_gap_report.md",
        "02_outputs/rfa_response_audit_report.md",
        "02_outputs/outgoing_rfa_set.md",
        "02_outputs/outgoing_rog_set.md",
        "02_outputs/outgoing_rfp_set.md",
        "02_outputs/draft_rfp_responses.md",
        "02_outputs/draft_rfa_responses.md",
        "02_outputs/draft_rog_answers.md",
        "01_discovery_outgoing/gap_suggested_rfp_issue_brief.md",
    ]
    for rel in expected:
        path = matter / rel
        if not path.is_file() or path.stat().st_size < 32:
            print(f"FAIL: missing/empty artifact {rel}", file=sys.stderr)
            return 1
    print(f"PASS: counsel-pack smoke ({len(STEPS)} steps, matter {MATTER_ID})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--matter-dir",
        type=Path,
        help="persist smoke matter here (default: temp dir cleaned on exit)",
    )
    p.add_argument(
        "--keep-temp",
        action="store_true",
        help="when using temp dir, print path and do not delete (debug)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.matter_dir is not None:
        matter = materialize_matter(args.matter_dir.expanduser().resolve())
        return run_smoke(matter)

    tmp = tempfile.mkdtemp(prefix="counsel-pack-smoke-")
    matter = materialize_matter(Path(tmp) / MATTER_ID)
    try:
        code = run_smoke(matter)
    finally:
        if args.keep_temp:
            print(f"kept smoke matter at: {matter}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
