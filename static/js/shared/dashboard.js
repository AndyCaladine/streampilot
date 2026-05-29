/* =============================================================
   dashboard.js — shared dashboard initialisation
   Runs on every dashboard page.
   ============================================================= */

let statsInterval = null;

document.addEventListener("DOMContentLoaded", () => {

  // Start onboarding tour if not completed
  startOnboarding();

  // -- Initialise WebSocket ----------------------------------
  SP.init();

  // -- Sidebar collapse toggle -------------------------------
  const sidebar            = document.getElementById("sidebar");
  const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");

  if (sidebar && sidebarCollapseBtn) {
    const isCollapsed = localStorage.getItem("sp_sidebar_collapsed") === "true";
    if (isCollapsed) sidebar.classList.add("collapsed");

    sidebarCollapseBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      const collapsed = sidebar.classList.contains("collapsed");
      localStorage.setItem("sp_sidebar_collapsed", collapsed);
    });
  }

  // -- Mobile menu toggle ------------------------------------
  const mobileMenuBtn = document.getElementById("mobileMenuBtn");

  if (mobileMenuBtn && sidebar) {
    mobileMenuBtn.addEventListener("click", () => {
      sidebar.classList.toggle("mobile-open");
    });

    document.addEventListener("click", (event) => {
      if (
        sidebar.classList.contains("mobile-open") &&
        !sidebar.contains(event.target) &&
        !mobileMenuBtn.contains(event.target)
      ) {
        sidebar.classList.remove("mobile-open");
      }
    });
  }

  // -- User menu dropdown ------------------------------------
  const userMenuBtn      = document.getElementById("userMenuBtn");
  const userMenuDropdown = document.getElementById("userMenuDropdown");

  if (userMenuBtn && userMenuDropdown) {
    userMenuBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      userMenuDropdown.classList.toggle("open");
    });

    userMenuDropdown.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    document.addEventListener("click", () => {
      userMenuDropdown.classList.remove("open");
    });
  }

  // -- Stream status from WebSocket --------------------------
  document.addEventListener("sp:stream_status", (event) => {
    updateOnAirStatus(event.detail);
  });

  // -- Load real Twitch stats --------------------------------
  loadStreamStats();

});


// ---- Real Twitch stats -------------------------------------
async function loadStreamStats() {
  try {
    const stats = await apiRequest("/api/stream/stats");

    // Don't overwrite stats if simulation is running
    const isSimulating = document.getElementById("simulateBtn")
      ?.textContent.includes("Stop");

    const onAirBtn   = document.getElementById("onAirBtn");
    const onAirLabel = document.getElementById("onAirLabel");

    if (stats.live && !isSimulating) {
      onAirBtn?.classList.add("live");
      onAirBtn?.classList.remove("simulating");
      if (onAirLabel) onAirLabel.textContent = "ON AIR";
    } else if (!isSimulating) {
      onAirBtn?.classList.remove("live", "simulating");
      if (onAirLabel) onAirLabel.textContent = "OFFLINE";
    }

    if (!isSimulating) {
      const viewers   = document.getElementById("statViewers");
      const followers = document.getElementById("statFollowers");
      const subs      = document.getElementById("statSubscribers");
      const uptime    = document.getElementById("statUptime");

      if (viewers)   setStatValue("statViewers",     stats.viewers     !== null ? formatNumber(stats.viewers)     : "—");
      if (followers) setStatValue("statFollowers",   stats.followers   !== null ? formatNumber(stats.followers)   : "—");
      if (subs)      setStatValue("statSubscribers", stats.subscribers !== null ? formatNumber(stats.subscribers) : "—");
      if (stats.live && stats.uptime_seconds !== null) {
        // Sync local uptime counter to Twitch's value on each poll
        // then let the local tick handle per-second updates
        if (!uptimeTick) {
          uptimeSeconds = stats.uptime_seconds;
          uptimeTick = setInterval(() => {
            uptimeSeconds++;
            setStatValue("statUptime", formatUptime(uptimeSeconds));
          }, 1000);
        }
      } else if (!stats.live && uptimeTick && !simulateInterval) {
        // Stream ended — stop local tick
        clearInterval(uptimeTick);
        uptimeTick    = null;
        uptimeSeconds = 0;
        setStatValue("statUptime", "—");
      }
    }

    // Poll every 10 seconds
    if (!statsInterval) {
      statsInterval = setInterval(loadStreamStats, 10000);
    }

  } catch (error) {
    console.warn("[Dashboard] Could not load stream stats:", error.message);
  }
}


async function loadChannelData() {
  try {
    const data = await apiRequest("/api/channel");
    if (data.viewer_count !== undefined) {
      updateOnAirStatus(data);
    }
  } catch (error) {
    console.warn("[SP] Could not load channel data:", error.message);
  }
}


function updateOnAirStatus(data) {
  const onAirBtn   = document.getElementById("onAirBtn");
  const onAirLabel = document.getElementById("onAirLabel");

  if (!onAirBtn) return;

  const isLive = data.live || data.viewer_count > 0;

  if (isLive) {
    onAirBtn.classList.add("live");
    if (onAirLabel) onAirLabel.textContent = "ON AIR";
  } else {
    onAirBtn.classList.remove("live");
    if (onAirLabel) onAirLabel.textContent = "OFFLINE";
  }

  if (data.viewer_count !== undefined) {
    const el = document.getElementById("statViewers");
    if (el) el.textContent = formatNumber(data.viewer_count);
  }

  if (data.follower_count !== undefined) {
    const el = document.getElementById("statFollowers");
    if (el) el.textContent = formatNumber(data.follower_count);
  }

  if (data.subscriber_count !== undefined) {
    const el = document.getElementById("statSubscribers");
    if (el) el.textContent = formatNumber(data.subscriber_count);
  }

  if (data.uptime_seconds !== undefined) {
    const el = document.getElementById("statUptime");
    if (el) el.textContent = formatUptime(data.uptime_seconds);
  }
}