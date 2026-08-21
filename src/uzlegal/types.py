"""Umumiy ma'lumot strukturalari.

Bu modul hech narsani import qilmaydi (eng past qatlam) — shuning uchun uni
istalgan joydan ishlatish mumkin va aylanma bog'liqlik yuzaga kelmaydi.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Model va backend
# --------------------------------------------------------------------------- #


class ModelStatus(StrEnum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    AVAILABLE = "available"
    LOADING = "loading"
    ACTIVE = "active"
    ERROR = "error"


class ModelSpec(BaseModel):
    """Model tavsifi — `configs/models.yaml` dagi bitta yozuv.

    Yangi model qo'shish = shu strukturada YAML yozuvi qo'shish. Kod o'zgarmaydi.
    """

    id: str = Field(description="Ichki identifikator, masalan 'qwen3-14b'")
    display_name: str
    backend: str = Field(description="Qaysi runtime: mlx · vllm · openai · echo")

    # Manba: HuggingFace ID yoki local yo'l yoki masofaviy endpoint
    hf_id: str | None = None
    local_path: str | None = None
    endpoint: str | None = None

    params: str | None = Field(default=None, description="Masalan '14B'")
    quant_bits: int | None = None
    quant_group_size: int | None = 64
    size_gb: float | None = None
    context_length: int = 8192
    license: str | None = None

    # Fikrlash rejimi (`thinking`) o'chirilsinmi.
    #
    # NEGA KERAK. Qwen3 va Qwen3.5 kabi modellar javobdan oldin uzun
    # ichki mulohaza yozadi. OpenAI ga mos API da u `reasoning` maydoniga
    # tushadi, `content` esa BO'SH qoladi — va butun token byudjeti
    # mulohazaga ketadi (`finish_reason: length`).
    #
    # O'lchandi (2026-08-21, qwen3.5): agent so'rovi 0 belgilik javob
    # qaytardi va uchala urinish ham yiqildi. `reasoning_effort: "none"`
    # bilan o'sha so'rov to'g'ri JSON qaytardi.
    #
    # Agentlarga tuzilgan chiqish kerak, mulohaza zanjiri emas — shuning
    # uchun fikrlash rejimi ular uchun foyda emas, to'siq.
    disable_thinking: bool = False

    # Faza 0 baholash uchun
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    note: str | None = None

    # Generatsiya standartlari
    default_temperature: float = 0.3
    default_max_tokens: int = 2000

    @property
    def source(self) -> str:
        return self.local_path or self.hf_id or self.endpoint or "(noma'lum)"


class AdapterSpec(BaseModel):
    """LoRA adapteri — rolga xos xatti-harakat qatlami (ADR-003)."""

    role: str
    version: str = "current"
    path: str
    base_model: str = Field(description="Qaysi baza model uchun o'qitilgan")
    rank: int = 16
    size_mb: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class GenerationParams(BaseModel):
    max_tokens: int = 2000
    temperature: float = 0.3
    top_p: float = 0.9
    stop: list[str] = Field(default_factory=list)
    seed: int | None = None
    prefix_cache: object | None = Field(default=None, exclude=True)

    system: str | None = Field(default=None, description="Tizim prompti (rol ko'rsatmasi)")
    raw: bool = Field(
        default=False,
        description="True — chat shabloni qo'llanmaydi (prompt tayyor formatda)",
    )
    thinking: bool = Field(
        default=False,
        description="Qwen3 'thinking' rejimi. Yuridik javobda odatda keraksiz uzunlik beradi.",
    )

    model_config = {"arbitrary_types_allowed": True}


class ModelInfo(BaseModel):
    """UI va API uchun model holati."""

    spec: ModelSpec
    status: ModelStatus
    is_active: bool = False
    downloaded_gb: float | None = None
    error: str | None = None
    fits_in_memory: bool = True
    memory_warning: str | None = None


# --------------------------------------------------------------------------- #
# Huquqiy domen (Faza 2+ da to'ldiriladi)
# --------------------------------------------------------------------------- #


class Citation(BaseModel):
    tag: str = Field(description="Kontekstdagi belgi, masalan 'C1'")
    doc_id: str
    doc_title: str | None = None
    doc_type: str | None = None
    article: str
    part: str | None = None
    version: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    status: Literal["in_force", "superseded", "repealed"] = "in_force"
    url: str | None = None
    excerpt: str | None = None


class DateCoverage(BaseModel):
    """`as_of` so'ralganda manbalarning sana qamrovi (docs/21 § 3).

    Korpusning to'rtdan uch qismida `valid_from` yo'q. Ya'ni «2019-yil
    holatiga ko'ra» degan so'rovni tizim ko'p manba uchun **tasdiqlay
    olmaydi**. Buni jimgina qilish — «buyruq muvaffaqiyat haqida xabar
    beradi, lekin ish bajarilmaydi» naqshi. Shuning uchun qamrov
    javobning o'zi bilan birga qaytariladi.
    """

    confirmed: int = Field(default=0, description="`valid_from` ma'lum bo'lgan manbalar")
    unknown: int = Field(default=0, description="Tahrir tarixi noma'lum manbalar")
    as_of: date

    @property
    def total(self) -> int:
        return self.confirmed + self.unknown


class Argument(BaseModel):
    claim: str
    citations: list[str] = Field(default_factory=list)
    strength: Literal["strong", "moderate", "weak"] = "moderate"


class Position(BaseModel):
    role: str
    stance: str
    arguments: list[Argument] = Field(default_factory=list)
    weaknesses: list[str] = Field(
        default_factory=list,
        description="O'z pozitsiyasining zaif tomonlari — rol qulflanishiga qarshi",
    )
    confidence: float = 0.5
