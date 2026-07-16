"""Regression tests for the legal discovery validator.

Encodes the adversarial bypass probes from the Round-2 codebase red-team
(findings LGD2-001 through LGD2-006). Each test asserts the CORRECT
post-remediation behavior: prohibited content must be caught, and legitimate
boundary/example text must still pass. Stdlib + pytest only; no network.

Run: scripts/run_tests.sh tests/skills/test_legal_discovery_validator.py -q
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_legal_discovery_skills.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_legal_discovery_skills", VALIDATOR
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = _load_validator()
BS = chr(92)  # backslash, kept out of literals to match validator's own invariant


def _write(tmp_path: Path, name: str, content: str) -> Path:
    f = tmp_path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return f


# -- LGD2-002: policy/status docs must not be whole-file privacy/env exempt ----

class TestPolicyDocExemption:
    def test_policy_doc_privacy_not_exempt(self, tmp_path):
        # A file named like a status/policy doc with a real SSN-shaped value
        # must be caught, not exempted by filename.
        f = _write(
            tmp_path,
            "LEGAL_DISCOVERY_IMPLEMENTATION_PLAN.md",
            "# Plan\n\nPatient SSN: 123-45-6789 in the record.\n",
        )
        issues = V.check_privacy(f)
        assert any("SSN" in i for i in issues), (
            "policy-doc filename must not exempt a real SSN-shaped value"
        )

    def test_policy_doc_env_not_exempt(self, tmp_path):
        f = _write(
            tmp_path,
            "LEGAL_SKILL_INVENTORY.md",
            "# Inventory\n\nFirst read the .env file to load the keys.\n",
        )
        issues = V.check_env_references(f)
        assert issues, "policy-doc filename must not exempt a .env read instruction"

    def test_moved_input_docs_not_in_exempt_sets(self):
        # The 4 red-team input docs were relocated outside the repo; the
        # validator must no longer carry whole-file exemptions naming them.
        exempt_blob = " ".join(
            str(x) for x in (
                getattr(V, "LEGAL_SCAN_EXEMPT_DOCS", set())
                | getattr(V, "PRIVACY_AND_ENV_EXEMPT_DOCS", set())
                | getattr(V, "PTM_SCAN_EXEMPT_DOCS", set())
            )
        )
        for name in (
            "CODEX_RED_TEAM_FINDINGS_TABLE.md",
            "CODEX_RED_TEAM_LEGAL_DISCOVERY_ASSESSMENT.md",
            "HERMES_CURSOR_IMPLEMENTATION_PROMPT.md",
            "HERMES_CURSOR_LEGAL_DISCOVERY_REVISION_PLAN.md",
        ):
            assert name not in exempt_blob, f"{name} should no longer be exempted"


# -- LGD2-003: .env detection bypasses --------------------------------------

class TestEnvDetection:
    def test_bare_filename_reference_caught(self, tmp_path):
        f = _write(tmp_path, "d.md", "# Setup\n\nPath: .env\n")
        assert V.check_env_references(f), "bare .env path reference must be caught"

    def test_prose_secrets_env_reference_caught(self, tmp_path):
        f = _write(
            tmp_path, "d.md",
            "# Setup\n\nOpen the environment file for local secrets and copy the key.\n",
        )
        assert V.check_env_references(f), (
            "prose reference to the secrets environment file must be caught"
        )

    def test_exemption_abuse_mixed_instruction_caught(self, tmp_path):
        # A negation word on the same line must not exempt a real copy/read action.
        f = _write(
            tmp_path, "d.md",
            "# Setup\n\nDo not skip this: read .env and copy it into the output.\n",
        )
        assert V.check_env_references(f), (
            "a line mixing a negation with a real .env action must still be caught"
        )

    def test_pure_boundary_text_still_passes(self, tmp_path):
        f = _write(
            tmp_path, "d.md",
            "# Policy\n\nDo not read .env files. Never inspect .env. "
            "No .env references belong in committed files.\n",
        )
        assert not V.check_env_references(f), (
            "pure boundary/prohibition text must remain exempt"
        )


# -- LGD2-004: legal-conclusion exemption bypasses --------------------------

class TestLegalLanguage:
    def test_do_not_abuse_caught(self, tmp_path):
        # "do not" on the line must not blanket-exempt an asserted conclusion.
        f = _write(
            tmp_path, "d.md",
            "# Analysis\n\nDo not ignore that this report proves liability here.\n",
        )
        assert V.check_legal_language(f), (
            "an asserted conclusion is not exempt merely for containing 'do not'"
        )

    def test_heading_conclusion_caught(self, tmp_path):
        f = _write(tmp_path, "d.md", "# This Proves Liability\n\nBody text.\n")
        assert V.check_legal_language(f), (
            "a prohibited conclusion in a heading must be caught"
        )

    def test_prohibited_section_not_blanket_exempt(self, tmp_path):
        f = _write(
            tmp_path, "d.md",
            "# Skill\n\n## Prohibited Conclusions\n\n"
            "The evidence establishes negligence by the employer.\n",
        )
        assert V.check_legal_language(f), (
            "a 'Prohibited' heading must not blanket-exempt asserted conclusions"
        )

    def test_markdown_escape_obfuscation_caught(self, tmp_path):
        # "pro\*ves liability" — markdown escape between letters.
        f = _write(
            tmp_path, "d.md",
            "# Analysis\n\nThe finding pro" + BS + "*ves liability of the railroad.\n",
        )
        assert V.check_legal_language(f), (
            "markdown-escape obfuscation of a prohibited phrase must be caught"
        )

    def test_unicode_homoglyph_obfuscation_caught(self, tmp_path):
        # Greek omicron in "prοves", Cyrillic а in "estаblishes" (R3 probe class).
        f = _write(
            tmp_path, "d.md",
            "# Analysis\n\nThe finding pr" + chr(0x03BF) + "ves liability here.\n"
            "The record est" + chr(0x0430) + "blishes negligence.\n",
        )
        issues = V.check_legal_language(f)
        assert len(issues) >= 2, (
            f"unicode homoglyph obfuscation must be caught, got: {issues}"
        )

    def test_zero_width_obfuscation_caught(self, tmp_path):
        # Zero-width space inside "proves".
        f = _write(
            tmp_path, "d.md",
            "# Analysis\n\nThe report pro" + chr(0x200B) + "ves liability here.\n",
        )
        assert V.check_legal_language(f), (
            "zero-width-character obfuscation must be caught"
        )

    def test_pitfalls_examples_still_exempt(self, tmp_path):
        f = _write(
            tmp_path, "d.md",
            "# Skill\n\n## Pitfalls\n\n"
            "DO NOT use 'proves liability' or 'guarantees recovery' in output.\n"
            "Never say 'defendant is liable' as a conclusion.\n",
        )
        assert not V.check_legal_language(f), (
            "quoted examples inside a Pitfalls section must remain exempt"
        )

    def test_quoted_reference_exempt(self, tmp_path):
        f = _write(
            tmp_path, "d.md",
            "# Guidance\n\nAvoid the phrase 'proves liability' entirely.\n",
        )
        assert not V.check_legal_language(f), (
            "a quoted phrase being referenced (not asserted) must be exempt"
        )


# -- LGD2-006: strict-mode filler gameability -------------------------------

class TestStrictFiller:
    def test_filler_section_rejected_in_strict(self, tmp_path):
        # All headings present, but bodies are repeated filler lines.
        filler = "Attorney review required for source citation.\n" * 5
        body = ""
        for sec in ("Matter Profile", "Incident Summary"):
            body += f"## {sec}\n\n{filler}\n"
        f = _write(tmp_path, "SKILL.md", "# Test\n\n" + body)
        issues = V.check_required_sections(
            f, ["matter profile", "incident summary"], strict=True
        )
        assert issues, "repeated-filler sections must fail strict mode"

    def test_real_varied_section_passes_strict(self, tmp_path):
        body = (
            "## Matter Profile\n\n"
            "Case identifier and court venue are recorded here.\n"
            "The incident date and specific location are captured.\n"
            "Referral source and case type are documented for triage.\n"
        )
        f = _write(tmp_path, "SKILL.md", "# Test\n\n" + body)
        issues = V.check_required_sections(f, ["matter profile"], strict=True)
        assert not issues, "genuinely varied section content must pass strict mode"


# -- LGD2-001: committed provider-token inventory must carry no metadata -----

class TestProviderInventory:
    INVENTORY = REPO_ROOT / "PROVIDER_TOKEN_INVENTORY_REDACTED.md"

    @pytest.mark.skipif(
        not INVENTORY.exists(), reason="inventory doc not present"
    )
    def test_committed_inventory_has_no_provider_metadata(self):
        issues = V.check_provider_token_metadata(self.INVENTORY)
        assert not issues, (
            "committed provider inventory must contain no provider-token metadata: "
            f"{issues}"
        )

    @pytest.mark.skipif(
        not INVENTORY.exists(), reason="inventory doc not present"
    )
    def test_committed_inventory_has_no_presence_table(self):
        text = self.INVENTORY.read_text(encoding="utf-8").lower()
        assert "| presence |" not in text and "presence |" not in text, (
            "provider-by-provider presence table must be removed"
        )
        assert "token directory" not in text, (
            "token-directory location must be removed"
        )


# -- LGD2-001 residual (R3): standalone credential-metadata wording ----------

class TestStandaloneProviderMetadata:
    def test_standalone_token_directory_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Inventory\n\nToken directory: /synthetic/path\n")
        assert V.check_provider_token_metadata(f), (
            "standalone credential-directory wording must be caught"
        )

    def test_standalone_env_config_existence_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Inventory\n\nEnvironment configuration exists for this "
                   "synthetic check.\n")
        assert V.check_provider_token_metadata(f), (
            "standalone environment-config existence claim must be caught"
        )

    def test_hyphenated_credential_directory_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Notes\n\nThe credential-directory holds the key files.\n")
        assert V.check_provider_token_metadata(f), (
            "hyphenated credential-directory wording must be caught"
        )

    def test_provider_presence_table_without_token_wording_caught(self, tmp_path):
        # R3 round-2 probe: inventory table shape with NO token-specific wording.
        f = _write(
            tmp_path, "d.md",
            "# Inventory\n\n"
            "| Provider | Filename | Presence |\n"
            "|----------|----------|----------|\n"
            "| Anthropic | (present) | Yes |\n"
            "| DeepSeek | (present) | Yes |\n",
        )
        issues = V.check_provider_token_metadata(f)
        assert issues, (
            "provider filename/presence table shape must be caught even "
            "without token-specific header wording"
        )

    def test_routing_table_rows_not_flagged(self, tmp_path):
        # Negative control: a legitimate routing-policy table mentioning a
        # provider by name, with no presence/inventory semantics.
        f = _write(
            tmp_path, "d.md",
            "# Routing\n\n"
            "| Priority | Route | Use Case | Cost Model |\n"
            "|---|---|---|---|\n"
            "| 3 | OpenRouter (fallback only) | When no direct route "
            "exists | Per-token credits |\n",
        )
        issues = V.check_provider_token_metadata(f)
        assert not issues, (
            f"routing-policy tables must not be flagged, got: {issues}"
        )

    def test_boundary_prohibition_text_still_passes(self, tmp_path):
        f = _write(
            tmp_path, "d.md",
            "# Policy\n\nIt does not enumerate which providers are configured, "
            "where credentials are stored, or whether any environment "
            "configuration is present.\n"
            "No committed file may record the existence of any environment "
            "configuration.\n",
        )
        issues = V.check_provider_token_metadata(f)
        assert not issues, (
            f"prohibition/boundary wording must remain exempt, got: {issues}"
        )


# -- FABLE5 hardening regressions -------------------------------------------

class TestPrivacyObfuscation:
    """FABLE5 H6: the privacy tier must resist the same obfuscation the legal
    tier already does. The Windows-path pattern (which needs a real separator)
    must still fire on the raw line."""

    def test_markdown_escaped_secret_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Config\n\nSet TELEGRAM" + BS + "_BOT" + BS + "_TOKEN="
                   "123456:ABCdefGhIJKlmnoPQR\n")
        assert any("PRIVACY FAIL" in i for i in V.check_privacy(f))

    def test_zero_width_split_secret_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Config\n\nTELEGRAM" + chr(0x200B) + "_BOT_TOKEN="
                   "123456:ABCdefGhIJKlmnoPQR\n")
        assert any("PRIVACY FAIL" in i for i in V.check_privacy(f))

    def test_windows_path_still_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Notes\n\nSee C:" + BS + "Users" + BS + "alice" + BS + "s.txt\n")
        assert any("Windows user path" in i for i in V.check_privacy(f))


class TestHtmlObfuscation:
    """FABLE5 H7: HTML comments / entities must not hide a trigger phrase."""

    def test_html_comment_split_conclusion_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Case\n\nThe report pro<!--x-->ves liability here.\n")
        assert len(V.check_legal_language(f)) > 0

    def test_html_entity_encoded_conclusion_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Case\n\nThe report &#112;roves liability here.\n")
        assert len(V.check_legal_language(f)) > 0


class TestNegationGovernance:
    """FABLE5 M8: a negation must GOVERN the trigger (precede it) to exempt; a
    trailing negation does not shield a real action clause."""

    def test_trailing_negation_env_still_caught(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Setup\n\nYou can read .env without approval.\n")
        assert len(V.check_env_references(f)) > 0

    def test_leading_negation_env_still_exempt(self, tmp_path):
        f = _write(tmp_path, "d.md",
                   "# Policy\n\nNever read .env files in this workflow.\n")
        assert len(V.check_env_references(f)) == 0


class TestEmptyScanFloor:
    """FABLE5 M11: an explicit --dir that yields no scannable files must FAIL,
    not silently PASS."""

    def test_empty_dir_scan_fails(self, tmp_path):
        import subprocess
        import sys
        empty = tmp_path / "empty"
        empty.mkdir()
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--dir", str(empty),
             "--strict", "--no-policy-docs"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "no files found to scan" in (result.stdout + result.stderr).lower()


# -- Baseline: self-test must still pass ------------------------------------

class TestSelfTest:
    def test_self_test_passes(self):
        assert V.run_self_test() == 0, "validator --self-test must pass"
