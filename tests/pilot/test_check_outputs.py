"""Tests for pilot/check_outputs.py structural gates."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECK = REPO / "pilot" / "check_outputs.py"


def _load_check_outputs():
    spec = importlib.util.spec_from_file_location("check_outputs_mod", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

INTAKE_STUB = """\
**SYNTHETIC / NON-CLIENT / TEST ONLY**

## Matter Profile
Test Valley Railroad (TVRR) — Northgate Yard — 2024-11-12

## Parties / Witnesses / Entities
J.T., L.M., R.K., D.W.

## Incident Summary
Northgate Yard incident involving locomotive TVRR 4721 on 2024-11-12.

## FELA / PI Issue Checklist
Requires attorney review against 45 U.S.C. §§ 51-60 before issue flags finalize.

## Injury / Medical-Treatment Capture
Left rotator cuff tear; County General treatment.

## Employment / Wage-Loss Capture
Freight Conductor; wage loss from 2024-11-12.

## Liability Theory Checklist
Evidence suggests unsecured cut — requires attorney review.

## Preservation / Spoliation Checklist
Preserve yard logs — requires attorney review.

## Missing-Information List
Union details — requires attorney review.

## Client Interview Follow-Up Questions
Clarify prior close-call report — requires attorney review.

## Initial Discovery Plan
Phased discovery — requires attorney review.

## Draft Discovery Starter Sets
Sample RFP topics — requires attorney review.

## Verification
SOL Issue Flag: limitations issue for attorney determination only.

## Pitfalls
Do not state liability as established fact.
"""


def _run(phase: str, directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), "--phase", phase, "--dir", str(directory)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )


def test_intake_stub_passes(tmp_path):
    d = tmp_path / "intake"
    d.mkdir()
    (d / "intake_package.md").write_text(INTAKE_STUB, encoding="utf-8")
    result = _run("intake", d)
    assert result.returncode == 0, result.stdout + result.stderr


def test_intake_missing_sol_flag_fails(tmp_path):
    d = tmp_path / "intake"
    d.mkdir()
    bad = INTAKE_STUB.replace("SOL Issue Flag", "SOL Deadline")
    (d / "intake_package.md").write_text(bad, encoding="utf-8")
    result = _run("intake", d)
    assert result.returncode != 0


def test_empty_section_detected(tmp_path):
    """FABLE5 L1: a required header present with an empty body must fail."""
    d = tmp_path / "intake"
    d.mkdir()
    # Blank out the Pitfalls section body (header present, no content).
    bad = INTAKE_STUB.replace(
        "## Pitfalls\nDo not state liability as established fact.\n",
        "## Pitfalls\n",
    )
    (d / "intake_package.md").write_text(bad, encoding="utf-8")
    result = _run("intake", d)
    assert result.returncode != 0
    assert "empty" in (result.stdout + result.stderr).lower()


def test_gate_phrase_overlap_counts_once():
    """FABLE5 M12: 'attorney review' ⊂ 'requires attorney review' is ONE signal."""
    co = _load_check_outputs()
    phrases = co.INTAKE_GATE_PHRASES
    # A single overlapping phrase must NOT satisfy min_count=2 on its own.
    only_overlap = "This output requires attorney review before use."
    assert co._missing_gate_phrases(only_overlap, phrases, min_count=2) is False
    # Two DISTINCT gate concepts do satisfy it.
    two_distinct = "Requires attorney review under 45 U.S.C. section 51."
    assert co._missing_gate_phrases(two_distinct, phrases, min_count=2) is True


def test_distinct_gate_phrases_collapses_supersets():
    co = _load_check_outputs()
    got = co._distinct_gate_phrases(["attorney review", "requires attorney review", "45 u.s.c"])
    # 'requires attorney review' collapses into 'attorney review'.
    assert "attorney review" in got
    assert "requires attorney review" not in got
    assert "45 u.s.c" in got
