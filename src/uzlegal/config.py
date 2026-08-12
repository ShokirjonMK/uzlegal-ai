"""Konfiguratsiya va global reestr.

Ustunlik tartibi (docs/12-repo-structure.md § 4):
    kod standartlari < profil YAML < configs/local.yaml < env < CLI argumentlari
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"


class TelegramSettings(BaseModel):
    """Telegram bot sozlamalari.

    Token **faqat muhit o'zgaruvchisidan** o'qiladi — hech qachon
    `configs/*.yaml` dan. Sabab: YAML fayllari repoga tushadi, token esa
    oshkor bo'lsa bot nomidan xabar yuborish imkonini beradi
    (docs/10-security-compliance.md § 4).

    `.env.example` ga qarang.
    """

    bot_token: str | None = Field(default=None, repr=False)
    chat_id: str | None = None
    allowed_chats: list[str] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def allows(self, chat_id: str) -> bool:
        """Bot shu chatga javob beradimi. Ro'yxat bo'sh bo'lsa — hammasiga."""
        return not self.allowed_chats or str(chat_id) in self.allowed_chats

    @classmethod
    def from_env(cls) -> TelegramSettings:
        allowed = os.getenv("UZLEGAL_TELEGRAM_ALLOWED_CHATS", "")
        return cls(
            bot_token=os.getenv("UZLEGAL_TELEGRAM_BOT_TOKEN") or None,
            chat_id=os.getenv("UZLEGAL_TELEGRAM_CHAT_ID") or None,
            allowed_chats=[c.strip() for c in allowed.split(",") if c.strip()],
        )


class Settings(BaseModel):
    profile: str = "local-dev"
    catalog_path: Path = CONFIGS_DIR / "models.yaml"
    state_path: Path = DATA_DIR / "runtime-state.json"
    models_dir: Path = MODELS_DIR

    api_host: str = "127.0.0.1"
    api_port: int = 8080
    log_level: str = "INFO"

    # Profil fayllari (`configs/profiles/*.yaml`) bu siyosatni ALLAQACHON
    # e'lon qilgan edi — `local-dev: auth: none`, `server: auth: api_key`
    # va rate-limit qiymatlari bilan. Lekin kod ularni hech qachon
    # o'qimasdi, ya'ni `server` profilida ham API butunlay ochiq edi.
    api_auth: str = "none"
    cors_origins: list[str] = Field(default_factory=list)
    rate_limit: dict[str, Any] = Field(default_factory=dict)

    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, profile: str | None = None) -> Settings:
        profile = profile or os.getenv("UZLEGAL_PROFILE") or "local-dev"
        _load_dotenv()
        raw: dict[str, Any] = {}

        profile_file = CONFIGS_DIR / "profiles" / f"{profile}.yaml"
        if profile_file.exists():
            raw = yaml.safe_load(profile_file.read_text(encoding="utf-8")) or {}

        local_file = CONFIGS_DIR / "local.yaml"
        if local_file.exists():
            raw = _deep_merge(raw, yaml.safe_load(local_file.read_text(encoding="utf-8")) or {})

        api = raw.get("api") or {}
        obs = raw.get("observability") or {}

        return cls(
            profile=profile,
            api_host=os.getenv("UZLEGAL_API_HOST", api.get("host", "127.0.0.1")),
            api_port=int(os.getenv("UZLEGAL_API_PORT", api.get("port", 8080))),
            api_auth=os.getenv("UZLEGAL_API_AUTH", str(api.get("auth", "none"))),
            cors_origins=list(api.get("cors_origins") or []),
            rate_limit=dict(api.get("rate_limit") or {}),
            log_level=os.getenv("UZLEGAL_LOG_LEVEL", obs.get("log_level", "INFO")),
            telegram=TelegramSettings.from_env(),
            raw=raw,
        )


def _load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """`.env` faylini o'qiydi (tashqi bog'liqliksiz).

    Allaqachon o'rnatilgan muhit o'zgaruvchilari **ustun** — CI va
    ishlab chiqarishda ular fayldan emas, tashqaridan keladi.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()


@functools.lru_cache(maxsize=1)
def get_registry():  # type: ignore[no-untyped-def]
    """Global model reestri — butun jarayonda bitta nusxa.

    Modelni faqat shu reestr yuklaydi va bo'shatadi, shuning uchun UI, CLI va
    API dan qilingan almashtirish hamma joyda darhol ko'rinadi.
    """
    from uzlegal.inference.registry import ModelRegistry

    settings = get_settings()
    return ModelRegistry(catalog_path=settings.catalog_path, state_path=settings.state_path)
