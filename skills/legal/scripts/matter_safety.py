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
_OWNER_GATE_FILE = re.compile(
    r"^OWNER_LIVE_GATE_(?P<slice>A[1-3]|B[1-3]|C[1-3]|D[1-3]|E1|F1|G1)"
    r"(?:_[A-Z0-9_-]+)?\.md$",
    re.IGNORECASE,
)
_NON_OWNER_GATE_NAME = re.compile(
    r"(?i)(REHEARSAL|DRAFT|ASSISTANT|REVIEW[_-]?PACKET)"
)
_FIELD_LINE = re.compile(r"(?im)^\s*(?P<key>[a-z_]+)\s*:\s*(?P<val>.*?)\s*$")
_CHECKED_BOX = re.compile(r"(?i)\[x\]")
_BLANKISH_FIELD = re.compile(r"^[_\-\s.]+$")


def _field_value(text: str, key: str) -> str:
    for match in _FIELD_LINE.finditer(text):
        if match.group("key").casefold() == key.casefold():
            return match.group("val").strip()
    return ""


def _field_is_blankish(value: str) -> bool:
    clean = value.strip().strip("`")
    return not clean or _BLANKISH_FIELD.match(clean) is not None


def _selected_choice(text: str, key: str, choices: tuple[str, ...]) -> str | None:
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if re.match(rf"(?i)^\s*{re.escape(key)}\s*:", line):
            start = idx
            break
    if start is None:
        return None

    region = [lines[start]]
    for line in lines[start + 1:start + 8]:
        if re.match(r"^\s*[a-z_]+\s*:", line, flags=re.IGNORECASE):
            break
        if line.strip().startswith("---"):
            break
        region.append(line)
    joined = "\n".join(region)

    checked = [
        choice for choice in choices
        if re.search(rf"(?i)\[x\]\s*{re.escape(choice)}\b", joined)
    ]
    if len(checked) == 1:
        return checked[0]
    if len(checked) > 1:
        return None

    direct = _field_value(text, key)
    if direct and "[" not in direct:
        token = re.split(r"\s+|\(|#", direct.strip(), maxsplit=1)[0]
        for choice in choices:
            if token.casefold() == choice.casefold():
                return choice
    return None


def _owner_gate_paths(attorney: Path) -> list[Path]:
    paths: list[Path] = []
    for path in attorney.glob("OWNER_LIVE_GATE*.md"):
        if _NON_OWNER_GATE_NAME.search(path.name):
            continue
        if _OWNER_GATE_FILE.match(path.name):
            paths.append(path)
    return sorted(paths)


def _section_95(text: str) -> str:
    match = re.search(r"(?im)^---\s*(?:§\s*)?9\.5\s+Ready-for-live.*$", text)
    if match:
        rest = text[match.end():]
        next_section = re.search(r"(?m)^---\s+", rest)
        end = match.end() + next_section.start() if next_section else len(text)
        return text[match.start():end]
    idx = text.find("§9.5")
    if idx < 0:
        idx = text.lower().find("9.5")
    return text[idx:idx + 1200] if idx >= 0 else ""


def _validate_owner_gate_text(
    text: str,
    *,
    path: Path,
    expected_matter_id: str | None = None,
    request_type: str | None = None,
    mode: str | None = None,
    slice_id: str | None = None,
) -> tuple[bool, str]:
    name_match = _OWNER_GATE_FILE.match(path.name)
    if not name_match or _NON_OWNER_GATE_NAME.search(path.name):
        return False, f"not a canonical owner gate filename: {path.name}"
    actual_slice = name_match.group("slice").upper()
    if slice_id and actual_slice != slice_id.upper():
        return False, f"owner gate slice mismatch: {actual_slice} != {slice_id.upper()}"

    if re.search(r"(?i)REHEARSAL_EVIDENCE|NOT\s+OWNER\s+APPROVAL|VOID\s+§?\s*9\.5", text):
        return False, "rehearsal/void gate is not owner §9.5 approval"

    matter_value = _field_value(text, "matter_id")
    if _field_is_blankish(matter_value):
        return False, "owner gate missing matter_id"
    if expected_matter_id and matter_value.casefold() != expected_matter_id.casefold():
        return False, f"owner gate matter_id mismatch: {matter_value} != {expected_matter_id}"

    selected_type = _selected_choice(text, "request_type", ("rog", "rfp", "rfa", "expert"))
    if selected_type is None:
        return False, "owner gate must select exactly one request_type"
    if request_type and selected_type.casefold() != request_type.casefold():
        return False, f"owner gate request_type mismatch: {selected_type} != {request_type}"

    selected_mode = _selected_choice(
        text,
        "mode",
        (
            "audit_incoming_response",
            "draft_outgoing_request",
            "audit_incoming_request",
            "trial_gap_assessment",
            "draft_response",
            "expert_needs_assessment",
            "enforcement_motion_draft",
        ),
    )
    if selected_mode is None:
        return False, "owner gate must select exactly one mode"
    if mode and selected_mode.casefold() != mode.casefold():
        return False, f"owner gate mode mismatch: {selected_mode} != {mode}"

    tip = _field_value(text, "tip_commit_sha")
    if not re.fullmatch(r"(?i)[0-9a-f]{7,40}", tip.strip()):
        return False, "owner gate missing valid tip_commit_sha"

    section = _section_95(text)
    if "9.5" not in section:
        return False, "owner gate missing §9.5 section"
    if len(_CHECKED_BOX.findall(section)) < 4:
        return False, "all four §9.5 boxes must be owner-checked"

    sig_match = _OWNER_SIG.search(text)
    if not sig_match:
        return False, "missing owner_signature"
    sig = sig_match.group("val").strip()
    if not sig or _VOIDISH_SIG.search(sig) or set(sig) <= {"_", "-", " ", "."}:
        return False, "owner_signature is empty/void"
    return True, f"ok ({path.name})"


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
    request_type: str | None = None,
    mode: str | None = None,
    slice_id: str | None = None,
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
    if request_type:
        cmd.extend(["--request-type", request_type])
    if mode:
        cmd.extend(["--mode", mode])
    if slice_id:
        cmd.extend(["--slice", slice_id])
    if may_skip_ocr_queue(root, synthetic_flag=synthetic_flag):
        cmd.append("--skip-ocr-queue")
    gates.append(cmd)


def owner_live_gate_satisfied(
    matter_dir: Path,
    *,
    expected_matter_id: str | None = None,
    request_type: str | None = None,
    mode: str | None = None,
    slice_id: str | None = None,
) -> tuple[bool, str]:
    """Mechanical §9.5 check for live non-SYN matters (not rehearsal evidence)."""
    root = Path(matter_dir).expanduser().resolve()
    attorney = root / "03_attorney"
    if not attorney.is_dir():
        return False, "missing 03_attorney/"
    gates = _owner_gate_paths(attorney)
    if not gates:
        return False, "missing canonical OWNER_LIVE_GATE_<slice>.md (owner 9.5)"
    first_failure = ""
    for gate in gates:
        try:
            text = gate.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            first_failure = first_failure or f"unreadable owner gate: {exc}"
            continue
        ok, detail = _validate_owner_gate_text(
            text,
            path=gate,
            expected_matter_id=expected_matter_id,
            request_type=request_type,
            mode=mode,
            slice_id=slice_id,
        )
        if ok:
            return True, detail
        first_failure = first_failure or detail
    return False, first_failure or "no valid owner 9.5 gate found"


def require_owner_live_gate_if_live(
    matter_dir: Path,
    *,
    expected_matter_id: str | None = None,
    request_type: str | None = None,
    mode: str | None = None,
    slice_id: str | None = None,
) -> tuple[bool, str]:
    """On live non-SYN paths, require a filled owner gate; SYN-* rehearsal skips."""
    root = Path(matter_dir).expanduser().resolve()
    if not is_live_matter_path(root):
        return True, "not a live Matters path"
    if is_syn_matter_id(resolve_matter_id(root)):
        return True, "SYN-* rehearsal path (owner §9.5 not forged by tooling)"
    return owner_live_gate_satisfied(
        root,
        expected_matter_id=expected_matter_id,
        request_type=request_type,
        mode=mode,
        slice_id=slice_id,
    )


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
