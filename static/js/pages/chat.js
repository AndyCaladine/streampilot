/* =============================================================
   chat.js — StreamPilot live chat
   
   Responsibilities:
   - Connect to Twitch IRC via SocketIO relay
   - Render messages with badges, colours, emotes
   - Persist chat log in sessionStorage (survives tab switches)
   - Username click → user card with real Twitch data
   - Chat profiles (nickname, notes, flag) saved to SP platform
   - Send messages back to Twitch chat
   - Export chat log to PDF
   ============================================================= */

const STORAGE_KEY  = "sp_chat_log";
const MAX_MESSAGES = 2000; // Cap stored messages to avoid sessionStorage bloat

// =============================================================
// State
// =============================================================

const state = {
  paused:              false,
  activeUser:          null,
  messageLog:          [],
  socket:              null,
  capWarningShown:     false,
  listenersAttached:   false,
  nicknames:           {},  // twitch_login → nickname
};

// =============================================================
// Init
// =============================================================

function initChat() {
  if (!document.querySelector(".chat-card")) return;

  restoreFromStorage();
  bindUI();
  connectSocket();
}


// =============================================================
// SocketIO connection
// =============================================================

function connectSocket() {
  state.socket = window._spSocket || io();
  window._spSocket = state.socket;

  // Remove old listeners before re-adding to avoid duplicates
  state.socket.off("chat_status");
  state.socket.off("chat_message");
  state.socket.off("chat_error");

  state.socket.on("chat_status", (data) => {
    updateStatusPill(data.status, data.error || "");
  });

  state.socket.on("chat_message", (msg) => {
    appendMessage(msg, true);
  });

  state.socket.on("chat_error", (data) => {
    showToast(data.error, "error");
  });

  // Emit start_chat — whether socket just connected or was already connected
  if (state.socket.connected) {
    state.socket.emit("start_chat");
  } else {
    state.socket.on("connect", () => {
      state.socket.emit("start_chat");
    });
  }
}


// =============================================================
// Status pill
// =============================================================

function updateStatusPill(status, error) {
  const pill = document.getElementById("chatStatusPill");
  if (!pill) return;

  const labels = {
    connected:    "Live",
    connecting:   "Connecting…",
    disconnected: "Disconnected",
    error:        "Error",
  };

  pill.textContent    = labels[status] || status;
  pill.dataset.status = status;

  if (status === "error" && error) {
    showToast(`Chat error: ${error}`, "error");
  }
}


// =============================================================
// Message rendering
// =============================================================

function appendMessage(msg, save = true) {
  const container = document.getElementById("chatMessages");
  const emptyState = document.getElementById("chatEmptyState");

  if (emptyState) emptyState.remove();

  const el = buildMessageEl(msg);
  container.appendChild(el);

  if (save) {
    saveMessage(msg);
  }

  if (!state.paused) {
    container.scrollTop = container.scrollHeight;
  }
}


function buildMessageEl(msg) {
  const row = document.createElement("div");
  row.className = `chat-message chat-message--${msg.role || "viewer"}`;
  row.dataset.userId = msg.twitch_id || "";
  row.dataset.msgId  = msg.id        || "";

  // Timestamp
  const time = document.createElement("span");
  time.className   = "chat-message__time";
  time.textContent = formatTime(msg.timestamp);

  // Badges
  const badgeEl = buildBadges(msg.badges || []);

  // Username — clickable
  const nameEl = document.createElement("button");
  nameEl.className   = "chat-message__username";
  nameEl.style.color = msg.color || "";
  nameEl.addEventListener("click", () => openUserCard(msg));

// Show nickname in brackets if one is stored
  const displayName = msg.display_name || msg.login;
  const nickname    = state.nicknames[msg.login] || null;
  nameEl.textContent = nickname
    ? `${displayName} (${nickname})`
    : displayName;

  // Separator
  const sep = document.createElement("span");
  sep.className   = "chat-message__sep";
  sep.textContent = ": ";

  // Message body
  const body = document.createElement("span");
  body.className = "chat-message__body";
  body.textContent = msg.message;  // Plain text — safe, no innerHTML

  row.append(time, badgeEl, nameEl, sep, body);
  return row;
}


function buildBadges(badges) {
  const wrap = document.createElement("span");
  wrap.className = "chat-message__badges";

  const icons = {
    broadcaster: { label: "Broadcaster", icon: "🔴" },
    moderator:   { label: "Mod",         icon: "🗡️" },
    vip:         { label: "VIP",         icon: "💎" },
    subscriber:  { label: "Sub",         icon: "⭐" },
  };

  badges.forEach(badge => {
    if (!icons[badge]) return;
    const b = document.createElement("span");
    b.className   = "chat-badge";
    b.title       = icons[badge].label;
    b.textContent = icons[badge].icon;
    wrap.appendChild(b);
  });

  return wrap;
}


function formatTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit"
    });
  } catch {
    return "";
  }
}


// =============================================================
// sessionStorage persistence
// =============================================================

function saveMessage(msg) {
  state.messageLog.push(msg);

  if (state.messageLog.length > MAX_MESSAGES) {
    state.messageLog.shift();

    // Warn once per session when the cap is first hit
    if (!state.capWarningShown) {
      state.capWarningShown = true;
      showToast(
        "Chat log capped at 2000 messages — early messages won't appear in exports.",
        "warning"
      );
    }
  }

  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.messageLog));
  } catch {
    // sessionStorage full — trim and retry
    state.messageLog = state.messageLog.slice(-500);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.messageLog));
  }
}


function restoreFromStorage() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const messages = JSON.parse(raw);
    if (!Array.isArray(messages) || messages.length === 0) return;

    state.messageLog = messages;

    // Remove empty state placeholder before replaying
    const emptyState = document.getElementById("chatEmptyState");
    if (emptyState) emptyState.remove();

    messages.forEach(msg => appendMessage(msg, false));

    const container = document.getElementById("chatMessages");
    if (container) container.scrollTop = container.scrollHeight;

  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}


function clearStorage() {
  sessionStorage.removeItem(STORAGE_KEY);
  state.messageLog = [];
}


// =============================================================
// User card
// =============================================================

async function openUserCard(msg) {
  state.activeUser = {
    twitch_id:    msg.twitch_id,
    login:        msg.login,
    display_name: msg.display_name,
  };

  const card = document.getElementById("userCard");
  card.hidden = false;

  // Populate what we already know immediately
  document.getElementById("ucDisplayName").textContent = msg.display_name || msg.login;
  document.getElementById("ucLogin").textContent       = `@${msg.login}`;
  document.getElementById("ucAvatar").src              = "";
  document.getElementById("ucAccountAge").textContent  = "Loading…";
  document.getElementById("ucFollowerSince").textContent = "Loading…";
  document.getElementById("ucNickname").value          = "";
  document.getElementById("ucNotes").value             = "";
  document.getElementById("ucHistory").innerHTML       = "";
  setActiveFlag("none");

  // Populate recent messages from session log
  populateHistory(msg.login);

  // Fetch full data from SP API
  try {
    const res  = await fetch(`/api/chat/user/${encodeURIComponent(msg.login)}`);
    const data = await res.json();

    if (!res.ok) {
      showToast(data.error || "Could not load user data", "error");
      return;
    }

    // Twitch profile
    document.getElementById("ucAvatar").src =
      data.twitch.avatar_url || "";
    document.getElementById("ucAccountAge").textContent =
      timeAgo(data.twitch.account_created);
    document.getElementById("ucFollowerSince").textContent =
      data.channel.follower_since
        ? formatDate(data.channel.follower_since)
        : "Not following";

    // SP profile
    document.getElementById("ucNickname").value =
      data.profile.nickname || "";
    document.getElementById("ucNotes").value =
      data.profile.notes || "";
    setActiveFlag(data.profile.flag || "none");

  // Store twitch_id for saving
      state.activeUser.twitch_id = data.twitch.id;

      // Cache nickname for chat rendering
      if (data.profile.nickname) {
        state.nicknames[data.twitch.login] = data.profile.nickname;
      } else {
        delete state.nicknames[data.twitch.login];
      }

  } catch (err) {
    showToast("Failed to load user data", "error");
  }
}


function populateHistory(login) {
  const list = document.getElementById("ucHistory");
  list.innerHTML = "";

  const userMessages = state.messageLog
    .filter(m => m.login === login)
    .slice(-10)
    .reverse();

  if (userMessages.length === 0) {
    list.innerHTML = `<p class="empty-state empty-state--sm">No messages in this session.</p>`;
    return;
  }

  userMessages.forEach(m => {
    const row = document.createElement("div");
    row.className = "uc-history-row";

    const time = document.createElement("span");
    time.className   = "uc-history-row__time";
    time.textContent = formatTime(m.timestamp);

    const text = document.createElement("span");
    text.className   = "uc-history-row__text";
    text.textContent = m.message;

    row.append(time, text);
    list.appendChild(row);
  });
}


function setActiveFlag(flag) {
  document.querySelectorAll(".flag-btn").forEach(btn => {
    btn.classList.toggle("flag-btn--active", btn.dataset.flag === flag);
  });
}


function closeUserCard() {
  document.getElementById("userCard").hidden = true;
  state.activeUser = null;
}


async function saveProfile() {
  if (!state.activeUser) return;

  const activeFlag = document.querySelector(".flag-btn--active");

  const payload = {
    twitch_user_id: state.activeUser.twitch_id,
    twitch_login:   state.activeUser.login,
    nickname:       document.getElementById("ucNickname").value.trim(),
    notes:          document.getElementById("ucNotes").value.trim(),
    flag:           activeFlag ? activeFlag.dataset.flag : "none",
  };

  try {
    const res = await fetch("/api/chat/profile", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });

    if (res.ok) {
      showToast("Profile saved", "success");
      // Update nickname cache immediately
      const nickname = document.getElementById("ucNickname").value.trim();
      if (nickname && state.activeUser) {
        state.nicknames[state.activeUser.login] = nickname;
      } else if (state.activeUser) {
        delete state.nicknames[state.activeUser.login];
      }
    } else {
      const data = await res.json();
      showToast(data.error || "Save failed", "error");
    }
  } catch {
    showToast("Save failed", "error");
  }
}


async function clearProfile() {
  if (!state.activeUser?.twitch_id) return;

  try {
    await fetch(`/api/chat/profile/${state.activeUser.twitch_id}`, {
      method: "DELETE",
    });
    document.getElementById("ucNickname").value = "";
    document.getElementById("ucNotes").value    = "";
    setActiveFlag("none");
    showToast("Profile cleared", "success");
  } catch {
    showToast("Clear failed", "error");
  }
}


// =============================================================
// Send message
// =============================================================

function sendMessage() {
  const input   = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message || !state.socket) return;

  state.socket.emit("send_chat_message", { message });

  // Echo own message immediately into the chat view
  appendMessage({
    id:           "local-" + Date.now(),
    twitch_id:    "",
    login:        window._spDisplayName || "you",
    display_name: window._spDisplayName || "You",
    color:        "",
    badges:       ["broadcaster"],
    role:         "broadcaster",
    message:      message,
    timestamp:    new Date().toISOString(),
  }, true);

  input.value = "";
  input.focus();
}


// =============================================================
// Export to PDF
// =============================================================

function exportToPDF() {
  if (state.messageLog.length === 0) {
    showToast("No messages to export", "error");
    return;
  }

  // Build a printable HTML document in a new window
  const lines = state.messageLog.map(msg => {
    const time    = formatTime(msg.timestamp);
    const name    = msg.display_name || msg.login;
    const badges  = (msg.badges || []).map(b => `[${b}]`).join(" ");
    const message = msg.message;
    return `<tr>
      <td class="col-time">${escHtml(time)}</td>
      <td class="col-name">${escHtml(badges)} ${escHtml(name)}</td>
      <td class="col-msg">${escHtml(message)}</td>
    </tr>`;
  }).join("\n");

  const exportDate = new Date().toLocaleString();
  const channelName = document.querySelector(".stat-pill--channel")?.textContent
    || "StreamPilot";

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>StreamPilot Chat Export</title>
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
    .col-time { white-space: nowrap; color: #888; width: 60px; }
    .col-name { white-space: nowrap; font-weight: 600; width: 140px; }
    .col-msg  { word-break: break-word; }
    .footer { margin-top: 16px; font-size: 9px; color: #aaa;
               text-align: center; }
  </style>
</head>
<body>
  <div class="header">
    <div class="header__brand">STREAM<span>PILOT</span></div>
    <div class="header__meta">
      <strong>Chat Export</strong>
      Exported: ${escHtml(exportDate)}<br>
      Messages: ${state.messageLog.length}
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th>User</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>
      ${lines}
    </tbody>
  </table>
  <div class="footer">Generated by StreamPilot &mdash; stream-pilot.co.uk</div>
</body>
</html>`;

  const win = window.open("", "_blank");
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => {
    win.print();  // Triggers browser Save as PDF / Print dialog
  }, 400);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,  "&amp;")
    .replace(/</g,  "&lt;")
    .replace(/>/g,  "&gt;")
    .replace(/"/g,  "&quot;");
}


// =============================================================
// UI helpers
// =============================================================

function timeAgo(isoDate) {
  if (!isoDate) return "Unknown";
  const diff  = Date.now() - new Date(isoDate).getTime();
  const days  = Math.floor(diff / 86400000);
  const years = Math.floor(days / 365);
  if (years > 0) return `${years} year${years > 1 ? "s" : ""} ago`;
  if (days  > 0) return `${days}  day${days  > 1 ? "s" : ""} ago`;
  return "Today";
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric"
  });
}

function showToast(message, type = "success") {
  const t = document.createElement("div");
  t.className   = `toast toast--${type}`;
  t.textContent = message;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// =============================================================
// Event bindings
// =============================================================

function bindUI() {
  // Guard — if core elements aren't in DOM yet, bail out
  if (!document.getElementById("pauseChat")) return;

  // Pause / resume scroll
  document.getElementById("pauseChat").addEventListener("click", function () {
    state.paused      = !state.paused;
    this.textContent  = state.paused ? "Resume" : "Pause";
    this.classList.toggle("btn--primary",   state.paused);
    this.classList.toggle("btn--secondary", !state.paused);
  });

  // Clear — show modal
  document.getElementById("clearChat").addEventListener("click", () => {
    document.getElementById("clearModal").hidden = false;
  });

  // Clear confirm
  document.getElementById("clearConfirm").addEventListener("click", () => {
    document.getElementById("chatMessages").innerHTML =
      `<p class="empty-state" id="chatEmptyState">Chat cleared.</p>`;
    clearStorage();
    document.getElementById("clearModal").hidden = true;
    closeUserCard();
  });

  // Clear cancel
  document.getElementById("clearCancel").addEventListener("click", () => {
    document.getElementById("clearModal").hidden = true;
  });

  // Export PDF
  document.getElementById("exportChat").addEventListener("click", exportToPDF);

  // Send message
  document.getElementById("chatSend").addEventListener("click", sendMessage);
  document.getElementById("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // User card — close
  document.getElementById("ucClose").addEventListener("click", closeUserCard);

  // User card — flag buttons
  document.querySelectorAll(".flag-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      setActiveFlag(btn.dataset.flag);
    });
  });

  // User card — save profile
  document.getElementById("ucSave").addEventListener("click", saveProfile);

  // User card — clear profile
  document.getElementById("ucClearProfile").addEventListener("click", clearProfile);

  // User card — mod actions
  document.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (!state.activeUser) return;
      const action   = btn.dataset.action;
      const duration = btn.dataset.duration;
      handleModAction(action, duration);
    });
  });
}


async function handleModAction(action, duration) {
  if (!state.activeUser) return;

  const name = state.activeUser.display_name || state.activeUser.login;
  const confirmMsg = action === "ban"
    ? `Ban ${name} from your channel?`
    : `Timeout ${name} for ${duration} seconds?`;

  if (!confirm(confirmMsg)) return;

  // Mod actions sent as chat commands — Twitch IRC handles them
  const command = action === "ban"
    ? `/ban ${state.activeUser.login}`
    : `/timeout ${state.activeUser.login} ${duration}`;

  if (state.socket) {
    state.socket.emit("send_chat_message", { message: command });
    showToast(
      action === "ban" ? `${name} banned` : `${name} timed out for ${duration}s`,
      "success"
    );
    closeUserCard();
  }
}


// =============================================================
// Boot
// =============================================================

document.addEventListener("DOMContentLoaded", initChat);
document.addEventListener("htmx:afterSettle", initChat);