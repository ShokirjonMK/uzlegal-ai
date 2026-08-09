"""Katalogni qayta o'qish yuklab olingan modelni ko'rishi kerak.

Real xato: modelni terminalda yuklab olgandan keyin UI dagi «Katalogni qayta
o'qish» tugmasi uni hamon `not_downloaded` deb ko'rsatardi, chunki holat
faqat birinchi marta tekshirilardi.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from uzlegal.inference.registry import ModelRegistry
from uzlegal.types import ModelStatus


@pytest.fixture
def registry(tmp_path: Path) -> ModelRegistry:
    catalog = tmp_path / "models.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "keyin-yuklanadi": {
                        "display_name": "Keyin yuklanadi",
                        "backend": "echo",
                        "local_path": str(tmp_path / "modellar" / "test-model"),
                        "size_gb": 1.0,
                    },
                    "stub": {"display_name": "Stub", "backend": "echo"},
                }
            }
        ),
        encoding="utf-8",
    )
    return ModelRegistry(catalog, tmp_path / "state.json", total_memory_gb=24.0)


def _status(reg: ModelRegistry, model_id: str) -> ModelStatus:
    return next(m.status for m in reg.list_models() if m.spec.id == model_id)


def test_yuklab_olingandan_keyin_holat_yangilanadi(
    registry: ModelRegistry, tmp_path: Path
) -> None:
    assert _status(registry, "keyin-yuklanadi") is ModelStatus.NOT_DOWNLOADED

    # Yuklab olishni taqlid qilamiz
    (tmp_path / "modellar" / "test-model").mkdir(parents=True)

    registry.reload_catalog()

    assert _status(registry, "keyin-yuklanadi") is ModelStatus.AVAILABLE


def test_qayta_oqish_faol_model_holatini_buzmaydi(registry: ModelRegistry) -> None:
    registry.activate("stub")
    registry.reload_catalog()
    assert _status(registry, "stub") is ModelStatus.ACTIVE
    assert registry.active_id == "stub"


def test_ochirilgan_model_qayta_not_downloaded_boladi(
    registry: ModelRegistry, tmp_path: Path
) -> None:
    path = tmp_path / "modellar" / "test-model"
    path.mkdir(parents=True)
    registry.reload_catalog()
    assert _status(registry, "keyin-yuklanadi") is ModelStatus.AVAILABLE

    path.rmdir()
    registry.reload_catalog()
    assert _status(registry, "keyin-yuklanadi") is ModelStatus.NOT_DOWNLOADED
