from flask import session
from flask_socketio import join_room, leave_room, emit
from extensions import socketio
from utils.db import get_db_connection, placeholder
from utils.security import validate_overlay_token


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

    session["active_channel_id"] = chosen_account["channel_id"]
    session["active_role"] = chosen_account["role"]

    join_room(f"channel_{chosen_account['channel_id']}")

    emit("account_switched", {
        "channel_id": chosen_account["channel_id"],
        "role": chosen_account["role"],
        "role_label": chosen_account["role_label"],
        "display_name": chosen_account["display_name"],
    })