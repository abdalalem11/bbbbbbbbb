import sqlite3
from datetime import datetime, timezone

from config import DATA_DIR

DB = DATA_DIR / "factory.db"


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                bot_token TEXT,
                api_id INTEGER NOT NULL,
                api_hash TEXT NOT NULL,
                method TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'stopped'
            )
            """
        )
        db.commit()


def add_account(values):
    with connect() as db:
        db.execute(
            """
            INSERT INTO accounts
            (
                id, name, phone, bot_token, api_id, api_hash,
                method, created_at, expires_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        db.commit()


def get_account(account_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM accounts WHERE id=?",
            (account_id,),
        ).fetchone()


def all_accounts():
    with connect() as db:
        return db.execute(
            "SELECT * FROM accounts ORDER BY created_at DESC"
        ).fetchall()


def set_status(account_id, status):
    with connect() as db:
        db.execute(
            "UPDATE accounts SET status=? WHERE id=?",
            (status, account_id),
        )
        db.commit()


def delete_account(account_id):
    with connect() as db:
        db.execute(
            "DELETE FROM accounts WHERE id=?",
            (account_id,),
        )
        db.commit()


def expired_accounts():
    now = datetime.now(timezone.utc).isoformat()

    with connect() as db:
        return db.execute(
            """
            SELECT *
            FROM accounts
            WHERE expires_at <= ?
              AND status != 'expired'
            """,
            (now,),
        ).fetchall()
