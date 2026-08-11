"""SQLite-backed foydalanuvchi ombori.

Nima uchun SQLite:
- stdlib, yangi bogʻliqlik yoʻq
- Bitta fayl — zaxira nusxa oson
- WAL rejimi — bir vaqtda oʻqish/yozish
- Tranzaksion — yarim yozilgan holat boʻlmaydi
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from uzlegal.users.models import (
    DuplicateUserError,
    UsageSummary,
    User,
    UserNotFoundError,
    generate_api_key,
    hash_api_key,
    month_str,
    now_iso,
    today_str,
)
from uzlegal.users.plans import PLANS, PlanTier

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    telegram_id TEXT UNIQUE,
    name TEXT DEFAULT '',
    plan TEXT DEFAULT 'bepul',
    api_key_hash TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS usage (
    user_id TEXT NOT NULL,
    date TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date, endpoint),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_usage_date ON usage(date);
CREATE INDEX IF NOT EXISTS idx_usage_user ON usage(user_id, date);
"""


class UserStore:
    """Foydalanuvchilar va foydalanish SQLite ombori."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ── CRUD ────────────────────────────────────────────────────────────

    def create_user(
        self,
        user_id: str,
        *,
        telegram_id: str | None = None,
        name: str = "",
        plan: PlanTier = PlanTier.BEPUL,
    ) -> tuple[User, str]:
        """Yangi foydalanuvchi yaratadi. (User, api_key) qaytaradi."""
        api_key = generate_api_key()
        key_hash = hash_api_key(api_key)
        ts = now_iso()

        try:
            self._conn.execute(
                """INSERT INTO users
                   (user_id, telegram_id, name, plan, api_key_hash, created_at, updated_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (user_id, telegram_id, name, plan.value, key_hash, ts, ts),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError(f"Foydalanuvchi mavjud: {user_id}") from exc

        user = User(
            user_id=user_id,
            telegram_id=telegram_id,
            name=name,
            plan=plan,
            api_key_hash=key_hash,
            created_at=ts,
            updated_at=ts,
        )
        return user, api_key

    def get_user(self, user_id: str) -> User:
        row = self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise UserNotFoundError(user_id)
        return _row_to_user(row)

    def get_by_telegram(self, telegram_id: str) -> User:
        row = self._conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if row is None:
            raise UserNotFoundError(f"telegram:{telegram_id}")
        return _row_to_user(row)

    def get_by_api_key(self, api_key: str) -> User:
        key_hash = hash_api_key(api_key)
        row = self._conn.execute(
            "SELECT * FROM users WHERE api_key_hash = ? AND is_active = 1",
            (key_hash,),
        ).fetchone()
        if row is None:
            raise UserNotFoundError("API kaliti notoʻgʻri")
        return _row_to_user(row)

    def update_plan(self, user_id: str, plan: PlanTier) -> User:
        ts = now_iso()
        cursor = self._conn.execute(
            "UPDATE users SET plan = ?, updated_at = ? WHERE user_id = ?",
            (plan.value, ts, user_id),
        )
        self._conn.commit()
        if cursor.rowcount == 0:
            raise UserNotFoundError(user_id)
        return self.get_user(user_id)

    def deactivate(self, user_id: str) -> None:
        ts = now_iso()
        cursor = self._conn.execute(
            "UPDATE users SET is_active = 0, updated_at = ? WHERE user_id = ?",
            (ts, user_id),
        )
        self._conn.commit()
        if cursor.rowcount == 0:
            raise UserNotFoundError(user_id)

    def regenerate_key(self, user_id: str) -> str:
        api_key = generate_api_key()
        key_hash = hash_api_key(api_key)
        ts = now_iso()
        cursor = self._conn.execute(
            "UPDATE users SET api_key_hash = ?, updated_at = ? WHERE user_id = ?",
            (key_hash, ts, user_id),
        )
        self._conn.commit()
        if cursor.rowcount == 0:
            raise UserNotFoundError(user_id)
        return api_key

    def list_users(self, *, active_only: bool = True) -> list[User]:
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at"
        rows = self._conn.execute(query).fetchall()
        return [_row_to_user(r) for r in rows]

    # ── Usage ───────────────────────────────────────────────────────────

    def record_usage(self, user_id: str, endpoint: str) -> None:
        date = today_str()
        self._conn.execute(
            """INSERT INTO usage (user_id, date, endpoint, count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(user_id, date, endpoint)
               DO UPDATE SET count = count + 1""",
            (user_id, date, endpoint),
        )
        self._conn.commit()

    def daily_usage(self, user_id: str, date: str | None = None) -> int:
        date = date or today_str()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM usage WHERE user_id = ? AND date = ?",
            (user_id, date),
        ).fetchone()
        return int(row["total"])

    def monthly_usage(self, user_id: str, month: str | None = None) -> int:
        month = month or month_str()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM usage WHERE user_id = ? AND date LIKE ?",
            (user_id, f"{month}%"),
        ).fetchone()
        return int(row["total"])

    def usage_summary(self, user_id: str) -> UsageSummary:
        user = self.get_user(user_id)
        plan = PLANS[user.plan]
        daily = self.daily_usage(user_id)
        monthly = self.monthly_usage(user_id)

        return UsageSummary(
            user_id=user_id,
            plan=user.plan,
            today_used=daily,
            today_limit=plan.limits.daily_queries,
            month_used=monthly,
            month_limit=plan.limits.monthly_queries,
            remaining_today=max(0, plan.limits.daily_queries - daily),
            remaining_month=max(0, plan.limits.monthly_queries - monthly),
        )


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        user_id=row["user_id"],
        telegram_id=row["telegram_id"],
        name=row["name"],
        plan=PlanTier(row["plan"]),
        api_key_hash=row["api_key_hash"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_active=bool(row["is_active"]),
    )
