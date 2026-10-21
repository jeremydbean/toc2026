"use strict";

// An unsent password is discarded before its field is unmasked.
// Audit 2026-10-21: a disconnect turned the password field back into a
// text field with the typed password still in it, and submitting it after
// a reconnect sent it as a command into history and the transcript.
// The function bodies are cut from the two consoles' scripts.

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

function cut(file, signature) {
    const text = fs.readFileSync(path.join(__dirname, "..", "webadmin", "static", file), "utf8");
    const start = text.indexOf(signature);
    assert.notEqual(start, -1, signature);
    let depth = 0;
    for (let i = text.indexOf("{", start); i < text.length; i += 1) {
        if (text[i] === "{") depth += 1;
        if (text[i] === "}" && --depth === 0) return text.slice(start, i + 1);
    }
    throw new Error("unbalanced " + signature);
}

function harness(file, signature, name, stateShape) {
    const input = { value: "", type: "text", placeholder: "" };
    const state = stateShape();
    const fn = new Function("state", "byId", cut(file, signature) + "\nreturn " + name + ";")(
        state, () => input);
    return { input, state, fn };
}

for (const [file, signature, name, secretOf] of [
    ["client.js", "function setSecretInput(secret)", "setSecretInput", (s) => s.secretInput],
    ["app.js", "function setConsoleSecret(secret)", "setConsoleSecret", (s) => s.terminal.secretInput],
]) {
    test(`${file}: leaving password mode clears what was typed`, () => {
        const { input, state, fn } = harness(file, signature, name,
            () => ({ secretInput: false, terminal: { secretInput: false } }));
        fn(true);
        assert.equal(input.type, "password");
        input.value = "hunter2";
        fn(false);                       // the connection closed
        assert.equal(input.type, "text");
        assert.equal(input.value, "", "never shown unmasked");
        assert.equal(secretOf(state), false);
    });

    test(`${file}: an ordinary draft survives a reconnect`, () => {
        const { input, fn } = harness(file, signature, name,
            () => ({ secretInput: false, terminal: { secretInput: false } }));
        input.value = "look at the fountain";
        fn(false);
        assert.equal(input.value, "look at the fountain");
    });
}
