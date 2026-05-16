/* =============================================================
   dashboard.js — main dashboard page
   ============================================================= */

document.addEventListener("DOMContentLoaded", async () => {

  // Load overlay connection status
  loadOverlayStatus();

  // Listen for live events
  document.addEventListener("sp:alert", (event) => {
    addEventFeedItem(event.detail);
  });

});


async function loadOverlayStatus() {
  try {
    const status = await apiRequest("/api/overlays/status");

    for (const [type, data] of Object.entries(status)) {
      const element = document.getElementById(
        `overlayStatus${type.charAt(0).toUpperCase() + type.slice(1)}`
      );
      if (!element) continue;

      element.textContent  = data.connected ? `Connected` : data.last_seen;
      element.className    = `overlay-status-item__status ${data.connected ? "connected" : "disconnected"}`;
    }
  } catch (error) {
    console.warn("[Dashboard] Could not load overlay status:", error.message);
  }
}


function addEventFeedItem(data) {
  const feed = document.getElementById("eventFeed");
  if (!feed) return;

  // Remove empty state if present
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

  // Add to top of feed
  feed.insertBefore(item, feed.firstChild);

  // Keep feed to last 50 items
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
    gift_sub: "gifted a subscription",
    raid:     `raided with ${formatNumber(data.viewers || 0)} viewers`,
    bits:     `cheered ${formatNumber(data.bits || 0)} bits`,
    resub:    `resubscribed for ${data.months || 1} months`,
  };
  return texts[data.type] || "triggered an event";
}