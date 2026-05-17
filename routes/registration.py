from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.db import get_db_connection
from utils.helpers import generate_token
from datetime import datetime, timedelta

registration_bp = Blueprint("registration", __name__)


# =============================================================
# Beta access
# This will be a temporary function until the 
# application is in final production where the code 
# will then be commented out
# =============================================================

@registration_bp.route("/beta", methods=["GET", "POST"])
def beta():
    """
    Waitlist request handler.
    GET  — not used directly, form lives on index.html.
    POST — handles waitlist form submission from the landing page.
           Validates fields, checks for duplicate email, stores the
           request and redirects back to the landing page with a
           flash message.
    """
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

        existing = conn.execute(
            "SELECT id FROM beta_requests WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            flash("We already have a waitlist application for that email address. We will be in touch soon.", "info")
            return redirect(url_for("index") + "#beta")

        conn.execute(
            """
            INSERT INTO beta_requests
                (name, email, streamer_tag, platform, reason,
                 consent_data, consent_marketing)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (first_name, email, streamer_tag, platform, reason,
             consent_data, consent_marketing)
        )
        conn.commit()
        conn.close()

        flash("You're on the list. We'll be in touch when the time is right.", "success")
        return redirect(url_for("index") + "#beta")

    # GET — redirect to landing page beta section
    return redirect(url_for("index") + "#beta")

@registration_bp.route("/join", methods=["GET", "POST"])
def join():
    """
    Beta codes redeem page
    GET -   shows the code entry form
    POST -  Verifies the code and stores it in the session.
            then redirects to the Twitch OAuth to compleate
            the registration. The beta code is marked as used
            after OAuth completes in app.py once the 
            user record is created 
    """
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()

        if not code:
            flash("Please enter your beta access code", "error")
            return render_template("join.html")
        
        conn = get_db_connection()

        beta_code = conn.execute(
            """
            SELECT *
            FROM beta_codes
            WHERE code = ?
            AND used_at IS NULL
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            (code,)
        ).fetchone()

        conn.close()

        if not beta_code:
            flash("Im sorry, that code is invalid or has already been used Please refer to the discord group for the next steps", "error")
            return render_template("join.html")
        
        # Store the validated code in the session
        # It will be marked as used in app.py after the Twitch OAuth completes
        # and the user record is created in the db
        session["beta_code"] = code
        return redirect(url_for("login"))
    
    return render_template("join.html")

# =============================================================
# Mod invite acceptance
# =============================================================

@registration_bp.route("/invite/<token>")
def accept_invite(token):
    """
    Mod invite link handler.
    The streamer generates an invite link in the team management page. 
    The mod clicks the link, which validates the token and stores it
    in their session, then sends them to Twitch OAuth to sign in.
    After OAuth completes in app.py the invite is marked as accepted 
    and the team members row is created
    """
    conn = get_db_connection()

    invite = conn.execute(
        """
        SELECT *
        FROM invite_tokens
        WHERE token = ?
        AND used_at IS NULL
        AND expires_at > CURRENT_TIMESTAMP
        """,
        (token,)
    ).fetchone()

    conn.close()

    if not invite:
        flash("I am sorry this invite link is invalid or has expired. Please contact your streamer to activate a new link.", "error")
        return redirect(url_for("index"))
    
    # Store the invite token in the session so app.py can
    # process it after Twitch OAuth completes
    session["invite_token"] = token
    flash("Please sign in with Twitch to accept your invitation.", "info")
    return redirect(url_for("login"))

