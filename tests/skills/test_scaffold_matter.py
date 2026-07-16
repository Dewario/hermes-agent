"""Tests for the live legal matter scaffold helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "scaffold_matter.py"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("scaffold_matter", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


scaffold = _load()


def test_scaffold_creates_live_matter_layout_and_stubs(tmp_path, capsys, monkeypatch):
    matter = tmp_path / "Smith-v-Acme"
    monkeypatch.setattr(scaffold, "REPO_ROOT", tmp_path / "checkout")

    assert scaffold.main([
        "--matter-dir", str(matter),
        "--bates-prefix", "ACME-PROD",
        "--bates-prefix", "SMITH",
    ]) == 0

    for relative in (
        "00_intake",
        "01_production/raw",
        "01_production/text",
        "02_outputs",
        "03_attorney",
        "correspondence",
    ):
        assert (matter / relative).is_dir()

    auth = matter / "03_attorney" / "PROVIDER_AUTH.md"
    assert auth.read_text(encoding="utf-8") == (
        REPO / "skills/legal/templates/PROVIDER_AUTH.template.md"
    ).read_text(encoding="utf-8")
    assert (matter / "03_attorney" / "anchors.json").is_file()
    assert "ATTORNEY WORK PRODUCT — fill before live use" in (
        matter / "03_attorney" / "cite_check_log.md"
    ).read_text(encoding="utf-8")
    manifest = (matter / "01_production" / "BATES_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert "ATTORNEY WORK PRODUCT — fill before live use" in manifest
    assert "ACME-PROD" in manifest and "SMITH" in manifest

    out = capsys.readouterr().out
    assert "sign PROVIDER_AUTH" in out
    assert "loadfile_to_manifest" in out
    assert "casegraph init" in out


def test_scaffold_preserves_existing_attorney_files(tmp_path, monkeypatch):
    matter = tmp_path / "Matter"
    monkeypatch.setattr(scaffold, "REPO_ROOT", tmp_path / "checkout")
    attorney = matter / "03_attorney"
    attorney.mkdir(parents=True)
    auth = attorney / "PROVIDER_AUTH.md"
    anchors = attorney / "anchors.json"
    auth.write_text("signed authorization", encoding="utf-8")
    anchors.write_text('{"fact_anchors":["existing"]}\n', encoding="utf-8")

    assert scaffold.main(["--matter-dir", str(matter)]) == 0

    assert auth.read_text(encoding="utf-8") == "signed authorization"
    assert anchors.read_text(encoding="utf-8") == '{"fact_anchors":["existing"]}\n'


def test_scaffold_refuses_matter_inside_checkout(tmp_path, capsys):
    inside_repo = REPO / ".tmp-scaffold-matter-test"
    try:
        assert scaffold.main(["--matter-dir", str(inside_repo)]) == 2
        assert "outside the hermes-agent git repository" in capsys.readouterr().err
        assert not inside_repo.exists()
    finally:
        if inside_repo.exists():
            inside_repo.rmdir()
