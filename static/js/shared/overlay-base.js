/* =============================================================
   overlay-base.js — WebSocket base for OBS overlay pages
   Connects to the server, joins the channel room, and
   sends a heartbeat every 30 seconds so the dashboard
   can show "Connected" status.

   OVERLAY_TOKEN, OVERLAY_TYPE and OVERLAY_CHANNEL must be
   defined in the template before this script loads.
   ============================================================= */

const OverlaySocket = {
  socket: null,

  init() {
    this.socket = io({ transports: ["websocket"] });

    this.socket.on("connect", () => {
      console.log(`[Overlay] Connected — joining as ${OVERLAY_TYPE}`);

      // Join the channel room
      this.socket.emit("join_overlay", {
        token:        OVERLAY_TOKEN,
        overlay_type: OVERLAY_TYPE,
      });

      // Start heartbeat
      this._startHeartbeat();
    });

    this.socket.on("overlay_ready", (data) => {
      console.log("[Overlay] Ready:", data);
      document.dispatchEvent(new CustomEvent("overlay:ready", { detail: data }));
    });

    this.socket.on("alert", (data) => {
      document.dispatchEvent(new CustomEvent("overlay:alert", { detail: data }));
    });

    this.socket.on("panel_show", (data) => {
      document.dispatchEvent(new CustomEvent("overlay:panel_show", { detail: data }));
    });

    this.socket.on("panel_hide", (data) => {
      document.dispatchEvent(new CustomEvent("overlay:panel_hide", { detail: data }));
    });

    this.socket.on("celebrate", (data) => {
      document.dispatchEvent(new CustomEvent("overlay:celebrate", { detail: data }));
    });
  },

  _startHeartbeat() {
    // Send heartbeat every 30 seconds
    setInterval(() => {
      if (this.socket && this.socket.connected) {
        this.socket.emit("overlay_heartbeat", {
          token:        OVERLAY_TOKEN,
          overlay_type: OVERLAY_TYPE,
        });
      }
    }, 30000);
  },
};

// Initialise when the page loads
document.addEventListener("DOMContentLoaded", () => {
  OverlaySocket.init();
});