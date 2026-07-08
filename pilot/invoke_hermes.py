#!/usr/bin/env python3
"""Invoke Hermes single-query chat with a prompt file (avoids shell quoting bugs)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--max-turns", type=int, default=35)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--hermes-bin", default="hermes")
    args = parser.parse_args()

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
