import re
import unittest
from pathlib import Path


class SensitiveCommandLoggingTests(unittest.TestCase):
    def test_password_bearing_commands_never_log_arguments(self) -> None:
        source = Path("src/interp.c").read_text(encoding="latin-1")

        for command in (
            "password",
            "delet",
            "delete",
            "pkill",
            "remort",
            "resetpwd",
        ):
            pattern = re.compile(
                rf'\{{\s*"{re.escape(command)}"\s*,[^\n]*\bLOG_NEVER\b'
            )
            self.assertRegex(
                source,
                pattern,
                msg=f"{command} must remain LOG_NEVER because it accepts a password",
            )


if __name__ == "__main__":
    unittest.main()
