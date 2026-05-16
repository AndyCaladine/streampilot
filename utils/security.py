import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, current_app
from functools import wraps
from utils.db import get_db_connection


# =============================================================
# IP whitelist
# Checked on every /admin request before anything else runs.
# Configured in .env as a comma-separated list of allowed IPs.
# In development 127.0.0.1 is always allowed.
# =============================================================

def get_whitelisted_ips():
    """
    Read the allowed IP addresses from the app config.
    Always includes localhost so development works without config.
    """
    configured = current_app.config.get("ADMIN_ALLOWED_IPS", "")
    allowed_ips = [ip.strip() for ip in configured.split(",") if ip.strip()]
    allowed_ips.extend(["127.0.0.1", "::1"])
    return allowed_ips


def ip_whitelisted(function):
    """
    Decorator that checks the request IP against the whitelist.
    Returns a 403 with no explanation if the IP is not allowed.
    Used on all /admin routes.

    Usage:
        @admin_bp.route("/dashboard")
        @ip_whitelisted
        @admin_login_required
        def dashboard():
            ...

    Note: ip_whitelisted must always be the outermost decorator
    so it runs first before any other checks.
    """
    @wraps(function)
    def decorated_function(*args, **kwargs):
        request_ip = request.remote_addr
        if request_ip not in get_whitelisted_ips():
            return "", 403
        return function(*args, **kwargs)
    return decorated_function


# =============================================================
# Password hashing
# Thin wrappers around werkzeug so route files never import
# werkzeug directly — all password logic stays in this file.
# =============================================================

def hash_password(plain_text_password):
    """
    Hash a plain text password for storage.
    Uses werkzeug's generate_password_hash which uses PBKDF2-SHA256.
    Never store plain text passwords — always hash first.
    """
    return generate_password_hash(plain_text_password)


def verify_password(plain_text_password, stored_hash):
    """
    Check a plain text password against a stored hash.
    Returns True if they match, False if not.
    """
    return check_password_hash(stored_hash, plain_text_password)


# =============================================================
# Admin password history
# Enforces that admin users cannot reuse their last 6 passwords.
# =============================================================

def password_in_history(admin_user_id, plain_text_password):
    """
    Check if a password has been used in the last 6 passwords
    for this admin user.
    Returns True if it has been used before — reject the password.
    Returns False if it is new — safe to use.
    """
    conn = get_db_connection()

    history = conn.execute(
        """
        SELECT password_hash
        FROM admin_password_history
        WHERE admin_user_id = ?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (admin_user_id,)
    ).fetchall()

    conn.close()

    for history_row in history:
        if verify_password(plain_text_password, history_row["password_hash"]):
            return True
    return False


def save_password_to_history(admin_user_id, password_hash):
    """
    Save a password hash to the admin user's password history.
    Prunes the oldest entry if history exceeds 6 records.
    Called every time an admin user successfully changes their password.
    """
    conn = get_db_connection()

    conn.execute(
        """
        INSERT INTO admin_password_history (admin_user_id, password_hash)
        VALUES (?, ?)
        """,
        (admin_user_id, password_hash)
    )
    conn.commit()

    # Count how many history records exist for this user
    history_count = conn.execute(
        """
        SELECT COUNT(*) as total
        FROM admin_password_history
        WHERE admin_user_id = ?
        """,
        (admin_user_id,)
    ).fetchone()["total"]

    # Prune the oldest record if we have more than 6
    if history_count > 6:
        oldest = conn.execute(
            """
            SELECT id
            FROM admin_password_history
            WHERE admin_user_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (admin_user_id,)
        ).fetchone()

        if oldest:
            conn.execute(
                "DELETE FROM admin_password_history WHERE id = ?",
                (oldest["id"],)
            )
            conn.commit()

    conn.close()


# =============================================================
# Password expiry
# Admin passwords must be changed every 45 days.
# =============================================================

def password_is_expired(password_expires_at):
    """
    Check if an admin user's password has expired.
    Returns True if expired — redirect to change password page.
    Returns False if still valid.
    """
    if not password_expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(password_expires_at)
        return datetime.utcnow() > expiry
    except Exception:
        return True


# =============================================================
# Overlay tokens
# Each OBS browser source URL contains a unique token that
# identifies which channel and overlay type it belongs to.
# Regenerating a token instantly invalidates the old URL.
# =============================================================

def get_or_create_overlay_token(channel_id, overlay_type):
    """
    Get the existing overlay token for a channel and overlay type,
    or create one if it does not exist yet.
    overlay_type must be: alerts | panels | celebrations
    Returns the token string.
    """
    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT token
        FROM overlay_tokens
        WHERE channel_id = ? AND overlay_type = ?
        """,
        (channel_id, overlay_type)
    ).fetchone()

    if existing:
        conn.close()
        return existing["token"]

    new_token = secrets.token_urlsafe(32)
    conn.execute(
        """
        INSERT INTO overlay_tokens (channel_id, overlay_type, token)
        VALUES (?, ?, ?)
        """,
        (channel_id, overlay_type, new_token)
    )
    conn.commit()
    conn.close()
    return new_token


def regenerate_overlay_token(channel_id, overlay_type):
    """
    Generate a brand new token for an overlay, invalidating the old URL.
    Called when a streamer resets their overlay URL in settings.
    Returns the new token string.
    """
    new_token = secrets.token_urlsafe(32)
    conn = get_db_connection()

    conn.execute(
        """
        INSERT INTO overlay_tokens (channel_id, overlay_type, token)
        VALUES (?, ?, ?)
        ON CONFLICT(channel_id, overlay_type)
        DO UPDATE SET token = excluded.token,
                      created_at = CURRENT_TIMESTAMP
        """,
        (channel_id, overlay_type, new_token)
    )
    conn.commit()
    conn.close()
    return new_token


def validate_overlay_token(token, overlay_type):
    """
    Validate an overlay URL token and return the channel_id.
    Returns the channel_id integer if valid.
    Returns None if the token does not exist or does not match
    the expected overlay type.
    Called by the overlay routes to authenticate OBS browser sources.
    """
    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT channel_id
        FROM overlay_tokens
        WHERE token = ? AND overlay_type = ?
        """,
        (token, overlay_type)
    ).fetchone()

    conn.close()
    return row["channel_id"] if row else None