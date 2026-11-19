"use strict";

const params = new URLSearchParams(location.search);
const urlToken = params.get("token") || "";

function readSession(key) {
  try {
    return sessionStorage.getItem(key) || "";
  } catch (_error) {
    return "";
  }
}

function writeSession(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch (_error) {
    // sessionStorage may be disabled; the URL token still works for this load.
  }
}

const token = urlToken || readSession("bb_token");
if (urlToken) {
  writeSession("bb_token", urlToken);
  params.delete("token");
  const rest = params.toString();
  history.replaceState(
    {},
    "",
    location.pathname + (rest ? "?" + rest : "") + location.hash
  );
}

const $ = (id) => document.getElementById(id);
const els = {
  headerState: $("header-state"),
  statusPill: $("status-pill"),
  statusLine: $("status-line"),
  statusBadge: $("status-badge"),
  statusText: $("status-text"),
  statusSub: $("status-sub"),
  statusFacts: $("status-facts"),
  openEvents: $("open-events"),
  openCount: $("open-count"),
  severity: $("filter-severity"),
  type: $("filter-type"),
  clearFilters: $("clear-filters"),
  timeline: $("timeline"),
  timelineEvents: $("timeline-events"),
  timelineEventsList: $("timeline-events-list"),
  timelineEventsCount: $("timeline-events-count"),
  rangeLabel: $("range-label"),
  eventCount: $("event-count"),
  timelineHint: $("timeline-hint"),
  prev: $("prev"),
  next: $("next"),
  today: $("today"),
  summarizeRange: $("summarize-range"),
  summary: $("summary"),
  summaryRange: $("summary-range"),
  summaryText: $("summary-text"),
  summaryClose: $("summary-close"),
  detail: $("detail"),
  detailSeverity: $("detail-severity"),
  detailTitle: $("detail-title"),
  detailTime: $("detail-time"),
  detailNarrative: $("detail-narrative"),
  detailDetails: $("detail-details"),
  detailMeta: $("detail-meta"),
  detailEvidence: $("detail-evidence"),
  detailClose: $("detail-close"),
  drawerScrim: $("drawer-scrim"),
  interval: $("interval"),
  retention: $("retention"),
  publicIp: $("public-ip"),
  publicIpHelp: $("public-ip-help"),
  saveSettings: $("save-settings"),
  saveStatus: $("save-status"),
  quitApp: $("quit-app"),
  quitStatus: $("quit-status"),
  footState: $("foot-state"),
  bootNotice: $("boot-notice"),
  noticeTitle: $("notice-title"),
  noticeMessage: $("notice-message"),
  noticeAction: $("notice-action"),
};

const VIEWS = ["day", "week", "month", "year"];
const SEVERITY_RANK = { info: 0, low: 1, medium: 2, high: 3 };
const SEVERITY_LABELS = {
  high: "สูง",
  medium: "กลาง",
  low: "ต่ำ",
  info: "ข้อมูล",
};
const TYPE_LABELS = {
  gateway_down: "เราเตอร์ไม่ตอบ",
  internet_down: "อินเทอร์เน็ตล่ม",
  dns_fail: "DNS ล้มเหลว",
  dns_slow: "DNS ช้า",
  packet_loss: "แพ็กเก็ตหาย",
  wifi_drop: "ไวไฟหลุด",
  latency_spike: "ความหน่วงสูง",
  new_device: "พบอุปกรณ์ใหม่",
  public_ip_change: "ไอพีสาธารณะเปลี่ยน",
  interface_change: "การเชื่อมต่อเปลี่ยน",
  monitor_gap: "ระบบหยุดบันทึก",
};
const MONTHS_TH = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];
const DAYS_TH = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."];

const DATE_TIME = new Intl.DateTimeFormat("th-TH", {
  dateStyle: "medium",
  timeStyle: "short",
});
const TIME = new Intl.DateTimeFormat("th-TH", {
  hour: "2-digit",
  minute: "2-digit",
});
const DAY_LABEL = new Intl.DateTimeFormat("th-TH", {
  weekday: "short",
  day: "numeric",
  month: "short",
});
const FULL_DATE = new Intl.DateTimeFormat("th-TH", { dateStyle: "full" });
const MONTH_YEAR = new Intl.DateTimeFormat("th-TH", {
  month: "long",
  year: "numeric",
});
const YEAR_LABEL = new Intl.DateTimeFormat("th-TH", { year: "numeric" });

const state = {
  view: VIEWS.includes(params.get("view")) ? params.get("view") : "day",
  cursor: parseDateParam(params.get("date")) || new Date(),
  data: null,
  range: null,
  request: null,
  summaryRequest: null,
  timers: [],
  tokenError: false,
  lastFocused: null,
  saveTimer: null,
};

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function parseDateParam(value) {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date, days) {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function rangeFor(view, cursor) {
  if (view === "day") {
    const start = startOfDay(cursor);
    return [start, addDays(start, 1)];
  }
  if (view === "week") {
    const day = startOfDay(cursor);
    const monday = addDays(day, -((day.getDay() + 6) % 7));
    return [monday, addDays(monday, 7)];
  }
  if (view === "month") {
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    return [start, new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1)];
  }
  const start = new Date(cursor.getFullYear(), 0, 1);
  return [start, new Date(cursor.getFullYear() + 1, 0, 1)];
}

function dateKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function isSameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function isSameMonth(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}

function severityClass(value) {
  return Object.prototype.hasOwnProperty.call(SEVERITY_RANK, value) ? value : "info";
}

function typeLabel(value) {
  return TYPE_LABELS[value] || value || "ไม่ทราบประเภท";
}

function toDate(value) {
  if (value instanceof Date) return value;
  return new Date(value);
}

function fmtDateTime(value) {
  const date = toDate(value);
  return Number.isNaN(date.getTime()) ? "—" : DATE_TIME.format(date);
}

function fmtTime(value) {
  const date = toDate(value);
  return Number.isNaN(date.getTime()) ? "—" : TIME.format(date);
}

function fmtDayLabel(value) {
  const date = toDate(value);
  return Number.isNaN(date.getTime()) ? "—" : DAY_LABEL.format(date);
}

function fmtDuration(start, end) {
  const startMs = toDate(start).getTime();
  const endMs = toDate(end).getTime();
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) return "—";
  const minutes = Math.max(0, Math.round((endMs - startMs) / 60000));
  if (minutes < 1) return "น้อยกว่า 1 นาที";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} นาที`;
  return rest ? `${hours} ชม. ${rest} นาที` : `${hours} ชม.`;
}

function icon(name, className = "icon") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#" + name);
  svg.appendChild(use);
  return svg;
}

function factRow(label, value) {
  const row = document.createElement("div");
  row.className = "fact";
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = value;
  row.append(term, detail);
  return row;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-API-Token", token);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const text = await response.text();
      if (text) {
        try {
          const parsed = JSON.parse(text);
          message = parsed.detail || parsed.message || text;
        } catch (_error) {
          message = text;
        }
      }
    } catch (_error) {
      // Keep the status-based message.
    }
    throw new ApiError(String(message).slice(0, 300), response.status);
  }

  if (response.status === 204) return null;
  return response.json();
}

function showNotice(title, message, actionLabel = "", action = null) {
  els.noticeTitle.textContent = title;
  els.noticeMessage.textContent = message;
  if (actionLabel && action) {
    els.noticeAction.hidden = false;
    els.noticeAction.textContent = actionLabel;
    els.noticeAction.onclick = action;
  } else {
    els.noticeAction.hidden = true;
    els.noticeAction.onclick = null;
  }
  els.bootNotice.hidden = false;
}

function showNoToken() {
  els.headerState.dataset.status = "unknown";
  els.statusPill.textContent = "ยังไม่ได้เชื่อมต่อ";
  els.statusLine.textContent = "—";
  els.statusText.textContent = "ยังไม่ได้เชื่อมต่อ";
  els.statusText.className = "status-text unknown";
  els.statusBadge.textContent = "ยังไม่เชื่อมต่อ";
  els.statusBadge.className = "status-badge";
  els.statusSub.textContent = "เปิดจาก tray เพื่อเชื่อมต่อ";
  els.statusFacts.replaceChildren();
  els.openEvents.replaceChildren();
  els.openCount.textContent = "";
  showNotice(
    "ต้องเปิดจาก tray",
    "เปิด Home Network Black Box จาก tray หรือเมนู Start แล้วเลือก “เปิดหน้าต่าง” เพื่อเชื่อมต่อกับโปรแกรม"
  );
}

function showTokenError() {
  if (state.tokenError) return;
  state.tokenError = true;
  stopPolling();
  els.headerState.dataset.status = "critical";
  els.statusPill.textContent = "รหัสไม่ถูกต้อง";
  els.statusLine.textContent = "—";
  els.statusText.textContent = "เชื่อมต่อไม่ได้";
  els.statusText.className = "status-text critical";
  els.statusSub.textContent = "รหัสเชื่อมต่อหมดอายุหรือไม่ตรงกับโปรแกรม";
  showNotice(
    "รหัสเชื่อมต่อไม่ถูกต้อง",
    "ปิดแท็บนี้ แล้วเปิด Home Network Black Box จาก tray อีกครั้ง เพื่อรับรหัสใหม่"
  );
}

function stopPolling() {
  for (const timer of state.timers) clearInterval(timer);
  state.timers = [];
}

function startPolling() {
  stopPolling();
  state.timers.push(
    setInterval(() => {
      if (!document.hidden && !state.tokenError) loadStatus();
    }, 15000)
  );
  state.timers.push(
    setInterval(() => {
      if (!document.hidden && !state.tokenError) loadTimeline();
    }, 30000)
  );
}

async function loadStatus() {
  if (!token || state.tokenError) return;
  try {
    const data = await api("/api/status");
    renderStatus(data);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showTokenError();
      return;
    }
    els.headerState.dataset.status = "unknown";
    els.statusPill.textContent = "เชื่อมต่อไม่ได้";
    els.statusLine.textContent = "—";
    els.statusText.textContent = "เชื่อมต่อไม่ได้";
    els.statusText.className = "status-text unknown";
    els.statusBadge.textContent = "ออฟไลน์";
    els.statusBadge.className = "status-badge";
    els.statusSub.textContent = "โปรแกรมไม่ตอบสนอง — กำลังลองใหม่";
  }
}

function renderStatus(data) {
  const status = ["ok", "warning", "critical", "info"].includes(data.status)
    ? data.status
    : "unknown";
  const statusText = data.status_text || "ไม่ทราบสถานะ";
  els.headerState.dataset.status = status;
  els.statusPill.textContent = statusText;
  els.statusLine.textContent = data.last_cycle
    ? `ตรวจล่าสุด ${fmtDateTime(data.last_cycle)}`
    : "ยังไม่มีการตรวจ";
  els.statusText.textContent = statusText;
  els.statusText.className = "status-text " + status;
  els.statusBadge.textContent = statusText;
  els.statusBadge.className = "status-badge" + (status === "unknown" ? "" : " " + status);
  els.statusSub.textContent = data.last_cycle
    ? `ตรวจล่าสุด ${fmtDateTime(data.last_cycle)}`
    : "ยังไม่มีรอบตรวจ";

  const facts = [
    ["เชื่อมต่อผ่าน", data.interface || "—"],
    ["เราเตอร์", data.gateway || "—"],
    ["ไอพีสาธารณะ", data.public_ip || "ไม่ได้เก็บ"],
    [
      "อุปกรณ์ในบ้าน",
      typeof data.device_count === "number" ? `${data.device_count} เครื่อง` : "—",
    ],
  ];
  els.statusFacts.replaceChildren(
    ...facts.map(([label, value]) => factRow(label, value))
  );

  const openEvents = Array.isArray(data.open_events) ? data.open_events : [];
  els.openCount.textContent = openEvents.length ? `${openEvents.length} รายการ` : "";
  els.openEvents.replaceChildren();

  if (!openEvents.length) {
    const empty = document.createElement("p");
    empty.className = "empty-inline";
    empty.textContent = "ไม่มีเหตุการณ์ที่กำลังเกิด";
    els.openEvents.appendChild(empty);
    return;
  }

  for (const event of openEvents) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "event-row";
    button.title = event.title || typeLabel(event.type);

    const dot = document.createElement("i");
    dot.className = "dot " + severityClass(event.severity);
    dot.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.className = "event-row-text";
    const title = document.createElement("span");
    title.className = "event-row-title";
    title.textContent = event.title || typeLabel(event.type);
    const time = document.createElement("span");
    time.className = "event-row-time";
    time.textContent = `เริ่ม ${fmtDateTime(event.ts_start)}`;
    text.append(title, time);
    button.append(dot, text);
    button.addEventListener("click", () => showDetail(event));
    els.openEvents.appendChild(button);
  }
}

function bucketFor(view) {
  if (view === "year") return "month";
  if (view === "month") return "day";
  return "hour";
}

async function loadTimeline() {
  if (!token || state.tokenError) return;

  const [start, end] = rangeFor(state.view, state.cursor);
  const query = new URLSearchParams({
    start: start.toISOString(),
    end: end.toISOString(),
    bucket: bucketFor(state.view),
  });
  if (els.severity.value) query.set("severity", els.severity.value);
  if (els.type.value) query.set("type", els.type.value);

  if (state.request) state.request.abort();
  const controller = new AbortController();
  state.request = controller;
  els.timeline.classList.add("is-loading");

  try {
    const data = await api("/api/timeline?" + query.toString(), {
      signal: controller.signal,
    });
    if (controller.signal.aborted) return;
    state.data = data;
    state.range = [new Date(data.start), new Date(data.end)];
    render();
  } catch (error) {
    if (error.name === "AbortError") return;
    if (error instanceof ApiError && error.status === 401) {
      showTokenError();
      return;
    }
    renderTimelineError(error);
  } finally {
    if (state.request === controller) {
      state.request = null;
      els.timeline.classList.remove("is-loading");
    }
  }
}

function renderTimelineError(error) {
  const box = document.createElement("div");
  box.className = "timeline-error";
  const title = document.createElement("strong");
  title.textContent = "โหลดไทม์ไลน์ไม่ได้";
  const detail = document.createElement("span");
  detail.textContent =
    error instanceof ApiError
      ? error.message
      : "โปรแกรมไม่ตอบสนอง — ตรวจว่าโปรแกรมยังทำงานอยู่";
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "button small";
  retry.append(icon("i-refresh"), document.createTextNode("ลองอีกครั้ง"));
  retry.addEventListener("click", loadTimeline);
  box.append(title, detail, retry);
  els.timeline.replaceChildren(box);
  els.eventCount.textContent = "—";
}

function render() {
  const data = state.data;
  if (!data) return;

  const start = new Date(data.start);
  const end = new Date(data.end);
  const events = Array.isArray(data.events) ? data.events : [];

  if (state.view === "day") {
    els.rangeLabel.textContent = FULL_DATE.format(start);
  } else if (state.view === "week") {
    const last = new Date(end.getTime() - 1);
    const yearText =
      start.getFullYear() === last.getFullYear()
        ? YEAR_LABEL.format(start)
        : `${YEAR_LABEL.format(start)} – ${YEAR_LABEL.format(last)}`;
    els.rangeLabel.textContent = `${fmtDayLabel(start)} – ${fmtDayLabel(last)} ${yearText}`;
  } else if (state.view === "month") {
    els.rangeLabel.textContent = MONTH_YEAR.format(start);
  } else {
    els.rangeLabel.textContent = YEAR_LABEL.format(start);
  }

  els.eventCount.textContent = `${events.length} เหตุการณ์`;
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;
  els.timelineHint.textContent =
    state.view === "day"
      ? coarsePointer
        ? "ปัดเพื่อเลื่อนเวลา · ใช้ “สรุปทั้งช่วง” เพื่อสรุป"
        : "ลากบนเส้นเวลาเพื่อสรุปช่วงที่เลือก"
      : "กด “สรุปทั้งช่วง” เพื่อสรุปช่วงที่แสดงอยู่";

  syncTabs();
  syncUrl();

  if (state.view === "day") renderDay(events, start, end);
  else if (state.view === "week") renderWeek(events, start);
  else if (state.view === "month") renderMonth(events, start);
  else renderYear(events, start);

  renderEventList(events);
}

function renderEventList(events) {
  if (!events.length) {
    els.timelineEvents.hidden = true;
    els.timelineEventsList.replaceChildren();
    els.timelineEventsCount.textContent = "";
    return;
  }

  const ordered = events.slice().sort((a, b) => {
    const diff = new Date(a.ts_start) - new Date(b.ts_start);
    return state.view === "day" ? diff : -diff;
  });
  const shown = ordered.slice(0, 8);
  els.timelineEvents.hidden = false;
  els.timelineEventsCount.textContent = `${events.length} รายการ`;
  els.timelineEventsList.replaceChildren();

  for (const event of shown) {
    const start = new Date(event.ts_start);
    const end = event.ts_end ? new Date(event.ts_end) : null;
    const row = document.createElement("button");
    row.type = "button";
    row.className = "timeline-event";

    const dot = document.createElement("i");
    dot.className = "dot " + severityClass(event.severity);
    dot.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.className = "timeline-event-text";
    const title = document.createElement("span");
    title.className = "timeline-event-title";
    title.textContent = event.title || typeLabel(event.type);
    const meta = document.createElement("span");
    meta.className = "timeline-event-meta";
    const prefix = state.view === "day" ? "" : `${fmtDayLabel(start)} `;
    const range = end
      ? `${fmtTime(start)}–${fmtTime(end)}`
      : `${fmtTime(start)}–กำลังเกิด`;
    meta.textContent = `${prefix}${range} · ${typeLabel(event.type)}`;
    text.append(title, meta);

    row.title = title.textContent;
    row.append(dot, text);
    row.addEventListener("click", () => showDetail(event));
    els.timelineEventsList.appendChild(row);
  }

  if (ordered.length > shown.length) {
    const more = document.createElement("p");
    more.className = "timeline-event-more";
    more.textContent = `อีก ${ordered.length - shown.length} เหตุการณ์ — ใช้ตัวกรองหรือเปลี่ยนช่วงเวลา`;
    els.timelineEventsList.appendChild(more);
  }
}

function syncTabs() {
  for (const button of document.querySelectorAll("[data-view]")) {
    const active = button.dataset.view === state.view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function syncUrl() {
  const next = new URLSearchParams();
  if (state.view !== "day") next.set("view", state.view);
  if (!isSameDay(state.cursor, new Date())) next.set("date", dateKey(state.cursor));
  const query = next.toString();
  history.replaceState({}, "", location.pathname + (query ? "?" + query : ""));
}

function eventWindow(event, start, end, now) {
  const rawStart = new Date(event.ts_start);
  if (Number.isNaN(rawStart.getTime())) return null;

  let rawEnd;
  if (event.ts_end) {
    rawEnd = new Date(event.ts_end);
  } else {
    const minimum = new Date(rawStart.getTime() + 5 * 60000);
    rawEnd = new Date(Math.max(now.getTime(), minimum.getTime()));
  }
  if (Number.isNaN(rawEnd.getTime()) || rawEnd <= rawStart) {
    rawEnd = new Date(rawStart.getTime() + 60000);
  }

  const windowStart = new Date(Math.max(rawStart.getTime(), start.getTime()));
  const windowEnd = new Date(Math.min(rawEnd.getTime(), end.getTime()));
  if (windowEnd <= windowStart) return null;
  return { start: windowStart, end: windowEnd, open: !event.ts_end };
}

function renderDay(events, start, end) {
  const now = new Date();
  const total = end - start;
  const trackTop = 14;
  const laneHeight = 30;

  const scroll = document.createElement("div");
  scroll.className = "timeline-scroll";
  const inner = document.createElement("div");
  inner.className = "day-inner";

  const ruler = document.createElement("div");
  ruler.className = "day-ruler";
  for (let hour = 0; hour <= 24; hour += 3) {
    const label = document.createElement("span");
    label.style.left = `${(hour / 24) * 100}%`;
    label.textContent = `${String(hour).padStart(2, "0")}:00`;
    if (hour === 24) label.classList.add("end");
    ruler.appendChild(label);
  }

  const track = document.createElement("div");
  track.className = "day-track";

  const windows = [];
  for (const event of events) {
    const window = eventWindow(event, start, end, now);
    if (window) windows.push({ event, window });
  }
  windows.sort((a, b) => a.window.start - b.window.start || b.window.end - a.window.end);

  const laneEnds = [];
  let laneCount = 0;
  for (const item of windows) {
    let lane = laneEnds.findIndex((laneEnd) => laneEnd <= item.window.start.getTime());
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(item.window.end.getTime());
    } else {
      laneEnds[lane] = item.window.end.getTime();
    }
    laneCount = Math.max(laneCount, lane + 1);

    const left = ((item.window.start - start) / total) * 100;
    const right = ((item.window.end - start) / total) * 100;
    const width = Math.min(100 - left, Math.max(0.8, right - left));
    const severity = severityClass(item.event.severity);
    const block = document.createElement("button");
    block.type = "button";
    block.className = `event-block ${severity}${item.window.open ? " is-open" : ""}`;
    block.style.left = `${left}%`;
    block.style.width = `${width}%`;
    block.style.top = `${trackTop + lane * laneHeight}px`;
    block.title =
      `${item.event.title || typeLabel(item.event.type)} · ` +
      `${fmtTime(item.window.start)}–` +
      `${item.window.open ? "กำลังเกิด" : fmtTime(item.window.end)}`;
    block.setAttribute(
      "aria-label",
      `${block.title} · ระดับ${SEVERITY_LABELS[severity]}`
    );
    block.setAttribute("aria-haspopup", "dialog");

    const dot = document.createElement("span");
    dot.className = "event-dot";
    dot.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.className = "event-label";
    label.textContent = item.event.title || typeLabel(item.event.type);
    block.append(dot, label);
    block.addEventListener("click", (clickEvent) => {
      clickEvent.stopPropagation();
      showDetail(item.event);
    });
    track.appendChild(block);
  }

  track.style.height = `${Math.max(220, trackTop + laneCount * laneHeight + 20)}px`;

  if (isSameDay(start, now)) {
    const ratio = (now - start) / total;
    if (ratio >= 0 && ratio <= 1) {
      const line = document.createElement("div");
      line.className = "now-line";
      line.style.left = `${ratio * 100}%`;
      if (ratio > 0.92) line.classList.add("is-end");
      const label = document.createElement("span");
      label.textContent = "ตอนนี้";
      line.appendChild(label);
      track.appendChild(line);
    }
  }

  if (!events.length) {
    const filtered = Boolean(els.severity.value || els.type.value);
    const empty = document.createElement("div");
    empty.className = "timeline-empty";
    empty.append(icon("i-activity", "icon"));
    const title = document.createElement("strong");
    title.textContent = filtered ? "ไม่พบเหตุการณ์ตามตัวกรอง" : "ไม่มีเหตุการณ์ในช่วงนี้";
    const detail = document.createElement("small");
    detail.textContent = filtered
      ? "ลองล้างตัวกรองหรือเปลี่ยนช่วงเวลา"
      : "ระบบบันทึกต่อเนื่องอยู่ — ถ้าเพิ่งเริ่ม อาจยังไม่มีข้อมูล";
    empty.append(title, detail);
    track.appendChild(empty);
  }

  attachRangeSelection(track, start, end);
  inner.append(ruler, track);
  scroll.appendChild(inner);
  els.timeline.replaceChildren(scroll);

  if (isSameDay(start, now) && scroll.scrollWidth > scroll.clientWidth) {
    const ratio = (now - start) / total;
    scroll.scrollLeft = Math.max(
      0,
      ratio * scroll.scrollWidth - scroll.clientWidth * 0.5
    );
  }
}

function attachRangeSelection(track, start, end) {
  let drag = null;
  const total = end - start;

  function positionFromEvent(event, rect) {
    return Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
  }

  function updateDrag(event) {
    if (!drag) return;
    const x = positionFromEvent(event, drag.rect);
    const left = Math.min(drag.startX, x);
    const right = Math.max(drag.startX, x);
    drag.overlay.style.left = `${left}px`;
    drag.overlay.style.width = `${right - left}px`;
    const from = new Date(start.getTime() + (left / drag.rect.width) * total);
    const to = new Date(start.getTime() + (right / drag.rect.width) * total);
    drag.label.textContent = `${fmtTime(from)} – ${fmtTime(to)}`;
    if (right - left >= 6) drag.moved = true;
  }

  function cleanupDrag() {
    if (!drag) return;
    const current = drag;
    drag = null;
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onCancel);
    current.overlay.remove();
    return current;
  }

  function onMove(event) {
    if (drag && event.pointerId === drag.pointerId) updateDrag(event);
  }

  function onUp(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const current = drag;
    updateDrag(event);
    const x = positionFromEvent(event, current.rect);
    const left = Math.min(current.startX, x);
    const right = Math.max(current.startX, x);
    const moved = current.moved && right - left >= 6;
    const rect = current.rect;
    cleanupDrag();
    if (!moved) return;
    const from = new Date(start.getTime() + (left / rect.width) * total);
    const to = new Date(start.getTime() + (right / rect.width) * total);
    showSummary(from, to);
  }

  function onCancel(event) {
    if (drag && event.pointerId === drag.pointerId) cleanupDrag();
  }

  track.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    // Touch is reserved for panning the horizontally scrollable day view.
    if (event.pointerType === "touch") return;
    if (event.target instanceof Element && event.target.closest(".event-block")) return;
    const rect = track.getBoundingClientRect();
    if (!rect.width) return;

    const overlay = document.createElement("div");
    overlay.className = "selection";
    const label = document.createElement("span");
    overlay.appendChild(label);
    track.appendChild(overlay);

    drag = {
      pointerId: event.pointerId,
      rect,
      startX: positionFromEvent(event, rect),
      overlay,
      label,
      moved: false,
    };
    updateDrag(event);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
    if (event.pointerType === "mouse") event.preventDefault();
  });
}

function addBucket(map, key, event) {
  const current = map.get(key) || { count: 0, severity: null, types: [] };
  current.count += 1;
  const severity = severityClass(event.severity);
  if (
    current.severity === null ||
    SEVERITY_RANK[severity] > SEVERITY_RANK[current.severity]
  ) {
    current.severity = severity;
  }
  if (event.type && !current.types.includes(event.type)) {
    current.types.push(event.type);
  }
  map.set(key, current);
}

function groupEvents(events, keyFor) {
  // The API buckets are floored in UTC. Aggregate from event timestamps in
  // the browser's local time so week/month/year cells line up with local days.
  const map = new Map();
  for (const event of events) {
    const date = new Date(event.ts_start);
    if (Number.isNaN(date.getTime())) continue;
    addBucket(map, keyFor(date), event);
  }
  return map;
}

function emptyNote(text, className, filtered) {
  const note = document.createElement("p");
  note.className = `empty-inline ${className}`;
  note.textContent = filtered ? "ไม่พบเหตุการณ์ตามตัวกรอง" : text;
  return note;
}

function renderWeek(events, start) {
  const now = new Date();
  const hasFilters = Boolean(els.severity.value || els.type.value);
  const buckets = groupEvents(events, (date) => `${dateKey(date)}:${date.getHours()}`);

  const scroll = document.createElement("div");
  scroll.className = "timeline-scroll";
  const inner = document.createElement("div");
  inner.className = "week-wrap";

  const head = document.createElement("div");
  head.className = "week-row week-head";
  const spacer = document.createElement("div");
  spacer.className = "week-day-label";
  head.appendChild(spacer);
  for (let hour = 0; hour < 24; hour++) {
    const label = document.createElement("div");
    label.className = "week-hour";
    label.textContent = hour % 3 === 0 ? String(hour).padStart(2, "0") : "";
    head.appendChild(label);
  }
  inner.appendChild(head);

  for (let dayIndex = 0; dayIndex < 7; dayIndex++) {
    const day = addDays(start, dayIndex);
    const row = document.createElement("div");
    row.className = "week-row" + (isSameDay(day, now) ? " is-today" : "");

    const label = document.createElement("div");
    label.className = "week-day-label";
    label.textContent = fmtDayLabel(day);
    row.appendChild(label);

    for (let hour = 0; hour < 24; hour++) {
      const bucket = buckets.get(`${dateKey(day)}:${hour}`);
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className =
        "week-cell" +
        (bucket ? " " + bucket.severity : "") +
        (isSameDay(day, now) ? " is-today" : "");
      const description = bucket
        ? `${bucket.count} เหตุการณ์ · ระดับสูงสุด ${SEVERITY_LABELS[bucket.severity]}`
        : "ไม่มีเหตุการณ์";
      cell.title = `${fmtDayLabel(day)} ${String(hour).padStart(2, "0")}:00 · ${description}`;
      cell.setAttribute("aria-label", cell.title);
      cell.addEventListener("click", () => {
        state.cursor = new Date(day);
        setView("day");
      });
      row.appendChild(cell);
    }
    inner.appendChild(row);
  }

  scroll.appendChild(inner);
  const fragment = document.createDocumentFragment();
  fragment.appendChild(scroll);
  if (!events.length) {
    fragment.appendChild(emptyNote("ไม่มีเหตุการณ์ในสัปดาห์นี้", "week-empty", hasFilters));
  }
  els.timeline.replaceChildren(fragment);
}

function renderMonth(events, start) {
  const now = new Date();
  const hasFilters = Boolean(els.severity.value || els.type.value);
  const buckets = groupEvents(events, dateKey);
  const first = new Date(start.getFullYear(), start.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const gridStart = addDays(first, -offset);

  const top = document.createElement("div");
  top.className = "month-view";
  const head = document.createElement("div");
  head.className = "month-head";
  for (const name of DAYS_TH) {
    const label = document.createElement("span");
    label.textContent = name;
    head.appendChild(label);
  }
  const grid = document.createElement("div");
  grid.className = "month-grid";

  for (let index = 0; index < 42; index++) {
    const day = addDays(gridStart, index);
    const inMonth = day.getMonth() === first.getMonth();
    const bucket = buckets.get(dateKey(day));
    const cell = document.createElement(inMonth ? "button" : "div");
    if (inMonth) cell.type = "button";
    cell.className =
      "month-cell" +
      (inMonth ? "" : " is-outside") +
      (bucket && inMonth ? " " + bucket.severity : "") +
      (inMonth && isSameDay(day, now) ? " is-today" : "");

    const dayLabel = document.createElement("span");
    dayLabel.className = "month-day";
    dayLabel.textContent = String(day.getDate());
    cell.appendChild(dayLabel);

    if (bucket && inMonth) {
      const count = document.createElement("span");
      count.className = "month-count";
      count.textContent = `${bucket.count} เหตุการณ์`;
      const severity = document.createElement("span");
      severity.className = "month-sev " + bucket.severity;
      severity.textContent = SEVERITY_LABELS[bucket.severity];
      cell.append(count, severity);
      cell.setAttribute(
        "aria-label",
        `${FULL_DATE.format(day)} · ${bucket.count} เหตุการณ์ · ระดับสูงสุด ${SEVERITY_LABELS[bucket.severity]}`
      );
    } else if (inMonth) {
      cell.setAttribute("aria-label", `${FULL_DATE.format(day)} · ไม่มีเหตุการณ์`);
    }

    if (inMonth) {
      cell.addEventListener("click", () => {
        state.cursor = new Date(day);
        setView("day");
      });
    }
    grid.appendChild(cell);
  }

  top.append(head, grid);
  const fragment = document.createDocumentFragment();
  fragment.appendChild(top);
  if (!events.length) {
    fragment.appendChild(emptyNote("ไม่มีเหตุการณ์ในเดือนนี้", "month-empty", hasFilters));
  }
  els.timeline.replaceChildren(fragment);
}

function renderYear(events, start) {
  const now = new Date();
  const hasFilters = Boolean(els.severity.value || els.type.value);
  const year = start.getFullYear();
  const buckets = groupEvents(events, monthKey);

  const grid = document.createElement("div");
  grid.className = "year-grid";

  for (let month = 0; month < 12; month++) {
    const bucket = buckets.get(`${year}-${String(month + 1).padStart(2, "0")}`);
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className =
      "year-cell" +
      (bucket ? " " + bucket.severity : "") +
      (isSameMonth(now, new Date(year, month, 1)) ? " is-current" : "");

    const name = document.createElement("span");
    name.className = "year-name";
    name.textContent = MONTHS_TH[month];
    cell.appendChild(name);

    const count = document.createElement("span");
    count.className = "year-count";
    count.textContent = bucket ? `${bucket.count} เหตุการณ์` : "ไม่มีเหตุการณ์";
    cell.appendChild(count);

    if (bucket) {
      const severity = document.createElement("span");
      severity.className = "year-sev " + bucket.severity;
      severity.textContent = SEVERITY_LABELS[bucket.severity];
      cell.appendChild(severity);
      cell.setAttribute(
        "aria-label",
        `${MONTHS_TH[month]} ${YEAR_LABEL.format(new Date(year, month, 1))} · ${bucket.count} เหตุการณ์ · ระดับสูงสุด ${SEVERITY_LABELS[bucket.severity]}`
      );
    } else {
      cell.setAttribute(
        "aria-label",
        `${MONTHS_TH[month]} ${YEAR_LABEL.format(new Date(year, month, 1))} · ไม่มีเหตุการณ์`
      );
    }

    cell.addEventListener("click", () => {
      state.cursor = new Date(year, month, 1);
      setView("month");
    });
    grid.appendChild(cell);
  }

  const fragment = document.createDocumentFragment();
  fragment.appendChild(grid);
  if (!events.length) {
    fragment.appendChild(emptyNote("ไม่มีเหตุการณ์ในปีนี้", "year-empty", hasFilters));
  }
  els.timeline.replaceChildren(fragment);
}

function closeSummary() {
  if (state.summaryRequest) {
    state.summaryRequest.abort();
    state.summaryRequest = null;
  }
  els.summary.hidden = true;
}

function showDetail(event) {
  const severity = severityClass(event.severity);
  state.lastFocused = document.activeElement;

  els.detailSeverity.textContent = SEVERITY_LABELS[severity];
  els.detailSeverity.className = "severity-badge " + severity;
  els.detailTitle.textContent = event.title || typeLabel(event.type);
  els.detailTime.textContent = event.ts_end
    ? `${fmtDateTime(event.ts_start)} – ${fmtDateTime(event.ts_end)}`
    : `เริ่ม ${fmtDateTime(event.ts_start)} · กำลังเกิด`;
  els.detailNarrative.textContent = event.narrative || "ไม่มีคำอธิบายเพิ่มเติม";
  els.detailDetails.textContent = event.details || "";
  els.detailDetails.hidden =
    !event.details || event.details === event.narrative;

  const end = event.ts_end ? new Date(event.ts_end) : new Date();
  els.detailMeta.replaceChildren(
    factRow("ประเภท", `${typeLabel(event.type)} (${event.type || "—"})`),
    factRow("เริ่ม", fmtDateTime(event.ts_start)),
    factRow("สิ้นสุด", event.ts_end ? fmtDateTime(event.ts_end) : "กำลังเกิด"),
    factRow("ระยะเวลา", fmtDuration(event.ts_start, end))
  );

  let evidence = event.evidence;
  if (typeof evidence === "string") {
    try {
      evidence = JSON.parse(evidence);
    } catch (_error) {
      // Keep the raw string below.
    }
  }
  if (evidence && typeof evidence === "object" && Object.keys(evidence).length) {
    els.detailEvidence.textContent = JSON.stringify(evidence, null, 2);
  } else if (typeof evidence === "string" && evidence.trim()) {
    els.detailEvidence.textContent = evidence;
  } else {
    els.detailEvidence.textContent = "ไม่มีข้อมูลหลักฐานเพิ่มเติม";
  }

  els.detail.hidden = false;
  els.drawerScrim.hidden = false;
  document.body.classList.add("no-scroll");
  els.detailClose.focus();
}

function closeDetail() {
  if (els.detail.hidden) return;
  els.detail.hidden = true;
  els.drawerScrim.hidden = true;
  document.body.classList.remove("no-scroll");
  if (state.lastFocused && typeof state.lastFocused.focus === "function") {
    state.lastFocused.focus();
  }
  state.lastFocused = null;
}

async function showSummary(start, end) {
  els.summary.hidden = false;
  els.summaryRange.textContent = `${fmtDateTime(start)} – ${fmtDateTime(end)}`;
  els.summaryText.textContent = "กำลังสรุป...";
  els.summary.scrollIntoView({ behavior: "smooth", block: "nearest" });

  if (state.summaryRequest) state.summaryRequest.abort();
  const controller = new AbortController();
  state.summaryRequest = controller;

  const query = new URLSearchParams({
    start: start.toISOString(),
    end: end.toISOString(),
  });
  if (els.severity.value) query.set("severity", els.severity.value);
  if (els.type.value) query.set("type", els.type.value);

  try {
    const data = await api("/api/summary?" + query.toString(), {
      signal: controller.signal,
    });
    if (controller.signal.aborted) return;
    els.summaryText.textContent = data.text || "ไม่พบเหตุการณ์ในช่วงนี้";
  } catch (error) {
    if (error.name === "AbortError") return;
    if (error instanceof ApiError && error.status === 401) {
      showTokenError();
      return;
    }
    els.summaryText.textContent =
      "สรุปไม่ได้: " +
      (error instanceof ApiError ? error.message : "โปรแกรมไม่ตอบสนอง");
  } finally {
    if (state.summaryRequest === controller) state.summaryRequest = null;
  }
}

function setView(view) {
  if (!VIEWS.includes(view)) return;
  closeSummary();
  state.view = view;
  syncTabs();
  syncUrl();
  loadTimeline();
}

function navigate(delta) {
  closeSummary();
  if (state.view === "day") {
    state.cursor = addDays(state.cursor, delta);
  } else if (state.view === "week") {
    state.cursor = addDays(state.cursor, delta * 7);
  } else if (state.view === "month") {
    state.cursor = new Date(
      state.cursor.getFullYear(),
      state.cursor.getMonth() + delta,
      1
    );
  } else {
    state.cursor = new Date(state.cursor.getFullYear() + delta, 0, 1);
  }
  syncUrl();
  loadTimeline();
}

function setSaveStatus(message, kind = "") {
  if (state.saveTimer) {
    clearTimeout(state.saveTimer);
    state.saveTimer = null;
  }
  els.saveStatus.textContent = message;
  els.saveStatus.className = "save-status" + (kind ? " " + kind : "");
  if (kind === "ok") {
    state.saveTimer = setTimeout(() => {
      els.saveStatus.textContent = "";
      els.saveStatus.className = "save-status";
    }, 4000);
  }
}

function updatePublicIpHelp() {
  els.publicIpHelp.textContent = els.publicIp.checked
    ? "เปิดอยู่ — จะตรวจไอพีสาธารณะทุก 15 นาที"
    : "ปิดอยู่ — ไม่มีการเช็กไอพีออกนอกเครื่อง";
}

function applySettings(data) {
  els.interval.value = data.base_interval_s;
  els.retention.value = data.retention_days;
  els.publicIp.checked = Boolean(data.public_ip_enabled);
  updatePublicIpHelp();
  els.footState.textContent = `ตรวจทุก ${data.base_interval_s} วินาที`;
}

async function loadSettings() {
  if (!token || state.tokenError) return;
  try {
    const data = await api("/api/settings");
    applySettings(data);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showTokenError();
      return;
    }
    setSaveStatus(
      "โหลดการตั้งค่าไม่ได้: " +
        (error instanceof ApiError ? error.message : "โปรแกรมไม่ตอบสนอง"),
      "error"
    );
  }
}

async function saveSettings() {
  const interval = Number(els.interval.value);
  const retention = Number(els.retention.value);
  if (!Number.isInteger(interval) || interval < 10 || interval > 3600) {
    setSaveStatus("ตรวจทุกต้องอยู่ระหว่าง 10–3600 วินาที", "error");
    return;
  }
  if (!Number.isInteger(retention) || retention < 1 || retention > 3650) {
    setSaveStatus("เก็บข้อมูลต้องอยู่ระหว่าง 1–3650 วัน", "error");
    return;
  }

  els.saveSettings.disabled = true;
  setSaveStatus("กำลังบันทึก...");
  try {
    const data = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({
        base_interval_s: interval,
        retention_days: retention,
        public_ip_enabled: els.publicIp.checked,
      }),
    });
    applySettings(data);
    setSaveStatus("บันทึกแล้ว", "ok");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showTokenError();
      return;
    }
    setSaveStatus(
      "บันทึกไม่ได้: " +
        (error instanceof ApiError ? error.message : "โปรแกรมไม่ตอบสนอง"),
      "error"
    );
  } finally {
    els.saveSettings.disabled = false;
  }
}

async function quitApp() {
  const confirmed = window.confirm(
    "ออกจาก Home Network Black Box?\nระบบจะหยุดเฝ้าอินเทอร์เน็ตจนกว่าจะเปิดใหม่"
  );
  if (!confirmed) return;

  els.quitApp.disabled = true;
  if (els.quitStatus) els.quitStatus.textContent = "กำลังปิด...";
  try {
    await api("/api/quit", { method: "POST" });
    stopPolling();
    closeDetail();
    document.title = "ปิดแล้ว — Home Network Black Box";
    showNotice(
      "ปิดโปรแกรมแล้ว",
      "หยุดเฝ้าอินเทอร์เน็ตและปิดการเชื่อมต่อในเครื่องแล้ว ปิดแท็บนี้ได้เลย"
    );
  } catch (error) {
    els.quitApp.disabled = false;
    const message =
      error instanceof ApiError && error.status === 503
        ? "โหมดนี้ปิดจากหน้าเว็บไม่ได้ — ปิดที่ tray"
        : "ปิดไม่ได้: " + (error instanceof ApiError ? error.message : "โปรแกรมไม่ตอบสนอง");
    if (els.quitStatus) els.quitStatus.textContent = message;
  }
}

function applyFilters() {
  closeSummary();
  loadTimeline();
}

function bindEvents() {
  for (const button of document.querySelectorAll("[data-view]")) {
    button.addEventListener("click", () => setView(button.dataset.view));
  }
  els.severity.addEventListener("change", applyFilters);
  els.type.addEventListener("change", applyFilters);
  els.clearFilters.addEventListener("click", () => {
    els.severity.value = "";
    els.type.value = "";
    closeSummary();
    loadTimeline();
  });

  els.prev.addEventListener("click", () => navigate(-1));
  els.next.addEventListener("click", () => navigate(1));
  els.today.addEventListener("click", () => {
    closeSummary();
    state.cursor = new Date();
    syncUrl();
    loadTimeline();
  });
  els.summarizeRange.addEventListener("click", () => {
    const range = state.range || rangeFor(state.view, state.cursor);
    showSummary(range[0], range[1]);
  });

  els.detailClose.addEventListener("click", closeDetail);
  els.drawerScrim.addEventListener("click", closeDetail);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.detail.hidden) closeDetail();
  });

  els.summaryClose.addEventListener("click", closeSummary);

  els.saveSettings.addEventListener("click", saveSettings);
  els.publicIp.addEventListener("change", updatePublicIpHelp);
  els.quitApp.addEventListener("click", quitApp);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && token && !state.tokenError) {
      loadStatus();
      loadTimeline();
    }
  });
}

function init() {
  bindEvents();
  syncTabs();
  syncUrl();
  if (!token) {
    showNoToken();
    return;
  }
  loadStatus();
  loadTimeline();
  loadSettings();
  startPolling();
}

init();
