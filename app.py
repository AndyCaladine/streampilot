from flask import Flask, render_template, redirect, url_for, session, request, flash
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


# =============================================================
# Public routes
# =============================================================

@app.route("/")
def index():
    """
    Landing page.
    Logged-in users are redirected to the dashboard or account
    picker depending on how many accounts they have access to.
    """
    if session.get("user_id"):
        return redirect(url_for("streamer.dashboard"))
    return render_template("index.html")


@app.route("/auth/login")
def login():
    """
    Redirect the user to Twitch to sign in.
    Scopes define what permissions we request from Twitch.
    Only request what we actually use — adding scopes later
    requires the user to re-consent.
    """
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
    """
    Handle the redirect back from Twitch after the user consents.

    Flow:
      1. Exchange the code for tokens
      2. Fetch their Twitch profile
      3. Create or update their user record
      4. Check how many accounts they have access to:
           - Own channel (streamer)
           - Mod roles on other channels
      5. One account  → set session and go to dashboard
         Multiple     → go to account picker
    """
    from utils.twitch import exchange_code, get_user
    from utils.db import get_db_connection

    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    # Step 1 — exchange code for tokens
    tokens = exchange_code(code)
    if not tokens or "access_token" not in tokens:
        flash("Something went wrong signing in with Twitch. Please try again.", "error")
        return redirect(url_for("login"))

    # Step 2 — fetch their Twitch profile
    twitch_user = get_user(tokens["access_token"])
    if not twitch_user:
        flash("We could not fetch your Twitch profile. Please try again.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    # Step 3 — create or update user record
    existing_user = conn.execute(
        """
        SELECT u.id
        FROM users u
        JOIN user_platforms up ON u.id = up.user_id
        WHERE up.platform = 'twitch'
        AND up.platform_user_id = ?
        """,
        (twitch_user["id"],)
    ).fetchone()

    if existing_user:
        # Returning user — update tokens and display info
        user_id = existing_user["id"]
        conn.execute(
            """
            UPDATE user_platforms SET
                platform_login        = ?,
                platform_display_name = ?,
                platform_avatar_url   = ?,
                access_token          = ?,
                refresh_token         = ?,
                last_login_at         = CURRENT_TIMESTAMP
            WHERE platform = 'twitch'
            AND platform_user_id = ?
            """,
            (
                twitch_user["login"],
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                tokens["access_token"],
                tokens.get("refresh_token"),
                twitch_user["id"],
            )
        )
        conn.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        conn.commit()
    else:
        # First time user — check for beta code in session
        beta_code = session.get("beta_code")
        if not beta_code:
            conn.close()
            flash("You need a beta access code to create an account.", "error")
            return redirect(url_for("registration.join"))

        # Validate the beta code is still unused
        valid_code = conn.execute(
            """
            SELECT id FROM beta_codes
            WHERE code = ?
            AND used_at IS NULL
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            (beta_code,)
        ).fetchone()

        if not valid_code:
            conn.close()
            flash("Your beta code is no longer valid. Please contact us for a new one.", "error")
            return redirect(url_for("registration.join"))

        # Create the user record
        cur = conn.execute(
            """
            INSERT INTO users (display_name, avatar_url, email)
            VALUES (?, ?, ?)
            """,
            (
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                twitch_user.get("email"),
            )
        )
        conn.commit()
        user_id = cur.lastrowid

        # Create their platform record
        conn.execute(
            """
            INSERT INTO user_platforms
                (user_id, platform, platform_user_id, platform_login,
                 platform_display_name, platform_avatar_url,
                 access_token, refresh_token)
            VALUES (?, 'twitch', ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                twitch_user["id"],
                twitch_user["login"],
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                tokens["access_token"],
                tokens.get("refresh_token"),
            )
        )

        # Create their channel record
        conn.execute(
            """
            INSERT INTO channels (user_id, platform, platform_channel_id)
            VALUES (?, 'twitch', ?)
            """,
            (user_id, twitch_user["id"])
        )
        conn.commit()

        # Mark the beta code as used
        conn.execute(
            """
            UPDATE beta_codes
            SET used_at = CURRENT_TIMESTAMP, used_by = ?
            WHERE code = ?
            """,
            (user_id, beta_code)
        )
        conn.commit()
        session.pop("beta_code", None)

    # Step 4 — check how many accounts this user has access to
    # Their own channel
    own_channel = conn.execute(
        """
        SELECT c.id as channel_id, up.platform_display_name as display_name,
               up.platform_avatar_url as avatar_url, 'owner' as role
        FROM channels c
        JOIN users u ON c.user_id = u.id
        JOIN user_platforms up ON u.id = up.user_id
        WHERE u.id = ? AND up.platform = 'twitch'
        """,
        (user_id,)
    ).fetchone()

    # Channels they moderate
    mod_channels = conn.execute(
        """
        SELECT c.id as channel_id, up.platform_display_name as display_name,
               up.platform_avatar_url as avatar_url, tm.role as role
        FROM team_members tm
        JOIN channels c ON tm.channel_id = c.id
        JOIN users channel_owner ON c.user_id = channel_owner.id
        JOIN user_platforms up ON channel_owner.id = up.user_id
        WHERE tm.user_id = ?
        AND tm.accepted_at IS NOT NULL
        AND up.platform = 'twitch'
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    # Build the full list of accounts this user can access
    available_accounts = []

    if own_channel:
        available_accounts.append({
            "channel_id":   own_channel["channel_id"],
            "display_name": own_channel["display_name"],
            "avatar_url":   own_channel["avatar_url"],
            "role":         "owner",
            "role_label":   "Owner — Your Channel",
        })

    for mod_channel in mod_channels:
        available_accounts.append({
            "channel_id":   mod_channel["channel_id"],
            "display_name": mod_channel["display_name"],
            "avatar_url":   mod_channel["avatar_url"],
            "role":         mod_channel["role"],
            "role_label":   "Lead Mod" if mod_channel["role"] == "lead_mod" else "Mod",
        })

    # Store core user info in session
    session.clear()
    session["user_id"]      = user_id
    session["display_name"] = twitch_user["display_name"]
    session["avatar_url"]   = twitch_user.get("profile_image_url")
    session["access_token"] = tokens["access_token"]

    # Step 5 — route them to the right place
    if len(available_accounts) == 1:
        # Only one account — skip the picker
        account = available_accounts[0]
        session["active_channel_id"] = account["channel_id"]
        session["active_role"]       = account["role"]
        return redirect(url_for("streamer.dashboard"))

    if len(available_accounts) == 0:
        # No channel yet — this shouldn't happen but handle it gracefully
        flash("Your account was created successfully. Setting up your channel.", "success")
        return redirect(url_for("streamer.dashboard"))

    # Multiple accounts — store the list and send to picker
    session["available_accounts"] = available_accounts
    return redirect(url_for("streamer.select_account"))


@app.route("/logout")
def logout():
    """Clear the session and return to the landing page."""
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    socketio.run(app, debug=app.config["DEBUG"], host="0.0.0.0", port=5000)