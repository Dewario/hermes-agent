#!/usr/bin/env python3
"""Umbrella dispatcher for discovery-workflow slices (SPEC §8).

Routes by (--request-type, --mode) to the dedicated slice module. Does not
reimplement parsers. Live use still requires owner §9.5 per matter × type × mode.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Callable


SCRIPT_PATH = Path(__file__).resolve()
WORKFLOW_SCRIPTS = SCRIPT_PATH.parent
LEGAL_ROOT = SCRIPT_PATH.parents[2]
DISCOVERY_RESPONSE = LEGAL_ROOT / "discovery-response" / "scripts" / "discovery_response.py"

# (request_type, mode) → slice script
DISPATCH: dict[tuple[str, str], Path] = {
    ("rfp", "audit_incoming_response"): DISCOVERY_RESPONSE,
    ("rfa", "audit_incoming_response"): WORKFLOW_SCRIPTS / "rfa_audit.py",
    ("rog", "audit_incoming_response"): WORKFLOW_SCRIPTS / "rog_audit.py",
    ("rfa", "draft_outgoing_request"): WORKFLOW_SCRIPTS / "rfa_outgoing.py",
    ("rog", "draft_outgoing_request"): WORKFLOW_SCRIPTS / "rog_outgoing.py",
    ("rfp", "draft_outgoing_request"): WORKFLOW_SCRIPTS / "rfp_outgoing.py",
    ("rfp", "audit_incoming_request"): WORKFLOW_SCRIPTS / "rfp_request_audit.py",
    ("rfa", "audit_incoming_request"): WORKFLOW_SCRIPTS / "rfa_request_audit.py",
    ("rog", "audit_incoming_request"): WORKFLOW_SCRIPTS / "rog_request_audit.py",
    # G1 is multi-type; any request_type routes to the same orchestrator.
    ("rfp", "trial_gap_assessment"): WORKFLOW_SCRIPTS / "trial_gap.py",
    ("rfa", "trial_gap_assessment"): WORKFLOW_SCRIPTS / "trial_gap.py",
    ("rog", "trial_gap_assessment"): WORKFLOW_SCRIPTS / "trial_gap.py",
}

SLICE_SELFTESTS: list[tuple[str, Path]] = [
    ("A1 rfp/audit", DISCOVERY_RESPONSE),
    ("A2 rfa/audit", WORKFLOW_SCRIPTS / "rfa_audit.py"),
    ("A3 rog/audit", WORKFLOW_SCRIPTS / "rog_audit.py"),
    ("B1 rfa/draft", WORKFLOW_SCRIPTS / "rfa_outgoing.py"),
    ("B2 rog/draft", WORKFLOW_SCRIPTS / "rog_outgoing.py"),
    ("B3 rfp/draft", WORKFLOW_SCRIPTS / "rfp_outgoing.py"),
    ("D1 rfp/request-audit", WORKFLOW_SCRIPTS / "rfp_request_audit.py"),
    ("D2 rfa/request-audit", WORKFLOW_SCRIPTS / "rfa_request_audit.py"),
    ("D3 rog/request-audit", WORKFLOW_SCRIPTS / "rog_request_audit.py"),
    ("G1 trial-gap", WORKFLOW_SCRIPTS / "trial_gap.py"),
]

# Commands that do not take a matter_dir positional
_NO_MATTER_COMMANDS = frozenset({"selftest", "selftest-all", "help"})


def _load_main(path: Path) -> Callable[[list[str] | None], int]:
    if not path.is_file():
        raise FileNotFoundError(f"slice script missing: {path}")
    name = f"dw_slice_{path.stem}_{abs(hash(str(path))) & 0xFFFF:x}"
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


def resolve_slice(request_type: str, mode: str) -> Path:
    key = (request_type.lower(), mode.lower())
    if mode.lower() == "draft_response":
        raise SystemExit(
            "ERROR: mode 'draft_response' is not implemented (SPEC C* deferred)."
        )
    if mode.lower() == "audit_incoming_request" and request_type.lower() not in {
        "rfp", "rfa", "rog",
    }:
        raise SystemExit(
            "ERROR: audit_incoming_request is implemented for rfp (D1), rfa (D2), "
            "and rog (D3) only."
        )
    if mode.lower() == "trial_gap_assessment":
        return WORKFLOW_SCRIPTS / "trial_gap.py"
    path = DISPATCH.get(key)
    if path is None:
        known = ", ".join(f"{t}/{m}" for t, m in sorted(DISPATCH))
        raise SystemExit(
            f"ERROR: no slice for request_type={request_type!r} mode={mode!r}. "
            f"Known: {known}"
        )
    return path


def forward(path: Path, argv: list[str]) -> int:
    main = _load_main(path)
    return int(main(argv))


def cmd_selftest_all() -> int:
    failed = 0
    for label, path in SLICE_SELFTESTS:
        print(f"=== selftest {label} ({path.name}) ===")
        code = forward(path, ["selftest"])
        if code != 0:
            print(f"FAIL: {label} exited {code}", file=sys.stderr)
            failed += 1
        else:
            print(f"PASS: {label}")
    if failed:
        print(f"FAIL: selftest-all ({failed} slice(s) failed)", file=sys.stderr)
        return 1
    print(f"PASS: discovery-workflow selftest-all ({len(SLICE_SELFTESTS)}/{len(SLICE_SELFTESTS)})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  discovery_workflow.py --request-type rfa --mode audit_incoming_response "
            "parse-rfa C:\\Matters\\X\n"
            "  discovery_workflow.py --matter-dir C:\\Matters\\X --request-type rfa "
            "--mode draft_outgoing_request parse-issue-brief\n"
            "  discovery_workflow.py selftest-all\n"
        ),
    )
    parser.add_argument("--matter-dir", type=Path, help="matter directory (injected if omitted from subcommand)")
    parser.add_argument("--request-type", choices=("rog", "rfp", "rfa"))
    parser.add_argument(
        "--mode",
        choices=(
            "audit_incoming_response",
            "draft_outgoing_request",
            "audit_incoming_request",
            "trial_gap_assessment",
            "draft_response",
        ),
    )
    parser.add_argument(
        "command",
        help="slice subcommand (parse-*, audit-*, package-*, validate-*, selftest) or selftest-all",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER, help="forwarded to the slice script")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    forwarded = list(args.args or [])
    # argparse REMAINDER keeps a leading "--" sometimes
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    if command in {"selftest-all", "matrix"}:
        return cmd_selftest_all()

    if not args.mode:
        print(
            "ERROR: --mode is required (except selftest-all).",
            file=sys.stderr,
        )
        return 2
    # G1 is multi-type; request_type optional (defaults to rfp for dispatch keying).
    request_type = args.request_type
    if args.mode == "trial_gap_assessment" and not request_type:
        request_type = "rfp"
    if not request_type:
        print(
            "ERROR: --request-type and --mode are required (except selftest-all; "
            "trial_gap_assessment may omit --request-type).",
            file=sys.stderr,
        )
        return 2

    try:
        path = resolve_slice(request_type, args.mode)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    slice_argv = [command, *forwarded]
    if (
        command not in _NO_MATTER_COMMANDS
        and args.matter_dir is not None
        and (not forwarded or not Path(str(forwarded[0])).exists())
    ):
        # Inject matter_dir as first positional after the subcommand.
        slice_argv = [command, str(args.matter_dir.expanduser()), *forwarded]

    if command == "selftest":
        slice_argv = ["selftest"]

    return forward(path, slice_argv)


if __name__ == "__main__":
    raise SystemExit(main())
