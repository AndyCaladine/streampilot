import requests
from flask import current_app


TWITCH_API_BASE  = "https://api.twitch.tv/helix"
TWITCH_AUTH_BASE = "https://id.twitch.tv/oauth2"


# =============================================================
# Private helpers
# =============================================================

def _auth_headers(access_token):
    """
    Build the auth headers every Twitch API call requires.
    Every request to the Helix API needs both the Bearer token
    and the Client-Id header — missing either returns a 401.
    """
    return {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": current_app.config["TWITCH_CLIENT_ID"],
    }


# =============================================================
# OAuth
# =============================================================

def exchange_code(code):
    """
    Exchange the OAuth authorisation code for tokens.
    Called in app.py after Twitch redirects back to /auth/callback.
    Returns the full token response dict or None on failure.

    Response includes:
      access_token  — used to make API calls on behalf of the user
      refresh_token — used to get a new access token when it expires
      expires_in    — seconds until the access token expires
    """
    response = requests.post(f"{TWITCH_AUTH_BASE}/token", data={
        "client_id":     current_app.config["TWITCH_CLIENT_ID"],
        "client_secret": current_app.config["TWITCH_CLIENT_SECRET"],
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  current_app.config["TWITCH_REDIRECT_URI"],
    })
    return response.json() if response.ok else None


def refresh_access_token(refresh_token):
    """
    Use a refresh token to get a new access token silently.
    Call this when an API call fails with a 401 so the user
    does not have to log in again.
    Returns the new token response dict or None on failure.
    """
    response = requests.post(f"{TWITCH_AUTH_BASE}/token", data={
        "client_id":     current_app.config["TWITCH_CLIENT_ID"],
        "client_secret": current_app.config["TWITCH_CLIENT_SECRET"],
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    })
    return response.json() if response.ok else None


# =============================================================
# User and channel
# =============================================================

def get_user(access_token):
    """
    Fetch the authenticated user's Twitch profile.
    Called after OAuth to get their ID, login name and avatar.

    Returns a dict with:
      id                — Twitch's own user ID (store this, not the login)
      login             — lowercase username e.g. "andycaladine"
      display_name      — display name e.g. "AndyCaladine"
      profile_image_url — avatar URL
      email             — only present if user:read:email scope granted
    """
    response = requests.get(
        f"{TWITCH_API_BASE}/users",
        headers=_auth_headers(access_token)
    )
    if response.ok:
        data = response.json().get("data", [])
        return data[0] if data else None
    return None


def get_stream(broadcaster_id, access_token):
    """
    Fetch live stream info for a channel.
    Returns None if the channel is currently offline.

    Returns a dict with:
      viewer_count — current viewers
      title        — stream title
      game_name    — category
      started_at   — ISO datetime the stream started
    """
    response = requests.get(
        f"{TWITCH_API_BASE}/streams",
        params={"user_id": broadcaster_id},
        headers=_auth_headers(access_token)
    )
    if response.ok:
        data = response.json().get("data", [])
        return data[0] if data else None
    return None


def get_channel(broadcaster_id, access_token):
    """
    Fetch channel info — title, game, language etc.
    Works even when the channel is offline, unlike get_stream().

    Returns a dict with:
      title                — current stream title
      game_name            — current category
      broadcaster_language — language set on the channel
    """
    response = requests.get(
        f"{TWITCH_API_BASE}/channels",
        params={"broadcaster_id": broadcaster_id},
        headers=_auth_headers(access_token)
    )
    if response.ok:
        data = response.json().get("data", [])
        return data[0] if data else None
    return None


def get_follower_count(broadcaster_id, access_token):
    """
    Fetch the total follower count for a channel.
    Returns an integer or None on failure.

    Note: individual follower data requires moderator scope.
    This endpoint returns the total count only.
    """
    response = requests.get(
        f"{TWITCH_API_BASE}/channels/followers",
        params={"broadcaster_id": broadcaster_id},
        headers=_auth_headers(access_token)
    )
    return response.json().get("total") if response.ok else None


def get_goals(broadcaster_id, access_token):
    """
    Fetch active creator goals set in the Twitch dashboard.
    e.g. follower goal, subscriber goal.
    Returns a list of goal dicts — usually 0 or 1 active at a time.
    """
    response = requests.get(
        f"{TWITCH_API_BASE}/goals",
        params={"broadcaster_id": broadcaster_id},
        headers=_auth_headers(access_token)
    )
    return response.json().get("data", []) if response.ok else []


def get_subscribers(broadcaster_id, access_token):
    """
    Fetch the total subscriber count for a channel.
    Requires channel:read:subscriptions scope.
    Returns an integer or None on failure.
    """
    response = requests.get(
        f"{TWITCH_API_BASE}/subscriptions",
        params={"broadcaster_id": broadcaster_id},
        headers=_auth_headers(access_token)
    )
    return response.json().get("total") if response.ok else None

def get_badge_urls(access_token: str, broadcaster_id: str) -> dict:
    """
    Fetch global and channel-specific Twitch badge image URLs.
    Returns a dict keyed by badge set name, value is the image URL
    for the first version (version "1" or "0").
    e.g. { "broadcaster": "https://...", "moderator": "https://...", ... }
    """
    import os
    client_id = os.environ.get("TWITCH_CLIENT_ID", "")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id,
    }
    badge_map = {}

    # Global badges
    try:
        r = requests.get(
            "https://api.twitch.tv/helix/chat/badges/global",
            headers=headers, timeout=5
        )
        if r.ok:
            for item in r.json().get("data", []):
                versions = item.get("versions", [])
                if versions:
                    badge_map[item["set_id"]] = versions[0]["image_url_1x"]
    except Exception as e:
        logger.warning(f"[Twitch] Could not fetch global badges: {e}")

    # Channel badges (override globals where applicable)
    try:
        r = requests.get(
            f"https://api.twitch.tv/helix/chat/badges?broadcaster_id={broadcaster_id}",
            headers=headers, timeout=5
        )
        if r.ok:
            for item in r.json().get("data", []):
                versions = item.get("versions", [])
                if versions:
                    badge_map[item["set_id"]] = versions[0]["image_url_1x"]
    except Exception as e:
        logger.warning(f"[Twitch] Could not fetch channel badges: {e}")

    return badge_map