"""The website behind Caddy at timesofchaos.com (2026-11-12).

The dashboard moved from public port 9001 to 127.0.0.1:9001 behind a
reverse proxy (deploy/windows-vm/Caddyfile) on 80 and 443. Every request
then arrives from loopback, which made two real hazards:

- the game bridge's PROXY line named 127.0.0.1 for every web player, an
  address the game's connection guard and login lockouts exempt. Proxy
  mode (WEB_ADMIN_PROXY_HEADERS / --proxy-headers, off by default) takes
  the player's address and scheme from X-Forwarded-For/-Proto, believed
  only from a listed proxy (127.0.0.1);
- the local unlock trusts a loopback peer, and would have handed an admin
  session cookie to the whole internet. It is refused in proxy mode, and
  for any request carrying a forwarding header, and it reads the TCP peer
  (socket_peer), never the client a header rewrote.

The rest holds the host side together: the setup script
(deploy/windows-vm/toc-web-proxy) played with every host command stubbed,
the Caddyfile and the unit agreeing on 127.0.0.1:9001, and toc-deploy and
toc-restore installing the same unit.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import pathlib
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
VM = ROOT / "deploy" / "windows-vm"
SCRIPT = VM / "toc-web-proxy"
CADDYFILE = VM / "Caddyfile"
UNIT = VM / "toc-web.service"

try:
    from fastapi.testclient import TestClient
    from starlette.requests import Request
    from starlette.websockets import WebSocket

    TESTCLIENT_UNAVAILABLE_REASON = None
except Exception as exc:  # pragma: no cover - C-only environments skip
    TestClient = None
    TESTCLIENT_UNAVAILABLE_REASON = (
        f"web test client unavailable ({type(exc).__name__}: {exc}). "
        "Install both webadmin/requirements.txt and scripts/requirements.txt."
    )


def load_server():
    """webadmin.server, imported with throwaway paths and a known token."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "player").mkdir()
    env = {
        "WEB_ADMIN_TOKEN": "secret",
        "WEB_ADMIN_LOCAL_UNLOCK": "1",
        "WEB_ADMIN_PROXY_HEADERS": "0",
        "WEB_ADMIN_FORWARDED_ALLOW_IPS": "127.0.0.1",
        "QUEUE_PATH": str(tmp / "webadmin.queue"),
        "LOG_FILE": str(tmp / "toc.log"),
        "EVENT_LOG_FILE": str(tmp / "events.tsv"),
        "PLAYER_PATH": str(tmp / "player"),
        "BACKUP_PATH": str(tmp),
        "AREA_PATH": str(ROOT / "area"),
        "MUD_HOST": "127.0.0.1",
        "MUD_PORT": "65534",
    }
    with patch.dict(os.environ, env, clear=False):
        sys.modules.pop("webadmin.server", None)
        server = importlib.import_module("webadmin.server")
    sys.modules.pop("webadmin.server", None)
    server.set_bind_address("127.0.0.1")
    return server, tmp


def run_middleware(server, scope: dict) -> dict:
    """Pass a scope through ForwardedPeerMiddleware; return what got inside."""
    seen = {}

    async def inner(inner_scope, receive, send):
        seen.update(inner_scope)

    asyncio.run(server.ForwardedPeerMiddleware(inner)(scope, None, None))
    return seen


def scope_for(kind="http", peer=("127.0.0.1", 40000), headers=(), scheme=None):
    return {
        "type": kind,
        "client": peer,
        "scheme": scheme or ("http" if kind == "http" else "ws"),
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers],
        "path": "/",
        "method": "GET",
        "query_string": b"",
    }


@unittest.skipIf(TestClient is None, TESTCLIENT_UNAVAILABLE_REASON or "")
class ProxyModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server, tmp = load_server()
        self.addCleanup(shutil.rmtree, tmp, True)

    def proxy(self, enabled: bool, allow: str = "127.0.0.1") -> None:
        self.server.configure_proxy_headers(enabled, allow)

    # ----------------------------------------------------------- the client
    def test_forwarding_headers_are_ignored_by_default(self) -> None:
        """No proxy configured: nobody may name their own address."""
        inside = run_middleware(self.server, scope_for(headers=[
            ("X-Forwarded-For", "198.51.100.7"), ("X-Forwarded-Proto", "https")]))
        self.assertEqual(inside["client"], ("127.0.0.1", 40000))
        self.assertEqual(inside["scheme"], "http")
        self.assertEqual(inside[self.server.PEER_SCOPE_KEY], ("127.0.0.1", 40000))

    def test_a_trusted_proxy_names_the_client_and_the_scheme(self) -> None:
        self.proxy(True)
        inside = run_middleware(self.server, scope_for(headers=[
            ("X-Forwarded-For", "198.51.100.7"), ("X-Forwarded-Proto", "https")]))
        self.assertEqual(inside["client"], ("198.51.100.7", 0))
        self.assertEqual(inside["scheme"], "https")
        # The true peer is kept beside it for the security decisions.
        self.assertEqual(inside[self.server.PEER_SCOPE_KEY], ("127.0.0.1", 40000))
        ws = run_middleware(self.server, scope_for(kind="websocket", headers=[
            ("X-Forwarded-For", "2001:db8::5"), ("X-Forwarded-Proto", "https")]))
        self.assertEqual(ws["client"], ("2001:db8::5", 0))
        self.assertEqual(ws["scheme"], "wss")

    def test_an_untrusted_peer_cannot_name_itself(self) -> None:
        self.proxy(True)
        inside = run_middleware(self.server, scope_for(
            peer=("203.0.113.9", 5000),
            headers=[("X-Forwarded-For", "127.0.0.1"), ("X-Forwarded-Proto", "https")]))
        self.assertEqual(inside["client"], ("203.0.113.9", 5000))
        self.assertEqual(inside["scheme"], "http")

    def test_the_chain_is_read_from_the_nearest_hop(self) -> None:
        self.proxy(True, "127.0.0.1, 10.0.0.0/8")
        cases = {
            # A client-written entry first, then what the proxy saw.
            "6.6.6.6, 198.51.100.7": "198.51.100.7",
            "198.51.100.7, 10.1.2.3": "198.51.100.7",
            "127.0.0.1": "127.0.0.1",
        }
        for header, expected in cases.items():
            with self.subTest(header=header):
                inside = run_middleware(self.server, scope_for(
                    headers=[("X-Forwarded-For", header)]))
                self.assertEqual(inside["client"][0], expected)
        for bad in ("not-an-address", "198.51.100.7,,", "", "198.51.100.7:443"):
            with self.subTest(bad=bad):
                inside = run_middleware(self.server, scope_for(
                    headers=[("X-Forwarded-For", bad), ("X-Forwarded-Proto", "gopher")]))
                self.assertEqual(inside["client"], ("127.0.0.1", 40000))
                self.assertEqual(inside["scheme"], "http")

    def test_a_wildcard_proxy_list_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.server.parse_forwarded_allow("*")
        with self.assertRaises(ValueError):
            self.server.parse_forwarded_allow("")
        with self.assertRaises(ValueError):
            self.server.parse_forwarded_allow("example.com")
        result = subprocess.run(
            [sys.executable, "-m", "webadmin.server", "--forwarded-allow-ips", "*"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
            env=dict(os.environ, WEB_ADMIN_TOKEN=""))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("may not be '*'", result.stderr)

    def test_uvicorns_own_rewrite_is_off(self) -> None:
        """uvicorn trusts loopback's X-Forwarded-For by default; with it on,
        the client is rewritten before the middleware can keep the peer."""
        source = (ROOT / "webadmin" / "server.py").read_text(encoding="utf-8")
        run = re.search(r"uvicorn\.run\(([^)]*)\)", source)
        self.assertIsNotNone(run)
        self.assertIn("proxy_headers=False", run.group(1))

    def test_the_bridge_names_the_player_to_the_game(self) -> None:
        """End to end: /ws through proxy mode sends the forwarded address."""
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)
        first_lines = []

        def game() -> None:
            conn, _ = listener.accept()
            with conn:
                data = b""
                while b"\n" not in data:
                    chunk = conn.recv(256)
                    if not chunk:
                        break
                    data += chunk
                first_lines.append(data.split(b"\n")[0].decode("latin-1").strip())
                conn.sendall(b"Welcome\r\n")

        thread = threading.Thread(target=game, daemon=True)
        thread.start()
        self.server.MUD_PORT = listener.getsockname()[1]
        self.proxy(True)
        client = TestClient(self.server.app, base_url="https://timesofchaos.com",
                            client=("127.0.0.1", 40000))
        with client.websocket_connect(
            "wss://timesofchaos.com/ws",
            headers={"origin": "https://timesofchaos.com", "host": "timesofchaos.com",
                     "x-forwarded-for": "198.51.100.7", "x-forwarded-proto": "https"},
        ) as ws:
            self.assertEqual(ws.receive_text(), "\0TOC_CONNECTED")
            self.assertIn("Welcome", ws.receive_text())
        thread.join(5)
        self.assertEqual(first_lines, ["PROXY TCP4 198.51.100.7 127.0.0.1 0 %d"
                                       % self.server.MUD_PORT])

    # ------------------------------------------------------ the local unlock
    def unlock_client(self, peer=("127.0.0.1", 40000), base_url="http://127.0.0.1:9001"):
        return TestClient(self.server.app, base_url=base_url, client=peer)

    def test_the_unlock_works_directly_on_loopback_without_a_proxy(self) -> None:
        client = self.unlock_client()
        self.assertTrue(client.get("/api/config").json()["local_admin_unlock"])
        opened = client.post("/api/auth/local")
        self.assertEqual(opened.status_code, 200)
        self.assertNotIn("secure", opened.headers["set-cookie"].lower())

    def test_the_unlock_is_refused_in_proxy_mode(self) -> None:
        self.proxy(True)
        self.assertFalse(self.server.local_admin_unlock_enabled())
        client = self.unlock_client()
        self.assertFalse(client.get("/api/config").json()["local_admin_unlock"])
        self.assertEqual(client.post("/api/auth/local").status_code, 403)
        client.cookies.set(self.server.LOCAL_ADMIN_COOKIE,
                           self.server.local_admin_session_value())
        self.assertEqual(client.get("/api/auth/check").status_code, 403)
        # The token still works, as it must behind the proxy.
        self.assertEqual(client.get("/api/auth/check",
                                    headers={"X-Admin-Token": "secret"}).status_code, 200)

    def test_any_forwarding_header_refuses_the_unlock(self) -> None:
        """Proxy mode off, a loopback peer -- and a proxy in front nobody
        told this process about. Each header alone is enough."""
        client = self.unlock_client()
        cookie = self.server.local_admin_session_value()
        for name in self.server.FORWARDING_HEADERS:
            with self.subTest(header=name):
                headers = {name: "127.0.0.1" if name != "forwarded" else "for=127.0.0.1"}
                self.assertFalse(client.get("/api/config", headers=headers)
                                 .json()["local_admin_unlock"])
                self.assertEqual(client.post("/api/auth/local", headers=headers)
                                 .status_code, 403)
                self.assertEqual(client.get(
                    "/api/auth/check",
                    headers={**headers, "cookie": f"{self.server.LOCAL_ADMIN_COOKIE}={cookie}"},
                ).status_code, 403)
                ws = WebSocket(scope_for(kind="websocket", headers=[
                    (name, "127.0.0.1"),
                    ("cookie", f"{self.server.LOCAL_ADMIN_COOKIE}={cookie}")]),
                    None, None)
                self.assertFalse(self.server.local_admin_websocket_authenticated(ws))
        ws = WebSocket(scope_for(kind="websocket", headers=[
            ("cookie", f"{self.server.LOCAL_ADMIN_COOKIE}={cookie}")]), None, None)
        self.assertTrue(self.server.local_admin_websocket_authenticated(ws))

    def test_the_unlock_reads_the_socket_peer_in_either_order(self) -> None:
        """A rewritten client never decides the unlock, whichever way round.

        A remote peer listed as a proxy that forwards "127.0.0.1" makes
        request.client loopback; the peer is still remote. A loopback peer
        forwarding a remote client is refused by the header.
        """
        self.proxy(True, "203.0.113.0/24")
        inside = run_middleware(self.server, scope_for(
            peer=("203.0.113.9", 5000), headers=[("X-Forwarded-For", "127.0.0.1")]))
        request = Request(inside)
        self.assertEqual(request.client.host, "127.0.0.1")
        self.assertEqual(self.server.socket_peer(request).host, "203.0.113.9")
        # With proxy mode itself out of the way, the peer still decides.
        with patch.object(self.server, "_PROXY_HEADERS", False):
            self.assertFalse(self.server.loopback_peer(self.server.socket_peer(request)))
            self.assertFalse(self.server.local_admin_connection_allowed(request))
        self.proxy(True)
        inside = run_middleware(self.server, scope_for(
            headers=[("X-Forwarded-For", "198.51.100.7")]))
        request = Request(inside)
        self.assertEqual(self.server.socket_peer(request).host, "127.0.0.1")
        with patch.object(self.server, "_PROXY_HEADERS", False):
            self.assertFalse(self.server.local_admin_connection_allowed(request))

    # --------------------------------------------- origin, scheme and cookie
    def test_same_origin_holds_over_https_behind_the_proxy(self) -> None:
        headers = [("Host", "timesofchaos.com"), ("Origin", "https://timesofchaos.com"),
                   ("X-Forwarded-For", "198.51.100.7"), ("X-Forwarded-Proto", "https")]
        self.proxy(True)
        request = Request(run_middleware(self.server, scope_for(headers=headers)))
        self.assertEqual(request.url.scheme, "https")
        self.assertTrue(self.server.same_origin_request(request))
        self.assertFalse(self.server.same_origin_request(Request(run_middleware(
            self.server, scope_for(headers=[("Host", "timesofchaos.com"),
                                            ("Origin", "https://evil.example"),
                                            ("X-Forwarded-Proto", "https")])))))
        ws = WebSocket(run_middleware(self.server, scope_for(kind="websocket", headers=headers)),
                       None, None)
        self.assertTrue(self.server.websocket_origin_allowed(ws))
        # Without proxy mode the scheme is the socket's, and an https Origin
        # is not this http origin.
        self.proxy(False)
        self.assertFalse(self.server.same_origin_request(
            Request(run_middleware(self.server, scope_for(headers=headers)))))

    def test_the_session_cookie_is_secure_over_https(self) -> None:
        client = self.unlock_client(base_url="https://127.0.0.1:9001")
        opened = client.post("/api/auth/local")
        self.assertEqual(opened.status_code, 200)
        self.assertIn("secure", opened.headers["set-cookie"].lower())

    def test_the_public_name_is_timesofchaos(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "MUD_PUBLIC_HOST"}
        with patch.dict(os.environ, env, clear=True):
            server, tmp = load_server()
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertEqual(server.MUD_PUBLIC_HOST, "timesofchaos.com")


class HostConfigurationTests(unittest.TestCase):
    """The Caddyfile, the unit and the installers agree."""

    def test_the_setup_script_parses(self) -> None:
        for shell in ("sh", "bash", "dash"):
            if shutil.which(shell):
                with self.subTest(shell=shell):
                    result = subprocess.run([shell, "-n", str(SCRIPT)],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_caddy_and_the_unit_agree_on_loopback_9001(self) -> None:
        caddy = CADDYFILE.read_text(encoding="utf-8")
        unit = UNIT.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("reverse_proxy 127.0.0.1:9001", caddy)
        self.assertRegex(caddy, r"(?m)^timesofchaos\.com \{")
        self.assertRegex(caddy, r"(?m)^www\.timesofchaos\.com \{\n\tredir https://timesofchaos\.com")
        self.assertIn("--host ${WEB_ADMIN_LISTEN} --port 9001", unit)
        self.assertIn("WEB_PORT=9001", script)
        self.assertIn("env_set WEB_ADMIN_LISTEN 127.0.0.1", script)
        self.assertIn("env_set WEB_ADMIN_PROXY_HEADERS 1", script)
        self.assertIn("env_set WEB_ADMIN_FORWARDED_ALLOW_IPS 127.0.0.1", script)
        self.assertIn("env_set WEB_ADMIN_LOCAL_UNLOCK 0", script)
        # A deploy of the unit alone never moves the dashboard: its own
        # defaults are the old public bind, and web.env (written by the
        # script) overrides them.
        self.assertIn("Environment=WEB_ADMIN_LISTEN=0.0.0.0", unit)
        self.assertIn("Environment=WEB_ADMIN_PROXY_HEADERS=0", unit)
        self.assertLess(unit.index("Environment=WEB_ADMIN_LISTEN"),
                        unit.index("EnvironmentFile=/etc/toc/web.env"))

    def test_deploy_and_restore_install_the_same_unit(self) -> None:
        deploy = (VM / "toc-deploy").read_text(encoding="utf-8")
        restore = (ROOT / "deploy" / "toc-restore").read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('for u in toc-web.service toc-game.service; do', deploy)
        self.assertIn('install -m 0644 "$BUILD/deploy/windows-vm/$u" "/etc/systemd/system/$u"', deploy)
        self.assertIn("toc-web.service", restore)
        self.assertIn('install -m 0644 "$BUILD/deploy/windows-vm/$u" /etc/systemd/system/', restore)
        self.assertIn('SRC="$BUILD/deploy/windows-vm"', script)
        self.assertIn('"$SRC/toc-web.service" "$UNIT_DIR/toc-web.service"', script)
        # Both keep checking the dashboard where it still answers.
        self.assertIn("http://127.0.0.1:9001/api/health", deploy)
        # A fresh box is told how to put the website back behind Caddy.
        self.assertTrue("toc-web-proxy" in restore, "toc-restore does not mention toc-web-proxy")

    def test_caddy_validates_the_caddyfile(self) -> None:
        caddy = os.environ.get("TOC_CADDY") or shutil.which("caddy")
        if not caddy:
            self.skipTest("caddy is not installed (apt install caddy)")
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, XDG_DATA_HOME=home, XDG_CONFIG_HOME=home)
            result = subprocess.run(
                [caddy, "validate", "--config", str(CADDYFILE), "--adapter", "caddyfile"],
                capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            formatted = subprocess.run([caddy, "fmt", str(CADDYFILE)], capture_output=True,
                                       text=True, env=env, timeout=60)
            if formatted.returncode == 0:
                self.assertEqual(formatted.stdout, CADDYFILE.read_text(encoding="utf-8"),
                                 "the Caddyfile is not as caddy fmt writes it")


# Every host command the script runs, stubbed. State the stubs keep lives
# in $STUB_DIR: which iptables ports are open, the systemctl calls made.
STUBS = {
    "systemctl": 'echo "systemctl $*" >> "$STUB_LOG"; exit 0',
    "apt-get": 'echo "apt-get $*" >> "$STUB_LOG"; exit "${STUB_APT:-0}"',
    "caddy": ('echo "caddy $*" >> "$STUB_LOG"; case "$1" in'
              ' version) echo v2.6.2;; validate) exit "${STUB_VALIDATE:-0}";; esac; exit 0'),
    "iptables": ('echo "iptables $*" >> "$STUB_LOG"; port=""; prev="";'
                 ' for a in "$@"; do [ "$prev" = --dport ] && port=$a; prev=$a; done;'
                 ' case "$1" in'
                 ' -C) grep -qx "$port" "$STUB_DIR/open" 2>/dev/null; exit $?;;'
                 ' -L) printf "Chain INPUT\\nnum target\\n1 ACCEPT\\n2 ACCEPT\\n3 REJECT\\n";;'
                 ' -I|-A) echo "$port" >> "$STUB_DIR/open";;'
                 ' esac; exit 0'),
    "netfilter-persistent": 'echo "netfilter-persistent $*" >> "$STUB_LOG"; exit 0',
    "ss": ('case "$*" in *9001*) printf "LISTEN 0 2048 %s 0.0.0.0:*\\n"'
           ' "${STUB_LISTEN:-127.0.0.1:9001}";; *) printf "%s" "${STUB_HOLDERS:-}";; esac'),
    "curl": ('case "$*" in'
             ' *--write-out*) echo "${STUB_REDIRECT:-308}";;'
             ' *https://*) [ "${STUB_TLS:-0}" = 1 ] || exit 7; echo \'{"status":"ok"}\';;'
             ' *9001/api/health*) [ "${STUB_HEALTH:-1}" = 1 ] || exit 7;'
             ' echo \'{"status":"ok","merc":true,"webadmin":true}\';;'
             ' esac; exit 0'),
    "sleep": "exit 0",
}


@unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
class SetupScriptTests(unittest.TestCase):
    TOKEN_LINE = "WEB_ADMIN_TOKEN=0123456789abcdef-synthetic"

    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, body in STUBS.items():
            path = bin_dir / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        self.bin_dir = bin_dir
        # A build tree with this commit's files, and a live tree whose
        # dashboard has proxy mode.
        self.build = self.tmp / "build"
        (self.build / "deploy" / "windows-vm").mkdir(parents=True)
        for name in ("Caddyfile", "toc-web.service", "toc-web-proxy"):
            shutil.copy(VM / name, self.build / "deploy" / "windows-vm" / name)
        self.current = self.tmp / "current"
        (self.current / "webadmin").mkdir(parents=True)
        shutil.copy(ROOT / "webadmin" / "server.py", self.current / "webadmin" / "server.py")
        self.etc = self.tmp / "etc"
        (self.etc / "caddy").mkdir(parents=True)
        (self.etc / "systemd").mkdir()
        (self.etc / "caddy" / "Caddyfile").write_text(":80 {\n\tfile_server\n}\n")
        self.old_unit = "[Service]\nExecStart=old --host 0.0.0.0 --port 9001\n"
        (self.etc / "systemd" / "toc-web.service").write_text(self.old_unit)
        self.web_env = self.etc / "web.env"
        self.web_env.write_text(
            self.TOKEN_LINE + "\nWEB_ADMIN_LOCAL_UNLOCK=1\nWEB_ADMIN_HOST_STATUS=1\n"
            "MUD_PUBLIC_HOST=toc.jeremybean.com\n")
        self.web_env.chmod(0o600)
        self.log = self.tmp / "calls.log"
        self.log.write_text("")

    def run_script(self, *args: str, **stub_env: str) -> tuple[int, str, str]:
        env = dict(
            os.environ, PATH=f"{self.bin_dir}:{os.environ['PATH']}",
            BUILD=str(self.build), CURRENT=str(self.current),
            TOC_WEB_ENV=str(self.web_env), TOC_CADDY_DIR=str(self.etc / "caddy"),
            TOC_UNIT_DIR=str(self.etc / "systemd"), TOC_WEB_PROXY_STATE=str(self.tmp / "state"),
            TOC_WEB_PROXY_ANY_USER="1", TOC_DEPLOY_LOCKED="1", TOC_WEB_PROXY_WAIT="2",
            STUB_LOG=str(self.log), STUB_DIR=str(self.tmp), **stub_env)
        result = subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True,
                                text=True, timeout=60)
        return result.returncode, result.stdout + result.stderr, self.log.read_text()

    def env_lines(self) -> list[str]:
        return self.web_env.read_text().splitlines()

    def test_a_dry_run_changes_nothing(self) -> None:
        before = self.web_env.read_text()
        status, output, calls = self.run_script("--dry-run")
        self.assertEqual(status, 0, output)
        self.assertIn("dry run: nothing was changed", output)
        self.assertEqual(self.web_env.read_text(), before)
        self.assertEqual((self.etc / "systemd" / "toc-web.service").read_text(), self.old_unit)
        self.assertNotIn("systemctl restart", calls)
        self.assertNotIn("iptables -I", calls)
        self.assertNotIn("synthetic", output, "a value from web.env was printed")

    def test_the_setup_moves_the_dashboard_and_keeps_the_rest(self) -> None:
        status, output, calls = self.run_script()
        self.assertEqual(status, 0, output)
        lines = self.env_lines()
        self.assertIn(self.TOKEN_LINE, lines)
        self.assertIn("WEB_ADMIN_HOST_STATUS=1", lines)
        for line in ("WEB_ADMIN_LISTEN=127.0.0.1", "WEB_ADMIN_PROXY_HEADERS=1",
                     "WEB_ADMIN_FORWARDED_ALLOW_IPS=127.0.0.1", "WEB_ADMIN_LOCAL_UNLOCK=0",
                     "MUD_PUBLIC_HOST=timesofchaos.com"):
            self.assertEqual(lines.count(line), 1, line)
        self.assertFalse(any(l.startswith("WEB_ADMIN_LOCAL_UNLOCK=1") for l in lines))
        self.assertEqual(stat.S_IMODE(self.web_env.stat().st_mode), 0o600)
        self.assertNotIn("synthetic", output)
        self.assertEqual((self.etc / "caddy" / "Caddyfile").read_text(), CADDYFILE.read_text())
        self.assertEqual((self.etc / "systemd" / "toc-web.service").read_text(), UNIT.read_text())
        self.assertTrue((self.tmp / "state" / "Caddyfile.before").exists())
        # Caddy is validated and started before the dashboard moves.
        self.assertLess(calls.index("caddy validate"), calls.index("systemctl restart caddy"))
        self.assertLess(calls.index("systemctl restart caddy"), calls.index("systemctl restart toc-web"))
        # 80 and 443 go in before the REJECT (line 3), then are saved.
        self.assertIn("iptables -I INPUT 3 -p tcp -m state --state NEW -m tcp --dport 80 -j ACCEPT", calls)
        self.assertIn("--dport 443 -j ACCEPT", calls)
        self.assertIn("netfilter-persistent save", calls)
        self.assertNotIn("9000", "".join(l for l in calls.splitlines() if l.startswith("iptables")))
        self.assertNotIn("toc-game", calls)
        self.assertIn("does not answer yet", output)  # no certificate in a test

        # Again: nothing to do, nothing duplicated.
        self.log.write_text("")
        status, output, calls = self.run_script(STUB_TLS="1")
        self.assertEqual(status, 0, output)
        self.assertNotIn("iptables -I", calls)
        self.assertNotIn("netfilter-persistent", calls)
        self.assertNotIn("systemctl restart caddy", calls)
        self.assertEqual(self.env_lines(), lines)
        self.assertIn("answers with a valid certificate", output)

    def test_a_caddy_that_does_not_answer_leaves_the_dashboard_alone(self) -> None:
        before = self.web_env.read_text()
        status, output, calls = self.run_script(STUB_REDIRECT="000")
        self.assertNotEqual(status, 0)
        self.assertIn("still on public 9001, untouched", output)
        self.assertEqual(self.web_env.read_text(), before)
        self.assertNotIn("restart toc-web", calls)
        status, output, calls = self.run_script(STUB_VALIDATE="1")
        self.assertNotEqual(status, 0)
        self.assertIn("does not validate", output)
        self.assertEqual(self.web_env.read_text(), before)

    def test_a_dashboard_that_does_not_come_back_is_put_back(self) -> None:
        before = self.web_env.read_text()
        status, output, calls = self.run_script(STUB_HEALTH="0")
        self.assertNotEqual(status, 0)
        self.assertIn("putting the dashboard back", output)
        self.assertEqual(self.web_env.read_text(), before)
        self.assertEqual((self.etc / "systemd" / "toc-web.service").read_text(), self.old_unit)
        self.assertEqual(calls.count("systemctl restart toc-web"), 2)
        # Listening anywhere but loopback is a failure too.
        status, output, _ = self.run_script(STUB_LISTEN="0.0.0.0:9001")
        self.assertNotEqual(status, 0)
        self.assertIn("not listening on 127.0.0.1:9001 only", output)
        self.assertEqual(self.web_env.read_text(), before)

    def test_it_refuses_before_the_dashboard_can_take_proxy_mode(self) -> None:
        (self.current / "webadmin" / "server.py").write_text("# an older dashboard\n")
        status, output, calls = self.run_script()
        self.assertNotEqual(status, 0)
        self.assertIn("deploy the commit that carries this script first", output)
        self.assertEqual(calls, "")

    def test_something_else_on_port_80_stops_it(self) -> None:
        status, output, calls = self.run_script(
            STUB_HOLDERS='LISTEN 0 511 0.0.0.0:80 0.0.0.0:* users:(("nginx",pid=1,fd=6))\n')
        self.assertNotEqual(status, 0)
        self.assertIn("other than Caddy", output)
        self.assertEqual(calls, "")

    def test_rollback(self) -> None:
        status, output, _ = self.run_script()
        self.assertEqual(status, 0, output)
        self.log.write_text("")
        status, output, calls = self.run_script("--rollback", STUB_LISTEN="0.0.0.0:9001")
        self.assertEqual(status, 0, output)
        lines = self.env_lines()
        for key in ("WEB_ADMIN_LISTEN", "WEB_ADMIN_PROXY_HEADERS", "WEB_ADMIN_FORWARDED_ALLOW_IPS"):
            self.assertFalse(any(l.startswith(key + "=") for l in lines), key)
        self.assertIn(self.TOKEN_LINE, lines)
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK=0", lines)
        self.assertIn("MUD_PUBLIC_HOST=timesofchaos.com", lines)
        self.assertLess(calls.index("systemctl restart toc-web"),
                        calls.index("systemctl disable --now caddy"))
        self.assertNotIn("iptables", calls)


if __name__ == "__main__":
    unittest.main()
