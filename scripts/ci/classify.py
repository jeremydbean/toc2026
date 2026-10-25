#!/usr/bin/env python3
"""Which tests a change needs, decided by a small, explicit policy.

    python3 scripts/ci/classify.py --head SHA [--base SHA] [--full] --out plan.json

The Validate workflow runs this first. It compares the commit under test
with a *trusted base* -- the newest commit on main, an ancestor of this
one, whose push run's deploy-gate passed (find_trusted_base) -- and sorts
every changed path into a class. The class of the change is the widest of
its paths':

  state        what the live game writes and the state sync commits:
               player files, logs, runtime area files. Never deployed,
               never run; nothing to test.
  docs         documentation no running code reads: the Markdown and
               notes. Cheap checks only -- except that some documents are
               contracts a test holds to the source (the achievements
               catalog, the install guides), and those tests run.
  web-ui       the browser terminal's static files: the JavaScript and
               web integration tests.
  web-backend  the dashboard's Python: the modules that exercise it.
  tests        test modules alone: those modules.
  full         everything else -- C and headers, area and generator data,
               scripts, the build, the shared test harness, CI and deploy
               policy, dependencies, and any path no rule names. Every
               module, the sanitizer jobs and the serial job.

A missing base, an unreadable diff, a forced run (--full: schedules, a
manual run) all mean full. Nothing here guesses at what a C function
reaches: one changed source file means the whole suite.

Why a trusted base and not the push's own "before": toc-auto-deploy ships
a code commit on a passing run of any commit built on it. A docs commit
pushed on top of code that failed must not pass on a docs-sized check, so
the diff runs from the last commit whose runtime CI has vouched for --
which brings the failed code into this run's diff and its full coverage.
A commit that passed reached that state either by running everything or
by changing nothing at runtime since one that did; that induction is what
lets a later partial run stand on it. The plan also records a fingerprint
of the deployable tree (the paths toc-auto-deploy calls code), and a
partial plan whose class claims no runtime change but whose fingerprint
moved is promoted to full.

The gate (scripts/ci/gate.py) recomputes the plan from the same base and
refuses a run whose executed plan differs, whose base is not a trusted
ancestor, or that is missing any result the plan asked for.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

# Narrowest first; a change takes the widest class among its paths.
ORDER = ["state", "docs", "web-ui", "web-backend", "tests", "full"]

# Written by the live game and committed by toc-state-sync: the same list
# as validate.yml's paths-ignore. Not deployed (toc-deploy excludes them).
STATE_GLOBS = [
    "player/**", "gods/**", "log/**", "heroes/**", "corpse/**", "area/built/**",
    "area/notes.txt", "area/bugs.txt", "area/ideas.txt", "area/typos.txt",
    "area/bugs.txt.*", "area/ideas.txt.*", "area/typos.txt.*",
    "area/pkilldata.txt", "area/wizlist.txt", "area/maxload.txt", "area/offense.txt",
    "area/relics.txt", "area/not.txt", "area/ban.txt", "area/dpsboard.txt",
]

# Paths that look narrow but are not: the shared harness, CI and deploy
# policy, and dependency lists. Checked before the narrow classes.
ALWAYS_FULL_GLOBS = [
    "tests/live_mud.py", "tests/fixtures/**", "tests/ci_*.json", "tests/*.c",
    "tests/*.lua", "scripts/ci/**", "scripts/test-parallel.sh", "scripts/validate.sh",
    ".github/**", "deploy/**", "webadmin/requirements.txt", "scripts/requirements.txt",
    "requirements*.txt", "Makefile", "CMakeLists.txt", "Dockerfile", "docker-*",
    ".gitattributes", ".gitignore",
]

DOC_GLOBS = ["wiki/**", "notes/**", "*.md", "**/*.md", "LICENSE", "LICENSE.*"]

WEB_UI_GLOBS = ["webadmin/static/**"]
# The browser tests (node) and the integration tests that serve or drive
# the static client: its JavaScript, the bridge, help paging, real IPs.
WEB_UI_MODULES = [
    "test_audit_tooling", "test_command_sequence", "test_console_output",
    "test_players_online", "test_web_client_real_ip", "test_web_help_and_paging",
    "test_webadmin_api", "test_websocket_close",
]

WEB_BACKEND_GLOBS = ["webadmin/**"]

TEST_MODULE_GLOBS = ["tests/test_*.py", "tests/test_*.js"]

# The Oracle reads these wiki pages at run time (webadmin/oracle.py's
# _DOC_FILES), so they are web-backend content, not inert documentation.
ORACLE_MODULES = ["test_oracle", "test_oracle_bridge_live"]

SERIAL_DEFAULT = "test_login_throttle"

# toc-auto-deploy's deployable(): everything but these is code a deploy
# carries. tests/test_ci_classify.py holds the two lists together.
DEPLOY_EXCLUDES = [
    "player/**", "gods/**", "heroes/**", "log/**", "corpse/**", "notes/**", "wiki/**",
    "tests/**", ".github/**", "**/*.md", "*.md", "area/notes.txt", "area/bugs.txt*",
    "area/ideas.txt*", "area/typos.txt*", "area/pkilldata.txt", "area/wizlist.txt",
    "area/maxload.txt", "area/offense.txt", "area/relics.txt", "area/not.txt",
    "area/ban.txt", "area/dpsboard.txt", "area/built/**",
]


def match(path: str, globs: list[str]) -> bool:
    for pattern in globs:
        if fnmatch.fnmatchcase(path, pattern):
            return True
        # "dir/**" also names the directory's direct children.
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def oracle_docs() -> list[str]:
    try:
        text = (ROOT / "webadmin" / "oracle.py").read_text(encoding="utf-8")
    except OSError:
        return []
    found = re.search(r"_DOC_FILES\s*=\s*\(([^)]*)\)", text)
    return re.findall(r'"([^"]+)"', found.group(1)) if found else []


def test_modules(tests: Path = TESTS) -> list[str]:
    return sorted(p.stem for p in tests.glob("test_*.py"))


def module_text(module: str, tests: Path = TESTS) -> str:
    try:
        return (tests / f"{module}.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


SERVER_MARKERS = ("LiveMud(", "find_binary", "skip_reason(", "TOC_SERVER_BINARY",
                  '"merc"', "'merc'", "bin/rom")


def uses_server(module: str, tests: Path = TESTS) -> bool:
    """Whether a module boots or runs the game, and so needs the built
    binary. Generous on purpose: a module wrongly thought to need it only
    costs a build; one wrongly thought not to would skip, and the gate
    fails an unexplained skip."""
    text = module_text(module, tests)
    return any(marker in text for marker in SERVER_MARKERS)


# The policy's own tests name paths as data; that is not reading them.
MENTION_SCAN_EXCLUDE = {"test_ci_classify"}


def mentioning(name: str, tests: Path = TESTS) -> list[str]:
    """Test modules whose source names a file: the ones that read it."""
    return [m for m in test_modules(tests)
            if m not in MENTION_SCAN_EXCLUDE and name in module_text(m, tests)]


def doc_contract_modules(path: str, tests: Path = TESTS) -> list[str]:
    """Test modules that read a document by name and hold it to the code."""
    return mentioning(Path(path).name, tests)


def classify_path(path: str, tests: Path = TESTS) -> tuple[str, list[str], str]:
    """(class, modules it selects, the reason) for one changed path."""
    if match(path, STATE_GLOBS):
        return "state", [], "live state the game writes; never deployed"
    if match(path, ALWAYS_FULL_GLOBS):
        return "full", [], "shared harness, CI/deploy policy, build or dependency"
    if path in oracle_docs():
        return "web-backend", ORACLE_MODULES + doc_contract_modules(path, tests), \
            "a wiki page the Oracle reads at run time"
    if match(path, DOC_GLOBS) and not path.startswith(("webadmin/", "area/", "src/")):
        contracts = doc_contract_modules(path, tests)
        return "docs", contracts, ("documentation; the tests that hold it to the code"
                                   if contracts else "documentation no code reads")
    if match(path, WEB_UI_GLOBS):
        return "web-ui", WEB_UI_MODULES, "browser terminal static asset"
    if match(path, WEB_BACKEND_GLOBS):
        modules = [m for m in test_modules(tests) if "webadmin" in module_text(m, tests)]
        return "web-backend", modules, "dashboard Python; the modules that use it"
    if match(path, TEST_MODULE_GLOBS):
        stem = Path(path).stem
        if path.endswith(".py"):
            # A deleted module selects nothing; the gate's inventory is the disk.
            return "tests", [stem] if (tests / f"{stem}.py").exists() else [], \
                "a test module changed"
        runners = mentioning(Path(path).name, tests)
        return ("tests", runners, "a browser test, and the modules that run it") if runners \
            else ("full", [], "a browser test no module names")
    return "full", [], "runtime code, data, build, or a path no rule names"


def fingerprint(sha: str, cwd: Path = ROOT) -> str | None:
    """A hash of the deployable tree at sha: every path toc-auto-deploy
    calls code, with its blob id. Equal fingerprints, same payload."""
    try:
        listing = subprocess.run(["git", "ls-tree", "-r", sha], cwd=cwd, check=True,
                                 capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    digest = hashlib.sha256()
    for line in listing.splitlines():
        meta, _, path = line.partition("\t")
        if not match(path, DEPLOY_EXCLUDES):
            digest.update(f"{path}\0{meta.split()[2]}\n".encode())
    return digest.hexdigest()


def changed_paths(base: str, head: str, cwd: Path = ROOT) -> list[str] | None:
    """Every path that differs, renames as a delete and an add."""
    try:
        out = subprocess.run(["git", "diff", "--name-only", "--no-renames", base, head],
                             cwd=cwd, check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [line for line in out.splitlines() if line]


def plan_for(paths: list[str] | None, *, head: str, base: str | None, why_full: str = "",
             serial: list[str], sanitize: list[str], tests: Path = TESTS,
             base_fingerprint: str | None = None, head_fingerprint: str | None = None) -> dict:
    """The plan for a change. paths None means the diff could not be read."""
    plan = {"schema": 1, "head": head, "base": base, "paths": paths or [],
            "classes": {}, "reasons": [], "fingerprint": head_fingerprint}
    every = test_modules(tests)
    if why_full or base is None or paths is None:
        reason = why_full or ("no trusted base" if base is None else "the diff could not be read")
        return full_plan(plan, every, serial, sanitize, reason)

    worst = "state"
    selected: set[str] = set()
    for path in paths:
        cls, modules, reason = classify_path(path, tests)
        plan["classes"][path] = cls
        plan["reasons"].append(f"{path}: {cls} ({reason})")
        if ORDER.index(cls) > ORDER.index(worst):
            worst = cls
        selected.update(m for m in modules if m in every)
    if worst == "full":
        return full_plan(plan, every, serial, sanitize, "a path needs full coverage")
    # docs, state and tests claim the deployable tree did not move.
    if worst in ("state", "docs", "tests") and base_fingerprint != head_fingerprint:
        return full_plan(plan, every, serial, sanitize,
                         "the deployable tree changed under a non-runtime class")

    modules = sorted(selected)
    plan.update({
        "scope": "partial", "class": worst, "modules": modules,
        "omitted": len(every) - len(modules),
        "omitted_reason": f"{worst} change: only the modules its paths name",
        "serial_modules": [m for m in serial if m in modules],
        # The sanitizer binary is for C; a partial plan has none, unless a
        # changed test module is one the sanitizer jobs play.
        "sanitize_modules": [m for m in sanitize if m in modules and worst == "tests"],
    })
    plan["jobs"] = {
        "build": any(uses_server(m, tests) for m in modules),
        "tests": bool([m for m in modules if m not in plan["serial_modules"]]),
        "serial": bool(plan["serial_modules"]),
        "sanitize": bool(plan["sanitize_modules"]),
    }
    return plan


def full_plan(plan: dict, every: list[str], serial: list[str], sanitize: list[str],
              reason: str) -> dict:
    plan.update({
        "scope": "full", "class": "full", "modules": every, "omitted": 0,
        "omitted_reason": "", "full_reason": reason,
        "serial_modules": [m for m in serial if m in every],
        "sanitize_modules": list(sanitize),
        "jobs": {"build": True, "tests": True, "serial": True, "sanitize": True},
    })
    return plan


def shard_counts(plan: dict, full_shards: int, full_sanitize_shards: int,
                 durations: dict[str, float]) -> tuple[int, int]:
    """How many normal and sanitizer shards a plan needs. A full plan takes
    the workflow's; a partial one enough for about SHARD_BUDGET seconds of
    measured module time per shard, at least one if it has any modules."""
    if plan["scope"] == "full":
        return full_shards, full_sanitize_shards
    known = sorted(durations.values())
    median = known[len(known) // 2] if known else 30.0
    normal = [m for m in plan["modules"] if m not in plan["serial_modules"]]
    cost = sum(max(2.0, durations.get(m, median)) for m in normal)
    shards = 0 if not normal else min(full_shards, max(1, -(-int(cost) // SHARD_BUDGET)))
    sanitize = min(full_sanitize_shards, len(plan["sanitize_modules"]))
    return shards, sanitize


# A shard runs four modules at a time, so this is about three minutes of
# wall time; a partial plan is spread over as few shards as fit it.
SHARD_BUDGET = 720


# ---------------------------------------------------------------- the base

def github_json(url: str, token: str | None):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def is_ancestor(base: str, head: str, cwd: Path = ROOT) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=cwd,
                          capture_output=True).returncode == 0


def gate_passed(repo: str, run_id: int, token: str | None, gate_job: str = "deploy-gate") -> bool:
    jobs = github_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
                       "?filter=latest&per_page=100", token).get("jobs", [])
    named = [j for j in jobs if j.get("name") == gate_job]
    return bool(named) and named[-1].get("conclusion") == "success"


def find_trusted_base(repo: str, head: str, token: str | None,
                      cwd: Path = ROOT) -> tuple[str | None, str]:
    """The newest main commit, an ancestor of head, whose push run's
    deploy-gate passed; (None, why) when there is none to be had."""
    try:
        data = github_json(f"https://api.github.com/repos/{repo}/actions/workflows/"
                           "validate.yml/runs?branch=main&event=push&status=success"
                           "&per_page=60", token)
    except Exception as exc:  # noqa: BLE001 -- any failure means no base
        return None, f"could not ask GitHub for passing runs: {exc}"
    for run in data.get("workflow_runs", []):
        sha = run.get("head_sha")
        if not sha or run.get("event") != "push" or run.get("head_branch") != "main":
            continue
        if not is_ancestor(sha, head, cwd):
            continue
        try:
            if gate_passed(repo, run["id"], token):
                return sha, f"run {run['id']} passed deploy-gate on {sha[:8]}"
        except Exception as exc:  # noqa: BLE001
            return None, f"could not read run {run.get('id')}'s jobs: {exc}"
    return None, "no passing push run on main is an ancestor of this commit"


def verify_trusted_base(repo: str, base: str, head: str, token: str | None,
                        cwd: Path = ROOT) -> tuple[bool, str]:
    """The gate's half of find_trusted_base: base is an ancestor of head
    and a push run on main for exactly base passed its deploy-gate."""
    if not is_ancestor(base, head, cwd):
        return False, "not an ancestor of the commit under test"
    try:
        data = github_json(f"https://api.github.com/repos/{repo}/actions/workflows/"
                           f"validate.yml/runs?head_sha={base}&event=push&branch=main"
                           "&status=success&per_page=20", token)
        for run in data.get("workflow_runs", []):
            if run.get("head_sha") == base and gate_passed(repo, run["id"], token):
                return True, f"run {run['id']} passed deploy-gate"
    except Exception as exc:  # noqa: BLE001 -- unverifiable is untrusted
        return False, f"could not ask GitHub: {exc}"
    return False, "no push run on main passed deploy-gate for it"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--head", default=os.environ.get("GITHUB_SHA", "HEAD"))
    parser.add_argument("--base", help="a trusted base, skipping the GitHub lookup")
    parser.add_argument("--full", action="store_true", help="run everything")
    parser.add_argument("--full-reason", default="a full run was asked for")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--serial", default=SERIAL_DEFAULT)
    parser.add_argument("--sanitize", default="")
    parser.add_argument("--shards", type=int, default=int(os.environ.get("SHARDS") or 8))
    parser.add_argument("--sanitize-shards", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--github-output", type=Path,
                        default=Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None)
    args = parser.parse_args()

    head = subprocess.run(["git", "rev-parse", args.head], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    base, base_source = args.base, "given"
    if args.full:
        base_source = "not looked for: full run"
    elif base is None:
        base, base_source = find_trusted_base(args.repo, head, os.environ.get("GITHUB_TOKEN"))
    if base is not None:
        base = subprocess.run(["git", "rev-parse", base], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip() or None
    paths = changed_paths(base, head) if base else None
    plan = plan_for(paths, head=head, base=base,
                    why_full=args.full_reason if args.full else "",
                    serial=args.serial.split(), sanitize=args.sanitize.split(),
                    base_fingerprint=fingerprint(base) if base else None,
                    head_fingerprint=fingerprint(head))
    plan["base_source"] = base_source
    try:
        durations = {k: float(v) for k, v in json.loads(
            (TESTS / "ci_durations.json").read_text())["modules"].items()}
    except (OSError, ValueError, KeyError):
        durations = {}
    plan["shards"], plan["sanitize_shards"] = shard_counts(
        plan, args.shards, args.sanitize_shards, durations)
    plan["run_id"] = os.environ.get("GITHUB_RUN_ID")
    plan["event"] = os.environ.get("GITHUB_EVENT_NAME")

    text = json.dumps(plan, indent=1) + "\n"
    if args.out:
        args.out.write_text(text)
    print(f"plan: {plan['scope']} ({plan['class']}); base {base or '-'} ({base_source}); "
          f"{len(plan['modules'])} module(s), {plan['omitted']} omitted")
    for reason in plan["reasons"][:50]:
        print(f"  {reason}")
    if plan.get("full_reason"):
        print(f"  full because: {plan['full_reason']}")
    if args.github_output:
        with args.github_output.open("a") as out:
            for job, needed in plan["jobs"].items():
                print(f"{job}={'true' if needed else 'false'}", file=out)
            print(f"scope={plan['scope']}", file=out)
            print(f"class={plan['class']}", file=out)
            print(f"shards={json.dumps(list(range(1, plan['shards'] + 1)))}", file=out)
            print(f"shard_count={plan['shards']}", file=out)
            print(f"sanitize_shards={json.dumps(list(range(1, plan['sanitize_shards'] + 1)))}",
                  file=out)
            print(f"sanitize_shard_count={plan['sanitize_shards']}", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
