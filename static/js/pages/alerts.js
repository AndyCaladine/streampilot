/* =============================================================
   alerts.js — alerts configuration page
   ============================================================= */

document.addEventListener("DOMContentLoaded", () => {

  // Wire up test alert buttons
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

});