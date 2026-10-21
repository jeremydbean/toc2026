"""The browser consoles' command lines, end to end.

tests/test_command_sequence.js holds TocCommandSequence.encode to its
rules. The live half sends the very lines encode produces, as the
browser's WebSocket bridge would, through the game's own input path --
the composition the audit (2026-10-21) found broken: the browser split a
line, the game split each piece again, and "say left\\;quit" quit.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import unittest

from live_mud import LiveMud, create_character, skip_reason

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
SKIP = skip_reason()
PASSWORD = "Zbrowser12"

ENCODE = r"""
const seq = require(process.argv[1]);
const aliases = { zk: "say {args}" };
function resolve(command, escape) {
    const [key, ...rest] = command.trim().split(/\s+/);
    const template = aliases[key.toLowerCase()];
    if (!template) return null;
    return template.replaceAll("{args}", escape(rest.join(" ")));
}
const lines = JSON.parse(process.argv[2]).map((l) => seq.encode(l, resolve).line);
process.stdout.write(JSON.stringify(lines));
"""


def encode(lines: list[str]) -> list[str]:
    result = subprocess.run(
        [NODE, "-e", ENCODE, str(ROOT / "webadmin" / "static" / "command-sequence.js"),
         json.dumps(lines)],
        capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipUnless(NODE, "Node.js is required for the browser command tests")
class CommandSequenceUnitTests(unittest.TestCase):
    def test_encode(self) -> None:
        result = subprocess.run(
            [NODE, "--test", str(ROOT / "tests" / "test_command_sequence.js")],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_both_consoles_send_the_line_whole(self) -> None:
        client = (ROOT / "webadmin" / "static" / "client.js").read_text()
        app = (ROOT / "webadmin" / "static" / "app.js").read_text()
        self.assertIn("TocCommandSequence.encode(command, expandAlias)", client)
        self.assertIn("sendTypedLine(input.value)", client)
        self.assertIn("state.terminal.socket.send(`${command}\\n`)", app)
        self.assertNotIn("sequence.commands", app)


@unittest.skipUnless(NODE, "Node.js is required for the browser command tests")
@unittest.skipIf(SKIP is not None, SKIP or "")
class BrowserLineLiveTests(unittest.TestCase):
    def test_what_the_browser_sends_is_read_as_typed(self) -> None:
        escaped, alias_line, aliased = encode([
            r"say left\;quit",
            "alias zpair say alpha;say omega",
            r"zk orc\;quit",
        ])
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbrowser", PASSWORD)
                said = run(client, escaped)
                self.assertIn("left;quit", said, said)
                self.assertIn("orc;quit", run(client, aliased), "a client alias's text stays text")
                run(client, alias_line)
                said = run(client, "zpair", 3.0)
                self.assertIn("alpha", said, said)
                self.assertIn("omega", said, said)
                # Still here: nothing above was read as QUIT.
                self.assertIn("You say 'still here'", run(client, "say still here"))
                client.send("quit")
                self.assertTrue(client.wait_closed())


if __name__ == "__main__":
    unittest.main()
