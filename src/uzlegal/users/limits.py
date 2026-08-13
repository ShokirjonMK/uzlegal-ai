"""Cheklovlar tekshiruvi — soʻrov chegarasi va ruxsat.

Har bir API chaqiruv uchun ikkita tekshiruv:
1. Foydalanuvchi ushbu endpointga ruxsati bormi (plan.features)
2. Kunlik/oylik soʻrov chegarasiga yetilmaganmi
"""

from __future__ import annotations

from uzlegal.users.models import QuotaExceededError
from uzlegal.users.plans import PLANS, PlanTier, billing, has_feature
from uzlegal.users.store import UserStore

ENDPOINT_TO_FEATURE: dict[str, str] = {
    "consult": "consult",
    "consult_stream": "stream",
    "court_analyze": "court_analyze",
    "litigation_advise": "litigation",
    "litigation_questions": "litigation",
    "integrity_check": "integrity",
    "integrity_profile": "integrity",
    "education": "education",
}


class FeatureNotAllowedError(Exception):
    def __init__(self, feature: str, plan: PlanTier) -> None:
        self.feature = feature
        self.plan = plan
        super().__init__(f"«{feature}» — «{plan.value}» rejasida mavjud emas")


def check_access(
    store: UserStore,
    user_id: str,
    endpoint: str,
) -> None:
    """Ruxsat va chegarani tekshiradi. Xatolik boʻlsa exception otadi.

    Bepul davrda (`billing.enabled: false`) chegaralar **umuman
    qoʻllanmaydi**. Foydalanish baribir qayd etiladi — u statistika va
    kelajakdagi narx qarori uchun kerak, lekin hech kim toʻxtatilmaydi.
    """
    user = store.get_user(user_id)

    if not billing().enabled:
        return

    plan = PLANS[user.plan]

    feature = ENDPOINT_TO_FEATURE.get(endpoint, "")
    if feature and not has_feature(user.plan, feature):
        raise FeatureNotAllowedError(feature, user.plan)

    daily = store.daily_usage(user_id)
    if daily >= plan.limits.daily_queries:
        raise QuotaExceededError("kunlik", daily, plan.limits.daily_queries)

    monthly = store.monthly_usage(user_id)
    if monthly >= plan.limits.monthly_queries:
        raise QuotaExceededError("oylik", monthly, plan.limits.monthly_queries)


def record_and_check(
    store: UserStore,
    user_id: str,
    endpoint: str,
) -> None:
    """Tekshiradi va foydalanishni qayd etadi — bitta chaqiruvda."""
    check_access(store, user_id, endpoint)
    store.record_usage(user_id, endpoint)
