#!/usr/bin/env python3
"""Invoke Hermes single-query chat with a prompt file (avoids shell quoting bugs)."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_PROVIDER_AUTH = (
    REPO_ROOT / "skills" / "legal" / "scripts" / "check_provider_auth.py"
)


def _load_provider_auth():
    spec = importlib.util.spec_from_file_location(
        "check_provider_auth", _PROVIDER_AUTH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--max-turns", type=int, default=35)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hermes-bin", default="hermes")
    parser.add_argument(
        "--matter-dir",
        type=Path,
        default=None,
        help="Live matter root — runs PROVIDER_AUTH gate before chat",
    )
    parser.add_argument(
        "--allow-unsigned-provider-auth",
        action="store_true",
        help="Skip PROVIDER_AUTH gate (synthetic / owner override)",
    )
    args = parser.parse_args()

    if args.matter_dir is not None:
        auth = _load_provider_auth()
        code, msg = auth.check_provider_auth(
            args.matter_dir,
            allow_unsigned=args.allow_unsigned_provider_auth,
        )
        if code != 0:
            print(msg, file=sys.stderr)
            return code

    prompt = args.prompt_file.read_text(encoding="utf-8")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        args.hermes_bin,
        "chat",
        "-q",
        prompt,
        "-s",
        args.skill,
        "--max-turns",
        str(args.max_turns),
        "-Q",
    ]

    stdout_path = args.output_dir / "hermes_stdout.txt"
    stderr_path = args.output_dir / "hermes_stderr.txt"

    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open(
        "w", encoding="utf-8"
    ) as err:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            stdout=out,
            stderr=err,
            text=True,
        )

    transcript = args.output_dir / "hermes_transcript.txt"
    transcript.write_text(
        stdout_path.read_text(encoding="utf-8", errors="replace")
        + "\n\n--- stderr ---\n"
        + stderr_path.read_text(encoding="utf-8", errors="replace"),
        encoding="utf-8",
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
