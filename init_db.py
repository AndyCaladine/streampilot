import sqlite3
import os

DB_PATH     = os.path.join("instance", "database.db")
SCHEMA_PATH = "schema.sql"


def init_db():
    os.makedirs("instance", exist_ok=True)

    print(f"Initialising database at {DB_PATH}...")

    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())

    print("Done. All tables created.")
    print()
    print("Next steps:")
    print("  1. Add your Twitch app credentials to .env")
    print("  2. Run: python app.py")
    print("  3. Open http://localhost:5000")


if __name__ == "__main__":
    init_db()