/* =============================================================
   commands.js — commands management page
   ============================================================= */

let editingId  = null;
let deletingId = null;

async function initCommands() {
  if (!document.getElementById("commandsList")) return;

  await loadCommands();
  bindCommandEvents();
}

document.addEventListener("DOMContentLoaded", initCommands);
document.addEventListener("htmx:afterSwap",   initCommands);


// =============================================================
// Event bindings
// =============================================================

function bindCommandEvents() {
  // New command button — opens modal in create mode
  document.getElementById("newCommandBtn")
    ?.addEventListener("click", () => openCommandModal());

  // Modal save
  document.getElementById("commandSaveBtn")
    ?.addEventListener("click", saveCommand);

  // Modal cancel
  document.getElementById("commandCancelBtn")
    ?.addEventListener("click", closeCommandModal);

  // Close modal on backdrop click
  document.getElementById("commandModal")
    ?.addEventListener("click", e => {
      if (e.target === e.currentTarget) closeCommandModal();
    });

  // Delete confirm / cancel
  document.getElementById("deleteConfirmBtn")
    ?.addEventListener("click", confirmDelete);
  document.getElementById("deleteCancelBtn")
    ?.addEventListener("click", closeDeleteModal);
  document.getElementById("deleteModal")
    ?.addEventListener("click", e => {
      if (e.target === e.currentTarget) closeDeleteModal();
    });

  // Delegated edit / delete / toggle on list
  document.getElementById("commandsList")
    ?.addEventListener("click", e => {
      const editBtn   = e.target.closest(".cmd-edit");
      const deleteBtn = e.target.closest(".cmd-delete");
      if (editBtn)   openCommandModal(editBtn.dataset.id);
      if (deleteBtn) openDeleteModal(deleteBtn.dataset.id, deleteBtn.dataset.trigger);
    });

  document.getElementById("commandsList")
    ?.addEventListener("change", e => {
      const toggle = e.target.closest(".cmd-toggle");
      if (toggle) toggleCommand(parseInt(toggle.dataset.id), toggle.checked);
    });
}


// =============================================================
// Load and render
// =============================================================

async function loadCommands() {
  try {
    const commands = await apiRequest("/api/commands");

    const countEl = document.getElementById("commandCount");
    if (countEl) countEl.textContent = commands.length;

    const listEl = document.getElementById("commandsList");
    if (!listEl) return;

    if (commands.length === 0) {
      listEl.innerHTML = `<p class="empty-state">No commands yet. Create your first one above.</p>`;
      return;
    }

    listEl.innerHTML = commands.map(cmd => `
      <div class="command-row" data-id="${cmd.id}"
           data-trigger="${escapeHtml(cmd.trigger)}"
           data-response="${escapeHtml(cmd.response)}"
           data-cooldown="${cmd.cooldown_s}"
           data-mod-only="${cmd.mod_only}"
           data-enabled="${cmd.enabled}">
        <div class="command-row__trigger">
          <code class="command-trigger">${escapeHtml(cmd.trigger)}</code>
          ${cmd.mod_only ? '<span class="badge badge--mod">Mod only</span>' : ''}
        </div>
        <div class="command-row__response">${escapeHtml(cmd.response)}</div>
        <div class="command-row__meta">
          <span class="command-meta-item" title="Cooldown">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            ${cmd.cooldown_s}s
          </span>
          <span class="command-meta-item" title="Total uses">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            ${cmd.use_count}
          </span>
        </div>
        <div class="command-row__actions">
          <label class="toggle" title="${cmd.enabled ? 'Enabled' : 'Disabled'}">
            <input type="checkbox" class="toggle__input cmd-toggle"
                   data-id="${cmd.id}" ${cmd.enabled ? 'checked' : ''}>
            <span class="toggle__slider"></span>
          </label>
          <button class="btn btn--secondary btn--sm cmd-edit" data-id="${cmd.id}">Edit</button>
          <button class="btn btn--danger btn--sm cmd-delete"
                  data-id="${cmd.id}"
                  data-trigger="${escapeHtml(cmd.trigger)}">Delete</button>
        </div>
      </div>
    `).join("");

  } catch (error) {
    showToast("Could not load commands.", "error");
    console.error("[Commands]", error.message);
  }
}


// =============================================================
// Modal — create / edit
// =============================================================

function openCommandModal(id = null) {
  editingId = id;
  const title = document.getElementById("commandModalTitle");

  // Reset form
  document.getElementById("cmdTrigger").value    = "";
  document.getElementById("cmdResponse").value   = "";
  document.getElementById("cmdCooldown").value   = 30;
  document.getElementById("cmdModOnly").checked  = false;
  document.getElementById("cmdEnabled").checked  = true;

  if (id) {
    title.textContent = "Edit Command";
    const row = document.querySelector(`.command-row[data-id="${id}"]`);
    if (row) {
      document.getElementById("cmdTrigger").value   = row.dataset.trigger;
      document.getElementById("cmdResponse").value  = row.dataset.response;
      document.getElementById("cmdCooldown").value  = row.dataset.cooldown;
      document.getElementById("cmdModOnly").checked = row.dataset.modOnly === "1";
      document.getElementById("cmdEnabled").checked = row.dataset.enabled === "1";
    }
  } else {
    title.textContent = "New Command";
  }

  document.getElementById("commandModal").hidden = false;
  document.getElementById("cmdTrigger").focus();
}

function closeCommandModal() {
  document.getElementById("commandModal").hidden = true;
  editingId = null;
}


// =============================================================
// Save (create or update)
// =============================================================

async function saveCommand() {
  const trigger    = document.getElementById("cmdTrigger").value.trim();
  const response   = document.getElementById("cmdResponse").value.trim();
  const cooldown_s = parseInt(document.getElementById("cmdCooldown").value) || 30;
  const mod_only   = document.getElementById("cmdModOnly").checked ? 1 : 0;
  const enabled    = document.getElementById("cmdEnabled").checked ? 1 : 0;

  if (!trigger || !response) {
    showToast("Please enter a trigger and response.", "warn");
    return;
  }

  const payload = { trigger, response, cooldown_s, mod_only, enabled };

  try {
    if (editingId) {
      await apiRequest(`/api/commands/${editingId}`, "PUT", payload);
      showToast("Command updated.", "success");
    } else {
      await apiRequest("/api/commands", "POST", payload);
      showToast(`Command ${trigger} created.`, "success");
    }
    closeCommandModal();
    await loadCommands();
  } catch (error) {
    showToast(error.message || "Could not save command.", "error");
  }
}


// =============================================================
// Toggle enabled
// =============================================================

async function toggleCommand(commandId, enabled) {
  try {
    await apiRequest(`/api/commands/${commandId}`, "PUT", { enabled: enabled ? 1 : 0 });
    showToast(enabled ? "Command enabled." : "Command disabled.", "success");
  } catch (error) {
    showToast("Could not update command.", "error");
    await loadCommands(); // Revert UI
  }
}


// =============================================================
// Delete modal
// =============================================================

function openDeleteModal(id, trigger) {
  deletingId = id;
  document.getElementById("deleteTriggerName").textContent = trigger;
  document.getElementById("deleteModal").hidden = false;
}

function closeDeleteModal() {
  document.getElementById("deleteModal").hidden = true;
  deletingId = null;
}

async function confirmDelete() {
  if (!deletingId) return;
  try {
    await apiRequest(`/api/commands/${deletingId}`, "DELETE");
    showToast("Command deleted.", "success");
    closeDeleteModal();
    await loadCommands();
  } catch (error) {
    showToast(error.message || "Could not delete command.", "error");
  }
}


// =============================================================
// CSV export
// =============================================================

async function exportCommandsCSV() {
  try {
    const commands = await apiRequest("/api/commands");
    if (commands.length === 0) {
      showToast("No commands to export.", "warn");
      return;
    }

    const header = ["Trigger", "Response", "Cooldown (s)", "Mod Only", "Enabled", "Uses"];
    const rows   = commands.map(cmd => [
      cmd.trigger,
      `"${cmd.response.replace(/"/g, '""')}"`,
      cmd.cooldown_s,
      cmd.mod_only  ? "Yes" : "No",
      cmd.enabled   ? "Yes" : "No",
      cmd.use_count
    ]);

    const csv  = [header, ...rows].map(row => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);

    const link    = document.createElement("a");
    link.href     = url;
    link.download = "streampilot-commands.csv";
    link.click();
    URL.revokeObjectURL(url);
    showToast("Commands exported.", "success");
  } catch (error) {
    showToast("Could not export commands.", "error");
  }
}


// =============================================================
// Helpers
// =============================================================

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}