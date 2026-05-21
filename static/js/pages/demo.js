/* =============================================================
   demo.js — simulation / demo mode for StreamPilot dashboard
   Loads from /static/data/demo.json
   Called by dashboard.js — never used in production flows
   ============================================================= */

let demoData     = null;
let demoRunning  = false;
let demoIntervals = [];


// ---- Boot --------------------------------------------------
async function loadDemoData() {
  if (demoData) return demoData;
  const res = await fetch("/static/data/demo.json");
  demoData  = await res.json();
  return demoData;
}


// ---- Start / Stop ------------------------------------------
async function startDemo() {
  if (demoRunning) return;
  if (!document.getElementById("chatMessages")) return;
  await loadDemoData();
  demoRunning = true;

  demoIntervals.push(setInterval(fireChatMessage, randomBetween(3000, 8000)));
  demoIntervals.push(setInterval(fireEvent,       randomBetween(25000, 45000)));
  demoIntervals.push(setInterval(fireCommand,     randomBetween(15000, 30000)));
}


function stopDemo() {
  demoRunning = false;
  demoIntervals.forEach(t => clearInterval(t));
  demoIntervals = [];
  clearChatFeed();
  clearRecentCommands();
}


// ---- Chat --------------------------------------------------
function fireChatMessage() {
  if (!demoData || !demoRunning) return;
  const streamer = randomFrom(demoData.streamers);
  const message  = randomFrom(demoData.chat_messages);
  renderChatMessage(streamer, message);
}


function renderChatMessage(streamer, message, isBot = false) {
  const feed = document.getElementById("chatMessages");
  if (!feed) return;

  const empty = feed.querySelector(".empty-state");
  if (empty) empty.remove();

  const item = document.createElement("div");
  item.className = "chat-message";

  const badgesHtml = (streamer.badges || []).map(b => badgeSvg(b)).join("");

  item.innerHTML = `
    <span class="chat-message__badges">${badgesHtml}</span>
    <span class="chat-message__name" style="color:${isBot ? "var(--accent)" : streamer.colour}">
      ${isBot ? "StreamPilotBot" : streamer.name}
    </span>
    <span class="chat-message__colon">:</span>
    <span class="chat-message__text">${message}</span>
  `;

  feed.appendChild(item);
  feed.scrollTop = feed.scrollHeight;

  while (feed.children.length > 100) {
    feed.removeChild(feed.firstChild);
  }
}


function clearChatFeed() {
  const feed = document.getElementById("chatMessages");
  if (!feed) return;
  feed.innerHTML = '<p class="empty-state">Chat will appear here when you go live.</p>';
}


// ---- Events ------------------------------------------------
function fireEvent() {
  if (!demoData || !demoRunning) return;
  const eventType = randomFrom(demoData.events);
  const user      = randomFrom(eventType.users);

  let detail = { type: eventType.type, user };

  if (eventType.type === "raid")     detail.viewers = randomFrom(eventType.viewers);
  if (eventType.type === "bits")     detail.bits    = randomFrom(eventType.amounts);
  if (eventType.type === "resub")    detail.months  = randomFrom(eventType.months);
  if (eventType.type === "gift_sub") detail.amount  = randomFrom(eventType.amounts);

  document.dispatchEvent(new CustomEvent("sp:alert", { detail }));

  const chatMsg = buildEventChatMessage(detail);
  if (chatMsg) {
    renderChatMessage(
      { name: "StreamPilotBot", colour: "var(--accent)", badges: ["bot"] },
      chatMsg,
      true
    );
  }
}


function buildEventChatMessage(detail) {
  const msgs = {
    follow:   `Welcome to the channel, ${detail.user}! 👋`,
    sub_t1:   `${detail.user} just subscribed! Welcome to the gang! 🎉`,
    sub_t2:   `${detail.user} subscribed at Tier 2! Massive! 🌟`,
    sub_t3:   `${detail.user} subscribed at Tier 3! Absolute legend! ✨`,
    gift_sub: `${detail.user} gifted ${detail.amount || 1} sub(s) to the community! 🎁`,
    resub:    `${detail.user} has resubscribed for ${detail.months} months! 🔄`,
    raid:     `${detail.user} is raiding with ${detail.viewers} viewers! Welcome raiders! ⚔️`,
    bits:     `${detail.user} cheered ${detail.bits} bits! 💎`,
  };
  return msgs[detail.type] || null;
}


// ---- Commands ----------------------------------------------
function fireCommand() {
  if (!demoData || !demoRunning) return;
  const command  = randomFrom(demoData.commands);
  const caller   = randomFrom(demoData.streamers.filter(s => !s.badges.includes("broadcaster")));
  const response = demoData.bot_responses[command.trigger];

  renderChatMessage(caller, command.trigger);
  addRecentCommand(command.trigger, caller.name);

  if (response) {
    setTimeout(() => {
      if (!demoRunning) return;
      renderChatMessage(
        { name: "StreamPilotBot", colour: "var(--accent)", badges: ["bot"] },
        response,
        true
      );
    }, randomBetween(800, 2000));
  }
}


function addRecentCommand(trigger, username) {
  const el = document.getElementById("recentCommands");
  if (!el) return;

  const empty = el.querySelector(".empty-state");
  if (empty) empty.remove();

  const item = document.createElement("div");
  item.className = "recent-command-item";
  item.innerHTML = `
    <span class="recent-command-item__trigger">${trigger}</span>
    <span class="recent-command-item__user">by ${username}</span>
    <span class="recent-command-item__time">${new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</span>
  `;

  el.insertBefore(item, el.firstChild);

  while (el.children.length > 10) {
    el.removeChild(el.lastChild);
  }
}


function clearRecentCommands() {
  const el = document.getElementById("recentCommands");
  if (!el) return;
  el.innerHTML = '<p class="empty-state">No commands used yet.</p>';
}


// ---- Badge SVGs --------------------------------------------
function badgeSvg(badge) {
  const badges = {
    broadcaster: `<svg class="chat-badge chat-badge--broadcaster" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" title="Broadcaster">
      <rect width="18" height="18" rx="4" fill="#E91916"/>
      <path d="M5 13V7l4 3 4-3v6" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`,
    mod: `<svg class="chat-badge chat-badge--mod" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" title="Moderator">
      <rect width="18" height="18" rx="4" fill="#00AD03"/>
      <path d="M9 3l1.8 3.6L15 7.5l-3 2.9.7 4.1L9 12.4l-3.7 2.1.7-4.1L3 7.5l4.2-.9L9 3z" fill="white"/>
    </svg>`,
    vip: `<svg class="chat-badge chat-badge--vip" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" title="VIP">
      <rect width="18" height="18" rx="4" fill="#E005B9"/>
      <text x="9" y="13" font-size="8" font-weight="bold" fill="white" text-anchor="middle" font-family="Arial">VIP</text>
    </svg>`,
    sub: `<svg class="chat-badge chat-badge--sub" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" title="Subscriber">
      <rect width="18" height="18" rx="4" fill="#9147FF"/>
      <path d="M9 4l1.4 2.8L14 7.6l-2.5 2.4.6 3.4L9 11.8l-3.1 1.6.6-3.4L4 7.6l3.6-.8L9 4z" fill="white"/>
    </svg>`,
    bot: `<svg class="chat-badge chat-badge--bot" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" title="Bot">
      <rect width="18" height="18" rx="4" fill="#5865F2"/>
      <text x="9" y="13" font-size="7" font-weight="bold" fill="white" text-anchor="middle" font-family="Arial">BOT</text>
    </svg>`,
  };
  return badges[badge] || "";
}


// ---- Utilities ---------------------------------------------
function randomFrom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomBetween(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}