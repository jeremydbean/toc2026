"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
require("../webadmin/static/console-output.js");

function capture(chunks) {
    const runs = [];
    const secrets = [];
    const decoder = TocConsoleOutput.create((text, className) => runs.push({ text, className }), (value) => secrets.push(value));
    for (const chunk of chunks) decoder.write(chunk);
    return { decoder, runs, secrets };
}

function characters(runs) {
    return runs.flatMap(({ text, className }) => Array.from(text, (char) => [char, className]));
}

test("colors, attributes, resets, and bright backgrounds survive parsing", () => {
    const { runs } = capture(["plain\x1b[1;31;44mred\x1b[22;39;49mnormal\x1b[96;101mbright\x1b[mend"]);
    assert.deepEqual(runs, [
        { text: "plain", className: "" },
        { text: "red", className: "ansi-bold ansi-fg-red ansi-bg-blue" },
        { text: "normal", className: "" },
        { text: "bright", className: "ansi-fg-bright-cyan ansi-bg-bright-red" },
        { text: "end", className: "" },
    ]);
});

test("all network split positions give identical output and password negotiation", () => {
    const stream = "Name:\r\n\xff\xfb\x01Password:\xff\xfc\x01\n\r\x1b[1;32mgreen\x1b[0m plain\xff\xfa\x18ignored\xff\xffdata\xff\xf0!\xff\xff";
    const baseline = capture([stream]);
    for (let i = 0; i <= stream.length; i += 1) {
        const result = capture([stream.slice(0, i), stream.slice(i)]);
        assert.deepEqual(characters(result.runs), characters(baseline.runs), `split ${i}`);
        assert.deepEqual(result.secrets, [false, true, false], `password split ${i}`);
    }
    assert.deepEqual(characters(capture([...stream]).runs), characters(baseline.runs));
    assert.equal(baseline.runs.map((run) => run.text).join(""), "Name:\nPassword:\ngreen plain!\xff");
});

test("color persists across frames until reset; reconnect clears partial sequences", () => {
    const result = capture(["\x1b[31mred", "still red", "\x1b["]);
    result.decoder.reset();
    result.decoder.write("plain\xff");
    result.decoder.reset();
    result.decoder.write("new session");
    assert.deepEqual(result.runs.map((run) => run.className), ["ansi-fg-red", "ansi-fg-red", "", ""]);
    assert.deepEqual(result.secrets, [false, false, false]);
});

test("plain text and mixed line endings remain readable across frames", () => {
    const { runs } = capture(["one\r", "\ntwo\n", "\rthree\n\nfour\t<&>\0"]);
    assert.equal(runs.map((run) => run.text).join(""), "one\ntwo\nthree\n\nfour\t<&>");
    assert.ok(runs.every((run) => run.className === ""));
});

test("unsupported controls do not become markup, text, or accidental attributes", () => {
    const { runs } = capture(["\x1b[38;2;1;31;4m<img src=x onerror=alert(1)>\x1b[2J", "\x1b]0;hidden title\x07ok", "\x1b]8;;https://example.com\x1b\\link\x1b]8;;\x1b\\"]);
    assert.equal(runs.map((run) => run.text).join(""), "<img src=x onerror=alert(1)>oklink");
    assert.ok(runs.every((run) => run.className === ""));
});

test("oversized and malformed SGR sequences are discarded without changing colors", () => {
    const { runs } = capture(["\x1b[31mred\x1b[", "1;".repeat(10000), "mstill red\x1b[?32mred\x1b[0mplain"]);
    assert.deepEqual(runs.map((run) => run.className), ["ansi-fg-red", "ansi-fg-red", "ansi-fg-red", ""]);
});

test("all supported foreground and background classes use only the fixed palette", () => {
    for (const first of [30, 40, 90, 100]) {
        for (let offset = 0; offset < 8; offset += 1) {
            const { runs } = capture([`\x1b[${first + offset}mcolor`]);
            assert.match(runs[0].className, /^ansi-(fg|bg)-(bright-)?(black|red|green|yellow|blue|magenta|cyan|white)$/);
        }
    }
});
