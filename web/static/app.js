let usersCache = new Map();
let eventsCache = [];

async function fetchJSON(url, options) {
    const opts = { ...options };
    const token = localStorage.getItem("auth_token");
    if (token) {
        opts.headers = { ...(opts.headers || {}), "Authorization": `Bearer ${token}` };
    }
    const resp = await fetch(url, opts);
    if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${detail}`);
    }
    return await resp.json();
}

function stateBadge(state) {
    const classMap = {
        IDLE: "pill idle",
        WAIT_ENTER: "pill wait",
        CHECK_ROOM: "pill check",
        ACCESS_GRANTED: "pill ok",
        ACCESS_DENIED: "pill deny",
        ALARM: "pill alarm",
        RESET: "pill reset",
    };
    const cls = classMap[state] || "pill";
    return `<span class="${cls}">${state}</span>`;
}

function doorStateFromFSM(state) {
    // Простая интерпретация: куда подсветить замок/доступ и тревогу
    switch (state) {
        case "WAIT_ENTER":
            return { door1Locked: false, door2Locked: true, alarm: false };
        case "ACCESS_GRANTED":
            return { door1Locked: true, door2Locked: false, alarm: false };
        case "ALARM":
            return { door1Locked: true, door2Locked: true, alarm: true };
        case "CHECK_ROOM":
        case "ACCESS_DENIED":
        case "RESET":
        case "IDLE":
        default:
            return { door1Locked: true, door2Locked: true, alarm: false };
    }
}

function renderDoors(state) {
    const map = doorStateFromFSM(state);
    const d1 = document.getElementById("door1-state");
    const d2 = document.getElementById("door2-state");
    const alarm = document.getElementById("alarm-state");
    if (!d1 || !d2 || !alarm) return;
    d1.textContent = map.door1Locked ? "Locked" : "Unlocked";
    d2.textContent = map.door2Locked ? "Locked" : "Unlocked";
    alarm.textContent = map.alarm ? "ALARM" : "Safe";
    d1.className = "door-state " + (map.door1Locked ? "locked" : "unlocked");
    d2.className = "door-state " + (map.door2Locked ? "locked" : "unlocked");
    alarm.className = "room-state " + (map.alarm ? "alarm" : "safe");
}

async function loadStatus() {
    try {
        const data = await fetchJSON("/api/status/");
        const el = document.getElementById("status-content");
        const userName = data.current_user_id && usersCache.has(data.current_user_id)
            ? usersCache.get(data.current_user_id).name
            : "-";
        el.innerHTML = `
            <div class="status-card">
                <div class="label">State</div>
                <div class="value">${stateBadge(data.state)}</div>
            </div>
            <div class="status-card">
                <div class="label">Current user</div>
                <div class="value">${userName} ${data.current_user_id ? "(#" + data.current_user_id + ")" : ""}</div>
            </div>
            <div class="status-card">
                <div class="label">Current card</div>
                <div class="value">${data.current_card_id ?? "-"}</div>
            </div>
        `;
        renderDoors(data.state);
    } catch (e) {
        console.error(e);
    }
}

async function loadUsers() {
    try {
        const users = await fetchJSON("/api/users/");
        usersCache = new Map(users.map(u => [u.id, u]));
        const tbody = document.querySelector("#users-table tbody");
        tbody.innerHTML = "";
        for (const u of users) {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${u.id}</td>
                <td>${u.name}</td>
                <td>${u.login}</td>
                <td>${u.card_id}</td>
                <td>${u.access_level}</td>
                <td>${u.is_blocked ? "yes" : "no"}</td>
            `;
            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error(e);
    }
}

function applyEventFilters() {
    const level = document.getElementById("filter-level").value;
    const text = document.getElementById("filter-text").value.toLowerCase();
    const tbody = document.querySelector("#events-table tbody");
    tbody.innerHTML = "";
    for (const ev of eventsCache) {
        if (level && ev.level !== level) continue;
        if (text && !ev.message.toLowerCase().includes(text) && !(ev.reason || "").toLowerCase().includes(text)) continue;
        const ts = new Date(ev.timestamp).toLocaleString();
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${ev.id}</td>
            <td>${ts}</td>
            <td>${ev.level}</td>
            <td>${ev.state}</td>
            <td>${ev.message}</td>
            <td>${ev.card_id ?? "-"}</td>
            <td>${ev.user_id ?? "-"}</td>
            <td>${ev.reason ?? "-"}</td>
        `;
        tbody.appendChild(tr);
    }
}

async function loadEvents() {
    try {
        eventsCache = await fetchJSON("/api/events/?limit=100");
        applyEventFilters();
    } catch (e) {
        console.error(e);
    }
}

async function init() {
    await loadUsers();
    await loadStatus();
    await loadEvents();
    setInterval(loadStatus, 3000);
    setInterval(loadEvents, 5000);

    const levelSelect = document.getElementById("filter-level");
    const textInput = document.getElementById("filter-text");
    if (levelSelect) levelSelect.addEventListener("change", applyEventFilters);
    if (textInput) textInput.addEventListener("input", applyEventFilters);
}

window.addEventListener("DOMContentLoaded", init);
