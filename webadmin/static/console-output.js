(() => {
    "use strict";

    const COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"];

    // Extended colours: 0-15 of the 256 are the sixteen the stylesheet
    // themes; the rest, and true colour, are drawn exactly, as "#rrggbb"
    // carried in an inline custom property. They used to be dropped,
    // leaving the colour before them in force.
    function hex(r, g, b) {
        return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
    }

    function xterm256(n) {
        if (n >= 232) { const v = 8 + (n - 232) * 10; return hex(v, v, v); }
        const cube = n - 16;
        const level = (step) => (step === 0 ? 0 : 55 + step * 40);
        return hex(level(Math.floor(cube / 36)), level(Math.floor(cube / 6) % 6), level(cube % 6));
    }

    function extendedAnsi(codes, index, names) {
        // codes[index] is 38 or 48; returns [colour or null, codes consumed].
        const byte = (v) => Number.isInteger(v) && v >= 0 && v <= 255;
        if (codes[index + 1] === 5) {
            const n = codes[index + 2];
            if (!byte(n)) return [null, 2];
            if (n < 16) return [n < 8 ? names[n] : `bright-${names[n - 8]}`, 2];
            return [xterm256(n), 2];
        }
        if (codes[index + 1] === 2) {
            const rgb = [codes[index + 2], codes[index + 3], codes[index + 4]];
            return [rgb.every(byte) ? hex(...rgb) : null, 4];
        }
        return [null, 0];
    }

    // The class for a colour, and for an exact one its inline property.
    function colourParts(kind, colour) {
        if (!colour) return ["", ""];
        if (colour.startsWith("#")) return [`ansi-${kind}-rgb`, `--ansi-${kind}: ${colour};`];
        return [`ansi-${kind}-${colour}`, ""];
    }

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
            const fg = colourParts("fg", style.fg);
            const bg = colourParts("bg", style.bg);
            if (fg[0]) classes.push(fg[0]);
            if (bg[0]) classes.push(bg[0]);
            writeText(pending, classes.join(" "), fg[1] + bg[1]);
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
                else if (code === 38 || code === 48) {
                    const [colour, used] = extendedAnsi(codes, i, COLORS);
                    if (colour) style[code === 38 ? "fg" : "bg"] = colour;
                    i += used;
                }
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
