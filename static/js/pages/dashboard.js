/* =============================================================
   dashboard.js — main dashboard page
   ============================================================= */

let simulateInterval = null;
let uptimeSeconds    = 0;
let uptimeTick       = null;

document.addEventListener("DOMContentLoaded", async () => {

  // Warn if navigating away during simulation
  document.querySelectorAll(".sidebar__nav-item").forEach(link => {
    link.addEventListener("click", (e) => {
      if (simulateInterval) {
        const confirm = window.confirm("Leaving the dashboard will stop the simulation. Continue?");
        if (!confirm) e.preventDefault();
      }
    });
  });

  // Load overlay connection status
  loadOverlayStatus();

  // Listen for live events
  document.addEventListener("sp:alert", (event) => {
    addEventFeedItem(event.detail);
  });

  // Simulate live button
  const simulateBtn = document.getElementById("simulateBtn");
  if (simulateBtn) {
    simulateBtn.addEventListener("click", () => {
      if (simulateInterval) {
        stopSimulation(simulateBtn);
      } else {
        startSimulation(simulateBtn);
      }
    });
  }

  // Stat pill hide/show on click
  document.querySelectorAll(".stat-pill").forEach(pill => {
    const valueEl = pill.querySelector("span:not(.stat-pill__label):not(svg)");
    if (!valueEl) return;
    let hidden = false;

    pill.addEventListener("click", () => {
      hidden = !hidden;
      if (hidden) {
        valueEl.dataset.realValue = valueEl.textContent;
        valueEl.textContent = "Hidden";
      } else {
        valueEl.textContent = valueEl.dataset.realValue || "—";
        delete valueEl.dataset.realValue;
      }
    });
  });

});


// ---- Overlay status ----------------------------------------
async function loadOverlayStatus() {
  try {
    const status = await apiRequest("/api/overlays/status");

    for (const [type, data] of Object.entries(status)) {
      const element = document.getElementById(
        `overlayStatus${type.charAt(0).toUpperCase() + type.slice(1)}`
      );
      if (!element) continue;

      element.textContent = data.connected ? "Connected" : data.last_seen;
      element.className   = `overlay-status-item__status ${data.connected ? "connected" : "disconnected"}`;
    }
  } catch (error) {
    console.warn("[Dashboard] Could not load overlay status:", error.message);
  }
}


// ---- Event feed --------------------------------------------
function addEventFeedItem(data) {
  const feed = document.getElementById("eventFeed");
  if (!feed) return;

  const emptyState = feed.querySelector(".empty-state");
  if (emptyState) emptyState.remove();

  const icons = {
    follow:   "⭐",
    sub_t1:   "🌟",
    sub_t2:   "💫",
    sub_t3:   "✨",
    gift_sub: "🎁",
    raid:     "⚔️",
    bits:     "💎",
    resub:    "🔄",
  };

  const item = document.createElement("div");
  item.className = "event-item";
  item.innerHTML = `
    <span class="event-item__icon">${icons[data.type] || "📢"}</span>
    <span class="event-item__text">
      <strong>${data.user || "Someone"}</strong>
      ${getEventText(data)}
    </span>
    <span class="event-item__time">${new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</span>
  `;

  feed.insertBefore(item, feed.firstChild);

  while (feed.children.length > 50) {
    feed.removeChild(feed.lastChild);
  }
}


function getEventText(data) {
  const texts = {
    follow:   "followed the channel",
    sub_t1:   "subscribed (Tier 1)",
    sub_t2:   "subscribed (Tier 2)",
    sub_t3:   "subscribed (Tier 3)",
    gift_sub: `gifted ${data.amount || 1} sub(s) to the community`,
    raid:     `raided with ${data.viewers || 0} viewers`,
    bits:     `cheered ${data.bits || 0} bits`,
    resub:    `resubscribed for ${data.months || 1} months`,
  };
  return texts[data.type] || "triggered an event";
}


// ---- Stat helpers ------------------------------------------
function setStatValue(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  if ("realValue" in el.dataset) {
    el.dataset.realValue = value;
  } else {
    el.textContent = value;
  }
}


// ---- Simulate live -----------------------------------------
function startSimulation(simulateBtn) {
  uptimeSeconds = 0;
  updateSimulatedStats();

  simulateInterval = setInterval(updateSimulatedStats, 120000);

  uptimeTick = setInterval(() => {
    uptimeSeconds++;
    setStatValue("statUptime", formatUptime(uptimeSeconds));
  }, 1000);

  document.getElementById("onAirBtn").classList.add("simulating");
  document.getElementById("onAirLabel").textContent = "LIVE";
  document.querySelectorAll(".stat-pill").forEach(p => p.classList.add("simulating"));

  simulateBtn.textContent = "⏹ Stop Sim";
  simulateBtn.classList.replace("btn--secondary", "btn--danger");

  // Start demo data
  startDemo();
}


function stopSimulation(simulateBtn) {
  clearInterval(simulateInterval);
  clearInterval(uptimeTick);
  simulateInterval = null;
  uptimeTick       = null;
  uptimeSeconds    = 0;

  setStatValue("statViewers",     "—");
  setStatValue("statFollowers",   "—");
  setStatValue("statSubscribers", "—");
  setStatValue("statUptime",      "—");

  document.getElementById("onAirBtn").classList.remove("simulating");
  document.getElementById("onAirLabel").textContent = "OFFLINE";
  document.querySelectorAll(".stat-pill").forEach(p => p.classList.remove("simulating"));

  simulateBtn.textContent = "▶ Simulate Live";
  simulateBtn.classList.replace("btn--danger", "btn--secondary");

  // Stop demo data
  stopDemo();

 //Restore real data
 loadStreamStats(); 
}


function updateSimulatedStats() {
  setStatValue("statViewers",     randomInt(50, 500));
  setStatValue("statFollowers",   randomInt(1000, 9999));
  setStatValue("statSubscribers", randomInt(10, 200));
}


function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map(v => String(v).padStart(2, "0")).join(":");
}


function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}