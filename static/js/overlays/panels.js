/* =============================================================
   panels.js — panels overlay for OBS browser source
   ============================================================= */

document.addEventListener("overlay:panel_show", (event) => {
  console.log("[Panels Overlay] Panel show:", event.detail);
});

document.addEventListener("overlay:panel_hide", (event) => {
  console.log("[Panels Overlay] Panel hide:", event.detail);
});