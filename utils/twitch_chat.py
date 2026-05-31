# =============================================================
# utils/twitch_chat.py — Twitch IRC relay
#
# Connects to Twitch IRC server-side using the streamer's
# stored OAuth token. Receives messages and pushes them to
# the browser via Flask-SocketIO. Also handles sending
# messages from the dashboard back to Twitch chat.
#
# One IRC connection per active channel, stored in _connections.
# Connection starts when the streamer opens the chat page and
# stops when they disconnect from the SocketIO room.
# =============================================================

import threading
import socket
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Active IRC connections keyed by channel_id
_connections: dict = {}
_lock = threading.Lock()

# =============================================================
# IRC message parser
# =============================================================

def _parse_irc_message(raw: str) -> dict | None:
    """
    Parse a raw Twitch IRC line into a structured dict.
    Returns None for non-PRIVMSG lines we don't care about.

    Twitch IRC format:
    @tags :user!user@user.tmi.twitch.tv PRIVMSG #channel :message
    """
    raw = raw.strip()

    # Extract tags if present
    tags = {}
    if raw.startswith("@"):
        tag_str, raw = raw[1:].split(" ", 1)
        for pair in tag_str.split(";"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                tags[k] = v

    # Match PRIVMSG lines only
    match = re.match(
        r":(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #(\w+) :(.+)",
        raw
    )
    if not match:
        return None

    login = match.group(1)
    message_text = match.group(3)

    # Build badge list from tags
    badges = []
    badge_str = tags.get("badges", "")
    if "broadcaster" in badge_str:
        badges.append("broadcaster")
    if "moderator" in badge_str:
        badges.append("moderator")
    if "vip" in badge_str:
        badges.append("vip")
    if "subscriber" in badge_str:
        badges.append("subscriber")

    # Determine role for colour coding
    if "broadcaster" in badges:
        role = "broadcaster"
    elif "moderator" in badges:
        role = "moderator"
    elif "vip" in badges:
        role = "vip"
    elif "subscriber" in badges:
        role = "subscriber"
    else:
        role = "viewer"

    return {
        "id": tags.get("id", ""),
        "twitch_id": tags.get("user-id", ""),
        "login": login,
        "display_name": tags.get("display-name", login),
        "color": tags.get("color", ""),
        "badges": badges,
        "role": role,
        "message": message_text,
        "emotes": tags.get("emotes", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bits": tags.get("bits", "0"),
    }

# =============================================================
# IRC connection class
# =============================================================

class TwitchIRCRelay:
    """
    Manages a single Twitch IRC connection for one channel.
    Runs in a background thread, parsing messages and emitting
    them to the SocketIO room for that channel.
    """

    TWITCH_IRC_HOST = "irc.chat.twitch.tv"
    TWITCH_IRC_PORT = 6667

    def __init__(self, channel_id: int, channel_login: str,
                 access_token: str, bot_login: str, socketio):
        self.channel_id = channel_id
        self.channel_login = channel_login.lower().lstrip("#")
        self.access_token = access_token
        self.bot_login = bot_login.lower()
        self.socketio = socketio
        self._socket = None
        self._thread = None
        self._running = False

    def start(self):
        """Start the IRC relay in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, daemon=True, name=f"irc-{self.channel_id}"
        )
        self._thread.start()
        logger.info(f"IRC relay started for channel {self.channel_login}")

    def stop(self):
        """Disconnect and stop the relay thread."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        logger.info(f"IRC relay stopped for channel {self.channel_login}")

    def send(self, message: str):
        """Send a message to Twitch chat."""
        if not self._socket or not self._running:
            return False
        try:
            self._socket.sendall(
                f"PRIVMSG #{self.channel_login} :{message}\r\n".encode("utf-8")
            )
            return True
        except Exception as e:
            logger.error(f"IRC send error: {e}")
            return False

    def _connect(self):
        """Open the socket and authenticate with Twitch IRC."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.TWITCH_IRC_HOST, self.TWITCH_IRC_PORT))
        s.settimeout(300)  # 5 min timeout — Twitch sends PINGs to keep alive

        def raw(line):
            s.sendall(f"{line}\r\n".encode("utf-8"))

        raw(f"PASS oauth:{self.access_token}")
        raw(f"NICK {self.bot_login}")
        raw("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership")
        raw(f"JOIN #{self.channel_login}")

        self._socket = s
        logger.info(f"IRC connected to #{self.channel_login}")

    def _run(self):
        """Main loop — read lines and emit to SocketIO."""
        try:
            self._connect()

        except Exception as e:
            logger.error(f"IRC connect failed for {self.channel_login}: {e}")
            self._emit_status("error", str(e))
            return

        self._emit_status("connected")
        buffer = ""

        while self._running:
            try:
                data = self._socket.recv(4096).decode("utf-8", errors="replace")
                if not data:
                    break

                buffer += data
                lines = buffer.split("\r\n")
                buffer = lines.pop()  # Keep incomplete line in buffer

                for line in lines:
                    self._handle_line(line)

            except socket.timeout:
                # Send PING to keep the connection alive
                try:
                    self._socket.sendall(b"PING :tmi.twitch.tv\r\n")
                except Exception:
                    break
            except Exception as e:
                if self._running:
                    logger.error(f"IRC recv error: {e}")
                break

        self._emit_status("disconnected")

    def _handle_line(self, line: str):
        """Handle one raw IRC line."""
        if not line:
            return

        # Respond to server PINGs immediately
        if line.startswith("PING"):
            try:
                self._socket.sendall(b"PONG :tmi.twitch.tv\r\n")
            except Exception:
                pass
            return

        # Parse and emit chat messages
        msg = _parse_irc_message(line)
        if msg:
            self.socketio.emit(
                "chat_message",
                msg,
                room=f"channel_{self.channel_id}"
            )
            # Dispatch to command handler if message starts with !
            if msg.get("message", "").startswith("!"):
                try:
                    from utils.commands_handler import handle_command
                    handle_command(
                        channel_id=self.channel_id,
                        channel_login=self.channel_login,
                        access_token=self.access_token,
                        username=msg.get("username", ""),
                        is_mod=msg.get("is_mod", False),
                        message=msg.get("message", ""),
                        socketio=self.socketio
                    )
                except Exception as e:
                    logger.warning(f"[COMMANDS] Handler error: {e}")

    def _emit_status(self, status: str, error: str = ""):
        """Emit connection status to the channel room."""
        self.socketio.emit(
            "chat_status",
            {"status": status, "error": error},
            room=f"channel_{self.channel_id}"
        )


# =============================================================
# Public API — called from ws_events.py
# =============================================================

def start_relay(channel_id: int, channel_login: str,
                access_token: str, bot_login: str, socketio) -> bool:
    """
    Start an IRC relay for a channel if one isn't already running.
    Returns True if started or already running.
    """
    with _lock:
        if channel_id in _connections:
            return True  # Already connected

        relay = TwitchIRCRelay(
            channel_id, channel_login, access_token, bot_login, socketio
        )
        relay.start()
        _connections[channel_id] = relay
        return True


def stop_relay(channel_id: int):
    """Stop and remove the IRC relay for a channel."""
    with _lock:
        relay = _connections.pop(channel_id, None)
        if relay:
            relay.stop()


def send_message(channel_id: int, message: str) -> bool:
    """
    Send a message to a channel's Twitch chat.
    Returns False if no active relay exists.
    """
    with _lock:
        relay = _connections.get(channel_id)
    if not relay:
        return False
    return relay.send(message)


def is_connected(channel_id: int) -> bool:
    """Check if a relay is active for this channel."""
    with _lock:
        return channel_id in _connections