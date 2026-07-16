"""Tests for the optional local Docling extraction helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "docling_extract.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


docling_extract = _load(SCRIPT, "docling_extract")


def test_missing_docling_exits_with_install_hint(tmp_path, monkeypatch, capsys):
    matter = tmp_path / "matter"
    source = matter / "01_production" / "raw" / "scan.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF")
    monkeypatch.setattr(
        docling_extract.importlib,
        "import_module",
        lambda _: (_ for _ in ()).throw(ImportError("missing")),
    )

    assert docling_extract.main(["--matter-dir", str(matter), "--src", str(source)]) == 2
    assert "pip install docling" in capsys.readouterr().err


def test_rejects_source_outside_matter(tmp_path, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF")

    assert docling_extract.main(["--matter-dir", str(matter), "--src", str(outside)]) == 2
    assert "must stay under matter directory" in capsys.readouterr().err
