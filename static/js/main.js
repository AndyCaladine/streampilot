/* =============================================================
   main.js — runs on every page
   Shared utilities available globally across all templates.
   ============================================================= */


// =============================================================
// Theme — light / dark mode
// Reads from localStorage on every page load and applies
// the correct theme before the page renders to avoid flash.
// =============================================================

(function () {
  const saved = localStorage.getItem("sp_theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
})();


// =============================================================
// Utility functions
// Available globally — call these from any page script.
// =============================================================

/**
 * Format a number for display.
 * 1234 → "1,234"    1500000 → "1.5M"
 */
function formatNumber(number) {
  if (number === null || number === undefined) return "—";
  if (number >= 1_000_000) return (number / 1_000_000).toFixed(1) + "M";
  if (number >= 1_000) return number.toLocaleString("en-GB");
  return String(number);
}


/**
 * Format seconds as hh:mm:ss uptime string.
 * 3661 → "01:01:01"
 */
function formatUptime(seconds) {
  if (!seconds) return "00:00:00";
  const hours   = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs    = seconds % 60;
  return [hours, minutes, secs]
    .map(value => String(value).padStart(2, "0"))
    .join(":");
}


/**
 * Show a brief toast notification at the bottom of the screen.
 * type: "success" | "error" | "info" | "warn"
 */
function showToast(message, type = "info") {
  const existing = document.getElementById("sp-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id        = "sp-toast";
  toast.className = `flash flash--${type}`;
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(12px);
    z-index: 9999;
    opacity: 0;
    transition: opacity 0.2s ease, transform 0.2s ease;
    pointer-events: none;
    white-space: nowrap;
    min-width: 200px;
    text-align: center;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    toast.style.opacity   = "1";
    toast.style.transform = "translateX(-50%) translateY(0)";
  });

  // Animate out and remove
  setTimeout(() => {
    toast.style.opacity   = "0";
    toast.style.transform = "translateX(-50%) translateY(12px)";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}


/**
 * Make a JSON API request.
 * Returns parsed JSON or throws an error with the server's message.
 *
 * Usage:
 *   const data = await apiRequest("/api/commands");
 *   await apiRequest("/api/commands/1", "DELETE");
 *   await apiRequest("/api/commands", "POST", { trigger: "discord", response: "..." });
 */
async function apiRequest(url, method = "GET", body = null) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(url, options);
  const data     = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `Request failed with status ${response.status}`);
  }
  return data;
}


/**
 * Debounce — delay function execution until after
 * wait ms have passed since the last call.
 */
function debounce(fn, wait = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}


