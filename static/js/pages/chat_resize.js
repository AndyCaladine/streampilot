
(function () {
  "use strict";

  const PREF_KEY      = "chat_layout";
  const SAVE_DEBOUNCE = 500;
  const DEFAULTS      = { eventFeedH: 180, manifestW: 300 };

  let prefs       = { ...DEFAULTS };
  let saveTimer   = null;
  let initialized = false;

  function applySizes() {
    const ep = document.getElementById("eventFeedPanel");
    const mp = document.getElementById("manifestPanel");
    if (ep) ep.style.height = prefs.eventFeedH + "px";
    if (mp) mp.style.width  = prefs.manifestW  + "px";
  }

  async function loadPrefs() {
    try {
      const data = await apiRequest("/api/preferences");
      const raw  = data[PREF_KEY];
      if (raw) {
        const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        prefs = { ...DEFAULTS, ...parsed };
      }
    } catch (e) {
      console.warn("[ChatResize] loadPrefs failed:", e.message);
    }
    applySizes();
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try {
        await apiRequest("/api/preferences", "POST", {
          [PREF_KEY]: JSON.stringify(prefs),
        });
      } catch (e) {
        console.warn("[ChatResize] save failed:", e.message);
      }
    }, SAVE_DEBOUNCE);
  }

  function initHorizontalDrag() {
    const handle = document.getElementById("dragHandleH");
    if (!handle) return;

    handle.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      handle.classList.add("is-dragging");
      document.body.classList.add("is-resizing");

      const startY = e.clientY;
      const startH = document.getElementById("eventFeedPanel").getBoundingClientRect().height;

      function onMove(e) {
        const newH = Math.max(80, Math.min(startH + (e.clientY - startY), window.innerHeight * 0.6));
        prefs.eventFeedH = Math.round(newH);
        applySizes();
      }

      function onUp() {
        handle.classList.remove("is-dragging");
        document.body.classList.remove("is-resizing");
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup",   onUp);
        scheduleSave();
      }

      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup",   onUp);
    });
  }

  function initVerticalDrag() {
    const handle = document.getElementById("dragHandleV");
    if (!handle) return;

    handle.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      handle.classList.add("is-dragging");
      document.body.classList.add("is-resizing");

      const startX = e.clientX;
      const startW = document.getElementById("manifestPanel").getBoundingClientRect().width;

      function onMove(e) {
        const newW = Math.max(160, Math.min(startW + (startX - e.clientX), window.innerWidth * 0.5));
        prefs.manifestW = Math.round(newW);
        applySizes();
      }

      function onUp() {
        handle.classList.remove("is-dragging");
        document.body.classList.remove("is-resizing");
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup",   onUp);
        scheduleSave();
      }

      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup",   onUp);
    });
  }

  function init() {
    if (!document.getElementById("dragHandleH")) return;
    if (initialized) return;
    initialized = true;
    loadPrefs();
    initHorizontalDrag();
    initVerticalDrag();
  }

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("htmx:afterSettle", init);

})();