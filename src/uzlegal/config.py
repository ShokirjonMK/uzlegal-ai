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


class Settings(BaseModel):
    profile: str = "local-dev"
    catalog_path: Path = CONFIGS_DIR / "models.yaml"
    state_path: Path = DATA_DIR / "runtime-state.json"
    models_dir: Path = MODELS_DIR

    api_host: str = "127.0.0.1"
    api_port: int = 8080
    log_level: str = "INFO"

    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, profile: str | None = None) -> Settings:
        profile = profile or os.getenv("UZLEGAL_PROFILE", "local-dev")
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
            log_level=os.getenv("UZLEGAL_LOG_LEVEL", obs.get("log_level", "INFO")),
            raw=raw,
        )


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
