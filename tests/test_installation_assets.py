import pathlib
import re
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
        path_unit = read("deploy/systemd/toc2026-update.path")
        web_unit = read("deploy/systemd/toc2026-web.service")

        self.assertIn("git -C \"$TOC_ROOT\" fetch --prune origin main", updater)
        self.assertIn("make -C \"$TOC_ROOT\" -j1", updater)
        self.assertIn("../merc --check-area", updater)
        self.assertIn("toc2026-player-backup.service", updater)
        self.assertIn("OnUnitActiveSec=1h", timer)
        self.assertIn("PathExists=/run/toc2026/update.request", path_unit)
        self.assertIn("TOC_UPDATE_REQUEST_PATH=/run/toc2026/update.request", web_unit)
        self.assertIn("toc2026-update.timer toc2026-update.path", installer)

    def test_pi_lan_profile_publishes_the_browser_without_local_unlock(self):
        pi_environment = read("deploy/pi.env.example")
        self.assertIn("WEB_ADMIN_BIND=0.0.0.0", pi_environment)
        self.assertIn("WEB_ADMIN_PORT=9001", pi_environment)
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK=0", pi_environment)

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
