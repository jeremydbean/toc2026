import importlib.util
import pathlib
import stat
import tempfile
import unittest
from contextlib import redirect_stderr
import io


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deploy" / "toc2026_mail.py"
SPEC = importlib.util.spec_from_file_location("toc2026_mail", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
mail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mail)


class MailNotifierTests(unittest.TestCase):
    def write_config(self, directory: pathlib.Path, mode: int = 0o600) -> pathlib.Path:
        path = directory / "mail.env"
        path.write_text(
            "TOC_SMTP_HOST=mail.example.test\n"
            "TOC_SMTP_PORT=2525\n"
            "TOC_SMTP_SECURITY=starttls\n"
            "TOC_SMTP_USERNAME=appliance\n"
            "TOC_SMTP_PASSWORD=private-password\n"
            "TOC_MAIL_FROM=ToC Appliance <toc@example.test>\n"
            "TOC_MAIL_TO=owner@example.test\n"
            "TOC_MAIL_FAILURE_INTERVAL_SEC=3600\n",
            encoding="utf-8",
        )
        path.chmod(mode)
        return path

    def test_private_configuration_is_parsed_without_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self.write_config(pathlib.Path(temporary_directory))
            config = mail.read_config(path)

        self.assertEqual(config["TOC_SMTP_HOST"], "mail.example.test")
        self.assertEqual(config["TOC_SMTP_PORT"], "2525")
        self.assertEqual(config["_SENDER"], "toc@example.test")
        self.assertEqual(config["_RECIPIENTS"], "owner@example.test")

    def test_configuration_rejects_group_or_world_access(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self.write_config(pathlib.Path(temporary_directory), mode=0o640)
            with self.assertRaises(mail.MailConfigurationError):
                mail.read_config(path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_operational_logs_redact_credentials_and_client_ipv4(self):
        log = (
            "password=hunter2 token: abc123 X-Admin-Token=xyz\n"
            "connection from 198.51.100.42 username appliance\n"
        )
        sanitized = mail.sanitize_log(log, ["appliance"])

        for private_value in ("hunter2", "abc123", "xyz", "198.51.100.42", "appliance"):
            self.assertNotIn(private_value, sanitized)
        self.assertIn("[REDACTED]", sanitized)
        self.assertIn("[IP redacted]", sanitized)

    def test_network_identity_ignores_temporary_ipv6_and_public_lookup(self):
        first = {
            "active": "wlan0:wifi:connected:Home",
            "wifi": "yes:Home",
            "ipv4": "wlan0 UP 192.0.2.10/24",
            "ipv6": "wlan0 UP 2001:db8::1/64",
            "route": "default via 192.0.2.1 dev wlan0",
            "public_ipv4": "198.51.100.10",
        }
        second = dict(first)
        second["ipv6"] = "wlan0 UP 2001:db8::2/64"
        second["public_ipv4"] = "not checked"

        self.assertEqual(
            mail.network_fingerprint(first),
            mail.network_fingerprint(second),
        )

    def test_invalid_event_is_rejected_before_configuration_is_read(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(mail.main(["toc2026-mail", "unknown-event"]), 2)


if __name__ == "__main__":
    unittest.main()
