from flask import Blueprint, jsonify, request, session
from utils.db import get_db_connection
from utils.helpers import api_login_required, current_channel_id
from app import socketio

api_bp = Blueprint("api", __name__)


# =============================================================
# Status
# =============================================================

@api_bp.route("/status")
def status():
    """
    This is a health check endpoint, no auth required.
    This is used to verify the app is running
    """
    return jsonify({"status": "ok", "version": "0.1.0"})

# =============================================================
# Channel
# =============================================================

@api_bp.route("/channel")
@api_login_required
def channel():
    """
    Return basic channel info from the session.
    Used by the topbar to show avatar, display name and live status
    """
    return jsonify({
        "display_name": session.get("display_name"),
        "avatar_url": session.get("avatar_url"),
        "active_channel_id": session.get("active_channel_id"),
        "active_role": session.get("active_role"),
    })

# =============================================================
# Commands
# =============================================================

@api_bp.route("/commands", methods=["GET"])
@api_login_required
def get_commands():
    """
    Return all active commands for the current channel. 
    Soft-deleted commands (deleted_at is not NULL) are excluded.
    """
    conn = get_db_connection()

    commands = conn.execute(
        """
        SELECT *
        FROM commands
        WHERE channel_id = ?
        AND deleted_at IS NULL
        ORDER BY trigger ASC
        """,
        (current_channel_id(),)
    ).fetchall()

    conn.close()
    return jsonify([dict(command) for command in commands])

@api_bp.route("/commands", methods=["POST"])
@api_login_required
def create_command():
    """
    Create a new chat command for the current channel.
    The trigger is stored without the ! prefix.
    Returns the new command id and trigger on success
    """

    data = request.get_json()
    trigger = data.get("trigger", "").strip().lstrip("!")
    response = data.get("response", "").strip()
    cooldown = data.get("cooldown_s", 30)

    if not trigger or not response:
        return jsonify({"error": "Trigger and response are required."}), 400
    
    conn = get_db_connection()

    # Check the trigger does not already exist for this channel
    existing = conn.execute(
        """
        SELECT id FROM commands
        WHERE channel_id = ? AND trigger = ? AND deleted_at IS NULL
        """,
        (current_channel_id(), trigger)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({"error": "A command with the trigger already exists."}), 409
    
    cur = conn.execute(
        """
        INSERT INTO commands (channel_id, trigger, respose, cooldown_s)
        VALUES (?, ?, ?, ?)
        """,
        (current_channel_id(), trigger, response, cooldown)
    )

    conn.commit()
    conn.close()

    return jsonify({"id": cur.lastrowid, "trigger": trigger}), 201

@api_bp.route("/commands/<int:command_id>", methods=["PUT"])
@api_login_required
def update_command(command_id):
    """
    Update an exisiting command.
    Only the channel that owns the command can update it. 
    Partial updates are supported - only pass the fields to change.
    """
    conn = get_db_connection()

    command = conn.execute(
        """
        SELECT id 
        FROM commands
        WHERE id = ?
        AND channel_id = ?
        AND deleted_at IS NULL
        """,
        (command_id, current_channel_id())
    ).fetchone()

    if not command:
        conn.close()
        return jsonify({"error": "Command not found"}), 404
    
    data = request.get_json()

    conn.execute(
        """
        UPDATE commands SET
            response = COALESCE(?, response),
            enabled = COALESCE(?, enabled),
            cooldown_s = COALESCE(?, cooldown_s),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            data.get("response"),
            data.get("enabled"),
            data.get("cooldown_s"),
            command_id
        )
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

@api_bp.route("/commands/<int:command_id>", methods=["DELETE"])
@api_login_required
def delete_command(command_id):
    """
    Soft-delete a command by setting deleted_at
    The row is kept in the database for audit purposes.
    Only the channel that owns the command can delete it. 
    """
    conn = get_db_connection()

    command = conn.execute(
        """
        SELECT id
        FROM commands
        WHERE id = ?
        AND channel_id = ?
        AND deleted_at IS NULL
        """,
        (command_id, current_channel_id())
    ).fetchone()

    if not command:
        conn.close()
        return jsonify({"error": "Command not found."}), 404
    
    conn.execute(
        "UPDATE commands SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
        (command_id,)
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

# =============================================================
# Panels
# =============================================================

@api_bp.route("/panels", methods=["GET"])
@api_login_required
def get_panels():
    """
    Return all active panels for the current channel.
    Order by sort_order so the frontend displays them
    in the right sequence the streamer has arranged them.
    """

    conn = get_db_connection()

    panels = conn.execute(
        """
        SELECT *
        FROM panels
        WHERE channel_id = ?
        AND deleted_at IS NULL
        ORDER BY sort_order ASC
        """,
        (current_channel_id(),)
    ).fetchall()

    conn.close()
    return jsonify([dict(panel) for panel in panels])

@api_bp.route("/panels/<int:panel_id>/test", methods=["POST"])
@api_login_required
def test_panel(panel_id):
    """
    Fire a test show of a panel to the OBS overlay immediately.
    Emits a 'panel_show' WebSocket event to the channel room.
    The overlay receives it and displays the panel exactly as
    it would during a live stream.
    This is a test function for the panels overlay
    """
    conn = get_db_connection()

    panel = conn.execute(
        """
        SELECT *
        FROM panels
        WHERE id = ? 
        AND channel_id = ?
        AND deleted_at IS NULL
        """,
        (panel_id, current_channel_id())
    ).fetchone()

    if not panel:
        conn.close()
        return jsonify({"error": "Panel not found."}), 404
    
    conn.close()

    #Emit to the channel room - all connected overlays will receive this
    socketio.emit(
        "panel_show",
        {"panel": dict(panel), "test": True},
        room=f"channel_{current_channel_id()}"
    )

    return jsonify({"ok": True, "message": "Test panel fired to overlay."})

# =============================================================
# Alerts
# =============================================================

@api_bp.route("/alerts/test", methods=["POST"])
@api_login_required
def test_alert():
    """
    Fire a test alert to the OBS overlay.
    Emits a fake 'alert' WebSocket event to the channel room. 
    The overlay receives it and plays the alert animation exactly
    as it would for a real follow, sub or raid. 
    This is a test function for the alerts overlay

    Request body:
        type -  the alert type to test:
                follow | sub_t1 | sub_t2 | sub_t3
                gift_sub | raid | bits | resub
    """

    data = request.get_json()
    alert_type = data.get("type", "follow")

    socketio.emit(
        "alert",
        {
            "type": alert_type,
            "test": True,
            "user": "StreamPilotTest",
            "message": "This is a test alert from StreamPilot", 
        },
        room=f"channel_{current_channel_id()}"
    )

    return jsonify({"ok": True, "message": f"Test {alert_type} alert fired to overlay."})

@api_bp.route("/celebrations/test", methods=["POST"])
@api_login_required
def test_celebration():
    """
    Fire a test celebration to the OBS overlay.
    Emits a fake 'celebrate' WebSocket event to the channel room.
    This is the test function for the celebrations overlay.

    Request Body: 
        type - the celebration type to test: follow | sub | raid    
    """

    data = request.get_json()
    celebration_type = data.get("type", "follow")

    socketio.emit(
        "celebrate",
        {
            "type": celebration_type,
            "test": True,
        },
        room=f"channel_{current_channel_id()}"
    )

    return jsonify({"ok": True, "message": f"Test {celebration_type} celebration fired to overlay."})

# =============================================================
# Overlay connection status
# =============================================================

@api_bp.route("/overlays/status", methods=["GET"])
@api_login_required
def overlay_status():
    """
    Return the last known connection time for each overlay type.
    Used by the settings page to show whether each OBS browser
    source is connected or not

    Returns for each overlay type:
        connected - True if connected in the last 60 seconds
        last_seen - human readable time e.g "2 minutes ago"
    """
    # The following is only used for this function,
    # if this changed think about changing the import to the top
    from utils.helpers import time_ago
    from datetime import datetime, timedelta, timezone

    conn = get_db_connection()

    connections = conn.execute(
        """
        SELECT overlay_type, last_connected_at
        FROM overlay_connections
        WHERE channel_id = ?
        """,
        (current_channel_id(),)
    ).fetchall()

    conn.close()

    # Build a dict keyed by overlay type
    status = {}
    sixty_seconds_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=60)

    for connection in connections:
        try:
            last_seen = datetime.fromisoformat(connection["last_connected_at"])
            is_connected = last_seen > sixty_seconds_ago
        except Exception:
            is_connected = False
        
        status[connection["overlay_type"]] = {
            "connected": is_connected,
            "last_seen": time_ago(connection["last_connected_at"]),
        }
    
    # Fill in any overlay types that have never connected
    for overlay_type in ["alerts", "panels", "celebrations"]:
        if overlay_type not in status:
            status[overlay_type] = {
                "connected": False,
                "last_seen": "Never connected",
            }

    return jsonify(status)

