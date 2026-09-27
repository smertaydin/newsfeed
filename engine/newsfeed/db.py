import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
    url TEXT PRIMARY KEY,
    category TEXT NOT NULL,        -- rss.json'daki kategori adı
    section TEXT NOT NULL,         -- eşlendiği bölüm (ipucu)
    active INTEGER NOT NULL DEFAULT 1,
    title TEXT,
    etag TEXT,
    last_modified TEXT,
    last_ok TEXT,
    last_error TEXT,
    fail_count INTEGER NOT NULL DEFAULT 0,
    item_count INTEGER NOT NULL DEFAULT 0,
    next_try TEXT
);
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL,
    domain TEXT NOT NULL,
    feed_url TEXT,
    section_hint TEXT,
    published TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    body TEXT,
    body_status TEXT,              -- NULL: denenmedi, ok, fail
    emb BLOB,
    story_id TEXT
);
CREATE INDEX IF NOT EXISTS articles_story ON articles(story_id);
CREATE INDEX IF NOT EXISTS articles_published ON articles(published);
CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, short, full, hidden
    section TEXT,
    importance INTEGER,
    mode TEXT,                                -- full | brief (kuruma özgü içerik)
    title TEXT,
    summary TEXT,
    points TEXT,
    facts TEXT,
    why TEXT,
    tags TEXT,
    timeline TEXT NOT NULL DEFAULT '[]',
    centroid BLOB,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,                 -- son kaynak eklenme zamanı
    written_at TEXT,
    written_n INTEGER NOT NULL DEFAULT 0      -- son yazımda kaç makale vardı
);
CREATE INDEX IF NOT EXISTS stories_updated ON stories(updated_at);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


class DB:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def q(self, sql, *args):
        return self.conn.execute(sql, args).fetchall()

    def one(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()

    def x(self, sql, *args):
        self.conn.execute(sql, args)

    def commit(self):
        self.conn.commit()

    def meta_get(self, key, default=None):
        row = self.one("SELECT value FROM meta WHERE key=?", key)
        return json.loads(row["value"]) if row else default

    def meta_set(self, key, value):
        self.x("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", key, json.dumps(value, ensure_ascii=False))
        self.commit()
