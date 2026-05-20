/* =============================================================
   theme.js — light / dark mode toggle + colour scheme
   Saves to localStorage always.
   Saves to the server only when the user is logged in.
   ============================================================= */

const COLOURS = ["default", "blue", "green", "red", "pink", "yellow", "mono", "teal"];

document.addEventListener("DOMContentLoaded", () => {

  // ---- Theme toggle ---------------------------------------
  const toggle = document.getElementById("themeToggleInput");
  const label  = document.getElementById("themeToggle");

  if (toggle && label) {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    toggle.checked = current === "dark";
    label.classList.toggle("dark", current === "dark");

    toggle.addEventListener("change", () => {
      const next = toggle.checked ? "dark" : "light";
      applyTheme(next);

      if (label.dataset.loggedIn === "true") {
        savePreference("theme", next);
      }
    });
  }

  // ---- Colour pickers -------------------------------------
  const currentColour = localStorage.getItem("sp_colour") || "default";
  applyColour(currentColour, false);
  markActiveSwatch(currentColour);

  // Bind all swatches (dropdown + settings)
  document.querySelectorAll("[data-colour-pick]").forEach(swatch => {
    swatch.addEventListener("click", () => {
      const colour = swatch.dataset.colourPick;
      applyColour(colour, true);
      markActiveSwatch(colour);

      const loggedIn = document.getElementById("themeToggle")?.dataset.loggedIn === "true";
      if (loggedIn) {
        savePreference("colour_scheme", colour);
      }
    });
  });

});


function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("sp_theme", theme);

  const toggle = document.getElementById("themeToggleInput");
  const label  = document.getElementById("themeToggle");
  if (toggle) toggle.checked = theme === "dark";
  if (label)  label.classList.toggle("dark", theme === "dark");
}


function applyColour(colour, save) {
  if (colour && colour !== "default") {
    document.documentElement.setAttribute("data-colour", colour);
  } else {
    document.documentElement.removeAttribute("data-colour");
  }
  if (save) {
    localStorage.setItem("sp_colour", colour);
  }
}


function markActiveSwatch(colour) {
  document.querySelectorAll("[data-colour-pick]").forEach(swatch => {
    swatch.classList.toggle("active", swatch.dataset.colourPick === colour);
  });
}


async function savePreference(preference, value) {
  try {
    await apiRequest("/api/preferences", "POST", { preference, value });
  } catch (error) {
    console.warn("Could not save preference to server:", error.message);
  }
}

// ---- Load saved colour from server ----------------------
  const loggedIn = document.getElementById("themeToggle")?.dataset.loggedIn === "true";
  if (loggedIn) {
    apiRequest("/api/preferences", "GET").then(prefs => {
      if (prefs.colour_scheme) {
        applyColour(prefs.colour_scheme, true);
        markActiveSwatch(prefs.colour_scheme);
      }
      if (prefs.theme) {
        applyTheme(prefs.theme);
      }
    }).catch(() => {});
  }