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
import zlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Telnet control bytes and the options the server implements.
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
TELOPT_NAWS, TELOPT_MSSP, TELOPT_GMCP, TELOPT_COMPRESS2 = 31, 70, 201, 86
MSSP_VAR, MSSP_VAL = 1, 2


def parse_mssp(payload: bytes) -> dict[str, str]:
    """Decode an MSSP subnegotiation body into a plain dict."""
    fields: dict[str, str] = {}
    # Body is a run of MSSP_VAR name MSSP_VAL value pairs.
    for chunk in payload.split(bytes([MSSP_VAR])):
        if not chunk:
            continue
        if bytes([MSSP_VAL]) not in chunk:
            continue
        name, _, value = chunk.partition(bytes([MSSP_VAL]))
        fields[name.decode("latin-1")] = value.decode("latin-1")
    return fields


def naws(width: int, height: int) -> bytes:
    """A client NAWS subnegotiation announcing a window size."""
    return (
        bytes([IAC, WILL, TELOPT_NAWS])
        + bytes([IAC, SB, TELOPT_NAWS])
        + width.to_bytes(2, "big")
        + height.to_bytes(2, "big")
        + bytes([IAC, SE])
    )

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
        self.raw = b""
        # MCCP2: everything after the IAC SB COMPRESS2 IAC SE acknowledgement
        # is a raw deflate stream, so the client has to switch mid-connection.
        self.compressed = False
        self._decomp = None
        self._pending = b""
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
        self._feed(chunk)
        return True

    def _absorb(self, data: bytes) -> None:
        if not data:
            return
        self.raw += data
        text = clean(data)
        self.buffer += text
        self.transcript += text

    def _feed(self, chunk: bytes) -> None:
        """Route bytes, switching to decompression at the MCCP handshake."""
        if self._decomp is not None:
            self._absorb(self._decomp.decompress(chunk))
            return

        self._pending += chunk
        ack = bytes([IAC, SB, TELOPT_COMPRESS2, IAC, SE])
        index = self._pending.find(ack)
        if index == -1:
            plain, self._pending = self._pending, b""
            self._absorb(plain)
            return

        # Plain up to the acknowledgement, deflate after it.
        self._absorb(self._pending[:index])
        self.raw += ack          # keep it visible for protocol assertions
        rest = self._pending[index + len(ack):]
        self._pending = b""
        self.compressed = True
        self._decomp = zlib.decompressobj()
        if rest:
            self._absorb(self._decomp.decompress(rest))

    def wait_closed(self, timeout: float = 20.0) -> bool:
        """Block until the server closes the connection.

        Quitting is the only reliable way to get a character out of the world,
        and the socket closing is the only reliable signal that it happened.
        Without waiting for it, a test that edits the player file can be
        racing a character that is still in memory -- and `login` answers the
        "already playing" prompt automatically, so the stale character comes
        back and the edit looks like it was ignored.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._pump():
                return True
        return False

    def send_raw(self, data: bytes) -> None:
        """Send bytes verbatim, for telnet negotiation."""
        self.sock.sendall(data)

    def subnegotiations(self, option: int) -> list[bytes]:
        """Every complete IAC SB <option> ... IAC SE payload seen so far."""
        found = []
        marker = bytes([IAC, SB, option])
        start = 0
        while True:
            index = self.raw.find(marker, start)
            if index == -1:
                return found
            body = index + len(marker)
            end = self.raw.find(bytes([IAC, SE]), body)
            if end == -1:
                return found
            found.append(self.raw[body:end])
            start = end

    def negotiated(self, verb: int, option: int) -> bool:
        """True if the server sent IAC <verb> <option>."""
        return bytes([IAC, verb, option]) in self.raw

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
        """Send a command and return the output it produced.

        Drains anything still in flight first. Login and room descriptions
        arrive in bursts, and without this the returned slice can be the tail
        of the previous screen rather than the reply to this command.
        """
        self.drain(0.4)
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


def _enter_game(client: MudClient, password: str | None = None) -> None:
    """Answer whatever the login/creation flow asks until the game responds.

    Detection is a positive probe rather than a prompt match. Waiting for the
    default prompt's "mv>" breaks for a character with a custom prompt or with
    `prompt` toggled off, and returning early is worse: the MOTD screens wait
    for a keypress, so the caller's first real command gets swallowed as that
    keypress.

    Exactly one line is sent per round. The server interprets roughly one
    command per player per pulse, so sending more than that per round builds a
    backlog that delays whatever the caller does next -- which showed up as a
    `quit` appearing not to run at all.
    """
    idle_rounds = 0

    for _ in range(60):
        client.drain(0.5)
        haystack = client.buffer.lower()

        if "you have" in haystack:          # `worth` answered: we are in.
            return
        if "wrong password" in haystack:
            raise AssertionError("login rejected the password")

        answered = False
        if password is not None:
            for needle, reply in CREATION_STEPS:
                if needle in haystack:
                    client.buffer = ""
                    client.send(password if reply is None else reply)
                    answered = True
                    idle_rounds = 0
                    break

        if answered:
            continue

        idle_rounds += 1
        client.buffer = ""
        if idle_rounds <= 3:
            client.send("")             # dismiss a pending screen
        else:
            client.send("worth")        # then probe for the game itself

    raise AssertionError(
        "never reached the game."
        + chr(10) + "--- transcript ---" + chr(10) + client.transcript[-4000:]
    )


def create_character(client: MudClient, name: str, password: str) -> None:
    """Walk a brand new character from the greeting into the game."""
    client.expect("by what name", "name:", "what is your name")
    client.send(name)
    _enter_game(client, password)


def login(client: MudClient, name: str, password: str) -> None:
    """Log an existing character in and wait until the game responds.

    Handles the "already playing, connect anyway?" prompt, which arrives
    after the password: a client socket closing races the server noticing, so
    a reconnect straight after a quit can still see the old descriptor.
    """
    client.expect("by what name", "name:")
    client.send(name)
    client.expect("password")
    client.send(password)

    # Clear the reconnect confirmation if it appears, then hand off.
    client.drain(0.6)
    if "y or n" in client.buffer.lower() or "connect anyway" in client.buffer.lower():
        client.buffer = ""
        client.send("Y")

    _enter_game(client)


def patch_player_file(mud: "LiveMud", name: str, **fields: object) -> None:
    """Rewrite fields in a saved character file.

    Used to set up state a fresh character cannot reach -- coins, a bank
    balance, an immortal level, a starting room. Editing the character's own
    saved file rather than writing one from scratch means the password hash is
    already correct, so no host crypt(3) binding is needed (Python removed the
    `crypt` module in 3.13). The character must have saved and quit first.

    Only ever touches the throwaway tree; see the module docstring.
    """
    path = mud.player_dir / name
    if not path.is_file():
        raise AssertionError("no saved player file for " + name)

    lines = path.read_text(encoding="latin-1").split("\n")
    for key, value in fields.items():
        replacement = "%s %s" % (key, value)
        for i, line in enumerate(lines):
            if line.split(" ")[0] == key:
                lines[i] = replacement
                break
        else:
            # Keys live before the terminating "End" of the player section.
            end = next(
                (i for i, line in enumerate(lines) if line.strip() == "End"),
                len(lines),
            )
            lines.insert(end, replacement)

    path.write_text("\n".join(lines), encoding="latin-1", newline="")


# A bank room, so deposit/withdraw are reachable. Rooms 4 and 9621 are the
# two carrying ROOM2_BANK in the shipped world.
BANK_ROOM_VNUM = 4


def make_funded_character(
    mud: "LiveMud",
    name: str,
    password: str,
    platinum: int = 10,
    gold: int = 20,
    silver: int = 30,
    copper: int = 40,
    bank_copper: int = 1000000,
) -> None:
    """Create a character, then fund it and stand it in a bank."""
    with mud.connect(timeout=120) as client:
        create_character(client, name, password)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(
                "character did not leave the world; editing its file now would "
                "race the copy still in memory"
            )

    patch_player_file(
        mud,
        name,
        NewPlat=platinum,
        NewGold=gold,
        NewSilv=silver,
        NewCopp=copper,
        BankCP=bank_copper,
        Room=BANK_ROOM_VNUM,
    )


COIN_VALUE = {"platinum": 1000000, "gold": 10000, "silver": 100, "copper": 1}


def coin_total(text: str) -> int:
    """Sum every '<n> <denomination>' pair in a fragment of game output."""
    return sum(
        int(count) * COIN_VALUE[unit]
        for count, unit in re.findall(
            r"(\d+) (platinum|gold|silver|copper)", text
        )
    )


def read_coins(client: MudClient, command: str, marker: str) -> int:
    """Run a money command and total the sentence it prints.

    Reads the buffer *after* the marker rather than scanning the transcript:
    the transcript still holds earlier money lines, and matching one of those
    is how a money test quietly measures the wrong thing.
    """
    client.send(command)
    client.expect(marker)
    client.drain(1.0)
    return coin_total(client.buffer.split(".")[0])


def carried_copper(client: MudClient) -> int:
    return read_coins(client, "worth", "You have")


def banked_copper(client: MudClient) -> int:
    return read_coins(client, "balance", "current balance is")
