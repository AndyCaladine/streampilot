# =============================================================
# utils/commands_handler.py — Chat command dispatcher
# =============================================================

import logging
import os
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from utils.twitch import get_stream

logger = logging.getLogger(__name__)

DYNAMIC_VARS = ["{game}", "{uptime}", "{viewers}", "{channel}", "{followers}"]


class _PgConn:
    """Minimal wrapper so psycopg2 behaves like sqlite3 for our purposes."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def _get_direct_connection():
    """
    Open a direct DB connection outside Flask request context.
    The IRC relay runs in a background thread where Flask's g is unavailable.
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url and database_url.startswith("postgres"):
        raw = psycopg2.connect(
            database_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        raw.autocommit = False
        return _PgConn(raw), "%s", "postgres"
    else:
        db_path = database_url if database_url else os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "instance", "database.db"
        )
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn, "?", "sqlite"


def _resolve_response(response: str, channel_login: str, access_token: str) -> str:
    if not any(v in response for v in DYNAMIC_VARS):
        return response

    stream = None
    try:
        stream = get_stream(access_token, channel_login)
    except Exception as e:
        logger.warning(f"[COMMANDS] Could not fetch stream data: {e}")

    if "{channel}" in response:
        response = response.replace("{channel}", channel_login)
    if "{game}" in response:
        game = stream.get("game_name", "Unknown") if stream else "Unknown"
        response = response.replace("{game}", game)
    if "{viewers}" in response:
        viewers = str(stream.get("viewer_count", 0)) if stream else "0"
        response = response.replace("{viewers}", viewers)
    if "{uptime}" in response:
        uptime = "offline"
        if stream and stream.get("started_at"):
            try:
                started = datetime.fromisoformat(
                    stream["started_at"].replace("Z", "+00:00")
                )
                delta = datetime.now(timezone.utc) - started
                h, m = divmod(delta.seconds // 60, 60)
                uptime = f"{h}h {m}m" if h else f"{m}m"
            except Exception:
                pass
        response = response.replace("{uptime}", uptime)
    if "{followers}" in response:
        response = response.replace("{followers}", "N/A")

    return response


def handle_command(channel_id: int, channel_login: str,
                   access_token: str, username: str,
                   is_mod: bool, message: str,
                   socketio=None) -> None:
    if not message.startswith("!"):
        return

    trigger = message.strip().split()[0].lower().lstrip("!")

    try:
        conn, p, db_type = _get_direct_connection()
    except Exception as e:
        logger.error(f"[COMMANDS] DB connection failed: {e}")
        return

    try:
        cmd = conn.execute(
            f"""
            SELECT id, response, cooldown_s, mod_only, enabled, last_used_at
            FROM commands
            WHERE channel_id = {p}
              AND LOWER(trigger) = {p}
              AND enabled = 1
              AND deleted_at IS NULL
            """,
            (channel_id, trigger)
        ).fetchone()
    except Exception as e:
        logger.error(f"[COMMANDS] Query error: {e}")
        conn.close()
        return

    if not cmd:
        conn.close()
        return

    # Mod-only check
    if cmd["mod_only"] and not is_mod:
        logger.debug(f"[COMMANDS] {username} tried mod-only command {trigger}")
        conn.close()
        return

    # Cooldown check
    if cmd["last_used_at"]:
        try:
            last = datetime.fromisoformat(str(cmd["last_used_at"]))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < cmd["cooldown_s"]:
                logger.debug(f"[COMMANDS] {trigger} on cooldown ({elapsed:.0f}s/{cmd['cooldown_s']}s)")
                conn.close()
                return
        except Exception as e:
            logger.warning(f"[COMMANDS] Could not parse last_used_at: {e}")

    conn.close()

    # Resolve dynamic variables
    response = _resolve_response(cmd["response"], channel_login, access_token)

    # Send to Twitch chat
    from utils.twitch_chat import send_message
    sent = send_message(channel_id, response)

    if sent:
        try:
            conn2, p2, _ = _get_direct_connection()
            conn2.execute(
                f"""
                UPDATE commands
                SET use_count = use_count + 1,
                    last_used_at = CURRENT_TIMESTAMP
                WHERE id = {p2}
                """,
                (cmd["id"],)
            )
            conn2.commit()
            conn2.close()
        except Exception as e:
            logger.error(f"[COMMANDS] Failed to update use_count: {e}")
        logger.info(f"[COMMANDS] Fired {trigger} for {username} in #{channel_login}")
        if socketio:
            socketio.emit(
                "chat_message",
                {
                    "username": channel_login,
                    "display_name": channel_login,
                    "message": response,
                    "color": "#9146ff",
                    "badges": ["broadcaster"],
                    "is_mod": False,
                    "is_bot": True,
                },
                room=f"channel_{channel_id}"
            )
    else:
        logger.warning(f"[COMMANDS] Failed to send response for {trigger}")