from flask import session
from flask_socketio import join_room, leave_room, emit
from extensions import socketio
from utils.db import get_db_connection
from utils.security import validate_overlay_token


# =============================================================
# WebSocket event handlers
#
# How rooms work:
#   Every channel has a room named "channel_<id>"
#   e.g. "channel_42"
#
#   When the dashboard connects it joins that room.
#   When an OBS overlay connects it also joins that room.
#   When the backend emits to the room, everyone in it
#   receives the event — this is how a test button in the
#   dashboard instantly fires the animation in OBS.
# =============================================================

@socketio.on("connect")
def handle_connect():
    """
    Called when any client connects via WebSocket.
    Dashboard clients join their channel room automatically
    using the active_channel_id stored in their session.
    OBS overlay clients join via join_overlay event instead.
    """
    channel_id = session.get("active_channel_id")
    if channel_id:
        join_room(f"channel_{channel_id}")
        emit("connected", {"status": "ok", "channel_id": channel_id})

@socketio.on("disconnect")
def handle_disconnect():
    """
    Called when a client disconnects.
    FRlask-SockIO handles room cleanup automatically
    but we leave explicity to be safe.
    """
    channel_id = session.get("active_channel_id")
    if channel_id:
        leave_room(f"channel_{channel_id}")

@socketio.on("join_overlay")
def handle_join_overlay(data):
    """
    Called by OBS overlay pages when they land in OBS.
    The overlay sends its toekn asnd overlay type.
    We validate the token, join the channel room, and
    record the connection time so the settings page can
    show "Alerts overlay - Connected 2 minutes ago".

    Data expected:
        token - the overlay URL token
        overlay_type - alerts | panels | celebrations
    """


    token = data.get("token")
    overlay_type = data.get("overlay_type")
    
    if not token or not overlay_type:
        return
    
    channel_id = validate_overlay_token(token, overlay_type)
    if not channel_id:
        return
    
    # Join the chasnnel room so this overlay receives events
    join_room(f"channel_{channel_id}")

    # Record that this overlay is connected
    # Uses INSERT ot REPLACE so we always have the latest time
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO overlay_connections (channel_id, overlay_type, last_connected_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
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
    """
    Called by OBS overlay pages every 30 seconds to confirm
    they are still connected and showing in OBS.
    Updates last_)connected_at so the settings page status
    stays current during a long stream

    Data expected:
        token - the overlay URL token
        overlay_type - alerts | panels | celebrations
    """

    token = data.get("token")
    overlay_type = data.get("overlay_type")

    if not token or not overlay_type:
        return
    
    channel_id = validate_overlay_token(token, overlay_type)
    if not channel_id:
        return

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE overlay_connections
        SET last_connected_at = CURRENT_TIMESTAMP
        WHERE channel_id = ? AND overlay_type = ?
        """,
        (channel_id, overlay_type)
    )
    conn.commit()
    conn.close()

@socketio.on("switch_account")
def handle_switch_account(data):
    """
    Called when a user switches between their streamer account
    and a channel they moderate, without logging out.
    Updates the active_channel_id and active_role in the session
    and moves them to the correct channel room.

    Data expected:
      channel_id — the channel to switch to
    """
    user_id = session.get("user_id")
    available_accounts = session.get("available_accounts", [])

    if not user_id or not available_accounts:
        return

    chosen_channel_id = data.get("channel_id")

    # Verify the requested channel is in their available list
    # Never trust client data — always validate against the session
    chosen_account = next(
        (account for account in available_accounts
         if account["channel_id"] == chosen_channel_id),
        None
    )

    if not chosen_account:
        return

    # Leave the old channel room
    old_channel_id = session.get("active_channel_id")
    if old_channel_id:
        leave_room(f"channel_{old_channel_id}")

    # Update the session
    session["active_channel_id"] = chosen_account["channel_id"]
    session["active_role"] = chosen_account["role"]

    # Join the new channel room
    join_room(f"channel_{chosen_account['channel_id']}")

    emit("account_switched", {
        "channel_id": chosen_account["channel_id"],
        "role": chosen_account["role"],
        "role_label": chosen_account["role_label"],
        "display_name": chosen_account["display_name"],
    })




