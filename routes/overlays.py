from flask import Blueprint, render_template, abort
from utils.security import validate_overlay_token

overlays_bp = Blueprint("overlays", __name__)

# =============================================================
# OBS browser source overlay routes
#
# These pages are loaded inside OBS as Browser Sources.
# They have a transparent background and listen for WebSocket
# events pushed from the StreamPilot backend.
#
# Each URL contains a unique token that identifies the channel.
# If the token is invalid the page returns a blank 403 —
# OBS just shows nothing, which is the correct behaviour.
#
# How to add to OBS:
#   Sources → Add → Browser Source
#   URL: https://stream-pilot.co.uk/overlay/alerts/your-token
#   Width: 1920  Height: 1080
#   Transparent background: ticked
# =============================================================

@overlays_bp.route("/alerts/<token>")
def alerts(token):
    """
    Alerts overlay
    Display the following as they happen
        Follow
        Subs
        Raids
        Bits
    Listen for 'alert' WebSocket events from the backend.

    Recommended OBS settings:
        Size 1920 x 1080 (match you stream canvas)
        Background: transparent
        Position: top of the source stack
    """

    channel_id = validate_overlay_token(token, "alerts")
    if not channel_id:
        abort(403)
    return render_template(
        "overlay/alerts.html",
        token=token,
        channel_id=channel_id
    )

@overlays_bp.route("/panels/<token>")
def panels(token):
    """
    Timed panels overlay.
    Displays scheduled information panels on stream. 
    Listens for 'panel_show' and 'panel_hide' WebSocket events.

    Recommended OBS settings:
        Size: match the area you want panels to appear in
        Background: transparent
        Position: above your game/camera source  
    """
    channel_id = validate_overlay_token(token, "panels")
    if not channel_id:
        abort(403)
    return render_template(
        "overlays/panels.html",
        token=token,
        channel_id=channel_id
    )

@overlays_bp.route("/celebrations/<token>")
def celebrations(token):
    """
    Celebrations overlay.
    Displays fireworks and confetti for followers, subs and raids.
    Listens for 'celebrate' WebSocket event from the backend.

    Recommended OBS settings:
        Size: 1920 x 1080 (match your stream canvus)
        Background: transparent
        Position: top of the source stack, above alerts
    """
    channel_id = validate_overlay_token(token, "celebrations")
    if not channel_id:
        abort(403)
    return render_template(
        "overlay/celebrations.html",
        token=token,
        channel_id= channel_id
    )
