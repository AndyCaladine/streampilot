import sqlite3
from flask import g, current_app


def get_db_connection():
    """
    Return the database connection for the current request.
    Stored on Flask's g object so we reuse one connection
    per request rather than opening a new one for every query.
    Columns can be accessed by name: row["display_name"]
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_URL"],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    """
    Close the database connection at the end of the request.
    Flask calls this automatically via teardown_appcontext
    which is registered in app.py.
    The error parameter is passed by Flask but we don't need it —
    we close the connection whether the request succeeded or failed.
    """
    database_connection = g.pop("db", None)
    if database_connection is not None:
        database_connection.close()