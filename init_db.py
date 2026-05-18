import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.environ.get("DATABASE_URL") or os.path.join("instance", "database.db")
SCHEMA_PATH = "schema.sql"

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    print(f"Initialising database at {DB_PATH}...")
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
    print("Done. All tables created.")

    if os.environ.get("FLASK_ENV") == "production":
        print("Running in production — database ready.")
    else:
        print()
        print("Next steps:")
        print("  1. Add your Twitch app credentials to .env")
        print("  2. Run: python app.py")
        print("  3. Open http://localhost:5001")

if __name__ == "__main__":
    init_db()