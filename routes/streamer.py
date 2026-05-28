from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from utils.helpers import login_required, is_htmx

streamer_bp = Blueprint("streamer", __name__)

# =============================================================
# Streamer dashboard routes
# These routes render the HTML pages the streamer sees.
# They do not return data — they just render templates.
# All data for the page is fetched by JavaScript calling
# the /api/* routes after the page loads.
# =============================================================

@streamer_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Main dashboard - stream stats, event feed, active goals. 
    This will be the first page the streamer sees after login in. 
    """
    if is_htmx():
        return render_template("partials/dashboard_content.html")
    return render_template("dashboard.html")

@streamer_bp.route("/chat")
@login_required
def chat():
    """
    Live chat viewer with moderation tools. 
    This shows incoming chat messages and mod actions in real time. 
    """
    if is_htmx():
        return render_template("partials/chat_content.html")
    return render_template("chat.html")

@streamer_bp.route("/commands")
@login_required
def commands():
    """
    Bot command management. 
    Create, edit, enable and disable chat commands. 
    """
    if is_htmx():
        return render_template("partials/commands_content.html")
    return render_template("commands.html")

@streamer_bp.route("/alerts")
@login_required
def alerts():
    """
    Alert Config.
    Set up follow, sub, raid and bits alerts for OBS overlay.
    """
    if is_htmx():
        return render_template("partials/alerts_content.html")
    return render_template("alerts.html")

@streamer_bp.route("/panels")
@login_required
def panels():
    """
    Timed on screen panel management. 
    Create panels, set schedules and config animations. 
    """
    if is_htmx():
        return render_template("partials/panels_content.html")
    return render_template("panels.html")

@streamer_bp.route("/team")
@login_required
def team():
    """
    Team Management.
    Invite and manage mods and lead mods for the channel. 
    """
    if is_htmx():
        return render_template("partials/team_content.html")
    return render_template("team.html")

@streamer_bp.route("/settings")
@login_required
def settings():
    """
    Account and channel settings. 
    Manage overlay URLs, platform connections and preferances. 
    """
    if is_htmx():
        return render_template("partials/settings_content.html")
    return render_template("settings.html")

@streamer_bp.route("/select-account", methods=["GET", "POST"])
@login_required
def select_account():
    """
    Account Picker - shown when a user has access to more than
    one channel (their own plus channels they moderate).

    GET -   shows the picker with all available accounts.
    POST -  sets the chosen account in the session and goes
            to the dashboard for that channel. 

    Each account is shown with:
        Display name - the channel name
        Avatar - the channels Twitch avatar
        Role - Owner - Your channel | Lead Mod | Mod
    """
    available_accounts = session.get("available_accounts", [])

    if not available_accounts:
        return redirect(url_for("streamer.dashboard"))
    
    if request.method == "POST":
        chosen_channel_id = request.form.get("channel_id", type=int)

        # Verify the chosen channel is actually in their available list
        # Never trust form input - always validate against the session

        chosen_account = next(
            (account for account in available_accounts
             if account["channel_id"] == chosen_channel_id),
             None
        )

        if not chosen_account:
            flash("Invalid account selection. Please try again", "error")
            return render_template("select_account.html", accounts=available_accounts)
        
        session["active_channel_id"] = chosen_account["channel_id"]
        session["active_role"] = chosen_account["role"]

        return redirect(url_for("streamer.dashboard"))
    
    return render_template("select_account.html", accounts=available_accounts)
