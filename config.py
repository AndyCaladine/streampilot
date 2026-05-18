import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    # SECRET_KEY signs session cookies — keep this secret in production
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    # Database
    # SQLite in development — file lives in instance/ (gitignored)
    # Set DATABASE_URL to a PostgreSQL string for production
    DATABASE_URL = os.environ.get("DATABASE_URL") or os.path.join(
        os.path.dirname(__file__), "instance", "database.db"
    )

    # Twitch OAuth
    # Create an app at https://dev.twitch.tv/console
    TWITCH_CLIENT_ID     = os.environ.get("TWITCH_CLIENT_ID", "")
    TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")
    TWITCH_REDIRECT_URI  = os.environ.get(
        "TWITCH_REDIRECT_URI",
        "http://localhost:5000/auth/callback"
    )

    # File uploads (panel images etc.) — not needed until Phase 4
    UPLOAD_FOLDER      = os.environ.get("UPLOAD_FOLDER", "static/uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB limit

    # Admin portal IP whitelist
    # Comma-separated list of allowed IPs — add VPN tunnel IP here for production
    ADMIN_ALLOWED_IPS = os.environ.get("ADMIN_ALLOWED_IPS", "127.0.0.1")