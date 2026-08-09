"""Model reestri va almashtirish mantiqi testlari.

Bu testlar `echo` backend bilan ishlaydi — GPU yoki yuklab olingan model
kerak emas, shuning uchun CI da ham o'tadi.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from uzlegal.inference.registry import ModelRegistry, ModelSwapError
from uzlegal.types import ModelStatus

CATALOG = {
    "models": {
        "echo-a": {"display_name": "Echo A", "backend": "echo", "size_gb": 0.0},
        "echo-b": {"display_name": "Echo B", "backend": "echo", "size_gb": 0.0},
        "kichik": {"display_name": "Kichik", "backend": "echo", "size_gb": 4.0},
        "ulkan": {"display_name": "Ulkan", "backend": "echo", "size_gb": 60.0},
        "yomon-backend": {"display_name": "Yomon", "backend": "yoq-bunday", "size_gb": 1.0},
    },
    "adapters": {},
}


@pytest.fixture
def registry(tmp_path: Path) -> ModelRegistry:
    catalog = tmp_path / "models.yaml"
    catalog.write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    return ModelRegistry(
        catalog_path=catalog,
        state_path=tmp_path / "state.json",
        total_memory_gb=24.0,
    )


# --------------------------------------------------------------------------- #
# Katalog
# --------------------------------------------------------------------------- #


def test_katalog_yuklanadi(registry: ModelRegistry) -> None:
    ids = {m.spec.id for m in registry.list_models()}
    assert ids == set(CATALOG["models"])


def test_yomon_yozuv_qolganini_buzmaydi(tmp_path: Path) -> None:
    """Bitta noto'g'ri YAML yozuvi butun katalogni ishdan chiqarmasligi kerak."""
    catalog = tmp_path / "models.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "yaxshi": {"display_name": "Yaxshi", "backend": "echo"},
                    "buzuq": {"backend": 12345, "context_length": "matn-emas-son"},
                }
            }
        ),
        encoding="utf-8",
    )
    reg = ModelRegistry(catalog, tmp_path / "s.json", total_memory_gb=24.0)
    assert "yaxshi" in {m.spec.id for m in reg.list_models()}


def test_katalogni_qayta_oqish_faol_modelni_saqlaydi(
    registry: ModelRegistry, tmp_path: Path
) -> None:
    registry.activate("echo-a")

    catalog = dict(CATALOG)
    catalog["models"] = {**CATALOG["models"], "yangi": {"display_name": "Yangi", "backend": "echo"}}
    registry.catalog_path.write_text(yaml.safe_dump(catalog), encoding="utf-8")

    registry.reload_catalog()

    assert "yangi" in {m.spec.id for m in registry.list_models()}
    assert registry.active_id == "echo-a", "qayta o'qish faol modelni to'xtatmasligi kerak"


# --------------------------------------------------------------------------- #
# Almashtirish
# --------------------------------------------------------------------------- #


def test_faollashtirish(registry: ModelRegistry) -> None:
    info = registry.activate("echo-a")
    assert info.is_active
    assert info.status is ModelStatus.ACTIVE
    assert registry.active_id == "echo-a"
    assert registry.backend.is_loaded


def test_almashtirish_eskisini_boshatadi(registry: ModelRegistry) -> None:
    registry.activate("echo-a")
    first = registry.backend

    registry.activate("echo-b")

    assert registry.active_id == "echo-b"
    assert not first.is_loaded, "eski model bo'shatilishi kerak (24 GB da ikkalasi sig'maydi)"
    assert registry.backend is not first


def test_ayni_modelni_qayta_faollashtirish_qayta_yuklamaydi(registry: ModelRegistry) -> None:
    registry.activate("echo-a")
    backend = registry.backend
    registry.activate("echo-a")
    assert registry.backend is backend


def test_nomalum_model(registry: ModelRegistry) -> None:
    with pytest.raises(KeyError, match="katalogda yo'q"):
        registry.activate("bunday-model-yoq")


def test_nomalum_backend(registry: ModelRegistry) -> None:
    from uzlegal.inference.backend import BackendUnavailableError

    with pytest.raises(BackendUnavailableError):
        registry.activate("yomon-backend")


def test_model_yoqda_backend_xatosi(registry: ModelRegistry) -> None:
    with pytest.raises(ModelSwapError, match="Faol model yo'q"):
        _ = registry.backend


# --------------------------------------------------------------------------- #
# Xotira nazorati
# --------------------------------------------------------------------------- #


def test_sigmaydigan_model_rad_etiladi(registry: ModelRegistry) -> None:
    with pytest.raises(ModelSwapError, match="sig'maydi"):
        registry.activate("ulkan")


def test_force_bilan_majburlash_mumkin(registry: ModelRegistry) -> None:
    info = registry.activate("ulkan", force=True)
    assert info.is_active


def test_sigmaydigan_model_royxatda_belgilanadi(registry: ModelRegistry) -> None:
    ulkan = next(m for m in registry.list_models() if m.spec.id == "ulkan")
    assert not ulkan.fits_in_memory
    assert ulkan.memory_warning is not None

    kichik = next(m for m in registry.list_models() if m.spec.id == "kichik")
    assert kichik.fits_in_memory


def test_kichik_xotirada_katta_model_sigmaydi(tmp_path: Path) -> None:
    catalog = tmp_path / "models.yaml"
    catalog.write_text(yaml.safe_dump(CATALOG), encoding="utf-8")
    reg = ModelRegistry(catalog, tmp_path / "s.json", total_memory_gb=8.0)

    kichik = next(m for m in reg.list_models() if m.spec.id == "kichik")
    assert not kichik.fits_in_memory, "8 GB mashinada 4 GB model + 9 GB zaxira sig'maydi"


# --------------------------------------------------------------------------- #
# Holatni saqlash
# --------------------------------------------------------------------------- #


def test_holat_saqlanadi(registry: ModelRegistry) -> None:
    registry.activate("echo-b")
    saved = json.loads(registry.state_path.read_text(encoding="utf-8"))
    assert saved["active_model"] == "echo-b"


def test_holat_tiklanadi(registry: ModelRegistry, tmp_path: Path) -> None:
    registry.activate("echo-b")
    registry.unload()
    assert registry.active_id is None

    fresh = ModelRegistry(registry.catalog_path, registry.state_path, total_memory_gb=24.0)
    assert fresh.restore_state() == "echo-b"
    assert fresh.active_id == "echo-b"


def test_buzuq_holat_fayli_xato_bermaydi(registry: ModelRegistry) -> None:
    registry.state_path.parent.mkdir(parents=True, exist_ok=True)
    registry.state_path.write_text("{buzuq json", encoding="utf-8")
    assert registry.restore_state() is None


def test_katalogdan_ochirilgan_model_tiklanmaydi(registry: ModelRegistry, tmp_path: Path) -> None:
    registry.activate("echo-b")
    registry.state_path.write_text(
        json.dumps({"active_model": "endi-yoq", "active_adapter": None}), encoding="utf-8"
    )
    fresh = ModelRegistry(registry.catalog_path, registry.state_path, total_memory_gb=24.0)
    assert fresh.restore_state() is None


# --------------------------------------------------------------------------- #
# Adapterlar
# --------------------------------------------------------------------------- #


def test_oqitilmagan_adapter_aniq_xato_beradi(registry: ModelRegistry) -> None:
    registry.activate("echo-a")
    with pytest.raises(KeyError, match="ro'yxatda yo'q"):
        registry.set_adapter("advocate")


def test_bazaga_qaytish(registry: ModelRegistry) -> None:
    registry.activate("echo-a")
    registry.set_adapter(None)
    assert registry.active_adapter is None


# --------------------------------------------------------------------------- #
# Tekshiruvlar almashtirishdan OLDIN bajarilishi kerak
# --------------------------------------------------------------------------- #


def test_yuklab_olinmagan_model_faolini_ochirmaydi(registry: ModelRegistry, tmp_path: Path) -> None:
    """Real xato: yo'q modelga o'tishga urinish ishlayotgan modelni yo'q qilardi."""
    catalog = dict(CATALOG)
    catalog["models"] = {
        **CATALOG["models"],
        "yoq-fayl": {
            "display_name": "Yo'q fayl",
            "backend": "echo",
            "local_path": str(tmp_path / "mavjud-emas"),
            "size_gb": 1.0,
        },
    }
    registry.catalog_path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    registry.reload_catalog()

    registry.activate("echo-a")
    with pytest.raises(ModelSwapError, match="yuklab olinmagan"):
        registry.activate("yoq-fayl")

    assert registry.active_id == "echo-a", "muvaffaqiyatsiz urinish faol modelni saqlashi kerak"
    assert registry.backend.is_loaded


def test_sigmaydigan_model_faolini_ochirmaydi(registry: ModelRegistry) -> None:
    registry.activate("echo-a")
    with pytest.raises(ModelSwapError, match="sig'maydi"):
        registry.activate("ulkan")
    assert registry.active_id == "echo-a"


def test_nomalum_backend_faolini_ochirmaydi(registry: ModelRegistry) -> None:
    from uzlegal.inference.backend import BackendUnavailableError

    registry.activate("echo-a")
    with pytest.raises(BackendUnavailableError):
        registry.activate("yomon-backend")
    assert registry.active_id == "echo-a"
