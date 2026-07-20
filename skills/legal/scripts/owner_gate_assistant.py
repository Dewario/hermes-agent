#!/usr/bin/env python3
"""Build a deterministic owner-review packet for discovery-workflow 9.5.

This tool helps the owner review a live-matter gate. It does not approve,
sign, or write OWNER_LIVE_GATE_*.md files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
LEGAL_ROOT = SCRIPT.parent.parent
REPO_ROOT = SCRIPT.parents[3]
WORKFLOW_SCRIPTS = LEGAL_ROOT / "discovery-workflow" / "scripts"
DISCOVERY_RESPONSE = LEGAL_ROOT / "discovery-response" / "scripts" / "discovery_response.py"
CASEGRAPH_SCRIPT = LEGAL_ROOT / "casegraph" / "scripts" / "casegraph.py"
LIVE_PREFLIGHT_SCRIPT = LEGAL_ROOT / "scripts" / "live_preflight.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ms = _load_module(SCRIPT.parent / "matter_safety.py", "matter_safety_gate_assistant")
_auth = _load_module(SCRIPT.parent / "check_provider_auth.py", "provider_auth_gate_assistant")


SLICE: dict[tuple[str, str], dict[str, Any]] = {
    ("rfp", "audit_incoming_response"): {
        "id": "A1",
        "label": "RFP response audit",
        "selftest": DISCOVERY_RESPONSE,
        "package": Path("02_outputs") / "response_audit_report.md",
        "allow_empty_cites": False,
    },
    ("rfa", "audit_incoming_response"): {
        "id": "A2",
        "label": "RFA response audit",
        "selftest": WORKFLOW_SCRIPTS / "rfa_audit.py",
        "package": Path("02_outputs") / "rfa_response_audit_report.md",
        "allow_empty_cites": False,
    },
    ("rog", "audit_incoming_response"): {
        "id": "A3",
        "label": "ROG answer audit",
        "selftest": WORKFLOW_SCRIPTS / "rog_audit.py",
        "package": Path("02_outputs") / "rog_response_audit_report.md",
        "allow_empty_cites": False,
    },
    ("rfa", "draft_outgoing_request"): {
        "id": "B1",
        "label": "Outgoing RFA draft",
        "selftest": WORKFLOW_SCRIPTS / "rfa_outgoing.py",
        "package": Path("02_outputs") / "outgoing_rfa_set.md",
        "allow_empty_cites": True,
    },
    ("rog", "draft_outgoing_request"): {
        "id": "B2",
        "label": "Outgoing ROG draft",
        "selftest": WORKFLOW_SCRIPTS / "rog_outgoing.py",
        "package": Path("02_outputs") / "outgoing_rog_set.md",
        "allow_empty_cites": True,
    },
    ("rfp", "draft_outgoing_request"): {
        "id": "B3",
        "label": "Outgoing RFP draft",
        "selftest": WORKFLOW_SCRIPTS / "rfp_outgoing.py",
        "package": Path("02_outputs") / "outgoing_rfp_set.md",
        "allow_empty_cites": True,
    },
    ("rfp", "audit_incoming_request"): {
        "id": "D1",
        "label": "Incoming RFP request audit",
        "selftest": WORKFLOW_SCRIPTS / "rfp_request_audit.py",
        "package": Path("02_outputs") / "incoming_rfp_request_audit_report.md",
        "allow_empty_cites": False,
    },
    ("rfa", "audit_incoming_request"): {
        "id": "D2",
        "label": "Incoming RFA request audit",
        "selftest": WORKFLOW_SCRIPTS / "rfa_request_audit.py",
        "package": Path("02_outputs") / "incoming_rfa_request_audit_report.md",
        "allow_empty_cites": False,
    },
    ("rog", "audit_incoming_request"): {
        "id": "D3",
        "label": "Incoming ROG request audit",
        "selftest": WORKFLOW_SCRIPTS / "rog_request_audit.py",
        "package": Path("02_outputs") / "incoming_rog_request_audit_report.md",
        "allow_empty_cites": False,
    },
    ("rfp", "trial_gap_assessment"): {
        "id": "G1",
        "label": "Trial gap assessment",
        "selftest": WORKFLOW_SCRIPTS / "trial_gap.py",
        "package": Path("02_outputs") / "trial_gap_report.md",
        "allow_empty_cites": False,
    },
    ("rfa", "trial_gap_assessment"): {
        "id": "G1",
        "label": "Trial gap assessment",
        "selftest": WORKFLOW_SCRIPTS / "trial_gap.py",
        "package": Path("02_outputs") / "trial_gap_report.md",
        "allow_empty_cites": False,
    },
    ("rog", "trial_gap_assessment"): {
        "id": "G1",
        "label": "Trial gap assessment",
        "selftest": WORKFLOW_SCRIPTS / "trial_gap.py",
        "package": Path("02_outputs") / "trial_gap_report.md",
        "allow_empty_cites": False,
    },
    ("expert", "expert_needs_assessment"): {
        "id": "E1",
        "label": "Expert needs assessment",
        "selftest": WORKFLOW_SCRIPTS / "expert_needs.py",
        "package": Path("02_outputs") / "expert_needs_assessment.md",
        "allow_empty_cites": True,
    },
    ("rfp", "draft_response"): {
        "id": "C1",
        "label": "Draft RFP responses",
        "selftest": WORKFLOW_SCRIPTS / "rfp_response_draft.py",
        "package": Path("02_outputs") / "draft_rfp_responses.md",
        "allow_empty_cites": True,
    },
    ("rfa", "draft_response"): {
        "id": "C2",
        "label": "Draft RFA responses",
        "selftest": WORKFLOW_SCRIPTS / "rfa_response_draft.py",
        "package": Path("02_outputs") / "draft_rfa_responses.md",
        "allow_empty_cites": True,
    },
    ("rog", "draft_response"): {
        "id": "C3",
        "label": "Draft ROG answers",
        "selftest": WORKFLOW_SCRIPTS / "rog_response_draft.py",
        "package": Path("02_outputs") / "draft_rog_answers.md",
        "allow_empty_cites": True,
    },
}


class CommandResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_command(command: list[str], *, cwd: Path | None = None) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _command_text(command: list[str]) -> str:
    return " ".join(command)


def _status_from_code(code: int) -> str:
    return "PASS" if code == 0 else "FAIL"


def _record(
    checks: list[dict[str, Any]],
    name: str,
    status: str,
    detail: str,
    command: list[str] | None = None,
) -> None:
    item: dict[str, Any] = {"name": name, "status": status, "detail": detail.strip()}
    if command is not None:
        item["command"] = command
    checks.append(item)


def _safe_detail(result: CommandResult) -> str:
    text = (result.stdout or result.stderr or "").strip()
    return text[-4000:] if text else f"exit {result.returncode}"


def git_head() -> str:
    result = run_command(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def resolve_slice(request_type: str, mode: str) -> dict[str, Any]:
    try:
        return SLICE[(request_type, mode)]
    except KeyError as exc:
        known = ", ".join(f"{t}/{m}" for t, m in sorted(SLICE))
        raise SystemExit(f"ERROR: unsupported request_type/mode. Known: {known}") from exc


def default_packet_path(matter_dir: Path, spec: dict[str, Any], request_type: str, mode: str) -> Path:
    filename = f"GATE_REVIEW_PACKET_{spec['id']}_{request_type}_{mode}.md"
    return matter_dir / "03_attorney" / filename


def _refuse_matching_owner_gate_filename(path: Path) -> None:
    if path.name.upper().startswith("OWNER_LIVE_GATE"):
        raise SystemExit(
            "ERROR: assistant packets must not be named OWNER_LIVE_GATE*.md. "
            "Use GATE_REVIEW_PACKET_<slice>.md."
        )


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_and_record(
    checks: list[dict[str, Any]],
    name: str,
    command: list[str],
    *,
    cwd: Path | None = None,
) -> bool:
    result = run_command(command, cwd=cwd)
    _record(checks, name, _status_from_code(result.returncode), _safe_detail(result), command)
    return result.returncode == 0


def collect_evidence(
    matter_dir: Path,
    *,
    request_type: str,
    mode: str,
    package_output: Path | None,
    run_synthetic_selftest: bool,
) -> dict[str, Any]:
    root = matter_dir.expanduser().resolve()
    spec = resolve_slice(request_type, mode)
    matter_id = _ms.resolve_matter_id(root)
    package_path = (
        package_output.expanduser().resolve()
        if package_output is not None
        else (root / spec["package"]).resolve()
    )

    checks: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matter_dir": str(root),
        "matter_id": matter_id,
        "request_type": request_type,
        "mode": mode,
        "slice": spec["id"],
        "slice_label": spec["label"],
        "tip_commit_sha": git_head(),
        "package_output": str(package_path),
        "checks": checks,
    }

    if not root.is_dir():
        _record(checks, "matter directory", "FAIL", f"not found: {root}")
        payload["ready_for_owner_review"] = False
        return payload

    gate_ok, gate_detail = _ms.owner_live_gate_satisfied(
        root,
        expected_matter_id=matter_id,
        request_type=request_type,
        mode=mode,
        slice_id=spec["id"],
    )
    _record(
        checks,
        "current owner gate",
        "PASS" if gate_ok else "OPEN",
        gate_detail,
    )

    auth_code, auth_msg = _auth.check_provider_auth(root, force=True)
    _record(
        checks,
        "provider authorization",
        "PASS" if auth_code == 0 else "FAIL",
        auth_msg,
        [sys.executable, str(SCRIPT.parent / "check_provider_auth.py"), str(root), "--force"],
    )
    if auth_code != 0:
        _record(
            checks,
            "matter command battery",
            "SKIP",
            "provider authorization failed; assistant did not inspect matter text",
        )
        payload["ready_for_owner_review"] = False
        return payload

    if run_synthetic_selftest:
        _run_and_record(
            checks,
            "synthetic slice selftest",
            [sys.executable, str(spec["selftest"]), "selftest"],
        )
    else:
        _record(checks, "synthetic slice selftest", "SKIP", "skipped by flag")

    _run_and_record(
        checks,
        "git diff --check",
        ["git", "diff", "--check"],
        cwd=REPO_ROOT,
    )
    _run_and_record(
        checks,
        "casegraph status",
        [sys.executable, str(CASEGRAPH_SCRIPT), "status", str(root)],
    )

    queue = run_command(
        [sys.executable, str(CASEGRAPH_SCRIPT), "export-ocr-queue", str(root)]
    )
    queue_status = "PASS" if queue.returncode == 0 else "FAIL"
    _record(
        checks,
        "OCR queue empty",
        queue_status,
        _safe_detail(queue),
        [sys.executable, str(CASEGRAPH_SCRIPT), "export-ocr-queue", str(root)],
    )

    if not package_path.is_file():
        _record(checks, "package output", "FAIL", f"not found: {package_path}")
    else:
        _record(checks, "package output", "PASS", str(package_path))
        verify_cmd = [
            sys.executable,
            str(CASEGRAPH_SCRIPT),
            "verify-cites",
            str(root),
            str(package_path),
        ]
        if spec["allow_empty_cites"]:
            verify_cmd.append("--allow-empty")
        _run_and_record(checks, "verify cites", verify_cmd)
        if spec["allow_empty_cites"]:
            _record(
                checks,
                "verify chronology",
                "SKIP",
                "slice validator permits empty cites; full preflight omits --output for this mode",
            )
        else:
            _run_and_record(
                checks,
                "verify chronology",
                [
                    sys.executable,
                    str(CASEGRAPH_SCRIPT),
                    "verify-chronology",
                    str(root),
                    str(package_path),
                    "--strict",
                ],
            )
        _run_and_record(
            checks,
            "check isolation",
            [
                sys.executable,
                str(CASEGRAPH_SCRIPT),
                "check-isolation",
                str(root),
                str(package_path),
                "--strict",
            ],
        )
        preflight_cmd = [
            sys.executable,
            str(LIVE_PREFLIGHT_SCRIPT),
            "--matter-dir",
            str(root),
            "--request-type",
            request_type,
            "--mode",
            mode,
            "--slice",
            str(spec["id"]),
        ]
        if not spec["allow_empty_cites"]:
            preflight_cmd.extend(["--output", str(package_path)])
        if gate_ok:
            _run_and_record(checks, "full live preflight", preflight_cmd)
        else:
            _record(
                checks,
                "full live preflight",
                "SKIP",
                "owner gate is open; run this after OWNER_LIVE_GATE_<slice>.md is signed",
                preflight_cmd,
            )

    blocking = [c for c in checks if c["status"] == "FAIL"]
    payload["ready_for_owner_review"] = not blocking
    return payload


def render_packet(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    lines = [
        f"# Gate Review Packet - {payload['slice']} {payload['request_type']} / {payload['mode']}",
        "",
        "**Packet only. Not owner approval. Do not rename this file to OWNER_LIVE_GATE_*.md.**",
        "",
        "## Identity",
        "",
        f"- Matter ID: {payload['matter_id']}",
        f"- Matter dir: `{payload['matter_dir']}`",
        f"- Slice: {payload['slice']} - {payload['slice_label']}",
        f"- Request type: `{payload['request_type']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Tip commit SHA: `{payload['tip_commit_sha']}`",
        f"- Package output: `{payload['package_output']}`",
        "",
        "## Mechanical Checks",
        "",
        "| Status | Check | Detail |",
        "|---|---|---|",
    ]
    for check in checks:
        detail = check["detail"].replace("\n", "<br>")
        lines.append(f"| {check['status']} | {check['name']} | {detail} |")

    lines.extend([
        "",
        "## Commands",
        "",
    ])
    any_command = False
    for check in checks:
        command = check.get("command")
        if command:
            any_command = True
            lines.append(f"- `{_command_text(command)}`")
    if not any_command:
        lines.append("- No commands ran.")

    ready = "yes" if payload.get("ready_for_owner_review") else "no"
    lines.extend([
        "",
        "## Owner Review Draft",
        "",
        f"- Mechanically ready for owner review: {ready}",
        "- This packet may support owner review of 9.1-9.3.",
        "- Full live_preflight remains required after the owner gate is signed.",
        "- The 9.5 approval lines below are intentionally unchecked.",
        "",
        "--- 9.5 Ready-for-live (OWNER ONLY - packet leaves this open) ---",
        "[ ] That slice's 9.1-9.3 are green on the tip_commit_sha above.",
        "[ ] Explicit written approval naming this matter_id + request_type + mode.",
        "[ ] Single-matter invocation confirmed.",
        "[ ] No client files under the repo.",
        "",
        "owner_name:",
        "owner_signature:",
        "date:",
        "",
        "To approve, the owner must create a separate canonical file named "
        f"`OWNER_LIVE_GATE_{payload['slice']}.md` in the matter attorney folder.",
    ])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matter-dir", required=True, type=Path)
    parser.add_argument("--request-type", required=True, choices=("rog", "rfp", "rfa", "expert"))
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "audit_incoming_response",
            "draft_outgoing_request",
            "audit_incoming_request",
            "trial_gap_assessment",
            "expert_needs_assessment",
            "draft_response",
        ),
    )
    parser.add_argument(
        "--package-output",
        type=Path,
        help="slice output package to verify; defaults to the known package path",
    )
    parser.add_argument(
        "--packet-output",
        type=Path,
        help="review packet path; defaults under 03_attorney/GATE_REVIEW_PACKET_*.md",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="JSON evidence path; defaults beside the packet",
    )
    parser.add_argument(
        "--skip-synthetic-selftest",
        action="store_true",
        help="do not re-run the selected slice selftest",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.matter_dir.expanduser().resolve()
    spec = resolve_slice(args.request_type, args.mode)
    packet = (
        args.packet_output.expanduser().resolve()
        if args.packet_output
        else default_packet_path(root, spec, args.request_type, args.mode).resolve()
    )
    _refuse_matching_owner_gate_filename(packet)
    if _is_under(packet, REPO_ROOT):
        raise SystemExit("ERROR: write gate review packets outside hermes-agent/")

    payload = collect_evidence(
        root,
        request_type=args.request_type,
        mode=args.mode,
        package_output=args.package_output,
        run_synthetic_selftest=not args.skip_synthetic_selftest,
    )
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(render_packet(payload), encoding="utf-8", newline="\n")

    json_path = (
        args.json_output.expanduser().resolve()
        if args.json_output
        else packet.with_suffix(".json")
    )
    if _is_under(json_path, REPO_ROOT):
        raise SystemExit("ERROR: write gate review JSON outside hermes-agent/")
    _write_json(json_path, payload)

    print(f"wrote gate review packet -> {packet}")
    print(f"wrote gate review json -> {json_path}")
    return 0 if payload.get("ready_for_owner_review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
