from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils.db import get_db_connection, placeholder
from utils.helpers import generate_token
from datetime import datetime, timedelta
import re
import hashlib
import os

registration_bp = Blueprint("registration", __name__)


def hash_password(password):
    """Hash a password using SHA-256 with a random salt."""
    salt = os.urandom(32)
    key  = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + key.hex()


def verify_password(stored_hash, password):
    """Verify a password against a stored hash."""
    try:
        salt_hex, key_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        key  = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False


def password_meets_requirements(password):
    """Check password meets all complexity requirements."""
    if len(password) < 8:
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[^A-Za-z0-9]', password):
        return False
    return True


# =============================================================
# Beta request — public waitlist form on the landing page
# =============================================================

@registration_bp.route("/beta", methods=["GET", "POST"])
def beta():
    if request.method == "POST":
        first_name        = request.form.get("first_name", "").strip()
        streamer_tag      = request.form.get("streamer_tag", "").strip()
        email             = request.form.get("email", "").strip().lower()
        platform          = request.form.get("platform", "").strip()
        reason            = request.form.get("reason", "").strip()
        consent_data      = 1 if request.form.get("consent_data") else 0
        consent_marketing = 1 if request.form.get("consent_marketing") else 0

        errors = []
        if not first_name:
            errors.append("Your name is required.")
        if not streamer_tag:
            errors.append("Your streamer tag is required.")
        if not email:
            errors.append("Your email address is required.")
        if not platform:
            errors.append("Please select your primary platform.")
        if not reason:
            errors.append("Please tell us why you'd be a good fit.")
        if not consent_data:
            errors.append("You must agree to us storing your details to process your application.")

        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("index") + "#beta")

        conn = get_db_connection()
        p    = placeholder()

        existing = conn.execute(
            f"SELECT id FROM beta_requests WHERE email = {p}",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            flash("We already have a waitlist application for that email address. We will be in touch soon.", "info")
            return redirect(url_for("index") + "#beta")

        conn.execute(
            f"""
            INSERT INTO beta_requests
                (name, email, streamer_tag, platform, reason,
                 consent_data, consent_marketing)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            (first_name, email, streamer_tag, platform, reason,
             consent_data, consent_marketing)
        )
        conn.commit()
        conn.close()

        flash("You're on the list. We'll be in touch when the time is right.", "success")
        return redirect(url_for("index") + "#beta")

    return redirect(url_for("index") + "#beta")


# =============================================================
# Validate beta code — AJAX endpoint called before form reveals
# =============================================================

@registration_bp.route("/validate-code", methods=["POST"])
def validate_code():
    data = request.get_json()
    code = (data.get("code", "") or "").strip()

    if not code or len(code) < 8:
        return jsonify({"valid": False, "message": "Code must be at least 8 characters."})

    conn = get_db_connection()
    p    = placeholder()

    beta_code = conn.execute(
        f"""
        SELECT id FROM beta_codes
        WHERE code = {p}
        AND used_at IS NULL
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        """,
        (code,)
    ).fetchone()

    conn.close()

    if not beta_code:
        return jsonify({
            "valid": False,
            "message": "That code is invalid or has already been used. Please contact Andy via the beta Discord for a new one."
        })

    return jsonify({"valid": True})


# =============================================================
# Join — registration form
# GET:  render the form
# POST: validate everything, create the StreamPilot account,
#       store user_id + beta_code in session, send to Twitch
# =============================================================

@registration_bp.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        code             = request.form.get("code", "").strip()
        full_name        = request.form.get("full_name", "").strip()
        chosen_name      = request.form.get("chosen_name", "").strip()
        email            = request.form.get("email", "").strip().lower()
        email_confirm    = request.form.get("email_confirm", "").strip().lower()
        password         = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        consent_data     = 1 if request.form.get("consent_data") else 0
        consent_twitch   = 1 if request.form.get("consent_twitch") else 0
        consent_marketing = 1 if request.form.get("consent_marketing") else 0

        # ---- Server-side validation -------------------------
        errors = []

        if not code or len(code) < 8:
            errors.append("A valid beta access code is required.")

        if not full_name:
            errors.append("Your full name is required.")

        if not chosen_name:
            errors.append("A display name is required.")

        if not email:
            errors.append("Your email address is required.")
        elif email != email_confirm:
            errors.append("Email addresses do not match.")

        if not password:
            errors.append("A password is required.")
        elif password != password_confirm:
            errors.append("Passwords do not match.")
        elif not password_meets_requirements(password):
            errors.append("Password must be at least 8 characters and include uppercase, lowercase, a number and a special character.")

        if not consent_data:
            errors.append("You must agree to StreamPilot storing your account details.")

        if not consent_twitch:
            errors.append("You must agree to StreamPilot connecting to your Twitch account.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("join.html")

        conn = get_db_connection()
        p    = placeholder()

        # ---- Validate beta code -----------------------------
        beta_code = conn.execute(
            f"""
            SELECT id FROM beta_codes
            WHERE code = {p}
            AND used_at IS NULL
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            (code,)
        ).fetchone()

        if not beta_code:
            conn.close()
            flash("That beta code is invalid or has already been used.", "error")
            return render_template("join.html")

        # ---- Check email not already registered -------------
        existing = conn.execute(
            f"SELECT id FROM users WHERE email = {p}",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            flash("An account with that email address already exists. Please log in instead.", "error")
            return render_template("join.html")

        # ---- Create the StreamPilot account -----------------
        password_hash = hash_password(password)

        cur = conn.execute(
            f"""
            INSERT INTO users (full_name, chosen_name, display_name, email)
            VALUES ({p}, {p}, {p}, {p})
            """,
            (full_name, chosen_name, chosen_name, email)
        )
        user_id = cur.lastrowid
        conn.commit()

        # ---- Store password in user_preferences -------------
        # We use user_preferences as a simple KV store so the
        # users table stays clean and platform-agnostic.
        conn.execute(
            f"""
            INSERT INTO user_preferences (user_id, preference, value)
            VALUES ({p}, 'password_hash', {p})
            """,
            (user_id, password_hash)
        )

        # ---- Store consent ---------------------------------- 
        conn.execute(
            f"""
            INSERT INTO user_preferences (user_id, preference, value)
            VALUES ({p}, 'consent_data', {p})
            """,
            (user_id, str(consent_data))
        )
        conn.execute(
            f"""
            INSERT INTO user_preferences (user_id, preference, value)
            VALUES ({p}, 'consent_twitch', {p})
            """,
            (user_id, str(consent_twitch))
        )
        conn.execute(
            f"""
            INSERT INTO user_preferences (user_id, preference, value)
            VALUES ({p}, 'consent_marketing', {p})
            """,
            (user_id, str(consent_marketing))
        )
        conn.commit()
        conn.close()

        # ---- Store in session for Twitch callback -----------
        session["pending_user_id"] = user_id
        session["beta_code"]       = code

        return redirect(url_for("login"))

    return render_template("join.html")


# =============================================================
# Invite — mod invite link handler
# =============================================================

@registration_bp.route("/invite/<token>")
def accept_invite(token):
    conn = get_db_connection()
    p    = placeholder()

    invite = conn.execute(
        f"""
        SELECT *
        FROM invite_tokens
        WHERE token = {p}
        AND used_at IS NULL
        AND expires_at > CURRENT_TIMESTAMP
        """,
        (token,)
    ).fetchone()

    conn.close()

    if not invite:
        flash("This invite link is invalid or has expired. Please contact your streamer to send a new one.", "error")
        return redirect(url_for("index"))

    session["invite_token"] = token
    flash("Please sign in with Twitch to accept your invitation.", "info")
    return redirect(url_for("login"))