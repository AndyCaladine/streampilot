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

  // ---- World clocks ----------------------------------------
  renderWorldClocksList();

  document.getElementById("addWorldClock")?.addEventListener("click", () => {
    showTimezonePickerModal();
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

const restartBtn = document.getElementById("restartTutorial");
  if (restartBtn) {
    restartBtn.addEventListener("click", async () => {
      await resetOnboarding();
      restartBtn.textContent = "Done — visit the dashboard to start the tour";
      restartBtn.disabled = true;
    });
  }

  // ---- World clocks ------------------------------------------
const COMMON_TIMEZONES = [
  { label: "London (GMT/BST)",       tz: "Europe/London" },
  { label: "New York (EST/EDT)",      tz: "America/New_York" },
  { label: "Los Angeles (PST/PDT)",   tz: "America/Los_Angeles" },
  { label: "Chicago (CST/CDT)",       tz: "America/Chicago" },
  { label: "Toronto (EST/EDT)",       tz: "America/Toronto" },
  { label: "Vancouver (PST/PDT)",     tz: "America/Vancouver" },
  { label: "Paris (CET/CEST)",        tz: "Europe/Paris" },
  { label: "Berlin (CET/CEST)",       tz: "Europe/Berlin" },
  { label: "Amsterdam (CET/CEST)",    tz: "Europe/Amsterdam" },
  { label: "Stockholm (CET/CEST)",    tz: "Europe/Stockholm" },
  { label: "Moscow (MSK)",            tz: "Europe/Moscow" },
  { label: "Dubai (GST)",             tz: "Asia/Dubai" },
  { label: "Tokyo (JST)",             tz: "Asia/Tokyo" },
  { label: "Seoul (KST)",             tz: "Asia/Seoul" },
  { label: "Shanghai (CST)",          tz: "Asia/Shanghai" },
  { label: "Singapore (SGT)",         tz: "Asia/Singapore" },
  { label: "Sydney (AEST/AEDT)",      tz: "Australia/Sydney" },
  { label: "Auckland (NZST/NZDT)",    tz: "Pacific/Auckland" },
  { label: "São Paulo (BRT)",         tz: "America/Sao_Paulo" },
  { label: "UTC",                     tz: "UTC" },
];

function getSavedWorldClocks() {
  try {
    return JSON.parse(localStorage.getItem("sp_world_clocks") || "[]");
  } catch {
    return [];
  }
}

function renderWorldClocksList() {
  const list = document.getElementById("worldClocksList");
  if (!list) return;

  const clocks = getSavedWorldClocks();

  if (clocks.length === 0) {
    list.innerHTML = `<p class="form-hint">No world clocks added yet.</p>`;
    return;
  }

  list.innerHTML = clocks.map(tz => {
    const label = COMMON_TIMEZONES.find(t => t.tz === tz)?.label || tz;
    return `
      <div class="world-clock-row" style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
        <span style="font-size:14px;color:var(--text)">${label}</span>
        <button class="btn btn--secondary btn--sm" onclick="removeWorldClockFromSettings('${tz}')">Remove</button>
      </div>
    `;
  }).join("");
}

function removeWorldClockFromSettings(tz) {
  removeWorldClock(tz); // from clock.js
  renderWorldClocksList();
  showToast("World clock removed.", "success");
}

function showTimezonePickerModal() {
  // Remove existing modal if any
  document.getElementById("tzModal")?.remove();

  const saved = getSavedWorldClocks();

  const modal = document.createElement("div");
  modal.id = "tzModal";
  modal.style.cssText = `
    position: fixed; inset: 0; z-index: 1000;
    background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center;
  `;

  modal.innerHTML = `
    <div style="
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      width: 420px;
      max-width: 90vw;
      box-shadow: var(--shadow-lg);
    ">
      <h3 style="font-size:16px;font-weight:600;margin-bottom:16px;color:var(--text)">Add World Clock</h3>
      <input
        type="text"
        id="tzSearch"
        placeholder="Search timezone..."
        class="form-input"
        style="margin-bottom:12px"
      >
      <div id="tzList" style="max-height:280px;overflow-y:auto;display:flex;flex-direction:column;gap:4px"></div>
      <div style="margin-top:16px;display:flex;justify-content:flex-end">
        <button class="btn btn--secondary btn--sm" id="tzCancel">Cancel</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const tzList   = document.getElementById("tzList");
  const tzSearch = document.getElementById("tzSearch");

  function renderTzList(filter = "") {
    const filtered = COMMON_TIMEZONES.filter(t =>
      t.label.toLowerCase().includes(filter.toLowerCase()) ||
      t.tz.toLowerCase().includes(filter.toLowerCase())
    );

    tzList.innerHTML = filtered.map(t => {
      const already = saved.includes(t.tz);
      return `
        <button
          class="btn btn--secondary btn--sm"
          style="text-align:left;justify-content:space-between;opacity:${already ? 0.4 : 1}"
          ${already ? "disabled" : ""}
          onclick="selectTimezone('${t.tz}')"
        >
          ${t.label}
          ${already ? "<span>Added</span>" : ""}
        </button>
      `;
    }).join("");
  }

  renderTzList();

  tzSearch.addEventListener("input", () => renderTzList(tzSearch.value));
  tzSearch.focus();

  document.getElementById("tzCancel").addEventListener("click", () => modal.remove());
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
}

function selectTimezone(tz) {
  addWorldClock(tz); // from clock.js
  document.getElementById("tzModal")?.remove();
  renderWorldClocksList();
  showToast("World clock added.", "success");
}