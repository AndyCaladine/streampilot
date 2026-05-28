/* =============================================================
   alerts.js — alerts configuration page
   ============================================================= */

function initAlerts() {
  if (!document.querySelector("[data-test-alert]")) return;

  document.querySelectorAll("[data-test-alert]").forEach(button => {
    button.addEventListener("click", async () => {
      const alertType = button.dataset.testAlert;
      try {
        await apiRequest("/api/alerts/test", "POST", { type: alertType });
        showToast(`Test ${alertType} alert fired to overlay.`, "success");
      } catch (error) {
        showToast("Could not fire test alert. Is your overlay connected?", "error");
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", initAlerts);
document.addEventListener("htmx:afterSwap",   initAlerts);