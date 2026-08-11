"""Konfiguratsiya va sirlarni boshqarish testlari."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from uzlegal.config import Settings, TelegramSettings, _load_dotenv


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "UZLEGAL_TELEGRAM_BOT_TOKEN",
        "UZLEGAL_TELEGRAM_CHAT_ID",
        "UZLEGAL_TELEGRAM_ALLOWED_CHATS",
    ):
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #


def test_sozlanmagan_holat() -> None:
    assert not TelegramSettings().is_configured


def test_envdan_oqiladi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UZLEGAL_TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("UZLEGAL_TELEGRAM_CHAT_ID", "999")

    telegram = TelegramSettings.from_env()

    assert telegram.is_configured
    assert telegram.chat_id == "999"


def test_faqat_token_yetarli_emas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UZLEGAL_TELEGRAM_BOT_TOKEN", "123:ABC")
    assert not TelegramSettings.from_env().is_configured


def test_token_repr_da_korinmaydi() -> None:
    """Token log yoki xato izida tasodifan chiqib ketmasligi kerak."""
    telegram = TelegramSettings(bot_token="123:MAXFIY", chat_id="1")
    assert "MAXFIY" not in repr(telegram)


def test_ruxsat_etilgan_chatlar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UZLEGAL_TELEGRAM_ALLOWED_CHATS", "111, 222")

    telegram = TelegramSettings.from_env()

    assert telegram.allows("111")
    assert telegram.allows(222)  # type: ignore[arg-type]
    assert not telegram.allows("333")


def test_bosh_royxat_hammaga_ruxsat() -> None:
    assert TelegramSettings().allows("istalgan")


# --------------------------------------------------------------------------- #
# .env
# --------------------------------------------------------------------------- #


def test_dotenv_oqiladi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("UZLEGAL_TELEGRAM_CHAT_ID=777\n# izoh\n\n", encoding="utf-8")
    monkeypatch.delenv("UZLEGAL_TELEGRAM_CHAT_ID", raising=False)

    _load_dotenv(env)

    assert os.environ["UZLEGAL_TELEGRAM_CHAT_ID"] == "777"


def test_mavjud_env_ustun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CI da o'zgaruvchi tashqaridan keladi — fayl uni bosib ketmasligi kerak."""
    env = tmp_path / ".env"
    env.write_text("UZLEGAL_TELEGRAM_CHAT_ID=fayldan\n", encoding="utf-8")
    monkeypatch.setenv("UZLEGAL_TELEGRAM_CHAT_ID", "tashqaridan")

    _load_dotenv(env)

    assert os.environ["UZLEGAL_TELEGRAM_CHAT_ID"] == "tashqaridan"


def test_qoshtirnoq_olib_tashlanadi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text('UZLEGAL_TELEGRAM_CHAT_ID="555"\n', encoding="utf-8")
    monkeypatch.delenv("UZLEGAL_TELEGRAM_CHAT_ID", raising=False)

    _load_dotenv(env)

    assert os.environ["UZLEGAL_TELEGRAM_CHAT_ID"] == "555"


def test_yoq_fayl_xato_bermaydi(tmp_path: Path) -> None:
    _load_dotenv(tmp_path / "yoq.env")


# --------------------------------------------------------------------------- #
# Sirlar repoda bo'lmasligi
# --------------------------------------------------------------------------- #

REPO = Path(__file__).parents[2]


def test_env_gitignore_da() -> None:
    assert ".env" in (REPO / ".gitignore").read_text(encoding="utf-8")


SECRET_KEY = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD)", re.IGNORECASE)


def test_env_example_da_sir_yoq() -> None:
    """Sir maydonlari bo'sh bo'lishi kerak.

    Sir bo'lmagan qiymatlar (`UZLEGAL_PROFILE=local-dev`) qoladi — ular
    namunaning foydali qismi.
    """
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if SECRET_KEY.search(key):
            assert not value.strip(), f"namuna faylda sir qolib ketgan: {key}"


# Haqiqiy sirga o'xshash qiymat: uzun tasodifiy satr yoki Telegram token shakli
SECRET_VALUE = re.compile(r"[A-Za-z0-9_\-]{24,}|\d{8,}:[A-Za-z0-9_\-]{30,}")

# Sir emas, lekin uzun bo'lishi mumkin — YAML da bular normal
ALLOWED = re.compile(r"^(https?://|\$\{|[a-z0-9_\-]+/[a-z0-9._\-]+$)", re.IGNORECASE)


def test_configlarda_sir_qiymat_yoq() -> None:
    """YAML fayllari repoga tushadi — ularda haqiqiy sir bo'lmasligi shart.

    Kalit nomlari (`auth: api_key`) muammo emas — ular rejim nomi.
    Tekshiriladigan narsa: sirga o'xshash **qiymat**.
    """
    for path in (REPO / "configs").rglob("*.yaml"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#") or ":" not in line:
                continue
            value = line.partition(":")[2].strip().strip("\"'")
            if not value or ALLOWED.match(value):
                continue
            assert not SECRET_VALUE.fullmatch(value), (
                f"{path.name}:{number} da sirga o'xshash qiymat: {value[:20]}…"
            )


def test_settings_telegramni_yuklaydi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UZLEGAL_TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("UZLEGAL_TELEGRAM_CHAT_ID", "42")

    assert Settings.load().telegram.chat_id == "42"
