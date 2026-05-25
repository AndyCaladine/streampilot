/* =============================================================
   theme.js — light / dark mode toggle + colour scheme
   Saves to localStorage always.
   Saves to the server only when the user is logged in.
   ============================================================= */

const COLOURS = ["default", "blue", "green", "red", "pink", "yellow", "mono", "teal"];

document.addEventListener("DOMContentLoaded", () => {

  // ---- Initialise LED arc state on load -------------------
  const arcOnLoad = document.getElementById("ledArc");
  if (arcOnLoad) {
    const loadedTheme = document.documentElement.getAttribute("data-theme") || "light";
    if (loadedTheme === "dark") {
      arcOnLoad.setAttribute("class", "led-toggle__arc led-full-on");
    }
  }

  // ---- Theme toggle ---------------------------------------
  const toggle = document.getElementById("themeToggleInput");
  const label  = document.getElementById("themeToggle");

  if (toggle && label) {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    toggle.checked = current === "dark";

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
  markActiveSwatch(currentColour, false);

  document.querySelectorAll("[data-colour-pick]").forEach(swatch => {
    swatch.addEventListener("click", () => {
      const colour = swatch.dataset.colourPick;
      applyColour(colour, true);
      markActiveSwatch(colour, true);

      const loggedIn = document.getElementById("themeToggle")?.dataset.loggedIn === "true";
      if (loggedIn) {
        savePreference("colour_scheme", colour);
      }
    });
  });

  // ---- Load saved colour from server ----------------------
  const loggedIn = document.getElementById("themeToggle")?.dataset.loggedIn === "true";
  if (loggedIn) {
    apiRequest("/api/preferences", "GET").then(prefs => {
      if (prefs.colour_scheme) {
        applyColour(prefs.colour_scheme, true);
        markActiveSwatch(prefs.colour_scheme, false);
      }
      if (prefs.theme) {
        applyTheme(prefs.theme);
      }
    }).catch(() => {});
  }

});


function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("sp_theme", theme);

  const toggle = document.getElementById("themeToggleInput");
  if (toggle) toggle.checked = theme === "dark";

  // LED sweep animation
  const arc = document.getElementById("ledArc");
  if (arc) {
    arc.setAttribute("class", "led-toggle__arc");
    setTimeout(() => {
      if (theme === "dark") {
        arc.setAttribute("class", "led-toggle__arc led-sweep-on");
        setTimeout(() => {
          arc.setAttribute("class", "led-toggle__arc led-full-on");
        }, 850);
      } else {
        arc.setAttribute("class", "led-toggle__arc led-sweep-off");
        setTimeout(() => {
          arc.setAttribute("class", "led-toggle__arc");
        }, 850);
      }
    }, 20);
  }
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


function markActiveSwatch(colour, showToast = false) {
  document.querySelectorAll("[data-colour-pick]").forEach(swatch => {
    swatch.classList.toggle("active", swatch.dataset.colourPick === colour);
  });

  if (!showToast) return;

  const confirm = document.getElementById("colourConfirm");
  if (!confirm) return;

  const labels = {
    default: "Default", blue: "Blue", green: "Green", red: "Red",
    pink: "Pink", yellow: "Yellow", mono: "Mono", teal: "Teal",
  };

  confirm.innerHTML = `
    <span>✓ Colour theme changed to ${labels[colour] || colour}</span>
    <span class="colour-confirm__close" id="colourConfirmClose">✕</span>
  `;
  confirm.style.display = "flex";

  document.getElementById("colourConfirmClose").addEventListener("click", () => {
    confirm.style.display = "none";
  });

  clearTimeout(window._colourConfirmTimer);
  window._colourConfirmTimer = setTimeout(() => {
    confirm.style.display = "none";
  }, 3000);
}


async function savePreference(preference, value) {
  try {
    await apiRequest("/api/preferences", "POST", { preference, value });
  } catch (error) {
    console.warn("Could not save preference to server:", error.message);
  }
}