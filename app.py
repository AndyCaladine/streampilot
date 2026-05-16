from flask import Flask, render_template, redirect, url_for, session, request
from flask_socketio import SocketIO
from config import Config
from routes.streamer import streamer_bp
from routes.admin import admin_bp
from routes.registration import registration_bp
from routes.overlays import overlays_bp
from routes.api import api_bp

app = Flask(__name__)
app.config.from_object(Config)

socketio = SocketIO(app, cors_allowed_origins="*")

app.register_blueprint(streamer_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(registration_bp)
app.register_blueprint(overlays_bp, url_prefix="/overlay")
app.register_blueprint(api_bp, url_prefix="/api")

# Register WebSocket event handlers
from routes import ws_events  # noqa: F401

# Close DB connection after every request
from utils.db import close_db
app.teardown_appcontext(close_db)


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("streamer.dashboard"))
    return render_template("index.html")


@app.route("/auth/login")
def login():
    """Redirect to Twitch OAuth."""
    import urllib.parse
    params = {
        "client_id":     app.config["TWITCH_CLIENT_ID"],
        "redirect_uri":  app.config["TWITCH_REDIRECT_URI"],
        "response_type": "code",
        "scope": " ".join([
            "user:read:email",
            "channel:read:subscriptions",
            "channel:read:goals",
            "channel:read:polls",
            "channel:manage:polls",
            "channel:manage:predictions",
            "channel:manage:raids",
            "moderator:read:followers",
            "moderator:manage:chat_messages",
            "moderator:manage:banned_users",
            "bits:read",
            "clips:edit",
        ]),
    }
    url = "https://id.twitch.tv/oauth2/authorize?" + urllib.parse.urlencode(params)
    return redirect(url)


@app.route("/auth/callback")
def callback():
    """Handle redirect back from Twitch after login."""
    from utils.twitch import exchange_code, get_user
    from utils.db import get_db_connection

    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    tokens = exchange_code(code)
    if not tokens or "access_token" not in tokens:
        return redirect(url_for("login"))

    twitch_user = get_user(tokens["access_token"])
    if not twitch_user:
        return redirect(url_for("login"))

    conn = get_db_connection()

    user = conn.execute(
        "SELECT id FROM users WHERE twitch_id = ?",
        (twitch_user["id"],)
    ).fetchone()

    if user:
        conn.execute(
            """UPDATE users SET
               twitch_login = ?, twitch_display_name = ?, twitch_avatar_url = ?,
               access_token = ?, refresh_token = ?, last_login_at = datetime('now')
               WHERE twitch_id = ?""",
            (
                twitch_user["login"],
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                tokens["access_token"],
                tokens.get("refresh_token"),
                twitch_user["id"],
            )
        )
        conn.commit()
        user_id = user["id"]
    else:
        cur = conn.execute(
            """INSERT INTO users
               (twitch_id, twitch_login, twitch_display_name, twitch_avatar_url,
                email, access_token, refresh_token)
               VALUES (?,?,?,?,?,?,?)""",
            (
                twitch_user["id"],
                twitch_user["login"],
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                twitch_user.get("email"),
                tokens["access_token"],
                tokens.get("refresh_token"),
            )
        )
        conn.commit()
        user_id = cur.lastrowid

        conn.execute(
            "INSERT INTO channels (user_id, twitch_id) VALUES (?,?)",
            (user_id, twitch_user["id"])
        )
        conn.commit()

    channel = conn.execute(
        "SELECT id FROM channels WHERE user_id = ?", (user_id,)
    ).fetchone()

    conn.close()

    session.clear()
    session["user_id"]      = user_id
    session["channel_id"]   = channel["id"] if channel else None
    session["twitch_id"]    = twitch_user["id"]
    session["display_name"] = twitch_user["display_name"]
    session["avatar_url"]   = twitch_user.get("profile_image_url")
    session["access_token"] = tokens["access_token"]

    return redirect(url_for("streamer.dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    socketio.run(app, debug=app.config["DEBUG"], host="0.0.0.0", port=5000)