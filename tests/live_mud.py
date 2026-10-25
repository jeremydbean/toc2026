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

import ctypes
import os
import re
import shutil
import signal
import socket
import zlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_AREA = ROOT / "tests" / "fixtures" / "area" / "ztestfix.are"
# The fixture area's vnums (LiveMud(fixtures=True)).
SPARRING_GUARD = 32700        # mob: sentinel, never flees or starts a fight
SPARRING_FLOOR = 32700        # room: north to the gallery
SPARRING_GALLERY = 32701
GAS_HALL = 32702              # room: west to GAS_HALL_EXIT
GAS_HALL_EXIT = 32703
WEST_PADDOCK = 32704          # outdoors: east to EAST_PADDOCK
EAST_PADDOCK = 32705

# Telnet control bytes and the options the server implements.
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
TELOPT_ECHO, TELOPT_NAWS, TELOPT_MSSP, TELOPT_GMCP, TELOPT_COMPRESS2 = (
    1, 31, 70, 201, 86
)
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
    # TOC_SERVER_BINARY picks one explicitly -- the CI sanitizer job and a
    # local ASan build use it to play real sessions under the sanitizers.
    chosen = os.environ.get("TOC_SERVER_BINARY")
    if chosen:
        path = Path(chosen).resolve()
        return path if path.is_file() and os.access(path, os.X_OK) else None
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


# What an AddressSanitizer, LeakSanitizer or UBSan report looks like in the
# server's output. halt_on_error stops the server, but a report written at
# shutdown -- after the last assertion, in LiveMud.__exit__ -- used to go
# unread: the test had already passed. Every LiveMud now reads its server's
# output when it stops and fails the test on one of these.
SANITIZER_REPORT_RE = re.compile(
    r"ERROR: (?:AddressSanitizer|LeakSanitizer|MemorySanitizer|ThreadSanitizer)"
    r"|SUMMARY: (?:AddressSanitizer|UndefinedBehaviorSanitizer)"
    r"|runtime error: ")

# The reply to WORTH. MudClient.sync sends it after a command: the game
# runs one connection's commands in order, so once this line has arrived,
# so has everything the command said -- lag and all -- without guessing a
# window. A mortal's goes on to experience, staff's ends at "silver and N
# copper." -- both are the barrier. WORTH needs POS_SLEEPING or better: a
# character mortally wounded, incapacitated or stunned is told "You are
# hurt far too bad for that." and the barrier never comes (a stinking cloud
# left a walker at -7 hit points, 2026-10-25); use barrier="time" there.
BARRIER_RE = re.compile(
    r"You have -?\d+ platinum, -?\d+ gold, -?\d+ silver(?:, -?\d+ copper\s+and| and -?\d+ copper\.)")
# TIME's answer, for a barrier any position may type (TIME is POS_DEAD):
# its system-time line, and the moon line that follows when one is up.
TIME_BARRIER_RE = re.compile(
    r"The system time is [^\n]*\n\r?"
    r"(?:(?:A New Moon is in the sky|A Crescent Moon is in the sky|A Full Moon is up)\.\n?\r?)?")
BARRIERS = {"worth": BARRIER_RE, "time": TIME_BARRIER_RE}


def _die_with_parent() -> None:
    """Ask Linux to SIGKILL a server whose test process dies.

    A cancelled CI job or a killed module takes its Python process down
    with SIGKILL, which runs no __exit__; without this its servers kept
    their ports and burned CPU for the rest of the job.
    """
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        PR_SET_PDEATHSIG = 1
        libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL)
    except (OSError, AttributeError):
        pass


def _artifact_dir() -> Path | None:
    """Where this test may leave evidence, if the runner asked for it.

    scripts/ci/run_tests.py sets TOC_TEST_ARTIFACTS per module and
    run_module.py sets TOC_CURRENT_TEST per test. Only the throwaway world
    is ever written there: server output, synthetic transcripts and the
    test world's own log/ -- never real player files.
    """
    base = os.environ.get("TOC_TEST_ARTIFACTS")
    if not base:
        return None
    test = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.environ.get("TOC_CURRENT_TEST", "unknown"))
    return Path(base) / test[-150:]


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

    def server_state(self) -> str:
        """What the server process is doing, for a timeout message.

        A stalled game loop and a dead process look identical from the
        client, and the difference decides where to look next. When the
        process is wedged and gdb is available, grab a backtrace while it is
        still stuck -- that is the only moment the evidence exists.
        """
        proc = getattr(self, "server_proc", None)
        if proc is None:
            return "server: unknown (no handle)"
        code = proc.poll()
        if code is not None:
            return f"server: exited with code {code} (so it died)"

        state = "server: still running (so the game loop stalled)"
        gdb = shutil.which("gdb")
        if gdb is None:
            return state + "\n(install gdb for a backtrace of the stall)"
        try:
            result = subprocess.run(
                [gdb, "-p", str(proc.pid), "-batch", "-nx",
                 "-ex", "thread apply all bt 25"],
                capture_output=True, text=True, timeout=30,
            )
            trace = (result.stdout or result.stderr).strip()
        except (OSError, subprocess.SubprocessError) as exc:
            trace = f"(gdb failed: {exc})"
        return state + "\n--- stalled server backtrace ---\n" + trace[-3000:]

    def expect(self, *patterns: str, timeout: float | None = None) -> str:
        """Wait until any pattern appears (case-insensitive substring).

        Returns the pattern that matched. Raises AssertionError with the
        transcript on timeout, which is what makes failures debuggable.
        """
        deadline = time.monotonic() + (timeout or self.timeout)
        hung_up = False
        while time.monotonic() < deadline:
            haystack = self.buffer.lower()
            for pattern in patterns:
                index = haystack.find(pattern.lower())
                if index != -1:
                    # Consume through the match so the next expect moves on.
                    self.buffer = self.buffer[index + len(pattern):]
                    return pattern
            if not self._pump():
                # The peer hung up. Whatever it said on the way out is still
                # in the buffer and still counts -- "Wrong password." arrives
                # immediately before the close.
                haystack = self.buffer.lower()
                for pattern in patterns:
                    index = haystack.find(pattern.lower())
                    if index != -1:
                        self.buffer = self.buffer[index + len(pattern):]
                        return pattern
                hung_up = True
                break
        # Which of the two it was leads the message: CI reprints only a
        # failure's first line, and "the server hung up without saying it"
        # is a different bug from "the server was too slow to say it".
        tail = " ".join(self.buffer.split())[-160:]
        raise AssertionError(
            f"{'server hung up before' if hung_up else 'timed out waiting for'} "
            f"{patterns!r}; last output: {tail!r}.\n"
            f"{self.server_state()}\n"
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

    def sync(self, line: str, timeout: float | None = None, barrier: str = "worth") -> str:
        """Send a command and return exactly its reply, however late.

        A fixed drain window is a guess: it is too short when the command
        waits out the last one's lag, or the server is slow (the sanitizer
        build), and the reply then lands in the next command's window. Here
        WORTH follows the command and its reply marks the end: the game
        answers one connection's commands in order, so everything between
        the two is this command's. Output that is not a reply -- a tick,
        a wandering mobile -- can still arrive in between; assert on what
        the command says, not on the absence of everything else. Do not
        sync the barrier command itself.

        The barrier is typed input: it is a command the character sends,
        so it counts down lag like any other and is logged. Never sync a
        command whose test proves something happens with nothing typed
        after it (WIMPY firing on its own after KILL); listen with expect().
        barrier="time" works in every position, WORTH only from sleeping up.
        """
        pattern = BARRIERS[barrier]
        deadline = time.monotonic() + (timeout or self.timeout)
        mark = len(self.transcript)
        self.send(line)
        self.send(barrier)
        while time.monotonic() < deadline:
            found = pattern.search(self.transcript, mark)
            if found:
                self.buffer = self.transcript[found.end():]
                return self.transcript[mark:found.start()]
            if not self._pump():
                break
        raise AssertionError(
            f"no reply to {line!r} within {timeout or self.timeout:.0f}s; "
            f"last output: {' '.join(self.transcript[mark:].split())[-200:]!r}.\n"
            f"{self.server_state()}\n--- transcript ---\n{self.transcript[-4000:]}")

    def must(self, line: str, *expected: str, timeout: float | None = None) -> str:
        """sync(line), and fail unless the reply says one of `expected`.

        A setup command is confirmed by what it says it did, never by the
        absence of an error: SET MOB on a shipped prototype answers "came
        with the game" -- no "Syntax" in it -- and a test that asserted
        only that took a refusal for a sentinel guard (2026-10-25)."""
        reply = self.sync(line, timeout)
        if not any(text in reply for text in expected):
            raise AssertionError(
                f"{line!r} did not answer any of {expected!r}; it said: "
                f"{' '.join(reply.split())[:800]!r}")
        return reply


class LiveMud:
    """Boot a real server against a throwaway data tree."""

    def __init__(self, extra_env: dict[str, str] | None = None,
                 expect_crash: bool = False, fixtures: bool = False):
        self.extra_env = extra_env or {}
        # fixtures=True loads tests/fixtures/area/ztestfix.are into this
        # world as a built area: rooms 32700-32705 joined to nothing, and
        # the sparring guard (mob 32700), a sentinel that never flees or
        # starts a fight. A shipped mobile is no fixture: SET MOB refuses
        # every prototype that came with the game, so a test that made the
        # Korzath guard "sentinel" that way was quietly refused and the
        # guard wandered off anyway (CI, 2026-10-25).
        self.fixtures = fixtures
        self.port = free_port()
        self.tmp: tempfile.TemporaryDirectory | None = None
        self.proc: subprocess.Popen | None = None
        self.root: Path | None = None
        self._output_path: Path | None = None
        self._clients: list[MudClient] = []
        # A test that crashes the server on purpose (test_playlog's SIGSEGV)
        # says so; anything else that leaves a sanitizer report fails.
        self.expect_crash = expect_crash
        self._outputs: list[Path] = []

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
        #
        # Runtime state is left behind, though. These four are written by
        # the running game and are no part of a fresh world: a working
        # copy carries the live board, so a test that writes its own note
        # found it numbered 23 behind a thousand real ones from the year
        # 2000. Clearing them after the copy does not work either --
        # notes are read into memory at boot and written back out from
        # there -- so they have to be missing before the server starts.
        shutil.copytree(
            ROOT / "area", self.root / "area",
            ignore=shutil.ignore_patterns(
                "notes.txt", "bugs.txt", "typos.txt", "ideas.txt",
                "bugs.txt.*", "typos.txt.*", "ideas.txt.*",
                # A test world must not inherit somebody's benchmark
                # board, for the same reason it must not inherit notes.
                "dpsboard.txt", "dpsboard.txt.tmp"))
        for name in ("player", "gods", "heroes", "corpse", "backups", "log"):
            (self.root / name).mkdir()
        if self.fixtures:
            built = self.root / "area" / "built"
            built.mkdir(exist_ok=True)
            shutil.copy2(FIXTURE_AREA, built / FIXTURE_AREA.name)
            listing = built / "built.lst"
            lines = [line for line in (listing.read_text().split() if listing.exists() else [])
                     if line != "$"]
            lines.append(f"built/{FIXTURE_AREA.name}")
            listing.write_text("\n".join(lines + ["$"]) + "\n")
        (self.root / "player" / "versions").mkdir()

        self._launch()
        return self

    def _launch(self) -> None:
        binary = find_binary()
        assert binary is not None, "no server binary; check skip_reason() first"

        env = dict(os.environ)
        # Hermie at the altar for six hours after every boot is the live
        # game's; several tests count every spellup mobile, so a test world
        # starts without her. Pass extra_env={"TOC_NO_BOOT_HERMIE": ""} and
        # pop it to see her (tests/test_spellup_mob.py does).
        env.setdefault("TOC_NO_BOOT_HERMIE", "1")
        # The calendar must not decide what a test sees: from Oct 18 the
        # game boots the Halloween copies of dresden, limbo and midennir,
        # and from Dec 16 the Christmas ones, which rename rooms the tests
        # look for. Pass extra_env={"TOC_SEASON": "halloween"} to see one.
        env.setdefault("TOC_SEASON", "none")
        # A treasure goblin appears somewhere at boot and wanders; a test
        # world starts without one so it cannot walk into somebody's
        # assertions. Pass extra_env={"TOC_NO_GOBLIN": None} to see him.
        env.setdefault("TOC_NO_GOBLIN", "1")
        # Area disasters (disaster_update) strike an occupied area at
        # random: an earthquake damages and stuns everyone in it, which
        # once landed between a fixture's two commands in CI. Pass
        # extra_env={"TOC_NO_DISASTERS": None} to allow them.
        env.setdefault("TOC_NO_DISASTERS", "1")
        env.update(self.extra_env)
        for key, value in self.extra_env.items():
            if value is None:
                env.pop(key, None)

        # To a file, not a pipe: log_string writes to stderr and nothing
        # read the pipe while the game ran, so a session that logged 64 KiB
        # would block the server in write() mid-test -- a hang that would
        # look like a slow reply.
        self._output_path = self.root / "server-output.log"
        if self._output_path not in self._outputs:
            self._outputs.append(self._output_path)
        output = open(self._output_path, "ab")
        try:
            self.proc = subprocess.Popen(
                [str(binary), str(self.port)],
                cwd=self.root / "area",
                stdout=output,
                stderr=subprocess.STDOUT,
                env=env,
                preexec_fn=_die_with_parent if sys.platform.startswith("linux") else None,
            )
        finally:
            output.close()
        self._wait_for_port()

    def restart(self) -> None:
        """Stop and boot again on the same tree, for testing persistence."""
        self._stop()
        self._launch()

    def _stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=15)
        self.proc = None

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
        # __exit__ never runs when __enter__ raises, so nothing else would
        # stop a server that is still booting.
        if self.proc is not None:
            self.proc.kill()
            self.proc.wait(timeout=15)
        raise AssertionError(
            f"server did not open port {self.port}:\n" + self.server_output()
        )

    def server_output(self) -> str:
        """The last 4000 characters the server wrote, so far."""
        path = self._output_path
        if path is None:
            return "<no output captured>"
        try:
            return path.read_bytes().decode("latin-1", "replace")[-4000:]
        except OSError:
            return "<output unavailable>"

    def connect(self, timeout: float = 30.0) -> MudClient:
        client = MudClient(self.port, timeout=timeout)
        # So a timeout can report whether the server died or stalled.
        client.server_proc = self.proc
        self._clients.append(client)
        return client

    def sanitizer_report(self) -> str | None:
        """The first sanitizer report the server wrote, with some context."""
        for path in self._outputs:
            try:
                text = path.read_bytes().decode("latin-1", "replace")
            except OSError:
                continue
            found = SANITIZER_REPORT_RE.search(text)
            if found:
                start = text.rfind("\n", 0, max(0, found.start() - 2000)) + 1
                return text[start:found.start() + 6000]
        return None

    def _save_artifacts(self) -> None:
        dest = _artifact_dir()
        if dest is None or self.root is None:
            return
        try:
            dest = dest / f"port-{self.port}"
            dest.mkdir(parents=True, exist_ok=True)
            if self._output_path is not None and self._output_path.exists():
                data = self._output_path.read_bytes()
                (dest / "server-output.log").write_bytes(data[-400_000:])
            for n, client in enumerate(self._clients, 1):
                (dest / f"client-{n}.txt").write_text(client.transcript[-200_000:],
                                                      encoding="latin-1", errors="replace")
            log_dir = self.root / "log"
            if log_dir.is_dir():
                for item in log_dir.iterdir():
                    if item.is_file() and item.stat().st_size < 2_000_000:
                        shutil.copy2(item, dest / f"log-{item.name}")
        except OSError:
            pass

    def __exit__(self, exc_type, exc, tb) -> None:
        report = None
        try:
            self._stop()
            report = None if self.expect_crash else self.sanitizer_report()
            self._save_artifacts()
        finally:
            if self.tmp is not None:
                self.tmp.cleanup()
        if report is not None:
            message = "the server wrote a sanitizer report:\n" + report
            if exc_type is None:
                raise AssertionError(message)
            # The test failed already; keep its error and add the report.
            print(message, file=sys.stderr)


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


def room_of(staff: MudClient, name: str) -> int:
    """The room a character stands in, by STAT -- the server's word,
    not a guess from a transcript."""
    reply = staff.must(f"stat char {name}", "Room:")
    match = re.search(r"Room: (-?\d+)", reply)
    assert match, reply
    return int(match.group(1))


def place_sparring_guard(staff: MudClient, staff_name: str, room: int) -> None:
    """Load the fixture world's sparring guard into `room` and prove it:
    the staff character is there, the guard is made, and STAT says it is
    a sentinel standing in that room. Needs LiveMud(fixtures=True)."""
    staff.sync(f"goto {room}")
    here = room_of(staff, staff_name)
    assert here == room, f"{staff_name} is in {here}, not {room}"
    staff.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
    stat = staff.must("stat mob sparring", "Vnum: %d" % SPARRING_GUARD)
    assert re.search(r"Room: %d\b" % room, stat), stat
    assert re.search(r"Act 1:.*\bsentinel\b", stat), stat
