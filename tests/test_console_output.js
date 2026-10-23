"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
require("../webadmin/static/console-output.js");

function capture(chunks) {
    const runs = [];
    const secrets = [];
    const decoder = TocConsoleOutput.create((text, className, inlineStyle) => {
        const run = { text, className };
        if (inlineStyle) run.inlineStyle = inlineStyle;
        runs.push(run);
    }, (value) => secrets.push(value));
    for (const chunk of chunks) decoder.write(chunk);
    return { decoder, runs, secrets };
}

function characters(runs) {
    return runs.flatMap(({ text, className, inlineStyle = "" }) => Array.from(text, (char) => [char, className, inlineStyle]));
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
    // The true colour is drawn exactly, and stays until a reset; its 31
    // and 4 are not red and underline.
    assert.ok(runs.every((run) => run.className === "ansi-fg-rgb" && run.inlineStyle === "--ansi-fg: #011f04;"));
});

test("256-colour and true colour are drawn, the first sixteen from the theme", () => {
    const { runs } = capture(["[38;5;9ma[38;5;196mb[48;5;232mc[0;38;2;255;128;0md[38;5;300me[0;48;2;1;2mf[0;7;38;5;21mg"]);
    assert.deepEqual(runs, [
        { text: "a", className: "ansi-fg-bright-red" },
        { text: "b", className: "ansi-fg-rgb", inlineStyle: "--ansi-fg: #ff0000;" },
        { text: "c", className: "ansi-fg-rgb ansi-bg-rgb", inlineStyle: "--ansi-fg: #ff0000;--ansi-bg: #080808;" },
        { text: "d", className: "ansi-fg-rgb", inlineStyle: "--ansi-fg: #ff8000;" },
        // An index past 255 changes nothing.
        { text: "e", className: "ansi-fg-rgb", inlineStyle: "--ansi-fg: #ff8000;" },
        // A short true colour changes nothing either.
        { text: "f", className: "" },
        { text: "g", className: "ansi-inverse ansi-fg-rgb", inlineStyle: "--ansi-fg: #0000ff;" },
    ]);
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

test("extended colours survive every frame split, including colon RGB", () => {
    const stream = "\x1b[38:2::1:31:4mA\x1b[48:5:208mB\x1b[0;38:2:0:8:9:10mC\x1b[38:2:11:12:13mD\x1b[0mE";
    const whole = capture([stream]);
    assert.equal(whole.runs[0].inlineStyle, "--ansi-fg: #011f04;");
    assert.equal(whole.runs[1].inlineStyle, "--ansi-fg: #011f04;--ansi-bg: #ff8700;");
    assert.equal(whole.runs[2].inlineStyle, "--ansi-fg: #08090a;");
    assert.equal(whole.runs[3].inlineStyle, "--ansi-fg: #0b0c0d;");
    for (let i = 0; i <= stream.length; i += 1) {
        assert.deepEqual(characters(capture([stream.slice(0, i), stream.slice(i)]).runs), characters(whole.runs));
    }
    assert.deepEqual(characters(capture([...stream]).runs), characters(whole.runs));
});

test("every xterm cube and grayscale entry is drawn exactly", () => {
    const levels = [0, 95, 135, 175, 215, 255];
    const rgbHex = (values) => "#" + values.map((n) => n.toString(16).padStart(2, "0")).join("");
    for (let n = 16; n < 256; n += 1) {
        const cube = n - 16;
        const rgb = n < 232
            ? [levels[Math.floor(cube / 36)], levels[Math.floor(cube / 6) % 6], levels[cube % 6]]
            : Array(3).fill(8 + (n - 232) * 10);
        const { runs } = capture([`\x1b[38;5;${n}mX`]);
        assert.equal(runs[0].inlineStyle, `--ansi-fg: ${rgbHex(rgb)};`, `index ${n}`);
    }
});

test("invalid RGB parameters never become SGR attributes or CSS", () => {
    for (const bad of ["38;2;1;31", "38;2;1;31;", "38:2::1:31", "38:2:1:0:31:4", "48;5;999", "38:5:999", "38:2::256:0:4"]) {
        const { runs } = capture([`\x1b[32mX\x1b[${bad}mY`]);
        assert.ok(runs.every((run) => run.className === "ansi-fg-green" && !run.inlineStyle), bad);
    }
});

test("control strings and character-set selectors never leak into text", () => {
    const stream = "a\x1b]8;;https://example.com\x1b\\b\x1b]8;;\x1b\\c\x1bPprivate payload\x1b\\d\x1b(Bend";
    for (let i = 0; i <= stream.length; i += 1) {
        const { runs } = capture([stream.slice(0, i), stream.slice(i)]);
        assert.equal(runs.map((run) => run.text).join(""), "abcdend");
    }
});

test("a fresh escape or cancel recovers from an unfinished control sequence", () => {
    for (const prefix of ["\x1b[31;", "\x1b]unterminated", "\x1bPunterminated"]) {
        const { runs } = capture([prefix, "\x1b[32mvisible\x1b[0mplain"]);
        assert.deepEqual(runs.map((r) => [r.text, r.className]), [["visible", "ansi-fg-green"], ["plain", ""]]);
    }
    assert.equal(capture(["\x1b[31;\x18visible"]).runs[0].text, "visible");
    const { runs } = capture(["\x1b[31mbefore\x1bcafter"]);
    assert.deepEqual(runs.map((r) => [r.text, r.className]), [["before", "ansi-fg-red"], ["after", ""]]);
});
