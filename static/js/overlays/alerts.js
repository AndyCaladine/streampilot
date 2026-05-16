/* =============================================================
   alerts.js — alerts overlay for OBS browser source
   Listens for overlay:alert events from overlay-base.js
   ============================================================= */

document.addEventListener("overlay:alert", (event) => {
  const data = event.detail;
  console.log("[Alerts Overlay] Alert received:", data);
  // Alert animation — to be built in Phase 2
});