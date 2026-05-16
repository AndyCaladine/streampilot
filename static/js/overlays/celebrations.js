/* =============================================================
   celebrations.js — celebrations overlay for OBS browser source
   ============================================================= */

document.addEventListener("overlay:celebrate", (event) => {
  console.log("[Celebrations Overlay] Celebrate:", event.detail);
});