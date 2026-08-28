(() => {
    "use strict";

    const MAX_COMMANDS = 50;

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

    window.TocCommandSequence = Object.freeze({ MAX_COMMANDS, parse });
})();
