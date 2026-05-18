import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, current_app
from functools import wraps
from utils.db import get_db_connection, placeholder


def get_whitelisted_ips():
    configured = current_app.config.get("ADMIN_ALLOWED_IPS", "")
    allowed_ips = [ip.strip() for ip in configured.split(",") if ip.strip()]
    allowed_ips.extend(["127.0.0.1", "::1"])
    return allowed_ips


def ip_whitelisted(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        request_ip = request.remote_addr
        if request_ip not in get_whitelisted_ips():
            return "", 403
        return function(*args, **kwargs)
    return decorated_function


def hash_password(plain_text_password):
    return generate_password_hash(plain_text_password)


def verify_password(plain_text_password, stored_hash):
    return check_password_hash(stored_hash, plain_text_password)


def password_in_history(admin_user_id, plain_text_password):
    conn = get_db_connection()
    p = placeholder()

    history = conn.execute(
        f"""
        SELECT password_hash
        FROM admin_password_history
        WHERE admin_user_id = {p}
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
    conn = get_db_connection()
    p = placeholder()

    conn.execute(
        f"""
        INSERT INTO admin_password_history (admin_user_id, password_hash)
        VALUES ({p}, {p})
        """,
        (admin_user_id, password_hash)
    )
    conn.commit()

    history_count = conn.execute(
        f"""
        SELECT COUNT(*) as total
        FROM admin_password_history
        WHERE admin_user_id = {p}
        """,
        (admin_user_id,)
    ).fetchone()["total"]

    if history_count > 6:
        oldest = conn.execute(
            f"""
            SELECT id
            FROM admin_password_history
            WHERE admin_user_id = {p}
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (admin_user_id,)
        ).fetchone()

        if oldest:
            conn.execute(
                f"DELETE FROM admin_password_history WHERE id = {p}",
                (oldest["id"],)
            )
            conn.commit()

    conn.close()


def password_is_expired(password_expires_at):
    if not password_expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(str(password_expires_at))
        return datetime.utcnow() > expiry
    except Exception:
        return True


def get_or_create_overlay_token(channel_id, overlay_type):
    conn = get_db_connection()
    p = placeholder()

    existing = conn.execute(
        f"""
        SELECT token
        FROM overlay_tokens
        WHERE channel_id = {p} AND overlay_type = {p}
        """,
        (channel_id, overlay_type)
    ).fetchone()

    if existing:
        conn.close()
        return existing["token"]

    new_token = secrets.token_urlsafe(32)
    conn.execute(
        f"""
        INSERT INTO overlay_tokens (channel_id, overlay_type, token)
        VALUES ({p}, {p}, {p})
        """,
        (channel_id, overlay_type, new_token)
    )
    conn.commit()
    conn.close()
    return new_token


def regenerate_overlay_token(channel_id, overlay_type):
    new_token = secrets.token_urlsafe(32)
    conn = get_db_connection()
    p = placeholder()

    conn.execute(
        f"""
        INSERT INTO overlay_tokens (channel_id, overlay_type, token)
        VALUES ({p}, {p}, {p})
        ON CONFLICT(channel_id, overlay_type)
        DO UPDATE SET token = EXCLUDED.token,
                      created_at = CURRENT_TIMESTAMP
        """,
        (channel_id, overlay_type, new_token)
    )
    conn.commit()
    conn.close()
    return new_token


def validate_overlay_token(token, overlay_type):
    conn = get_db_connection()
    p = placeholder()

    row = conn.execute(
        f"""
        SELECT channel_id
        FROM overlay_tokens
        WHERE token = {p} AND overlay_type = {p}
        """,
        (token, overlay_type)
    ).fetchone()

    conn.close()
    return row["channel_id"] if row else None