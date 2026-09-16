(() => {
    "use strict";

    const COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"];

    // Network frames may end inside either a Telnet command or an ANSI sequence.
    function create(writeText, setSecretInput) {
        let style, telnet, negotiation, ansi, parameters, newline, pending;

        function reset() {
            style = {};
            telnet = "data";
            negotiation = 0;
            ansi = "text";
            parameters = "";
            newline = "";
            pending = "";
            setSecretInput(false);
        }

        function flush() {
            if (!pending) return;
            const classes = ["bold", "dim", "italic", "underline", "inverse"]
                .filter((name) => style[name]).map((name) => `ansi-${name}`);
            if (style.fg) classes.push(`ansi-fg-${style.fg}`);
            if (style.bg) classes.push(`ansi-bg-${style.bg}`);
            writeText(pending, classes.join(" "));
            pending = "";
        }

        function applyCodes(raw) {
            if (!/^[\d;]*$/.test(raw)) return;
            const codes = raw.split(";").map((part) => Number(part || 0));
            for (let i = 0; i < codes.length; i += 1) {
                const code = codes[i];
                if (code === 0) style = {};
                else if (code === 1) style.bold = true;
                else if (code === 2) style.dim = true;
                else if (code === 3) style.italic = true;
                else if (code === 4) style.underline = true;
                else if (code === 7) style.inverse = true;
                else if (code === 22) { style.bold = false; style.dim = false; }
                else if (code === 23) style.italic = false;
                else if (code === 24) style.underline = false;
                else if (code === 27) style.inverse = false;
                else if (code >= 30 && code <= 37) style.fg = COLORS[code - 30];
                else if (code === 39) style.fg = null;
                else if (code >= 40 && code <= 47) style.bg = COLORS[code - 40];
                else if (code === 49) style.bg = null;
                else if (code >= 90 && code <= 97) style.fg = `bright-${COLORS[code - 90]}`;
                else if (code >= 100 && code <= 107) style.bg = `bright-${COLORS[code - 100]}`;
                // Consume extended-color parameters without interpreting them as attributes.
                else if ((code === 38 || code === 48) && codes[i + 1] === 5) i += 2;
                else if ((code === 38 || code === 48) && codes[i + 1] === 2) i += 4;
            }
        }

        function textByte(char) {
            if (ansi === "osc" || ansi === "oscEscape") {
                if (char === "\x07" || (ansi === "oscEscape" && char === "\\")) ansi = "text";
                else ansi = char === "\x1b" ? "oscEscape" : "osc";
                return;
            }
            if (ansi === "escape") {
                ansi = char === "[" ? "csi" : char === "]" ? "osc" : "text";
                parameters = "";
                return;
            }
            if (ansi === "csi" || ansi === "discardCsi") {
                const code = char.charCodeAt(0);
                if (code >= 64 && code <= 126) {
                    if (ansi === "csi" && char === "m") { flush(); applyCodes(parameters); }
                    ansi = "text";
                    parameters = "";
                } else if (parameters.length < 256 && ansi === "csi") parameters += char;
                else { ansi = "discardCsi"; parameters = ""; }
                return;
            }
            if (char === "\x1b") { ansi = "escape"; return; }
            if (char === "\r" || char === "\n") {
                if (newline && char !== newline) { newline = ""; return; }
                newline = char;
                pending += "\n";
            } else if (char === "\t" || char.charCodeAt(0) >= 32) {
                newline = "";
                pending += char;
            }
        }

        function write(value) {
            for (const char of String(value)) {
                const code = char.charCodeAt(0);
                if (telnet === "option") {
                    if (code === 1 && (negotiation === 251 || negotiation === 252)) setSecretInput(negotiation === 251);
                    telnet = "data";
                } else if (telnet === "sub") {
                    if (code === 255) telnet = "subIac";
                } else if (telnet === "subIac") {
                    telnet = code === 240 ? "data" : "sub";
                } else if (telnet === "iac") {
                    telnet = "data";
                    if (code === 255) textByte(char);
                    else if ([251, 252, 253, 254].includes(code)) { negotiation = code; telnet = "option"; }
                    else if (code === 250) telnet = "sub";
                } else if (code === 255) telnet = "iac";
                else textByte(char);
            }
            flush();
        }

        reset();
        return { write, reset };
    }

    globalThis.TocConsoleOutput = Object.freeze({ create });
})();
