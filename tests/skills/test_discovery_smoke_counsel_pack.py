"""E2E smoke for counsel-pack synthetic matter fixture."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO / "skills" / "legal" / "discovery-workflow" / "scripts" / "smoke_counsel_pack.py"
)
SEED = (
    REPO / "skills" / "legal" / "discovery-workflow" / "fixtures" / "smoke_matter" / "seed"
)


def _load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("smoke_counsel_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["smoke_counsel_pack"] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_seed_complete():
    assert SEED.is_dir()
    for rel in mod.REQUIRED_SEED:
        assert (SEED / rel).is_file(), rel


def test_smoke_counsel_pack_e2e():
    assert mod.main([]) == 0


def test_smoke_persists_to_matter_dir(tmp_path):
    matter = tmp_path / "SYN-SMOKE-COUNSEL"
    assert mod.main(["--matter-dir", str(matter)]) == 0
    assert (matter / "02_outputs" / "trial_gap_report.md").is_file()
    assert (matter / "02_outputs" / "outgoing_rfp_set.md").is_file()
