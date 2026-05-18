import sqlite3
import psycopg2
import psycopg2.extras
from flask import g, current_app


def get_db_connection():
    if "db" not in g:
        database_url = current_app.config["DATABASE_URL"]
        
        if database_url.startswith("postgres"):
            conn = psycopg2.connect(
                database_url,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            conn.autocommit = False
            g.db = _PostgresConnectionWrapper(conn)
            g.db_type = "postgres"
        else:
            conn = sqlite3.connect(
                database_url,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
            g.db_type = "sqlite"
    
    return g.db


class _PostgresConnectionWrapper:
    """
    Wraps a psycopg2 connection to behave like SQLite's connection.
    Allows conn.execute() and conn.commit() to work the same way.
    """
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cursor = self._conn.cursor()
        cursor.execute(sql, params or ())
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_db_type():
    return g.get("db_type", "sqlite")


def placeholder():
    return "%s" if get_db_type() == "postgres" else "?"


def close_db(error=None):
    database_connection = g.pop("db", None)
    if database_connection is not None:
        database_connection.close()