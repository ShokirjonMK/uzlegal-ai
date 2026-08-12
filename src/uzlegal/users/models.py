"""Foydalanuvchi va foydalanish modellari."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime

from pydantic import BaseModel

from uzlegal.users.plans import PlanTier

API_KEY_PREFIX = "uzl_"
_HMAC_KEY = b"uzlegal-api-key-derivation"


class User(BaseModel):
    user_id: str
    telegram_id: str | None = None
    name: str = ""
    plan: PlanTier = PlanTier.BEPUL
    api_key_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
    is_active: bool = True


class UsageRecord(BaseModel):
    user_id: str
    date: str
    endpoint: str
    count: int = 0


class UsageSummary(BaseModel):
    user_id: str
    plan: PlanTier
    today_used: int = 0
    today_limit: int = 0
    month_used: int = 0
    month_limit: int = 0
    remaining_today: int = 0
    remaining_month: int = 0


class QuotaExceededError(Exception):
    def __init__(self, period: str, used: int, limit: int) -> None:
        self.period = period
        self.used = used
        self.limit = limit
        super().__init__(f"{period.capitalize()} chegarasiga yetildi: {used}/{limit}")


class UserNotFoundError(Exception):
    pass


class DuplicateUserError(Exception):
    pass


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hmac.new(_HMAC_KEY, key.encode(), hashlib.sha256).hexdigest()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def month_str() -> str:
    return datetime.now().strftime("%Y-%m")
