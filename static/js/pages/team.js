/* =============================================================
   team.js — team management page
   Handles crew display, pending invites, Twitch import and
   the invite modal flow.
   ============================================================= */

function initTeam() {
  if (!document.getElementById("activeList")) return;

  loadTeamMembers();
  bindImportButton();
  bindModal();
}

// =============================================================
// Load current crew and pending invites
// =============================================================
async function loadTeamMembers() {
  try {
    const res  = await fetch("/api/team/members");
    const data = await res.json();

    renderActiveMembers(data.active  || []);
    renderPendingInvites(data.pending || []);
  } catch (err) {
    console.error("Failed to load team members", err);
  }
}

function renderActiveMembers(members) {
  const el    = document.getElementById("activeList");
  const badge = document.getElementById("activeCount");
  badge.textContent = members.length;

  if (!members.length) {
    el.innerHTML = '<p class="empty-state">No crew members yet. Invite your first mod below.</p>';
    return;
  }

  el.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Member</th>
          <th>Twitch</th>
          <th>Role</th>
          <th>Joined</th>
        </tr>
      </thead>
      <tbody>
        ${members.map(m => `
          <tr>
            <td>
              <div style="display:flex; align-items:center; gap:0.5rem;">
                ${m.platform_avatar_url ? `<img src="${m.platform_avatar_url}" width="28" height="28" style="border-radius:50%;">` : ""}
                <span>${m.display_name}</span>
              </div>
            </td>
            <td style="color: var(--text-muted);">@${m.platform_login || "—"}</td>
            <td><span class="badge badge--${m.role === "co_pilot" ? "accent" : "default"}">${m.role === "co_pilot" ? "Co-Pilot" : "Mod"}</span></td>
            <td style="color: var(--text-muted); font-size:0.85rem;">${formatDate(m.accepted_at)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderPendingInvites(invites) {
  const el    = document.getElementById("pendingList");
  const badge = document.getElementById("pendingCount");
  badge.textContent = invites.length;

  if (!invites.length) {
    el.innerHTML = '<p class="empty-state">No pending invites.</p>';
    return;
  }

  el.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Twitch</th>
          <th>Role</th>
          <th>Sent to</th>
          <th>Expires</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${invites.map(i => `
          <tr>
            <td>@${i.twitch_login || "—"}</td>
            <td><span class="badge badge--${i.role === "co_pilot" ? "accent" : "default"}">${i.role === "co_pilot" ? "Co-Pilot" : "Mod"}</span></td>
            <td style="color: var(--text-muted);">${i.email || "Link only"}</td>
            <td style="color: var(--text-muted); font-size:0.85rem;">${formatDate(i.expires_at)}</td>
            <td>
              <button class="btn btn--ghost btn--sm cancel-invite-btn" data-id="${i.id}">Cancel</button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;

  document.querySelectorAll(".cancel-invite-btn").forEach(btn => {
    btn.addEventListener("click", () => cancelInvite(btn.dataset.id));
  });
}

async function cancelInvite(inviteId) {
  if (!confirm("Cancel this invite?")) return;
  try {
    await fetch(`/api/team/invite/${inviteId}`, { method: "DELETE" });
    loadTeamMembers();
  } catch (err) {
    console.error("Failed to cancel invite", err);
  }
}

// =============================================================
// Import from Twitch
// =============================================================
function bindImportButton() {
  const btn = document.getElementById("importTwitchBtn");
  if (!btn) return;
  btn.addEventListener("click", loadTwitchMods);
}

async function loadTwitchMods() {
  const btn = document.getElementById("importTwitchBtn");
  const el  = document.getElementById("twitchModList");
  btn.disabled    = true;
  btn.textContent = "Loading...";

  try {
    const res  = await fetch("/api/team/twitch-mods");
    const data = await res.json();
    renderTwitchMods(data.mods || []);
  } catch (err) {
    el.innerHTML = '<p class="empty-state">Failed to load Twitch mod list.</p>';
    console.error(err);
  } finally {
    btn.disabled    = false;
    btn.textContent = "Refresh Twitch Mod List";
  }
}

function renderTwitchMods(mods) {
  const el = document.getElementById("twitchModList");

  if (!mods.length) {
    el.innerHTML = '<p class="empty-state">All your Twitch mods are already in StreamPilot or have pending invites.</p>';
    return;
  }

  el.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Twitch User</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${mods.map(m => `
          <tr>
            <td>
              <div style="display:flex; align-items:center; gap:0.5rem;">
                <span>${m.display_name}</span>
                <span style="color: var(--text-muted); font-size:0.85rem;">@${m.twitch_login}</span>
              </div>
            </td>
            <td style="text-align:right;">
              <button class="btn btn--primary btn--sm invite-twitch-btn"
                data-user-id="${m.twitch_user_id}"
                data-login="${m.twitch_login}"
                data-name="${m.display_name}">
                Invite
              </button>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;

  document.querySelectorAll(".invite-twitch-btn").forEach(btn => {
    btn.addEventListener("click", () => openInviteModal(
      btn.dataset.userId,
      btn.dataset.login,
      btn.dataset.name
    ));
  });
}

// =============================================================
// Invite modal
// =============================================================
function bindModal() {
  document.getElementById("inviteModalClose")?.addEventListener("click",  closeInviteModal);
  document.getElementById("inviteModalCancel")?.addEventListener("click", closeInviteModal);
  document.getElementById("inviteSubmitBtn")?.addEventListener("click",   submitInvite);
  document.getElementById("copyLinkBtn")?.addEventListener("click",       copyInviteLink);

  document.getElementById("inviteModal")?.addEventListener("click", e => {
    if (e.target.id === "inviteModal") closeInviteModal();
  });
}

function openInviteModal(userId, login, name) {
  document.getElementById("inviteTwitchUserId").value = userId;
  document.getElementById("inviteTwitchLogin").value  = login;
  document.getElementById("inviteDisplayName").value  = name;
  document.getElementById("inviteModalName").textContent = `${name} (@${login})`;
  document.getElementById("inviteEmail").value        = "";
  document.getElementById("inviteLinkResult").style.display = "none";
  document.getElementById("inviteSubmitBtn").textContent    = "Send Invite";
  document.getElementById("inviteSubmitBtn").disabled       = false;
  document.getElementById("inviteModal").style.display      = "flex";
}

function closeInviteModal() {
  document.getElementById("inviteModal").style.display = "none";
  loadTeamMembers();
}

async function submitInvite() {
  const btn = document.getElementById("inviteSubmitBtn");
  btn.disabled    = true;
  btn.textContent = "Sending...";

  const payload = {
    twitch_user_id: document.getElementById("inviteTwitchUserId").value,
    twitch_login:   document.getElementById("inviteTwitchLogin").value,
    display_name:   document.getElementById("inviteDisplayName").value,
    email:          document.getElementById("inviteEmail").value.trim(),
    role:           document.getElementById("inviteRole").value,
  };

  try {
    const res  = await fetch("/api/team/invite", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "Failed to send invite.");
      btn.disabled    = false;
      btn.textContent = "Send Invite";
      return;
    }

    if (data.sent_via === "link") {
      document.getElementById("inviteLinkInput").value        = data.invite_url;
      document.getElementById("inviteLinkResult").style.display = "block";
      btn.textContent = "Done";
    } else {
      btn.textContent = "Invite Sent!";
      setTimeout(closeInviteModal, 1500);
    }
  } catch (err) {
    console.error("Invite error", err);
    btn.disabled    = false;
    btn.textContent = "Send Invite";
  }
}

function copyInviteLink() {
  const input = document.getElementById("inviteLinkInput");
  navigator.clipboard.writeText(input.value).then(() => {
    const btn = document.getElementById("copyLinkBtn");
    btn.textContent = "Copied!";
    setTimeout(() => btn.textContent = "Copy", 2000);
  });
}

// =============================================================
// Helpers
// =============================================================
function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric", month: "short", year: "numeric"
    });
  } catch {
    return dateStr;
  }
}

document.addEventListener("DOMContentLoaded", initTeam);
document.addEventListener("htmx:afterSwap",   initTeam);