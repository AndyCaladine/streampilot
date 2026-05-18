import secrets
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, jsonify


# =============================================================
# Authentication decorators
# Used on any route that requires the user to be signed in.
# =============================================================

def login_required(function):
    """
    Redirects to the landing page if no active streamer session.
    Use on all dashboard routes.

    Usage:
        @streamer_bp.route("/dashboard")
        @login_required
        def dashboard():
            ...
    """
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("index"))
        return function(*args, **kwargs)
    return decorated_function


def api_login_required(function):
    """
    Same as login_required but returns JSON 401 instead of a redirect.
    Use on all /api/* routes called by JavaScript fetch().

    Usage:
        @api_bp.route("/commands")
        @api_login_required
        def get_commands():
            ...
    """
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Not authenticated"}), 401
        return function(*args, **kwargs)
    return decorated_function


def admin_login_required(function):
    """
    Redirects to the admin login page if no active admin session.
    Use on all /admin/* routes except /admin/login itself.
    """
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        return function(*args, **kwargs)
    return decorated_function


def owner_required(function):
    """
    Restricts a route to admin users with the owner role only.
    Use on routes that create/delete admin accounts or change
    platform-wide settings.
    """
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        if session.get("admin_role") != "owner":
            return redirect(url_for("admin.dashboard"))
        return function(*args, **kwargs)
    return decorated_function


# =============================================================
# Session helpers
# Shorthand for reading common values from the session.
# =============================================================

def current_user_id():
    """Return the logged-in streamer's database user ID."""
    return session.get("user_id")


def current_channel_id():
    """Return the logged-in streamer's channel ID."""
    return session.get("active_channel_id")


def current_admin_id():
    """Return the logged-in admin's database ID."""
    return session.get("admin_id")


def current_admin_role():
    """Return the logged-in admin's role: owner | manager | worker."""
    return session.get("admin_role")


# =============================================================
# Token generation
# Used for overlay URLs, invite links, and beta codes.
# =============================================================

def generate_token(length=32):
    """
    Generate a cryptographically secure random URL-safe token.
    Default length of 32 produces a 43-character string.
    """
    return secrets.token_urlsafe(length)


# =============================================================
# Password validation
# Shared between admin password change and reset flows.
# Returns a list of error strings — empty list means valid.
# =============================================================

def validate_password(password, confirm_password=None):
    """
    Validate a password against StreamPilot's requirements.
    Pass confirm_password to also check they match.

    Requirements:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one number
      - At least one special character
    """
    errors = []

    if not password:
        errors.append("Password is required.")
        return errors

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")

    if not any(char.isupper() for char in password):
        errors.append("Password must include at least one uppercase letter.")

    if not any(char.islower() for char in password):
        errors.append("Password must include at least one lowercase letter.")

    if not any(char.isdigit() for char in password):
        errors.append("Password must include at least one number.")

    if not any(not char.isalnum() for char in password):
        errors.append("Password must include at least one special character.")

    if confirm_password is not None and password != confirm_password:
        errors.append("Passwords do not match.")

    return errors


# =============================================================
# Formatting helpers
# Small utility functions used across route files and templates.
# =============================================================

def format_number(number):
    """
    Format a number for display.
    1234 → "1,234"
    1500000 → "1.5M"
    """
    if number is None:
        return "—"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    return f"{number:,}"


def time_ago(datetime_string):
    """
    Convert an ISO datetime string to a human-readable time ago string.
    "2026-05-16T14:30:00" → "3 minutes ago"
    Returns "never" if the value is empty.
    """
    if not datetime_string:
        return "never"
    try:
        past = datetime.fromisoformat(datetime_string)
        difference = datetime.utcnow() - past
        total_seconds = int(difference.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s ago"
        if total_seconds < 3600:
            return f"{total_seconds // 60}m ago"
        if total_seconds < 86400:
            return f"{total_seconds // 3600}h ago"
        return f"{total_seconds // 86400}d ago"
    except Exception:
        return "unknown"