/* =============================================================
   clock.js — local clock and world clocks in the topbar
   Handles:
     - Local time display (12/24 hour)
     - Click to hide/show local clock
     - World clocks loaded from user preferences
   ============================================================= */

let clockFormat  = localStorage.getItem("sp_clock_format") || "24";
let clockVisible = localStorage.getItem("sp_clock_visible") !== "false";
let clockInterval;


document.addEventListener("DOMContentLoaded", () => {
  const localClock = document.getElementById("localClock");
  if (!localClock) return;

  // Start the clock
  updateLocalClock();
  clockInterval = setInterval(updateLocalClock, 1000);

  // Click to hide/show
  localClock.addEventListener("click", () => {
    clockVisible = !clockVisible;
    localStorage.setItem("sp_clock_visible", clockVisible);
    updateLocalClock();
  });

  // Load world clocks from localStorage
  loadWorldClocks();
});


function updateLocalClock() {
  const timeEl  = document.getElementById("localTime");
  const labelEl = document.getElementById("localLabel");
  if (!timeEl) return;

  if (!clockVisible) {
    timeEl.textContent = "--:--:--";
    return;
  }

  const now = new Date();
  timeEl.textContent  = formatClockTime(now, clockFormat);

  if (labelEl) {
    // Show timezone abbreviation e.g. BST, GMT
    labelEl.textContent = getTimezoneAbbreviation();
  }
}


function formatClockTime(date, format) {
  const options = {
    hour:   "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: format === "12",
  };
  return date.toLocaleTimeString("en-GB", options);
}


function getTimezoneAbbreviation() {
  return Intl.DateTimeFormat("en-GB", { timeZoneName: "short" })
    .formatToParts(new Date())
    .find(part => part.type === "timeZoneName")?.value || "Local";
}


function loadWorldClocks() {
  const container = document.getElementById("worldClocks");
  if (!container) return;

  // Load saved world clocks from localStorage
  const saved = localStorage.getItem("sp_world_clocks");
  if (!saved) return;

  let worldClocks;
  try {
    worldClocks = JSON.parse(saved);
  } catch {
    return;
  }

  // Render each world clock
  worldClocks.forEach(timezone => {
    const clockEl = createWorldClock(timezone);
    container.appendChild(clockEl);
  });

  // Update world clocks every second
  setInterval(() => updateWorldClocks(worldClocks), 1000);
}


function createWorldClock(timezone) {
  const div = document.createElement("div");
  div.className      = "clock";
  div.dataset.timezone = timezone;

  const timeEl  = document.createElement("span");
  timeEl.className   = "clock__time";

  const labelEl = document.createElement("span");
  labelEl.className  = "clock__label";

  // Get the abbreviation for this timezone
  try {
    labelEl.textContent = Intl.DateTimeFormat("en-GB", {
      timeZone:     timezone,
      timeZoneName: "short",
    }).formatToParts(new Date())
      .find(p => p.type === "timeZoneName")?.value || timezone;
  } catch {
    labelEl.textContent = timezone;
  }

  div.appendChild(timeEl);
  div.appendChild(labelEl);
  return div;
}


function updateWorldClocks(timezones) {
  timezones.forEach(timezone => {
    const clockEl = document.querySelector(`[data-timezone="${timezone}"]`);
    if (!clockEl) return;

    const timeEl = clockEl.querySelector(".clock__time");
    if (!timeEl) return;

    try {
      timeEl.textContent = new Date().toLocaleTimeString("en-GB", {
        timeZone: timezone,
        hour:     "2-digit",
        minute:   "2-digit",
        second:   "2-digit",
        hour12:   clockFormat === "12",
      });
    } catch {
      timeEl.textContent = "--:--:--";
    }
  });
}


// Exported so settings.js can call these when preferences change
function setClockFormat(format) {
  clockFormat = format;
  localStorage.setItem("sp_clock_format", format);
}


function addWorldClock(timezone) {
  const saved = localStorage.getItem("sp_world_clocks");
  let clocks  = saved ? JSON.parse(saved) : [];

  if (!clocks.includes(timezone)) {
    clocks.push(timezone);
    localStorage.setItem("sp_world_clocks", JSON.stringify(clocks));
  }

  const container = document.getElementById("worldClocks");
  if (container) {
    const clockEl = createWorldClock(timezone);
    container.appendChild(clockEl);
    updateWorldClocks([timezone]);
  }
}


function removeWorldClock(timezone) {
  const saved = localStorage.getItem("sp_world_clocks");
  let clocks  = saved ? JSON.parse(saved) : [];
  clocks      = clocks.filter(tz => tz !== timezone);
  localStorage.setItem("sp_world_clocks", JSON.stringify(clocks));

  const clockEl = document.querySelector(`[data-timezone="${timezone}"]`);
  if (clockEl) clockEl.remove();
}