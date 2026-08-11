"""Foydalanuvchi tizimi — obuna, cheklov, foydalanish hisobi.

    user, key = store.create_user("u1", plan=PlanTier.ASOSIY)
    check_access(store, "u1", "consult")      # OK yoki exception
    record_and_check(store, "u1", "consult")  # tekshir + qayd et
    summary = store.usage_summary("u1")       # kunlik/oylik statistika

SQLite-backed, deterministik, model chaqirilmaydi.
"""

from uzlegal.users.limits import FeatureNotAllowedError, check_access, record_and_check
from uzlegal.users.models import (
    DuplicateUserError,
    QuotaExceededError,
    UsageSummary,
    User,
    UserNotFoundError,
)
from uzlegal.users.plans import PLANS, Plan, PlanTier, get_plan, has_feature
from uzlegal.users.store import UserStore

__all__ = [
    "PLANS",
    "DuplicateUserError",
    "FeatureNotAllowedError",
    "Plan",
    "PlanTier",
    "QuotaExceededError",
    "UsageSummary",
    "User",
    "UserNotFoundError",
    "UserStore",
    "check_access",
    "get_plan",
    "has_feature",
    "record_and_check",
]
