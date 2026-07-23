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
    # Never write __pycache__ into skills/legal/ — the legal validator
    # privacy-scans that tree and fails (correctly, fail-closed) on binary
    # .pyc artifacts.
    import sys
    sys.dont_write_bytecode = True
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
        assert cg.bates_from_filename("TVRR-PROD-000123.pdf") == ("TVRR-PROD", 123, 123)
        assert cg.bates_from_filename("notes.txt") is None
        assert cg.bates_from_filename("Plaintiff 000001-12.pdf") == ("PLAINTIFF", 1, 12)
        assert cg.bates_from_filename("Plaintiff 000013 - 17.pdf") == ("PLAINTIFF", 13, 17)
        assert cg.bates_from_filename("Plaintiff 000101 - 110.pdf") == ("PLAINTIFF", 101, 110)
        assert cg.bates_from_filename("Plaintiff 000187.pdf") == ("PLAINTIFF", 187, 187)
        # Short end token with borrow from start padding
        assert cg.bates_from_filename("ACME-000100-05.pdf") == ("ACME", 100, 105)

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
        out = capsys.readouterr().out
        assert "UNREADABLE" in out or "OCR QUEUE" in out
        queue = matter / ".casegraph" / "needs_ocr.json"
        assert queue.exists()
        payload = json.loads(queue.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 2
        assert payload["count"] >= 1
        queued = next(
            d for d in payload["documents"]
            if "scan_TVRR-PROD-000010.pdf" in d["relpath"]
        )
        # ocrmypdf only when extract status is none/partial; unsupported
        # (no usable PDF parser path) routes to manual_or_vision.
        if row["text_extractable"] in ("none", "partial"):
            assert queued["recommended_action"] == "ocrmypdf"
        else:
            assert queued["recommended_action"] == "manual_or_vision"
        assert "Docling is an optional" in payload["guidance"]
        assert cg.main(["export-ocr-queue", str(matter)]) == 1

    def test_ocr_queue_write_retries_transient_replace_denial(self, matter, monkeypatch):
        calls = {"count": 0}
        original_replace = cg.os.replace

        def flaky_replace(src, dst):
            calls["count"] += 1
            if calls["count"] == 1:
                raise PermissionError("transient Windows file lock")
            return original_replace(src, dst)

        monkeypatch.setattr(cg.os, "replace", flaky_replace)
        path = cg.write_ocr_queue(
            matter,
            [{"relpath": "production/scan_TVRR-PROD-000010.pdf", "text_extractable": "none"}],
            "SYN-A",
        )
        assert calls["count"] == 2
        assert path.exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["count"] == 1

    def test_incremental_build_skips_unchanged(self, matter, capsys):
        assert cg.main(["build", str(matter), "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["unchanged"] == 2 and report["new"] == 0

    def test_incremental_filename_widen_respects_header(self, tmp_path):
        """Stale single-page index + batch filename must not beat header range.

        Red-team: filename ``Plaintiff 000001-12`` with header 000001-000002
        must not expand to 1-12 on an mtime-stable rebuild (cite laundering).
        """
        m = tmp_path / "matter"
        prod = m / "production"
        prod.mkdir(parents=True)
        (prod / "Plaintiff 000001-12.md").write_text(
            "**Bates Range:** PLAINTIFF-000001 - PLAINTIFF-000002\n\n"
            "Narrow header range; filename claims a wider batch.\n",
            encoding="utf-8",
        )
        assert cg.main(["init", str(m), "--matter-id", "SYN-BATCH",
                        "--bates-prefix", "PLAINTIFF"]) == 0
        assert cg.main(["build", str(m)]) == 0
        docs_path = m / ".casegraph" / "documents.jsonl"
        poisoned = []
        for line in docs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "Plaintiff" in row.get("relpath", ""):
                row["bates_end"] = row["bates_start"]  # stale single-page stamp
            poisoned.append(row)
        docs_path.write_text(
            "\n".join(json.dumps(r) for r in poisoned) + "\n", encoding="utf-8"
        )
        assert cg.main(["build", str(m)]) == 0
        rows = cg.load_documents(m)
        row = next(r for r in rows if "Plaintiff" in r["relpath"])
        assert row["bates_start"] == 1 and row["bates_end"] == 2
        out = tmp_path / "o.md"
        out.write_text("Fact (PLAINTIFF-000008).\n", encoding="utf-8")
        assert cg.main(["verify-cites", str(m), str(out), "--no-quotes"]) == 1

    def test_write_containment(self, matter, tmp_path):
        """build/gates must write only under .casegraph (and the explicit
        fingerprint store) — never into the production tree."""
        before = {p.as_posix() for p in (matter / "production").rglob("*")}
        out = _write(tmp_path / "o.md", "Cites TVRR-PROD-000001.")
        cg.main(["verify-cites", str(matter), str(out), "--no-quotes"])
        cg.main(["check-isolation", str(matter), str(out)])
        cg.main(["build", str(matter)])
        after = {p.as_posix() for p in (matter / "production").rglob("*")}
        assert before == after


# ── verify-cites ────────────────────────────────────────────────────────────

class TestVerifyCites:
    def test_pass_on_resolvable_citations(self, matter, tmp_path):
        out = _write(tmp_path / "o.md",
                     "Fact A (TVRR-PROD-000001). Fact B (TVRR-PROD-000003).")
        assert cg.main(["verify-cites", str(matter), str(out), "--no-quotes"]) == 0

    def test_fail_on_fabricated_citation(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md", "Fact (TVRR-PROD-000099).")
        assert cg.main(["verify-cites", str(matter), str(out), "--no-quotes"]) == 1
        assert "TVRR-PROD-000099" in capsys.readouterr().out

    def test_range_interior_resolves(self, matter, tmp_path):
        # 000002 is interior to doc 1's range (000001-000002).
        out = _write(tmp_path / "o.md", "See TVRR-PROD-000002.")
        assert cg.main(["verify-cites", str(matter), str(out), "--no-quotes"]) == 0

    def test_foreign_prefix_is_not_verify_cites_job(self, matter, tmp_path):
        # Foreign prefixes are the isolation gate's job; verify-cites must not
        # double-report them as unresolved. With fail-closed empty-cite policy,
        # foreign-only text still needs --allow-empty to pass (zero same-matter
        # cites), but must not emit an "unresolved citation: NORF-..." failure.
        out = _write(tmp_path / "o.md", "See NORF-PROD-000001.")
        assert cg.main(["verify-cites", str(matter), str(out),
                        "--allow-empty", "--no-quotes"]) == 0

    def test_empty_citations_fail_closed(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md", "Narrative facts with no Doc IDs.")
        assert cg.main(["verify-cites", str(matter), str(out), "--no-quotes"]) == 1
        assert "no same-matter Bates citations" in capsys.readouterr().out

    def test_quote_verification(self, matter, tmp_path, capsys):
        good = _write(tmp_path / "good.md",
                      'Report says "unsafe coupling procedure at Northgate Yard" '
                      "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(good)]) == 0
        bad = _write(tmp_path / "bad.md",
                     'Report says "the brakeman ignored three separate radio warnings" '
                     "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(bad)]) == 1
        assert "quote not found" in capsys.readouterr().out

    def test_curly_quote_verification(self, matter, tmp_path):
        good = _write(tmp_path / "good.md",
                      "Report says \u201cunsafe coupling procedure at Northgate Yard\u201d "
                      "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(good)]) == 0

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

    def test_all_caps_multiword_name_still_checked(self, matter, tmp_path, capsys):
        # Multi-word ALL-CAPS must not be skipped as a heading (red-team P1-5).
        out = _write(tmp_path / "o.md", "Spoke with HAROLD QUIMBY at the yard.")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "HAROLD QUIMBY" in capsys.readouterr().out

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


# ── verify-chronology ───────────────────────────────────────────────────────

class TestVerifyChronology:
    """Dated chronology events must trace to documents that contain the date."""

    CHRONO_OK = (
        "## Chronology\n\n"
        "Date: 2024-11-13\n"
        "Event: Incident report authored.\n"
        "Source: TVRR-PROD-000001\n\n"
    )
    # Doc 000001's text says 2024-11-13 (its Date header); 2024-12-25 appears nowhere.
    CHRONO_WRONG_DATE = (
        "## Chronology\n\n"
        "Date: 2024-12-25\n"
        "Event: Alleged holiday inspection.\n"
        "Source: TVRR-PROD-000001\n\n"
    )
    CHRONO_BAD_CITE = (
        "## Chronology\n\n"
        "Date: 2024-11-13\n"
        "Event: Phantom document event.\n"
        "Source: TVRR-PROD-000099\n\n"
    )

    def test_date_found_in_cited_doc_passes(self, matter, tmp_path):
        out = _write(tmp_path / "c.md", self.CHRONO_OK)
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 0

    def test_date_absent_warns_and_strict_fails(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "c.md", self.CHRONO_WRONG_DATE)
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 0
        assert "not found in any cited document" in capsys.readouterr().out
        assert cg.main(["verify-chronology", str(matter), str(out), "--strict"]) == 1

    def test_unresolved_citation_fails(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "c.md", self.CHRONO_BAD_CITE)
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 1
        assert "unresolved citation" in capsys.readouterr().out

    def test_date_variant_renderings_match(self, matter, tmp_path):
        # Doc says "2024-11-13" in its header; also add a doc with prose date.
        prod = matter / "production"
        _write(prod / "TVRR-PROD-000005.md",
               "**Bates Range:** TVRR-PROD-000005 - TVRR-PROD-000005\n\n"
               "On November 14, 2024 the crew reported the defect.\n")
        assert cg.main(["build", str(matter)]) == 0
        out = _write(tmp_path / "c.md",
                     "Date: 2024-11-14\nEvent: Defect reported.\n"
                     "Source: TVRR-PROD-000005\n")
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 0

    def test_entry_without_citation_fails_closed(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "c.md",
                     "Date: 2024-11-13\nEvent: No source given.\n")
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 1
        assert "no same-matter Bates Source" in capsys.readouterr().out
        assert cg.main(["verify-chronology", str(matter), str(out),
                        "--allow-uncited"]) == 0

    def test_chronology_heading_without_dates_fails(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "c.md",
                     "## Chronology\n\nNo parseable dates here, just prose.\n")
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 1
        assert "no parseable dated rows" in capsys.readouterr().out
        assert cg.main(["verify-chronology", str(matter), str(out),
                        "--allow-empty-chronology"]) == 0


# ── receipt-run hardening (2026-07-08): prose false-positives, declared
# ranges, table chronology, meta-quotes ──────────────────────────────────────

class TestProseFalsePositives:
    """The permissive bates regex must not fire on ordinary legal prose."""

    def test_months_and_sections_are_not_foreign_bates(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md",
                     "In November 2024 and again February 2025, per Section 218 "
                     "and Part 218, TVRR filed responses (TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "foreign bates" not in capsys.readouterr().out

    def test_issue_codes_are_not_foreign_bates(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md",
                     "Tagged DAM-001 and PROC-002; contradiction CONTRA-001 "
                     "(TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "foreign bates" not in capsys.readouterr().out

    def test_real_foreign_bates_still_fails(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md", "See NORF-PROD-000123 (TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 1
        assert "NORF-PROD" in capsys.readouterr().out

    def test_headings_and_table_rows_do_not_warn(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "o.md",
                     "# Production Gap Analysis\n\n"
                     "| Document Inventory | Attorney Review Flag |\n"
                     "|---|---|\n"
                     "| Payroll Records | Yes |\n\n"
                     "Cited to TVRR-PROD-000001.\n")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "WARN" not in capsys.readouterr().out

    def test_name_in_field_value_still_warns(self, matter, tmp_path, capsys):
        # Label is skipped, but a person NAME in the value must still WARN.
        out = _write(tmp_path / "o.md",
                     "Witness: Harold Quimby stated facts (TVRR-PROD-000001).")
        assert cg.main(["check-isolation", str(matter), str(out)]) == 0
        assert "Harold Quimby" in capsys.readouterr().out


class TestDeclaredRanges:
    """Cover-letter declared ranges are inventory signals, not cite grounding.
    Default verify-cites FAILs declared-not-indexed; --allow-declared-gaps
    opts into gap-analysis INFO treatment. Filename-only 'cover letter'
    must not harvest ranges (laundering vector)."""

    @pytest.fixture()
    def matter_with_cover(self, matter):
        _write(matter / "production" / "cover_letter.md",
               "**Document Type:** Production Cover Letter\n\n"
               "Produced herewith: Personnel File TVRR-PROD-000200 through "
               "TVRR-PROD-000210; Inspection Reports TVRR-PROD-000220 to 000230.\n")
        assert cg.main(["build", str(matter)]) == 0
        return matter

    def test_declared_not_indexed_fails_by_default(
            self, matter_with_cover, tmp_path, capsys):
        out = _write(tmp_path / "o.md",
                     "Listed as produced at TVRR-PROD-000205 (TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter_with_cover), str(out),
                        "--no-quotes"]) == 1
        assert "declared-not-indexed" in capsys.readouterr().out

    def test_allow_declared_gaps_opts_into_info(
            self, matter_with_cover, tmp_path, capsys):
        out = _write(tmp_path / "o.md",
                     "Listed as produced at TVRR-PROD-000205 (TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter_with_cover), str(out),
                        "--no-quotes", "--allow-declared-gaps"]) == 0
        assert "declared-not-indexed" in capsys.readouterr().out

    def test_outside_declared_ranges_still_fails(self, matter_with_cover, tmp_path):
        out = _write(tmp_path / "o.md", "See TVRR-PROD-000299 (TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter_with_cover), str(out),
                        "--no-quotes"]) == 1

    def test_filename_alone_does_not_declare_ranges(self, matter, tmp_path, capsys):
        # Plant a file named cover_letter.md WITHOUT Document Type — must not
        # harvest ranges or launder cites (red-team P1-6).
        _write(matter / "production" / "cover_letter.md",
               "Produced herewith: TVRR-PROD-000200 through TVRR-PROD-000210.\n")
        assert cg.main(["build", str(matter)]) == 0
        out = _write(tmp_path / "o.md",
                     "See TVRR-PROD-000205 (TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(out), "--no-quotes"]) == 1
        assert "declared-not-indexed" not in capsys.readouterr().out


class TestChronologyTableLayout:
    def test_table_rows_are_verified(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "c.md",
                     "| Date | Event | Source |\n|---|---|---|\n"
                     "| 2024-11-13 | Report authored | TVRR-PROD-000001 |\n")
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 0
        assert "1 dated+cited entries" in capsys.readouterr().out

    def test_table_row_wrong_date_warns(self, matter, tmp_path, capsys):
        out = _write(tmp_path / "c.md",
                     "| 2019-01-01 | Impossible event | TVRR-PROD-000001 |\n")
        assert cg.main(["verify-chronology", str(matter), str(out)]) == 0
        assert "not found in any cited document" in capsys.readouterr().out


class TestMetaQuotes:
    def test_gate_language_quotes_are_not_checked(self, matter, tmp_path):
        out = _write(tmp_path / "o.md",
                     'Marked "evidence supports an inference of negligence here" '
                     "and cited TVRR-PROD-000001.")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 0

    def test_adjacent_quotes_do_not_cross_pair(self, matter, tmp_path):
        """A short quotation followed by a real one must not cross-pair the
        first's closing mark with the second's opening mark and 'verify' the
        prose between them (receipt-run finding)."""
        out = _write(tmp_path / "o.md",
                     'Says lighting "always dim." Unquoted filler prose here. '
                     'Then quotes the "unsafe coupling procedure at Northgate Yard" '
                     "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 0

    def test_cross_paired_fabrication_still_caught(self, matter, tmp_path):
        # The REAL quoted span (odd parity) that is absent must still fail.
        out = _write(tmp_path / "o.md",
                     'Says "dim." then "the brakeman ignored three radio warnings" '
                     "(TVRR-PROD-000001).")
        assert cg.main(["verify-cites", str(matter), str(out)]) == 1

    def test_ellipsis_trimmed_before_match(self, matter, tmp_path):
        out = _write(tmp_path / "o.md",
                     'Report noted an "unsafe coupling procedure at Northgate Yard…" '
                     "(TVRR-PROD-000001).")
        # Fixture contains the words without the trailing ellipsis.
        assert cg.main(["verify-cites", str(matter), str(out)]) == 0


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
