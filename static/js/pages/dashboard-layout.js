/* =============================================================
   dashboard-layout.js — dashboard widget layout system
   
   Handles:
     - Base config (default layout)
     - Loading saved layout from server
     - Saving layout to server
     - Rendering widgets into the grid
     - Drag and drop reordering
   ============================================================= */

// ---- Base config -------------------------------------------
// This is what every new user gets and what Reset restores.
// w = width in grid columns (max 2), h = height in grid rows

const DASHBOARD_BASE_CONFIG = [
  { id: "event-feed",      title: "Event Feed",      w: 1, h: 2 },
  { id: "active-goals",    title: "Active Goals",    w: 1, h: 1 },
  { id: "recent-commands", title: "Recent Commands", w: 1, h: 1 },
  { id: "overlay-status",  title: "Overlay Status",  w: 1, h: 1 },
  { id: "chat-feed",       title: "Chat Feed",       w: 2, h: 2 },
];

// ---- All available widgets ---------------------------------
// This registry grows as new widgets are built.
// Only widgets in this list can be added to the dashboard.

const WIDGET_REGISTRY = [
  { id: "event-feed",      title: "Event Feed",      description: "Live stream events — follows, subs, raids" },
  { id: "active-goals",    title: "Active Goals",    description: "Your current channel goals" },
  { id: "recent-commands", title: "Recent Commands", description: "Commands used in chat recently" },
  { id: "overlay-status",  title: "Overlay Status",  description: "OBS browser source connection status" },
  { id: "chat-feed",       title: "Chat Feed",       description: "Live chat with send capability" },
];

// ---- State -------------------------------------------------
let currentLayout  = null;
let isEditMode     = false;

// ---- Boot --------------------------------------------------
async function initDashboardLayout() {
  if (!document.getElementById("dashboardGrid")) return;

  const saved = await loadLayout();
  currentLayout = saved || [...DASHBOARD_BASE_CONFIG];
  renderDashboard();
}

document.addEventListener("DOMContentLoaded", initDashboardLayout);
document.addEventListener("htmx:afterSwap",   initDashboardLayout);


// ---- Load layout from server -------------------------------
async function loadLayout() {
  try {
    const data = await apiRequest("/api/dashboard/layout");
    if (data.layout) {
      return JSON.parse(data.layout);
    }
    return null;
  } catch (error) {
    console.warn("[Layout] Could not load layout:", error.message);
    return null;
  }
}


// ---- Save layout to server ---------------------------------
async function saveLayout() {
  try {
    await apiRequest("/api/dashboard/layout", "POST", {
      layout: JSON.stringify(currentLayout)
    });
  } catch (error) {
    console.warn("[Layout] Could not save layout:", error.message);
    showToast("Could not save layout.", "error");
  }
}


// ---- Render dashboard --------------------------------------
function renderDashboard() {
  const grid = document.getElementById("dashboardGrid");
  if (!grid) return;

  grid.innerHTML = "";

  currentLayout.forEach(widget => {
    const el = createWidgetEl(widget);
    grid.appendChild(el);
  });

  if (isEditMode) enableDragDrop();
}


// ---- Create widget element ---------------------------------
function createWidgetEl(widget) {
  const el = document.createElement("div");
  el.className        = "dashboard-widget";
  el.dataset.widgetId = widget.id;
  el.dataset.w        = widget.w;
  el.dataset.h        = widget.h;

  // Span columns if w = 2
  if (widget.w === 2) el.classList.add("dashboard-widget--wide");
  if (widget.h === 2) el.classList.add("dashboard-widget--tall");

  el.innerHTML = `
    <div class="dashboard-widget__inner" id="widget-${widget.id}">
      ${getWidgetContent(widget.id)}
    </div>
    ${isEditMode ? `
    <div class="dashboard-widget__edit-handle">
      <span class="dashboard-widget__drag-icon">⠿</span>
      <span class="dashboard-widget__title">${widget.title}</span>
      <button class="dashboard-widget__remove" data-widget-id="${widget.id}" title="Remove widget">✕</button>
    </div>` : ""}
  `;

  if (isEditMode) {
    el.querySelector(".dashboard-widget__remove")
      .addEventListener("click", () => removeWidget(widget.id));
  }

  return el;
}


// ---- Widget content ----------------------------------------
function getWidgetContent(id) {
  switch (id) {
    case "event-feed":
      return `
        <div class="card">
          <div class="card__header">
            <h2 class="card__title">Event <span class="card__title-accent">Feed</span></h2>
            <span class="card__badge" id="eventCount">0</span>
          </div>
          <div class="card__body">
            <div class="event-feed" id="eventFeed">
              <p class="empty-state">No events yet — go live to see activity here.</p>
            </div>
          </div>
        </div>`;

    case "active-goals":
      return `
        <div class="card">
          <div class="card__header">
            <h2 class="card__title">Active <span class="card__title-accent">Goals</span></h2>
          </div>
          <div class="card__body">
            <div id="goalsFeed">
              <p class="empty-state">No active goals.</p>
            </div>
          </div>
        </div>`;

    case "recent-commands":
      return `
        <div class="card">
          <div class="card__header">
            <h2 class="card__title">Recent <span class="card__title-accent">Commands</span></h2>
          </div>
          <div class="card__body">
            <div id="recentCommands">
              <p class="empty-state">No commands used yet.</p>
            </div>
          </div>
        </div>`;

    case "overlay-status":
      return `
        <div class="card">
          <div class="card__header">
            <h2 class="card__title">Overlay <span class="card__title-accent">Status</span></h2>
          </div>
          <div class="card__body">
            <div class="overlay-status-list" id="overlayStatusList">
              <div class="overlay-status-item">
                <span class="overlay-status-item__name">Alerts</span>
                <span class="overlay-status-item__status" id="overlayStatusAlerts">Checking...</span>
              </div>
              <div class="overlay-status-item">
                <span class="overlay-status-item__name">Panels</span>
                <span class="overlay-status-item__status" id="overlayStatusPanels">Checking...</span>
              </div>
              <div class="overlay-status-item">
                <span class="overlay-status-item__name">Celebrations</span>
                <span class="overlay-status-item__status" id="overlayStatusCelebrations">Checking...</span>
              </div>
            </div>
          </div>
        </div>`;

    case "chat-feed":
      return `
        <div class="card dashboard-chat">
          <div class="card__header">
            <h2 class="card__title">Chat <span class="card__title-accent">Feed</span></h2>
            <div class="card__actions">
              <button class="btn btn--secondary btn--sm" id="pauseChat">Pause</button>
              <button class="btn btn--danger btn--sm" id="clearChat">Clear</button>
            </div>
          </div>
          <div class="card__body chat-body" id="chatMessages">
            <p class="empty-state">Chat will appear here when you go live.</p>
          </div>
          <div class="card__footer">
            <input type="text" class="form-input" id="chatInput" placeholder="Send a message as your bot...">
            <button class="btn btn--primary" id="chatSend">Send</button>
          </div>
        </div>`;

    default:
      return `<div class="card"><div class="card__body"><p class="empty-state">Unknown widget.</p></div></div>`;
  }
}


// ---- Remove widget -----------------------------------------
function removeWidget(widgetId) {
  currentLayout = currentLayout.filter(w => w.id !== widgetId);
  renderDashboard();
  saveLayout();
  showToast("Widget removed.", "success");
}


// ---- Drag and drop -----------------------------------------
function enableDragDrop() {
  const grid = document.getElementById("dashboardGrid");
  if (!grid) return;

  let dragging = null;

  grid.querySelectorAll(".dashboard-widget").forEach(widget => {
    widget.setAttribute("draggable", "true");

    widget.addEventListener("dragstart", () => {
      dragging = widget;
      setTimeout(() => widget.classList.add("dragging"), 0);
    });

    widget.addEventListener("dragend", () => {
      widget.classList.remove("dragging");
      dragging = null;
      updateLayoutFromDOM();
      saveLayout();
    });

    widget.addEventListener("dragover", (e) => {
      e.preventDefault();
      const target = e.currentTarget;
      if (target !== dragging) {
        const rect     = target.getBoundingClientRect();
        const midpoint = rect.top + rect.height / 2;
        if (e.clientY < midpoint) {
          grid.insertBefore(dragging, target);
        } else {
          grid.insertBefore(dragging, target.nextSibling);
        }
      }
    });
  });
}


// ---- Sync layout order from DOM ----------------------------
function updateLayoutFromDOM() {
  const grid = document.getElementById("dashboardGrid");
  if (!grid) return;

  const newOrder = [];
  grid.querySelectorAll(".dashboard-widget").forEach(el => {
    const existing = currentLayout.find(w => w.id === el.dataset.widgetId);
    if (existing) newOrder.push(existing);
  });
  currentLayout = newOrder;
}

// ---- Edit mode ---------------------------------------------
function enterEditMode() {
  if (isEditMode) return;
  isEditMode = true;
  renderDashboard();

  // Add toolbar above the grid
  const grid = document.getElementById("dashboardGrid");
  const toolbar = document.createElement("div");
  toolbar.className = "dashboard-edit-toolbar";
  toolbar.id = "editToolbar";
  toolbar.innerHTML = `
    <span class="dashboard-edit-toolbar__msg">
      ✏️ Edit mode — drag to reorder, ✕ to remove
    </span>
    <button class="btn btn--secondary btn--sm" id="addWidgetBtn">
      + Add Widget
    </button>
    <button class="btn btn--primary btn--sm" id="doneEditBtn">
      Done
    </button>
  `;
  grid.parentElement.insertBefore(toolbar, grid);

  // Add edit-mode class to all widgets
  document.querySelectorAll(".dashboard-widget")
    .forEach(w => w.classList.add("edit-mode"));

  // Wire up buttons
  document.getElementById("doneEditBtn")
    .addEventListener("click", exitEditMode);

  document.getElementById("addWidgetBtn")
    .addEventListener("click", showWidgetPicker);
}


function exitEditMode() {
  isEditMode = false;
  document.getElementById("editToolbar")?.remove();
  renderDashboard();
  showToast("Layout saved.", "success");
}


// ---- Edit layout button — wired on every dashboard load ----
function wireEditLayoutBtn() {
  const btn = document.getElementById("editLayoutBtn");
  if (!btn) return;

  btn.addEventListener("click", () => {
    if (simulateInterval || window._spSimulating) {
      showToast("Cannot edit layout while live. Stop the stream first.", "warn");
      return;
    }
    enterEditMode();
  });
}

document.addEventListener("DOMContentLoaded", wireEditLayoutBtn);
document.addEventListener("htmx:afterSwap",   wireEditLayoutBtn);


// ---- Widget picker -----------------------------------------
function showWidgetPicker() {
  document.getElementById("widgetPickerModal")?.remove();

  const alreadyAdded = currentLayout.map(w => w.id);
  const available    = WIDGET_REGISTRY.filter(w => !alreadyAdded.includes(w.id));

  const modal = document.createElement("div");
  modal.id = "widgetPickerModal";
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
      <h3 style="font-size:16px;font-weight:600;margin-bottom:16px;color:var(--text)">
        Add Widget
      </h3>
      ${available.length === 0
        ? `<p class="empty-state">All available widgets are already on your dashboard.</p>`
        : available.map(w => `
          <div style="
            display:flex;align-items:center;justify-content:space-between;
            padding:10px 0;border-bottom:1px solid var(--border);gap:12px;
          ">
            <div>
              <div style="font-size:14px;font-weight:500;color:var(--text)">${w.title}</div>
              <div style="font-size:12px;color:var(--muted)">${w.description}</div>
            </div>
            <button class="btn btn--secondary btn--sm" onclick="addWidget('${w.id}')">
              Add
            </button>
          </div>
        `).join("")
      }
      <div style="margin-top:16px;display:flex;justify-content:flex-end">
        <button class="btn btn--secondary btn--sm" id="closePickerBtn">Close</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  document.getElementById("closePickerBtn")
    .addEventListener("click", () => modal.remove());
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.remove();
  });
}


// ---- Add widget --------------------------------------------
function addWidget(widgetId) {
  document.getElementById("widgetPickerModal")?.remove();

  const widget = WIDGET_REGISTRY.find(w => w.id === widgetId);
  if (!widget) return;

  currentLayout.push({ ...widget });
  renderDashboard();
  saveLayout();

  // Re-enter edit mode so user can keep editing
  enterEditMode();
  showToast(`${widget.title} added.`, "success");
}