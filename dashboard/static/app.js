// --- утилиты ---
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

async function api(path) {
  const r = await fetch(path);
  if (r.status === 401) { location.href = "/login"; throw new Error("unauth"); }
  if (!r.ok) throw new Error("api " + r.status);
  return r.json();
}

function fmt(n) {
  if (n === null || n === undefined) return "—";
  if (typeof n !== "number") return n;
  if (Number.isInteger(n)) return n.toLocaleString("ru-RU");
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function timeAgo(dt) {
  if (!dt) return "—";
  return escapeHtml(dt);
}

function blockedTag(v) {
  if (v === 0) return `<span class="tag ok">Активен</span>`;
  if (v === 1) return `<span class="tag err">Заблок</span>`;
  if (v === 2) return `<span class="tag warn">Ушёл из клуба</span>`;
  return `<span class="tag muted">?</span>`;
}

function statusTag(s) {
  if (s === "pending") return `<span class="tag warn">Ожидает</span>`;
  if (s === "approved" || s === "completed") return `<span class="tag ok">${s === "approved" ? "Одобрено" : "Выполнено"}</span>`;
  if (s === "rejected") return `<span class="tag err">Отклонено</span>`;
  if (s === "ignored") return `<span class="tag muted">Пропущено</span>`;
  if (s === "active") return `<span class="tag info">Активно</span>`;
  if (s === "closed") return `<span class="tag muted">Закрыто</span>`;
  return `<span class="tag muted">${escapeHtml(s)}</span>`;
}

function opTag(op) {
  if (op === "add") return `<span class="tag ok">+ add</span>`;
  if (op === "subtract") return `<span class="tag err">− sub</span>`;
  if (op === "set") return `<span class="tag info">= set</span>`;
  return escapeHtml(op);
}

// --- переключение вкладок ---
$$(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".nav-btn").forEach(b => b.classList.remove("active"));
    $$(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
    onTabChange(btn.dataset.tab);
  });
});

function onTabChange(name) {
  if (name === "overview") loadOverview();
  if (name === "users") loadUsers();
  if (name === "transactions") loadTx();
  if (name === "requests") loadReq();
  if (name === "orders") loadOrd();
  if (name === "quests") loadQuests();
  if (name === "logs") initLogs();
}

// --- Overview ---
let chartActivity = null, chartClubs = null, chartRequests = null;

async function loadOverview() {
  const ov = await api("/api/overview");
  const cards = [
    ["Пользователей", ov.users.total, `${ov.users.active} активных`],
    ["Заблокировано", ov.users.blocked_manual + ov.users.blocked_auto,
      `${ov.users.blocked_manual} ручно · ${ov.users.blocked_auto} авто`],
    ["Транзакций сегодня", ov.transactions.today, `Всего ${fmt(ov.transactions.total)}`],
    ["Ожидают заявок", ov.requests.pending, `${ov.orders.pending} заказов`],
    ["Points в системе", fmt(Math.round(ov.points.total)),
      `+${fmt(Math.round(ov.points.added_today))} сегодня`],
    ["Активных квестов", ov.quests.active, `${ov.staff.active} стафф`],
  ];
  $("#ov-cards").innerHTML = cards.map(([l,v,s]) => `
    <div class="card">
      <div class="label">${escapeHtml(l)}</div>
      <div class="value">${fmt(v)}</div>
      <div class="sub">${escapeHtml(s)}</div>
    </div>`).join("");

  const ts = await api("/api/timeseries?days=14");
  const clubs = await api("/api/clubs");
  renderActivity(ts);
  renderRequestsChart(ts);
  renderClubs(clubs);
}

function buildDayRange(days) {
  const arr = [];
  const now = new Date();
  now.setUTCHours(0,0,0,0);
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setUTCDate(d.getUTCDate() - i);
    arr.push(d.toISOString().slice(0, 10));
  }
  return arr;
}

function align(series, days, key) {
  const map = new Map(series.map(r => [r.d, r.c || r[key]]));
  return days.map(d => Number(map.get(d) || 0));
}

function chartTheme() {
  return {
    grid: "#262f3d",
    text: "#8b98a9",
    accent: "#7c5cff",
    accent2: "#5aa9ff",
    ok: "#2ecc71",
    warn: "#f5a524",
    err: "#ef4444",
  };
}

function renderActivity(ts) {
  const days = buildDayRange(14);
  const t = chartTheme();
  const regs = align(ts.registrations, days, "c");
  const tx = align(ts.transactions, days, "c");
  if (chartActivity) chartActivity.destroy();
  chartActivity = new Chart($("#chart-activity"), {
    type: "line",
    data: {
      labels: days,
      datasets: [
        { label: "Регистрации", data: regs, borderColor: t.accent,
          backgroundColor: "rgba(124,92,255,0.15)", tension: 0.35, fill: true },
        { label: "Транзакции", data: tx, borderColor: t.accent2,
          backgroundColor: "rgba(90,169,255,0.10)", tension: 0.35, fill: true },
      ]
    },
    options: chartOpts(),
  });
}

function renderRequestsChart(ts) {
  const days = buildDayRange(14);
  const t = chartTheme();
  const byStatus = { approved: {}, rejected: {}, pending: {} };
  for (const r of ts.requests) {
    if (byStatus[r.status]) byStatus[r.status][r.d] = r.c;
  }
  const toArr = (obj) => days.map(d => Number(obj[d] || 0));
  if (chartRequests) chartRequests.destroy();
  chartRequests = new Chart($("#chart-requests"), {
    type: "bar",
    data: {
      labels: days,
      datasets: [
        { label: "Одобрено", data: toArr(byStatus.approved), backgroundColor: t.ok },
        { label: "Отклонено", data: toArr(byStatus.rejected), backgroundColor: t.err },
        { label: "Ожидают", data: toArr(byStatus.pending), backgroundColor: t.warn },
      ]
    },
    options: {
      ...chartOpts(),
      scales: {
        x: { stacked: true, ticks: { color: t.text }, grid: { color: t.grid } },
        y: { stacked: true, ticks: { color: t.text }, grid: { color: t.grid } },
      }
    }
  });
}

function renderClubs(rows) {
  const t = chartTheme();
  const labels = rows.map(r => r.club || "—");
  const data = rows.map(r => r.c);
  const palette = [t.accent, t.accent2, t.ok, t.warn, t.err, "#c084fc", "#38bdf8"];
  if (chartClubs) chartClubs.destroy();
  chartClubs = new Chart($("#chart-clubs"), {
    type: "doughnut",
    data: { labels, datasets: [{ data, backgroundColor: palette, borderColor: "#151a22" }] },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: t.text, boxWidth: 12 } }
      }
    }
  });
}

function chartOpts() {
  const t = chartTheme();
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: t.text } } },
    scales: {
      x: { ticks: { color: t.text }, grid: { color: t.grid } },
      y: { ticks: { color: t.text }, grid: { color: t.grid } },
    }
  };
}

// --- Users ---
const usersState = { limit: 50, offset: 0, total: 0 };

async function loadUsers() {
  const q = encodeURIComponent($("#users-q").value.trim());
  const blocked = $("#users-blocked").value;
  const order = $("#users-order").value;
  const url = `/api/users?q=${q}&blocked=${blocked}&order=${order}&limit=${usersState.limit}&offset=${usersState.offset}`;
  const data = await api(url);
  usersState.total = data.total;
  $("#users-count").textContent = `Всего: ${fmt(data.total)}`;
  const rows = data.rows.map(u => `
    <tr data-tg="${u.telegram_id}">
      <td class="mono">${u.telegram_id}</td>
      <td>${escapeHtml(u.nickname)}${u.username ? `<div class="dim">@${escapeHtml(u.username)}</div>` : ""}</td>
      <td>${escapeHtml(u.club_name || "—")}<div class="dim mono">${escapeHtml(u.player_tag || "")}</div></td>
      <td><b>${fmt(u.points)}</b></td>
      <td class="mono">${u.tickets_platinum}/${u.tickets_gold}/${u.tickets_silver}/${u.tickets_bronze}</td>
      <td class="mono">${u.tickets_support}/${u.tickets_help}</td>
      <td class="mono">${u.unwarns}/${u.unmutes}</td>
      <td>${blockedTag(u.is_blocked)}</td>
      <td class="dim">${escapeHtml(u.registered_at || "")}</td>
    </tr>
  `).join("");
  $("#users-table tbody").innerHTML = rows || `<tr class="no-hover"><td colspan="9" class="dim" style="padding:20px;text-align:center">Ничего не найдено</td></tr>`;
  $$("#users-table tbody tr[data-tg]").forEach(tr => {
    tr.addEventListener("click", () => openUser(tr.dataset.tg));
  });
  renderPager("#users-pager", usersState, loadUsers);
}

$("#users-q").addEventListener("input", debounce(() => { usersState.offset = 0; loadUsers(); }, 300));
$("#users-blocked").addEventListener("change", () => { usersState.offset = 0; loadUsers(); });
$("#users-order").addEventListener("change", () => { usersState.offset = 0; loadUsers(); });

function renderPager(sel, state, fn) {
  const box = $(sel);
  const total = state.total || 0;
  const cur = Math.floor(state.offset / state.limit) + 1;
  const pages = Math.max(1, Math.ceil(total / state.limit));
  box.innerHTML = `
    <button ${state.offset === 0 ? "disabled" : ""}>‹ Назад</button>
    <span class="info">Стр. ${cur} из ${pages}</span>
    <button ${cur >= pages ? "disabled" : ""}>Вперёд ›</button>
  `;
  const [prev, , next] = box.children;
  prev.addEventListener("click", () => { state.offset = Math.max(0, state.offset - state.limit); fn(); });
  next.addEventListener("click", () => { state.offset += state.limit; fn(); });
}

function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// --- User modal ---
$("#user-modal-close").addEventListener("click", () => $("#user-modal-back").hidden = true);
$("#user-modal-back").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) $("#user-modal-back").hidden = true;
});

async function openUser(tg) {
  const data = await api(`/api/user/${tg}`);
  const u = data.user;
  const c = $("#user-modal-content");
  c.innerHTML = `
    <h2 style="color:var(--text);font-size:18px;margin:0 0 10px">${escapeHtml(u.nickname)}
      ${u.username ? `<span class="dim">@${escapeHtml(u.username)}</span>` : ""}</h2>
    <div class="u-head">
      <div class="kv"><div class="k">Telegram ID</div><div class="v mono">${u.telegram_id}</div></div>
      <div class="kv"><div class="k">Player tag</div><div class="v mono">${escapeHtml(u.player_tag || "—")}</div></div>
      <div class="kv"><div class="k">Клуб</div><div class="v">${escapeHtml(u.club_name || "—")}</div></div>
      <div class="kv"><div class="k">Статус</div><div class="v">${blockedTag(u.is_blocked)}</div></div>
      <div class="kv"><div class="k">Регистрация</div><div class="v">${escapeHtml(u.registered_at || "")}</div></div>
      <div class="kv"><div class="k">Одобрено заявок</div><div class="v">${u.approved_requests}</div></div>
    </div>
    <div class="cards" style="margin-bottom:16px">
      <div class="card"><div class="label">Points</div><div class="value">${fmt(u.points)}</div></div>
      <div class="card"><div class="label">Platinum</div><div class="value">${u.tickets_platinum}</div></div>
      <div class="card"><div class="label">Gold</div><div class="value">${u.tickets_gold}</div></div>
      <div class="card"><div class="label">Silver</div><div class="value">${u.tickets_silver}</div></div>
      <div class="card"><div class="label">Bronze</div><div class="value">${u.tickets_bronze}</div></div>
      <div class="card"><div class="label">Support</div><div class="value">${u.tickets_support}</div></div>
      <div class="card"><div class="label">Help</div><div class="value">${u.tickets_help}</div></div>
      <div class="card"><div class="label">Unwarns / Unmutes</div><div class="value">${u.unwarns} / ${u.unmutes}</div></div>
    </div>
    <h2>Последние транзакции (${data.transactions.length})</h2>
    <div class="panel table-wrap" style="max-height:280px;margin-bottom:14px">
      <table><thead><tr><th>Дата</th><th>Валюта</th><th>Оп.</th><th>Кол-во</th><th>Причина</th><th>Кем</th></tr></thead><tbody>
      ${data.transactions.map(t => `
        <tr class="no-hover"><td class="dim">${escapeHtml(t.created_at)}</td>
        <td class="mono">${escapeHtml(t.currency_type)}</td>
        <td>${opTag(t.operation)}</td>
        <td>${fmt(t.amount)}</td>
        <td>${escapeHtml(t.reason || "")}</td>
        <td class="mono dim">${t.performed_by || "—"}</td></tr>
      `).join("") || `<tr class="no-hover"><td colspan="6" class="dim" style="padding:14px;text-align:center">пусто</td></tr>`}
      </tbody></table>
    </div>
    <h2>Заявки (${data.requests.length})</h2>
    <div class="panel table-wrap" style="max-height:240px">
      <table><thead><tr><th>Дата</th><th>Валюта</th><th>Кол-во</th><th>Причина</th><th>Статус</th></tr></thead><tbody>
      ${data.requests.map(r => `
        <tr class="no-hover"><td class="dim">${escapeHtml(r.created_at)}</td>
        <td class="mono">${escapeHtml(r.currency_type)}</td>
        <td>${fmt(r.amount)}</td>
        <td>${escapeHtml(r.reason || "")}</td>
        <td>${statusTag(r.status)}</td></tr>
      `).join("") || `<tr class="no-hover"><td colspan="5" class="dim" style="padding:14px;text-align:center">пусто</td></tr>`}
      </tbody></table>
    </div>
  `;
  $("#user-modal-back").hidden = false;
}

// --- Transactions ---
const txState = { limit: 100, offset: 0, total: 0 };
async function loadTx() {
  const cur = $("#tx-currency").value;
  const op = $("#tx-op").value;
  const url = `/api/transactions?currency=${cur}&operation=${op}&limit=${txState.limit}&offset=${txState.offset}`;
  const data = await api(url);
  txState.total = data.total;
  $("#tx-count").textContent = `Всего: ${fmt(data.total)}`;
  $("#tx-table tbody").innerHTML = data.rows.map(t => `
    <tr class="no-hover">
      <td class="mono dim">${t.id}</td>
      <td class="dim">${escapeHtml(t.created_at)}</td>
      <td>${escapeHtml(t.nickname || "?")}<div class="dim mono">${t.telegram_id || ""}</div></td>
      <td class="mono">${escapeHtml(t.currency_type)}</td>
      <td>${opTag(t.operation)}</td>
      <td><b>${fmt(t.amount)}</b></td>
      <td class="mono dim">${t.performed_by || "—"}</td>
      <td>${escapeHtml(t.reason || "")}</td>
    </tr>
  `).join("") || `<tr class="no-hover"><td colspan="8" class="dim" style="padding:20px;text-align:center">пусто</td></tr>`;
  renderPager("#tx-pager", txState, loadTx);
}
$("#tx-currency").addEventListener("change", () => { txState.offset = 0; loadTx(); });
$("#tx-op").addEventListener("change", () => { txState.offset = 0; loadTx(); });

// --- Requests ---
const reqState = { limit: 100, offset: 0, total: 0 };
async function loadReq() {
  const st = $("#req-status").value;
  const data = await api(`/api/requests?status=${st}&limit=${reqState.limit}&offset=${reqState.offset}`);
  reqState.total = data.total;
  $("#req-count").textContent = `Всего: ${fmt(data.total)}`;
  $("#req-table tbody").innerHTML = data.rows.map(r => `
    <tr class="no-hover">
      <td class="mono dim">${r.id}</td>
      <td class="dim">${escapeHtml(r.created_at)}</td>
      <td>${escapeHtml(r.nickname || "?")}<div class="dim mono">${r.telegram_id || ""}</div></td>
      <td class="mono">${escapeHtml(r.currency_type)}</td>
      <td><b>${fmt(r.amount)}</b></td>
      <td>${escapeHtml(r.reason || "")}</td>
      <td>${statusTag(r.status)}</td>
      <td class="dim">${escapeHtml(r.reviewed_at || "—")}</td>
    </tr>
  `).join("") || `<tr class="no-hover"><td colspan="8" class="dim" style="padding:20px;text-align:center">пусто</td></tr>`;
  renderPager("#req-pager", reqState, loadReq);
}
$("#req-status").addEventListener("change", () => { reqState.offset = 0; loadReq(); });

// --- Orders ---
const ordState = { limit: 100, offset: 0, total: 0 };
async function loadOrd() {
  const st = $("#ord-status").value;
  const data = await api(`/api/orders?status=${st}&limit=${ordState.limit}&offset=${ordState.offset}`);
  ordState.total = data.total;
  $("#ord-count").textContent = `Всего: ${fmt(data.total)}`;
  $("#ord-table tbody").innerHTML = data.rows.map(o => `
    <tr class="no-hover">
      <td class="mono dim">${o.id}</td>
      <td class="dim">${escapeHtml(o.created_at)}</td>
      <td>${escapeHtml(o.nickname || "?")}<div class="dim mono">${o.telegram_id || ""}</div></td>
      <td class="mono">${escapeHtml(o.order_type)}</td>
      <td>${escapeHtml(o.details || "")}</td>
      <td>${statusTag(o.status)}</td>
      <td class="dim">${escapeHtml(o.completed_at || "—")}</td>
    </tr>
  `).join("") || `<tr class="no-hover"><td colspan="7" class="dim" style="padding:20px;text-align:center">пусто</td></tr>`;
  renderPager("#ord-pager", ordState, loadOrd);
}
$("#ord-status").addEventListener("change", () => { ordState.offset = 0; loadOrd(); });

// --- Quests ---
async function loadQuests() {
  const st = $("#quest-status").value;
  const rows = await api(`/api/quests?status=${st}`);
  $("#quests-list").innerHTML = rows.map(q => `
    <div class="quest-card">
      <h3>${escapeHtml(q.title)}</h3>
      <div class="meta">
        ${statusTag(q.status)} · Награда: <b>${fmt(q.reward_amount)}</b> ${escapeHtml(q.reward_type)}
        ${q.deadline ? `· до ${escapeHtml(q.deadline)}` : ""}
      </div>
      <div class="dim" style="font-size:13px">${escapeHtml(q.description).slice(0, 240)}${q.description.length > 240 ? "…" : ""}</div>
      <div class="stats">
        <span>Взято: <b>${q.taken}</b> / ${q.max_executors}</span>
        <span>Ожидают: <b>${q.pending}</b></span>
        <span>Одобрено: <b>${q.approved}</b></span>
      </div>
    </div>
  `).join("") || `<div class="dim">Нет квестов</div>`;
}
$("#quest-status").addEventListener("change", loadQuests);

// --- Logs ---
let logSource = null;
let logsInited = false;

async function initLogs() {
  if (!logsInited) {
    logsInited = true;
    const days = await api("/api/logs/days");
    const sel = $("#log-day");
    sel.innerHTML = `<option value="">— Сегодня (live) —</option>` +
      days.days.slice().reverse().map(d => `<option value="${d}">${d}</option>`).join("");
    sel.addEventListener("change", refreshLogs);
    $("#log-live").addEventListener("change", refreshLogs);
    $("#log-filter").addEventListener("input", debounce(applyLogFilter, 200));
    $("#log-clear").addEventListener("click", () => { $("#log-view").innerHTML = ""; countLogs(); });
  }
  refreshLogs();
}

function stopLiveStream() {
  if (logSource) { logSource.close(); logSource = null; }
}

async function refreshLogs() {
  stopLiveStream();
  const day = $("#log-day").value;
  const live = $("#log-live").checked;
  const view = $("#log-view");
  view.innerHTML = "";

  if (day) {
    const data = await api(`/api/logs/day/${day}`);
    for (const line of data.lines) view.appendChild(renderLogLine(line));
    scrollLogsBottom();
    countLogs();
    return;
  }

  if (live) {
    logSource = new EventSource("/api/logs/stream");
    logSource.onmessage = (e) => {
      try {
        const { line } = JSON.parse(e.data);
        if (line) {
          const el = renderLogLine(line);
          if (matchesFilter(line)) view.appendChild(el);
          trimLogs();
          scrollLogsBottom();
          countLogs();
        }
      } catch (_) {}
    };
    logSource.onerror = () => { /* авто-реконнект браузером */ };
  } else {
    const data = await api("/api/logs/tail?n=1000");
    for (const line of data.lines) {
      if (matchesFilter(line)) view.appendChild(renderLogLine(line));
    }
    scrollLogsBottom();
    countLogs();
  }
}

function renderLogLine(line) {
  const div = document.createElement("div");
  let lvl = "INFO";
  if (line.includes("| ERROR ")) lvl = "ERROR";
  else if (line.includes("| WARNING ")) lvl = "WARNING";
  else if (line.includes("| DEBUG ")) lvl = "DEBUG";
  if (line.includes("[OWNER:")) lvl = "OWNER";
  div.className = "log-line " + lvl;
  div.textContent = line;
  return div;
}

function trimLogs() {
  const view = $("#log-view");
  const max = 2000;
  while (view.childNodes.length > max) view.removeChild(view.firstChild);
}

function scrollLogsBottom() {
  const v = $("#log-view");
  v.scrollTop = v.scrollHeight;
}

function countLogs() {
  $("#log-count").textContent = `Строк: ${$("#log-view").childNodes.length}`;
}

function matchesFilter(line) {
  const f = $("#log-filter").value.trim();
  if (!f) return true;
  try {
    const re = new RegExp(f, "i");
    return re.test(line);
  } catch (_) {
    return line.toLowerCase().includes(f.toLowerCase());
  }
}

function applyLogFilter() {
  const view = $("#log-view");
  view.childNodes.forEach(n => {
    n.style.display = matchesFilter(n.textContent) ? "" : "none";
  });
}

// --- старт ---
loadOverview();
