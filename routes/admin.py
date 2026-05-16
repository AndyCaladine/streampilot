from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.db import get_db_connection
from utils.helpers import admin_login_required, owner_required, current_admin_id, current_admin_role
from utils.security import (
    ip_whitelisted,
    hash_password,
    verify_password,
    password_in_history,
    save_password_to_history,
    password_is_expired
)
from utils.helpers import validate_password

admin_bp = Blueprint("admin", __name__)


# =============================================================
# Admin login
# =============================================================

@admin_bp.route("/login", methods=["GET", "POST"])
@ip_whitelisted
def login():
    """
    Admin login page.
    Username and password only - no Twitch OAuth. 
    Checks in order:
        1. IP whitelist (handled by @ip_whitelisted decorator)
        2. Username exists and account is active
        3. Password is correct
        4. Password has not expired
    On success sets the admin session and redirects to the dashboard. 
    On fail flash a error - same message for wrong username
    or wrong password to aviod leaking with one was wrong.
    """
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter your username and password.", "error")
            return render_template("admin/login.html")
        
        conn = get_db_connection()

        admin_user = conn.execute(
            """
            SELECT *
            FROM admin_users
            WHERE username = ?
            AND active = 1
            """,
            (username,)
        ).fetchone()

        conn.close()

        # Use the same error message for wrong username or wrong password
        # This prevents any attackers knowing which one is incorrect
        if not admin_user or not verify_password(password, admin_user["password_hash"]):
            flash("Incorrect username or password.", "error")
            return render_template("admin/login.html")
        
        # Check if the password has expired
        if password_is_expired(admin_user["password_expires_at"]):
            # Store minimal session so they can only access change password
            session["admin_id"] = admin_user["id"]
            session["admin_role"] = admin_user["role"]
            session["admin_username"] = admin_user["username"]
            session["admin_password_expired"] = True
            flash("Your password has expired, Please set a new one to continue.", "warn")
            return redirect(url_for("admin.change_password"))
        
        # Check if admin has been flagged to change password
        if admin_user["must_change_password"]:
            session["admin_id"] = admin_user["id"]
            session["admin_role"] = admin_user["role"]
            session["admin_username"] = admin_user["username"]
            session["admin_password_expired"] = True
            flash("You must set a new password before you can login to the application.", "warn")
            return redirect(url_for("admin.change_password"))
        
        # Successful login = set full session
        session.clear()
        session["admin_id"] = admin_user["id"]
        session["admin_role"] = admin_user["role"]
        session["admin_username"] = admin_user["username"]
        session["admin_password_expired"] = False

        # Update last login time
        conn = get_db_connection()
        conn.execute(
            "UPDATE admin_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (admin_user["id"],)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("admin.dashboard"))
    
    return render_template("admin/login.html")

@admin_bp.route("/logout")
def logout():
    """
    Clear the admin session and return to the admin login page.
    Only clears admin session keys - does not affect any 
    streamer session the user may also have open
    """
    session.pop('admin_id', None)
    session.pop("admin_role", None)
    session.pop("admin_username", None)
    session.pop("admin_password_expired", None)
    flash("You have been logged out you may close your browser window", "success")
    return redirect(url_for("admin.login"))

# =============================================================
# Password management
# =============================================================

@admin_bp.route("/change-password", methods=["GET", "POST"])
@ip_whitelisted
@admin_login_required
def change_password():
    """
    Admin password change page.
    Enforces all password rules:
      - Minimum 8 characters
      - At least one uppercase, lowercase, number, special character
      - Cannot match any of the last 6 passwords
      - Sets new expiry 45 days from now
      - Clears the must_change_password flag
    """
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        conn = get_db_connection()

        admin_user = conn.execute(
            "SELECT * FROM admin_users WHERE id = ?",
            (current_admin_id(),)
        ).fetchone()

        errors = []

        # Verify current password — skip if forced change by owner
        if not admin_user["must_change_password"]:
            if not verify_password(current_password, admin_user["password_hash"]):
                errors.append("Your current password is incorrect.")

        # Validate the new password meets requirements
        errors.extend(validate_password(new_password, confirm_password))

        # Check it has not been used in the last 6 passwords
        if not errors and password_in_history(current_admin_id(), new_password):
            errors.append("You cannot reuse any of your last 6 passwords.")

        if errors:
            conn.close()
            for error in errors:
                flash(error, "error")
            return render_template("admin/change_password.html")

        # All checks passed — hash and save the new password
        new_hash = hash_password(new_password)

        conn.execute(
            """
            UPDATE admin_users SET
                password_hash = ?,
                password_changed_at = CURRENT_TIMESTAMP,
                password_expires_at = datetime('now', '+45 days'),
                must_change_password = 0
            WHERE id = ?
            """,
            (new_hash, current_admin_id())
        )
        conn.commit()

        # Save to password history
        save_password_to_history(current_admin_id(), new_hash)

        conn.close()

        session["admin_password_expired"] = False
        flash("Your password has been changed successfully.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/change_password.html")


# =============================================================
# Dashboard
# =============================================================

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@ip_whitelisted
@admin_login_required
def dashboard():
    """
    Admin dashboard — platform overview.
    Shows key stats at a glance:
      - Total users
      - Active beta codes
      - Pending beta requests
      - Total channels
    """
    conn = get_db_connection()

    stats = {
        "total_users": conn.execute(
            "SELECT COUNT(*) as total FROM users"
        ).fetchone()["total"],

        "pending_requests": conn.execute(
            "SELECT COUNT(*) as total FROM beta_requests WHERE status = 'pending'"
        ).fetchone()["total"],

        "active_beta_codes": conn.execute(
            "SELECT COUNT(*) as total FROM beta_codes WHERE used_at IS NULL"
        ).fetchone()["total"],

        "total_channels": conn.execute(
            "SELECT COUNT(*) as total FROM channels"
        ).fetchone()["total"],
    }

    conn.close()
    return render_template("admin/dashboard.html", stats=stats)


# =============================================================
# Beta requests
# =============================================================

@admin_bp.route("/beta-requests")
@ip_whitelisted
@admin_login_required
def beta_requests():
    """
    List all beta access requests.
    Sorted by status (pending first) then by date received.
    """
    conn = get_db_connection()

    requests_list = conn.execute(
        """
        SELECT br.*, au.username as reviewed_by_username
        FROM beta_requests br
        LEFT JOIN admin_users au ON br.reviewed_by = au.id
        ORDER BY
            CASE br.status WHEN 'pending' THEN 0 ELSE 1 END,
            br.created_at DESC
        """
    ).fetchall()

    conn.close()
    return render_template("admin/beta_requests.html", requests=requests_list)


@admin_bp.route("/beta-requests/<int:request_id>/approve", methods=["POST"])
@ip_whitelisted
@admin_login_required
def approve_beta_request(request_id):
    """
    Approve a beta request and generate a beta code for the user.
    The generated code is shown on screen for the admin to send
    to the applicant manually.
    """
    import secrets

    conn = get_db_connection()

    beta_request = conn.execute(
        "SELECT * FROM beta_requests WHERE id = ?",
        (request_id,)
    ).fetchone()

    if not beta_request:
        conn.close()
        flash("Beta request not found.", "error")
        return redirect(url_for("admin.beta_requests"))

    # Generate a readable beta code — uppercase, 8 characters
    code = secrets.token_urlsafe(6).upper()[:8]

    conn.execute(
        """
        INSERT INTO beta_codes (code, note, created_by)
        VALUES (?, ?, ?)
        """,
        (code, f"Generated for {beta_request['email']}", current_admin_id())
    )

    conn.execute(
        """
        UPDATE beta_requests SET
            status = 'approved',
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?
        WHERE id = ?
        """,
        (current_admin_id(), request_id)
    )
    conn.commit()
    conn.close()

    flash(f"Request approved. Beta code for {beta_request['email']}: {code}", "success")
    return redirect(url_for("admin.beta_requests"))


@admin_bp.route("/beta-requests/<int:request_id>/reject", methods=["POST"])
@ip_whitelisted
@admin_login_required
def reject_beta_request(request_id):
    """
    Reject a beta request.
    The request is kept in the database for reference.
    """
    conn = get_db_connection()

    conn.execute(
        """
        UPDATE beta_requests SET
            status = 'rejected',
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?
        WHERE id = ?
        """,
        (current_admin_id(), request_id)
    )
    conn.commit()
    conn.close()

    flash("Beta request rejected.", "success")
    return redirect(url_for("admin.beta_requests"))


# =============================================================
# Beta codes
# =============================================================

@admin_bp.route("/beta-codes")
@ip_whitelisted
@admin_login_required
def beta_codes():
    """
    List all beta codes — used and unused.
    Shows who created each code and whether it has been redeemed.
    """
    conn = get_db_connection()

    codes = conn.execute(
        """
        SELECT bc.*, au.username as created_by_username,
               u.display_name as used_by_name
        FROM beta_codes bc
        LEFT JOIN admin_users au ON bc.created_by = au.id
        LEFT JOIN users u ON bc.used_by = u.id
        ORDER BY bc.created_at DESC
        """
    ).fetchall()

    conn.close()
    return render_template("admin/beta_codes.html", codes=codes)


@admin_bp.route("/beta-codes/generate", methods=["POST"])
@ip_whitelisted
@admin_login_required
def generate_beta_code():
    """
    Manually generate a beta code without an associated request.
    Used when inviting someone directly rather than via the
    beta request form.
    """
    import secrets

    note = request.form.get("note", "").strip()
    code = secrets.token_urlsafe(6).upper()[:8]

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO beta_codes (code, note, created_by)
        VALUES (?, ?, ?)
        """,
        (code, note or None, current_admin_id())
    )
    conn.commit()
    conn.close()

    flash(f"Beta code generated: {code}", "success")
    return redirect(url_for("admin.beta_codes"))


# =============================================================
# User management
# =============================================================

@admin_bp.route("/users")
@ip_whitelisted
@admin_login_required
def users():
    """
    List all StreamPilot users.
    Shows platform, tier, and when they joined.
    """
    conn = get_db_connection()

    users_list = conn.execute(
        """
        SELECT u.*, up.platform, up.platform_login,
               up.platform_display_name, up.last_login_at as platform_last_login
        FROM users u
        LEFT JOIN user_platforms up ON u.id = up.user_id
        ORDER BY u.created_at DESC
        """
    ).fetchall()

    conn.close()
    return render_template("admin/users.html", users=users_list)


# =============================================================
# Admin user management — owner only
# =============================================================

@admin_bp.route("/admin-users")
@ip_whitelisted
@owner_required
def admin_users():
    """
    List all admin users.
    Owner only — managers and workers cannot see this page.
    """
    conn = get_db_connection()

    admin_users_list = conn.execute(
        """
        SELECT au.*, creator.username as created_by_username
        FROM admin_users au
        LEFT JOIN admin_users creator ON au.created_by = creator.id
        ORDER BY au.created_at ASC
        """
    ).fetchall()

    conn.close()
    return render_template("admin/admin_users.html", admin_users=admin_users_list)


@admin_bp.route("/admin-users/create", methods=["GET", "POST"])
@ip_whitelisted
@owner_required
def create_admin_user():
    """
    Create a new admin user.
    Owner only.
    New admin users are flagged must_change_password = 1
    so they are forced to set their own password on first login.
    The owner sets a temporary password to share with them securely.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "worker")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = validate_password(password, confirm)

        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email address is required.")
        if role not in ["owner", "manager", "worker"]:
            errors.append("Invalid role selected.")

        if not errors:
            conn = get_db_connection()

            existing = conn.execute(
                "SELECT id FROM admin_users WHERE username = ? OR email = ?",
                (username, email)
            ).fetchone()

            if existing:
                errors.append("An admin user with that username or email already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("admin/create_admin_user.html")

        password_hash = hash_password(password)

        conn.execute(
            """
            INSERT INTO admin_users
                (username, email, password_hash, role,
                 must_change_password, created_by)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (username, email, password_hash, role, current_admin_id())
        )
        conn.commit()

        new_admin_id = conn.execute(
            "SELECT id FROM admin_users WHERE username = ?",
            (username,)
        ).fetchone()["id"]

        save_password_to_history(new_admin_id, password_hash)
        conn.close()

        flash(f"Admin user '{username}' created successfully.", "success")
        return redirect(url_for("admin.admin_users"))

    return render_template("admin/create_admin_user.html")


@admin_bp.route("/admin-users/<int:admin_user_id>/deactivate", methods=["POST"])
@ip_whitelisted
@owner_required
def deactivate_admin_user(admin_user_id):
    """
    Deactivate an admin user account.
    Sets active = 0 — they cannot log in but their record is kept.
    Owner cannot deactivate their own account.
    """
    if admin_user_id == current_admin_id():
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.admin_users"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE admin_users SET active = 0 WHERE id = ?",
        (admin_user_id,)
    )
    conn.commit()
    conn.close()

    flash("Admin user deactivated.", "success")
    return redirect(url_for("admin.admin_users"))