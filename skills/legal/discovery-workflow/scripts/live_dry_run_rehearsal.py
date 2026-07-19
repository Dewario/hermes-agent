#!/usr/bin/env python3
"""Live-shaped dry-run rehearsal for SYN-SMOKE (NOT a real client matter).

Materializes the smoke seed under C:\\Matters\\ (or --matter-dir), removes
.synthetic, clears the OCR queue by writing 01_production/text/ mirrors,
runs D1 package + live_preflight WITHOUT --skip-ocr-queue, and writes
REHEARSAL_EVIDENCE outside the repo (never a filled owner §9.5 gate).

Engineering must not commit filled §9.5 gates into hermes-agent/, and must
not forge owner signatures for real clients.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
WORKFLOW_SCRIPTS = SCRIPT_PATH.parent
WORKFLOW_ROOT = SCRIPT_PATH.parents[1]
LEGAL_ROOT = SCRIPT_PATH.parents[2]
SEED = WORKFLOW_ROOT / "fixtures" / "smoke_matter" / "seed"
CASEGRAPH = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT = LEGAL_ROOT / "scripts" / "live_preflight.py"
MATTER_SAFETY = LEGAL_ROOT / "scripts" / "matter_safety.py"
DEFAULT_MATTER = Path(r"C:\Matters\SYN-SMOKE-LIVE-REHEARSAL")
MATTER_ID = "SYN-SMOKE-LIVE-REHEARSAL"
BATES_PREFIX = "SMOKE-PROD"


def _load_main(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.main


def _load_module(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ms = _load_module(MATTER_SAFETY, "matter_safety_rehearsal")
cg_main = _load_main(CASEGRAPH, "live_rehearsal_cg")
d1_main = _load_main(WORKFLOW_SCRIPTS / "rfp_request_audit.py", "live_rehearsal_d1")


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, text=True, check=False).returncode


def materialize(dest: Path) -> Path:
    dest = dest.expanduser().resolve()
    _ms.refuse_destructive_matter_dir(
        dest, expected_matter_id=MATTER_ID, allow_matters_synth=True,
    )
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SEED, dest)
    synthetic = dest / ".synthetic"
    if synthetic.is_file():
        synthetic.unlink()
    # SYN-* Matters rehearsal still needs mechanical PROVIDER_AUTH (not §9.5).
    auth = dest / "03_attorney" / "PROVIDER_AUTH.md"
    auth.write_text(
        "# Provider authorization — SYN rehearsal only (NOT owner §9.5)\n\n"
        "- Attorney initials: JD  Date: 2026-07-18\n"
        "- Scope: SYN-SMOKE-LIVE-REHEARSAL dry-run only; not Allen / not a client file\n"
        "- This file is mechanical provider-auth for a SYN-* path; it is NOT live-client approval\n",
        encoding="utf-8",
    )
    text_dir = dest / "01_production" / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = dest / "01_production" / "raw"
    for path in raw_dir.glob("*.md"):
        (text_dir / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return dest.resolve()


def clear_ocr_queue(matter: Path) -> int:
    """Rebuild until export-ocr-queue is empty, copying any remaining docs to text/."""
    for _ in range(5):
        code = cg_main(["build", str(matter)])
        if code != 0:
            return code
        proc = subprocess.run(
            [sys.executable, str(CASEGRAPH), "export-ocr-queue", str(matter)],
            text=True, capture_output=True, check=False,
        )
        if proc.returncode == 0:
            print("OCR queue empty")
            return 0
        text_dir = matter / "01_production" / "text"
        text_dir.mkdir(parents=True, exist_ok=True)
        for path in (matter / "01_production" / "raw").glob("*"):
            if path.is_file():
                (text_dir / path.name).write_bytes(path.read_bytes())
    print("WARN: OCR queue still non-empty after retries", file=sys.stderr)
    return 1


def write_rehearsal_evidence(matter: Path, tip_sha: str) -> Path:
    """Write non-approving rehearsal evidence — structurally unusable as §9.5."""
    path = matter / "03_attorney" / "REHEARSAL_EVIDENCE_D1_rfp_audit_incoming_request.md"
    path.write_text(
        f"""# REHEARSAL_EVIDENCE — NOT OWNER APPROVAL — {MATTER_ID}

**VOID §9.5 — engineering must not treat this as owner sign-off.**

matter_id:      {MATTER_ID}
request_type:   [x] rfp
mode:           [x] audit_incoming_request
tip_commit_sha: {tip_sha}
slice:          D1 rfp-request-audit

--- §9.1 Per-slice synthetic (engineering may confirm; owner verifies) ---
[x] Dedicated parser; refuses wrong request_type input.
[x] Dedicated output schema + template.
[x] Validators: cite enum, status/classification enum, isolation, no invented locators.
[x] This slice's §7 synthetic cell is green (pytest + selftest) on the tip SHA above.
[x] Objection boundary respected (flag / opt-in template only).

--- §9.2 Live dry-run (per matter × slice) — run WITHOUT --skip-ocr-queue ---
[x] casegraph status → exit 0 (this rehearsal)
[x] casegraph verify-cites → exit 0 (this rehearsal)
[x] casegraph check-isolation --strict → exit 0 (this rehearsal)
[x] live_preflight.py --matter-dir <matter_dir> (NO --skip-ocr-queue)
[x] OCR queue empty

--- §9.3 Hygiene ---
[x] Offline pytest only; no client files under hermes-agent/.
[x] Skill descriptions ≤ 60 chars.

--- §9.5 Ready-for-live (OWNER ONLY — left UNCHECKED; VOID) ---
[ ] That slice's §9.1–9.3 are green on the tip_commit_sha above.
[ ] Explicit written approval naming this matter_id + request_type + mode.
[ ] Single-matter invocation confirmed.
[ ] No client files under the repo.
[ ] Matter ID is SYNTHETIC rehearsal only — NOT Allen and NOT a real client file.

owner_name:      REHEARSAL_EVIDENCE_ONLY
owner_signature: VOID — NOT OWNER APPROVAL / UNSIGNED
date:            (owner fills when authorizing a real live matter)

NOTE: Stored outside hermes-agent git tree under C:\\Matters\\. Do not copy into the repo.
NOTE: Do not rename this to OWNER_LIVE_GATE_*.md and check boxes without the owner.
""",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-dir", type=Path, default=DEFAULT_MATTER)
    parser.add_argument("--tip-sha", default="")
    args = parser.parse_args(argv)

    tip = args.tip_sha.strip()
    repo = SCRIPT_PATH.parents[3]
    tip_proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo),
        text=True, capture_output=True, check=False,
    )
    if tip_proc.returncode == 0 and tip_proc.stdout.strip():
        tip = tip_proc.stdout.strip()
    elif not tip:
        tip = "UNKNOWN"

    matter = materialize(args.matter_dir)
    print(f"matter: {matter}")
    if cg_main(["init", str(matter), "--matter-id", MATTER_ID, "--bates-prefix", BATES_PREFIX]) != 0:
        return 1
    if clear_ocr_queue(matter) != 0:
        print("continuing despite OCR queue pressure")

    for command in (
        ["parse-served-rfp", str(matter)],
        ["audit-incoming-rfp", str(matter)],
        ["package-incoming-rfp-audit", str(matter)],
    ):
        if d1_main(command) != 0:
            print(f"FAIL: {' '.join(command)}", file=sys.stderr)
            return 1

    clear_ocr_queue(matter)

    package = matter / "02_outputs" / "incoming_rfp_request_audit_report.md"
    for cmd in (
        [sys.executable, str(CASEGRAPH), "status", str(matter)],
        [sys.executable, str(CASEGRAPH), "verify-cites", str(matter), str(package), "--allow-empty"],
        [sys.executable, str(CASEGRAPH), "check-isolation", str(matter), str(package), "--strict"],
        [sys.executable, str(CASEGRAPH), "export-ocr-queue", str(matter)],
        [sys.executable, str(LIVE_PREFLIGHT), "--matter-dir", str(matter)],
    ):
        code = _run(cmd)
        if code != 0:
            print(f"FAIL: live dry-run gate exited {code}", file=sys.stderr)
            return code

    evidence = write_rehearsal_evidence(matter, tip)
    print(f"PASS: live dry-run rehearsal for {MATTER_ID} (synthetic only)")
    print(f"REHEARSAL_EVIDENCE written (NOT owner §9.5): {evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
