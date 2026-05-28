/* =============================================================
   panels.js — timed panels management page
   Phase 2: panel scheduling and OBS delivery
   ============================================================= */

function initPanels() {
  if (!document.getElementById("panelsList")) return;
  // Panels functionality coming in Phase 2
}

document.addEventListener("DOMContentLoaded", initPanels);
document.addEventListener("htmx:afterSwap",   initPanels);