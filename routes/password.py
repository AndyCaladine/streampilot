# =============================================================
# password.py — change password and forgot/reset password flows
# =============================================================

import secrets
import hashlib
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import get_db_connection, placeholder, get_db_type
from utils.helpers import login_required, validate_password
from utils.email import send_password_changed_email, send_password_reset_email

password_bp = Blueprint("password", __name__)


# ---- Helpers ------------------------------------------------
def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key  = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(stored: str, provided: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":")
        salt    = bytes.fromhex(salt_hex)
        key     = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac("sha256", provided.encode("utf-8"), salt, 100000)
        return new_key == key
    except Exception:
        return False


def save_password_hash(conn, user_id: int, new_hash: str):
    p = placeholder()
    if get_db_type() == "postgres":
        conn.execute(
            f"""
            INSERT INTO user_preferences (user_id, preference, value)
            VALUES ({p}, 'password_hash', {p})
            ON CONFLICT (user_id, preference) DO UPDATE SET value = {p}
            """,
            (user_id, new_hash, new_hash)
        )
    else:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO user_preferences (user_id, preference, value)
            VALUES ({p}, 'password_hash', {p})
            """,
            (user_id, new_hash)
        )


# ---- Change password ----------------------------------------
@password_bp.route("/settings/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")

    current = request.form.get("current_password", "").strip()
    new     = request.form.get("new_password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()

    if not current or not new or not confirm:
        flash("All fields are required.", "error")
        return render_template("change_password.html")

    if new != confirm:
        flash("New passwords do not match.", "error")
        return render_template("change_password.html")

    errors = validate_password(new)
    if errors:
        flash(errors[0], "error")
        return render_template("change_password.html")

    conn = get_db_connection()
    p    = placeholder()

    user = conn.execute(
        f"SELECT id, email, chosen_name FROM users WHERE id = {p}",
        (session["user_id"],)
    ).fetchone()

    stored = conn.execute(
        f"""
        SELECT value FROM user_preferences
        WHERE user_id = {p} AND preference = 'password_hash'
        """,
        (session["user_id"],)
    ).fetchone()

    if not user or not stored or not verify_password(stored["value"], current):
        conn.close()
        flash("Current password is incorrect.", "error")
        return render_template("change_password.html")

    new_hash = hash_password(new)
    save_password_hash(conn, session["user_id"], new_hash)
    conn.commit()
    conn.close()

    send_password_changed_email(user["email"], user["chosen_name"] or "Pilot")

    flash("Password changed successfully.", "success")
    return redirect(url_for("streamer.settings"))


# ---- Forgot password ----------------------------------------
@password_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Please enter your email address.", "error")
        return render_template("forgot_password.html")

    conn = get_db_connection()
    p    = placeholder()

    user = conn.execute(
        f"SELECT id, chosen_name FROM users WHERE LOWER(email) = {p}",
        (email,)
    ).fetchone()

    # Always show the same message — never confirm if email exists
    if user:
        token      = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        conn.execute(
            f"DELETE FROM password_reset_tokens WHERE user_id = {p}",
            (user["id"],)
        )
        conn.execute(
            f"""
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES ({p}, {p}, {p})
            """,
            (user["id"], token, expires_at)
        )
        conn.commit()

        reset_url = url_for("password.reset_password", token=token, _external=True)
        send_password_reset_email(email, user["chosen_name"] or "Pilot", reset_url, expires_at)

        
    conn.close()

    flash("If that email is registered you'll receive a reset link shortly.", "success")
    return render_template("forgot_password.html")


# ---- Reset password -----------------------------------------
@password_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token") or request.form.get("token", "")

    if not token:
        flash("Invalid or missing reset token.", "error")
        return redirect(url_for("password.forgot_password"))

    conn = get_db_connection()
    p    = placeholder()

    record = conn.execute(
        f"""
        SELECT prt.id, prt.user_id, prt.expires_at, u.email, u.chosen_name
        FROM password_reset_tokens prt
        JOIN users u ON u.id = prt.user_id
        WHERE prt.token = {p}
        """,
        (token,)
    ).fetchone()

    if not record:
        conn.close()
        flash("This reset link is invalid or has already been used.", "error")
        return redirect(url_for("password.forgot_password"))

    # Check expiry
    expires_at = record["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        conn.execute(
            f"DELETE FROM password_reset_tokens WHERE token = {p}",
            (token,)
        )
        conn.commit()
        conn.close()
        flash("This reset link has expired. Please request a new one.", "error")
        return redirect(url_for("password.forgot_password"))

    if request.method == "GET":
        conn.close()
        return render_template("reset_password.html", token=token)

    new     = request.form.get("new_password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()

    if new != confirm:
        conn.close()
        flash("Passwords do not match.", "error")
        return render_template("reset_password.html", token=token)

    errors = validate_password(new)
    if errors:
        conn.close()
        flash(errors[0], "error")
        return render_template("reset_password.html", token=token)

    new_hash = hash_password(new)
    save_password_hash(conn, record["user_id"], new_hash)

    conn.execute(
        f"DELETE FROM password_reset_tokens WHERE token = {p}",
        (token,)
    )
    conn.commit()
    conn.close()

    flash("Password reset successfully. You can now log in.", "success")
    return redirect(url_for("login"))