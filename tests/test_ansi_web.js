"use strict";

// The web consoles' colours (2026-10-23, from a Codex review):
// - ANSI 100-107 are bright backgrounds in the player client too, and its
//   stylesheet draws them;
// - a white background leaves the text colour alone;
// - reverse video swaps foreground and background (filter: invert() drew
//   each colour's complement);
// - 256-colour and true colour are drawn, not dropped.

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

const STATIC = path.join(__dirname, "..", "webadmin", "static");
const read = (file) => fs.readFileSync(path.join(STATIC, file), "utf8");

test("both web clients use the streaming decoder and load it before their script", () => {
    for (const [script, html, writer] of [
        ["client.js", "client.html", "gameOutput.write(message)"],
        ["app.js", "index.html", "consoleOutput.write"],
    ]) {
        const source = read(script);
        const document = read(html);
        assert.match(source, /TocConsoleOutput.create\(/);
        assert.ok(source.includes(writer));
        assert.ok(document.indexOf("/static/console-output.js") < document.indexOf("/static/" + script));
    }
});

for (const [file, prefix] of [["client.css", ""], ["app.css", "#game-terminal "]]) {
    test(`${file}: every colour, no invert, white keeps the text colour`, () => {
        const css = read(file);
        assert.doesNotMatch(css, /filter:\s*invert/);
        const names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"];
        const all = [...names, ...names.map((n) => `bright-${n}`)];
        for (const kind of ["fg", "bg"]) {
            for (const name of all) {
                const rule = css.match(new RegExp(`${prefix}\\.ansi-${kind}-${name} \\{([^}]*)\\}`));
                assert.ok(rule, `${kind} ${name}`);
                assert.match(rule[1], new RegExp(`--ansi-${kind}: #[0-9a-f]{6};`));
                if (kind === "bg") assert.doesNotMatch(rule[1], /(^|;)\s*color:/, `${name} background sets a text colour`);
            }
            assert.match(css, new RegExp(`${prefix}\\.ansi-${kind}-rgb \\{`));
        }
        // Reverse video comes after every colour rule, so it wins.
        const inverse = css.indexOf(`${prefix}.ansi-inverse {`);
        assert.ok(inverse > css.lastIndexOf(".ansi-bg-"), "inverse after the colours");
        assert.match(css.slice(inverse), /color: var\(--ansi-bg, var\(--terminal-bg/);
        assert.match(css.slice(inverse), /background: var\(--ansi-fg, #[0-9a-f]{6}\);/);
    });
}
