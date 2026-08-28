(() => {
    "use strict";

    const TOKEN_KEY = "toc_webadmin_token";
    const MAX_TERMINAL_CHARS = 250000;
    const ISSUE_PAGE_SIZE = 50;
    const VIEW_NAMES = new Set([
        "overview", "world", "areas", "players", "gear", "console", "logs", "operations",
    ]);
    const SVG_NS = "http://www.w3.org/2000/svg";

    const state = {
        view: "overview",
        token: "",
        authenticated: false,
        config: null,
        stats: null,
        areaHealth: null,
        areas: [],
        world: { type: "mobs", page: 1, pageSize: 50, query: "", total: 0, loading: false },
        issues: { page: 1, severity: "all", query: "" },
        terminal: { socket: null, connected: false, failed: false, secretInput: false, history: [], historyIndex: 0 },
        logs: { socket: null, shouldReconnect: false, reconnectTimer: null },
        map: { data: null, scale: 1, x: 0, y: 0, dragging: false, startX: 0, startY: 0 },
    };

    const byId = (id) => document.getElementById(id);
    const all = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    function node(tag, options = {}, children = []) {
        const element = document.createElement(tag);
        if (options.className) element.className = options.className;
        if (options.text !== undefined) element.textContent = String(options.text);
        if (options.attrs) {
            Object.entries(options.attrs).forEach(([name, value]) => {
                if (value !== null && value !== undefined) element.setAttribute(name, String(value));
            });
        }
        for (const child of children) {
            if (child === null || child === undefined) continue;
            element.append(child instanceof Node ? child : document.createTextNode(String(child)));
        }
        return element;
    }

    function svgNode(tag, attrs = {}) {
        const element = document.createElementNS(SVG_NS, tag);
        Object.entries(attrs).forEach(([name, value]) => element.setAttribute(name, String(value)));
        return element;
    }

    function formatNumber(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed.toLocaleString() : "-";
    }

    function formatBytes(value) {
        const bytes = Number(value || 0);
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
        return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
    }

    function stripMudColor(value) {
        return String(value ?? "").replace(/\{[A-Za-z0-9]/g, "");
    }

    function displayValue(value) {
        if (value === null || value === undefined || value === "") return "-";
        if (Array.isArray(value)) return value.length ? value.map(displayValue).join(", ") : "-";
        if (typeof value === "object") {
            return Object.entries(value).map(([key, item]) => `${key}: ${displayValue(item)}`).join("; ");
        }
        if (typeof value === "boolean") return value ? "Yes" : "No";
        return stripMudColor(value);
    }

    function toast(message, type = "info") {
        const item = node("div", { className: `toast ${type}`, text: message });
        byId("toast-region").append(item);
        window.setTimeout(() => item.remove(), 5000);
    }

    class ApiError extends Error {
        constructor(message, status, detail = null) {
            super(message);
            this.name = "ApiError";
            this.status = status;
            this.detail = detail;
        }
    }

    function detailMessage(detail, fallback) {
        if (typeof detail === "string" && detail.trim()) return detail;
        if (detail && typeof detail === "object") {
            if (typeof detail.message === "string") return detail.message;
            try {
                return JSON.stringify(detail);
            } catch (_) {
                return fallback;
            }
        }
        return fallback;
    }

    async function request(path, options = {}) {
        const headers = new Headers(options.headers || {});
        if (options.auth && state.token) headers.set("X-Admin-Token", state.token);
        if (options.body !== undefined && !(options.body instanceof FormData)) {
            headers.set("Content-Type", "application/json");
        }

        let response;
        try {
            response = await fetch(path, {
                method: options.method || "GET",
                headers,
                body: options.body === undefined
                    ? undefined
                    : options.body instanceof FormData ? options.body : JSON.stringify(options.body),
                signal: options.signal,
            });
        } catch (error) {
            throw new ApiError(`Network request failed: ${error.message}`, 0);
        }

        const contentType = response.headers.get("content-type") || "";
        let data = null;
        if (response.status !== 204) {
            if (contentType.includes("application/json")) {
                try {
                    data = await response.json();
                } catch (_) {
                    data = null;
                }
            } else {
                data = await response.text();
            }
        }

        if (!response.ok) {
            const detail = data && typeof data === "object" && "detail" in data ? data.detail : data;
            throw new ApiError(detailMessage(detail, `Request failed with HTTP ${response.status}`), response.status, detail);
        }
        return { data, response };
    }

    async function api(path, options = {}) {
        return (await request(path, options)).data;
    }

    function loadSavedToken() {
        const sessionToken = sessionStorage.getItem(TOKEN_KEY) || "";
        const rememberedToken = localStorage.getItem(TOKEN_KEY) || "";
        state.token = sessionToken || rememberedToken;
        byId("auth-remember").checked = Boolean(rememberedToken);
    }

    function saveToken(token, remember) {
        state.token = token.trim();
        sessionStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(TOKEN_KEY);
        if (state.token) {
            (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, state.token);
        }
    }

    function setAuthenticated(value) {
        state.authenticated = Boolean(value);
        byId("auth-dot").className = `status-dot ${value ? "status-unlocked" : "status-locked"}`;
        byId("auth-label").textContent = value ? "Admin unlocked" : "Admin locked";
        byId("runtime-auth").textContent = value
            ? "Authenticated"
            : state.config?.admin_token_configured ? "Locked" : "Disabled";
        byId("players-lock-note").textContent = value ? "Authenticated" : "Admin token required";
        byId("operations-lock-note").textContent = value ? "Authenticated" : "Admin token required";
    }

    async function validateToken(silent = false) {
        try {
            await api("/api/auth/check", { auth: Boolean(state.token) });
            setAuthenticated(true);
            return true;
        } catch (error) {
            setAuthenticated(false);
            if (!silent && error.status !== 403) toast(error.message, "error");
            return false;
        }
    }

    async function unlockLocalAdmin() {
        if (!state.config?.local_admin_unlock) return false;
        try {
            await api("/api/auth/local", { method: "POST" });
            return await validateToken(true);
        } catch (_error) {
            setAuthenticated(false);
            return false;
        }
    }

    async function ensureAuth() {
        if (state.authenticated) return true;
        if (await validateToken(true)) return true;
        if (await unlockLocalAdmin()) return true;
        openAuthDialog();
        return false;
    }

    function openAuthDialog() {
        const dialog = byId("auth-dialog");
        byId("auth-token").value = state.token;
        byId("auth-error").textContent = state.config?.admin_token_configured === false
            ? "WEB_ADMIN_TOKEN is not configured on the server."
            : "";
        if (!dialog.open) dialog.showModal();
        window.setTimeout(() => byId("auth-token").focus(), 0);
    }

    async function submitAuth(event) {
        event.preventDefault();
        const token = byId("auth-token").value.trim();
        const remember = byId("auth-remember").checked;
        const submit = byId("auth-submit");
        submit.disabled = true;
        byId("auth-error").textContent = "";
        saveToken(token, remember);
        const valid = await validateToken(true);
        submit.disabled = false;
        if (!valid) {
            byId("auth-error").textContent = state.config?.admin_token_configured === false
                ? "Admin operations are disabled until WEB_ADMIN_TOKEN is configured."
                : "The token was rejected.";
            return;
        }
        byId("auth-dialog").close();
        toast("Admin access unlocked.", "success");
        await refreshCurrentView();
    }

    async function clearAuth() {
        try {
            await api("/api/auth/logout", { method: "POST" });
        } catch (_error) {
            // Local cookie cleanup is best effort; browser token storage is cleared below.
        }
        saveToken("", false);
        setAuthenticated(false);
        stopLogs();
        byId("auth-token").value = "";
        byId("auth-dialog").close();
        toast("Admin access locked.", "success");
    }

    function closeNavigation() {
        document.body.classList.remove("nav-open");
    }

    function navigate(view, updateHash = true) {
        if (!VIEW_NAMES.has(view)) view = "overview";
        if (state.view === "logs" && view !== "logs") stopLogs();
        state.view = view;
        all(".view").forEach((item) => item.classList.toggle("is-active", item.id === `${view}-view`));
        all(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.view === view));
        const active = byId(`${view}-view`);
        byId("page-title").textContent = active?.dataset.title || "Web Admin";
        closeNavigation();
        if (updateHash && location.hash !== `#${view}`) history.replaceState(null, "", `#${view}`);
        void loadView(view);
    }

    async function loadView(view) {
        if (view === "overview") await loadOverview();
        else if (view === "world") await loadWorld();
        else if (view === "areas") await loadAreasAndHealth();
        else if (view === "players") await loadPlayerNames();
        else if (view === "logs") await connectLogs();
        else if (view === "operations") await loadBackups();
    }

    async function refreshCurrentView() {
        await loadView(state.view);
    }

    function setServiceStatus(dotId, online) {
        byId(dotId).className = `status-dot ${online ? "status-ok" : "status-offline"}`;
    }

    async function loadRuntimeStatus() {
        try {
            const health = await api("/api/health");
            setServiceStatus("admin-status-dot", Boolean(health.webadmin));
            setServiceStatus("mud-status-dot", Boolean(health.merc));
            byId("runtime-admin").textContent = health.webadmin ? "Online" : "Unavailable";
            byId("runtime-mud").textContent = health.merc ? "Online" : "Offline";
        } catch (_) {
            setServiceStatus("admin-status-dot", false);
            setServiceStatus("mud-status-dot", false);
            byId("runtime-admin").textContent = "Unavailable";
            byId("runtime-mud").textContent = "Unknown";
        }
    }

    async function loadConfig() {
        try {
            state.config = await api("/api/config");
            byId("version-label").textContent = `Web admin ${state.config.version || ""}`.trim();
            byId("runtime-endpoint").textContent = state.config.mud_endpoint || "-";
            if (!state.authenticated) {
                byId("runtime-auth").textContent = state.config.admin_token_configured ? "Locked" : "Disabled";
            }
        } catch (_) {
            state.config = null;
        }
    }

    async function loadOverview() {
        const results = await Promise.allSettled([
            api("/api/stats"),
            api("/api/area_health?include_issues=false"),
            loadRuntimeStatus(),
            loadConfig(),
        ]);

        if (results[0].status === "fulfilled") {
            state.stats = results[0].value;
            byId("metric-areas").textContent = formatNumber(state.stats.areas);
            byId("metric-rooms").textContent = formatNumber(state.stats.rooms);
            byId("metric-mobs").textContent = formatNumber(state.stats.mobiles);
            byId("metric-objects").textContent = formatNumber(state.stats.objects);
        }

        if (results[1].status === "fulfilled") {
            const summary = results[1].value.summary || {};
            const severities = summary.by_severity || {};
            byId("health-critical").textContent = formatNumber(severities.critical || 0);
            byId("health-warning").textContent = formatNumber(severities.warning || 0);
            byId("health-info").textContent = formatNumber(severities.info || 0);
            byId("health-summary").textContent = `${formatNumber(summary.issues || 0)} findings across ${formatNumber(summary.areas || 0)} parsed areas; ${formatNumber(summary.parse_errors || 0)} parse errors.`;
        }
        byId("overview-updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }

    function setTableLoading(tableId, columnCount) {
        const body = byId(tableId).querySelector("tbody");
        const cell = node("td", { className: "empty-state", text: "Loading...", attrs: { colspan: columnCount } });
        body.replaceChildren(node("tr", {}, [cell]));
    }

    function tableHeader(table, columns) {
        const row = node("tr");
        columns.forEach((column) => row.append(node("th", { text: column.label })));
        table.querySelector("thead").replaceChildren(row);
    }

    function tableCell(value, className = "") {
        return node("td", { className, text: displayValue(value) });
    }

    const worldColumns = {
        mobs: [
            { label: "Vnum", key: "vnum", className: "numeric" },
            { label: "Mobile", key: "short_desc" },
            { label: "Level", key: "level", className: "numeric" },
            { label: "Race", key: "race" },
            { label: "Area", key: "area" },
        ],
        objects: [
            { label: "Vnum", key: "vnum", className: "numeric" },
            { label: "Object", key: "short_desc" },
            { label: "Type", key: "item_type" },
            { label: "Level", key: "level", className: "numeric" },
            { label: "Wear", key: "wear_locations" },
            { label: "Area", key: "area" },
        ],
        rooms: [
            { label: "Vnum", key: "vnum", className: "numeric" },
            { label: "Room", key: "name" },
            { label: "Sector", key: "sector_type" },
            { label: "Exits", key: "exits_count", className: "numeric" },
            { label: "Area", key: "area" },
        ],
    };

    function renderWorld(items) {
        const table = byId("world-table");
        const columns = worldColumns[state.world.type];
        tableHeader(table, columns);
        const body = table.querySelector("tbody");
        if (!items.length) {
            body.replaceChildren(node("tr", {}, [node("td", { className: "empty-state", text: "No matching records.", attrs: { colspan: columns.length } })]));
            return;
        }

        const fragment = document.createDocumentFragment();
        items.forEach((item) => {
            const row = node("tr", { attrs: { "data-record-id": item.vnum, tabindex: "0" } });
            columns.forEach((column) => row.append(tableCell(item[column.key], column.className || "")));
            const open = () => void openWorldDetail(state.world.type, item.vnum);
            row.addEventListener("click", open);
            row.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    open();
                }
            });
            fragment.append(row);
        });
        body.replaceChildren(fragment);
    }

    async function loadWorld() {
        if (state.world.loading) return;
        state.world.loading = true;
        const columns = worldColumns[state.world.type];
        setTableLoading("world-table", columns.length);
        const offset = (state.world.page - 1) * state.world.pageSize;
        const params = new URLSearchParams({ limit: state.world.pageSize, offset });
        if (state.world.query) {
            params.set(state.world.type === "objects" ? "name" : "q", state.world.query);
        }

        try {
            const { data, response } = await request(`/api/${state.world.type}?${params}`);
            state.world.total = Number(response.headers.get("X-Total-Count") || data.length || 0);
            const maxPage = Math.max(1, Math.ceil(state.world.total / state.world.pageSize));
            if (state.world.page > maxPage) {
                state.world.page = maxPage;
                state.world.loading = false;
                await loadWorld();
                return;
            }
            renderWorld(data);
            byId("world-count").textContent = `${formatNumber(state.world.total)} results`;
            byId("world-page-label").textContent = `Page ${state.world.page} of ${maxPage}`;
            byId("world-prev").disabled = state.world.page <= 1;
            byId("world-next").disabled = state.world.page >= maxPage;
        } catch (error) {
            const body = byId("world-table").querySelector("tbody");
            body.replaceChildren(node("tr", {}, [node("td", { className: "empty-state", text: error.message, attrs: { colspan: columns.length } })]));
        } finally {
            state.world.loading = false;
        }
    }

    function definitionList(entries) {
        const list = node("dl", { className: "definition-grid" });
        entries.forEach(([label, value]) => {
            list.append(node("div", {}, [node("dt", { text: label }), node("dd", { text: displayValue(value) })]));
        });
        return list;
    }

    function tagList(values) {
        const wrapper = node("div", { className: "tag-list" });
        const items = Array.isArray(values) ? values : [];
        if (!items.length) wrapper.append(node("span", { className: "tag", text: "None" }));
        else items.forEach((value) => wrapper.append(node("span", { className: "tag", text: displayValue(value) })));
        return wrapper;
    }

    function detailSection(title, content, full = false) {
        return node("section", { className: `detail-section${full ? " full" : ""}` }, [
            node("h3", { text: title }), content,
        ]);
    }

    function dataTable(items, columns, emptyText = "None") {
        const frame = node("div", { className: "table-frame borderless" });
        const table = node("table");
        const headRow = node("tr");
        columns.forEach((column) => headRow.append(node("th", { text: column.label })));
        const head = node("thead", {}, [headRow]);
        const body = node("tbody");
        if (!items || !items.length) {
            body.append(node("tr", {}, [node("td", { className: "empty-state", text: emptyText, attrs: { colspan: columns.length } })]));
        } else {
            items.forEach((item) => {
                const row = node("tr");
                columns.forEach((column) => row.append(tableCell(column.value ? column.value(item) : item[column.key])));
                body.append(row);
            });
        }
        table.append(head, body);
        frame.append(table);
        return frame;
    }

    async function openWorldDetail(type, vnum) {
        const singular = type === "mobs" ? "mob" : type === "objects" ? "object" : "room";
        byId("detail-eyebrow").textContent = `${singular} #${vnum}`;
        byId("detail-title").textContent = "Loading...";
        byId("detail-body").replaceChildren(node("div", { className: "empty-state large", text: "Loading record..." }));
        if (!byId("detail-dialog").open) byId("detail-dialog").showModal();
        try {
            const data = await api(`/api/${type}/${vnum}`);
            renderWorldDetail(type, data);
        } catch (error) {
            byId("detail-title").textContent = "Unable to load record";
            byId("detail-body").replaceChildren(node("div", { className: "empty-state large", text: error.message }));
        }
    }

    function renderWorldDetail(type, data) {
        const grid = node("div", { className: "detail-grid" });
        if (type === "mobs") {
            byId("detail-title").textContent = stripMudColor(data.short_desc);
            grid.append(
                detailSection("Core", definitionList([
                    ["Vnum", data.vnum], ["Level", data.level], ["Race", data.race], ["Area", data.area],
                    ["Alignment", data.alignment], ["Hitroll", data.hitroll], ["Damage", data.dam_dice], ["Wealth", data.wealth],
                ])),
                detailSection("Combat", definitionList([
                    ["Hit points", data.hitp_dice], ["Mana", data.mana_dice], ["Damage type", data.dam_type], ["Armor", data.ac],
                    ["Start position", data.start_pos], ["Default position", data.default_pos], ["Size", data.size], ["Material", data.material],
                ])),
                detailSection("Description", node("p", { className: "description-block", text: stripMudColor(data.description || data.long_desc) }), true),
                detailSection("Flags", tagList([...(data.act_flags || []), ...(data.off_flags || []), ...(data.affected_by || [])])),
                detailSection("Defenses", tagList([...(data.imm_flags || []).map((x) => `immune: ${x}`), ...(data.res_flags || []).map((x) => `resist: ${x}`), ...(data.vuln_flags || []).map((x) => `vulnerable: ${x}`)])),
                detailSection("Drops", dataTable(data.drops, [
                    { label: "Vnum", key: "vnum" }, { label: "Object", key: "name" }, { label: "Level", key: "level" }, { label: "Type", key: "item_type" },
                ]), true),
                detailSection("Spawn rooms", dataTable(data.spawn_rooms, [
                    { label: "Vnum", key: "vnum" }, { label: "Room", key: "name" }, { label: "Area", key: "area" },
                ]), true),
            );
        } else if (type === "objects") {
            byId("detail-title").textContent = stripMudColor(data.short_desc);
            grid.append(
                detailSection("Core", definitionList([
                    ["Vnum", data.vnum], ["Level", data.level], ["Type", data.item_type], ["Material", data.material],
                    ["Weight", data.weight], ["Cost", data.cost], ["Condition", data.condition], ["Area", data.area],
                ])),
                detailSection("Flags", tagList([...(data.extra_flags || []), ...(data.wear_flags || [])])),
                detailSection("Description", node("p", { className: "description-block", text: stripMudColor(data.long_desc) }), true),
                detailSection("Values", definitionList(Object.entries(data.values_interpreted || data.values || {}).map(([key, value]) => [key, value]))),
                detailSection("Affects", dataTable(data.affects, [
                    { label: "Location", value: (item) => item.location ?? item.apply ?? "-" },
                    { label: "Modifier", key: "modifier" },
                ])),
                detailSection("Carried by", dataTable(data.carried_by, [
                    { label: "Vnum", key: "vnum" }, { label: "Mobile", key: "name" }, { label: "Level", key: "level" }, { label: "Area", key: "area" },
                ]), true),
            );
        } else {
            byId("detail-title").textContent = stripMudColor(data.name);
            grid.append(
                detailSection("Core", definitionList([
                    ["Vnum", data.vnum], ["Area", data.area], ["Area file", data.area_file], ["Sector", data.sector_type],
                ])),
                detailSection("Flags", tagList(data.room_flags)),
                detailSection("Description", node("p", { className: "description-block", text: stripMudColor(data.description) }), true),
                detailSection("Exits", dataTable(data.exits, [
                    { label: "Direction", key: "direction" }, { label: "To", value: (item) => `#${item.to_room} ${stripMudColor(item.to_room_name)}` },
                    { label: "Door", key: "keyword" }, { label: "Key", key: "key_vnum" },
                ]), true),
                detailSection("Mobiles", dataTable(data.mobs, [
                    { label: "Vnum", key: "vnum" }, { label: "Mobile", key: "name" }, { label: "Level", key: "level" }, { label: "Race", key: "race" },
                ])),
                detailSection("Objects", dataTable(data.objects, [
                    { label: "Vnum", key: "vnum" }, { label: "Object", key: "name" }, { label: "Level", key: "level" }, { label: "Type", key: "item_type" },
                ])),
            );
        }
        byId("detail-body").replaceChildren(grid);
    }

    async function loadAreasAndHealth() {
        setTableLoading("issues-table", 4);
        setTableLoading("areas-table", 5);
        try {
            const [health, areas] = await Promise.all([api("/api/area_health"), api("/api/areas")]);
            state.areaHealth = health;
            state.areas = areas;
            const summary = health.summary || {};
            const severities = summary.by_severity || {};
            byId("area-critical-count").textContent = formatNumber(severities.critical || 0);
            byId("area-warning-count").textContent = formatNumber(severities.warning || 0);
            byId("area-info-count").textContent = formatNumber(severities.info || 0);
            byId("area-parse-count").textContent = formatNumber(summary.parse_errors || 0);
            renderIssues();
            renderAreas();
        } catch (error) {
            toast(error.message, "error");
        }
    }

    function filteredIssues() {
        const issues = state.areaHealth?.issues || [];
        const query = state.issues.query.toLowerCase();
        return issues.filter((issue) => {
            if (state.issues.severity !== "all" && issue.severity !== state.issues.severity) return false;
            if (!query) return true;
            return [issue.code, issue.area_file, issue.message, issue.vnum].some((value) => String(value ?? "").toLowerCase().includes(query));
        });
    }

    function renderIssues() {
        const filtered = filteredIssues();
        const pages = Math.max(1, Math.ceil(filtered.length / ISSUE_PAGE_SIZE));
        state.issues.page = Math.min(state.issues.page, pages);
        const start = (state.issues.page - 1) * ISSUE_PAGE_SIZE;
        const items = filtered.slice(start, start + ISSUE_PAGE_SIZE);
        const body = byId("issues-table").querySelector("tbody");
        const fragment = document.createDocumentFragment();
        items.forEach((issue) => {
            const location = [issue.area_file, issue.vnum ? `#${issue.vnum}` : ""].filter(Boolean).join(" ");
            fragment.append(node("tr", {}, [
                node("td", {}, [node("span", { className: `severity-badge severity-${issue.severity}`, text: issue.severity })]),
                tableCell(issue.code), tableCell(location), tableCell(issue.message),
            ]));
        });
        if (!items.length) fragment.append(node("tr", {}, [node("td", { className: "empty-state", text: "No matching issues.", attrs: { colspan: 4 } })]));
        body.replaceChildren(fragment);
        byId("issue-count").textContent = `${formatNumber(filtered.length)} issues`;
        byId("issues-page-label").textContent = `Page ${state.issues.page} of ${pages}`;
        byId("issues-prev").disabled = state.issues.page <= 1;
        byId("issues-next").disabled = state.issues.page >= pages;
    }

    function renderAreas() {
        const query = byId("area-search").value.trim().toLowerCase();
        const areas = state.areas.filter((area) => !query || [area.name, area.builder, area.filename, area.vnums].some((value) => String(value ?? "").toLowerCase().includes(query)));
        const body = byId("areas-table").querySelector("tbody");
        const fragment = document.createDocumentFragment();
        areas.forEach((area) => {
            const mapButton = node("button", { className: "button button-secondary compact", text: "Map", attrs: { type: "button" } });
            mapButton.addEventListener("click", () => void openAreaMap(area.filename));
            fragment.append(node("tr", {}, [
                tableCell(area.name), tableCell(area.builder || area.builders), tableCell(area.filename, "mono"), tableCell(area.vnums), node("td", {}, [mapButton]),
            ]));
        });
        if (!areas.length) fragment.append(node("tr", {}, [node("td", { className: "empty-state", text: "No matching areas.", attrs: { colspan: 5 } })]));
        body.replaceChildren(fragment);
    }

    function setAreaTab(tab) {
        all("[data-area-tab]").forEach((button) => button.classList.toggle("is-active", button.dataset.areaTab === tab));
        byId("area-issues-panel").hidden = tab !== "issues";
        byId("area-catalog-panel").hidden = tab !== "catalog";
    }

    async function openAreaMap(filename) {
        byId("map-title").textContent = "Loading area map...";
        byId("map-room-count").textContent = "";
        byId("area-map").replaceChildren();
        if (!byId("map-dialog").open) byId("map-dialog").showModal();
        try {
            const data = await api(`/api/areas/${encodeURIComponent(filename)}/map`);
            state.map.data = data;
            state.map.scale = 1;
            state.map.x = 0;
            state.map.y = 0;
            byId("map-title").textContent = stripMudColor(data.area_name);
            byId("map-room-count").textContent = `${formatNumber(data.rooms.length)} rooms`;
            renderAreaMap(data);
            applyMapTransform();
        } catch (error) {
            byId("map-title").textContent = "Unable to load map";
            byId("map-room-count").textContent = error.message;
        }
    }

    function renderAreaMap(data) {
        const svg = byId("area-map");
        svg.replaceChildren();
        if (!data.rooms.length) return;
        const roomByVnum = new Map(data.rooms.map((room) => [room.vnum, room]));
        const spacing = 96;
        const roomWidth = 76;
        const roomHeight = 42;
        const xs = data.rooms.map((room) => room.x * spacing);
        const ys = data.rooms.map((room) => room.y * spacing);
        const minX = Math.min(...xs) - 80;
        const minY = Math.min(...ys) - 80;
        const width = Math.max(320, Math.max(...xs) - minX + 160);
        const height = Math.max(240, Math.max(...ys) - minY + 160);
        svg.setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`);

        const exits = svgNode("g", { "aria-hidden": "true" });
        data.rooms.forEach((room) => {
            for (const exit of room.exits || []) {
                const target = roomByVnum.get(exit.to_room);
                if (!target || room.vnum > target.vnum) continue;
                exits.append(svgNode("line", {
                    class: "map-exit",
                    x1: room.x * spacing,
                    y1: room.y * spacing,
                    x2: target.x * spacing,
                    y2: target.y * spacing,
                }));
            }
        });
        svg.append(exits);

        const rooms = svgNode("g");
        data.rooms.forEach((room) => {
            const classes = ["map-room"];
            if (room.mob_count) classes.push("has-mob");
            if (room.obj_count) classes.push("has-object");
            const group = svgNode("g", {
                class: classes.join(" "),
                transform: `translate(${room.x * spacing - roomWidth / 2} ${room.y * spacing - roomHeight / 2})`,
                tabindex: "0",
                role: "button",
            });
            group.append(svgNode("rect", { width: roomWidth, height: roomHeight, rx: 4 }));
            const title = svgNode("title");
            title.textContent = `#${room.vnum} ${stripMudColor(room.name)}`;
            group.append(title);
            const name = svgNode("text", { x: roomWidth / 2, y: 17, "text-anchor": "middle" });
            const cleanName = stripMudColor(room.name);
            name.textContent = cleanName.length > 13 ? `${cleanName.slice(0, 11)}..` : cleanName;
            const vnum = svgNode("text", { class: "map-vnum", x: roomWidth / 2, y: 32, "text-anchor": "middle" });
            vnum.textContent = `#${room.vnum}`;
            group.append(name, vnum);
            const open = () => {
                byId("map-dialog").close();
                void openWorldDetail("rooms", room.vnum);
            };
            group.addEventListener("click", open);
            group.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    open();
                }
            });
            rooms.append(group);
        });
        svg.append(rooms);
    }

    function applyMapTransform() {
        byId("area-map").style.transform = `translate(${state.map.x}px, ${state.map.y}px) scale(${state.map.scale})`;
    }

    async function loadPlayerNames() {
        if (!await ensureAuth()) return;
        try {
            const names = await api("/api/players", { auth: true });
            const list = byId("player-names");
            list.replaceChildren(...names.map((name) => node("option", { attrs: { value: name } })));
        } catch (error) {
            if (error.status === 403) setAuthenticated(false);
            toast(error.message, "error");
        }
    }

    async function loadPlayer(name) {
        if (!await ensureAuth()) return;
        const profile = byId("player-profile");
        profile.replaceChildren(node("div", { className: "empty-state large", text: "Loading player..." }));
        try {
            const data = await api(`/api/player/${encodeURIComponent(name)}`, { auth: true });
            renderPlayer(data);
        } catch (error) {
            profile.replaceChildren(node("div", { className: "empty-state large", text: error.message }));
        }
    }

    function resourceLabel(current, maximum) {
        return `${formatNumber(current)} / ${formatNumber(maximum)}`;
    }

    function renderPlayer(player) {
        const profile = byId("player-profile");
        const summary = node("div", { className: "player-summary" });
        [
            ["Name", [player.name, stripMudColor(player.title || "")].filter(Boolean).join(" ")],
            ["Level", player.level],
            ["Class", player.class_name],
            ["Guild", player.guild_name],
            ["Race", player.race],
            ["Remorts", player.num_remorts],
        ].forEach(([label, value]) => summary.append(node("div", {}, [node("span", { text: label }), node("strong", { text: displayValue(value) })])));

        const left = node("div");
        left.append(
            profileSection("Resources", definitionList([
                ["Hit points", resourceLabel(player.hp_cur, player.hp_max)],
                ["Mana", resourceLabel(player.mana_cur, player.mana_max)],
                ["Movement", resourceLabel(player.mv_cur, player.mv_max)],
                ["Experience", formatNumber(player.exp)],
                ["Practices", player.practices],
                ["Trains", player.trains],
                ["Quest points", player.quest_points],
                ["Gold / platinum", `${formatNumber(player.gold)} / ${formatNumber(player.platinum)}`],
            ])),
            profileSection("Attributes", definitionList([
                ["Strength", player.str_total], ["Intelligence", player.int_total], ["Wisdom", player.wis_total],
                ["Dexterity", player.dex_total], ["Constitution", player.con_total], ["Hitroll", player.hitroll],
                ["Damroll", player.damroll], ["Alignment", player.alignment],
            ])),
            profileSection("Active affects", tagList((player.affects || []).map((affect) => `${affect.spell}${affect.duration !== undefined ? ` (${affect.duration})` : ""}`))),
        );

        const right = node("div");
        right.append(
            profileSection("Description", node("p", { className: "description-block", text: stripMudColor(player.description || "No description set.") })),
            profileSection("Equipment", dataTable(player.equipment, [
                { label: "Slot", value: (item) => item.wear_slot || item.wear },
                { label: "Vnum", key: "vnum" }, { label: "Object", key: "name" },
                { label: "Level", key: "level" }, { label: "Affects", value: (item) => displayValue(item.affects) },
            ], "No equipment.")),
            profileSection("Skills", dataTable((player.skills || []).slice().sort((a, b) => b.pct - a.pct), [
                { label: "Skill", key: "name" }, { label: "Learned", value: (item) => `${item.pct}%` },
            ], "No learned skills.")),
        );

        profile.replaceChildren(summary, node("div", { className: "player-grid" }, [left, right]));
    }

    function profileSection(title, content) {
        return node("section", { className: "profile-section" }, [node("h3", { text: title }), content]);
    }

    async function loadGear() {
        const className = byId("gear-class").value;
        const raceName = byId("gear-race").value;
        const level = Number(byId("gear-level").value);
        const limit = Number(byId("gear-limit").value);
        const results = byId("gear-results");
        results.replaceChildren(node("div", { className: "empty-state large", text: "Scoring available equipment..." }));
        try {
            const params = new URLSearchParams({ class_name: className, race_name: raceName, level, limit });
            const data = await api(`/api/best_gear?${params}`);
            renderGear(data);
        } catch (error) {
            results.replaceChildren(node("div", { className: "empty-state large", text: error.message }));
        }
    }

    function renderGear(data) {
        const results = byId("gear-results");
        const fragment = document.createDocumentFragment();
        const slots = Object.entries(data).sort(([a], [b]) => a.localeCompare(b));
        if (!slots.length) {
            results.replaceChildren(node("div", { className: "empty-state large", text: "No compatible scored gear was found." }));
            return;
        }
        slots.forEach(([slot, items]) => {
            const section = node("section", { className: "gear-slot" }, [node("h3", { text: slot })]);
            items.forEach((item) => {
                const details = node("details");
                details.append(node("summary", { text: "Score details" }));
                const list = node("ul");
                (item.score_breakdown || []).forEach((line) => list.append(node("li", { text: line })));
                details.append(list);
                const nameButton = node("button", { className: "text-button", text: stripMudColor(item.name), attrs: { type: "button" } });
                nameButton.addEventListener("click", () => void openWorldDetail("objects", item.vnum));
                section.append(node("div", { className: "gear-item" }, [
                    node("div", {}, [nameButton, node("small", { text: ` #${item.vnum}` })]),
                    node("div", {}, [node("small", { text: "Level" }), node("div", { text: item.level })]),
                    node("div", {}, [node("small", { text: "Score" }), node("div", { text: item.score })]),
                    node("div", {}, [node("small", { text: stripMudColor(item.area) }), details]),
                ]));
            });
            fragment.append(section);
        });
        results.replaceChildren(fragment);
    }

    function setConsoleConnected(connected, label = null) {
        state.terminal.connected = connected;
        byId("console-status").textContent = label || (connected ? "Connected" : "Disconnected");
        byId("console-connect").disabled = connected;
        byId("console-disconnect").disabled = !connected;
        byId("console-input").disabled = !connected;
        byId("console-form").querySelector("button").disabled = !connected;
        if (connected) byId("console-input").focus();
    }

    function appendTerminal(element, text) {
        const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        element.textContent += text;
        if (element.textContent.length > MAX_TERMINAL_CHARS) {
            element.textContent = element.textContent.slice(-MAX_TERMINAL_CHARS);
        }
        if (nearBottom) element.scrollTop = element.scrollHeight;
    }

    function decodeMudOutput(value) {
        let output = "";
        for (let index = 0; index < value.length; index += 1) {
            const code = value.charCodeAt(index);
            if (code !== 255) {
                output += value[index];
                continue;
            }
            const command = value.charCodeAt(index + 1);
            const option = value.charCodeAt(index + 2);
            if (command === 251 || command === 252 || command === 253 || command === 254) {
                if (option === 1 && command === 251) state.terminal.secretInput = true;
                if (option === 1 && command === 252) state.terminal.secretInput = false;
                index += 2;
                continue;
            }
            if (command === 250) {
                index += 2;
                while (index + 1 < value.length && !(value.charCodeAt(index) === 255 && value.charCodeAt(index + 1) === 240)) index += 1;
                index += 1;
                continue;
            }
            index += 1;
        }
        byId("console-input").type = state.terminal.secretInput ? "password" : "text";
        byId("console-input").placeholder = state.terminal.secretInput ? "Password" : "Command";
        return output
            .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "")
            .replace(/\r\n|\n\r/g, "\n")
            .replace(/\r/g, "\n");
    }

    function connectConsole() {
        if (state.terminal.socket && state.terminal.socket.readyState < WebSocket.CLOSING) return;
        state.terminal.failed = false;
        setConsoleConnected(false, "Connecting to game");
        byId("console-connect").disabled = true;
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const socket = new WebSocket(`${protocol}//${location.host}/ws`);
        state.terminal.socket = socket;
        socket.addEventListener("open", () => {
            byId("console-status").textContent = "Connecting to game";
        });
        socket.addEventListener("message", (event) => {
            const message = String(event.data);
            if (message === "\0TOC_CONNECTED") {
                setConsoleConnected(true);
                appendTerminal(byId("game-terminal"), "[Connected]\n");
                return;
            }
            if (message.startsWith("\0TOC_ERROR:")) {
                state.terminal.failed = true;
                setConsoleConnected(false, "Game unavailable");
                appendTerminal(byId("game-terminal"), `[${message.slice(11)}]\n`);
                return;
            }
            appendTerminal(byId("game-terminal"), decodeMudOutput(message));
        });
        socket.addEventListener("close", () => {
            if (state.terminal.socket === socket) state.terminal.socket = null;
            setConsoleConnected(false, state.terminal.failed ? "Game unavailable" : "Disconnected");
            appendTerminal(byId("game-terminal"), "\n[Disconnected]\n");
        });
        socket.addEventListener("error", () => setConsoleConnected(false, "Connection error"));
    }

    function disconnectConsole() {
        state.terminal.socket?.close();
    }

    function sendConsoleCommand(event) {
        event.preventDefault();
        const input = byId("console-input");
        const command = input.value;
        let commands = [command];
        if (!state.terminal.socket || state.terminal.socket.readyState !== WebSocket.OPEN) return;
        if (!state.terminal.secretInput && command.includes(";")) {
            if (!window.TocCommandSequence) {
                toast("Command chaining is unavailable. Reload the dashboard.", "error");
                return;
            }
            const sequence = window.TocCommandSequence.parse(command);
            if (sequence.overflow) {
                toast(`A command chain can contain at most ${window.TocCommandSequence.MAX_COMMANDS} commands.`, "error");
                return;
            }
            commands = sequence.commands;
        }
        commands.forEach((part) => {
            state.terminal.socket.send(`${part}\n`);
            if (!state.terminal.secretInput && part) {
                appendTerminal(byId("game-terminal"), `> ${part}\n`);
            }
        });
        const shouldRemember = commands.length > 0 || !command.includes(";");
        if (!state.terminal.secretInput && shouldRemember && command) {
            if (state.terminal.history.at(-1) !== command) state.terminal.history.push(command);
            state.terminal.history = state.terminal.history.slice(-100);
        }
        state.terminal.historyIndex = state.terminal.history.length;
        input.value = "";
    }

    function focusConsoleFromTerminal() {
        const selection = window.getSelection();
        if (selection && !selection.isCollapsed) return;
        const input = byId("console-input");
        if (!input.disabled) input.focus();
    }

    function stopLogs() {
        state.logs.shouldReconnect = false;
        window.clearTimeout(state.logs.reconnectTimer);
        if (state.logs.socket) {
            state.logs.socket.onclose = null;
            if (state.logs.socket.readyState === WebSocket.OPEN) {
                state.logs.socket.send(JSON.stringify({ type: "close" }));
            }
            state.logs.socket.close();
            state.logs.socket = null;
        }
        byId("log-status").textContent = "Disconnected";
    }

    async function connectLogs() {
        if (!await ensureAuth()) return;
        stopLogs();
        state.logs.shouldReconnect = true;
        byId("log-status").textContent = "Connecting";
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const socket = new WebSocket(`${protocol}//${location.host}/ws/logs`);
        state.logs.socket = socket;
        socket.addEventListener("open", () => {
            socket.send(JSON.stringify({ type: "auth", token: state.token }));
        });
        socket.addEventListener("message", (event) => {
            byId("log-status").textContent = "Live";
            appendTerminal(byId("log-terminal"), String(event.data));
        });
        socket.addEventListener("close", (event) => {
            if (state.logs.socket === socket) state.logs.socket = null;
            if (event.code === 4003) {
                state.logs.shouldReconnect = false;
                setAuthenticated(false);
                byId("log-status").textContent = "Forbidden";
                appendTerminal(byId("log-terminal"), "[Log access rejected]\n");
                return;
            }
            byId("log-status").textContent = "Disconnected";
            if (state.logs.shouldReconnect && state.view === "logs") {
                state.logs.reconnectTimer = window.setTimeout(connectLogs, 3000);
            }
        });
        socket.addEventListener("error", () => {
            byId("log-status").textContent = "Connection error";
        });
    }

    async function readLatestLogs() {
        if (!await ensureAuth()) return;
        const lines = Math.max(1, Math.min(5000, Number(byId("log-lines").value) || 300));
        try {
            const text = await api(`/api/logs?lines=${lines}`, { auth: true });
            byId("log-terminal").textContent = text;
            byId("log-terminal").scrollTop = byId("log-terminal").scrollHeight;
            byId("log-status").textContent = "Snapshot";
        } catch (error) {
            if (error.status === 404) {
                byId("log-terminal").textContent = "Log file not found.\n";
                byId("log-status").textContent = "No log file";
            } else {
                toast(error.message, "error");
            }
        }
    }

    async function confirmAction({ title, message, phrase = "", danger = true }) {
        const dialog = byId("confirm-dialog");
        byId("confirm-title").textContent = title;
        byId("confirm-message").textContent = message;
        byId("confirm-phrase-row").hidden = !phrase;
        byId("confirm-phrase-label").textContent = phrase;
        byId("confirm-phrase").value = "";
        byId("confirm-submit").className = `button ${danger ? "button-danger" : "button-primary"}`;
        dialog.showModal();
        return new Promise((resolve) => {
            dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
        });
    }

    async function runOperation(type) {
        if (!await ensureAuth()) return;
        const descriptions = {
            backup: { title: "Create backup", message: "Queue a new server backup?", danger: false },
            reload: { title: "Refresh dashboard data", message: "Reparse area files for the dashboard? The running game is not reloaded.", danger: false },
            shutdown: { title: "Shut down game", message: "This queues an immediate game-server shutdown.", phrase: "SHUTDOWN", danger: true },
        };
        if (!await confirmAction(descriptions[type])) return;
        try {
            const result = await api(`/api/${type}`, { method: "POST", auth: true });
            const label = type === "reload" && result && typeof result === "object"
                ? `Dashboard refreshed: ${formatNumber(result.rooms)} rooms.`
                : `${type[0].toUpperCase()}${type.slice(1)} queued.`;
            toast(label, "success");
            if (type === "reload") {
                state.areaHealth = null;
                await loadOverview();
            }
        } catch (error) {
            toast(error.message, "error");
        }
    }

    async function loadBackups() {
        if (!await ensureAuth()) return;
        setTableLoading("backups-table", 3);
        try {
            const backups = await api("/api/backups", { auth: true });
            const body = byId("backups-table").querySelector("tbody");
            if (!backups.length) {
                body.replaceChildren(node("tr", {}, [node("td", { className: "empty-state", text: "No backup archives found.", attrs: { colspan: 3 } })]));
                return;
            }
            body.replaceChildren(...backups.map((backup) => node("tr", {}, [
                tableCell(backup.name, "mono"), tableCell(formatBytes(backup.size_bytes)), tableCell(new Date(backup.modified * 1000).toLocaleString()),
            ])));
        } catch (error) {
            byId("backups-table").querySelector("tbody").replaceChildren(node("tr", {}, [node("td", { className: "empty-state", text: error.message, attrs: { colspan: 3 } })]));
        }
    }

    async function submitBroadcast(event) {
        event.preventDefault();
        if (!await ensureAuth()) return;
        const message = byId("broadcast-message").value.trim();
        const level = Number(byId("broadcast-level").value);
        if (!message) return;
        try {
            await api("/api/wizinfo", { method: "POST", auth: true, body: { message, level } });
            byId("broadcast-message").value = "";
            toast("Broadcast queued.", "success");
        } catch (error) {
            toast(error.message, "error");
        }
    }

    async function submitAdminCommand(event) {
        event.preventDefault();
        if (!await ensureAuth()) return;
        const command = byId("admin-command").value.trim();
        if (!command) return;
        if (!await confirmAction({ title: "Queue immortal command", message: `Run: ${command}`, danger: true })) return;
        try {
            await api("/api/command", { method: "POST", auth: true, body: { command } });
            byId("admin-command").value = "";
            toast("Command queued.", "success");
        } catch (error) {
            toast(error.message, "error");
        }
    }

    function bindEvents() {
        all("[data-view]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.view)));
        all("[data-go-view]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.goView)));
        byId("menu-button").addEventListener("click", () => document.body.classList.toggle("nav-open"));
        byId("sidebar-scrim").addEventListener("click", closeNavigation);
        byId("refresh-view").addEventListener("click", () => void refreshCurrentView());
        byId("auth-button").addEventListener("click", openAuthDialog);
        byId("auth-form").addEventListener("submit", submitAuth);
        byId("auth-clear").addEventListener("click", clearAuth);
        byId("auth-dialog").querySelector("[value=cancel]").addEventListener("click", (event) => {
            event.preventDefault();
            byId("auth-dialog").close();
        });
        byId("detail-close").addEventListener("click", () => byId("detail-dialog").close());
        byId("map-close").addEventListener("click", () => byId("map-dialog").close());

        all("[data-world-type]").forEach((button) => button.addEventListener("click", () => {
            state.world.type = button.dataset.worldType;
            state.world.page = 1;
            all("[data-world-type]").forEach((item) => item.classList.toggle("is-active", item === button));
            void loadWorld();
        }));
        let worldTimer = null;
        byId("world-search").addEventListener("input", (event) => {
            window.clearTimeout(worldTimer);
            worldTimer = window.setTimeout(() => {
                state.world.query = event.target.value.trim();
                state.world.page = 1;
                void loadWorld();
            }, 250);
        });
        byId("world-page-size").addEventListener("change", (event) => {
            state.world.pageSize = Number(event.target.value);
            state.world.page = 1;
            void loadWorld();
        });
        byId("world-prev").addEventListener("click", () => {
            if (state.world.page > 1) state.world.page -= 1;
            void loadWorld();
        });
        byId("world-next").addEventListener("click", () => {
            state.world.page += 1;
            void loadWorld();
        });

        all("[data-area-tab]").forEach((button) => button.addEventListener("click", () => setAreaTab(button.dataset.areaTab)));
        byId("issue-search").addEventListener("input", (event) => {
            state.issues.query = event.target.value.trim();
            state.issues.page = 1;
            renderIssues();
        });
        byId("issue-severity").addEventListener("change", (event) => {
            state.issues.severity = event.target.value;
            state.issues.page = 1;
            renderIssues();
        });
        byId("issues-prev").addEventListener("click", () => {
            state.issues.page = Math.max(1, state.issues.page - 1);
            renderIssues();
        });
        byId("issues-next").addEventListener("click", () => {
            state.issues.page += 1;
            renderIssues();
        });
        byId("area-search").addEventListener("input", renderAreas);

        byId("player-form").addEventListener("submit", (event) => {
            event.preventDefault();
            const name = byId("player-search").value.trim();
            if (name) void loadPlayer(name);
        });
        byId("gear-form").addEventListener("submit", (event) => {
            event.preventDefault();
            void loadGear();
        });

        byId("console-connect").addEventListener("click", connectConsole);
        byId("console-disconnect").addEventListener("click", disconnectConsole);
        byId("console-clear").addEventListener("click", () => { byId("game-terminal").textContent = ""; });
        byId("console-form").addEventListener("submit", sendConsoleCommand);
        byId("console-input").addEventListener("keydown", (event) => {
            if (!state.terminal.history.length) return;
            if (event.key === "ArrowUp") {
                event.preventDefault();
                state.terminal.historyIndex = Math.max(0, state.terminal.historyIndex - 1);
                event.target.value = state.terminal.history[state.terminal.historyIndex] || "";
            } else if (event.key === "ArrowDown") {
                event.preventDefault();
                state.terminal.historyIndex = Math.min(state.terminal.history.length, state.terminal.historyIndex + 1);
                event.target.value = state.terminal.history[state.terminal.historyIndex] || "";
            }
        });
        byId("game-terminal").addEventListener("click", focusConsoleFromTerminal);

        byId("logs-connect").addEventListener("click", () => void connectLogs());
        byId("logs-refresh").addEventListener("click", () => void readLatestLogs());
        byId("logs-clear").addEventListener("click", () => { byId("log-terminal").textContent = ""; });
        all("[data-operation]").forEach((button) => button.addEventListener("click", () => void runOperation(button.dataset.operation)));
        byId("backups-refresh").addEventListener("click", () => void loadBackups());
        byId("broadcast-form").addEventListener("submit", submitBroadcast);
        byId("command-form").addEventListener("submit", submitAdminCommand);

        byId("confirm-form").addEventListener("submit", (event) => {
            if (event.submitter?.value !== "confirm") return;
            const phrase = byId("confirm-phrase-label").textContent;
            if (phrase && byId("confirm-phrase").value !== phrase) {
                event.preventDefault();
                toast(`Type ${phrase} to confirm.`, "warning");
            }
        });

        const mapCanvas = byId("map-canvas");
        mapCanvas.addEventListener("wheel", (event) => {
            event.preventDefault();
            state.map.scale = Math.max(0.45, Math.min(3, state.map.scale + (event.deltaY < 0 ? 0.1 : -0.1)));
            applyMapTransform();
        }, { passive: false });
        mapCanvas.addEventListener("pointerdown", (event) => {
            if (event.target.closest(".map-room")) return;
            state.map.dragging = true;
            state.map.startX = event.clientX - state.map.x;
            state.map.startY = event.clientY - state.map.y;
            mapCanvas.setPointerCapture(event.pointerId);
            mapCanvas.classList.add("is-dragging");
        });
        mapCanvas.addEventListener("pointermove", (event) => {
            if (!state.map.dragging) return;
            state.map.x = event.clientX - state.map.startX;
            state.map.y = event.clientY - state.map.startY;
            applyMapTransform();
        });
        const finishDrag = () => {
            state.map.dragging = false;
            mapCanvas.classList.remove("is-dragging");
        };
        mapCanvas.addEventListener("pointerup", finishDrag);
        mapCanvas.addEventListener("pointercancel", finishDrag);

        window.addEventListener("hashchange", () => navigate(location.hash.slice(1), false));
        document.addEventListener("keydown", (event) => {
            const tag = event.target?.tagName?.toLowerCase();
            if (tag === "input" || tag === "textarea" || tag === "select" || event.target?.isContentEditable) return;
            if (event.key === "/") {
                event.preventDefault();
                navigate("world");
                byId("world-search").focus();
            }
        });
    }

    async function init() {
        loadSavedToken();
        bindEvents();
        await loadConfig();
        if (!await validateToken(true)) await unlockLocalAdmin();
        navigate(location.hash.slice(1) || "overview", false);
    }

    void init();
})();
