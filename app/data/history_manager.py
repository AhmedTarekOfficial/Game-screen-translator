"""
history_manager.py
------------------
Manages the SQLite database for storing translation history.
DB file: history.db (auto-created in project root on first run).
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).resolve().parents[2] / "history.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT    NOT NULL,
    translated_text TEXT    NOT NULL,
    source_detected TEXT,
    target_language TEXT,
    llm_used        TEXT,
    ocr_engine      TEXT,
    confidence      REAL,
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class HistoryManager:
    """
    Thread-safe SQLite history manager.
    Each public method opens and closes its own connection
    (SQLite connections are not thread-safe; use check_same_thread=False
    plus a threading.Lock for safety).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_path = DB_PATH
        return cls._instance

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """Create the history table if it doesn't already exist."""
        with self._connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_entry(
        self,
        original_text: str,
        translated_text: str,
        source_detected: str = "",
        target_language: str = "",
        llm_used: str = "",
        ocr_engine: str = "",
        confidence: float = 0.0,
    ) -> int:
        """
        Insert a new translation record.
        Returns the new row id.
        """
        sql = """
            INSERT INTO history
                (original_text, translated_text, source_detected,
                 target_language, llm_used, ocr_engine, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            cursor = conn.execute(
                sql,
                (
                    original_text,
                    translated_text,
                    source_detected,
                    target_language,
                    llm_used,
                    ocr_engine,
                    confidence,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_all(self, limit: int = 200) -> list[dict]:
        """
        Fetch the most recent `limit` entries, newest first.
        Returns a list of dicts.
        """
        sql = """
            SELECT id, original_text, translated_text, source_detected,
                   target_language, llm_used, ocr_engine, confidence, timestamp
            FROM history
            ORDER BY id DESC
            LIMIT ?
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 100) -> list[dict]:
        """
        Full-text search on original_text and translated_text.
        Returns a list of matching dicts.
        """
        pattern = f"%{query}%"
        sql = """
            SELECT id, original_text, translated_text, source_detected,
                   target_language, llm_used, ocr_engine, confidence, timestamp
            FROM history
            WHERE original_text LIKE ? OR translated_text LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (pattern, pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    def delete_entry(self, entry_id: int) -> None:
        """Remove a single record by its id."""
        with self._connect() as conn:
            conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()

    def clear_all(self) -> None:
        """Delete every record from history (dangerous — use with care)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM history")
            conn.commit()

    def get_count(self) -> int:
        """Return the total number of history entries."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM history").fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self, output_path: str) -> int:
        """
        Export all history to a CSV file at `output_path`.
        Returns the number of rows written.
        """
        rows = self.get_all(limit=100_000)
        if not rows:
            return 0
        fieldnames = list(rows[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path), check_same_thread=False)
