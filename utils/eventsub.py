"""
utils/eventsub.py
Register and delete Twitch EventSub subscriptions.
Called after OAuth connect and on account disconnect.
"""

import requests
from flask import current_app


EVENTSUB_URL = "https://api.twitch.tv/helix/eventsub/subscriptions"

# Event types we subscribe to and their conditions
SUBSCRIPTION_TYPES = [
    {
        "type":    "channel.follow",
        "version": "2",
        "condition_key": "moderator_user_id",  # requires moderator_user_id as well
    },
    {
        "type":    "channel.subscribe",
        "version": "1",
        "condition_key": None,
    },
    {
        "type":    "channel.subscription.gift",
        "version": "1",
        "condition_key": None,
    },
    {
        "type":    "channel.subscription.message",
        "version": "1",
        "condition_key": None,
    },
    {
        "type":    "channel.cheer",
        "version": "1",
        "condition_key": None,
    },
    {
        "type":    "channel.raid",
        "version": "1",
        "condition_key": None,
    },
]


def get_app_token(client_id, client_secret):
    """Get an app access token for EventSub registration (not user token)."""
    res = requests.post("https://id.twitch.tv/oauth2/token", params={
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "client_credentials",
    })
    data = res.json()
    return data.get("access_token")


def register_subscriptions(broadcaster_id):
    """
    Register all EventSub subscriptions for a broadcaster.
    Uses app token — called after OAuth connect.
    """
    client_id     = current_app.config["TWITCH_CLIENT_ID"]
    client_secret = current_app.config["TWITCH_CLIENT_SECRET"]
    secret        = current_app.config["EVENTSUB_SECRET"]
    callback_url  = current_app.config["TWITCH_REDIRECT_URI"].replace(
        "/auth/callback", "/webhooks/twitch"
    )

    app_token = get_app_token(client_id, client_secret)
    if not app_token:
        current_app.logger.error("[EventSub] Could not get app token")
        return

    headers = {
        "Client-ID":     client_id,
        "Authorization": f"Bearer {app_token}",
        "Content-Type":  "application/json",
    }

    for sub in SUBSCRIPTION_TYPES:
        condition = {"broadcaster_user_id": broadcaster_id}

        # channel.follow v2 also requires moderator_user_id
        if sub["condition_key"] == "moderator_user_id":
            condition["moderator_user_id"] = broadcaster_id

        # channel.raid uses to_broadcaster_user_id
        if sub["type"] == "channel.raid":
            condition = {"to_broadcaster_user_id": broadcaster_id}

        payload = {
            "type":      sub["type"],
            "version":   sub["version"],
            "condition": condition,
            "transport": {
                "method":   "webhook",
                "callback": callback_url,
                "secret":   secret,
            },
        }

        res = requests.post(EVENTSUB_URL, json=payload, headers=headers)

        if res.status_code in (200, 202):
            current_app.logger.info(f"[EventSub] Subscribed: {sub['type']}")
        elif res.status_code == 409:
            current_app.logger.info(f"[EventSub] Already subscribed: {sub['type']}")
        else:
            current_app.logger.error(
                f"[EventSub] Failed {sub['type']}: {res.status_code} {res.text}"
            )


def delete_subscriptions(broadcaster_id):
    """
    Delete all EventSub subscriptions for a broadcaster.
    Called on account disconnect.
    """
    client_id     = current_app.config["TWITCH_CLIENT_ID"]
    client_secret = current_app.config["TWITCH_CLIENT_SECRET"]

    app_token = get_app_token(client_id, client_secret)
    if not app_token:
        return

    headers = {
        "Client-ID":     client_id,
        "Authorization": f"Bearer {app_token}",
    }

    # Fetch all subscriptions
    res  = requests.get(EVENTSUB_URL, headers=headers)
    subs = res.json().get("data", [])

    for sub in subs:
        condition = sub.get("condition", {})
        if condition.get("broadcaster_user_id") == broadcaster_id or \
           condition.get("to_broadcaster_user_id") == broadcaster_id:
            requests.delete(
                f"{EVENTSUB_URL}?id={sub['id']}",
                headers=headers
            )
            current_app.logger.info(f"[EventSub] Deleted: {sub['type']}")