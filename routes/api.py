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

        allowed = {"theme", "colour_scheme", "clock_format", "clock_visible", "world_clocks", "onboarding_complete"}    
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

@api_bp.route("/stream/stats", methods=["GET"])
@api_login_required
def stream_stats():
    from utils.twitch import get_stream, get_follower_count, get_subscribers
    from datetime import datetime, timezone

    access_token = session.get("access_token")
    if not access_token:
        return jsonify({"error": "No Twitch token in session"}), 401

    conn = get_db_connection()
    p = placeholder()

    # Get the Twitch broadcaster ID for the active channel
    platform_row = conn.execute(
        f"""
        SELECT up.platform_user_id
        FROM user_platforms up
        JOIN channels c ON c.user_id = up.user_id
        WHERE c.id = {p}
        AND up.platform = 'twitch'
        """,
        (current_channel_id(),)
    ).fetchone()

    conn.close()

    if not platform_row:
        return jsonify({"error": "No Twitch platform linked"}), 404

    broadcaster_id = platform_row["platform_user_id"]

    # Fetch from Twitch
    stream = get_stream(broadcaster_id, access_token)
    followers = get_follower_count(broadcaster_id, access_token)
    subscribers = get_subscribers(broadcaster_id, access_token)

    is_live = stream is not None
    viewers = stream["viewer_count"] if is_live else None
    started_at = stream["started_at"] if is_live else None

    # Calculate uptime in seconds if live
    uptime_seconds = None
    if started_at:
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            uptime_seconds = int(
                (datetime.now(timezone.utc) - start).total_seconds()
            )
        except Exception:
            pass

    return jsonify({
        "live": is_live,
        "viewers": viewers,
        "followers": followers,
        "subscribers": subscribers,
        "uptime_seconds": uptime_seconds,
        "started_at": started_at,
    })

# =============================================================
# Dashboard layout
# Saves and loads the user's dashboard widget layout.
# Stored in user_preferences as key = 'dashboard_layout',
# value = JSON string.
# =============================================================

@api_bp.route("/dashboard/layout", methods=["GET"])
@api_login_required
def get_dashboard_layout():
    conn = get_db_connection()
    p = placeholder()
    user_id = session.get("user_id")

    row = conn.execute(
        f"SELECT value FROM user_preferences WHERE user_id = {p} AND preference = {p}",
        (user_id, "dashboard_layout")
    ).fetchone()

    if row:
        return jsonify({"layout":  row["value"]})
    return jsonify({"layout": None})

@api_bp.route("/dashboard/layout", methods=["POST"])
@api_login_required
def save_dashboard_layout():
    conn = get_db_connection()
    p = placeholder()
    user_id = session.get("user_id")
    layout = request.json.get("layout")

    if not layout:
        return jsonify({"error": "No layout provided"}), 400
    
    conn.execute(
            f"""INSERT INTO user_preferences (user_id, preference, value, updated_at)
                VALUES ({p}, {p}, {p}, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, preference)
                DO UPDATE SET value = {p}, updated_at = CURRENT_TIMESTAMP""",
            (user_id, "dashboard_layout", layout, layout)
        )
    conn.commit()
    return jsonify({"status": "ok"})

# =============================================================
# Chat — Twitch user lookup
# Called when a username is clicked in the chat viewer.
# Returns real Twitch profile data plus the stored SP profile.
# =============================================================

@api_bp.route("/chat/user/<twitch_login>")
@api_login_required
def chat_user(twitch_login):
    import requests
    from flask import current_app

    access_token = session.get("access_token")
    if not access_token:
        return jsonify({"error": "No Twitch token"}), 401

    client_id = current_app.config["TWITCH_CLIENT_ID"]
    headers   = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id":     client_id,
    }

    # --- Twitch user profile ---
    r = requests.get(
        "https://api.twitch.tv/helix/users",
        params={"login": twitch_login},
        headers=headers,
    )
    if not r.ok or not r.json().get("data"):
        return jsonify({"error": "User not found"}), 404

    twitch_user   = r.json()["data"][0]
    twitch_user_id = twitch_user["id"]

    # --- Follower status for this channel ---
    conn = get_db_connection()
    p    = placeholder()

    platform_row = conn.execute(
        f"""
        SELECT up.platform_user_id
        FROM user_platforms up
        JOIN channels c ON c.user_id = up.user_id
        WHERE c.id = {p} AND up.platform = 'twitch'
        """,
        (current_channel_id(),)
    ).fetchone()

    broadcaster_id = platform_row["platform_user_id"] if platform_row else None

    follower_since = None
    if broadcaster_id:
        fr = requests.get(
            "https://api.twitch.tv/helix/channels/followers",
            params={
                "broadcaster_id": broadcaster_id,
                "user_id":        twitch_user_id,
            },
            headers=headers,
        )
        if fr.ok:
            fdata = fr.json().get("data", [])
            if fdata:
                follower_since = fdata[0].get("followed_at")

    # --- StreamPilot chat profile ---
    profile = conn.execute(
        f"""
        SELECT nickname, notes, flag
        FROM chat_profiles
        WHERE channel_id = {p} AND twitch_user_id = {p}
        """,
        (current_channel_id(), twitch_user_id)
    ).fetchone()

    conn.close()

    return jsonify({
        "twitch": {
            "id":               twitch_user_id,
            "login":            twitch_user["login"],
            "display_name":     twitch_user["display_name"],
            "avatar_url":       twitch_user.get("profile_image_url"),
            "account_created":  twitch_user.get("created_at"),
            "description":      twitch_user.get("description", ""),
        },
        "channel": {
            "follower_since":   follower_since,
        },
        "profile": {
            "nickname": profile["nickname"] if profile else None,
            "notes":    profile["notes"]    if profile else None,
            "flag":     profile["flag"]     if profile else "none",
        },
    })


# =============================================================
# Chat profiles — save/update
# Stores per-viewer nickname, notes and flag against channel.
# =============================================================

@api_bp.route("/chat/profile", methods=["POST"])
@api_login_required
def save_chat_profile():
    from utils.db import get_db_type

    data           = request.get_json()
    twitch_user_id = (data.get("twitch_user_id") or "").strip()
    twitch_login   = (data.get("twitch_login")   or "").strip()
    nickname       = (data.get("nickname")        or "").strip() or None
    notes          = (data.get("notes")           or "").strip() or None
    flag           = (data.get("flag")            or "none").strip()

    if not twitch_user_id or not twitch_login:
        return jsonify({"error": "twitch_user_id and twitch_login are required"}), 400

    allowed_flags = {"none", "star", "warning", "ban_watch"}
    if flag not in allowed_flags:
        flag = "none"

    conn = get_db_connection()
    p    = placeholder()

    if get_db_type() == "postgres":
        conn.execute(
            f"""
            INSERT INTO chat_profiles
                (channel_id, twitch_user_id, twitch_login, nickname, notes, flag, updated_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, CURRENT_TIMESTAMP)
            ON CONFLICT (channel_id, twitch_user_id)
            DO UPDATE SET
                nickname   = {p},
                notes      = {p},
                flag       = {p},
                twitch_login = {p},
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                current_channel_id(), twitch_user_id, twitch_login,
                nickname, notes, flag,
                nickname, notes, flag, twitch_login,
            )
        )
    else:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO chat_profiles
                (channel_id, twitch_user_id, twitch_login, nickname, notes, flag, updated_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, CURRENT_TIMESTAMP)
            """,
            (current_channel_id(), twitch_user_id, twitch_login, nickname, notes, flag)
        )

    conn.commit()
    conn.close()

    return jsonify({"ok": True})


# =============================================================
# Chat profiles — delete
# Removes all stored notes/nickname/flag for a viewer.
# =============================================================

@api_bp.route("/chat/profile/<twitch_user_id>", methods=["DELETE"])
@api_login_required
def delete_chat_profile(twitch_user_id):
    conn = get_db_connection()
    p    = placeholder()

    conn.execute(
        f"""
        DELETE FROM chat_profiles
        WHERE channel_id = {p} AND twitch_user_id = {p}
        """,
        (current_channel_id(), twitch_user_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})
