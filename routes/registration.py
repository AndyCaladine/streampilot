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
    Public Beta Page. 
    GET - Shows the beta information page with two options:
        1. Request access to beta form
        2. Enter a beta code to register
    
    POST - handles the beta access requests for submits. 
    Stores the request in the database for the admin to review. 
    """
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        twitch_login = request.form.get("twitch_login", "").strip().lower()
        reason = request.form.get("reason", "").strip()

        errors = []

        if not name:
            errors.append("Your name is required.")
        if not email:
            errors.append("Your email address is required.")
        if not reason:
            errors.append("Please tell me why you would like access to the beta program")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("beta.html", form_data=request.form)
        
        conn = get_db_connection()

        # Check to see if the email address entered has already requested access. 
        existing = conn.execute(
            "SELECT id FROM beta_requests WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            flash("Thank you for your interest, We already have a beta request for that email address. I will be in touch soon", "info")
            return render_template("beta.html", form_data=request.form)
        
        conn.execute(
            """
            INSERT INTO beta_requests (name, email, twitch_login, reason)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, twitch_login or None, reason)
        )
        conn.commit()
        conn.close()

        flash("Thanks! Your beta request has been received. I will be in touch very soon.", "success")
        return redirect(url_for("registration.beta"))
    
    return render_template("beta.html", form_data={})

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

