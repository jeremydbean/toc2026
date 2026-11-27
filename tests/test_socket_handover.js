"use strict";

// Review, 2026-11-27: a socket still closing can be replaced by a new one,
// and the old one's late close cleared the shared connection state --
// "Disconnected" while the replacement was connected -- unmasked the
// password field and scheduled a reconnect. Only the current socket may
// speak for the connection now. The functions are cut from the consoles'
// scripts and run against a fake WebSocket.

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

class FakeSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    static made = [];
    constructor(url) {
        this.url = url;
        this.readyState = FakeSocket.CONNECTING;
        this.listeners = {};
        FakeSocket.made.push(this);
    }
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
    emit(type, event = {}) { for (const fn of this.listeners[type] || []) fn(event); }
    send() {}
    close() { this.readyState = FakeSocket.CLOSING; }
}

function element() { return { textContent: "", disabled: false, firstElementChild: { textContent: "" } }; }

test("client.js: a replaced socket's late close leaves its replacement connected", () => {
    FakeSocket.made = [];
    const calls = { connection: [], secret: [], reconnect: 0, written: [] };
    const state = { socket: null, connected: false, settings: { autoReconnect: true } };
    const els = {};
    const connectGame = new Function(
        "state", "WebSocket", "location", "window", "gameOutput", "setSecretInput",
        "setConnectionState", "appendSystem", "byId", "scheduleReconnect",
        cut("client.js", "function connectGame()") + "\nreturn connectGame;")(
        state, FakeSocket, { protocol: "http:", host: "x" },
        { clearTimeout() {}, setTimeout() {} },
        { reset() {}, write(text) { calls.written.push(text); } },
        (secret) => calls.secret.push(secret),
        (kind, label) => calls.connection.push(label),
        () => {}, (id) => (els[id] ||= element()), () => { calls.reconnect += 1; });

    connectGame();
    const first = FakeSocket.made[0];
    first.emit("message", { data: "\0TOC_CONNECTED" });
    first.readyState = FakeSocket.CLOSING;        // closing, not yet closed
    connectGame();
    const second = FakeSocket.made[1];
    assert.notEqual(second, undefined, "the closing socket is replaced");
    second.emit("message", { data: "\0TOC_CONNECTED" });
    calls.secret.length = 0;
    calls.connection.length = 0;

    first.emit("message", { data: "a late line from the old connection" });
    first.emit("error");
    first.emit("close");

    assert.equal(state.socket, second);
    assert.equal(state.connected, true, "still connected");
    assert.deepEqual(calls.connection, [], "no Disconnected or Connection error");
    assert.deepEqual(calls.secret, [], "the password prompt is left alone");
    assert.equal(calls.reconnect, 0, "no reconnect scheduled");
    assert.ok(!calls.written.includes("a late line from the old connection"));

    // The current socket's own close still does all of it.
    second.emit("close");
    assert.equal(state.connected, false);
    assert.deepEqual(calls.connection, ["Disconnected"]);
    assert.deepEqual(calls.secret, [false]);
    assert.equal(calls.reconnect, 1);
});

test("app.js: the console's replaced socket cannot reset its replacement", () => {
    FakeSocket.made = [];
    const calls = { connected: [], secret: [] };
    const state = { terminal: { socket: null, failed: false } };
    const els = {};
    const connectConsole = new Function(
        "state", "WebSocket", "location", "consoleOutput", "setConsoleConnected",
        "appendTerminal", "setConsoleSecret", "byId",
        cut("app.js", "function connectConsole()") + "\nreturn connectConsole;")(
        state, FakeSocket, { protocol: "http:", host: "x" },
        { reset() {}, write() {} },
        (on, label) => calls.connected.push([on, label]),
        () => {}, (secret) => calls.secret.push(secret), (id) => (els[id] ||= element()));

    connectConsole();
    const first = FakeSocket.made[0];
    first.emit("message", { data: "\0TOC_CONNECTED" });
    first.readyState = FakeSocket.CLOSING;
    connectConsole();
    const second = FakeSocket.made[1];
    second.emit("message", { data: "\0TOC_CONNECTED" });
    calls.connected.length = 0;
    calls.secret.length = 0;
    first.emit("close");
    first.emit("error");
    assert.equal(state.terminal.socket, second);
    assert.deepEqual(calls.connected, []);
    assert.deepEqual(calls.secret, []);
});
