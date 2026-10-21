(() => {
    "use strict";

    const MAX_COMMANDS = 50;

    // The game sends these lines whole, semicolons and all: an alias body,
    // a password. Mirrors typed_line_whole() in src/comm.c.
    const WHOLE_LINE = ["alias", "unalias", "password", "resetpwd", "delete", "remort"];

    function quoteCanOpen(current) {
        if (!current) return true;
        return /[\s([{=:,]/.test(current[current.length - 1]);
    }

    function isEscaped(input, index) {
        let slashes = 0;
        for (let cursor = index - 1; cursor >= 0 && input[cursor] === "\\"; cursor -= 1) {
            slashes += 1;
        }
        return slashes % 2 === 1;
    }

    // The commands a typed line holds, on the game's rules
    // (split_typed_commands in src/comm.c): quotes and \; keep a semicolon.
    function parse(value) {
        const input = String(value ?? "");
        const commands = [];
        let current = "";
        let quote = "";
        let overflow = false;

        function appendCurrent() {
            const command = current.trim();
            current = "";
            if (!command) return;
            if (commands.length >= MAX_COMMANDS) {
                overflow = true;
                return;
            }
            commands.push(command);
        }

        for (let index = 0; index < input.length; index += 1) {
            const character = input[index];
            const next = input[index + 1];

            if (character === "\\" && next === ";") {
                current += ";";
                index += 1;
                continue;
            }
            if (quote) {
                current += character;
                if (character === quote && !isEscaped(input, index)) quote = "";
                continue;
            }
            if ((character === "'" || character === '"') && quoteCanOpen(current)) {
                quote = character;
                current += character;
                continue;
            }
            if (character === ";") {
                appendCurrent();
                continue;
            }
            current += character;
        }

        appendCurrent();
        return { commands, overflow };
    }

    function wholeLine(value) {
        const word = String(value ?? "").trim().split(/\s+/)[0].toLowerCase();
        return word.length >= 2 && WHOLE_LINE.some((name) => name.startsWith(word));
    }

    // A semicolon the game must read as text, not as a separator.
    function escapeSemicolons(text) {
        return String(text).replace(/;/g, "\\;");
    }

    // The one line to send for what was typed. The game splits a typed
    // line itself, and splitting it here first was a second parse that
    // disagreed with the first: \; became a bare ; the game split again
    // ("say left\;quit" quit), an ALIAS body was cut at its first
    // semicolon, and a BUILD answer or a password became two commands
    // (audit, 2026-10-21). So the line goes as typed. `resolve` is the play
    // client's own aliases: given one command and escapeSemicolons, it
    // returns the expansion, or null. Only when one applies is the line
    // rebuilt, with every literal semicolon escaped so the game reads it
    // as the user meant.
    function encode(value, resolve) {
        const input = String(value ?? "");
        if (wholeLine(input)) return { line: input, overflow: false };
        const { commands, overflow } = parse(input);
        if (overflow) return { line: input, overflow: true };
        if (typeof resolve !== "function") return { line: input, overflow: false };

        let changed = false;
        const parts = commands.map((command) => {
            const expanded = resolve(command, escapeSemicolons);
            if (expanded === null || expanded === undefined) return escapeSemicolons(command);
            changed = true;
            return expanded;
        });
        return { line: changed ? parts.join(";") : input, overflow: false };
    }

    const api = Object.freeze({ MAX_COMMANDS, parse, encode, wholeLine, escapeSemicolons });
    if (typeof window !== "undefined") window.TocCommandSequence = api;
    if (typeof module !== "undefined") module.exports = api;
})();
