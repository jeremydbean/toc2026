"use strict";

// webadmin/static/command-sequence.js: what the browser consoles send.
// Audit 2026-10-21: both consoles split a typed line and sent each piece,
// and the game split each piece again -- "say left\;quit" said "left" and
// quit, an ALIAS body lost everything after its first semicolon, and a
// BUILD answer or a password became two commands. A typed line now goes
// as one line, and the game splits it once.

const assert = require("node:assert/strict");
const test = require("node:test");
const seq = require("../webadmin/static/command-sequence.js");

const aliases = { k: "kill {args}", gg: "get all corpse;sacrifice corpse" };

function resolve(command, escape) {
    const [key, ...rest] = command.trim().split(/\s+/);
    const template = aliases[key.toLowerCase()];
    if (!template) return null;
    const args = escape(rest.join(" "));
    return template.includes("{args}") ? template.replaceAll("{args}", args)
        : (args ? `${template} ${args}` : template);
}

test("a typed line goes as typed when no client alias applies", () => {
    for (const line of ["say left\\;quit", "n;kill orc", "say 'inside;quotes'", "look"]) {
        assert.equal(seq.encode(line, resolve).line, line);
        assert.equal(seq.encode(line).line, line);
    }
});

test("whole-line commands are never touched, aliases or not", () => {
    for (const line of ["alias zpair say alpha;say omega", "alias k say x;y",
                        "password old;one new;two", "unal k;j", "remort pw;x mage"]) {
        assert.equal(seq.encode(line, resolve).line, line);
    }
});

test("a client alias expands in place, and what was typed stays text", () => {
    assert.equal(seq.encode("k orc;say a\\;b", resolve).line, "kill orc;say a\\;b");
    assert.equal(seq.encode("k orc\\;quit", resolve).line, "kill orc\\;quit");
    assert.equal(seq.encode("gg;n", resolve).line, "get all corpse;sacrifice corpse;n");
});

test("the commands of a line are counted on the game's rules", () => {
    assert.deepEqual(seq.parse("say a;say 'b;c';say d\\;e").commands,
                     ["say a", "say 'b;c'", "say d;e"]);
    const flood = Array(seq.MAX_COMMANDS + 1).fill("say x").join(";");
    assert.equal(seq.encode(flood).overflow, true);
});
