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
        compose = read("docker/compose.yml")
        self.assertIn("${MUD_BIND:-127.0.0.1}", compose)
        self.assertIn("${WEB_ADMIN_BIND:-127.0.0.1}", compose)
        self.assertIn("WEB_ADMIN_LOCAL_UNLOCK=${WEB_ADMIN_LOCAL_UNLOCK:-1}", compose)
        self.assertIn("healthcheck:", compose)
        # Every path the game writes is in the state folder, outside the
        # checkout -- the live world included, which the old layout kept
        # inside the container and lost on every rebuild (2026-10-21).
        mounts = {f"${{TOC_STATE:-./state}}/{d}:/app/{d}"
                  for d in ("area", "player", "gods", "heroes", "corpse", "log", "backups")}
        self.assertEqual(mounts - set(re.findall(r"\$\{TOC_STATE[^\s]*:/app/\w+", compose)), set())
        # The game saves everyone on SIGTERM; give it the time to.
        self.assertIn("stop_grace_period: 60s", compose)
        self.assertIn("image: ${TOC_IMAGE:-ghcr.io/jeremydbean/toc2026:latest}", compose)

    def test_private_runtime_data_is_excluded_from_images(self):
        dockerignore = set(read(".dockerignore").splitlines())
        for entry in (".env", "backups", "corpse", "gods", "heroes", "log", "player",
                      "state", "area/bugs.txt*", "area/notes.txt", "area/ban.txt",
                      "area/shutdown.txt"):
            with self.subTest(entry=entry):
                self.assertIn(entry, dockerignore)

        dockerfile = read("docker/Dockerfile")
        # The image's mount points exist and the world is loaded at build
        # time, so an image whose areas do not boot is never produced.
        self.assertIn("mkdir -p /app/area /app/player /app/gods /app/heroes /app/corpse /app/log /app/backups",
                      dockerfile)
        self.assertIn("../merc --check-area", dockerfile)
        self.assertIn("COPY --from=build /src/area /app/dist/area", dockerfile)
        self.assertNotIn("valgrind", dockerfile)

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
                    "promote",
                    "backup",
                    "restore",
                    "uninstall",
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

    def test_live_game_has_watchdog_and_restarts(self):
        comm = read("src/comm.c")
        game_service = read("deploy/windows-vm/toc-game.service")

        self.assertIn('notify_systemd( "READY=1', comm)
        self.assertIn('notify_systemd( "WATCHDOG=1" )', comm)
        self.assertIn("Type=notify", game_service)
        self.assertIn("WatchdogSec=", game_service)
        self.assertIn("Restart=always", game_service)

    def test_retired_hosts_left_nothing_behind(self):
        """The Raspberry Pi and Hyper-V VM are gone (2026-09-29, 2026-10-01);
        so are their installers, units and runbooks (2026-11-11). Only the
        live Oracle host's scripts remain in deploy/."""
        self.assertEqual(sorted(p.name for p in (ROOT / "deploy").glob("toc2026-*")), [])
        for gone in ("deploy/systemd", "deploy/apt", "deploy/journald", "deploy/tmpfiles",
                     "deploy/README.md", "deploy/install-pi.sh", "deploy/update-pi.sh",
                     "deploy/pi.env.example", "deploy/windows-vm/Publish-ToCWeb.ps1",
                     "zStartup", "archive"):
            with self.subTest(path=gone):
                self.assertFalse((ROOT / gone).exists())
        for kept in ("deploy/toc-restore", "deploy/sync-player-backup.sh",
                     "deploy/windows-vm/toc-deploy", "deploy/windows-vm/toc-auto-deploy",
                     "deploy/windows-vm/toc-state-sync"):
            with self.subTest(path=kept):
                self.assertTrue((ROOT / kept).is_file())

    def test_documentation_covers_access_auth_and_builds(self):
        hosting = read("wiki/hosting-guide.md")
        security = read(".github/SECURITY.md")
        self.assertIn("make -j1", hosting)
        self.assertIn("do not forward port 9001", security)


if __name__ == "__main__":
    unittest.main()
