from __future__ import annotations

INDEX_HTML = """<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <title>Home Network Black Box</title>
  <style>
    :root { color-scheme: dark; }
    body {
      font-family: system-ui, "Segoe UI", sans-serif;
      margin: 0; padding: 24px; background: #0f1115; color: #e6e6e6;
    }
    h1 { font-size: 24px; margin: 0 0 4px; }
    h2 { font-size: 18px; margin: 0 0 12px; }
    .muted { color: #9aa4b2; }
    .card {
      background: #171a21; border: 1px solid #262b36;
      border-radius: 12px; padding: 16px; margin-top: 16px;
    }
    .status { font-size: 22px; font-weight: 600; }
    .ok { color: #2ecc71; }
    .warning { color: #f1c40f; }
    .critical { color: #e74c3c; }
    ul { padding-left: 20px; margin: 0; }
    li { margin: 8px 0; }
    label { display: block; margin: 10px 0; }
    input {
      background: #0f1115; color: #e6e6e6; border: 1px solid #333;
      border-radius: 6px; padding: 6px 8px;
    }
    input[type="number"] { width: 110px; }
    button {
      background: #2ecc71; color: #0f1115; border: 0; border-radius: 6px;
      padding: 8px 14px; font-weight: 600; cursor: pointer;
    }
  </style>
</head>
<body>
  <h1>Home Network Black Box</h1>
  <div class="muted">สถานะเน็ตบ้านและเหตุการณ์ล่าสุด</div>

  <div class="card">
    <div id="status" class="status">กำลังโหลด...</div>
    <div id="details" class="muted"></div>
  </div>

  <div class="card">
    <h2>เหตุการณ์ล่าสุด</h2>
    <ul id="events"><li class="muted">กำลังโหลด...</li></ul>
  </div>

  <div class="card">
    <h2>ตั้งค่า</h2>
    <label>ตรวจทุก (วินาที) <input id="interval" type="number" min="10" max="3600"></label>
    <label>เก็บข้อมูล (วัน) <input id="retention" type="number" min="1" max="3650"></label>
    <label><input id="public-ip" type="checkbox"> เก็บ Public IP</label>
    <button id="save-settings">บันทึก</button>
    <span id="save-status" class="muted"></span>
  </div>

  <script>
    const params = new URLSearchParams(location.search);
    const token = params.get("token") || sessionStorage.getItem("bb_token") || "";
    if (params.has("token")) {
      sessionStorage.setItem("bb_token", token);
      history.replaceState({}, "", "/");
    }
    const statusEl = document.getElementById("status");
    const detailsEl = document.getElementById("details");
    const eventsEl = document.getElementById("events");

    async function api(path, options = {}) {
      const headers = { "X-API-Token": token, ...(options.headers || {}) };
      const response = await fetch(path, { ...options, headers });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    function showStatus(data) {
      statusEl.textContent = data.status_text;
      statusEl.className = "status " + data.status;
      const parts = [];
      if (data.interface) parts.push("Interface: " + data.interface);
      if (data.gateway) parts.push("Gateway: " + data.gateway);
      if (data.public_ip) parts.push("Public IP: " + data.public_ip);
      if (data.device_count) parts.push("อุปกรณ์: " + data.device_count);
      if (data.last_cycle) parts.push("ตรวจล่าสุด: " + data.last_cycle);
      detailsEl.textContent = parts.join(" · ");
    }

    function showEvents(events) {
      eventsEl.innerHTML = "";
      if (!events.length) {
        const item = document.createElement("li");
        item.className = "muted";
        item.textContent = "ไม่มีเหตุการณ์";
        eventsEl.appendChild(item);
        return;
      }
      for (const event of events) {
        const item = document.createElement("li");
        item.textContent = (event.narrative || event.title) + " [" + event.severity + "]";
        eventsEl.appendChild(item);
      }
    }

    async function refresh() {
      try {
        const [status, events] = await Promise.all([
          api("/api/status"),
          api("/api/events?limit=10"),
        ]);
        showStatus(status);
        showEvents(events);
      } catch (error) {
        statusEl.textContent = "เชื่อมต่อไม่ได้";
        statusEl.className = "status critical";
        detailsEl.textContent = String(error);
      }
    }

    async function loadSettings() {
      const intervalEl = document.getElementById("interval");
      const retentionEl = document.getElementById("retention");
      const publicEl = document.getElementById("public-ip");
      try {
        const data = await api("/api/settings");
        intervalEl.value = data.base_interval_s;
        retentionEl.value = data.retention_days;
        publicEl.checked = data.public_ip_enabled;
      } catch (error) {
        document.getElementById("save-status").textContent = String(error);
      }
    }

    async function saveSettings() {
      const statusEl = document.getElementById("save-status");
      statusEl.textContent = "กำลังบันทึก...";
      try {
        await api("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            base_interval_s: Number(document.getElementById("interval").value),
            retention_days: Number(document.getElementById("retention").value),
            public_ip_enabled: document.getElementById("public-ip").checked,
          }),
        });
        statusEl.textContent = "บันทึกแล้ว";
      } catch (error) {
        statusEl.textContent = "บันทึกไม่ได้: " + error;
      }
    }

    if (!token) {
      statusEl.textContent = "กรุณาเปิดจาก tray";
      statusEl.className = "status warning";
      detailsEl.textContent = "เปิดแอปจาก tray แล้วเลือก 'เปิดหน้าต่าง'";
    } else {
      refresh();
      setInterval(refresh, 5000);
      loadSettings();
      document.getElementById("save-settings").addEventListener("click", saveSettings);
    }
  </script>
</body>
</html>
"""
