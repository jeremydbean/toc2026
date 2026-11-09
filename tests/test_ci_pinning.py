"""Every third-party action a workflow runs is pinned to a commit.

A tag such as v4 can be moved by whoever controls the action's
repository, and the workflows hold the deploy gate and the image
publisher. Each `uses:` names a full forty-character commit id, with
the version it stands for in a comment so Dependabot can raise it.
The token the deployer sends to the dashboard stays off curl's
command line, where any process could read it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$", re.M)


class ActionPinningTests(unittest.TestCase):
    def test_every_action_is_pinned_to_a_commit(self) -> None:
        loose = []
        seen = 0
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            for match in USES.finditer(workflow.read_text(encoding="utf-8")):
                ref, rest = match.group(1), match.group(2)
                if ref.startswith("./"):
                    continue
                seen += 1
                _, _, version = ref.partition("@")
                if not re.fullmatch(r"[0-9a-f]{40}", version) or "#" not in rest:
                    loose.append(f"{workflow.name}: {ref}")
        self.assertGreater(seen, 10)
        self.assertEqual(loose, [])

    def test_dependabot_watches_the_actions(self) -> None:
        text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertRegex(text, r"package-ecosystem:\s*[\"']?github-actions")


class DeployTokenTests(unittest.TestCase):
    def test_the_admin_token_never_rides_on_argv(self) -> None:
        script = (ROOT / "deploy" / "windows-vm" / "toc-deploy").read_text(encoding="utf-8")
        self.assertNotRegex(script, r"-H\s+[\"']?X-Admin-Token")
        self.assertRegex(script, r"printf 'X-Admin-Token: %s\\n' \"\$token\" \|\s*\n\s*curl [^\n]*-H @-")


if __name__ == "__main__":
    unittest.main()
