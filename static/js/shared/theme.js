/* =============================================================
   theme.js — light / dark mode toggle
   Handles the theme toggle button in the dashboard topbar.
   Saves preference to localStorage and to the server.
   ============================================================= */

document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("themeToggle");
  if (!themeToggle) return;

  // Apply saved theme on load
  const savedTheme = localStorage.getItem("sp_theme") || "light";
  applyTheme(savedTheme);

  // Toggle on button click
  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next    = current === "light" ? "dark" : "light";
    applyTheme(next);
    saveThemePreference(next);
  });
});


function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("sp_theme", theme);
}


async function saveThemePreference(theme) {
  // Save to server so it persists across devices
  try {
    await apiRequest("/api/preferences", "POST", {
      preference: "theme",
      value:      theme,
    });
  } catch (error) {
    // Non-critical — localStorage already saved it locally
    console.warn("Could not save theme preference to server:", error.message);
  }
}