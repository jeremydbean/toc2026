#!/usr/bin/python3
"""Send bounded, secret-safe operational email for the ToC appliance."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import smtplib
import socket
import ssl
import stat
import subprocess
import sys
import time
from email.message import EmailMessage
from email.utils import getaddresses
from urllib.request import urlopen


DEFAULT_CONFIG_PATH = Path("/etc/toc2026/mail.env")
DEFAULT_STATE_DIR = Path("/var/lib/toc2026/mail")
PUBLIC_IP_URL = "https://dynamicdns.park-your-domain.com/getip"
HEALTH_URL = "http://127.0.0.1:9001/api/health"
MAX_COMMAND_OUTPUT = 20_000
MAX_JOURNAL_OUTPUT = 30_000
FAILURE_INTERVAL_SECONDS = 3600

EVENTS = {
    "startup": "Startup report",
    "test": "Test notification",
    "network": "Network changed",
    "game-failure": "ALERT: game service failed",
    "web-failure": "ALERT: web service failed",
    "healthcheck-repair": "ALERT: automatic repair started",
    "healthcheck-failure": "ALERT: health check failed",
    "recovery-failure": "ALERT: host recovery failed",
    "update-failure": "ALERT: source update failed",
    "backup-failure": "ALERT: encrypted player backup failed",
    "ddns-failure": "ALERT: public DNS update failed",
    "maintenance-failure": "ALERT: OS maintenance failed",
    "discovery-failure": "ALERT: local discovery failed",
    "recovered": "RECOVERED: services are healthy",
}

FAILURE_EVENTS = {
    event for event in EVENTS if event.endswith("-failure")
}
FAILURE_EVENTS.add("healthcheck-repair")

JOURNAL_UNITS = {
    "game-failure": (
        "toc2026-healthcheck.service",
        "toc2026-recovery.service",
    ),
    "web-failure": (
        "toc2026-healthcheck.service",
        "toc2026-recovery.service",
    ),
    "healthcheck-repair": (
        "toc2026-healthcheck.service",
        "toc2026-recovery.service",
    ),
    "healthcheck-failure": (
        "toc2026-healthcheck.service",
        "toc2026-recovery.service",
    ),
    "recovery-failure": (
        "toc2026-recovery.service",
        "toc2026-update.service",
    ),
    "update-failure": (
        "toc2026-update.service",
        "toc2026-player-backup.service",
    ),
    "backup-failure": ("toc2026-player-backup.service",),
    "ddns-failure": ("toc2026-namecheap-ddns.service",),
    "maintenance-failure": ("toc2026-maintenance.service",),
    "discovery-failure": (
        "toc2026-local-discovery.service",
        "NetworkManager.service",
        "avahi-daemon.service",
    ),
    "recovered": (
        "toc2026-healthcheck.service",
        "toc2026-recovery.service",
    ),
}

STATUS_UNITS = (
    "toc2026-game.service",
    "toc2026-web.service",
    "toc2026-local-discovery.service",
    "toc2026-healthcheck.timer",
    "toc2026-network-notify.timer",
    "toc2026-update.timer",
    "toc2026-player-backup.timer",
    "toc2026-namecheap-ddns.timer",
    "toc2026-maintenance.timer",
)

SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|token|secret|authorization|x-admin-token)"
    r"(\s*[:=]\s*)(\S+)"
)
IPV4_PATTERN = re.compile(
    r"(?<![0-9.])(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})"
    r"(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}(?![0-9.])"
)


class MailConfigurationError(RuntimeError):
    """The private mail configuration is missing or unsafe."""


def read_config(path: Path) -> dict[str, str]:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError as error:
        raise MailConfigurationError(f"Mail configuration not found: {path}") from error
    if mode & 0o077:
        raise MailConfigurationError(
            f"Mail configuration must not be group/world accessible: {path}"
        )

    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MailConfigurationError(f"Invalid mail configuration line {number}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise MailConfigurationError(f"Invalid mail configuration key on line {number}")
        values[key] = value.strip()

    required = (
        "TOC_SMTP_HOST",
        "TOC_SMTP_PORT",
        "TOC_SMTP_USERNAME",
        "TOC_SMTP_PASSWORD",
        "TOC_MAIL_FROM",
        "TOC_MAIL_TO",
    )
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise MailConfigurationError(
            "Missing required mail configuration: " + ", ".join(missing)
        )

    try:
        port = int(values["TOC_SMTP_PORT"])
    except ValueError as error:
        raise MailConfigurationError("TOC_SMTP_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise MailConfigurationError("TOC_SMTP_PORT is outside the valid range")

    security = values.get("TOC_SMTP_SECURITY", "starttls").lower()
    if security not in {"starttls", "ssl"}:
        raise MailConfigurationError("TOC_SMTP_SECURITY must be starttls or ssl")
    values["TOC_SMTP_SECURITY"] = security

    for header_key in ("TOC_MAIL_FROM", "TOC_MAIL_TO"):
        if "\r" in values[header_key] or "\n" in values[header_key]:
            raise MailConfigurationError(f"{header_key} contains a newline")
    senders = [address for _, address in getaddresses([values["TOC_MAIL_FROM"]])]
    if len(senders) != 1 or "@" not in senders[0]:
        raise MailConfigurationError("TOC_MAIL_FROM must contain one valid email address")
    recipients = [address for _, address in getaddresses([values["TOC_MAIL_TO"]])]
    if not recipients or any("@" not in address for address in recipients):
        raise MailConfigurationError("TOC_MAIL_TO must contain a valid email address")
    try:
        interval = int(
            values.get("TOC_MAIL_FAILURE_INTERVAL_SEC", FAILURE_INTERVAL_SECONDS)
        )
    except ValueError as error:
        raise MailConfigurationError(
            "TOC_MAIL_FAILURE_INTERVAL_SEC must be an integer"
        ) from error
    if not 60 <= interval <= 604800:
        raise MailConfigurationError(
            "TOC_MAIL_FAILURE_INTERVAL_SEC must be between 60 and 604800"
        )
    values["_SENDER"] = senders[0]
    values["_RECIPIENTS"] = ",".join(recipients)
    return values


def run_command(arguments: list[str], timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unavailable"
    output = (result.stdout or result.stderr).strip()
    if not output:
        output = f"exit status {result.returncode}"
    if len(output) > MAX_COMMAND_OUTPUT:
        output = output[-MAX_COMMAND_OUTPUT:]
    return output


def public_ipv4() -> str:
    try:
        with urlopen(PUBLIC_IP_URL, timeout=12) as response:
            value = response.read(128).decode("ascii", "strict").strip()
        address = ipaddress.ip_address(value)
        if address.version != 4:
            return "unavailable"
        return str(address)
    except (OSError, UnicodeError, ValueError):
        return "unavailable"


def web_health() -> str:
    try:
        with urlopen(HEALTH_URL, timeout=5) as response:
            payload = json.loads(response.read(4096).decode("utf-8"))
        return json.dumps(payload, sort_keys=True)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return "unavailable"


def appliance_network(include_public: bool = True) -> dict[str, str]:
    active = run_command(
        [
            "/usr/bin/nmcli",
            "-t",
            "-f",
            "DEVICE,TYPE,STATE,CONNECTION",
            "device",
            "status",
        ]
    )
    wifi = run_command(
        ["/usr/bin/nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"]
    )
    active_wifi = "\n".join(
        line for line in wifi.splitlines() if line.startswith("yes:")
    ) or "none"
    ipv4 = run_command(["/usr/sbin/ip", "-brief", "-4", "address", "show", "up"])
    ipv6 = run_command(["/usr/sbin/ip", "-brief", "-6", "address", "show", "up"])
    route = run_command(["/usr/sbin/ip", "route", "show", "default"])
    return {
        "active": active,
        "wifi": active_wifi,
        "ipv4": ipv4,
        "ipv6": ipv6,
        "route": route,
        "public_ipv4": public_ipv4() if include_public else "not checked",
    }


def network_fingerprint(network: dict[str, str]) -> str:
    stable = "\n".join(
        network[key] for key in ("active", "wifi", "ipv4", "route")
    )
    return hashlib.sha256(stable.encode("utf-8", "replace")).hexdigest()


def service_status() -> str:
    lines = []
    for unit in STATUS_UNITS:
        state = run_command(
            [
                "/bin/systemctl",
                "show",
                unit,
                "--property=ActiveState",
                "--property=SubState",
                "--property=Result",
                "--property=ExecMainStatus",
                "--property=NRestarts",
            ],
            timeout=5,
        )
        values = " / ".join(state.splitlines())
        lines.append(f"{unit}: {values}")
    return "\n".join(lines)


def host_resources() -> str:
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, value = line.split(":", 1)
            memory[key] = int(value.strip().split()[0])
    except (OSError, ValueError):
        memory = {}
    total_mb = memory.get("MemTotal", 0) // 1024
    available_mb = memory.get("MemAvailable", 0) // 1024
    swap_total_mb = memory.get("SwapTotal", 0) // 1024
    swap_free_mb = memory.get("SwapFree", 0) // 1024

    disk = shutil.disk_usage("/")
    disk_used_percent = ((disk.total - disk.free) * 100 / disk.total) if disk.total else 0
    try:
        load = ", ".join(f"{value:.2f}" for value in os.getloadavg())
    except OSError:
        load = "unavailable"
    try:
        temperature = (
            f"{int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000:.1f} C"
        )
    except (OSError, ValueError):
        temperature = "unavailable"

    return "\n".join(
        (
            f"Uptime: {run_command(['/usr/bin/uptime', '-p'])}",
            f"Load (1/5/15m): {load}",
            f"Memory: {available_mb} MiB available / {total_mb} MiB total",
            f"Swap: {swap_total_mb - swap_free_mb} MiB used / {swap_total_mb} MiB total",
            f"Root filesystem: {disk_used_percent:.1f}% used",
            f"CPU temperature: {temperature}",
        )
    )


def sanitize_log(text: str, secrets: list[str]) -> str:
    clean = text
    for secret in sorted((secret for secret in secrets if secret), key=len, reverse=True):
        clean = clean.replace(secret, "[REDACTED]")
    clean = SECRET_PATTERN.sub(r"\1\2[REDACTED]", clean)
    clean = IPV4_PATTERN.sub("[IP redacted]", clean)
    if len(clean) > MAX_JOURNAL_OUTPUT:
        clean = "[older output omitted]\n" + clean[-MAX_JOURNAL_OUTPUT:]
    return clean


def journal_for_event(event: str, secrets: list[str]) -> str:
    units = JOURNAL_UNITS.get(event)
    if not units:
        return ""
    arguments = [
        "/bin/journalctl",
        "--no-pager",
        "--output=short-iso",
        "--since=-20min",
        "--lines=160",
    ]
    for unit in units:
        arguments.extend(("--unit", unit))
    automation_log = run_command(arguments, timeout=15)
    manager_log = run_command(
        [
            "/bin/journalctl",
            "--no-pager",
            "--output=short-iso",
            "--since=-20min",
            "--lines=100",
            "_PID=1",
            "--grep=toc2026-(game|web|healthcheck|recovery)",
        ],
        timeout=15,
    )
    combined = "Automation units:\n" + automation_log
    combined += "\n\nSystem manager:\n" + manager_log
    return sanitize_log(combined, secrets)


def startup_wait() -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        health = web_health()
        if '"merc": true' in health and '"webadmin": true' in health:
            return
        time.sleep(5)


def access_details() -> str:
    return "\n".join(
        (
            "SSH account: toc (key-based: ssh toc)",
            "MUD: telnet toc.local 9000",
            "MUD public name: toc.jeremybean.com:9000",
            "Browser client: http://toc.local:9001/client",
            "Admin dashboard: http://toc.local:9001/",
            "Admin token: retained only in /home/toc/toc2026/.env; not emailed",
            "Passwords and private keys are never included in notifications.",
        )
    )


def build_body(event: str, network: dict[str, str], config: dict[str, str]) -> str:
    hostname = socket.gethostname()
    deployed = "unavailable"
    try:
        deployed = Path("/var/lib/toc2026/deployed-commit").read_text(
            encoding="ascii"
        ).strip()
    except OSError:
        pass
    boot_id = "unavailable"
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii"
        ).strip()
    except OSError:
        pass

    sections = (
        f"Times of Chaos appliance event: {EVENTS[event]}",
        "\n".join(
            (
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
                f"Hostname: {hostname}",
                f"Boot ID: {boot_id}",
                f"Deployed commit: {deployed}",
            )
        ),
        "Access\n------\n" + access_details(),
        "Network\n-------\n"
        + "\n".join(
            (
                "Active devices/connections:",
                network["active"],
                "",
                "Active Wi-Fi SSID:",
                network["wifi"],
                "",
                "Local IPv4:",
                network["ipv4"],
                "",
                "Local IPv6:",
                network["ipv6"],
                "",
                f"Public IPv4: {network['public_ipv4']}",
                f"Default route: {network['route']}",
            )
        ),
        "Services\n--------\n"
        + service_status()
        + f"\nDashboard health: {web_health()}",
        "Resources\n---------\n" + host_resources(),
    )

    journal = journal_for_event(
        event,
        [config.get("TOC_SMTP_PASSWORD", ""), config.get("TOC_SMTP_USERNAME", "")],
    )
    if journal:
        return (
            "\n\n".join(sections)
            + "\n\nRecent operational journal (redacted; gameplay logs excluded)\n"
            + "--------------------------------------------------------------\n"
            + journal
        )
    return "\n\n".join(sections)


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def failure_is_rate_limited(event: str, state_dir: Path, interval: int) -> bool:
    stamp_path = state_dir / f"last-{event}"
    try:
        last_sent = int(stamp_path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    return int(time.time()) - last_sent < interval


def send_message(config: dict[str, str], subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = config["TOC_MAIL_FROM"]
    message["To"] = config["TOC_MAIL_TO"]
    message["Subject"] = subject
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(body)

    host = config["TOC_SMTP_HOST"]
    port = int(config["TOC_SMTP_PORT"])
    context = ssl.create_default_context()
    if config["TOC_SMTP_SECURITY"] == "ssl":
        connection = smtplib.SMTP_SSL(host, port, timeout=25, context=context)
    else:
        connection = smtplib.SMTP(host, port, timeout=25)
    with connection as client:
        client.ehlo()
        if config["TOC_SMTP_SECURITY"] == "starttls":
            client.starttls(context=context)
            client.ehlo()
        client.login(config["TOC_SMTP_USERNAME"], config["TOC_SMTP_PASSWORD"])
        client.send_message(
            message,
            from_addr=config["_SENDER"],
            to_addrs=config["_RECIPIENTS"].split(","),
        )


def main(arguments: list[str]) -> int:
    if len(arguments) != 2 or arguments[1] not in EVENTS:
        print("Usage: toc2026-mail EVENT", file=sys.stderr)
        return 2
    event = arguments[1]
    config_path = Path(os.environ.get("TOC_MAIL_CONFIG", str(DEFAULT_CONFIG_PATH)))
    state_dir = Path(os.environ.get("TOC_MAIL_STATE_DIR", str(DEFAULT_STATE_DIR)))
    try:
        config = read_config(config_path)
    except MailConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1

    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_dir.chmod(0o700)

    if event == "startup":
        startup_wait()

    alert_path = state_dir / "alert-active"
    if event in FAILURE_EVENTS:
        atomic_write(alert_path, f"{int(time.time())} {event}\n")
        interval = int(config.get("TOC_MAIL_FAILURE_INTERVAL_SEC", FAILURE_INTERVAL_SECONDS))
        if failure_is_rate_limited(event, state_dir, interval):
            print(f"A recent {event} notification was already sent; suppressing duplicate.")
            return 0
    elif event == "recovered" and not alert_path.exists():
        print("No unresolved ToC alert exists; recovery email not needed.")
        return 0

    network = appliance_network(include_public=event != "network")
    fingerprint = network_fingerprint(network)
    network_state_path = state_dir / "network-fingerprint"
    if event == "network":
        try:
            previous = network_state_path.read_text(encoding="ascii").strip()
        except OSError:
            previous = ""
        if previous == fingerprint:
            print("The active ToC network identity is unchanged; email not needed.")
            return 0
        network["public_ipv4"] = public_ipv4()

    hostname = socket.gethostname()
    subject = f"[ToC] {EVENTS[event]} on {hostname}"
    body = build_body(event, network, config)
    try:
        send_message(config, subject, body)
    except (OSError, smtplib.SMTPException) as error:
        print(f"Could not send ToC email: {type(error).__name__}", file=sys.stderr)
        return 1

    now = str(int(time.time())) + "\n"
    if event in FAILURE_EVENTS:
        atomic_write(state_dir / f"last-{event}", now)
    if event in {"network", "startup"}:
        atomic_write(network_state_path, fingerprint + "\n")
    if event == "recovered":
        alert_path.unlink(missing_ok=True)
    print(f"Sent {event} notification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
