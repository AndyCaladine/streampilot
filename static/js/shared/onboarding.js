/* =============================================================
   onboarding.js — first-time dashboard tutorial
   Tooltip-based walkthrough of key UI elements.
   Saves completion state to user_preferences via API.
   Can be manually retriggered from Settings.
   ============================================================= */

const ONBOARDING_STEPS = [
  {
    target:    "#userMenuBtn",
    title:     "Day / Night mode",
    body:      "Open this menu to switch between light and dark mode. Your preference is saved to your account so it follows you across devices.",
    position:  "bottom-left",
    openMenu:  true,
  },
  {
    target:    "#userMenuBtn",
    title:     "Colour themes",
    body:      "Pick an accent colour to match your stream's brand. Eight themes available — Default, Blue, Green, Red, Pink, Yellow, Mono and Teal. Saved to your account automatically.",
    position:  "bottom-left",
    openMenu:  true,
  },
  {
    target:    "#userMenuBtn",
    title:     "Change your password",
    body:      "Open this menu and click Change Password to update your StreamPilot password at any time.",
    position:  "bottom-left",
    openMenu:  false,
  },
  {
    target:    ".topbar__stats",
    title:     "Stream stats",
    body:      "Viewers, Followers, Subscribers and Uptime update live when you're streaming. Click any pill to hide it — useful when screen sharing or going facecam-only.",
    position:  "bottom",
  },
  {
    target:    "#simulateBtn",
    title:     "Simulate Live",
    body:      "Hit this to fill the dashboard with realistic stream activity — chat messages, events, commands — so you can test settings without being live.",
    position:  "bottom",
  },
  {
    target:    "#eventFeed",
    title:     "Event Feed",
    body:      "Follows, subscriptions, raids, bits and gift subs all appear here in real time during your stream.",
    position:  "right",
  },
  {
    target:    "#chatMessages",
    title:     "Chat Feed",
    body:      "Your live Twitch chat appears here on the dashboard so you never have to switch tabs mid-stream.",
    position:  "top",
  },
  {
    target:    "a[href='/alerts']",
    title:     "Alerts",
    body:      "Configure your stream alerts here — follows, subs, raids and more. Wire them to OBS via a browser source URL.",
    position:  "right",
  },
  {
    target:    "a[href='/panels']",
    title:     "Panels",
    body:      "Set up timed on-screen information panels — follower goals, social links, command lists. They appear in OBS on a schedule you control.",
    position:  "right",
  },
  {
    target:    "a[href='/team']",
    title:     "Flight Crew",
    body:      "Manage your mod team here. Assign roles, invite mods, and control who has access to your StreamPilot dashboard.",
    position:  "right",
  },
{
    target:    "a[href='/settings']",
    title:     "Settings",
    body:      "OBS overlay URLs, connection status, clock preferences and appearance settings all live here.",
    position:  "top",
  },
  {
    target:    "#sidebarCollapseBtn",
    title:     "Collapse the sidebar",
    body:      "Click here to collapse the sidebar to icons only — gives you more screen real estate during a stream.",
    position:  "top",
  },
];

let currentStep  = 0;
let overlay      = null;
let tooltip      = null;
let highlightBox = null;


// ---- Public API --------------------------------------------
async function startOnboarding(force = false) {
  if (!force) {
    try {
      const prefs = await apiRequest("/api/preferences", "GET");
      if (prefs.onboarding_complete === "true") return;
    } catch {
      return;
    }
  }

  currentStep = 0;
  buildOverlay();
  showStep(currentStep);
}


async function completeOnboarding() {
  destroyOverlay();
  try {
    await apiRequest("/api/preferences", "POST", {
      preference: "onboarding_complete",
      value:      "true",
    });
  } catch {
    // Fail silently — don't block the user
  }
}


async function resetOnboarding() {
  try {
    await apiRequest("/api/preferences", "POST", {
      preference: "onboarding_complete",
      value:      "false",
    });
  } catch {}
}


// ---- Build DOM ---------------------------------------------
function buildOverlay() {
  // Backdrop
  overlay = document.createElement("div");
  overlay.id = "onboardingOverlay";
  overlay.className = "onboarding-overlay";

  // Highlight cutout
  highlightBox = document.createElement("div");
  highlightBox.className = "onboarding-highlight";
  overlay.appendChild(highlightBox);

  // Tooltip
  tooltip = document.createElement("div");
  tooltip.className = "onboarding-tooltip";
  tooltip.innerHTML = `
    <button class="onboarding-tooltip__close" id="onboardingClose" aria-label="Close tutorial">✕</button>
    <div class="onboarding-tooltip__step" id="onboardingStepLabel"></div>
    <h3 class="onboarding-tooltip__title" id="onboardingTitle"></h3>
    <p class="onboarding-tooltip__body" id="onboardingBody"></p>
    <div class="onboarding-tooltip__footer">
      <button class="onboarding-tooltip__skip" id="onboardingSkip">Don't show again</button>
      <div class="onboarding-tooltip__nav">
        <button class="btn btn--secondary btn--sm" id="onboardingPrev">Previous</button>
        <button class="btn btn--primary btn--sm" id="onboardingNext">Next</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
  document.body.appendChild(tooltip);

  // Events
  document.getElementById("onboardingClose").addEventListener("click", completeOnboarding);
  document.getElementById("onboardingSkip").addEventListener("click", completeOnboarding);
  document.getElementById("onboardingPrev").addEventListener("click", () => {
    if (currentStep > 0) { currentStep--; showStep(currentStep); }
  });
  document.getElementById("onboardingNext").addEventListener("click", () => {
    if (currentStep < ONBOARDING_STEPS.length - 1) {
      currentStep++;
      showStep(currentStep);
    } else {
      completeOnboarding();
    }
  });
}


// ---- Show a step -------------------------------------------
function showStep(index) {
  const step   = ONBOARDING_STEPS[index];
  const target = document.querySelector(step.target);

  document.getElementById("onboardingStepLabel").textContent = `${index + 1} of ${ONBOARDING_STEPS.length}`;
  document.getElementById("onboardingTitle").textContent     = step.title;
  document.getElementById("onboardingBody").textContent      = step.body;
  document.getElementById("onboardingPrev").style.visibility = index === 0 ? "hidden" : "visible";
  document.getElementById("onboardingNext").textContent      = index === ONBOARDING_STEPS.length - 1 ? "Finish" : "Next";

  const dropdown = document.getElementById("userMenuDropdown");
  if (step.openMenu) {
    if (dropdown) dropdown.classList.add("open");
  } else {
    if (dropdown) dropdown.classList.remove("open");
  }

  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => {
      positionHighlight(target);
      positionTooltip(target, step.position);
    }, 150);
  } else {
    if (index < ONBOARDING_STEPS.length - 1) {
      currentStep++;
      showStep(currentStep);
    } else {
      completeOnboarding();
    }
  }
}


// ---- Position highlight box --------------------------------
function positionHighlight(target) {
  const rect    = target.getBoundingClientRect();
  const padding = 6;

  highlightBox.style.top    = `${rect.top    - padding + window.scrollY}px`;
  highlightBox.style.left   = `${rect.left   - padding}px`;
  highlightBox.style.width  = `${rect.width  + padding * 2}px`;
  highlightBox.style.height = `${rect.height + padding * 2}px`;
}


// ---- Position tooltip relative to target -------------------
function positionTooltip(target, position) {
  const rect        = target.getBoundingClientRect();
  const tipW        = 320;
  const tipH        = tooltip.offsetHeight || 180;
  const gap         = 16;
  const padding     = 6;

  let top, left;

  switch (position) {
    case "bottom":
      top  = rect.bottom + padding + gap + window.scrollY;
      left = rect.left + rect.width / 2 - tipW / 2;
      break;
    case "bottom-left":
      top  = rect.bottom + padding + gap + window.scrollY;
      left = rect.right - tipW;
      break;
    case "top":
      top  = rect.top - padding - gap - tipH + window.scrollY;
      left = rect.left + rect.width / 2 - tipW / 2;
      break;
    case "right":
      top  = rect.top + rect.height / 2 - tipH / 2 + window.scrollY;
      left = rect.right + padding + gap;
      break;
    default:
      top  = rect.bottom + padding + gap + window.scrollY;
      left = rect.left;
  }

  // Clamp to viewport
  left = Math.max(12, Math.min(left, window.innerWidth - tipW - 12));
  top  = Math.max(12, top);

  tooltip.style.top   = `${top}px`;
  tooltip.style.left  = `${left}px`;
  tooltip.style.width = `${tipW}px`;
}


// ---- Destroy -----------------------------------------------
function destroyOverlay() {
  if (overlay)  { overlay.remove();  overlay  = null; }
  if (tooltip)  { tooltip.remove();  tooltip  = null; }
  highlightBox = null;

  // Close user menu if open
  const dropdown = document.getElementById("userMenuDropdown");
  if (dropdown) dropdown.classList.remove("open");
}