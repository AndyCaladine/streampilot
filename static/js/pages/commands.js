/* =============================================================
   commands.js — commands management page
   ============================================================= */

async function initCommands() {
  if (!document.getElementById("commandsList")) return;

  await loadCommands();

  document.getElementById("newCommandBtn")
    ?.addEventListener("click", () => {
      document.getElementById("newCommandForm").style.display = "block";
      document.getElementById("commandTrigger").focus();
    });

  document.getElementById("cancelNewCommand")
    ?.addEventListener("click", () => {
      document.getElementById("newCommandForm").style.display = "none";
      clearNewCommandForm();
    });

  document.getElementById("saveNewCommand")
    ?.addEventListener("click", saveCommand);

  document.getElementById("exportCommandsBtn")
    ?.addEventListener("click", exportCommandsCSV);
}

document.addEventListener("DOMContentLoaded", initCommands);
document.addEventListener("htmx:afterSwap",   initCommands);


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

    listEl.innerHTML = commands.map(command => `
      <div class="command-item" data-id="${command.id}">
        <span class="command-item__trigger">!${command.trigger}</span>
        <span class="command-item__response">${command.response}</span>
        <div class="command-item__actions">
          <label class="toggle" title="${command.enabled ? "Enabled" : "Disabled"}">
            <input type="checkbox"
                   ${command.enabled ? "checked" : ""}
                   onchange="toggleCommand(${command.id}, this.checked)">
            <span class="toggle-slider"></span>
          </label>
          <button class="btn btn--ghost btn--sm btn--icon"
                  onclick="deleteCommand(${command.id})"
                  title="Delete command">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" width="14" height="14">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14H6L5 6"/>
              <path d="M10 11v6M14 11v6"/>
              <path d="M9 6V4h6v2"/>
            </svg>
          </button>
        </div>
      </div>
    `).join("");

  } catch (error) {
    showToast("Could not load commands.", "error");
    console.error("[Commands]", error.message);
  }
}


async function saveCommand() {
  const trigger  = document.getElementById("commandTrigger").value.trim();
  const response = document.getElementById("commandResponse").value.trim();
  const cooldown = parseInt(document.getElementById("commandCooldown").value) || 30;

  if (!trigger || !response) {
    showToast("Please enter a trigger and response.", "warn");
    return;
  }

  try {
    await apiRequest("/api/commands", "POST", { trigger, response, cooldown_s: cooldown });
    showToast(`Command !${trigger} created.`, "success");
    document.getElementById("newCommandForm").style.display = "none";
    clearNewCommandForm();
    await loadCommands();
  } catch (error) {
    showToast(error.message, "error");
  }
}


async function toggleCommand(commandId, enabled) {
  try {
    await apiRequest(`/api/commands/${commandId}`, "PUT", { enabled: enabled ? 1 : 0 });
  } catch (error) {
    showToast("Could not update command.", "error");
  }
}


async function deleteCommand(commandId) {
  if (!confirm("Delete this command?")) return;
  try {
    await apiRequest(`/api/commands/${commandId}`, "DELETE");
    showToast("Command deleted.", "success");
    await loadCommands();
  } catch (error) {
    showToast(error.message, "error");
  }
}


function clearNewCommandForm() {
  document.getElementById("commandTrigger").value  = "";
  document.getElementById("commandResponse").value = "";
  document.getElementById("commandCooldown").value = "30";
}


async function exportCommandsCSV() {
  try {
    const commands = await apiRequest("/api/commands");
    if (commands.length === 0) {
      showToast("No commands to export.", "warn");
      return;
    }

    const header = ["Trigger", "Response", "Cooldown (s)", "Enabled"];
    const rows   = commands.map(command => [
      `!${command.trigger}`,
      `"${command.response.replace(/"/g, '""')}"`,
      command.cooldown_s,
      command.enabled ? "Yes" : "No",
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