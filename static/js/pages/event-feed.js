/* =============================================================
   event_feed.js — StreamPilot
   Listens for stream events via SocketIO and renders them
   into the Event Feed panel on the chat page.
   Controls: pause, clear, export (mirrors chat.js pattern).
   ============================================================= */

const EF_STORAGE_KEY  = "sp_event_log";
const EF_MAX_EVENTS   = 500;

const efState = {
  paused:    false,
  eventLog:  [],
  capShown:  false,
};

// =============================================================
// Init
// =============================================================

function initEventFeed() {
  if (!document.getElementById("eventFeedPanel")) return;

  efRestoreFromStorage();
  efBindUI();
  efConnectSocket();
}


// =============================================================
// Socket
// =============================================================

function efConnectSocket() {
  const socket = window._spSocket || io();
  window._spSocket = socket;

  socket.off("stream_event");
  socket.on("stream_event", (event) => {
    efAppendEvent(event, true);
  });
}


// =============================================================
// Render
// =============================================================

function efAppendEvent(event, save = true) {
  const container = document.getElementById("eventFeedMessages");
  const empty     = document.getElementById("eventFeedEmpty");
  if (!container) return;

  if (empty) empty.remove();

  const el = efBuildEventEl(event);
  container.appendChild(el);

  if (save) efSaveEvent(event);

  if (!efState.paused) {
    container.scrollTop = container.scrollHeight;
  }
}


function efBuildEventEl(event) {
  const row = document.createElement("div");
  row.className = `event-feed-row event-feed-row--${event.type || "default"}`;

  const time = document.createElement("span");
  time.className   = "event-feed-row__time";
  time.textContent = efFormatTime(event.ts);

  const icon = document.createElement("span");
  icon.className   = "event-feed-row__icon";
  icon.textContent = event.icon || "📌";

  const title = document.createElement("span");
  title.className   = "event-feed-row__title";
  title.textContent = event.title || "";

  // Optional message (resub, cheer)
  if (event.message) {
    const msg = document.createElement("span");
    msg.className   = "event-feed-row__message";
    msg.textContent = event.message;
    row.append(time, icon, title, msg);
  } else {
    row.append(time, icon, title);
  }

  return row;
}


function efFormatTime(iso) {
  try {
    return new Date(iso || Date.now()).toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit"
    });
  } catch {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit"
    });
  }
}


// =============================================================
// sessionStorage persistence
// =============================================================

function efSaveEvent(event) {
  efState.eventLog.push(event);

  if (efState.eventLog.length > EF_MAX_EVENTS) {
    efState.eventLog.shift();
    if (!efState.capShown) {
      efState.capShown = true;
      showToast("Event log capped at 500 events.", "warning");
    }
  }

  try {
    sessionStorage.setItem(EF_STORAGE_KEY, JSON.stringify(efState.eventLog));
  } catch {
    efState.eventLog = efState.eventLog.slice(-100);
    sessionStorage.setItem(EF_STORAGE_KEY, JSON.stringify(efState.eventLog));
  }
}


function efRestoreFromStorage() {
  try {
    const raw = sessionStorage.getItem(EF_STORAGE_KEY);
    if (!raw) return;
    const events = JSON.parse(raw);
    if (!Array.isArray(events) || events.length === 0) return;

    efState.eventLog = events;

    const empty = document.getElementById("eventFeedEmpty");
    if (empty) empty.remove();

    events.forEach(e => efAppendEvent(e, false));

    const container = document.getElementById("eventFeedMessages");
    if (container) container.scrollTop = container.scrollHeight;

  } catch {
    sessionStorage.removeItem(EF_STORAGE_KEY);
  }
}


function efClearStorage() {
  sessionStorage.removeItem(EF_STORAGE_KEY);
  efState.eventLog = [];
}


// =============================================================
// Export
// =============================================================

function efExport() {
  if (efState.eventLog.length === 0) {
    showToast("No events to export", "error");
    return;
  }

  const rows = efState.eventLog.map(e => `
    <tr>
      <td class="col-time">${efFormatTime(e.ts)}</td>
      <td class="col-icon">${e.icon || ""}</td>
      <td class="col-title">${e.title || ""}</td>
      <td class="col-msg">${e.message || ""}</td>
    </tr>
  `).join("");

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>StreamPilot Event Export</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'DM Sans', Arial, sans-serif; font-size: 11px;
           color: #1a1a2e; background: #fff; padding: 20px; }
    .header { display: flex; justify-content: space-between;
              align-items: flex-start; margin-bottom: 20px;
              padding-bottom: 12px; border-bottom: 2px solid #00c8ff; }
    .header__brand { font-size: 20px; font-weight: 700; color: #00c8ff;
                     letter-spacing: 1px; }
    .header__brand span { color: #1a1a2e; }
    .header__meta { text-align: right; color: #555; font-size: 10px; }
    .header__meta strong { display: block; font-size: 13px; color: #1a1a2e; }
    table { width: 100%; border-collapse: collapse; }
    th { background: #1a1a2e; color: #fff; padding: 6px 8px;
         text-align: left; font-size: 10px; letter-spacing: 0.5px; }
    td { padding: 4px 8px; border-bottom: 1px solid #f0f0f0;
         vertical-align: top; }
    tr:nth-child(even) td { background: #f9f9f9; }
    .col-time { white-space: nowrap; color: #888; width: 55px; }
    .col-icon { width: 30px; text-align: center; }
    .col-title { font-weight: 600; width: 280px; }
    .col-msg  { color: #555; word-break: break-word; }
    .footer { margin-top: 16px; font-size: 9px; color: #aaa;
              text-align: center; }
  </style>
</head>
<body>
  <div class="header">
    <div class="header__brand">STREAM<span>PILOT</span></div>
    <div class="header__meta">
      <strong>Event Export</strong>
      Exported: ${new Date().toLocaleString()}<br>
      Events: ${efState.eventLog.length}
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th></th>
        <th>Event</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>
  <div class="footer">Generated by StreamPilot &mdash; stream-pilot.co.uk</div>
</body>
</html>`;

  const win = window.open("", "_blank");
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 400);
}


// =============================================================
// UI bindings
// =============================================================

function efBindUI() {
  const pauseBtn  = document.getElementById("efPause");
  const clearBtn  = document.getElementById("efClear");
  const exportBtn = document.getElementById("efExport");

  if (pauseBtn) {
    pauseBtn.addEventListener("click", function () {
      efState.paused     = !efState.paused;
      this.textContent   = efState.paused ? "Resume" : "Pause";
      this.classList.toggle("btn--primary",   efState.paused);
      this.classList.toggle("btn--secondary", !efState.paused);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      const container = document.getElementById("eventFeedMessages");
      if (container) {
        container.innerHTML =
          `<p class="empty-state" id="eventFeedEmpty">Event feed cleared.</p>`;
      }
      efClearStorage();
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", efExport);
  }
}


// =============================================================
// Boot
// =============================================================

document.addEventListener("DOMContentLoaded", initEventFeed);
document.addEventListener("htmx:afterSettle", initEventFeed);