(() => {
    "use strict";

    const TOKEN_KEY = "toc_webadmin_token";
    const SETTINGS_KEY = "toc_client_settings_v1";
    const ALIASES_KEY = "toc_client_aliases_v1";
    const MAX_TERMINAL_CHARS = 350000;
    const MAX_TRANSCRIPT_CHARS = 750000;
    const MAX_LOG_CHARS = 120000;
    const DEFAULT_SETTINGS = {
        fontSize: 15,
        lineWrap: true,
        timestamps: false,
        localEcho: true,
        autoReconnect: true,
    };

    const state = {
        socket: null,
        connected: false,
        connectedAt: null,
        manualDisconnect: false,
        everConnected: false,
        failed: false,
        reconnectAttempts: 0,
        reconnectTimer: null,
        secretInput: false,
        telnetCarry: "",
        ansiCarry: "",
        ansiStyle: freshAnsiStyle(),
        terminalChars: 0,
        terminalLineStart: true,
        transcript: "",
        history: [],
        historyIndex: 0,
        draft: "",
        settings: { ...DEFAULT_SETTINGS },
        aliases: [],
        token: "",
        authenticated: false,
        players: [],
        logSocket: null,
        config: null,
    };

    const byId = (id) => document.getElementById(id);
    const all = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    function node(tag, options = {}, children = []) {
        const element = document.createElement(tag);
        if (options.className) element.className = options.className;
        if (options.text !== undefined) element.textContent = String(options.text);
        Object.entries(options.attrs || {}).forEach(([name, value]) => element.setAttribute(name, String(value)));
        children.forEach((child) => element.append(child));
        return element;
    }

    function freshAnsiStyle() {
        return { bold: false, dim: false, italic: false, underline: false, inverse: false, fg: null, bg: null };
    }

    function readJsonStorage(key, fallback) {
        try {
            const parsed = JSON.parse(localStorage.getItem(key) || "null");
            return parsed ?? fallback;
        } catch (_error) {
            return fallback;
        }
    }

    function writeJsonStorage(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Private browsing can disable persistent storage; the session still works.
        }
    }

    function readStoredToken() {
        try {
            return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) || "";
        } catch (_error) {
            return "";
        }
    }

    function storeToken(token, remember) {
        try {
            sessionStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(TOKEN_KEY);
            (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
        } catch (_error) {
            // The in-memory token remains available for this page.
        }
    }

    function clearStoredToken() {
        try {
            sessionStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(TOKEN_KEY);
        } catch (_error) {
            // Nothing else is needed when storage is unavailable.
        }
    }

    function toast(message, type = "") {
        const item = node("div", { className: `toast ${type}`.trim(), text: message });
        byId("toast-region").append(item);
        window.setTimeout(() => item.remove(), 4200);
    }

    function formatNumber(value) {
        return new Intl.NumberFormat().format(Number(value) || 0);
    }

    function formatBytes(value) {
        const bytes = Number(value) || 0;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remaining = seconds % 60;
        return [hours, minutes, remaining].map((value) => String(value).padStart(2, "0")).join(":");
    }

    function setConnectionState(kind, label) {
        const dot = byId("game-status-dot");
        dot.className = `status-dot status-${kind}`;
        byId("game-status").textContent = label;
        const connected = kind === "online";
        byId("connect-button").disabled = connected || kind === "pending";
        byId("disconnect-button").disabled = !connected && kind !== "pending";
        byId("command-input").disabled = !connected;
        byId("command-form").querySelector("button").disabled = !connected;
        const mobileConnection = byId("mobile-connection");
        mobileConnection?.setAttribute("aria-label", connected ? "Disconnect" : "Connect");
        mobileConnection?.setAttribute("title", connected ? "Disconnect" : "Connect");
        if (connected) byId("command-input").focus();
    }

    function updateSessionDuration() {
        const seconds = state.connectedAt ? Math.max(0, Math.floor((Date.now() - state.connectedAt) / 1000)) : 0;
        byId("session-duration").textContent = formatDuration(seconds);
    }

    function scrollTerminalIfNeeded(nearBottom) {
        if (nearBottom) byId("game-terminal").scrollTop = byId("game-terminal").scrollHeight;
    }

    function appendTerminalSegment(text, className = "") {
        if (!text) return;
        const terminal = byId("game-terminal");
        const nearBottom = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight < 100;
        const fragment = document.createDocumentFragment();
        let remaining = text;

        while (remaining) {
            if (state.terminalLineStart && state.settings.timestamps) {
                const timestamp = node("span", {
                    className: "terminal-time",
                    text: `[${new Date().toLocaleTimeString([], { hour12: false })}] `,
                });
                timestamp.dataset.length = String(timestamp.textContent.length);
                state.terminalChars += timestamp.textContent.length;
                fragment.append(timestamp);
            }

            const newline = remaining.indexOf("\n");
            const part = newline === -1 ? remaining : remaining.slice(0, newline + 1);
            const span = node("span", { className, text: part });
            span.dataset.length = String(part.length);
            fragment.append(span);
            state.terminalChars += part.length;
            state.terminalLineStart = part.endsWith("\n");
            remaining = newline === -1 ? "" : remaining.slice(newline + 1);
        }

        terminal.append(fragment);
        while (state.terminalChars > MAX_TERMINAL_CHARS && terminal.firstChild) {
            state.terminalChars -= Number(terminal.firstChild.dataset?.length || terminal.firstChild.textContent.length || 0);
            terminal.firstChild.remove();
        }
        scrollTerminalIfNeeded(nearBottom);
    }

    function recordTranscript(text) {
        state.transcript += text;
        if (state.transcript.length > MAX_TRANSCRIPT_CHARS) {
            state.transcript = state.transcript.slice(-MAX_TRANSCRIPT_CHARS);
        }
    }

    function appendSystem(text, className = "terminal-system") {
        appendTerminalSegment(text, className);
        recordTranscript(text);
    }

    function ansiClassName() {
        const style = state.ansiStyle;
        return [
            style.bold && "ansi-bold",
            style.dim && "ansi-dim",
            style.italic && "ansi-italic",
            style.underline && "ansi-underline",
            style.inverse && "ansi-inverse",
            style.fg && `ansi-fg-${style.fg}`,
            style.bg && `ansi-bg-${style.bg}`,
        ].filter(Boolean).join(" ");
    }

    const ANSI_COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"];

    function applyAnsiCodes(rawParameters) {
        const codes = rawParameters === "" ? [0] : rawParameters.split(";").map((part) => Number(part || 0));
        for (let index = 0; index < codes.length; index += 1) {
            const code = codes[index];
            if (code === 0) state.ansiStyle = freshAnsiStyle();
            else if (code === 1) state.ansiStyle.bold = true;
            else if (code === 2) state.ansiStyle.dim = true;
            else if (code === 3) state.ansiStyle.italic = true;
            else if (code === 4) state.ansiStyle.underline = true;
            else if (code === 7) state.ansiStyle.inverse = true;
            else if (code === 22) { state.ansiStyle.bold = false; state.ansiStyle.dim = false; }
            else if (code === 23) state.ansiStyle.italic = false;
            else if (code === 24) state.ansiStyle.underline = false;
            else if (code === 27) state.ansiStyle.inverse = false;
            else if (code >= 30 && code <= 37) state.ansiStyle.fg = ANSI_COLORS[code - 30];
            else if (code === 39) state.ansiStyle.fg = null;
            else if (code >= 40 && code <= 47) state.ansiStyle.bg = ANSI_COLORS[code - 40];
            else if (code === 49) state.ansiStyle.bg = null;
            else if (code >= 90 && code <= 97) state.ansiStyle.fg = `bright-${ANSI_COLORS[code - 90]}`;
            else if (code >= 100 && code <= 107) state.ansiStyle.bg = ANSI_COLORS[code - 100];
            else if ((code === 38 || code === 48) && codes[index + 1] === 5) index += 2;
            else if ((code === 38 || code === 48) && codes[index + 1] === 2) index += 4;
        }
    }

    function appendAnsi(text) {
        const data = state.ansiCarry + text;
        state.ansiCarry = "";
        let visible = "";
        let cursor = 0;

        while (cursor < data.length) {
            const escape = data.indexOf("\x1b", cursor);
            if (escape === -1) {
                const plain = data.slice(cursor);
                appendTerminalSegment(plain, ansiClassName());
                visible += plain;
                break;
            }
            if (escape > cursor) {
                const plain = data.slice(cursor, escape);
                appendTerminalSegment(plain, ansiClassName());
                visible += plain;
            }
            if (escape + 1 >= data.length) {
                state.ansiCarry = data.slice(escape);
                break;
            }
            if (data[escape + 1] !== "[") {
                cursor = escape + 2;
                continue;
            }
            let finalIndex = escape + 2;
            while (finalIndex < data.length) {
                const code = data.charCodeAt(finalIndex);
                if (code >= 64 && code <= 126) break;
                finalIndex += 1;
            }
            if (finalIndex >= data.length) {
                state.ansiCarry = data.slice(escape);
                break;
            }
            const finalCharacter = data[finalIndex];
            if (finalCharacter === "m") applyAnsiCodes(data.slice(escape + 2, finalIndex));
            cursor = finalIndex + 1;
        }
        recordTranscript(visible);
    }

    function setSecretInput(secret) {
        state.secretInput = secret;
        const input = byId("command-input");
        input.type = secret ? "password" : "text";
        input.placeholder = secret ? "Password" : "Command";
    }

    function decodeTelnet(value) {
        const data = state.telnetCarry + value;
        state.telnetCarry = "";
        let output = "";
        let index = 0;

        while (index < data.length) {
            if (data.charCodeAt(index) !== 255) {
                output += data[index];
                index += 1;
                continue;
            }
            if (index + 1 >= data.length) {
                state.telnetCarry = data.slice(index);
                break;
            }
            const command = data.charCodeAt(index + 1);
            if (command === 255) {
                output += String.fromCharCode(255);
                index += 2;
                continue;
            }
            if ([251, 252, 253, 254].includes(command)) {
                if (index + 2 >= data.length) {
                    state.telnetCarry = data.slice(index);
                    break;
                }
                const option = data.charCodeAt(index + 2);
                if (option === 1 && command === 251) setSecretInput(true);
                if (option === 1 && command === 252) setSecretInput(false);
                index += 3;
                continue;
            }
            if (command === 250) {
                const end = data.indexOf(String.fromCharCode(255, 240), index + 2);
                if (end === -1) {
                    state.telnetCarry = data.slice(index);
                    break;
                }
                index = end + 2;
                continue;
            }
            index += 2;
        }
        return output.replace(/\r\n|\n\r/g, "\n").replace(/\r/g, "\n");
    }

    function scheduleReconnect() {
        if (!state.settings.autoReconnect || state.manualDisconnect || !state.everConnected) return;
        window.clearTimeout(state.reconnectTimer);
        const delay = Math.min(15000, 2000 * (2 ** Math.min(state.reconnectAttempts, 3)));
        state.reconnectAttempts += 1;
        setConnectionState("pending", `Reconnecting in ${Math.ceil(delay / 1000)}s`);
        state.reconnectTimer = window.setTimeout(connectGame, delay);
    }

    function connectGame() {
        if (state.socket && state.socket.readyState < WebSocket.CLOSING) return;
        window.clearTimeout(state.reconnectTimer);
        state.manualDisconnect = false;
        state.failed = false;
        state.telnetCarry = "";
        setSecretInput(false);
        setConnectionState("pending", "Connecting");

        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const socket = new WebSocket(`${protocol}//${location.host}/ws`);
        state.socket = socket;

        socket.addEventListener("message", (event) => {
            const message = String(event.data);
            if (message === "\0TOC_CONNECTED") {
                state.connected = true;
                state.everConnected = true;
                state.connectedAt = Date.now();
                state.reconnectAttempts = 0;
                setConnectionState("online", "Connected");
                byId("terminal-banner").firstElementChild.textContent = "Game online";
                appendSystem("[Connected to Times of Chaos]\n");
                return;
            }
            if (message.startsWith("\0TOC_ERROR:")) {
                state.failed = true;
                setConnectionState("offline", "Game unavailable");
                byId("terminal-banner").firstElementChild.textContent = "Game offline";
                appendSystem(`[${message.slice(11)}]\n`, "terminal-error");
                return;
            }
            appendAnsi(decodeTelnet(message));
        });

        socket.addEventListener("close", () => {
            const wasConnected = state.connected;
            if (state.socket === socket) state.socket = null;
            state.connected = false;
            state.connectedAt = null;
            setSecretInput(false);
            setConnectionState("offline", state.failed ? "Game unavailable" : "Disconnected");
            if (wasConnected) appendSystem("\n[Disconnected]\n");
            scheduleReconnect();
        });

        socket.addEventListener("error", () => {
            if (!state.connected) setConnectionState("offline", "Connection error");
        });
    }

    function disconnectGame() {
        state.manualDisconnect = true;
        window.clearTimeout(state.reconnectTimer);
        state.socket?.close();
    }

    function resolveAlias(command) {
        const trimmed = command.trim();
        if (!trimmed || state.secretInput) return command;
        const separator = trimmed.search(/\s/);
        const key = (separator === -1 ? trimmed : trimmed.slice(0, separator)).toLowerCase();
        const args = separator === -1 ? "" : trimmed.slice(separator).trim();
        const alias = state.aliases.find((item) => item.key.toLowerCase() === key);
        if (!alias) return command;
        if (alias.command.includes("{args}")) return alias.command.replaceAll("{args}", args);
        return args ? `${alias.command} ${args}` : alias.command;
    }

    function sendCommand(command) {
        if (!state.socket || state.socket.readyState !== WebSocket.OPEN || !state.connected) {
            toast("The game is not connected.", "error");
            return false;
        }
        if (!command) return false;
        const resolved = resolveAlias(command);
        state.socket.send(`${resolved}\n`);
        if (!state.secretInput) {
            if (state.settings.localEcho) {
                appendTerminalSegment(`> ${resolved}\n`, "terminal-local");
                recordTranscript(`> ${resolved}\n`);
            }
            if (state.history[state.history.length - 1] !== command) state.history.push(command);
            state.history = state.history.slice(-200);
            state.historyIndex = state.history.length;
            state.draft = "";
        }
        return true;
    }

    function submitCommand(event) {
        event.preventDefault();
        const input = byId("command-input");
        if (sendCommand(input.value)) input.value = "";
    }

    function handleCommandHistory(event) {
        if (state.secretInput) return;
        const input = event.currentTarget;
        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (state.historyIndex === state.history.length) state.draft = input.value;
            state.historyIndex = Math.max(0, state.historyIndex - 1);
            input.value = state.history[state.historyIndex] || "";
            input.setSelectionRange(input.value.length, input.value.length);
        } else if (event.key === "ArrowDown") {
            event.preventDefault();
            state.historyIndex = Math.min(state.history.length, state.historyIndex + 1);
            input.value = state.historyIndex === state.history.length ? state.draft : state.history[state.historyIndex];
            input.setSelectionRange(input.value.length, input.value.length);
        }
    }

    function clearTerminal() {
        byId("game-terminal").replaceChildren();
        state.terminalChars = 0;
        state.terminalLineStart = true;
        state.transcript = "";
        state.ansiCarry = "";
        state.ansiStyle = freshAnsiStyle();
    }

    function downloadTranscript() {
        if (!state.transcript) {
            toast("The transcript is empty.");
            return;
        }
        const stamp = new Date().toISOString().replaceAll(":", "-").replace(/\.\d{3}Z$/, "Z");
        const url = URL.createObjectURL(new Blob([state.transcript], { type: "text/plain;charset=utf-8" }));
        const anchor = node("a", { attrs: { href: url, download: `toc-session-${stamp}.txt` } });
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
    }

    function applySettings() {
        const size = Math.max(12, Math.min(22, Number(state.settings.fontSize) || 15));
        state.settings.fontSize = size;
        document.documentElement.style.setProperty("--terminal-font-size", `${size}px`);
        byId("font-size").value = String(size);
        byId("font-size-value").textContent = `${size}px`;
        byId("line-wrap").checked = Boolean(state.settings.lineWrap);
        byId("timestamps").checked = Boolean(state.settings.timestamps);
        byId("local-echo").checked = Boolean(state.settings.localEcho);
        byId("auto-reconnect").checked = Boolean(state.settings.autoReconnect);
        byId("game-terminal").classList.toggle("no-wrap", !state.settings.lineWrap);
    }

    function saveSettings() {
        writeJsonStorage(SETTINGS_KEY, state.settings);
        applySettings();
    }

    function openPanel() {
        document.body.classList.add("panel-open");
    }

    function closePanel() {
        document.body.classList.remove("panel-open");
    }

    function showUtilityPanel(name) {
        all("[data-panel]").forEach((tab) => {
            const active = tab.dataset.panel === name;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
        });
        byId("session-panel").classList.toggle("is-active", name === "session");
        byId("admin-panel").classList.toggle("is-active", name === "admin");
        if (name === "admin" && state.authenticated) void loadAdmin();
    }

    function renderAliases() {
        const list = byId("alias-list");
        const fragment = document.createDocumentFragment();
        if (!state.aliases.length) {
            fragment.append(node("span", { className: "muted", text: "No aliases saved." }));
        }
        state.aliases
            .slice()
            .sort((a, b) => a.key.localeCompare(b.key))
            .forEach((alias) => {
                const edit = node("button", { text: "Edit", attrs: { type: "button" } });
                const remove = node("button", { text: "Delete", attrs: { type: "button" } });
                edit.addEventListener("click", () => openAliasDialog(alias));
                remove.addEventListener("click", () => {
                    state.aliases = state.aliases.filter((item) => item.key !== alias.key);
                    writeJsonStorage(ALIASES_KEY, state.aliases);
                    renderAliases();
                });
                fragment.append(node("div", { className: "alias-row" }, [
                    node("div", {}, [node("strong", { text: alias.key }), node("small", { text: alias.command })]),
                    node("div", { className: "alias-buttons" }, [edit, remove]),
                ]));
            });
        list.replaceChildren(fragment);

        const strip = byId("macro-strip");
        const pinned = state.aliases.filter((alias) => alias.pinned);
        strip.replaceChildren(...pinned.map((alias) => {
            const button = node("button", { text: alias.key, attrs: { type: "button", title: alias.command } });
            button.addEventListener("click", () => sendCommand(alias.key));
            return button;
        }));
        strip.classList.toggle("has-items", pinned.length > 0);
    }

    function openAliasDialog(alias = null) {
        byId("alias-dialog-title").textContent = alias ? "Edit alias" : "New alias";
        byId("alias-original").value = alias?.key || "";
        byId("alias-key").value = alias?.key || "";
        byId("alias-command").value = alias?.command || "";
        byId("alias-pinned").checked = Boolean(alias?.pinned);
        byId("alias-error").textContent = "";
        byId("alias-dialog").showModal();
        byId("alias-key").focus();
    }

    function saveAlias(event) {
        event.preventDefault();
        const original = byId("alias-original").value;
        const key = byId("alias-key").value.trim();
        const command = byId("alias-command").value.trim();
        if (!/^[A-Za-z0-9_-]+$/.test(key)) {
            byId("alias-error").textContent = "Use letters, numbers, hyphens, or underscores.";
            return;
        }
        if (!command || /[\r\n]/.test(command)) {
            byId("alias-error").textContent = "Enter one game command.";
            return;
        }
        const duplicate = state.aliases.some((item) => item.key.toLowerCase() === key.toLowerCase() && item.key !== original);
        if (duplicate) {
            byId("alias-error").textContent = "That alias already exists.";
            return;
        }
        state.aliases = state.aliases.filter((item) => item.key !== original);
        state.aliases.push({ key, command, pinned: byId("alias-pinned").checked });
        writeJsonStorage(ALIASES_KEY, state.aliases);
        renderAliases();
        byId("alias-dialog").close();
    }

    async function api(path, options = {}) {
        const headers = new Headers(options.headers || {});
        if (options.auth) headers.set("X-Admin-Token", state.token);
        if (options.body !== undefined) headers.set("Content-Type", "application/json");
        const response = await fetch(path, {
            method: options.method || "GET",
            headers,
            body: options.body === undefined ? undefined : JSON.stringify(options.body),
        });
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json") ? await response.json() : await response.text();
        if (!response.ok) {
            if (response.status === 403 && options.auth) setAdminAuthenticated(false, false);
            const detail = payload && typeof payload === "object" ? payload.detail : payload;
            const error = new Error(detail || `Request failed (${response.status})`);
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    async function refreshPublicStatus() {
        try {
            const config = await api("/api/config");
            state.config = config;
            byId("terminal-banner").replaceChildren(
                node("strong", { text: "Game endpoint" }),
                node("span", { text: config.mud_endpoint }),
            );
        } catch (_error) {
            byId("terminal-banner").replaceChildren(
                node("strong", { text: "Dashboard unavailable" }),
                node("span", { text: location.host }),
            );
        }
    }

    function setAdminAuthenticated(authenticated, clearToken = false) {
        state.authenticated = authenticated;
        byId("admin-locked").hidden = authenticated;
        byId("admin-workspace").hidden = !authenticated;
        if (!authenticated) stopLogs();
        if (clearToken) {
            state.token = "";
            clearStoredToken();
        }
    }

    async function validateStoredToken() {
        state.token = readStoredToken();
        if (!state.token) return;
        try {
            await api("/api/auth/check", { auth: true });
            setAdminAuthenticated(true);
        } catch (_error) {
            setAdminAuthenticated(false, true);
        }
    }

    function openAuthDialog() {
        byId("auth-error").textContent = "";
        byId("auth-token").value = "";
        byId("auth-dialog").showModal();
        byId("auth-token").focus();
    }

    async function unlockAdmin(event) {
        event.preventDefault();
        const token = byId("auth-token").value;
        if (!token) return;
        state.token = token;
        byId("auth-submit").disabled = true;
        try {
            await api("/api/auth/check", { auth: true });
            storeToken(token, byId("auth-remember").checked);
            setAdminAuthenticated(true);
            byId("auth-dialog").close();
            toast("Admin unlocked.", "success");
            await loadAdmin();
        } catch (error) {
            state.token = "";
            byId("auth-error").textContent = error.status === 503 ? "Admin access is not configured." : "Token rejected.";
        } finally {
            byId("auth-submit").disabled = false;
        }
    }

    function renderBackups(backups) {
        const list = byId("backup-list");
        if (!backups.length) {
            list.replaceChildren(node("span", { className: "muted", text: "No backup archives." }));
            return;
        }
        list.replaceChildren(...backups.slice(0, 5).map((backup) => node("div", {}, [
            node("span", { text: backup.name }),
            node("span", { text: formatBytes(backup.size_bytes) }),
        ])));
    }

    function renderPlayer(data) {
        const summary = byId("player-summary");
        const fields = [
            ["Race", data.race], ["Class", data.class_name],
            ["Guild", data.guild_name], ["Remorts", data.num_remorts],
            ["HP", `${data.hp_cur} / ${data.hp_max}`], ["Mana", `${data.mana_cur} / ${data.mana_max}`],
            ["Move", `${data.mv_cur} / ${data.mv_max}`], ["Hit / Dam", `${data.hitroll} / ${data.damroll}`],
        ];
        const grid = node("div", { className: "player-grid" });
        fields.forEach(([label, value]) => grid.append(node("div", {}, [
            node("span", { text: label }), node("strong", { text: value ?? "-" }),
        ])));
        const equipment = (data.equipment || []).slice(0, 12);
        const children = [
            node("div", { className: "player-heading" }, [
                node("strong", { text: `${data.name}${data.title ? ` ${data.title}` : ""}` }),
                node("span", { text: `Level ${data.level}` }),
            ]),
            grid,
        ];
        if (equipment.length) {
            children.push(node("div", { className: "equipment-list" }, equipment.map((item) =>
                node("div", {}, [node("span", { text: item.wear_slot }), node("strong", { text: item.name })])
            )));
        }
        summary.replaceChildren(...children);
    }

    async function loadAdmin() {
        if (!state.authenticated) return;
        try {
            const [health, stats, areaHealth, players, backups] = await Promise.all([
                api("/api/health"),
                api("/api/stats"),
                api("/api/area_health?include_issues=false"),
                api("/api/players", { auth: true }),
                api("/api/backups", { auth: true }),
            ]);
            state.players = players;
            byId("admin-game-state").textContent = health.merc ? "Online" : "Offline";
            byId("admin-player-count").textContent = formatNumber(players.length);
            byId("admin-warning-count").textContent = formatNumber(areaHealth.summary.by_severity.warning);
            byId("admin-room-count").textContent = formatNumber(stats.rooms);
            byId("player-names").replaceChildren(...players.map((name) => node("option", { attrs: { value: name } })));
            renderBackups(backups);
        } catch (error) {
            toast(error.message, "error");
        }
    }

    async function findPlayer(event) {
        event.preventDefault();
        const name = byId("player-name").value.trim();
        if (!name) return;
        try {
            renderPlayer(await api(`/api/player/${encodeURIComponent(name)}`, { auth: true }));
        } catch (error) {
            byId("player-summary").replaceChildren(node("span", { className: "terminal-error", text: error.message }));
        }
    }

    async function sendAnnouncement(event) {
        event.preventDefault();
        const message = byId("wizinfo-message").value.trim();
        const level = Number(byId("wizinfo-level").value);
        if (!message) return;
        try {
            await api("/api/wizinfo", { method: "POST", auth: true, body: { message, level } });
            byId("wizinfo-message").value = "";
            toast("Announcement queued.", "success");
        } catch (error) {
            toast(error.message, "error");
        }
    }

    async function queueAdminCommand(event) {
        event.preventDefault();
        const input = byId("admin-command");
        const command = input.value.trim();
        if (!command) return;
        try {
            await api("/api/command", { method: "POST", auth: true, body: { command } });
            input.value = "";
            toast("Server command queued.", "success");
        } catch (error) {
            toast(error.message, "error");
        }
    }

    function appendLog(text) {
        const terminal = byId("admin-log");
        const nearBottom = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight < 80;
        terminal.textContent += text;
        if (terminal.textContent.length > MAX_LOG_CHARS) terminal.textContent = terminal.textContent.slice(-MAX_LOG_CHARS);
        if (nearBottom) terminal.scrollTop = terminal.scrollHeight;
    }

    function stopLogs() {
        if (state.logSocket) {
            state.logSocket.onclose = null;
            if (state.logSocket.readyState === WebSocket.OPEN) {
                state.logSocket.send(JSON.stringify({ type: "close" }));
            }
            state.logSocket.close();
            state.logSocket = null;
        }
        byId("log-status").textContent = "Disconnected";
        byId("log-connect").textContent = "Connect";
    }

    function connectLogs() {
        if (!state.authenticated) return openAuthDialog();
        if (state.logSocket) {
            stopLogs();
            return;
        }
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const socket = new WebSocket(`${protocol}//${location.host}/ws/logs`);
        state.logSocket = socket;
        byId("log-status").textContent = "Connecting";
        byId("log-connect").textContent = "Disconnect";
        socket.addEventListener("open", () => socket.send(JSON.stringify({ type: "auth", token: state.token })));
        socket.addEventListener("message", (event) => {
            byId("log-status").textContent = "Live";
            appendLog(String(event.data));
        });
        socket.addEventListener("close", (event) => {
            if (state.logSocket === socket) state.logSocket = null;
            byId("log-connect").textContent = "Connect";
            byId("log-status").textContent = event.code === 4003 ? "Forbidden" : "Disconnected";
            if (event.code === 4003) setAdminAuthenticated(false, true);
        });
        socket.addEventListener("error", () => { byId("log-status").textContent = "Error"; });
    }

    async function snapshotLogs() {
        try {
            byId("admin-log").textContent = await api("/api/logs?lines=300", { auth: true });
            byId("log-status").textContent = "Snapshot";
        } catch (error) {
            if (error.status === 404) {
                byId("admin-log").textContent = "Log file not found.\n";
                byId("log-status").textContent = "No log";
            } else {
                toast(error.message, "error");
            }
        }
    }

    function confirmAction({ title, message, phrase = "", danger = true }) {
        const dialog = byId("confirm-dialog");
        byId("confirm-title").textContent = title;
        byId("confirm-message").textContent = message;
        byId("confirm-phrase-row").hidden = !phrase;
        byId("confirm-phrase-label").textContent = phrase;
        byId("confirm-phrase").value = "";
        byId("confirm-submit").className = `button ${danger ? "button-danger" : "button-primary"}`;
        dialog.showModal();
        return new Promise((resolve) => {
            dialog.addEventListener("close", () => {
                const phraseMatches = !phrase || byId("confirm-phrase").value === phrase;
                resolve(dialog.returnValue === "confirm" && phraseMatches);
            }, { once: true });
        });
    }

    async function runOperation(operation) {
        const descriptions = {
            backup: { title: "Create backup", message: "Queue a server backup?", danger: false },
            reload: { title: "Refresh dashboard data", message: "Reparse area files for the dashboard? The running game is unchanged.", danger: false },
            shutdown: { title: "Shut down game", message: "Queue an immediate game-server shutdown?", phrase: "SHUTDOWN", danger: true },
        };
        if (!await confirmAction(descriptions[operation])) return;
        try {
            await api(`/api/${operation}`, { method: "POST", auth: true });
            toast(operation === "reload" ? "Dashboard data refreshed." : `${operation[0].toUpperCase()}${operation.slice(1)} queued.`, "success");
            await loadAdmin();
        } catch (error) {
            toast(error.message, "error");
        }
    }

    async function resetClient() {
        if (!await confirmAction({ title: "Reset client", message: "Remove saved aliases and restore display settings?", danger: true })) return;
        state.settings = { ...DEFAULT_SETTINGS };
        state.aliases = [];
        try {
            localStorage.removeItem(SETTINGS_KEY);
            localStorage.removeItem(ALIASES_KEY);
        } catch (_error) {
            // In-memory state has still been reset.
        }
        applySettings();
        renderAliases();
        toast("Client settings reset.", "success");
    }

    function bindEvents() {
        byId("connect-button").addEventListener("click", connectGame);
        byId("disconnect-button").addEventListener("click", disconnectGame);
        byId("mobile-connection")?.addEventListener("click", () => state.connected ? disconnectGame() : connectGame());
        byId("download-button").addEventListener("click", downloadTranscript);
        byId("command-form").addEventListener("submit", submitCommand);
        byId("command-input").addEventListener("keydown", handleCommandHistory);
        byId("clear-terminal").addEventListener("click", clearTerminal);
        byId("reset-settings").addEventListener("click", () => void resetClient());

        all("[data-command]").forEach((button) => button.addEventListener("click", () => sendCommand(button.dataset.command)));
        byId("panel-toggle").addEventListener("click", openPanel);
        byId("panel-close").addEventListener("click", closePanel);
        byId("panel-scrim").addEventListener("click", closePanel);
        all("[data-panel]").forEach((tab) => tab.addEventListener("click", () => showUtilityPanel(tab.dataset.panel)));

        byId("font-size").addEventListener("input", (event) => {
            state.settings.fontSize = Number(event.target.value);
            saveSettings();
        });
        byId("line-wrap").addEventListener("change", (event) => { state.settings.lineWrap = event.target.checked; saveSettings(); });
        byId("timestamps").addEventListener("change", (event) => { state.settings.timestamps = event.target.checked; saveSettings(); });
        byId("local-echo").addEventListener("change", (event) => { state.settings.localEcho = event.target.checked; saveSettings(); });
        byId("auto-reconnect").addEventListener("change", (event) => { state.settings.autoReconnect = event.target.checked; saveSettings(); });

        byId("add-alias").addEventListener("click", () => openAliasDialog());
        byId("alias-form").addEventListener("submit", saveAlias);
        byId("admin-unlock").addEventListener("click", openAuthDialog);
        byId("auth-form").addEventListener("submit", (event) => void unlockAdmin(event));
        byId("admin-lock").addEventListener("click", () => { setAdminAuthenticated(false, true); toast("Admin locked."); });
        byId("admin-refresh").addEventListener("click", () => void loadAdmin());
        byId("player-form").addEventListener("submit", (event) => void findPlayer(event));
        byId("wizinfo-form").addEventListener("submit", (event) => void sendAnnouncement(event));
        byId("admin-command-form").addEventListener("submit", (event) => void queueAdminCommand(event));
        byId("log-connect").addEventListener("click", connectLogs);
        byId("log-snapshot").addEventListener("click", () => void snapshotLogs());
        byId("log-clear").addEventListener("click", () => { byId("admin-log").textContent = ""; });
        all("[data-operation]").forEach((button) => button.addEventListener("click", () => void runOperation(button.dataset.operation)));

        window.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                if (!byId("command-input").disabled) byId("command-input").focus();
            } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "l") {
                event.preventDefault();
                clearTerminal();
            } else if (event.key === "Escape") {
                closePanel();
            }
        });

        window.addEventListener("beforeunload", () => {
            state.manualDisconnect = true;
            state.socket?.close();
            state.logSocket?.close();
        });
    }

    async function init() {
        const storedSettings = readJsonStorage(SETTINGS_KEY, {});
        state.settings = { ...DEFAULT_SETTINGS, ...(storedSettings && typeof storedSettings === "object" ? storedSettings : {}) };
        const storedAliases = readJsonStorage(ALIASES_KEY, []);
        state.aliases = Array.isArray(storedAliases)
            ? storedAliases.filter((item) => item && typeof item.key === "string" && typeof item.command === "string").slice(0, 100)
            : [];
        applySettings();
        renderAliases();
        bindEvents();
        await Promise.all([refreshPublicStatus(), validateStoredToken()]);
        connectGame();
        window.setInterval(updateSessionDuration, 1000);
    }

    void init();
})();
