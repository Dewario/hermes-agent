"""Tests for ocr_from_queue helper (plan mode; no live OCR)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "ocr_from_queue.py"
CASEGRAPH = REPO / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ocr = _load(SCRIPT, "ocr_from_queue")
cg = _load(CASEGRAPH, "casegraph_for_ocr_test")


@pytest.fixture()
def matter_with_scan(tmp_path):
    m = tmp_path / "matter"
    prod = m / "01_production" / "raw"
    prod.mkdir(parents=True)
    (prod / "scan_ACME-000001.pdf").write_bytes(
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nnot a real pdf"
    )
    assert cg.main(["init", str(m), "--matter-id", "OCR-T",
                    "--bates-prefix", "ACME"]) == 0
    assert cg.main(["build", str(m)]) == 0
    return m


def test_plan_from_queue(matter_with_scan, capsys):
    rc = ocr.main([str(matter_with_scan)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "OCR queue:" in out
    assert "ocrmypdf" in out or "Manual" in out
    assert "Docling" in out
    assert (matter_with_scan / ".casegraph" / "needs_ocr.json").exists()


def test_json_plan(matter_with_scan, capsys):
    assert ocr.main([str(matter_with_scan), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] >= 1
    assert payload["plan"]


def test_run_skips_completed_sha_and_honors_pdf_limit(tmp_path, monkeypatch):
    matter = tmp_path / "matter"
    raw = matter / "01_production" / "raw"
    raw.mkdir(parents=True)
    first = raw / "first.pdf"
    second = raw / "second.pdf"
    first.write_bytes(b"first PDF")
    second.write_bytes(b"second PDF")
    queue_dir = matter / ".casegraph"
    queue_dir.mkdir()
    (queue_dir / "needs_ocr.json").write_text(json.dumps({
        "matter_id": "OCR-LIMIT",
        "documents": [
            {"relpath": "01_production/raw/first.pdf"},
            {"relpath": "01_production/raw/second.pdf"},
        ],
    }), encoding="utf-8")
    state = queue_dir / "ocr_farm_state.json"
    first_sha = ocr.sha256_file(first)
    state.write_text(json.dumps({"completed_sha256": [first_sha]}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(ocr.shutil, "which", lambda _: "ocrmypdf")
    monkeypatch.setattr(
        ocr.subprocess, "call",
        lambda command: calls.append(command) or 0,
    )

    assert ocr.main([str(matter), "--run", "--limit", "1"]) == 0
    assert calls == [[
        "ocrmypdf", "--skip-text", str(second),
        str(matter / "01_production" / "text" / "second.searchable.pdf"),
    ]]
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert set(saved["completed_sha256"]) == {first_sha, ocr.sha256_file(second)}
