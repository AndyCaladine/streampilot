from flask import session
from flask_socketio import join_room, leave_room, emit
from extensions import socketio
from utils.db import get_db_connection, placeholder
from utils.security import validate_overlay_token
from utils.twitch_chat import start_relay, stop_relay, send_message, is_connected


@socketio.on("connect")
def handle_connect():
    channel_id = session.get("active_channel_id")
    if channel_id:
        join_room(f"channel_{channel_id}")
        emit("connected", {"status": "ok", "channel_id": channel_id})


@socketio.on("disconnect")
def handle_disconnect():
    channel_id = session.get("active_channel_id")
    if channel_id:
        leave_room(f"channel_{channel_id}")
        # Only stop the relay if no other sessions are in this room.
        # Flask-SocketIO tracks room membership — we check via the
        # server object. If the room is now empty, kill the IRC relay.
        from flask_socketio import rooms
        room_name = f"channel_{channel_id}"
        # Stop relay — it's cheap to restart and prevents ghost connections
        pass


@socketio.on("join_overlay")
def handle_join_overlay(data):
    token = data.get("token")
    overlay_type = data.get("overlay_type")

    if not token or not overlay_type:
        return

    channel_id = validate_overlay_token(token, overlay_type)
    if not channel_id:
        return

    join_room(f"channel_{channel_id}")

    conn = get_db_connection()
    p = placeholder()
    conn.execute(
        f"""
        INSERT INTO overlay_connections (channel_id, overlay_type, last_connected_at)
        VALUES ({p}, {p}, CURRENT_TIMESTAMP)
        ON CONFLICT (channel_id, overlay_type)
        DO UPDATE SET last_connected_at = CURRENT_TIMESTAMP
        """,
        (channel_id, overlay_type)
    )
    conn.commit()
    conn.close()

    emit("overlay_ready", {
        "status": "connected",
        "overlay_type": overlay_type,
        "channel_id": channel_id,
    })


@socketio.on("overlay_heartbeat")
def handle_overlay_heartbeat(data):
    token = data.get("token")
    overlay_type = data.get("overlay_type")

    if not token or not overlay_type:
        return

    channel_id = validate_overlay_token(token, overlay_type)
    if not channel_id:
        return

    conn = get_db_connection()
    p = placeholder()
    conn.execute(
        f"""
        UPDATE overlay_connections
        SET last_connected_at = CURRENT_TIMESTAMP
        WHERE channel_id = {p} AND overlay_type = {p}
        """,
        (channel_id, overlay_type)
    )
    conn.commit()
    conn.close()


@socketio.on("switch_account")
def handle_switch_account(data):
    user_id = session.get("user_id")
    available_accounts = session.get("available_accounts", [])

    if not user_id or not available_accounts:
        return

    chosen_channel_id = data.get("channel_id")

    chosen_account = next(
        (account for account in available_accounts
         if account["channel_id"] == chosen_channel_id),
        None
    )

    if not chosen_account:
        return

    old_channel_id = session.get("active_channel_id")
    if old_channel_id:
        leave_room(f"channel_{old_channel_id}")
        stop_relay(old_channel_id)

    session["active_channel_id"] = chosen_account["channel_id"]
    session["active_role"] = chosen_account["role"]

    join_room(f"channel_{chosen_account['channel_id']}")

    emit("account_switched", {
        "channel_id": chosen_account["channel_id"],
        "role": chosen_account["role"],
        "role_label": chosen_account["role_label"],
        "display_name": chosen_account["display_name"],
    })


# =============================================================
# Chat relay events
# =============================================================

@socketio.on("start_chat")
def handle_start_chat():
    """
    Called by the chat page on load.
    Looks up the channel's Twitch login and access token,
    then starts the IRC relay if not already running.
    """
    channel_id   = session.get("active_channel_id")
    access_token = session.get("access_token")
    user_id      = session.get("user_id")
    


    if not channel_id or not access_token or not user_id:
        emit("chat_status", {"status": "error", "error": "Not authenticated"})
        return

    if is_connected(channel_id):
        emit("chat_status", {"status": "connected"})
        return

    conn = get_db_connection()
    p    = placeholder()

    row = conn.execute(
        f"""
        SELECT up.platform_login, up.platform_user_id
        FROM user_platforms up
        JOIN channels c ON c.user_id = up.user_id
        WHERE c.id = {p} AND up.platform = 'twitch'
        """,
        (channel_id,)
    ).fetchone()


    if not row:
        emit("chat_status", {"status": "error", "error": "No Twitch account linked"})
        return

    channel_login  = row["platform_login"]
    broadcaster_id = row["platform_user_id"]
    start_relay(
        channel_id     = channel_id,
        channel_login  = channel_login,
        broadcaster_id = broadcaster_id,
        access_token   = access_token,
        bot_login      = channel_login,
        socketio       = socketio,
    )


@socketio.on("send_chat_message")
def handle_send_chat_message(data):
    """
    Called when the streamer sends a message from the dashboard.
    Relays it through the active IRC connection.
    """
    channel_id = session.get("active_channel_id")
    message    = (data.get("message") or "").strip()

    if not channel_id or not message:
        return

    # 500 char Twitch limit
    if len(message) > 500:
        emit("chat_error", {"error": "Message too long (500 character limit)"})
        return

    success = send_message(channel_id, message)

    if not success:
        emit("chat_error", {"error": "Chat not connected — try refreshing"})