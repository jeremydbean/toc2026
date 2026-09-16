import os
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class InstallationAssetsTests(unittest.TestCase):
    def test_platform_entrypoints_are_present(self):
        expected = (
            "install.ps1",
            "install.sh",
            "Install-ToC.cmd",
            "Install-ToC.command",
            "toc.ps1",
            "toc.sh",
            "Start-ToC.cmd",
            "Start-ToC.command",
            "scripts/bootstrap_windows.ps1",
            "scripts/bootstrap_macos.sh",
            "scripts/bootstrap_linux.sh",
        )
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())

    def test_compose_defaults_are_private_and_state_is_persistent(self):
        compose = read("docker-compose.yml")
        self.assertIn("${MUD_BIND:-127.0.0.1}", compose)
        self.assertIn("${WEB_ADMIN_BIND:-127.0.0.1}", compose)
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK=${WEB_ADMIN_LOCAL_UNLOCK:-1}", compose)
        self.assertIn("healthcheck:", compose)
        for directory in ("player", "gods", "heroes", "corpse", "log", "backups"):
            with self.subTest(directory=directory):
                self.assertIn(f"./{directory}:/app/{directory}", compose)

    def test_private_runtime_data_is_excluded_from_images(self):
        dockerignore = set(read(".dockerignore").splitlines())
        for entry in (".env", "backups", "corpse", "gods", "heroes", "log", "player"):
            with self.subTest(entry=entry):
                self.assertIn(entry, dockerignore)

        dockerfile = read("Dockerfile")
        self.assertIn("mkdir -p player gods heroes corpse log backups", dockerfile)

    def test_launchers_expose_the_documented_lifecycle(self):
        for relative_path in ("toc.ps1", "toc.sh"):
            launcher = read(relative_path)
            with self.subTest(path=relative_path):
                for command in (
                    "start",
                    "build",
                    "stop",
                    "restart",
                    "status",
                    "logs",
                    "doctor",
                    "update",
                    "open",
                    "play",
                    "admin",
                ):
                    self.assertIn(command, launcher)

    def test_launchers_expose_player_and_admin_urls(self):
        powershell_common = read("scripts/toc_common.ps1")
        shell_common = read("scripts/toc_common.sh")
        self.assertIn("/client", powershell_common)
        self.assertIn("/client", shell_common)
        self.assertIn("Open-TocClient", powershell_common)
        self.assertIn("open|play)", read("toc.sh"))
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK", powershell_common)
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK", shell_common)

    def test_shell_scripts_are_kept_with_unix_line_endings(self):
        self.assertIn("*.sh text eol=lf", read(".gitattributes"))
        paths = [*ROOT.glob("*.sh"), *(ROOT / "scripts").glob("*.sh"), *(ROOT / "area").glob("*.sh")]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(b"\r\n", path.read_bytes())

    def test_bootstraps_do_not_pipe_downloads_to_a_shell(self):
        pattern = re.compile(r"curl[^\n|]*\|\s*(?:ba)?sh\b")
        for relative_path in (
            "scripts/setup_mac.sh",
            "scripts/bootstrap_macos.sh",
            "scripts/bootstrap_linux.sh",
        ):
            with self.subTest(path=relative_path):
                self.assertNotRegex(read(relative_path), pattern)

    def test_windows_token_generation_supports_windows_powershell(self):
        common = read("scripts/toc_common.ps1")
        self.assertNotIn("RandomNumberGenerator]::Fill", common)
        self.assertNotIn("Convert]::ToHexString", common)
        self.assertIn("GetBytes($bytes)", common)

    def test_readme_points_to_easy_installers(self):
        readme = read("README.md")
        self.assertIn("Install-ToC.cmd", readme)
        self.assertIn("Install-ToC.command", readme)
        self.assertIn("bootstrap_windows.ps1", readme)
        self.assertIn("bootstrap_macos.sh", readme)

    def test_pi_updater_is_periodic_and_portal_triggered(self):
        updater = read("deploy/toc2026-update")
        installer = read("deploy/install-pi.sh")
        timer = read("deploy/systemd/toc2026-update.timer")
        service = read("deploy/systemd/toc2026-update.service")
        path_unit = read("deploy/systemd/toc2026-update.path")
        web_unit = read("deploy/systemd/toc2026-web.service")

        self.assertIn("fetch --prune origin main", updater)
        self.assertIn("http.lowSpeedTime=60", updater)
        self.assertIn("fetch_attempt", updater)
        self.assertIn("make -C \"$TOC_ROOT\" -j1", updater)
        self.assertIn("../merc --check-area", updater)
        self.assertIn("tests.test_webadmin_api tests.test_installation_assets", updater)
        self.assertIn('install-pi.sh" --refresh', updater)
        self.assertIn("toc2026-player-backup.service", updater)
        self.assertIn("reset-failed toc2026-player-backup.service", updater)
        self.assertIn("OnCalendar=Sun *-*-* 04:00:00", timer)
        self.assertIn("RandomizedDelaySec=30min", timer)
        self.assertIn("Persistent=true", timer)
        self.assertNotIn("OnUnitActiveSec=", timer)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("RestartSec=15min", service)
        self.assertIn("ProtectSystem=full", service)
        for writable_path in (
            "/usr/local/sbin",
            "/etc/systemd/system",
            "/etc/systemd/system.conf.d",
            "/etc/systemd/journald.conf.d",
            "/etc/tmpfiles.d",
            "/etc/apt/apt.conf.d",
        ):
            self.assertIn(f"ReadWritePaths={writable_path}", service)
        self.assertIn("PathExists=/run/toc2026/update.request", path_unit)
        self.assertIn("TOC_UPDATE_REQUEST_PATH=/run/toc2026/update.request", web_unit)
        self.assertIn("toc2026-update.timer toc2026-update.path", installer)

    def test_pi_lan_profile_publishes_the_browser_without_local_unlock(self):
        pi_environment = read("deploy/pi.env.example")
        web_unit = read("deploy/systemd/toc2026-web.service")
        self.assertIn("WEB_ADMIN_BIND=0.0.0.0", pi_environment)
        self.assertIn("WEB_ADMIN_PORT=9001", pi_environment)
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK=0", pi_environment)
        self.assertIn("WEB_ADMIN_HOST_STATUS=1", pi_environment)
        self.assertIn("SupplementaryGroups=systemd-journal", web_unit)

    def test_pi_act_led_tracks_the_game_service(self):
        indicator = read("deploy/toc2026-led")
        service = read("deploy/systemd/toc2026-led.service")
        installer = read("deploy/install-pi.sh")

        self.assertIn("printf '%s\\n' timer", indicator)
        self.assertIn("printf '%s\\n' 3000", indicator)
        self.assertIn("printf '%s\\n' 1000", indicator)
        self.assertIn("printf '%s\\n' 100 >\"$led_path/delay_on\"", indicator)
        self.assertIn("printf '%s\\n' 100 >\"$led_path/delay_off\"", indicator)
        self.assertIn("failed)", indicator)
        self.assertIn("printf '%s\\n' none", indicator)
        self.assertIn("BindsTo=toc2026-game.service", service)
        self.assertIn("PartOf=toc2026-game.service", service)
        self.assertIn("After=toc2026-game.service", service)
        self.assertIn("WantedBy=toc2026-game.service", service)
        self.assertIn("MemoryMax=8M", service)
        self.assertIn("systemctl enable --now toc2026-led.service", installer)

    def test_pi_game_has_watchdog_and_bounded_recovery(self):
        comm = read("src/comm.c")
        game_service = read("deploy/systemd/toc2026-game.service")
        recovery_service = read("deploy/systemd/toc2026-recovery.service")
        stable_service = read("deploy/systemd/toc2026-stable.service")
        recovery = read("deploy/toc2026-recover")
        stability = read("deploy/toc2026-stable")
        updater = read("deploy/toc2026-update")
        installer = read("deploy/install-pi.sh")

        self.assertIn('notify_systemd( "READY=1', comm)
        self.assertIn('notify_systemd( "WATCHDOG=1" )', comm)
        self.assertIn("Type=notify", game_service)
        self.assertNotIn("network-online.target", game_service)
        self.assertIn("WatchdogSec=45s", game_service)
        self.assertIn("WatchdogSignal=SIGKILL", game_service)
        self.assertIn("OnFailure=toc2026-recovery.service", game_service)
        self.assertIn("TOC_UPDATE_FORCE", updater)
        self.assertIn("systemctl reset-failed", updater)
        self.assertIn("TOC_UPDATE_FORCE=1", recovery)
        self.assertIn("TOC_RECOVERY_MAX_ATTEMPTS:-3", recovery)
        self.assertIn("TOC_RECOVERY_COOLDOWN_SEC:-21600", recovery)
        self.assertIn("recovery-planned-reboot", recovery)
        self.assertIn("toc2026-web.service", recovery)
        self.assertIn('"merc":true', recovery)
        self.assertIn('"webadmin":true', stability)
        self.assertIn('"$SYSTEMCTL" --no-block reboot', recovery)
        self.assertIn("Automatic recovery limit reached", recovery)
        self.assertIn("TOC_STABILITY_DELAY_SEC:-600", stability)
        self.assertIn("BindsTo=toc2026-game.service", stable_service)
        self.assertIn("MemoryMax=256M", recovery_service)
        self.assertNotIn("network-online.target", recovery_service)
        self.assertIn("deploy/systemd/toc2026-*", installer)
        self.assertIn("systemctl enable --now toc2026-stable.service", installer)

    def test_pi_healthcheck_repairs_repeated_endpoint_failures(self):
        healthcheck = ROOT / "deploy/toc2026-healthcheck"
        service = read("deploy/systemd/toc2026-healthcheck.service")
        timer = read("deploy/systemd/toc2026-healthcheck.timer")
        web_service = read("deploy/systemd/toc2026-web.service")
        installer = read("deploy/install-pi.sh")

        self.assertIn("OnFailure=toc2026-recovery.service", service)
        self.assertIn("OnUnitActiveSec=2min", timer)
        self.assertIn("OnFailure=toc2026-recovery.service", web_service)
        self.assertNotIn("network-online.target", web_service)
        self.assertIn("toc2026-healthcheck.timer", installer)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            state = temporary / "state"
            state.mkdir()
            (state / "health-failures").write_text("2\n", encoding="ascii")
            curl_count = temporary / "curl-count"
            curl_count.write_text("0\n", encoding="ascii")
            mock_curl = temporary / "curl"
            mock_curl.write_text(
                "#!/bin/sh\n"
                f"count_file='{curl_count}'\n"
                "count=$(cat \"$count_file\")\n"
                "count=$((count + 1))\n"
                "printf '%s\\n' \"$count\" >\"$count_file\"\n"
                "if [ \"$count\" -eq 1 ]; then exit 22; fi\n"
                "printf '%s\\n' '{\"status\":\"ok\",\"merc\":true,\"webadmin\":true}'\n",
                encoding="utf-8",
            )
            mock_curl.chmod(0o755)
            systemctl_log = temporary / "systemctl.log"
            mock_systemctl = temporary / "systemctl"
            mock_systemctl.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$*\" >>'{systemctl_log}'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            mock_systemctl.chmod(0o755)
            mock_flock = temporary / "flock"
            mock_flock.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mock_flock.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "TOC_HEALTH_STATE_DIR": str(state),
                    "TOC_HEALTH_LOCK_FILE": str(temporary / "health.lock"),
                    "TOC_CURL": str(mock_curl),
                    "TOC_SYSTEMCTL": str(mock_systemctl),
                    "TOC_SLEEP": "/usr/bin/true",
                    "TOC_FLOCK": str(mock_flock),
                }
            )

            result = subprocess.run(
                [str(healthcheck)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((state / "health-failures").exists())
            self.assertIn("restart toc2026-web.service", systemctl_log.read_text())

    def test_pi_has_weekly_os_maintenance_and_hardware_watchdog(self):
        maintenance = read("deploy/toc2026-maintenance")
        maintenance_service = read("deploy/systemd/toc2026-maintenance.service")
        maintenance_timer = read("deploy/systemd/toc2026-maintenance.timer")
        watchdog = read("deploy/systemd/99-toc2026-watchdog.conf")
        apt_config = read("deploy/apt/52toc2026-maintenance")
        installer = read("deploy/install-pi.sh")

        self.assertIn("unattended-upgrade", maintenance)
        self.assertIn("toc2026-player-backup.service", maintenance)
        self.assertIn('"$SYSTEMCTL" --no-block reboot', maintenance)
        self.assertIn("Restart=on-failure", maintenance_service)
        self.assertIn("OnCalendar=Sun *-*-* 05:30:00", maintenance_timer)
        self.assertIn("Persistent=true", maintenance_timer)
        self.assertIn("RuntimeWatchdogSec=1min", watchdog)
        self.assertIn("RebootWatchdogSec=2min", watchdog)
        self.assertIn('APT::Periodic::Unattended-Upgrade "0"', apt_config)
        self.assertIn('Unattended-Upgrade::Automatic-Reboot "false"', apt_config)
        self.assertIn("toc2026-maintenance.timer", installer)

    def test_pi_recovery_cooldown_prevents_rebuild_thrashing(self):
        recovery = ROOT / "deploy/toc2026-recover"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            state = temporary / "state"
            state.mkdir()
            now = "1789500000"
            boot_id = "test-boot-id"
            (state / "recovery-count").write_text("3\n", encoding="ascii")
            (state / "recovery-last-attempt").write_text(f"{now}\n", encoding="ascii")
            (state / "recovery-last-boot").write_text(f"{boot_id}\n", encoding="ascii")
            boot_id_file = temporary / "boot-id"
            boot_id_file.write_text(f"{boot_id}\n", encoding="ascii")

            def executable(name: str, body: str) -> pathlib.Path:
                path = temporary / name
                path.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
                path.chmod(0o755)
                return path

            mock_curl = executable("curl", "exit 22\n")
            mock_flock = executable("flock", "exit 0\n")
            mock_systemctl = executable("systemctl", "exit 1\n")
            mock_date = executable("date", f"printf '%s\\n' '{now}'\n")
            update_log = temporary / "update.log"
            mock_update = executable("update", f"touch '{update_log}'\n")
            mock_led = executable("led", "exit 0\n")
            environment = os.environ.copy()
            environment.update(
                {
                    "TOC_RECOVERY_STATE_DIR": str(state),
                    "TOC_RECOVERY_LOCK_FILE": str(temporary / "recovery.lock"),
                    "TOC_UPDATE_LOCK_FILE": str(temporary / "update.lock"),
                    "TOC_SYSTEMCTL": str(mock_systemctl),
                    "TOC_CURL": str(mock_curl),
                    "TOC_SLEEP": "/usr/bin/true",
                    "TOC_FLOCK": str(mock_flock),
                    "TOC_DATE": str(mock_date),
                    "TOC_BOOT_ID_FILE": str(boot_id_file),
                    "TOC_UPDATE_COMMAND": str(mock_update),
                    "TOC_LED_COMMAND": str(mock_led),
                }
            )

            result = subprocess.run(
                [str(recovery)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("cooling down", result.stdout)
            self.assertFalse(update_log.exists())

    def test_pi_namecheap_ddns_is_secret_backed_and_periodic(self):
        updater = read("deploy/toc2026-namecheap-ddns")
        example = read("deploy/namecheap-ddns.env.example")
        service = read("deploy/systemd/toc2026-namecheap-ddns.service")
        timer = read("deploy/systemd/toc2026-namecheap-ddns.timer")
        installer = read("deploy/install-pi.sh")

        self.assertIn("https://dynamicdns.park-your-domain.com", updater)
        self.assertIn("$endpoint/getip", updater)
        self.assertIn("<ErrCount>0</ErrCount>", updater)
        self.assertIn("replace-with-the-domain-dynamic-dns-password", example)
        self.assertIn("EnvironmentFile=/etc/toc2026/namecheap-ddns.env", service)
        self.assertIn("DynamicUser=yes", service)
        self.assertIn("MemoryMax=32M", service)
        self.assertIn("OnUnitActiveSec=10min", timer)
        self.assertIn("toc2026-namecheap-ddns.timer", installer)

    def test_pi_namecheap_ddns_validates_a_successful_update(self):
        updater = ROOT / "deploy/toc2026-namecheap-ddns"
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            mock_curl = temporary / "curl"
            mock_curl.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  -4) printf '203.0.113.42\\n' ;;\n"
                "  *) printf '<interface-response><IP>203.0.113.42</IP>"
                "<ErrCount>0</ErrCount></interface-response>\\n' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            mock_curl.chmod(0o755)
            runtime_directory = temporary / "run"
            state_directory = temporary / "state"
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{temporary}:/usr/bin:/bin",
                    "NAMECHEAP_DDNS_HOST": "toc",
                    "NAMECHEAP_DDNS_DOMAIN": "example.test",
                    "NAMECHEAP_DDNS_PASSWORD": "testtoken",
                    "TOC_DDNS_RUNTIME_DIR": str(runtime_directory),
                    "TOC_DDNS_STATE_DIR": str(state_directory),
                }
            )

            result = subprocess.run(
                [str(updater)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((state_directory / "last-ip").read_text(), "203.0.113.42\n")
            self.assertNotIn("testtoken", result.stdout + result.stderr)

    def test_pi_documentation_covers_access_auth_backup_and_updates(self):
        runbook = read("deploy/README.md")
        hosting = read("wiki/hosting-guide.md")
        security = read("SECURITY.md")
        admin = read("wiki/web-admin-guide.md")

        self.assertIn("http://toc.local:9001/client", runbook)
        self.assertIn("Remember on this browser", runbook)
        self.assertIn("toc2026-player-backup.timer", runbook)
        self.assertIn("toc2026-update", runbook)
        self.assertIn("make -j1", hosting)
        self.assertIn("do not forward port 9001", security)
        self.assertIn("Update ToC", admin)


if __name__ == "__main__":
    unittest.main()
