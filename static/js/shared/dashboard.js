/* =============================================================
   dashboard.js — shared dashboard initialisation
   Runs on every dashboard page.
   Handles:
     - WebSocket connection
     - Sidebar collapse toggle
     - Mobile menu toggle
     - User menu dropdown
     - ON AIR button state
     - Topbar channel info
   ============================================================= */

document.addEventListener("DOMContentLoaded", () => {

  // -- Initialise WebSocket ----------------------------------
  SP.init();

  // -- Sidebar collapse toggle -------------------------------
  const sidebar            = document.getElementById("sidebar");
  const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");

  if (sidebar && sidebarCollapseBtn) {
    // Restore saved state
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

    // Close sidebar when clicking outside on mobile
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

    // Close when clicking outside
    document.addEventListener("click", () => {
      userMenuDropdown.classList.remove("open");
    });
  }

  // -- Stream status from WebSocket --------------------------
  document.addEventListener("sp:stream_status", (event) => {
    updateOnAirStatus(event.detail);
  });

  // -- Load initial channel data -----------------------------
  loadChannelData();

});


async function loadChannelData() {
  try {
    const data = await apiRequest("/api/channel");

    // Update topbar stats if present
    if (data.viewer_count !== undefined) {
      updateOnAirStatus(data);
    }
  } catch (error) {
    console.warn("[SP] Could not load channel data:", error.message);
  }
}


function updateOnAirStatus(data) {
  const onAirBtn   = document.getElementById("onAirBtn");
  const onAirDot   = document.getElementById("onAirDot");
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

  // Update stat pills
  if (data.viewer_count !== undefined) {
    const viewerEl = document.getElementById("statViewers");
    if (viewerEl) viewerEl.textContent = formatNumber(data.viewer_count);
  }

  if (data.follower_count !== undefined) {
    const followerEl = document.getElementById("statFollowers");
    if (followerEl) followerEl.textContent = formatNumber(data.follower_count);
  }

  if (data.subscriber_count !== undefined) {
    const subEl = document.getElementById("statSubscribers");
    if (subEl) subEl.textContent = formatNumber(data.subscriber_count);
  }

  if (data.uptime_seconds !== undefined) {
    const uptimeEl = document.getElementById("statUptime");
    if (uptimeEl) uptimeEl.textContent = formatUptime(data.uptime_seconds);
  }
}