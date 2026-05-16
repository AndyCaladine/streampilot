/* =============================================================
   settings.js — settings page
   ============================================================= */

document.addEventListener("DOMContentLoaded", async () => {
  await loadOverlayStatus();

  // Refresh button
  document.getElementById("refreshStatus")
    ?.addEventListener("click", loadOverlayStatus);

  // Clock format buttons
  document.querySelectorAll(".clock-format-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".clock-format-btn")
        .forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      setClockFormat(btn.dataset.format);
      showToast(`Switched to ${btn.dataset.format}-hour clock.`, "success");
    });
  });

  // Theme buttons
  document.querySelectorAll(".theme-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".theme-btn")
        .forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      applyTheme(btn.dataset.theme);
      showToast(`Theme set to ${btn.dataset.theme}.`, "success");
    });
  });

  // Mark active theme button
  const currentTheme = localStorage.getItem("sp_theme") || "light";
  document.querySelector(`[data-theme="${currentTheme}"]`)
    ?.classList.add("active");

  // Mark active clock format
  const currentFormat = localStorage.getItem("sp_clock_format") || "24";
  document.querySelector(`[data-format="${currentFormat}"]`)
    ?.classList.add("active");
});


async function loadOverlayStatus() {
  try {
    const status = await apiRequest("/api/overlays/status");
    const container = document.getElementById("connectionStatus");
    if (!container) return;

    container.innerHTML = Object.entries(status).map(([type, data]) => `
      <div class="overlay-status-item">
        <span class="overlay-status-item__name">
          ${type.charAt(0).toUpperCase() + type.slice(1)}
        </span>
        <span class="overlay-status-item__status ${data.connected ? "connected" : "disconnected"}">
          ${data.connected ? "✓ Connected" : data.last_seen}
        </span>
      </div>
    `).join("");

  } catch (error) {
    showToast("Could not load overlay status.", "error");
  }
}