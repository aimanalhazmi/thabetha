"""SQLite database setup and schema management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "thabetha.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'individual',
    tax_id TEXT,
    commercial_registration TEXT,
    whatsapp_enabled INTEGER NOT NULL DEFAULT 1,
    ai_enabled INTEGER NOT NULL DEFAULT 0,
    trust_score INTEGER NOT NULL DEFAULT 50,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_profiles (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    shop_name TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qr_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS groups_ (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups_(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    UNIQUE (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS debts (
    id TEXT PRIMARY KEY,
    creditor_id TEXT NOT NULL REFERENCES users(id),
    debtor_id TEXT REFERENCES users(id),
    debtor_name TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    description TEXT NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_confirmation',
    invoice_url TEXT,
    notes TEXT,
    group_id TEXT REFERENCES groups_(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    paid_at TEXT
);

CREATE TABLE IF NOT EXISTS debt_events (
    id TEXT PRIMARY KEY,
    debt_id TEXT NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    actor_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_confirmations (
    id TEXT PRIMARY KEY,
    debt_id TEXT NOT NULL UNIQUE REFERENCES debts(id) ON DELETE CASCADE,
    debtor_id TEXT NOT NULL REFERENCES users(id),
    creditor_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    note TEXT,
    requested_at TEXT NOT NULL,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    debt_id TEXT NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    uploader_id TEXT NOT NULL REFERENCES users(id),
    attachment_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    content_type TEXT,
    storage_path TEXT NOT NULL,
    public_url TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    debt_id TEXT REFERENCES debts(id),
    read_at TEXT,
    whatsapp_attempted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merchant_notification_preferences (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    merchant_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    whatsapp_enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, merchant_id)
);

CREATE TABLE IF NOT EXISTS trust_score_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta INTEGER NOT NULL,
    score_after INTEGER NOT NULL,
    reason TEXT NOT NULL,
    debt_id TEXT REFERENCES debts(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_settlements (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups_(id) ON DELETE CASCADE,
    payer_id TEXT NOT NULL REFERENCES users(id),
    debtor_id TEXT NOT NULL REFERENCES users(id),
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_debts_creditor ON debts(creditor_id);
CREATE INDEX IF NOT EXISTS idx_debts_debtor ON debts(debtor_id);
CREATE INDEX IF NOT EXISTS idx_debts_status_due ON debts(status, due_date);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read_at);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id, status);
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create a SQLite connection with recommended settings."""
    path = str(db_path or _DEFAULT_DB_PATH)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Run schema migration."""
    conn.executescript(SCHEMA)
    conn.commit()
