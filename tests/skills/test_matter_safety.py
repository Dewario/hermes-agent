"""Tests for skills/legal/scripts/matter_safety.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "matter_safety.py"
OWNER_GATE_TEMPLATE = REPO / "skills" / "legal" / "discovery-workflow" / "OWNER_LIVE_GATE.md"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("matter_safety", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["matter_safety"] = module
    spec.loader.exec_module(module)
    return module


ms = _load()


def _valid_owner_gate(
    *,
    matter_id: str = "REAL-CLIENT-01",
    request_type: str = "rfp",
    mode: str = "audit_incoming_request",
    slice_id: str = "D1",
) -> str:
    request_choices = {
        "rog": "[x] rog   [ ] rfp   [ ] rfa   [ ] expert",
        "rfp": "[ ] rog   [x] rfp   [ ] rfa   [ ] expert",
        "rfa": "[ ] rog   [ ] rfp   [x] rfa   [ ] expert",
        "expert": "[ ] rog   [ ] rfp   [ ] rfa   [x] expert",
    }[request_type]
    modes = [
        "audit_incoming_response",
        "draft_outgoing_request",
        "audit_incoming_request",
        "trial_gap_assessment",
        "draft_response",
        "expert_needs_assessment",
        "enforcement_motion_draft",
        "objection_motion_draft",
    ]
    mode_choices = "\n                ".join(
        f"[{'x' if item == mode else ' '}] {item}" for item in modes
    )
    return f"""# 9.5 Owner Live Gate - {matter_id}

matter_id:      {matter_id}
request_type:   {request_choices}
mode:           {mode_choices}
tip_commit_sha: 9718cc340eb3697222ad0d05f7f37f7b9bfe0c52
slice:          {slice_id}

--- 9.5 Ready-for-live (OWNER ONLY) ---
[x] That slice's 9.1-9.3 are green on the tip_commit_sha above.
[x] Explicit written approval naming this matter_id + request_type + mode.
[x] Single-matter invocation confirmed.
[x] No client files under the repo.

owner_name:      Responsible Attorney
owner_signature: Responsible Attorney
date:            2026-07-20
"""


def test_syn_id_rejects_allen_embed():
    assert ms.is_syn_matter_id("SYN-SMOKE-COUNSEL") is True
    assert ms.is_syn_matter_id("SYN-ALLENCASE") is False
    assert ms.is_syn_matter_id("REAL-CLIENT-01") is False


def test_may_skip_ocr_temp_with_marker(tmp_path):
    matter = tmp_path / "SYN-TEMP"
    matter.mkdir()
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    assert ms.may_skip_ocr_queue(matter, synthetic_flag=False) is True


def test_may_skip_ocr_refuses_live_non_syn(tmp_path, monkeypatch):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    (matter / ".synthetic").write_text("SYNTHETIC / NON-CLIENT / TEST ONLY\n", encoding="utf-8")
    monkeypatch.setattr(ms, "is_live_matter_path", lambda _p: True)
    assert ms.may_skip_ocr_queue(matter, synthetic_flag=True) is False


def test_refuse_destructive_non_syn(tmp_path):
    dest = tmp_path / "REAL-CLIENT-01"
    dest.mkdir()
    (dest / "keep.txt").write_text("x\n", encoding="utf-8")
    try:
        ms.refuse_destructive_matter_dir(dest, expected_matter_id="REAL-CLIENT-01")
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "SYN" in str(exc)
    assert (dest / "keep.txt").is_file()


def test_owner_gate_rejects_rehearsal_evidence(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_D1.md").write_text(
        "# REHEARSAL_EVIDENCE — NOT OWNER APPROVAL\n\n"
        "--- §9.5 ---\n[ ] unchecked\n"
        "owner_signature: VOID — NOT OWNER APPROVAL\n",
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(matter)
    assert ok is False
    assert "rehearsal" in detail.lower() or "void" in detail.lower()


def test_owner_gate_ignores_draft_filename_even_if_checked(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_DRAFT.md").write_text(
        _valid_owner_gate(),
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(matter)
    assert ok is False
    assert "canonical" in detail.lower()


def test_owner_gate_accepts_canonical_matching_axis(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_D1.md").write_text(
        _valid_owner_gate(),
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(
        matter,
        expected_matter_id="REAL-CLIENT-01",
        request_type="rfp",
        mode="audit_incoming_request",
        slice_id="D1",
    )
    assert ok is True
    assert "OWNER_LIVE_GATE_D1.md" in detail


def test_owner_gate_rejects_wrong_mode_for_requested_slice(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_D1.md").write_text(
        _valid_owner_gate(mode="audit_incoming_request"),
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(
        matter,
        request_type="rfp",
        mode="draft_outgoing_request",
        slice_id="D1",
    )
    assert ok is False
    assert "mode mismatch" in detail.lower()


def test_append_live_preflight_gate_threads_owner_axes(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    gates: list[list[str]] = []

    ms.append_live_preflight_gate(
        gates,
        matter,
        live_preflight_script=Path("live_preflight.py"),
        skip_live_preflight=False,
        request_type="rfp",
        mode="audit_incoming_request",
        slice_id="D1",
        python="python",
    )

    command = gates[0]
    assert command[command.index("--request-type") + 1] == "rfp"
    assert command[command.index("--mode") + 1] == "audit_incoming_request"
    assert command[command.index("--slice") + 1] == "D1"


def test_owner_gate_template_matches_validator_contract():
    text = OWNER_GATE_TEMPLATE.read_text(encoding="utf-8")
    assert "owner_gate_assistant.py" in text
    assert "GATE_REVIEW_PACKET_*.md" in text
    assert "OWNER_LIVE_GATE_<slice>.md" in text
    assert "file_name:" in text
    assert "matter_id:" in text
    assert "tip_commit_sha:" in text
    assert "owner_signature:" in text
    assert "enforcement_motion_draft" in text
    assert "objection_motion_draft" in text
    assert "F1 enforcement-motion" in text
    assert "F2 objection-motion" in text
    assert "--request-type <rog|rfp|rfa|expert> --mode <mode> --slice <slice>" in text


def test_owner_gate_accepts_expert_needs_axis(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_E1.md").write_text(
        _valid_owner_gate(
            request_type="expert",
            mode="expert_needs_assessment",
            slice_id="E1",
        ),
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(
        matter,
        expected_matter_id="REAL-CLIENT-01",
        request_type="expert",
        mode="expert_needs_assessment",
        slice_id="E1",
    )
    assert ok is True
    assert "OWNER_LIVE_GATE_E1.md" in detail


def test_owner_gate_accepts_f2_objection_axis(tmp_path):
    matter = tmp_path / "REAL-CLIENT-01"
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    (attorney / "OWNER_LIVE_GATE_F2.md").write_text(
        _valid_owner_gate(
            request_type="rfa",
            mode="objection_motion_draft",
            slice_id="F2",
        ),
        encoding="utf-8",
    )
    ok, detail = ms.owner_live_gate_satisfied(
        matter,
        expected_matter_id="REAL-CLIENT-01",
        request_type="rfa",
        mode="objection_motion_draft",
        slice_id="F2",
    )
    assert ok is True
    assert "OWNER_LIVE_GATE_F2.md" in detail


def test_refuse_skip_live_preflight_on_live(tmp_path, monkeypatch):
    matter = tmp_path / "REAL-CLIENT-01"
    matter.mkdir()
    monkeypatch.setattr(ms, "is_live_matter_path", lambda _p: True)
    try:
        ms.refuse_skip_live_preflight_if_live(matter, skip=True)
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "skip-live-preflight" in str(exc)
