"""Obuna rejalari — cheklovlar va imkoniyatlar.

Har bir reja: kunlik/oylik soʻrov chegarasi, ruxsat etilgan
imkoniyatlar va batch hajmi.

## Rejalar KODDA emas, KONFIGURATSIYADA

Quyidagi `_DEFAULT_PLANS` — faqat **zaxira qiymat**. Amaldagi rejalar
`configs/plans.yaml` dan oʻqiladi va ular xizmatni toʻxtatmasdan
oʻzgartiriladi:

    uzlegal plans show                    # joriy holat
    POST /v1/admin/plans/reload           # YAML ni qayta oʻqish

Sabab: narx va chegara — **biznes qarori**, kod qarori emas. Ularni
oʻzgartirish uchun релиз chiqarish talab qilinishi notoʻgʻri.

## Bepul davr

`billing.enabled: false` boʻlsa chegaralar **umuman qoʻllanmaydi** —
hamma narsa bepul. Bu ishga tushirishning birinchi bosqichi uchun:
foydalanuvchi jalb qilinadi, keyin toʻlov yoqiladi.

Rejalar tuzilmasi oʻsha-oʻsha qoladi, yaʼni toʻlovni yoqish uchun
bitta bayroqni oʻzgartirish yetarli — kod oʻzgarmaydi.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


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


_DEFAULT_PLANS: dict[PlanTier, Plan] = {
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


# --------------------------------------------------------------------------- #
# Konfiguratsiyadan oʻqish
# --------------------------------------------------------------------------- #

CONFIG_PATH = Path("configs/plans.yaml")


class Billing(BaseModel):
    """Toʻlov holati.

    `enabled: false` — bepul davr: chegaralar qoʻllanmaydi.
    """

    enabled: bool = False
    note: str = "Bepul davr — chegaralar qoʻllanmaydi"


_plans: dict[PlanTier, Plan] = dict(_DEFAULT_PLANS)
_billing = Billing()
_loaded = False


def _load() -> None:
    """`configs/plans.yaml` ni oʻqiydi. Xato boʻlsa zaxira qiymat qoladi.

    Buzuq YAML xizmatni toʻxtatmasligi kerak: rejalar yordamchi
    mexanizm, ularning sozlamasi savol-javobni yiqitmasin. Lekin xato
    jimgina oʻtmaydi — u log ga yoziladi.
    """
    global _plans, _billing, _loaded
    _loaded = True

    if not CONFIG_PATH.exists():
        PLANS.clear()
        PLANS.update(_DEFAULT_PLANS)
        return

    try:
        raw: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        log.warning("plans.yaml oʻqilmadi (%s) — standart rejalar qoladi", exc)
        PLANS.clear()
        PLANS.update(_DEFAULT_PLANS)
        return

    _billing = Billing(**(raw.get("billing") or {}))

    parsed: dict[PlanTier, Plan] = {}
    for name, body in (raw.get("plans") or {}).items():
        try:
            tier = PlanTier(name)
            parsed[tier] = _merge(_DEFAULT_PLANS[tier], dict(body or {}))
        except Exception as exc:
            log.warning("Reja '%s' yozuvi notoʻgʻri: %s", name, exc)

    # Qisman yuklash xavfli: bitta reja yozuvida xato boʻlsa, uning
    # foydalanuvchilari chegarasiz qolardi. Shuning uchun yetishmagan
    # rejalar standartdan toʻldiriladi.
    _plans = {**_DEFAULT_PLANS, **parsed}
    PLANS.clear()
    PLANS.update(_plans)


def _merge(base: Plan, override: dict[str, Any]) -> Plan:
    """YAML yozuvini standart reja USTIGA qoʻyadi.

    NEGA ALMASHTIRISH EMAS, USTIGA QOʻYISH. Admin faqat narxni
    oʻzgartirmoqchi boʻlsa, butun `features` blokini qayta yozishga
    majbur boʻlmasligi kerak. Birinchi urinishda `Plan(**body)` ishlatilgan
    edi va `features` yozilmagan yozuv validatsiyadan oʻtmasdi — natijada
    reja JIMGINA standartga qaytardi va buni faqat log koʻrsatardi.
    Konfiguratsiya faylida bu eng yomon xatti-harakat: admin qiymatni
    oʻzgartirdim deb oʻylaydi, tizim esa eskisini ishlatadi.

    Ichki bloklar (`limits`, `features`) ham xuddi shunday birlashtiriladi:
    `daily_queries` ni oʻzgartirish uchun `monthly_queries` ni qayta
    yozish shart emas.
    """
    data = base.model_dump()
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    data["tier"] = base.tier
    return Plan(**data)


def reload_plans() -> dict[str, Any]:
    """YAML ni qayta oʻqiydi — xizmatni toʻxtatmasdan."""
    _load()
    return {"plans": len(_plans), "billing_enabled": _billing.enabled}


def all_plans() -> dict[PlanTier, Plan]:
    if not _loaded:
        _load()
    return _plans


def billing() -> Billing:
    if not _loaded:
        _load()
    return _billing


def get_plan(tier: PlanTier) -> Plan:
    return all_plans()[tier]


def has_feature(tier: PlanTier, feature: str) -> bool:
    """Bepul davrda barcha imkoniyatlar ochiq."""
    if not billing().enabled:
        return True
    return getattr(all_plans()[tier].features, feature, False)


# `PLANS` — oddiy lugʻat va u JOYIDA yangilanadi (`clear` + `update`).
#
# NEGA PROKSI EMAS. Birinchi urinishda `dict` merosxoʻri yozilgan edi:
# u `__getitem__` va `values()` ni qayta aniqlardi, lekin ostidagi
# lugʻat BOʻSH qolardi. Natijada `tier in PLANS` — `__contains__`
# qayta aniqlanmagani uchun — har doim `False` qaytarardi.
#
# Oʻzi haqida yolgʻon gapiradigan `dict` merosxoʻri — tuzoq: qaysi
# metod qayta aniqlangani esda qolmaydi va qolganlari jimgina notoʻgʻri
# ishlaydi. Joyida yangilanadigan haqiqiy lugʻat esa barcha metodlarda
# toʻgʻri ishlaydi va havola ham buzilmaydi.
PLANS: dict[PlanTier, Plan] = dict(_DEFAULT_PLANS)
