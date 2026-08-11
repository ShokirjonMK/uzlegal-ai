"""Bilim bazasini yangilash mantiqi testlari.

Tarmoqqa chiqmaydi — faqat rejalashtirish, holat va sozlamalar tekshiriladi.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from uzlegal.ingest.connectors.lex_uz import MIN_CRAWL_DELAY, RateLimiter
from uzlegal.ingest.sync import (
    DEFAULT_INTERVAL_DAYS,
    STALE_WARNING_DAYS,
    SyncManager,
    SyncState,
    SyncStatus,
)


@pytest.fixture
def manager(tmp_path: Path) -> SyncManager:
    return SyncManager(state_path=tmp_path / "sync-state.json")


# --------------------------------------------------------------------------- #
# Rejalashtirish
# --------------------------------------------------------------------------- #


def test_standart_interval_7_kun() -> None:
    assert SyncState().interval_days == DEFAULT_INTERVAL_DAYS == 7


def test_hech_qachon_yangilanmagan_bolsa_muddati_kelgan() -> None:
    assert SyncState().is_due()


def test_yangi_yangilangandan_keyin_muddati_kelmagan() -> None:
    state = SyncState(last_sync_at=datetime.now(UTC) - timedelta(days=1))
    assert not state.is_due()


def test_7_kundan_keyin_muddati_keladi() -> None:
    state = SyncState(last_sync_at=datetime.now(UTC) - timedelta(days=7, minutes=1))
    assert state.is_due()


def test_avtomatik_ochirilsa_muddati_kelmaydi() -> None:
    state = SyncState(last_sync_at=datetime.now(UTC) - timedelta(days=90), auto_enabled=False)
    assert not state.is_due()


def test_maxsus_interval() -> None:
    state = SyncState(last_sync_at=datetime.now(UTC) - timedelta(days=3), interval_days=2)
    assert state.is_due()


def test_keyingi_muddat_hisoblanadi() -> None:
    now = datetime.now(UTC)
    state = SyncState(last_sync_at=now, interval_days=7)
    assert state.next_due() == now + timedelta(days=7)


# --------------------------------------------------------------------------- #
# Eskirish ogohlantirishi
# --------------------------------------------------------------------------- #


def test_yangi_baza_eskirmagan() -> None:
    assert not SyncState(last_sync_at=datetime.now(UTC) - timedelta(days=3)).is_stale()


def test_14_kundan_keyin_eskirgan() -> None:
    old = datetime.now(UTC) - timedelta(days=STALE_WARNING_DAYS + 1)
    assert SyncState(last_sync_at=old).is_stale()


def test_qurilmagan_baza_eskirgan_hisoblanadi() -> None:
    """Bo'sh bilim bazasi eng xavfli holat — u ochiq belgilanishi kerak."""
    assert SyncState().is_stale()


def test_yosh_kunlarda() -> None:
    state = SyncState(last_sync_at=datetime.now(UTC) - timedelta(days=5))
    assert 4.9 < state.age_days() < 5.1


# --------------------------------------------------------------------------- #
# Boshqaruvchi
# --------------------------------------------------------------------------- #


def test_boshlangich_holat(manager: SyncManager) -> None:
    assert manager.status is SyncStatus.IDLE
    assert manager.current is None


def test_info_admin_uchun_toliq(manager: SyncManager) -> None:
    info = manager.info()
    for key in (
        "status",
        "auto_enabled",
        "interval_days",
        "last_sync_at",
        "next_due_at",
        "is_due",
        "is_stale",
        "kb_version",
    ):
        assert key in info


def test_sozlamalar_saqlanadi(manager: SyncManager, tmp_path: Path) -> None:
    manager.configure(interval_days=14, auto_enabled=False)

    reloaded = SyncManager(state_path=tmp_path / "sync-state.json")
    assert reloaded.state.interval_days == 14
    assert reloaded.state.auto_enabled is False


@pytest.mark.parametrize("bad", [0, -1, 91, 365])
def test_notogri_interval_rad_etiladi(manager: SyncManager, bad: int) -> None:
    with pytest.raises(ValueError, match="1 dan 90"):
        manager.configure(interval_days=bad)


def test_buzuq_holat_fayli_xato_bermaydi(tmp_path: Path) -> None:
    (tmp_path / "sync-state.json").write_text("{buzuq", encoding="utf-8")
    manager = SyncManager(state_path=tmp_path / "sync-state.json")
    assert manager.state.interval_days == DEFAULT_INTERVAL_DAYS


def test_muddati_kelmagan_bolsa_avtomatik_ishlamaydi(manager: SyncManager) -> None:
    manager.state.last_sync_at = datetime.now(UTC)
    assert manager.maybe_run_scheduled() is None


def test_avtomatik_ochirilgan_bolsa_ishlamaydi(manager: SyncManager) -> None:
    manager.configure(auto_enabled=False)
    assert manager.maybe_run_scheduled() is None


def test_cancel_ishlamayotganda_false(manager: SyncManager) -> None:
    assert manager.cancel() is False


# --------------------------------------------------------------------------- #
# Crawl-delay — lex.uz robots.txt talabi
# --------------------------------------------------------------------------- #


def test_crawl_delay_minimumdan_past_tushmaydi() -> None:
    """robots.txt 20 s talab qiladi — kodda uni chetlab o'tib bo'lmasligi kerak."""
    assert RateLimiter(delay=1.0).delay == MIN_CRAWL_DELAY
    assert RateLimiter(delay=0).delay == MIN_CRAWL_DELAY


def test_kattaroq_delay_saqlanadi() -> None:
    assert RateLimiter(delay=30.0).delay == 30.0


def test_birinchi_sorov_kutmaydi() -> None:
    assert RateLimiter(delay=20.0).wait() == 0.0
