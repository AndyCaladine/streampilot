/* =============================================================
   theme.js — light / dark mode toggle
   Saves to localStorage always.
   Saves to the server only when the user is logged in.
   ============================================================= */

document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("themeToggle");
  if (!themeToggle) return;

  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next    = current === "light" ? "dark" : "light";
    applyTheme(next);

    if (themeToggle.dataset.loggedIn === "true") {
      saveThemePreference(next);
    }
  });
});


function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("sp_theme", theme);
}


async function saveThemePreference(theme) {
  try {
    await apiRequest("/api/preferences", "POST", {
      preference: "theme",
      value:      theme,
    });
  } catch (error) {
    console.warn("Could not save theme preference to server:", error.message);
  }
}