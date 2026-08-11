"""Obuna rejalari — cheklovlar va imkoniyatlar.

Har bir reja qat'iy belgilangan: kunlik/oylik soʻrov chegarasi,
ruxsat etilgan endpointlar, va batchga ruxsat. Reja oʻzgartirish
faqat admin yoki toʻlov tizimi orqali amalga oshiriladi.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PlanTier(StrEnum):
    BEPUL = "bepul"
    ASOSIY = "asosiy"
    PROFESSIONAL = "professional"
    TASHKILOT = "tashkilot"


class FeatureSet(BaseModel):
    consult: bool = True
    court_analyze: bool = True
    litigation: bool = False
    integrity: bool = False
    education: bool = False
    batch_api: bool = False
    stream: bool = False


class PlanLimits(BaseModel):
    daily_queries: int = 5
    monthly_queries: int = 100
    max_batch_size: int = 1


class Plan(BaseModel):
    tier: PlanTier
    name_uz: str
    limits: PlanLimits
    features: FeatureSet
    price_uzs: int = Field(default=0, description="Narx (soʻm/oy)")


PLANS: dict[PlanTier, Plan] = {
    PlanTier.BEPUL: Plan(
        tier=PlanTier.BEPUL,
        name_uz="Bepul",
        limits=PlanLimits(daily_queries=5, monthly_queries=100, max_batch_size=1),
        features=FeatureSet(
            consult=True,
            court_analyze=True,
        ),
        price_uzs=0,
    ),
    PlanTier.ASOSIY: Plan(
        tier=PlanTier.ASOSIY,
        name_uz="Asosiy",
        limits=PlanLimits(daily_queries=50, monthly_queries=1_000, max_batch_size=5),
        features=FeatureSet(
            consult=True,
            court_analyze=True,
            litigation=True,
            education=True,
            stream=True,
        ),
        price_uzs=99_000,
    ),
    PlanTier.PROFESSIONAL: Plan(
        tier=PlanTier.PROFESSIONAL,
        name_uz="Professional",
        limits=PlanLimits(daily_queries=200, monthly_queries=5_000, max_batch_size=20),
        features=FeatureSet(
            consult=True,
            court_analyze=True,
            litigation=True,
            integrity=True,
            education=True,
            batch_api=True,
            stream=True,
        ),
        price_uzs=299_000,
    ),
    PlanTier.TASHKILOT: Plan(
        tier=PlanTier.TASHKILOT,
        name_uz="Tashkilot",
        limits=PlanLimits(daily_queries=1_000, monthly_queries=20_000, max_batch_size=100),
        features=FeatureSet(
            consult=True,
            court_analyze=True,
            litigation=True,
            integrity=True,
            education=True,
            batch_api=True,
            stream=True,
        ),
        price_uzs=999_000,
    ),
}


def get_plan(tier: PlanTier) -> Plan:
    return PLANS[tier]


def has_feature(tier: PlanTier, feature: str) -> bool:
    plan = PLANS[tier]
    return getattr(plan.features, feature, False)
