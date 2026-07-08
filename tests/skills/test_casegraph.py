"""Tests for casegraph — per-matter case file index + verification gates.

Covers the SPEC.md test plan including adversarial/red-team cases: stale
index, duplicate bates, fabricated citations, foreign-prefix contamination,
fingerprint cross-matter detection (incl. sub-spans and homoglyphs),
unreadable-document degradation, allowlist suppression, strict mode, exit
codes, and write containment (nothing outside .casegraph / the explicit
fingerprint store). Synthetic data only; stdlib + pytest.

Run: python -m pytest tests/skills/test_casegraph.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CASEGRAPH = REPO_ROOT / "skills" / "legal" / "casegraph" / "scripts" / "casegraph.py"


def _load():
    spec = importlib.util.spec_from_file_location("casegraph", CASEGRAPH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cg = _load()


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def matter(tmp_path):
    """A synthetic matter with two production documents (TVRR prefix)."""
    m = tmp_path / "matter"
    prod = m / "production"
    prod.mkdir(parents=True)
    (prod / "TVRR-PROD-000001.md").write_text(
        "**Bates Range:** TVRR-PROD-000001 - TVRR-PROD-000002\n"
        "**Author:** R.K., Trainmaster, Test Valley Railroad\n"
        "**Custodian:** TVRR Safety Department\n"
        "**Date:** 2024-11-13\n\n"
        "The conductor reported an unsafe coupling procedure at Northgate Yard.\n",
        encoding="utf-8",
    )
    (prod / "TVRR-PROD-000003.md").write_text(
        "**Bates Range:** TVRR-PROD-000003 - TVRR-PROD-000003\n"
        "**Author:** L.M., Engineer, Test Valley Railroad\n"
        "**Date:** 2024-11-14\n\n"
        "Witness statement regarding track conditions.\n",
        encoding="utf-8",
    )
    assert cg.main(["init", str(m), "--matter-id", "SYN-A",
                    "--bates-prefix", "TVRR-PROD"]) == 0
    assert cg.main(["build", str(m)]) == 0
    return m


@pytest.fixture()
def other_matter(tmp_path):
    """A second, unrelated synthetic matter (NORF prefix, distinct people)."""
    m = tmp_path / "matter_b"
    prod = m / "production"
    prod.mkdir(parents=True)
    (prod / "NORF-PROD-000001.md").write_text(
        "**Bates Range:** NORF-PROD-000001 - NORF-PROD-000001\n"
        "**Author:** Dana Whitfield, Safety Officer, Northern Freight Lines\n\n"
        "Grade crossing incident involving Marcus Ellery at Cedar Junction.\n",
        encoding="utf-8",
    )
    assert cg.main(["init", str(m), "--matter-id", "SYN-B",
                    "--bates-prefix", "NORF-PROD"]) == 0
    assert cg.main(["build", str(m)]) == 0
    assert cg.main(["add-entity", str(m), "--name", "Marcus Ellery",
                    "--role", "plaintiff"]) == 0
    assert cg.main(["add-entity", str(m), "--name", "Cedar Junction",
                    "--role", "location"]) == 0
    return m


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ── parsing ─────────────────────────────────────────────────────────────────

class TestParsing:
    @pytest.mark.parametrize("value,expected", [
        ("TVRR-PROD-000001 - TVRR-PROD-000004", ("TVRR-PROD", 1, 4)),
        ("ACME-000010 through ACME-000012", ("ACME", 10, 12)),
        ("TVRR-PROD-000005 – TVRR-PROD-000007", ("TVRR-PROD", 5, 7)),  # en-dash
        ("TVRR-PROD-000009", ("TVRR-PROD", 9, 9)),
    ])
    def test_bates_range_parse(self, value, expected):
        assert cg.parse_bates_range(value) == expected

    def test_bates_from_filename(self):
        assert cg.bates_from_filename("TVRR-PROD-000123.pdf") == ("TVRR-PROD", 123)
        assert cg.bates_from_filename("notes.txt") is None

    def test_normalize_homoglyph_and_punct(self):
        # Fullwidth (NFKC), case, punctuation all normalize away.
        assert cg._normalize_identifier("Ｍarcus　Ellery") == "marcus ellery"
        assert cg._normalize_identifier("J.T.") == cg._normalize_identifier("j t")

    def test_header_fields(self):
        fields = cg.parse_header_fields("**Bates Range:** X-000001\n**Author:** A. Person\n")
        assert fields["bates_range"] == "X-000001"
        assert fields["author"] == "A. Person"


# ── build / status / dupes / unreadable ─────────────────────────────────────

class TestBuildAndStatus:
    def test_build_indexes_documents_and_bates(self, matter):
        rows = cg.load_documents(matter)
        assert len(rows) == 2
        by_rel = {r["relpath"]: r for r in rows}
        r1 = by_rel["production/TVRR-PROD-000001.md"]
        assert r1["bates_prefix"] == "TVRR-PROD"
        assert (r1["bates_start"], r1["bates_end"]) == (1, 2)
        assert r1["author"].startswith("R.K.")

    def test_status_current_then_stale(self, matter, capsys):
        assert cg.main(["status", str(matter)]) == 0
        # Add a new production document -> stale.
        _write(matter / "production" / "TVRR-PROD-000004.md",
               "**Bates Range:** TVRR-PROD-000004 - TVRR-PROD-000004\n\nSupplemental.\n")
        assert cg.main(["status", str(matter)]) == 1
        out = capsys.readouterr().out
        assert "STALE" in out and "TVRR-PROD-000004.md" in out
        # Rebuild -> current again.
        assert cg.main(["build", str(matter)]) == 0
        assert cg.main(["status", str(matter)]) == 0

    def test_status_detects_modified_file(self, matter):
        target = matter / "production" / "TVRR-PROD-000003.md"
        time.sleep(0.01)
        target.write_text(target.read_text(encoding="utf-8") + "\nEdited.\n",
                          encoding="utf-8")
        os.utime(target)  # ensure mtime moves even on coarse filesystems
        assert cg.main(["status", str(matter)]) == 1

    def test_exact_duplicates_marked(self, matter):
        src = matter / "production" / "TVRR-PROD-000001.md"
        dup = matter / "production" / "copy_of_000001.md"
        dup.write_bytes(src.read_bytes())
        assert cg.main(["build", str(matter)]) == 0
        rows = {r["relpath"]: r for r in cg.load_documents(matter)}
        assert rows["production/copy_of_000001.md"]["dupes_of"] == \
            "production/TVRR-PROD-000001.md"
        assert rows["production/TVRR-PROD-000001.md"]["dupes_of"] is None

    def test_unreadable_pdf_flagged_not_guessed(self, matter, capsys):
        # A corrupt/no-text-layer PDF must index as unreadable, never crash.
        (matter / "production" / "scan_TVRR-PROD-000010.pdf").write_bytes(
            b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nnot really a pdf body")
        assert cg.main(["build", str(matter)]) == 0
        rows = {r["relpath"]: r for r in cg.load_documents(matter)}
        row = rows["production/scan_TVRR-PROD-000010.pdf"]
        assert row["text_extractable"] in ("none", "unsupported")
        # Bates still recovered from the filename.
        assert row["bates_prefix"] == "TVRR-PROD" and row["bates_start"] == 10
        assert "UNREADABLE" in capsys.readouterr().out

    def test_incremental_build_skips_unchanged(self, matter, capsys):
        assert cg.main(["build", str(matter), "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["unchanged"] == 2 and report["new"] == 0

    def test_write_containment(self, matter, tmp_path):
        """build/gates must write only under .casegraph (and the explicit
        fingerprint store) — never into the production tree."""
        before = {p.as_posix() for p in (matter / "production").rglob("*")}
        out = _write(tmp_path / "o.md", "Cites TVRR-PROD-000001.")
        cg.main(["verify-cites", str(matter), str(out)])
        cg.main(["check-isolation", str(matter), str(out)])
        cg.main(["build", str(matter)])
        after = {p.as_posix() for p in (matter / "production").rglob("*")}
        assert before == after


# ── verify-cites ────────────────────────────────────────────────────────────

class TestVerifyCites:
    def test_pass_on_resolvable_citations(self, matter, tmp_path):
        out = _write(tmp_path / "o.md",
                     "Fact A (TVRR-PROD-000001). Fact B (TVRR-PROD-000003).")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 0

    def test_fail_on_fabricated_citation(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md", "Fact (TVRR-PROD-000099).")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 1
        assert "TVRR-PROD-000099" in capsys.readouterr().out

    def test_range_interior_resolves(self, matter, tmp_path):
        # 000002 is interior to doc 1's range (000001-000002).
        out = _write(tmp_path / "o.md", "See TVRR-PROD-000002.")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 0

    def test_foreign_prefix_is_not_verify_cites_job(self, matter, tmp_path):
        # Foreign prefixes are the isolation gate's job; verify-cites must not
        # double-report them (avoids two gates fighting over one finding).
        out = _write(tmp_path / "o.md", "See NORF-PROD-000001.")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 0

    def test_quote_verification(self, matter, tmp_path, capsys):
        good = _write(tmp_path / "good.md",
                      'Report says "unsafe coupling procedure at Northgate Yard" '
                      "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(good), "--quotes"]) == 0
        bad = _write(tmp_path / "bad.md",
                     'Report says "the brakeman ignored three separate radio warnings" '
                     "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(bad), "--quotes"]) == 1
        assert "quote not found" in capsys.readouterr().out

    def test_missing_output_file_is_usage_error(self, matter):
        assert cg.main(["verify-cites", str(matter), str(matter / "nope.md")]) == 2


# ── check-isolation ─────────────────────────────────────────────────────────

class TestIsolation:
    def test_foreign_bates_prefix_fails(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md", "See NORF-PROD-000001 for details.")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 1
        assert "foreign bates prefix 'NORF-PROD'" in capsys.readouterr().out

    def test_registered_entity_passes(self, matter, tmp_path):
        cg.main(["add-entity", str(matter), "--name", "Northgate Yard",
                 "--role", "location"])
        out = _write(tmp_path / "o.md",
                     "Incident at Northgate Yard (TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0

    def test_unregistered_name_warns_but_passes(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md", "Interviewed Harold Quimby yesterday.")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "WARN" in capsys.readouterr().out

    def test_strict_mode_fails_on_warns(self, matter, tmp_path):
        out = _write(tmp_path / "o.md", "Interviewed Harold Quimby yesterday.")
        assert cg.main(["check-isolation", str(matter), str(out), "--strict"]) == 1

    def test_allowlist_suppresses_legal_terms(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md",
                     "Claim under the Federal Employers Liability Act; "
                     "Requests for Production served; Pain and Suffering damages.")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "WARN" not in capsys.readouterr().out

    def test_fingerprint_detects_other_matter_entity(
            self, matter, other_matter, tmp_path, capsys):
        store = tmp_path / "fp.json"
        assert cg.main(["export-fingerprint", str(other_matter),
                        "--store", str(store)]) == 0
        out = _write(tmp_path / "o.md",
                     "Witness Marcus Ellery observed the coupling "
                     "(TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out),
                        "--fingerprints", str(store)]) == 1
        assert "registered to matter 'SYN-B'" in capsys.readouterr().out

    def test_fingerprint_homoglyph_variant_detected(
            self, matter, other_matter, tmp_path):
        # Fullwidth homoglyphs normalize (NFKC) before hashing.
        store = tmp_path / "fp.json"
        cg.main(["export-fingerprint", str(other_matter), "--store", str(store)])
        out = _write(tmp_path / "o.md", "Spoke with Ｍarcus Ｅllery today.")
        assert cg.main(["check-isolation", str(matter), str(out),
                        "--fingerprints", str(store)]) == 1

    def test_own_matter_fingerprint_not_self_flagged(
            self, matter, other_matter, tmp_path):
        # Both matters export; the active matter's own identifiers must not
        # trigger a cross-matter FAIL against its own fingerprint entry.
        store = tmp_path / "fp.json"
        cg.main(["export-fingerprint", str(matter), "--store", str(store)])
        cg.main(["export-fingerprint", str(other_matter), "--store", str(store)])
        cg.main(["add-entity", str(matter), "--name", "Northgate Yard"])
        cg.main(["export-fingerprint", str(matter), "--store", str(store)])
        out = _write(tmp_path / "o.md",
                     "Incident at Northgate Yard (TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out),
                        "--fingerprints", str(store)]) == 0

    def test_fingerprint_store_contains_no_plaintext(
            self, other_matter, tmp_path):
        store = tmp_path / "fp.json"
        cg.main(["export-fingerprint", str(other_matter), "--store", str(store)])
        blob = store.read_text(encoding="utf-8").lower()
        assert "marcus" not in blob and "ellery" not in blob
        assert "cedar" not in blob and "whitfield" not in blob


# ── entities & query ────────────────────────────────────────────────────────

class TestEntitiesAndQuery:
    def test_header_entities_harvested(self, matter):
        entities = cg.load_entities(matter)
        assert cg._normalize_identifier("Test Valley Railroad") in entities
        assert cg._normalize_identifier("Trainmaster") in entities

    def test_query_bates(self, matter, capsys):
        assert cg.main(["query", str(matter), "--bates", "TVRR-PROD-000002"]) == 0
        hit = json.loads(capsys.readouterr().out)
        assert hit[0]["relpath"] == "production/TVRR-PROD-000001.md"

    def test_query_grep_uses_text_cache(self, matter, capsys):
        assert cg.main(["query", str(matter), "--grep", "coupling"]) == 0
        hits = json.loads(capsys.readouterr().out)
        assert any("coupling" in h["text"] for h in hits)

    def test_query_unknown_bates_exits_nonzero(self, matter, capsys):
        assert cg.main(["query", str(matter), "--bates", "TVRR-PROD-000999"]) == 1


# ── misc ────────────────────────────────────────────────────────────────────

class TestMisc:
    def test_init_refuses_double_init(self, matter):
        assert cg.main(["init", str(matter), "--matter-id", "X"]) == 2

    def test_selftest_green(self, capsys):
        assert cg.main(["selftest"]) == 0
        assert "selftest: PASS" in capsys.readouterr().out
