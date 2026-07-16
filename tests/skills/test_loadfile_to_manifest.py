"""Tests for the synthetic e-discovery loadfile manifest helper."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "legal" / "scripts" / "loadfile_to_manifest.py"
FIXTURES = REPO / "skills" / "legal" / "discovery-review" / "fixtures" / "loadfile"


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("loadfile_to_manifest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


manifest = _load()


def test_dat_and_opt_write_explicit_manifest_and_json(tmp_path, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()

    assert manifest.main([
        "--matter-dir", str(matter),
        "--dat", str(FIXTURES / "SYNTHETIC_pipe.dat"),
        "--opt", str(FIXTURES / "SYNTHETIC_images.opt"),
        "--json",
        "--print-casegraph-init",
    ]) == 0

    output = (matter / "01_production" / "BATES_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    payload = json.loads(
        (matter / "01_production" / "BATES_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert "SYN-PROD-000001" in output
    assert "OPT-PROD-000100" in output
    assert payload["prefixes"] == ["OPT-PROD", "SYN-PROD"]
    assert len(payload["ranges"]) == 4
    assert "casegraph init" in capsys.readouterr().out


def test_concordance_thorn_delimited_dat_is_parsed(tmp_path):
    matter = tmp_path / "matter"
    matter.mkdir()

    assert manifest.main([
        "--matter-dir", str(matter),
        "--dat", str(FIXTURES / "SYNTHETIC_concordance.dat"),
    ]) == 0

    output = (matter / "01_production" / "BATES_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert "THORN-PROD-000010" in output
    assert "THORN-PROD-000011" in output


def test_directory_input_and_unparseable_bates_do_not_invent_identifiers(tmp_path):
    matter = tmp_path / "matter"
    source = tmp_path / "loadfiles"
    matter.mkdir()
    source.mkdir()
    (source / "synthetic.dat").write_text(
        "BEGDOC|ENDDOC\n000001|000002\n", encoding="utf-8"
    )

    assert manifest.main(["--matter-dir", str(matter), "--dat", str(source)]) == 0

    output = (matter / "01_production" / "BATES_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert "Bates prefixes: none found" in output
    assert "000001" not in output


def test_production_folder_scans_dat_and_opt(tmp_path):
    matter = tmp_path / "matter"
    production = tmp_path / "production"
    matter.mkdir()
    production.mkdir()
    (production / "production.dat").write_text(
        "BEGDOC|ENDDOC\nFOLDER-PROD-000001|FOLDER-PROD-000001\n",
        encoding="utf-8",
    )
    (production / "images.lfp").write_text(
        "FOLDER-IMG-000010,volume\\image.tif,Y\n", encoding="utf-8"
    )

    assert manifest.main([
        "--matter-dir", str(matter),
        "--production-dir", str(production),
    ]) == 0

    output = (matter / "01_production" / "BATES_MANIFEST.md").read_text(
        encoding="utf-8"
    )
    assert "FOLDER-PROD-000001" in output
    assert "FOLDER-IMG-000010" in output


def test_rejects_output_outside_matter_dir(tmp_path, capsys):
    matter = tmp_path / "matter"
    matter.mkdir()
    outside = tmp_path / "outside.md"

    assert manifest.main([
        "--matter-dir", str(matter),
        "--dat", str(FIXTURES / "SYNTHETIC_pipe.dat"),
        "--out", str(outside),
    ]) == 2

    assert not outside.exists()
    assert "must stay under matter directory" in capsys.readouterr().err
