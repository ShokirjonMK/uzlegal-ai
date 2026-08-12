"""API kirish nazorati testlari.

Bu testlar bitta narsani isbotlaydi: `/v1/admin/*` marshrutlari
**hech qanday holatda** kalitsiz ochiq qolmaydi. Ilgari ular ochiq edi —
`POST /v1/admin/users` va kalit qayta yaratish hech narsa so'ramasdi.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from uzlegal.api import auth as auth_mod
from uzlegal.api.app import app
from uzlegal.config import get_settings

ADMIN_KEY = "admin-test-kaliti-32-belgi-xxxxxxxx"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Har test toza muhitdan boshlanadi.

    IP hisoblagichi ham tozalanadi: aks holda testlar bir-birining
    chastota oynasiga tushib, tartibga bog'liq bo'lib qolardi.
    """
    monkeypatch.delenv(auth_mod.ADMIN_KEY_ENV, raising=False)
    monkeypatch.delenv(auth_mod.STATIC_KEYS_ENV, raising=False)
    auth_mod._ip_limiter._hits.clear()


# --------------------------------------------------------------------------- #
# Admin marshrutlari
# --------------------------------------------------------------------------- #


def test_admin_kalitsiz_503(client: TestClient) -> None:
    """Kalit sozlanmagan — marshrut O'CHIRILADI, ochiq qolmaydi.

    «Sozlanmagan» hech qachon «hammaga ruxsat» degani emas.
    """
    response = client.post("/v1/admin/users", json={"user_id": "x"})
    assert response.status_code == 503
    assert auth_mod.ADMIN_KEY_ENV in response.json()["detail"]


def test_admin_notogri_kalit_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth_mod.ADMIN_KEY_ENV, ADMIN_KEY)
    response = client.post(
        "/v1/admin/users", json={"user_id": "x"}, headers={"X-API-Key": "boshqa-kalit"}
    )
    assert response.status_code == 401


def test_admin_kalitsiz_sorov_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth_mod.ADMIN_KEY_ENV, ADMIN_KEY)
    assert client.get("/v1/admin/sync").status_code == 401


def test_admin_togri_kalit_otadi(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth_mod.ADMIN_KEY_ENV, ADMIN_KEY)
    response = client.get("/v1/admin/sync", headers={"X-API-Key": ADMIN_KEY})
    assert response.status_code == 200


def test_admin_bearer_sarlavhasi_ham_ishlaydi(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(auth_mod.ADMIN_KEY_ENV, ADMIN_KEY)
    response = client.get("/v1/admin/sync", headers={"Authorization": f"Bearer {ADMIN_KEY}"})
    assert response.status_code == 200


def test_notanish_admin_marshruti_ham_yopiq(client: TestClient) -> None:
    """Prefiks bo'yicha himoya — kelajakdagi marshrutlar avtomatik yopiq.

    Aynan shu narsa `Depends()` yondashuvida yo'q edi: yangi endpoint
    yozgan odam bog'liqlikni qo'shishni unutsa, u jimgina ochiq qolardi.
    """
    assert client.get("/v1/admin/hali-yozilmagan-marshrut").status_code == 503


# --------------------------------------------------------------------------- #
# Ommaviy marshrutlar
# --------------------------------------------------------------------------- #


def test_health_har_doim_ochiq(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uptime monitori kalit yubora olmaydi."""
    monkeypatch.setenv(auth_mod.ADMIN_KEY_ENV, ADMIN_KEY)
    assert client.get("/v1/health").status_code == 200


def test_health_himoya_holatini_kotarsatadi(client: TestClient) -> None:
    body = client.get("/v1/health").json()
    assert body["auth"]["admin_key_configured"] is False
    assert "admin_key" not in str(body).lower() or ADMIN_KEY not in str(body)


def test_plans_ochiq(client: TestClient) -> None:
    assert client.get("/v1/plans").status_code == 200


# --------------------------------------------------------------------------- #
# `auth: api_key` rejimi
# --------------------------------------------------------------------------- #


@pytest.fixture
def api_key_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """`server` profilidagi kabi: kalit majburiy."""
    settings = get_settings()
    monkeypatch.setattr(settings, "api_auth", "api_key")


def test_api_key_rejimida_kalitsiz_401(client: TestClient, api_key_mode: None) -> None:
    response = client.post("/v1/consult", json={"question": "Savol matni?"})
    assert response.status_code == 401


def test_api_key_rejimida_statik_kalit_otadi(
    client: TestClient, api_key_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(auth_mod.STATIC_KEYS_ENV, "kalit-bir, kalit-ikki")
    response = client.post(
        "/v1/consult", json={"question": "Savol matni?"}, headers={"X-API-Key": "kalit-ikki"}
    )
    # 401 EMAS — kalit qabul qilindi. Javobning o'zi model holatiga bog'liq.
    assert response.status_code != 401


def test_api_key_rejimida_notogri_kalit_401(
    client: TestClient, api_key_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(auth_mod.STATIC_KEYS_ENV, "kalit-bir")
    response = client.post(
        "/v1/consult", json={"question": "Savol matni?"}, headers={"X-API-Key": "yolgon"}
    )
    assert response.status_code == 401


def test_none_rejimida_kalit_talab_qilinmaydi(client: TestClient) -> None:
    """`local-dev` — standart holat, kalitsiz ishlaydi."""
    assert get_settings().api_auth == "none"
    response = client.post("/v1/consult", json={"question": "Savol matni?"})
    assert response.status_code != 401


# --------------------------------------------------------------------------- #
# IP chastotasi
# --------------------------------------------------------------------------- #


def test_ip_chegarasi_429_beradi(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit", {"per_ip_minute": 3})

    codes = [client.get("/v1/agents").status_code for _ in range(5)]
    assert 429 in codes
    assert codes.count(429) == 2  # dastlabki 3 tasi o'tadi


def test_ip_chegarasi_nol_bolsa_ochirilgan(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit", {"per_ip_minute": 0})
    assert all(client.get("/v1/agents").status_code != 429 for _ in range(20))


def test_chegara_retry_after_beradi(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """429 javobi qachon qayta urinishni AYTISHI kerak."""
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit", {"per_ip_minute": 1})

    client.get("/v1/agents")
    response = client.get("/v1/agents")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


# --------------------------------------------------------------------------- #
# Kalit taqqoslash
# --------------------------------------------------------------------------- #


def test_kalit_bosh_joydan_tozalanadi() -> None:
    assert auth_mod._presented_key(None, "  kalit  ") == "kalit"
    assert auth_mod._presented_key("Bearer   kalit  ", None) == "kalit"


def test_bearer_registri_muhim_emas() -> None:
    assert auth_mod._presented_key("bearer kalit", None) == "kalit"
    assert auth_mod._presented_key("BEARER kalit", None) == "kalit"


def test_x_api_key_bearerdan_ustun() -> None:
    assert auth_mod._presented_key("Bearer a", "b") == "b"


def test_statik_kalitlar_verguldan_ajratiladi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth_mod.STATIC_KEYS_ENV, " a , b ,, c ")
    assert auth_mod._static_keys() == {"a", "b", "c"}


def test_bosh_admin_kaliti_none_hisoblanadi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bo'sh satr kalit EMAS — aks holda `UZLEGAL_ADMIN_KEY=` himoyani ochardi."""
    monkeypatch.setenv(auth_mod.ADMIN_KEY_ENV, "   ")
    assert auth_mod._admin_key() is None
