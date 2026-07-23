#!/usr/bin/env python3
"""Run the mandatory readiness gates before live legal matter work."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
CASEGRAPH_SCRIPT = SCRIPTS_DIR.parent / "casegraph" / "scripts" / "casegraph.py"
PROVIDER_AUTH_SCRIPT = SCRIPTS_DIR / "check_provider_auth.py"

_ms_spec = importlib.util.spec_from_file_location(
    "matter_safety_preflight", SCRIPTS_DIR / "matter_safety.py"
)
assert _ms_spec and _ms_spec.loader
_ms = importlib.util.module_from_spec(_ms_spec)
sys.modules["matter_safety_preflight"] = _ms
_ms_spec.loader.exec_module(_ms)


class CommandResult:
    """Captured local command result."""

    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_command(command: list[str]) -> CommandResult:
    """Run a local verification command without passing shell input."""
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _command_label(command: list[str]) -> str:
    return " ".join(command[2:]) if len(command) > 2 else " ".join(command)


def _record(
    results: list[dict[str, str]], name: str, status: str, detail: str
) -> None:
    results.append({"name": name, "status": status, "detail": detail.strip()})


def _run_required(
    results: list[dict[str, str]], name: str, command: list[str]
) -> bool:
    result = run_command(command)
    detail = result.stdout or result.stderr or _command_label(command)
    if result.returncode == 0:
        _record(results, name, "PASS", detail)
        return True
    _record(results, name, "FAIL", detail)
    return False


def run_preflight(
    matter_dir: Path,
    *,
    output: Path | None = None,
    skip_ocr_queue: bool = False,
    request_type: str | None = None,
    mode: str | None = None,
    slice_id: str | None = None,
) -> tuple[int, list[dict[str, str]]]:
    """Run ordered live-matter safety gates and return exit status plus results."""
    root = matter_dir.expanduser().resolve()
    results: list[dict[str, str]] = []
    if not root.is_dir():
        _record(results, "matter directory", "FAIL", f"not found: {root}")
        return 2, results

    try:
        _ms.refuse_skip_ocr_if_live(root, skip_ocr_queue=skip_ocr_queue)
    except SystemExit as exc:
        _record(results, "OCR skip policy", "FAIL", str(exc))
        return 1, results

    gate_ok, gate_detail = _ms.require_owner_live_gate_if_live(
        root,
        expected_matter_id=_ms.resolve_matter_id(root),
        request_type=request_type,
        mode=mode,
        slice_id=slice_id,
    )
    if not gate_ok:
        _record(results, "owner §9.5 live gate", "FAIL", gate_detail)
        return 1, results
    if _ms.is_live_matter_path(root) and not _ms.is_syn_matter_id(_ms.resolve_matter_id(root)):
        _record(results, "owner §9.5 live gate", "PASS", gate_detail)
    else:
        _record(results, "owner §9.5 live gate", "SKIP", gate_detail)

    auth_command = [sys.executable, str(PROVIDER_AUTH_SCRIPT), str(root), "--force"]
    if not _run_required(results, "provider authorization", auth_command):
        return 1, results

    has_casegraph = (root / ".casegraph").is_dir()
    if has_casegraph:
        status_command = [sys.executable, str(CASEGRAPH_SCRIPT), "status", str(root)]
        if not _run_required(results, "casegraph status", status_command):
            return 1, results

        if skip_ocr_queue:
            _record(results, "OCR queue", "SKIP", "skipped by --skip-ocr-queue")
        else:
            queue_command = [
                sys.executable, str(CASEGRAPH_SCRIPT), "export-ocr-queue", str(root),
            ]
            queue = run_command(queue_command)
            detail = queue.stdout or queue.stderr or _command_label(queue_command)
            if queue.returncode == 0:
                _record(results, "OCR queue", "PASS", detail)
            elif queue.returncode == 1:
                _record(results, "OCR queue", "WARN", detail)
            else:
                _record(results, "OCR queue", "FAIL", detail)
                return 1, results
    else:
        _record(results, "casegraph", "SKIP", ".casegraph does not exist")

    if output is not None:
        output_path = output.expanduser().resolve()
        if not output_path.is_file():
            _record(results, "output package", "FAIL", f"not found: {output_path}")
            return 1, results
        if not has_casegraph:
            _record(
                results, "output gates", "FAIL",
                "casegraph must be initialized before checking an output package",
            )
            return 1, results

        gates = [
            (
                "verify cites",
                [sys.executable, str(CASEGRAPH_SCRIPT), "verify-cites", str(root),
                 str(output_path)],
            ),
            (
                "verify chronology",
                [sys.executable, str(CASEGRAPH_SCRIPT), "verify-chronology", str(root),
                 str(output_path), "--strict"],
            ),
        ]
        hermes_home = os.environ.get("HERMES_HOME")
        if not hermes_home:
            try:
                from hermes_constants import get_hermes_home
                hermes_home = str(get_hermes_home())
            except Exception:
                hermes_home = None
        fingerprint_store = (
            Path(hermes_home) / "casegraph" / "fingerprints.json"
            if hermes_home else None
        )
        isolation_command = [
            sys.executable, str(CASEGRAPH_SCRIPT), "check-isolation", str(root),
            str(output_path), "--strict",
        ]
        if fingerprint_store and fingerprint_store.is_file():
            isolation_command.extend(["--fingerprints", str(fingerprint_store)])
        gates.append(("check isolation", isolation_command))

        for name, command in gates:
            if not _run_required(results, name, command):
                return 1, results

    return (1 if any(item["status"] == "WARN" for item in results) else 0), results


def print_summary(results: list[dict[str, str]], as_json: bool) -> None:
    if as_json:
        status = "FAIL" if any(r["status"] == "FAIL" for r in results) else (
            "WARN" if any(r["status"] == "WARN" for r in results) else "PASS"
        )
        print(json.dumps({"status": status, "checks": results}, indent=2))
        return

    print("Live matter preflight:")
    for result in results:
        print(f"[{result['status']}] {result['name']}: {result['detail']}")
    summary = "FAIL" if any(r["status"] == "FAIL" for r in results) else (
        "WARN" if any(r["status"] == "WARN" for r in results) else "PASS"
    )
    print(f"Summary: {summary}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Completed package Markdown path")
    parser.add_argument(
        "--skip-ocr-queue", action="store_true",
        help="Do not block on the casegraph OCR queue",
    )
    parser.add_argument("--request-type", choices=("rog", "rfp", "rfa", "expert"))
    parser.add_argument(
        "--mode",
        choices=(
            "audit_incoming_response",
            "draft_outgoing_request",
            "audit_incoming_request",
            "trial_gap_assessment",
            "draft_response",
            "expert_needs_assessment",
            "enforcement_motion_draft",
            "objection_motion_draft",
        ),
    )
    parser.add_argument(
        "--slice",
        dest="slice_id",
        choices=(
            "A1", "A2", "A3",
            "B1", "B2", "B3",
            "C1", "C2", "C3",
            "D1", "D2", "D3",
            "E1",
            "F1",
            "F2",
            "G1",
        ),
        help="Expected slice id, e.g. D1",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON results")
    args = parser.parse_args(argv)

    code, results = run_preflight(
        args.matter_dir,
        output=args.output,
        skip_ocr_queue=args.skip_ocr_queue,
        request_type=args.request_type,
        mode=args.mode,
        slice_id=args.slice_id,
    )
    print_summary(results, args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
