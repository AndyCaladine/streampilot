/* =============================================================
   theme.js — light / dark mode toggle
   Saves to localStorage always.
   Saves to the server only when the user is logged in.
   ============================================================= */

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("themeToggleInput");
  const label  = document.getElementById("themeToggle");
  if (!toggle || !label) return;

  const current = document.documentElement.getAttribute("data-theme") || "light";
  toggle.checked = current === "dark";
  label.classList.toggle("dark", current === "dark");

  toggle.addEventListener("change", () => {
    const next = toggle.checked ? "dark" : "light";
    applyTheme(next);

    if (label.dataset.loggedIn === "true") {
      saveThemePreference(next);
    }
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


async function saveThemePreference(theme) {
  try {
    await apiRequest("/api/preferences", "POST", {
      preference: "theme",
      value: theme,
    });
  } catch (error) {
    console.warn("Could not save theme preference to server:", error.message);
  }
}