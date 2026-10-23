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

function cut(text, signature) {
    const start = text.indexOf(signature);
    assert.notEqual(start, -1, signature);
    let depth = 0;
    for (let i = text.indexOf("{", start); i < text.length; i += 1) {
        if (text[i] === "{") depth += 1;
        if (text[i] === "}" && --depth === 0) return text.slice(start, i + 1);
    }
    throw new Error("unbalanced " + signature);
}

// The player client's SGR handling, cut from client.js and run alone.
function clientDecoder() {
    const js = read("client.js");
    const body = [
        cut(js, "function freshAnsiStyle()"),
        js.slice(js.indexOf("const ANSI_COLORS"), js.indexOf("\n", js.indexOf("const ANSI_COLORS"))),
        cut(js, "function hex("), cut(js, "function xterm256("), cut(js, "function extendedAnsi("),
        cut(js, "function colourParts("), cut(js, "function ansiClassName()"),
        cut(js, "function ansiInlineStyle()"), cut(js, "function applyAnsiCodes("),
    ].join("\n");
    return new Function("state", body +
        "\nstate.ansiStyle = freshAnsiStyle();" +
        "\nreturn (codes) => { applyAnsiCodes(codes); return [ansiClassName(), ansiInlineStyle()]; };")({});
}

test("the player client: bright backgrounds, extended colours", () => {
    const sgr = clientDecoder();
    assert.deepEqual(sgr("101"), ["ansi-bg-bright-red", ""]);
    assert.deepEqual(sgr("0;31;47"), ["ansi-fg-red ansi-bg-white", ""]);
    assert.deepEqual(sgr("0;38;5;208"), ["ansi-fg-rgb", "--ansi-fg: #ff8700;"]);
    assert.deepEqual(sgr("0;38;5;12"), ["ansi-fg-bright-blue", ""]);
    assert.deepEqual(sgr("0;7;48;2;10;20;30"), ["ansi-inverse ansi-bg-rgb", "--ansi-bg: #0a141e;"]);
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
        assert.match(css.slice(inverse), /color: var\(--ansi-bg, #[0-9a-f]{6}\); background: var\(--ansi-fg, #[0-9a-f]{6}\);/);
    });
}
