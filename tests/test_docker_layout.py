"""The Docker files live in docker/, and an installation keeps its project.

The repository root was tidied on 2026-11-12: `Dockerfile` became
`docker/Dockerfile` and `docker-compose.yml` became `docker/compose.yml`.
Three things have to stay exactly as they were for that to be invisible:

* The build context is the checkout's root, so the root .dockerignore
  keeps player files, logs and reports out of every image.
* Compose reads .env and every relative path (./state, the context) from
  the project directory, and names the project after it. The launchers
  pass --project-directory the checkout and -f docker/compose.yml, so the
  project is still the checkout folder's name -- the one it had when the
  file sat at the root -- and `toc.sh stop` or `update` still finds the
  container an existing installation started.
* `toc.sh update` pulls the move and then execs the launcher it pulled
  (`_finish-update`); an installation updated across the move must come
  out on the same project. The update test runs the real launchers in a
  throwaway Git checkout against a stand-in `docker` that refuses, as
  compose does, a compose file that is not there.

Synthetic checkouts only; nothing here reads or writes runtime state.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class LayoutTests(unittest.TestCase):
    def test_the_docker_files_are_in_docker_and_not_at_the_root(self) -> None:
        self.assertTrue((ROOT / "docker" / "Dockerfile").is_file())
        self.assertTrue((ROOT / "docker" / "compose.yml").is_file())
        for gone in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                     "compose.yml", "compose.yaml"):
            with self.subTest(path=gone):
                self.assertFalse((ROOT / gone).exists())

    def test_the_root_dockerignore_is_the_one_that_applies(self) -> None:
        # BuildKit prefers <Dockerfile>.dockerignore beside the Dockerfile
        # to the context's .dockerignore; one in docker/ would let player
        # data into the published image.
        self.assertTrue((ROOT / ".dockerignore").is_file())
        self.assertEqual(sorted(p.name for p in (ROOT / "docker").glob("*dockerignore")), [])

    def test_compose_builds_from_the_root_and_names_no_project(self) -> None:
        compose = read("docker/compose.yml")
        build = compose[compose.index("    build:"):compose.index("    container_name:")]
        self.assertRegex(build, r"\n\s+context: \.\n")
        self.assertIn("dockerfile: docker/Dockerfile", build)
        # A fixed name: would rename the project of every installation
        # whose checkout folder is called something else.
        self.assertIsNone(re.search(r"(?m)^name:", compose))

    def test_the_image_workflow_builds_the_moved_dockerfile_from_the_root(self) -> None:
        workflow = read(".github/workflows/docker-image.yml")
        self.assertRegex(workflow, r"\n\s+context: \.\n\s+file: docker/Dockerfile\n")

    def test_every_launcher_compose_call_names_the_file_and_the_checkout(self) -> None:
        shell = read("scripts/toc_common.sh")
        self.assertIn('docker compose --project-directory "$TOC_REPO_ROOT" \\\n'
                      '        -f "$TOC_REPO_ROOT/docker/compose.yml" "$@"', shell)
        powershell = read("scripts/toc_common.ps1")
        self.assertIn("Join-Path (Join-Path $script:TocRepoRoot 'docker') 'compose.yml'",
                      powershell)
        self.assertIn("@('compose', '--project-directory', $script:TocRepoRoot, '-f', "
                      "$script:TocComposeFile)", powershell)
        # Nothing calls compose for a project without going through those.
        for relative in ("toc.sh", "install.sh", "scripts/toc_common.sh",
                         "scripts/toc_native.sh"):
            text = read(relative)
            with self.subTest(path=relative):
                calls = re.findall(r"docker compose (?!version)[^\n]*", text)
                self.assertEqual([c for c in calls if "--project-directory" not in c], [])
        for relative in ("toc.ps1", "install.ps1", "scripts/toc_common.ps1"):
            text = read(relative)
            with self.subTest(path=relative):
                self.assertNotIn("compose --project-directory", text)
                self.assertNotIn("'compose', '--project-directory', $script:TocRepoRoot)", text)


@unittest.skipIf(shutil.which("docker") is None
                 or subprocess.run(["docker", "compose", "version"], capture_output=True)
                 .returncode != 0, "docker compose is not installed")
class ComposeConfigTests(unittest.TestCase):
    """What compose itself makes of the file, as the launchers call it."""

    def test_the_project_paths_and_name_are_the_checkouts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="toc-compose-") as tmp:
            checkout = pathlib.Path(tmp) / "mytoc"
            (checkout / "docker").mkdir(parents=True)
            shutil.copy(ROOT / "docker" / "compose.yml", checkout / "docker" / "compose.yml")
            (checkout / ".env").write_text("TOC_STATE=./state\nMUD_PORT=9123\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
            for name in ("TOC_STATE", "MUD_PORT", "TOC_IMAGE"):
                env.pop(name, None)
            # From another directory, as a launcher may be run.
            proc = subprocess.run(
                ["docker", "compose", "--project-directory", str(checkout),
                 "-f", str(checkout / "docker" / "compose.yml"), "config", "--format", "json"],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            config = json.loads(proc.stdout)
        self.assertEqual(config["name"], "mytoc")
        game = config["services"]["game"]
        self.assertEqual(game["build"]["context"], str(checkout))
        self.assertEqual(game["build"]["dockerfile"], "docker/Dockerfile")
        sources = {v["target"]: v["source"] for v in game["volumes"]}
        self.assertEqual(sources["/app/player"], str(checkout / "state" / "player"))
        # .env was read from the checkout, not from docker/.
        self.assertEqual({p["published"] for p in game["ports"]} & {"9123"}, {"9123"})


FAKE_DOCKER = r"""#!/usr/bin/env bash
# A stand-in docker. compose calls are checked as compose checks them: an
# -f file must exist, and with none the project directory must hold a
# default compose file. The project is named as compose names it.
if [ "$1" = compose ]; then
    shift
    pd=""
    files=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --project-directory) pd="$2"; shift 2 ;;
            -f) files+=("$2"); shift 2 ;;
            *) break ;;
        esac
    done
    [ "${1:-}" = version ] && { echo "Docker Compose version v2.99.0"; exit 0; }
    if [ "${#files[@]}" -eq 0 ]; then
        base="${pd:-$PWD}"
        for c in compose.yaml compose.yml docker-compose.yml docker-compose.yaml; do
            [ -f "$base/$c" ] && { files=("$base/$c"); break; }
        done
        [ "${#files[@]}" -gt 0 ] || { echo "no configuration file provided: not found" >&2; exit 14; }
    fi
    for f in "${files[@]}"; do
        [ -f "$f" ] || { echo "open $f: no such file or directory" >&2; exit 14; }
    done
    project="$(basename "${pd:-$(dirname "${files[0]}")}")"
    echo "compose project=$project file=${files[0]} :: $*" >> "$CALLS"
    case "$1" in
        up) touch "$CALLS.up" ;;
        ps) [ -f "$CALLS.up" ] && echo abc123 ;;
    esac
    exit 0
fi
echo "docker $*" >> "$CALLS"
case "$1" in
    container) exit 1 ;;          # no container from before the state folder
    inspect) echo healthy ;;
esac
exit 0
"""

OLD_TOC_COMPOSE = '''toc_compose() {
    docker compose --project-directory "$TOC_REPO_ROOT" "$@"
}'''


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class UpdateAcrossTheMoveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="toc-docker-move-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.upstream = self.tmp / "upstream"
        self.checkout = self.tmp / "my-toc"
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "docker").write_text(FAKE_DOCKER)
        (bin_dir / "docker").chmod(0o755)
        self.calls = self.tmp / "calls.log"
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(8)
        self.addCleanup(listener.close)
        self.port = listener.getsockname()[1]
        self.env = dict(os.environ, CALLS=str(self.calls),
                        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                        GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                        GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid",
                        TOC_GAME_WAIT_SECONDS="10", TOC_DOCKER_WAIT_SECONDS="5")
        for name in list(self.env):
            if name.startswith(("COMPOSE_", "TOC_STATE", "TOC_MODE", "GIT_DIR", "GIT_WORK_TREE")):
                del self.env[name]

    def git(self, cwd: pathlib.Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                       capture_output=True, text=True, timeout=60)

    def lay(self, where: pathlib.Path, *, old: bool) -> None:
        """The launcher files as they stand, or as they stood before the move."""
        (where / "scripts").mkdir(parents=True, exist_ok=True)
        for relative in ("toc.sh", "scripts/toc_native.sh", ".gitignore"):
            shutil.copy2(ROOT / relative, where / relative)
        common = read("scripts/toc_common.sh")
        compose = read("docker/compose.yml")
        if old:
            new_compose = re.search(r"toc_compose\(\) \{\n.*?\n\}", common, re.S).group(0)
            common = common.replace(new_compose, OLD_TOC_COMPOSE)
            self.assertIn(OLD_TOC_COMPOSE, common)
            (where / "docker-compose.yml").write_text(compose)
            shutil.rmtree(where / "docker", ignore_errors=True)
        else:
            (where / "docker-compose.yml").unlink(missing_ok=True)
            (where / "docker").mkdir(exist_ok=True)
            (where / "docker" / "compose.yml").write_text(compose)
        (where / "scripts" / "toc_common.sh").write_text(common)

    def toc(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.checkout / "toc.sh"), *args], cwd=self.tmp,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def test_an_update_across_the_move_keeps_the_project(self) -> None:
        self.upstream.mkdir()
        self.git(self.upstream, "init", "-q", "-b", "main")
        self.lay(self.upstream, old=True)
        self.git(self.upstream, "add", "-A")
        self.git(self.upstream, "commit", "-q", "-m", "before the move")
        self.git(self.tmp, "clone", "-q", str(self.upstream), str(self.checkout))
        (self.checkout / ".env").write_text(
            "TOC_MODE=docker\nTOC_STATE=./state\nTOC_IMAGE=example/toc:test\n"
            f"MUD_PORT={self.port}\nWEB_ADMIN_PORT={self.port}\nWEB_ADMIN_TOKEN=x\n")
        for sub in ("area", "player", "gods", "heroes", "corpse", "backups", "log"):
            (self.checkout / "state" / sub).mkdir(parents=True)
        (self.checkout / "state" / ".layout").write_text("1\n")

        before = self.toc("status")
        self.assertEqual(before.returncode, 0, before.stdout + before.stderr)
        old_calls = [l for l in self.calls.read_text().splitlines() if l.startswith("compose ")]
        self.assertTrue(old_calls)
        self.assertTrue(all(f"project=my-toc file={self.checkout}/docker-compose.yml" in l
                            for l in old_calls), old_calls)

        self.lay(self.upstream, old=False)
        self.git(self.upstream, "add", "-A")
        self.git(self.upstream, "commit", "-q", "-m", "docker files into docker/")
        self.calls.write_text("")

        update = self.toc("update")
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        self.assertFalse((self.checkout / "docker-compose.yml").exists())
        calls = [l for l in self.calls.read_text().splitlines() if l.startswith("compose ")]
        # The old launcher's prepare, then the pulled one's pull, up and wait.
        self.assertTrue(any(":: up -d --no-build game" in l for l in calls), calls)
        after = calls[[i for i, l in enumerate(calls) if ":: pull" in l or ":: build" in l][0]:]
        self.assertTrue(after)
        for line in after:
            self.assertIn(f"project=my-toc file={self.checkout}/docker/compose.yml", line)

        self.calls.write_text("")
        stop = self.toc("stop")
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)
        self.assertIn(f"compose project=my-toc file={self.checkout}/docker/compose.yml"
                      " :: stop game", self.calls.read_text())


if __name__ == "__main__":
    unittest.main()
