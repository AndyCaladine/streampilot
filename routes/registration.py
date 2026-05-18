from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.db import get_db_connection, placeholder
from utils.helpers import generate_token
from datetime import datetime, timedelta

registration_bp = Blueprint("registration", __name__)

@registration_bp.route("/beta", methods=["GET", "POST"])
def beta():
    if request.method == "POST":
        first_name   = request.form.get("first_name", "").strip()
        streamer_tag = request.form.get("streamer_tag", "").strip()
        email = request.form.get("email", "").strip().lower()
        platform = request.form.get("platform", "").strip()
        reason = request.form.get("reason", "").strip()
        consent_data = 1 if request.form.get("consent_data") else 0
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
        p = placeholder()

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


@registration_bp.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        code = request.form.get("code", "").strip()

        if not code:
            flash("Please enter your beta access code", "error")
            return render_template("join.html")
        
        conn = get_db_connection()
        p = placeholder()

        beta_code = conn.execute(
            f"""
            SELECT *
            FROM beta_codes
            WHERE code = {p}
            AND used_at IS NULL
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            (code,)
        ).fetchone()

        conn.close()

        if not beta_code:
            flash("Im sorry, that code is invalid or has already been used Please refer to the discord group for the next steps", "error")
            return render_template("join.html")
        
        session["beta_code"] = code
        return redirect(url_for("login"))
    
    return render_template("join.html")


@registration_bp.route("/invite/<token>")
def accept_invite(token):
    conn = get_db_connection()
    p = placeholder()

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
        flash("I am sorry this invite link is invalid or has expired. Please contact your streamer to activate a new link.", "error")
        return redirect(url_for("index"))
    
    session["invite_token"] = token
    flash("Please sign in with Twitch to accept your invitation.", "info")
    return redirect(url_for("login"))