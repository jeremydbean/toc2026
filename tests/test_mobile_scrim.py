"""On a phone the menu and the client's tool panel could not be used
(owner, 2026-11-12: "doesn't let you click anything after clicking the
menu. It's dimmed").

theme-dragon.css makes .app-shell and .client-app their own stacking
contexts (position: relative; z-index: 1). The dimming scrim sat after
the shell, at body level, so its z-index (25, 50) was compared with the
shell's 1 and it covered the whole shell -- the open sidebar or panel
included -- and every tap landed on the scrim. Each scrim now lives
inside its shell, beside the sidebar or panel it dims behind. Checked in
a browser at 390 px before and after; this pins the structure.
"""

from __future__ import annotations

import unittest
from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "webadmin" / "static"


class Ancestry(HTMLParser):
    VOID = {"meta", "link", "br", "img", "input", "hr", "source", "area", "col",
            "embed", "param", "track", "wbr", "base"}

    def __init__(self, target_id: str) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.target_id = target_id
        self.found: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        label = "%s.%s" % (tag, (attrs.get("class") or "").split(" ")[0])
        if attrs.get("id") == self.target_id and self.found is None:
            self.found = list(self.stack)
        if tag not in self.VOID:
            self.stack.append(label)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].split(".")[0] == tag:
                del self.stack[i:]
                break


def ancestors(page: str, element_id: str) -> list[str]:
    parser = Ancestry(element_id)
    parser.feed((STATIC / page).read_text(encoding="utf-8"))
    assert parser.found is not None, f"{element_id} not in {page}"
    return parser.found


class ScrimTests(unittest.TestCase):
    def test_the_sidebar_scrim_is_inside_the_app_shell(self) -> None:
        self.assertIn("div.app-shell", ancestors("index.html", "sidebar-scrim"))

    def test_the_panel_scrim_is_inside_the_client_app(self) -> None:
        self.assertIn("div.client-app", ancestors("client.html", "panel-scrim"))

    def test_the_theme_still_makes_the_shells_stacking_contexts(self) -> None:
        """If the theme stops doing this, the scrims may move back out --
        but the two must change together."""
        theme = (STATIC / "theme-dragon.css").read_text(encoding="utf-8")
        self.assertIn(".app-shell,\n.client-app {\n    position: relative;\n    z-index: 1;", theme)


if __name__ == "__main__":
    unittest.main()
