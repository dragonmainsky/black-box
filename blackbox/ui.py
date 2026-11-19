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

    async function api(path) {
      const response = await fetch(path, { headers: { "X-API-Token": token } });
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

    if (!token) {
      statusEl.textContent = "กรุณาเปิดจาก tray";
      statusEl.className = "status warning";
      detailsEl.textContent = "เปิดแอปจาก tray แล้วเลือก 'เปิดหน้าต่าง'";
    } else {
      refresh();
      setInterval(refresh, 5000);
    }
  </script>
</body>
</html>
"""
