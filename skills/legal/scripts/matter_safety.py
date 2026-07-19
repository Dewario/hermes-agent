#!/usr/bin/env python3
"""Shared path / synthetic safety guards for legal matter tooling.

Used by discovery-workflow materializers, live_preflight, and provider-auth
exemption so smoke/rehearsal cannot rmtree live dirs and planted ``.synthetic``
markers cannot dual-bypass OCR + PROVIDER_AUTH on real Matters paths.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

LIVE_ID_BLOCKLIST = re.compile(
    r"(allen|client[\s_-]?[ab]|prod[-_]?client|live[-_]?client)",
    re.IGNORECASE,
)
SYN_ID_RE = re.compile(r"^SYN-[A-Z0-9][A-Z0-9_-]*$", re.IGNORECASE)

_MATTER_ID_YAML = re.compile(
    r"(?m)^\s*matter_id:\s*[\"']?([^\s\"'#]+)"
)
_OWNER_SIG = re.compile(
    r"(?im)^\s*owner_signature:\s*(?P<val>\S.*?)\s*$"
)
_VOIDISH_SIG = re.compile(
    r"(?i)\b(void|unsigned|rehearsal|not\s+approval|n/?a|none|_+)\b"
)


def is_syn_matter_id(matter_id: str | None) -> bool:
    text = (matter_id or "").strip()
    if not text or not SYN_ID_RE.match(text):
        return False
    if LIVE_ID_BLOCKLIST.search(text):
        return False
    return True


def is_live_matter_path(matter_dir: Path) -> bool:
    """True for canonical live matter roots (e.g. C:\\Matters\\...)."""
    parts = tuple(p.casefold() for p in Path(matter_dir).expanduser().resolve().parts)
    if len(parts) >= 2 and parts[1] == "matters":
        return True
    if parts and parts[0] == "matters":
        return True
    return False


def resolve_matter_id(matter_dir: Path) -> str:
    """Best-effort matter_id from profile, casegraph manifest, or directory name."""
    root = Path(matter_dir).expanduser().resolve()
    profile = root / "03_attorney" / "matter_profile.yaml"
    if profile.is_file():
        try:
            text = profile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        match = _MATTER_ID_YAML.search(text)
        if match:
            return match.group(1).strip()
    manifest = root / ".casegraph" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            mid = str(data.get("matter_id") or "").strip()
            if mid:
                return mid
        except (OSError, json.JSONDecodeError):
            pass
    return root.name


def refuse_live_path(path: Path, *, allow_matters_synth: bool) -> None:
    """Refuse Allen/live-looking paths; Matters roots require SYN-* when allowed."""
    text = str(path.expanduser().resolve())
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
        if not is_syn_matter_id(name):
            raise SystemExit(
                f"ERROR: Matters path must be SYN-* matter id, got {name!r}"
            )


def refuse_destructive_matter_dir(
    dest: Path,
    *,
    expected_matter_id: str | None = None,
    allow_matters_synth: bool = True,
) -> None:
    """Refuse rmtree/replace of non-synthetic or live-looking matter dirs."""
    dest = dest.expanduser().resolve()
    refuse_live_path(dest, allow_matters_synth=allow_matters_synth)
    expected = expected_matter_id or dest.name
    if not is_syn_matter_id(expected) and not is_syn_matter_id(dest.name):
        raise SystemExit(
            f"ERROR: destructive materialize requires SYN-* matter id, got "
            f"dest={dest.name!r} expected={expected!r}"
        )
    if LIVE_ID_BLOCKLIST.search(expected) or LIVE_ID_BLOCKLIST.search(dest.name):
        raise SystemExit(
            f"ERROR: refused live-looking matter_id for materialize: {expected!r}"
        )
    if not dest.exists():
        return
    if dest.is_file():
        raise SystemExit(f"ERROR: matter dest is a file, not a directory: {dest}")
    has_synth = (dest / ".synthetic").is_file()
    if not has_synth and not is_syn_matter_id(dest.name):
        raise SystemExit(
            f"ERROR: refuse rmtree of non-synthetic directory: {dest}"
        )


def may_skip_ocr_queue(matter_dir: Path, *, synthetic_flag: bool = False) -> bool:
    """OCR skip only for clear synthetic matters — not planted markers on live paths."""
    root = Path(matter_dir).expanduser().resolve()
    has_marker = bool(synthetic_flag) or (root / ".synthetic").is_file()
    if not has_marker:
        return False
    if is_live_matter_path(root):
        return is_syn_matter_id(resolve_matter_id(root))
    return True


def refuse_skip_live_preflight_if_live(matter_dir: Path, *, skip: bool) -> None:
    """Block --skip-live-preflight on live non-SYN Matters paths."""
    if not skip:
        return
    root = Path(matter_dir).expanduser().resolve()
    if is_live_matter_path(root) and not is_syn_matter_id(resolve_matter_id(root)):
        raise SystemExit(
            "ERROR: --skip-live-preflight refused on live non-SYN matter "
            f"({root.name}). Owner §9.5 + live_preflight required."
        )


def append_live_preflight_gate(
    gates: list,
    root: Path,
    *,
    live_preflight_script: Path,
    skip_live_preflight: bool,
    synthetic_flag: bool = False,
    python: Optional[str] = None,
) -> None:
    """Append live_preflight argv with OCR-skip policy, or refuse illegal skip."""
    refuse_skip_live_preflight_if_live(root, skip=skip_live_preflight)
    if skip_live_preflight:
        return
    cmd = [
        python or sys.executable,
        str(live_preflight_script),
        "--matter-dir",
        str(root),
    ]
    if may_skip_ocr_queue(root, synthetic_flag=synthetic_flag):
        cmd.append("--skip-ocr-queue")
    gates.append(cmd)


def owner_live_gate_satisfied(matter_dir: Path) -> tuple[bool, str]:
    """Mechanical §9.5 check for live non-SYN matters (not rehearsal evidence)."""
    root = Path(matter_dir).expanduser().resolve()
    attorney = root / "03_attorney"
    if not attorney.is_dir():
        return False, "missing 03_attorney/"
    gates = sorted(
        p
        for p in attorney.glob("OWNER_LIVE_GATE*.md")
        if "REHEARSAL" not in p.name.upper()
    )
    if not gates:
        return False, "missing OWNER_LIVE_GATE_*.md (owner §9.5)"
    try:
        text = gates[0].read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"unreadable owner gate: {exc}"
    if re.search(r"(?i)REHEARSAL_EVIDENCE|NOT\s+OWNER\s+APPROVAL|VOID\s+§?\s*9\.5", text):
        return False, "rehearsal/void gate is not owner §9.5 approval"
    if "§9.5" not in text and "9.5" not in text:
        return False, "owner gate missing §9.5 section"
    # Require at least one checked box in the §9.5 region.
    section = text
    idx = text.find("§9.5")
    if idx < 0:
        idx = text.lower().find("9.5")
    if idx >= 0:
        section = text[idx : idx + 1200]
    if "[x]" not in section.lower() and "[X]" not in section:
        # markdown checkboxes often written [x]
        if not re.search(r"(?i)\[x\]", section):
            return False, "§9.5 boxes not owner-checked"
    sig_match = _OWNER_SIG.search(text)
    if not sig_match:
        return False, "missing owner_signature"
    sig = sig_match.group("val").strip()
    if not sig or _VOIDISH_SIG.search(sig) or set(sig) <= {"_", "-", " ", "."}:
        return False, "owner_signature is empty/void"
    return True, f"ok ({gates[0].name})"


def require_owner_live_gate_if_live(matter_dir: Path) -> tuple[bool, str]:
    """On live non-SYN paths, require a filled owner gate; SYN-* rehearsal skips."""
    root = Path(matter_dir).expanduser().resolve()
    if not is_live_matter_path(root):
        return True, "not a live Matters path"
    if is_syn_matter_id(resolve_matter_id(root)):
        return True, "SYN-* rehearsal path (owner §9.5 not forged by tooling)"
    return owner_live_gate_satisfied(root)


def refuse_skip_ocr_if_live(matter_dir: Path, *, skip_ocr_queue: bool) -> None:
    """Refuse --skip-ocr-queue on live non-SYN Matters paths."""
    if not skip_ocr_queue:
        return
    root = Path(matter_dir).expanduser().resolve()
    if is_live_matter_path(root) and not is_syn_matter_id(resolve_matter_id(root)):
        raise SystemExit(
            "ERROR: --skip-ocr-queue refused on live non-SYN matter "
            f"({root.name}). Clear the OCR queue or obtain owner §9.5."
        )
