/* =============================================================
   websocket.js — WebSocket connection manager
   Connects to the server via Socket.IO and dispatches
   incoming events as CustomEvents so page scripts can
   subscribe without coupling to this file.

   Usage in a page script:
     document.addEventListener("sp:alert", (e) => {
       console.log(e.detail); // the alert data
     });
   ============================================================= */

const SP = {
  socket: null,

  init() {
    this.socket = io({ transports: ["websocket"] });

    this.socket.on("connect", () => {
      console.log("[SP] WebSocket connected");
      document.dispatchEvent(new CustomEvent("sp:connected"));
    });

    this.socket.on("disconnect", () => {
      console.log("[SP] WebSocket disconnected");
      document.dispatchEvent(new CustomEvent("sp:disconnected"));
    });

    this.socket.on("alert", (data) => {
      document.dispatchEvent(new CustomEvent("sp:alert", { detail: data }));
    });

    this.socket.on("panel_show", (data) => {
      document.dispatchEvent(new CustomEvent("sp:panel_show", { detail: data }));
    });

    this.socket.on("panel_hide", (data) => {
      document.dispatchEvent(new CustomEvent("sp:panel_hide", { detail: data }));
    });

    this.socket.on("celebrate", (data) => {
      document.dispatchEvent(new CustomEvent("sp:celebrate", { detail: data }));
    });

    this.socket.on("account_switched", (data) => {
      document.dispatchEvent(new CustomEvent("sp:account_switched", { detail: data }));
    });
  },

  /**
   * Fire a test alert to the OBS overlay.
   * Called by the test buttons on the alerts page.
   */
  testAlert(type) {
    if (!this.socket) return;
    this.socket.emit("test_alert", { type });
  },

  /**
   * Switch to a different channel account without logging out.
   * Called by the switch role option in the user menu.
   */
  switchAccount(channelId) {
    if (!this.socket) return;
    this.socket.emit("switch_account", { channel_id: channelId });
  },
};