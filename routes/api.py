from flask import Blueprint, jsonify, request, session
from utils.db import get_db_connection, placeholder
from utils.helpers import api_login_required, current_channel_id
from extensions import socketio


api_bp = Blueprint("api", __name__)


@api_bp.route("/status")
def status():
    return jsonify({"status": "ok", "version": "0.1.0"})


@api_bp.route("/channel")
@api_login_required
def channel():
    return jsonify({
        "display_name": session.get("display_name"),
        "avatar_url": session.get("avatar_url"),
        "active_channel_id": session.get("active_channel_id"),
        "active_role": session.get("active_role"),
    })


@api_bp.route("/commands", methods=["GET"])
@api_login_required
def get_commands():
    conn = get_db_connection()
    p = placeholder()

    commands = conn.execute(
        f"""
        SELECT *
        FROM commands
        WHERE channel_id = {p}
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
    data = request.get_json()
    trigger = data.get("trigger", "").strip().lstrip("!")
    response = data.get("response", "").strip()
    cooldown = data.get("cooldown_s", 30)

    if not trigger or not response:
        return jsonify({"error": "Trigger and response are required."}), 400
    
    conn = get_db_connection()
    p = placeholder()

    existing = conn.execute(
        f"""
        SELECT id FROM commands
        WHERE channel_id = {p} AND trigger = {p} AND deleted_at IS NULL
        """,
        (current_channel_id(), trigger)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({"error": "A command with that trigger already exists."}), 409
    
    cur = conn.execute(
        f"""
        INSERT INTO commands (channel_id, trigger, response, cooldown_s)
        VALUES ({p}, {p}, {p}, {p})
        """,
        (current_channel_id(), trigger, response, cooldown)
    )

    conn.commit()
    conn.close()

    return jsonify({"id": cur.lastrowid, "trigger": trigger}), 201


@api_bp.route("/commands/<int:command_id>", methods=["PUT"])
@api_login_required
def update_command(command_id):
    conn = get_db_connection()
    p = placeholder()

    command = conn.execute(
        f"""
        SELECT id 
        FROM commands
        WHERE id = {p}
        AND channel_id = {p}
        AND deleted_at IS NULL
        """,
        (command_id, current_channel_id())
    ).fetchone()

    if not command:
        conn.close()
        return jsonify({"error": "Command not found"}), 404
    
    data = request.get_json()

    conn.execute(
        f"""
        UPDATE commands SET
            response = COALESCE({p}, response),
            enabled = COALESCE({p}, enabled),
            cooldown_s = COALESCE({p}, cooldown_s),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = {p}
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
    conn = get_db_connection()
    p = placeholder()

    command = conn.execute(
        f"""
        SELECT id
        FROM commands
        WHERE id = {p}
        AND channel_id = {p}
        AND deleted_at IS NULL
        """,
        (command_id, current_channel_id())
    ).fetchone()

    if not command:
        conn.close()
        return jsonify({"error": "Command not found."}), 404
    
    conn.execute(
        f"UPDATE commands SET deleted_at = CURRENT_TIMESTAMP WHERE id = {p}",
        (command_id,)
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@api_bp.route("/panels", methods=["GET"])
@api_login_required
def get_panels():
    conn = get_db_connection()
    p = placeholder()

    panels = conn.execute(
        f"""
        SELECT *
        FROM panels
        WHERE channel_id = {p}
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
    conn = get_db_connection()
    p = placeholder()

    panel = conn.execute(
        f"""
        SELECT *
        FROM panels
        WHERE id = {p}
        AND channel_id = {p}
        AND deleted_at IS NULL
        """,
        (panel_id, current_channel_id())
    ).fetchone()

    if not panel:
        conn.close()
        return jsonify({"error": "Panel not found."}), 404
    
    conn.close()

    socketio.emit(
        "panel_show",
        {"panel": dict(panel), "test": True},
        room=f"channel_{current_channel_id()}"
    )

    return jsonify({"ok": True, "message": "Test panel fired to overlay."})


@api_bp.route("/alerts/test", methods=["POST"])
@api_login_required
def test_alert():
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


@api_bp.route("/overlays/status", methods=["GET"])
@api_login_required
def overlay_status():
    from utils.helpers import time_ago
    from datetime import datetime, timedelta, timezone

    conn = get_db_connection()
    p = placeholder()

    connections = conn.execute(
        f"""
        SELECT overlay_type, last_connected_at
        FROM overlay_connections
        WHERE channel_id = {p}
        """,
        (current_channel_id(),)
    ).fetchall()

    conn.close()

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
    
    for overlay_type in ["alerts", "panels", "celebrations"]:
        if overlay_type not in status:
            status[overlay_type] = {
                "connected": False,
                "last_seen": "Never connected",
            }

    return jsonify(status)

@api_bp.route("/preferences", methods=["POST"])
@api_login_required
def save_preference():
    from utils.db import get_db_type
    data = request.get_json()
    preference = data.get("preference", "").strip()
    value = data.get("value", "").strip()

    if not preference or not value:
        return jsonify({"error": "Preference and value are required."}), 400

    allowed = {"theme", "colour_scheme", "clock_format", "clock_visible", "world_clocks"}
    if preference not in allowed:
        return jsonify({"error": "Unknown preference."}), 400

    conn = get_db_connection()
    p = placeholder()

    if get_db_type() == "postgres":
        conn.execute(
            f"""
            INSERT INTO user_preferences (user_id, preference, value)
            VALUES ({p}, {p}, {p})
            ON CONFLICT (user_id, preference) DO UPDATE SET value = {p}, updated_at = CURRENT_TIMESTAMP
            """,
            (session["user_id"], preference, value, value)
        )
    else:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO user_preferences (user_id, preference, value)
            VALUES ({p}, {p}, {p})
            """,
            (session["user_id"], preference, value)
        )

    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@api_bp.route("/preferences", methods=["GET"])
@api_login_required
def get_preferences():
    conn = get_db_connection()
    p = placeholder()

    prefs = conn.execute(
        f"""
        SELECT preference, value FROM user_preferences
        WHERE user_id = {p}
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()
    return jsonify({row["preference"]: row["value"] for row in prefs})