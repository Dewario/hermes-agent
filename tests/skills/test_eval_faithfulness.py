"""Tests for pilot/eval_faithfulness.py — synthetic legal goldens only."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "pilot" / "eval_faithfulness.py"
REVIEW_GOLDEN = (
    REPO / "skills/legal/discovery-review/examples/2026-07-07-synthetic-v1/review_package.md"
)
REVIEW_FIXTURES = REPO / "skills/legal/discovery-review/fixtures"


def _load_eval():
    spec = importlib.util.spec_from_file_location("eval_faithfulness_mod", EVAL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_synthetic_golden_review_passes():
    ev = _load_eval()
    report = ev.evaluate(REVIEW_GOLDEN, REVIEW_FIXTURES)
    assert report["pass"], json.dumps(report["failures"][:5], indent=2)
    assert report["claims_checked"] >= 10
    assert report["corpus_documents"] == 6


def test_fabricated_claim_fails(tmp_path):
    ev = _load_eval()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "TVRR-PROD-000001.md").write_text(
        "**SYNTHETIC / NON-CLIENT / TEST ONLY**\n\n"
        "**Document ID:** TVRR-PROD-000001 through TVRR-PROD-000001\n"
        "**Bates Range:** TVRR-PROD-000001 - TVRR-PROD-000001\n\n"
        "The locomotive was inspected on 2024-11-01 with no defects noted.\n",
        encoding="utf-8",
    )
    package = tmp_path / "review_package.md"
    package.write_text(
        "**SYNTHETIC / NON-CLIENT / TEST ONLY**\n\n"
        "## Section 4: Key Fact Extraction\n\n"
        "| Doc ID | Fact |\n"
        "|--------|------|\n"
        "| TVRR-PROD-000001 | The engineer reported a catastrophic brake failure "
        "and derailment at Northgate Yard before any coupling occurred. |\n",
        encoding="utf-8",
    )
    report = ev.evaluate(package, corpus)
    assert not report["pass"]
    assert report["failures"]


def test_missing_synthetic_banner_fails(tmp_path):
    ev = _load_eval()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "TVRR-PROD-000001.md").write_text(
        "**Document ID:** TVRR-PROD-000001 through TVRR-PROD-000001\n\n"
        "Northgate Yard switching operation on Track 2.\n",
        encoding="utf-8",
    )
    package = tmp_path / "package.md"
    package.write_text(
        "Claim about Northgate Yard switching on TVRR-PROD-000001.\n",
        encoding="utf-8",
    )
    report = ev.evaluate(package, corpus, require_synthetic=True)
    assert not report["pass"]
    assert "synthetic banner" in report.get("error", "").lower()


def test_quoted_span_must_appear_in_corpus(tmp_path):
    ev = _load_eval()
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "TVRR-PROD-000095.md").write_text(
        "**SYNTHETIC / NON-CLIENT / TEST ONLY**\n\n"
        "**Bates Range:** TVRR-PROD-000095 - TVRR-PROD-000097\n\n"
        "The lighting on Track 2 has always been dim.\n",
        encoding="utf-8",
    )
    package = tmp_path / "review_package.md"
    package.write_text(
        "**SYNTHETIC / NON-CLIENT / TEST ONLY**\n\n"
        "## Section 4: Key Fact Extraction\n\n"
        "Per TVRR-PROD-000095, the witness said "
        '"the lighting on Track 2 has always been excellent and bright".\n',
        encoding="utf-8",
    )
    report = ev.evaluate(package, corpus)
    assert not report["pass"]
    assert any("quote" in f.get("reason", "").lower() for f in report["failures"])


def test_cli_json_exit_code():
    result = subprocess.run(
        [
            sys.executable,
            str(EVAL),
            "--package",
            str(REVIEW_GOLDEN),
            "--corpus",
            str(REVIEW_FIXTURES),
            "--json",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["pass"] is True
    assert payload["claims_checked"] >= 10
