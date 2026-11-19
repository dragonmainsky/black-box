const params = new URLSearchParams(location.search);
const token = params.get("token") || sessionStorage.getItem("bb_token") || "";
if (params.has("token")) {
  sessionStorage.setItem("bb_token", token);
  history.replaceState({}, "", "/");
}

const els = {
  status: document.getElementById("status"),
  statusLine: document.getElementById("status-line"),
  statusPill: document.getElementById("status-pill"),
  details: document.getElementById("details"),
  timeline: document.getElementById("timeline"),
  rangeLabel: document.getElementById("range-label"),
  severity: document.getElementById("filter-severity"),
  type: document.getElementById("filter-type"),
  summary: document.getElementById("summary"),
  summaryText: document.getElementById("summary-text"),
  detail: document.getElementById("detail"),
  detailTitle: document.getElementById("detail-title"),
  detailTime: document.getElementById("detail-time"),
  detailNarrative: document.getElementById("detail-narrative"),
  detailEvidence: document.getElementById("detail-evidence"),
};

const state = {
  view: ["day", "week", "month", "year"].includes(params.get("view"))
    ? params.get("view")
    : "day",
  cursor: params.get("date") && !isNaN(new Date(params.get("date")))
    ? new Date(params.get("date"))
    : new Date(),
  timeline: null,
};

const SEVERITY_CLASS = ["high", "medium", "low", "info"];
const MONTHS_TH = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
const DAYS_TH = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."];

function severityClass(severity) {
  return SEVERITY_CLASS.includes(severity) ? severity : "info";
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function rangeFor(view, cursor) {
  if (view === "day") {
    const start = startOfDay(cursor);
    return [start, new Date(start.getTime() + 86400000)];
  }
  if (view === "week") {
    const day = startOfDay(cursor);
    const monday = new Date(day);
    monday.setDate(day.getDate() - ((day.getDay() + 6) % 7));
    return [monday, new Date(monday.getTime() + 7 * 86400000)];
  }
  if (view === "month") {
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    return [start, new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1)];
  }
  const start = new Date(cursor.getFullYear(), 0, 1);
  return [start, new Date(cursor.getFullYear() + 1, 0, 1)];
}

function bucketFor(view) {
  if (view === "year") return "month";
  if (view === "month") return "day";
  return "hour";
}

function dateKey(date) {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

function monthKey(date) {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  return `${date.getFullYear()}-${m}`;
}

function fmtDateTime(ts) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("th-TH", {
    dateStyle: "medium", timeStyle: "short",
  });
}

function fmtRange(start, end) {
  return `${fmtDateTime(start)} – ${fmtDateTime(end)}`;
}

async function api(path, options = {}) {
  const headers = { "X-API-Token": token, ...(options.headers || {}) };
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function loadStatus() {
  try {
    const data = await api("/api/status");
    els.status.textContent = data.status_text;
    els.status.className = "status " + severityClass(data.status);
    els.statusPill.textContent = data.status_text;
    els.statusPill.className = "pill " + data.status;
    els.statusLine.textContent = data.last_cycle
      ? "ตรวจล่าสุด: " + fmtDateTime(data.last_cycle)
      : "ยังไม่มีข้อมูล";
    const parts = [];
    if (data.interface) parts.push("Interface: " + data.interface);
    if (data.gateway) parts.push("Gateway: " + data.gateway);
    if (data.public_ip) parts.push("Public IP: " + data.public_ip);
    if (data.device_count) parts.push("อุปกรณ์: " + data.device_count);
    els.details.textContent = parts.join(" · ");
  } catch (error) {
    els.status.textContent = "เชื่อมต่อไม่ได้";
    els.status.className = "status critical";
    els.details.textContent = String(error);
  }
}

async function loadTimeline() {
  const [start, end] = rangeFor(state.view, state.cursor);
  const query = new URLSearchParams({
    start: start.toISOString(),
    end: end.toISOString(),
    bucket: bucketFor(state.view),
  });
  if (els.severity.value) query.set("severity", els.severity.value);
  if (els.type.value) query.set("type", els.type.value);

  try {
    state.timeline = await api("/api/timeline?" + query);
    render();
  } catch (error) {
    els.timeline.textContent = "โหลด timeline ไม่ได้: " + error;
  }
}

function render() {
  const data = state.timeline;
  if (!data) return;
  const start = new Date(data.start);
  const end = new Date(data.end);

  if (state.view === "day") {
    els.rangeLabel.textContent = start.toLocaleDateString("th-TH", {
      dateStyle: "full",
    });
  } else if (state.view === "week") {
    els.rangeLabel.textContent = `${start.toLocaleDateString("th-TH")} – ${end.toLocaleDateString("th-TH")}`;
  } else if (state.view === "month") {
    els.rangeLabel.textContent = `${MONTHS_TH[start.getMonth()]} ${start.getFullYear()}`;
  } else {
    els.rangeLabel.textContent = String(start.getFullYear());
  }

  if (state.view === "day") renderDay(data);
  else if (state.view === "week") renderWeek(data);
  else if (state.view === "month") renderMonth(data);
  else renderYear(data);
}

function renderDay(data) {
  const start = new Date(data.start);
  const end = new Date(data.end);
  const total = end - start;
  els.timeline.innerHTML = "";

  const grid = document.createElement("div");
  grid.className = "day-grid";

  for (let hour = 0; hour < 24; hour += 3) {
    const label = document.createElement("span");
    label.className = "hour-label";
    label.style.left = (hour / 24 * 100) + "%";
    label.textContent = `${String(hour).padStart(2, "0")}:00`;
    grid.appendChild(label);
  }

  const laneEnds = [];
  for (const event of data.events) {
    const eventStart = new Date(event.ts_start);
    const eventEnd = event.ts_end
      ? new Date(event.ts_end)
      : new Date(Math.min(end, eventStart.getTime() + 5 * 60000));
    const clampedStart = Math.max(start, eventStart);
    const clampedEnd = Math.min(end, eventEnd);
    if (clampedEnd <= start || clampedStart >= end) continue;

    let lane = laneEnds.findIndex((laneEnd) => laneEnd <= clampedStart);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(clampedEnd);
    } else {
      laneEnds[lane] = clampedEnd;
    }

    const block = document.createElement("div");
    block.className = "event-block " + severityClass(event.severity);
    block.style.left = ((clampedStart - start) / total * 100) + "%";
    block.style.width = Math.max(0.6, (clampedEnd - clampedStart) / total * 100) + "%";
    block.style.top = (30 + lane * 30) + "px";
    block.textContent = event.title || event.type;
    block.title = event.narrative || event.title || event.type;
    block.addEventListener("click", () => showDetail(event));
    grid.appendChild(block);
  }

  grid.style.height = Math.max(280, laneEnds.length * 30 + 60) + "px";
  attachRangeSelection(grid, start, end);
  els.timeline.appendChild(grid);
}

function attachRangeSelection(grid, start, end) {
  let downX = null;
  let overlay = null;
  let moveHandler = null;

  grid.addEventListener("mousedown", (event) => {
    if (event.target.closest(".event-block")) return;
    const rect = grid.getBoundingClientRect();
    downX = event.clientX;
    overlay = document.createElement("div");
    overlay.className = "selection";
    grid.appendChild(overlay);

    const move = (moveEvent) => {
      const left = Math.min(downX, moveEvent.clientX) - rect.left;
      const right = Math.max(downX, moveEvent.clientX) - rect.left;
      overlay.style.left = Math.max(0, left) + "px";
      overlay.style.width = Math.max(0, Math.min(rect.width, right) - Math.max(0, left)) + "px";
    };
    moveHandler = move;
    window.addEventListener("mousemove", move);

    const up = (upEvent) => {
      window.removeEventListener("mousemove", moveHandler);
      if (!overlay) return;
      const left = Math.min(downX, upEvent.clientX) - rect.left;
      const right = Math.max(downX, upEvent.clientX) - rect.left;
      const width = Math.min(rect.width, right) - Math.max(0, left);
      overlay.remove();
      overlay = null;
      if (width < 4) return;

      const ratioStart = Math.max(0, left) / rect.width;
      const ratioEnd = Math.min(rect.width, right) / rect.width;
      const rangeStart = new Date(start.getTime() + ratioStart * (end - start));
      const rangeEnd = new Date(start.getTime() + ratioEnd * (end - start));
      showSummary(rangeStart, rangeEnd);
    };
    window.addEventListener("mouseup", up, { once: true });
  });
}

function renderWeek(data) {
  const start = new Date(data.start);
  els.timeline.innerHTML = "";
  const bucketMap = new Map();
  for (const bucket of data.buckets) {
    const date = new Date(bucket.start);
    bucketMap.set(dateKey(date) + ":" + date.getHours(), bucket);
  }

  const wrapper = document.createElement("div");
  wrapper.className = "week-grid";
  for (let dayIndex = 0; dayIndex < 7; dayIndex++) {
    const day = new Date(start.getTime() + dayIndex * 86400000);
    const row = document.createElement("div");
    row.className = "week-day";
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = DAYS_TH[dayIndex] + " " + day.getDate();
    row.appendChild(label);

    for (let hour = 0; hour < 24; hour++) {
      const cell = document.createElement("div");
      const bucket = bucketMap.get(dateKey(day) + ":" + hour);
      cell.className = "cell " + (bucket && bucket.max_severity
        ? severityClass(bucket.max_severity) : "");
      cell.title = `${dateKey(day)} ${String(hour).padStart(2, "0")}:00` +
        (bucket ? ` · ${bucket.event_count} เหตุการณ์` : "");
      cell.addEventListener("click", () => {
        state.cursor = new Date(day);
        setView("day");
      });
      row.appendChild(cell);
    }
    wrapper.appendChild(row);
  }
  els.timeline.appendChild(wrapper);
}

function renderMonth(data) {
  const start = new Date(data.start);
  els.timeline.innerHTML = "";
  const bucketMap = new Map();
  for (const bucket of data.buckets) {
    bucketMap.set(dateKey(new Date(bucket.start)), bucket);
  }

  const grid = document.createElement("div");
  grid.className = "month-grid";
  for (const name of DAYS_TH) {
    const head = document.createElement("div");
    head.className = "month-head";
    head.textContent = name;
    grid.appendChild(head);
  }

  const first = new Date(start.getFullYear(), start.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - offset);

  for (let index = 0; index < 42; index++) {
    const day = new Date(gridStart);
    day.setDate(gridStart.getDate() + index);
    const cell = document.createElement("div");
    const inMonth = day.getMonth() === start.getMonth();
    const bucket = bucketMap.get(dateKey(day));
    cell.className = "month-cell" +
      (inMonth ? "" : " empty") +
      (bucket && bucket.max_severity ? " " + severityClass(bucket.max_severity) : "");
    cell.innerHTML = `<div class="day">${day.getDate()}</div>`;
    if (bucket) {
      const info = document.createElement("div");
      info.className = "muted";
      info.textContent = `${bucket.event_count} เหตุการณ์`;
      cell.appendChild(info);
    }
    if (inMonth) {
      cell.addEventListener("click", () => {
        state.cursor = new Date(day);
        setView("day");
      });
    }
    grid.appendChild(cell);
  }
  els.timeline.appendChild(grid);
}

function renderYear(data) {
  const start = new Date(data.start);
  els.timeline.innerHTML = "";
  const bucketMap = new Map();
  for (const bucket of data.buckets) {
    bucketMap.set(monthKey(new Date(bucket.start)), bucket);
  }

  const grid = document.createElement("div");
  grid.className = "year-grid";
  for (let month = 0; month < 12; month++) {
    const key = `${start.getFullYear()}-${String(month + 1).padStart(2, "0")}`;
    const bucket = bucketMap.get(key);
    const cell = document.createElement("div");
    cell.className = "year-cell" +
      (bucket && bucket.max_severity ? " " + severityClass(bucket.max_severity) : "");
    cell.innerHTML = `<strong>${MONTHS_TH[month]}</strong>`;
    if (bucket) {
      const info = document.createElement("div");
      info.className = "muted";
      info.textContent = `${bucket.event_count} เหตุการณ์`;
      cell.appendChild(info);
    }
    cell.addEventListener("click", () => {
      state.cursor = new Date(start.getFullYear(), month, 1);
      setView("month");
    });
    grid.appendChild(cell);
  }
  els.timeline.appendChild(grid);
}

function showDetail(event) {
  els.detail.hidden = false;
  els.detailTitle.textContent = event.title || event.type;
  els.detailTime.textContent = event.ts_end
    ? fmtRange(event.ts_start, event.ts_end)
    : "เริ่ม " + fmtDateTime(event.ts_start) + " · กำลังเกิด";
  els.detailNarrative.textContent = event.narrative || event.details || "";
  els.detailEvidence.textContent = JSON.stringify(event.evidence || {}, null, 2);
}

async function showSummary(start, end) {
  els.summary.hidden = false;
  els.summaryText.textContent = "กำลังสรุป...";
  try {
    const query = new URLSearchParams({
      start: start.toISOString(),
      end: end.toISOString(),
    });
    const data = await api("/api/summary?" + query);
    els.summaryText.textContent = data.text;
  } catch (error) {
    els.summaryText.textContent = "สรุปไม่ได้: " + error;
  }
}

function setView(view) {
  state.view = view;
  syncTabs();
  loadTimeline();
}

function syncTabs() {
  for (const button of document.querySelectorAll(".tabs button")) {
    button.classList.toggle("active", button.dataset.view === state.view);
  }
}

async function loadSettings() {
  try {
    const data = await api("/api/settings");
    document.getElementById("interval").value = data.base_interval_s;
    document.getElementById("retention").value = data.retention_days;
    document.getElementById("public-ip").checked = data.public_ip_enabled;
  } catch (error) {
    document.getElementById("save-status").textContent = String(error);
  }
}

async function saveSettings() {
  const status = document.getElementById("save-status");
  status.textContent = "กำลังบันทึก...";
  try {
    const data = await api("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_interval_s: Number(document.getElementById("interval").value),
        retention_days: Number(document.getElementById("retention").value),
        public_ip_enabled: document.getElementById("public-ip").checked,
      }),
    });
    status.textContent = "บันทึกแล้ว";
    els.statusLine.textContent = "ตรวจทุก " + data.base_interval_s + " วินาที";
  } catch (error) {
    status.textContent = "บันทึกไม่ได้: " + error;
  }
}

document.querySelectorAll(".tabs button").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});
els.severity.addEventListener("change", loadTimeline);
els.type.addEventListener("change", loadTimeline);
document.getElementById("prev").addEventListener("click", () => {
  if (state.view === "day") state.cursor.setDate(state.cursor.getDate() - 1);
  else if (state.view === "week") state.cursor.setDate(state.cursor.getDate() - 7);
  else if (state.view === "month") state.cursor.setMonth(state.cursor.getMonth() - 1);
  else state.cursor.setFullYear(state.cursor.getFullYear() - 1);
  loadTimeline();
});
document.getElementById("next").addEventListener("click", () => {
  if (state.view === "day") state.cursor.setDate(state.cursor.getDate() + 1);
  else if (state.view === "week") state.cursor.setDate(state.cursor.getDate() + 7);
  else if (state.view === "month") state.cursor.setMonth(state.cursor.getMonth() + 1);
  else state.cursor.setFullYear(state.cursor.getFullYear() + 1);
  loadTimeline();
});
document.getElementById("today").addEventListener("click", () => {
  state.cursor = new Date();
  loadTimeline();
});
document.getElementById("detail-close").addEventListener("click", () => {
  els.detail.hidden = true;
});
document.getElementById("summary-close").addEventListener("click", () => {
  els.summary.hidden = true;
});
document.getElementById("save-settings").addEventListener("click", saveSettings);

if (!token) {
  els.status.textContent = "กรุณาเปิดจาก tray";
  els.status.className = "status warning";
  els.details.textContent = "เปิดแอปจาก tray แล้วเลือก 'เปิดหน้าต่าง'";
} else {
  syncTabs();
  loadStatus();
  loadTimeline();
  loadSettings();
  setInterval(loadStatus, 15000);
  setInterval(loadTimeline, 30000);
}
