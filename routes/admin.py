from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.db import get_db_connection, placeholder
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
from datetime import datetime, timedelta

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/login", methods=["GET", "POST"])
@ip_whitelisted
def login():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter your username and password.", "error")
            return render_template("admin/login.html")
        
        conn = get_db_connection()
        p = placeholder()

        admin_user = conn.execute(
            f"""
            SELECT *
            FROM admin_users
            WHERE username = {p}
            AND active = 1
            """,
            (username,)
        ).fetchone()

        conn.close()

        if not admin_user or not verify_password(password, admin_user["password_hash"]):
            flash("Incorrect username or password.", "error")
            return render_template("admin/login.html")
        
        if password_is_expired(admin_user["password_expires_at"]):
            session["admin_id"] = admin_user["id"]
            session["admin_role"] = admin_user["role"]
            session["admin_username"] = admin_user["username"]
            session["admin_password_expired"] = True
            flash("Your password has expired, Please set a new one to continue.", "warn")
            return redirect(url_for("admin.change_password"))
        
        if admin_user["must_change_password"]:
            session["admin_id"] = admin_user["id"]
            session["admin_role"] = admin_user["role"]
            session["admin_username"] = admin_user["username"]
            session["admin_password_expired"] = True
            flash("You must set a new password before you can login to the application.", "warn")
            return redirect(url_for("admin.change_password"))
        
        session.clear()
        session["admin_id"] = admin_user["id"]
        session["admin_role"] = admin_user["role"]
        session["admin_username"] = admin_user["username"]
        session["admin_password_expired"] = False

        conn = get_db_connection()
        p = placeholder()
        conn.execute(
            f"UPDATE admin_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = {p}",
            (admin_user["id"],)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("admin.dashboard"))
    
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop('admin_id', None)
    session.pop("admin_role", None)
    session.pop("admin_username", None)
    session.pop("admin_password_expired", None)
    flash("You have been logged out you may close your browser window", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/change-password", methods=["GET", "POST"])
@ip_whitelisted
@admin_login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        conn = get_db_connection()
        p = placeholder()

        admin_user = conn.execute(
            f"SELECT * FROM admin_users WHERE id = {p}",
            (current_admin_id(),)
        ).fetchone()

        errors = []

        if not admin_user["must_change_password"]:
            if not verify_password(current_password, admin_user["password_hash"]):
                errors.append("Your current password is incorrect.")

        errors.extend(validate_password(new_password, confirm_password))

        if not errors and password_in_history(current_admin_id(), new_password):
            errors.append("You cannot reuse any of your last 6 passwords.")

        if errors:
            conn.close()
            for error in errors:
                flash(error, "error")
            return render_template("admin/change_password.html")

        new_hash = hash_password(new_password)
        expiry = datetime.utcnow() + timedelta(days=45)

        conn.execute(
            f"""
            UPDATE admin_users SET
                password_hash = {p},
                password_changed_at = CURRENT_TIMESTAMP,
                password_expires_at = {p},
                must_change_password = 0
            WHERE id = {p}
            """,
            (new_hash, expiry.isoformat(), current_admin_id())
        )
        conn.commit()

        save_password_to_history(current_admin_id(), new_hash)
        conn.close()

        session["admin_password_expired"] = False
        flash("Your password has been changed successfully.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/change_password.html")


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@ip_whitelisted
@admin_login_required
def dashboard():
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


@admin_bp.route("/beta-requests")
@ip_whitelisted
@admin_login_required
def beta_requests():
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
    import secrets

    conn = get_db_connection()
    p = placeholder()

    beta_request = conn.execute(
        f"SELECT * FROM beta_requests WHERE id = {p}",
        (request_id,)
    ).fetchone()

    if not beta_request:
        conn.close()
        flash("Beta request not found.", "error")
        return redirect(url_for("admin.beta_requests"))

    code = secrets.token_urlsafe(6).upper()[:8]

    conn.execute(
        f"""
        INSERT INTO beta_codes (code, note, created_by)
        VALUES ({p}, {p}, {p})
        """,
        (code, f"Generated for {beta_request['email']}", current_admin_id())
    )

    conn.execute(
        f"""
        UPDATE beta_requests SET
            status = 'approved',
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = {p}
        WHERE id = {p}
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
    conn = get_db_connection()
    p = placeholder()

    conn.execute(
        f"""
        UPDATE beta_requests SET
            status = 'rejected',
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = {p}
        WHERE id = {p}
        """,
        (current_admin_id(), request_id)
    )
    conn.commit()
    conn.close()

    flash("Beta request rejected.", "success")
    return redirect(url_for("admin.beta_requests"))


@admin_bp.route("/beta-codes")
@ip_whitelisted
@admin_login_required
def beta_codes():
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
    import secrets

    note = request.form.get("note", "").strip()
    code = secrets.token_urlsafe(6).upper()[:8]

    conn = get_db_connection()
    p = placeholder()
    conn.execute(
        f"""
        INSERT INTO beta_codes (code, note, created_by)
        VALUES ({p}, {p}, {p})
        """,
        (code, note or None, current_admin_id())
    )
    conn.commit()
    conn.close()

    flash(f"Beta code generated: {code}", "success")
    return redirect(url_for("admin.beta_codes"))


@admin_bp.route("/users")
@ip_whitelisted
@admin_login_required
def users():
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


@admin_bp.route("/admin-users")
@ip_whitelisted
@owner_required
def admin_users():
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
            p = placeholder()

            existing = conn.execute(
                f"SELECT id FROM admin_users WHERE username = {p} OR email = {p}",
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
            f"""
            INSERT INTO admin_users
                (username, email, password_hash, role,
                 must_change_password, created_by)
            VALUES ({p}, {p}, {p}, {p}, 1, {p})
            """,
            (username, email, password_hash, role, current_admin_id())
        )
        conn.commit()

        new_admin_id = conn.execute(
            f"SELECT id FROM admin_users WHERE username = {p}",
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
    if admin_user_id == current_admin_id():
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.admin_users"))

    conn = get_db_connection()
    p = placeholder()
    conn.execute(
        f"UPDATE admin_users SET active = 0 WHERE id = {p}",
        (admin_user_id,)
    )
    conn.commit()
    conn.close()

    flash("Admin user deactivated.", "success")
    return redirect(url_for("admin.admin_users"))