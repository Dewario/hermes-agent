import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "scan_compat.py"
)
SPEC = importlib.util.spec_from_file_location("scan_compat", SCRIPT_PATH)
scan_compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan_compat)

DEPRECATED_CHAT = "deepseek" + "-chat"
DEPRECATED_OPENROUTER_CHAT = "deepseek/" + DEPRECATED_CHAT


class ScanCompatTests(unittest.TestCase):
    def scan_one(self, filename, content):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            (root / filename).write_text(content, encoding="utf-8")
            return scan_compat.scan_directory(root, "full", [])

    def test_active_code_deprecation_comment_still_critical(self):
        findings = self.scan_one(
            "active.py",
            f'MODEL = "{DEPRECATED_OPENROUTER_CHAT}"  # deprecated, replace later\n',
        )

        self.assertEqual(findings[0]["classification"], "CRITICAL")

    def test_native_deepseek_api_call_is_warning(self):
        findings = self.scan_one(
            "native.py",
            (
                'requests.post("https://api.deepseek.com/chat/completions", '
                f'json={{"model": "{DEPRECATED_CHAT}"}})\n'
            ),
        )

        self.assertEqual(findings[0]["classification"], "WARNING")

    def test_external_allow_marker_does_not_suppress_findings(self):
        findings = self.scan_one(
            "external.py",
            f'MODEL = "{DEPRECATED_CHAT}"  # compat-scanner:allow\n',
        )

        self.assertEqual(findings[0]["classification"], "CRITICAL")

    def test_external_scan_compat_file_allow_marker_does_not_suppress(self):
        findings = self.scan_one(
            "scan_compat.py",
            f'MODEL = "{DEPRECATED_CHAT}"  # compat-scanner:allow\n',
        )

        self.assertEqual(findings[0]["classification"], "CRITICAL")

    def test_documented_deprecation_is_ok(self):
        findings = self.scan_one(
            "notes.md",
            (
                f"The {DEPRECATED_CHAT} alias is deprecated; "
                "replacement is deepseek-v4-flash.\n"
            ),
        )

        self.assertEqual(findings[0]["classification"], "OK")

    def test_unacknowledged_doc_reference_is_warning(self):
        findings = self.scan_one(
            "notes.md",
            f"Example model: {DEPRECATED_CHAT}\n",
        )

        self.assertEqual(findings[0]["classification"], "WARNING")

    def test_findings_use_relative_paths_and_mask_sensitive_context(self):
        win_path = "C:" + "\\Users\\" + "ExampleUser" + "\\AppData\\Local\\hermes"
        secret_value = "s" + "k-" + "testvalue"
        delivery_target = "-" + "100" + "1234567890"
        findings = self.scan_one(
            "sensitive.py",
            (
                f'MODEL = "{DEPRECATED_CHAT}"; path = "{win_path}"; '
                f'secret = "{secret_value}"; target = "{delivery_target}"\n'
            ),
        )

        self.assertEqual(findings[0]["file"], "sensitive.py")
        self.assertIn("<USER_HOME>", findings[0]["context"])
        self.assertIn("<REDACTED_" + "API" + "_KEY>", findings[0]["context"])
        self.assertIn("<REDACTED_" + "CHAT" + "_ID>", findings[0]["context"])

    def test_generic_api_key_assignment_is_masked(self):
        key_name = "CUSTOM_SERVICE" + "_API_KEY"
        findings = self.scan_one(
            "sensitive.py",
            (
                f'MODEL = "{DEPRECATED_CHAT}"; '
                f'{key_name} = "abc123secret"\n'
            ),
        )

        self.assertIn(key_name + ' = "<REDACTED_API_KEY>"',
                      findings[0]["context"])

    def test_relative_exclude_handles_spaces(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            excluded = root / "folder with spaces"
            excluded.mkdir()
            (excluded / "active.py").write_text(
                f'MODEL = "{DEPRECATED_CHAT}"\n',
                encoding="utf-8",
            )

            findings = scan_compat.scan_directory(
                root, "full", ["folder with spaces"]
            )

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
