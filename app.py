from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, redirect, url_for, session, request, flash
from extensions import socketio
from config import Config

from routes.streamer import streamer_bp
from routes.admin import admin_bp
from routes.registration import registration_bp
from routes.overlays import overlays_bp
from routes.api import api_bp
from routes.password import password_bp

from datetime import datetime, timezone, timedelta
from utils.db import get_db_connection, close_db, placeholder


app = Flask(__name__)
app.config.from_object(Config)
socketio.init_app(app, cors_allowed_origins="*")

app.register_blueprint(streamer_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(registration_bp)
app.register_blueprint(overlays_bp, url_prefix="/overlay")
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(password_bp)

from routes import ws_events  # noqa: F401

from utils.db import close_db
app.teardown_appcontext(close_db)

def _calc_expiry(expires_in):
    if not expires_in:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))


@app.context_processor
def inject_user_theme():
    theme = "light"
    if session.get("user_id"):
        try:
            conn = get_db_connection()
            p = placeholder()
            row = conn.execute(
                f"""
                SELECT value FROM user_preferences
                WHERE user_id = {p} AND preference = 'theme'
                """,
                (session["user_id"],)
            ).fetchone()
            if row:
                theme = row["value"]
        except Exception:
            pass
    return {"current_user_theme": theme}


@app.context_processor
def inject_now():
    return {"now": datetime.now(timezone.utc)}


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("streamer.dashboard"))
    return render_template("index.html")


@app.route("/auth/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("streamer.dashboard"))

    if request.method == "POST":
        from routes.registration import verify_password
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        conn = get_db_connection()
        p    = placeholder()

        user = conn.execute(
            f"SELECT id, display_name FROM users WHERE email = {p}",
            (email,)
        ).fetchone()

        if not user:
            conn.close()
            flash("Email or password is incorrect.", "error")
            return render_template("login.html")

        stored = conn.execute(
            f"""
            SELECT value FROM user_preferences
            WHERE user_id = {p} AND preference = 'password_hash'
            """,
            (user["id"],)
        ).fetchone()

        if not stored or not verify_password(stored["value"], password):
            conn.close()
            flash("Email or password is incorrect.", "error")
            return render_template("login.html")

        conn.close()
        session["pending_user_id"] = user["id"]
        return redirect(url_for("twitch_auth"))

    return render_template("login.html")


@app.route("/auth/twitch")
def twitch_auth():
    import urllib.parse
    params = {
        "client_id":     app.config["TWITCH_CLIENT_ID"],
        "redirect_uri":  app.config["TWITCH_REDIRECT_URI"],
        "response_type": "code",
        "scope": " ".join([
            "user:read:email",
            "chat:read",
            "chat:edit",
            "channel:read:subscriptions",
            "channel:read:goals",
            "channel:read:polls",
            "channel:manage:polls",
            "channel:manage:predictions",
            "channel:manage:raids",
            "moderator:read:followers",
            "moderator:read:chatters",
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
    from utils.twitch import exchange_code, get_user
    from utils.db import get_db_connection

    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    tokens = exchange_code(code)
    if not tokens or "access_token" not in tokens:
        flash("Something went wrong signing in with Twitch. Please try again.", "error")
        return redirect(url_for("login"))

    twitch_user = get_user(tokens["access_token"])
    if not twitch_user:
        flash("We could not fetch your Twitch profile. Please try again.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    p = placeholder()

    existing_user = conn.execute(
        f"""
        SELECT u.id
        FROM users u
        JOIN user_platforms up ON u.id = up.user_id
        WHERE up.platform = 'twitch'
        AND up.platform_user_id = {p}
        """,
        (twitch_user["id"],)
    ).fetchone()

    if existing_user:
        # ---- Returning user — update tokens and last login --
        user_id = existing_user["id"]
        conn.execute(
            f"""
            UPDATE user_platforms SET
                platform_login        = {p},
                platform_display_name = {p},
                platform_avatar_url   = {p},
                access_token          = {p},
                refresh_token         = {p},
                token_expiry          = {p},
                last_login_at         = CURRENT_TIMESTAMP
            WHERE platform = 'twitch'
            AND platform_user_id = {p}
            """,
            (
                twitch_user["login"],
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                tokens["access_token"],
                tokens.get("refresh_token"),
                _calc_expiry(tokens.get("expires_in")),
                twitch_user["id"],
            )
        )
        conn.execute(
            f"UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = {p}",
            (user_id,)
        )
        conn.commit()

        # Register EventSub subscriptions for this broadcaster
        try:
            from utils.eventsub import register_subscriptions
            register_subscriptions(twitch_user["id"])
        except Exception as e:
            app.logger.error(f"[EventSub] Registration failed: {e}")

    else:
        # ---- New user — link Twitch to the account created on /join
        pending_user_id = session.get("pending_user_id")
        beta_code       = session.get("beta_code")

        if not pending_user_id or not beta_code:
            flash("You need a beta access code to create an account.", "error")
            return redirect(url_for("registration.join"))

        valid_code = conn.execute(
            f"""
            SELECT id FROM beta_codes
            WHERE code = {p}
            AND used_at IS NULL
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            (beta_code,)
        ).fetchone()

        if not valid_code:
            flash("Your beta code is no longer valid. Please contact us for a new one.", "error")
            return redirect(url_for("registration.join"))

        user_id = pending_user_id

        conn.execute(
            f"""
            INSERT INTO user_platforms
                (user_id, platform, platform_user_id, platform_login,
                 platform_display_name, platform_avatar_url,
                 access_token, refresh_token, token_expiry)
            VALUES ({p}, 'twitch', {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            (
                user_id,
                twitch_user["id"],
                twitch_user["login"],
                twitch_user["display_name"],
                twitch_user.get("profile_image_url"),
                tokens["access_token"],
                tokens.get("refresh_token"),
                _calc_expiry(tokens.get("expires_in")),
            )
        )

        conn.execute(
            f"""
            INSERT INTO channels (user_id, platform, platform_channel_id)
            VALUES ({p}, 'twitch', {p})
            """,
            (user_id, twitch_user["id"])
        )
        conn.commit()

        conn.execute(
            f"""
            UPDATE beta_codes
            SET used_at = CURRENT_TIMESTAMP, used_by = {p}
            WHERE code = {p}
            """,
            (user_id, beta_code)
        )
        conn.commit()

        session.pop("pending_user_id", None)
        session.pop("beta_code", None)

        # Register EventSub subscriptions for this broadcaster
        try:
            from utils.eventsub import register_subscriptions
            register_subscriptions(twitch_user["id"])
        except Exception as e:
            app.logger.error(f"[EventSub] Registration failed: {e}")

    # ---- Build available accounts for session ---------------
    own_channel = conn.execute(
        f"""
        SELECT c.id as channel_id, up.platform_display_name as display_name,
               up.platform_avatar_url as avatar_url, 'owner' as role
        FROM channels c
        JOIN users u ON c.user_id = u.id
        JOIN user_platforms up ON u.id = up.user_id
        WHERE u.id = {p} AND up.platform = 'twitch'
        """,
        (user_id,)
    ).fetchone()

    mod_channels = conn.execute(
        f"""
        SELECT c.id as channel_id, up.platform_display_name as display_name,
               up.platform_avatar_url as avatar_url, tm.role as role
        FROM team_members tm
        JOIN channels c ON tm.channel_id = c.id
        JOIN users channel_owner ON c.user_id = channel_owner.id
        JOIN user_platforms up ON channel_owner.id = up.user_id
        WHERE tm.user_id = {p}
        AND tm.accepted_at IS NOT NULL
        AND up.platform = 'twitch'
        """,
        (user_id,)
    ).fetchall()

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

    session.clear()
    session["user_id"]      = user_id
    session["display_name"] = twitch_user["display_name"]
    session["avatar_url"]   = twitch_user.get("profile_image_url")
    session["access_token"] = tokens["access_token"]

    if len(available_accounts) == 1:
        account = available_accounts[0]
        session["active_channel_id"] = account["channel_id"]
        session["active_role"]       = account["role"]
        return redirect(url_for("streamer.dashboard"))

    if len(available_accounts) == 0:
        flash("Your account was created successfully. Setting up your channel.", "success")
        return redirect(url_for("streamer.dashboard"))

    session["available_accounts"] = available_accounts
    return redirect(url_for("streamer.select_account"))


@app.route("/webhooks/twitch", methods=["POST"])
def twitch_webhook():
    import hmac
    import hashlib

    secret    = app.config["EVENTSUB_SECRET"].encode("utf-8")
    msg_id    = request.headers.get("Twitch-Eventsub-Message-Id", "")
    timestamp = request.headers.get("Twitch-Eventsub-Message-Timestamp", "")
    body      = request.get_data()

    # ── Verify signature ─────────────────────────────────────────
    sig_header = request.headers.get("Twitch-Eventsub-Message-Signature", "")
    hmac_msg   = (msg_id + timestamp).encode("utf-8") + body
    expected   = "sha256=" + hmac.new(secret, hmac_msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig_header):
        app.logger.warning("[Webhook] Invalid signature")
        return "Forbidden", 403

    data     = request.get_json()
    msg_type = request.headers.get("Twitch-Eventsub-Message-Type", "")

    # ── Challenge handshake ───────────────────────────────────────
    if msg_type == "webhook_callback_verification":
        return data["challenge"], 200, {"Content-Type": "text/plain"}

    # ── Revocation notice ─────────────────────────────────────────
    if msg_type == "revocation":
        app.logger.warning(f"[Webhook] Subscription revoked: {data}")
        return "", 204

    # ── Live event ────────────────────────────────────────────────
    if msg_type == "notification":
        event_type     = data.get("subscription", {}).get("type")
        event          = data.get("event", {})
        broadcaster_id = (
            event.get("broadcaster_user_id") or
            event.get("to_broadcaster_user_id")
        )

        payload = build_event_payload(event_type, event)

        if payload and broadcaster_id:
            socketio.emit("stream_event", payload, room=broadcaster_id)

    return "", 204


def build_event_payload(event_type, event):
    """Normalise a Twitch event into a consistent payload for the frontend."""

    if event_type == "channel.follow":
        return {
            "type":  "follow",
            "icon":  "💜",
            "title": f"{event.get('user_name')} followed!",
            "user":  event.get("user_name"),
            "ts":    event.get("followed_at"),
        }

    if event_type == "channel.subscribe":
        tier = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(
            event.get("tier"), "Tier 1"
        )
        return {
            "type":  "sub",
            "icon":  "⭐",
            "title": f"{event.get('user_name')} subscribed! ({tier})",
            "user":  event.get("user_name"),
            "tier":  tier,
            "ts":    None,
        }

    if event_type == "channel.subscription.message":
        tier    = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(
            event.get("tier"), "Tier 1"
        )
        months  = event.get("cumulative_months", 1)
        message = event.get("message", {}).get("text", "")
        return {
            "type":    "resub",
            "icon":    "🔄",
            "title":   f"{event.get('user_name')} resubbed for {months} months! ({tier})",
            "user":    event.get("user_name"),
            "message": message,
            "months":  months,
            "ts":      None,
        }

    if event_type == "channel.subscription.gift":
        tier  = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(
            event.get("tier"), "Tier 1"
        )
        total = event.get("total", 1)
        giver = event.get("user_name") or "An anonymous gifter"
        return {
            "type":  "gift",
            "icon":  "🎁",
            "title": f"{giver} gifted {total} sub{'s' if total > 1 else ''}! ({tier})",
            "user":  giver,
            "total": total,
            "ts":    None,
        }

    if event_type == "channel.cheer":
        bits = event.get("bits", 0)
        return {
            "type":    "cheer",
            "icon":    "💎",
            "title":   f"{event.get('user_name')} cheered {bits} bits!",
            "user":    event.get("user_name"),
            "bits":    bits,
            "message": event.get("message", ""),
            "ts":      None,
        }

    if event_type == "channel.raid":
        viewers = event.get("viewers", 0)
        return {
            "type":    "raid",
            "icon":    "🚀",
            "title":   f"{event.get('from_broadcaster_user_name')} raided with {viewers} viewers!",
            "user":    event.get("from_broadcaster_user_name"),
            "viewers": viewers,
            "ts":      None,
        }

    return None


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    socketio.run(app, debug=app.config["DEBUG"], host="0.0.0.0", port=5001)