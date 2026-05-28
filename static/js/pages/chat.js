/* =============================================================
   chat.js — live chat page
   Phase 2: Twitch EventSub integration
   ============================================================= */

function initChat() {
  if (!document.querySelector(".chat-card")) return;
  // Chat functionality coming in Phase 2
}

document.addEventListener("DOMContentLoaded", initChat);
document.addEventListener("htmx:afterSwap",   initChat);