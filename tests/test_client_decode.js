"use strict";

// The play client's Telnet decoder gives the same text however the
// stream is cut into WebSocket frames. Audit 2026-10-22: the game ends
// its lines "\n\r", and a frame that ended between the two showed the
// line break twice -- 73 split points of one short exchange did it.
// Both consoles use the same streaming decoder, exercised at every split.

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

require("../webadmin/static/console-output.js");

function decoder() {
    const secret = [];
    let output = "";
    const stream = TocConsoleOutput.create((text) => { output += text; }, (on) => secret.push(on));
    return {
        secret,
        stream,
        decode(frame) {
            output = "";
            stream.write(frame);
            return output;
        },
    };
}

function run(frames) {
    const { decode, secret } = decoder();
    let out = "";
    for (const frame of frames) out += decode(frame);
    return JSON.stringify([out, secret]);
}

const C = String.fromCharCode;
const STREAMS = {
    "the game's line ends": "You are hungry.\n\rYou are thirsty.\n\r\n\r<20hp 100m>",
    "CR LF line ends": "one\r\ntwo\r\n\r\nthree",
    "lone breaks": "a\rb\nc\n\nd\r\re",
    "a password prompt with negotiation": "Password: " + C(255, 251, 1) + "x" + C(255, 255) +
        "y" + C(255, 250, 201) + "Core {}" + C(255, 240) + "\n\r" + C(255, 252, 1) + "ok\n\r",
};

for (const [name, stream] of Object.entries(STREAMS)) {
    test(`${name}: every split decodes as the whole`, () => {
        const whole = run([stream]);
        const bad = [];
        for (let i = 1; i < stream.length; i += 1) {
            if (run([stream.slice(0, i), stream.slice(i)]) !== whole) bad.push([i]);
            for (let j = i; j < stream.length; j += 1) {
                const parts = [stream.slice(0, i), stream.slice(i, j), stream.slice(j)];
                if (run(parts) !== whole) bad.push([i, j]);
            }
        }
        assert.deepEqual(bad.slice(0, 5), [], `${bad.length} splits differ from ${whole}`);
    });
}

test("a pair is one break and a doubled break is two", () => {
    assert.equal(JSON.parse(run(["a\n\rb"]))[0], "a\nb");
    assert.equal(JSON.parse(run(["a\n", "\rb"]))[0], "a\nb");
    assert.equal(JSON.parse(run(["a\r", "\nb"]))[0], "a\nb");
    assert.equal(JSON.parse(run(["a\n", "\nb"]))[0], "a\n\nb");
    assert.equal(JSON.parse(run(["a\n\r", "\n\rb"]))[0], "a\n\nb");
});

test("a reconnect forgets the last frame's line break", () => {
    const connect = cut("client.js", "function connectGame()");
    const { decode, stream } = decoder();
    decode("\x1b[31mold\n\x1b[");
    const state = {};
    class Socket { static CLOSING = 2; addEventListener() {} }
    const reconnect = new Function("state", "gameOutput", "window", "setSecretInput", "setConnectionState", "location", "WebSocket",
        connect + "\nreturn connectGame;")(state, stream, { clearTimeout() {} }, () => {}, () => {},
            { protocol: "http:", host: "test.invalid" }, Socket);
    reconnect();
    assert.equal(decode("\rnew session"), "\nnew session");
});

test("clearing scrollback keeps password masking and Telnet negotiation", () => {
    const { decode, stream, secret } = decoder();
    decode("\xff\xfb\x01Password: \xff\xfc");
    assert.deepEqual(secret, [false, true]);
    const clear = new Function("state", "gameOutput", "byId", cut("client.js", "function clearTerminal()") + "\nreturn clearTerminal;")(
        {}, stream, () => ({ replaceChildren() {} }));
    clear();
    assert.deepEqual(secret, [false, true]);
    decode("\x01");
    assert.deepEqual(secret, [false, true, false]);
});
