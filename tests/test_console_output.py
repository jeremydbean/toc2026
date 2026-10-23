"""Include the dependency-free browser decoder tests when Node.js is available."""
import pathlib
import shutil
import subprocess
import unittest


class ConsoleOutputTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for browser decoder tests')
    def test_streaming_decoder(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which('node'), '--test', str(root / 'tests/test_console_output.js')],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for browser decoder tests')
    def test_web_colours(self):
        """Bright backgrounds, reverse video, exact 256 and true colour in
        both consoles and their stylesheets (tests/test_ansi_web.js)."""
        root = pathlib.Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which('node'), '--test', str(root / 'tests/test_ansi_web.js')],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
