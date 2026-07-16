#!/usr/bin/env python3
"""Mechanical PROVIDER_AUTH gate for live legal matters.

Live matters must have ``<matter>/03_attorney/PROVIDER_AUTH.md`` present,
non-empty, and attorney-initialed before remote models see client text.

Synthetic pilot fixtures are exempt (path under ``skills/legal/*/fixtures``
or ``examples``, a SYNTHETIC banner in the matter, or
``--allow-unsigned-provider-auth``).

Enforcement triggers when the matter path looks live (``C:\\Matters\\...`` /
``/Matters/...``) or ``HERMES_REQUIRE_PROVIDER_AUTH=1``.

Exit codes: 0 = ok / exempt; 1 = missing or incomplete; 2 = usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

PROVIDER_AUTH_REL = Path("03_attorney") / "PROVIDER_AUTH.md"

# "- Attorney initials: JD  Date: 2026-07-12" — reject template underscores.
_ATTORNEY_INITIALS_LINE = re.compile(
    r"(?im)^\s*[-*]?\s*Attorney initials:\s*(?P<val>\S.*?)\s*$"
)
_BLANKISH = re.compile(r"^[_—–\-\s.]+$")
# Alternate attestation form: "/s/ JD" (do not use initials? — matches "initialed").
_SLASH_S_INITIALS = re.compile(
    r"(?i)(?:^|[\s(])/s/\s+([A-Za-z]{2,4}|[A-Za-z]\.[A-Za-z]\.?)\b"
)
_SYNTHETIC_MARK = re.compile(
    r"(?i)\bSYNTHETIC\b.*\b(?:NON-CLIENT|TEST ONLY|FIXTURE)\b"
    r"|\bSYNTHETIC\s*/\s*NON-CLIENT\b"
)
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def provider_auth_path(matter_dir: Path) -> Path:
    return Path(matter_dir).expanduser().resolve() / PROVIDER_AUTH_REL


def _path_parts_lower(matter_dir: Path) -> Tuple[str, ...]:
    return tuple(p.casefold() for p in Path(matter_dir).expanduser().resolve().parts)


def is_synthetic_matter_path(matter_dir: Path) -> bool:
    """True when the matter lives under legal fixtures/examples trees."""
    parts = _path_parts_lower(matter_dir)
    if "fixtures" not in parts and "examples" not in parts:
        return False
    try:
        legal_idx = parts.index("legal")
    except ValueError:
        # Repo checkout without a 'legal' segment — still treat skills/**/fixtures
        # as synthetic when present.
        if "skills" not in parts:
            return False
        skills_idx = parts.index("skills")
        return any(p in ("fixtures", "examples") for p in parts[skills_idx + 1:])
    return any(p in ("fixtures", "examples") for p in parts[legal_idx + 1:])


def matter_has_synthetic_banner(matter_dir: Path) -> bool:
    """True when a matter-root marker advertises SYNTHETIC / NON-CLIENT."""
    root = Path(matter_dir).expanduser().resolve()
    for name in ("README.md", "SYNTHETIC", "MATTER.md", ".synthetic",
                 "SOUL.md", "matter.json"):
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            continue
        if _SYNTHETIC_MARK.search(text) or (
            "SYNTHETIC" in text.upper() and "NON-CLIENT" in text.upper()
        ):
            return True
    return False


def is_live_matter_path(matter_dir: Path) -> bool:
    """True for canonical live matter roots (e.g. C:\\Matters\\...)."""
    parts = _path_parts_lower(matter_dir)
    # Drive:\Matters\... or /Matters/...
    if len(parts) >= 2 and parts[1] == "matters":
        return True
    if parts and parts[0] == "matters":
        return True
    return False


def env_requires_provider_auth(env: Optional[dict] = None) -> bool:
    env = env if env is not None else os.environ
    return str(env.get("HERMES_REQUIRE_PROVIDER_AUTH", "")).strip().casefold() in _TRUTHY


def should_enforce(matter_dir: Path, *, force: bool = False,
                   env: Optional[dict] = None) -> bool:
    if force or env_requires_provider_auth(env):
        return True
    return is_live_matter_path(matter_dir)


def is_exempt(matter_dir: Path, *, allow_unsigned: bool = False) -> bool:
    if allow_unsigned:
        return True
    return (is_synthetic_matter_path(matter_dir)
            or matter_has_synthetic_banner(matter_dir))


def attorney_initials_complete(text: str) -> bool:
    """True when PROVIDER_AUTH body has real attorney initials (not blanks)."""
    if not text or not text.strip():
        return False
    for m in _ATTORNEY_INITIALS_LINE.finditer(text):
        val = m.group("val").strip()
        # Drop a trailing "Date: ..." if it shared the line.
        if re.search(r"(?i)\bDate:", val):
            val = re.split(r"(?i)\bDate:", val, maxsplit=1)[0].strip()
        if not val or _BLANKISH.match(val) or set(val) <= {"_", " ", "—", "–", "-"}:
            continue
        if re.fullmatch(r"_+", val):
            continue
        # Require at least two letters somewhere in the initials field.
        letters = re.sub(r"[^A-Za-z]", "", val)
        if len(letters) >= 2:
            return True
    return _SLASH_S_INITIALS.search(text) is not None


def check_provider_auth_file(auth_path: Path) -> Tuple[bool, str]:
    """Return (ok, reason) for a PROVIDER_AUTH.md path."""
    if not auth_path.is_file():
        return False, f"missing {auth_path}"
    try:
        text = auth_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, f"unreadable {auth_path}: {e}"
    if not text.strip():
        return False, f"empty {auth_path}"
    if not attorney_initials_complete(text):
        return False, (
            f"incomplete attorney initials in {auth_path} "
            f"(fill 'Attorney initials: XX' — template blanks are not enough)"
        )
    return True, "ok"


def check_provider_auth(
    matter_dir: Path,
    *,
    allow_unsigned: bool = False,
    force: bool = False,
    env: Optional[dict] = None,
) -> Tuple[int, str]:
    """Gate a matter directory.

    Returns (exit_code, message). 0 = proceed; 1 = stop; 2 = bad args.
    """
    try:
        root = Path(matter_dir).expanduser().resolve()
    except OSError as e:
        return 2, f"ERROR: invalid matter dir: {e}"
    if not root.is_dir():
        return 2, f"ERROR: matter directory not found: {root}"

    if is_exempt(root, allow_unsigned=allow_unsigned):
        return 0, "exempt (synthetic or --allow-unsigned-provider-auth)"

    if not should_enforce(root, force=force, env=env):
        return 0, "not enforced (not a live Matters path; set HERMES_REQUIRE_PROVIDER_AUTH=1 to force)"

    ok, reason = check_provider_auth_file(provider_auth_path(root))
    if ok:
        return 0, reason
    return 1, (
        f"PROVIDER_AUTH gate FAILED: {reason}. "
        f"Copy skills/legal/templates/PROVIDER_AUTH.template.md to "
        f"{PROVIDER_AUTH_REL.as_posix()} and have the attorney complete it. STOP."
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mechanical PROVIDER_AUTH.md gate for live legal matters.")
    parser.add_argument("matter_dir", type=Path, help="Matter directory root")
    parser.add_argument(
        "--allow-unsigned-provider-auth",
        action="store_true",
        help="Exempt this run (synthetic / owner override)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Enforce even when the path is not under Matters/",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable result")
    args = parser.parse_args(argv)

    code, msg = check_provider_auth(
        args.matter_dir,
        allow_unsigned=args.allow_unsigned_provider_auth,
        force=args.force,
    )
    if args.json:
        import json
        print(json.dumps({"ok": code == 0, "exit": code, "message": msg}, indent=2))
    else:
        stream = sys.stdout if code == 0 else sys.stderr
        print(msg, file=stream)
    return code


if __name__ == "__main__":
    sys.exit(main())
