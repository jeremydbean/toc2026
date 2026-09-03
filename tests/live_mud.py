"""Support code for driving a real ToC server over Telnet.

Everything here is deliberately isolated from live data. The game resolves its
mutable paths relative to the working directory (`PLAYER_DIR "../player/"` and
friends in `src/merc.h`), so running a server from a throwaway `area/` copy
sends every character file, log, corpse, and backup it writes into a temporary
tree. Real `player/`, `gods/`, and `heroes/` data is never touched, which is
what AGENTS.md requires.

Stdlib only, so this runs anywhere the built binary runs.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# The Make build writes ./merc; CMake writes ./bin/rom. Either will do.
CANDIDATE_BINARIES = (ROOT / "merc", ROOT / "bin" / "rom")

# IAC-prefixed telnet negotiation and ANSI colour both show up mid-stream and
# would break naive prompt matching.
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
IAC_SIMPLE_RE = re.compile(rb"\xff[\xfb-\xfe].", re.DOTALL)   # WILL/WONT/DO/DONT
IAC_SUBNEG_RE = re.compile(rb"\xff\xfa.*?\xff\xf0", re.DOTALL)  # SB ... SE
IAC_TWO_BYTE_RE = re.compile(rb"\xff[\xf1-\xf9]")             # GA, NOP, etc.


def find_binary() -> Path | None:
    for candidate in CANDIDATE_BINARIES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def skip_reason() -> str | None:
    """Why a live test cannot run here, or None if it can."""
    if sys.platform.startswith("win"):
        return (
            "the game is POSIX-only; run these tests from WSL, Linux, or macOS"
        )
    if find_binary() is None:
        return "no built server binary (run `make` or the CMake build first)"
    return None


def clean(data: bytes) -> str:
    """Strip telnet negotiation and ANSI colour, normalise line endings."""
    data = IAC_SUBNEG_RE.sub(b"", data)
    data = IAC_SIMPLE_RE.sub(b"", data)
    data = IAC_TWO_BYTE_RE.sub(b"", data)
    data = ANSI_RE.sub(b"", data)
    text = data.decode("latin-1")
    return text.replace("\n\r", "\n").replace("\r\n", "\n").replace("\r", "\n")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class MudClient:
    """A minimal expect-style Telnet client."""

    def __init__(self, port: int, timeout: float = 30.0):
        self.timeout = timeout
        self.buffer = ""
        self.transcript = ""
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.settimeout(0.5)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> "MudClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _pump(self) -> bool:
        """Read whatever is available. False once the peer has hung up."""
        try:
            chunk = self.sock.recv(8192)
        except socket.timeout:
            return True
        except OSError:
            return False
        if not chunk:
            return False
        text = clean(chunk)
        self.buffer += text
        self.transcript += text
        return True

    def expect(self, *patterns: str, timeout: float | None = None) -> str:
        """Wait until any pattern appears (case-insensitive substring).

        Returns the pattern that matched. Raises AssertionError with the
        transcript on timeout, which is what makes failures debuggable.
        """
        deadline = time.monotonic() + (timeout or self.timeout)
        while time.monotonic() < deadline:
            haystack = self.buffer.lower()
            for pattern in patterns:
                index = haystack.find(pattern.lower())
                if index != -1:
                    # Consume through the match so the next expect moves on.
                    self.buffer = self.buffer[index + len(pattern):]
                    return pattern
            if not self._pump():
                break
        raise AssertionError(
            f"timed out waiting for {patterns!r}.\n"
            f"--- transcript ---\n{self.transcript[-4000:]}"
        )

    def drain(self, seconds: float = 0.6) -> str:
        """Collect output for a moment; useful before asserting on a screen."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not self._pump():
                break
        return self.transcript

    def send(self, line: str = "") -> None:
        self.sock.sendall(line.encode("latin-1") + b"\n")

    def command(self, line: str, settle: float = 0.5) -> str:
        """Send a command and return the output it produced."""
        self.buffer = ""
        mark = len(self.transcript)
        self.send(line)
        deadline = time.monotonic() + settle
        while time.monotonic() < deadline:
            if not self._pump():
                break
        return self.transcript[mark:]


class LiveMud:
    """Boot a real server against a throwaway data tree."""

    def __init__(self, extra_env: dict[str, str] | None = None):
        self.extra_env = extra_env or {}
        self.port = free_port()
        self.tmp: tempfile.TemporaryDirectory | None = None
        self.proc: subprocess.Popen | None = None
        self.root: Path | None = None

    @property
    def player_dir(self) -> Path:
        assert self.root is not None
        return self.root / "player"

    def __enter__(self) -> "LiveMud":
        self.tmp = tempfile.TemporaryDirectory(prefix="toc-live-")
        self.root = Path(self.tmp.name)

        # A full copy, not symlinks: the server writes into its working
        # directory (shutdown.txt, *.dmp, pkill data), and symlinks would
        # write straight back into the repository.
        shutil.copytree(ROOT / "area", self.root / "area")
        for name in ("player", "gods", "heroes", "corpse", "backups", "log"):
            (self.root / name).mkdir()
        (self.root / "player" / "versions").mkdir()

        binary = find_binary()
        assert binary is not None, "no server binary; check skip_reason() first"

        env = dict(os.environ)
        env.update(self.extra_env)

        self.proc = subprocess.Popen(
            [str(binary), str(self.port)],
            cwd=self.root / "area",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        self._wait_for_port()
        return self

    def _wait_for_port(self, timeout: float = 120.0) -> None:
        """World boot parses ~7,800 rooms, and more under sanitizers."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                raise AssertionError(
                    "server exited during boot:\n" + self.server_output()
                )
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1.0):
                    return
            except OSError:
                time.sleep(0.25)
        raise AssertionError(
            f"server did not open port {self.port}:\n" + self.server_output()
        )

    def server_output(self) -> str:
        if self.proc is None or self.proc.stdout is None:
            return "<no output captured>"
        try:
            self.proc.kill()
        except OSError:
            pass
        try:
            return self.proc.stdout.read().decode("latin-1", "replace")[-4000:]
        except Exception:
            return "<output unavailable>"

    def connect(self, timeout: float = 30.0) -> MudClient:
        return MudClient(self.port, timeout=timeout)

    def __exit__(self, *exc) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=15)
        if self.proc is not None and self.proc.stdout is not None:
            self.proc.stdout.close()
        if self.tmp is not None:
            self.tmp.cleanup()


# Prompt -> reply table for character creation. Driven by matching whatever
# the server actually asks rather than a fixed script, so an extra or skipped
# step (immortal MOTD, alignment, customisation) does not break the walk.
CREATION_STEPS = (
    ("did i get that right", "Y"),
    ("give me a password", None),          # filled in with the password
    ("retype password", None),
    ("what is your race", "human"),
    ("what is your sex", "m"),
    ("select a class", "warrior"),
    ("which alignment", "n"),
    ("customize this character", "N"),
    ("pick a weapon", "sword"),
    ("press enter", ""),
    ("[hit return to continue]", ""),
)


def create_character(client: MudClient, name: str, password: str) -> None:
    """Walk a brand new character from the greeting into the game."""
    client.expect("by what name", "name:", "what is your name")
    client.send(name)

    # Bounded prompt-driven loop: answer whatever is asked until the game
    # starts sending normal play output.
    for _ in range(40):
        client.drain(0.4)
        haystack = client.buffer.lower()

        if not haystack.strip():
            client.send("")
            continue

        for needle, reply in CREATION_STEPS:
            if needle in haystack:
                client.buffer = ""
                client.send(password if reply is None else reply)
                break
        else:
            # No creation prompt outstanding: assume we are in the game.
            return
    raise AssertionError(
        "character creation did not finish.\n"
        f"--- transcript ---\n{client.transcript[-4000:]}"
    )
