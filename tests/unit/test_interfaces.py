"""Interfeys qatlami testlari — REST, SSE, Telegram, MCP, SDK.

Beshta interfeys bitta `consult()` ni chaqiradi. Bu testlarning maqsadi
shu qoidani qo'riqlash: agar interfeyslardan biri o'z mantiqini
qo'shsa, javoblar bir-biridan farq qila boshlaydi va foydalanuvchi
qaysi kanal orqali so'raganiga qarab boshqa javob oladi.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from uzlegal.types import Citation, ConsultMode, ConsultResult, GateReport, TraceEvent

# --------------------------------------------------------------------------- #
# Soxta natija
# --------------------------------------------------------------------------- #


def fake_result(**kwargs: Any) -> ConsultResult:
    defaults: dict[str, Any] = {
        "question": "Daʼvo muddati qancha",
        "mode": ConsultMode.SIMPLE,
        "answer": "Daʼvo muddati uch yil [C1]",
        "confidence": 0.8,
        "citations": [
            Citation(
                tag="C1",
                doc_id="fk",
                doc_title="Fuqarolik kodeksi",
                article="150",
                url="https://lex.uz/docs/fk#150",
            )
        ],
        "trace": [TraceEvent(node="retrieve", ms=120, detail={"chunks": 3})],
        "total_ms": 4200,
    }
    return ConsultResult(**{**defaults, **kwargs})


@pytest.fixture
def patched_consult(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """`core.consult` ni almashtiradi va chaqiruvlarni yozib boradi."""
    calls: list[dict[str, Any]] = []

    def fake(question: str, **kwargs: Any) -> ConsultResult:
        calls.append({"question": question, **kwargs})
        observe = kwargs.get("observe")
        if observe is not None:
            observe(TraceEvent(node="retrieve", ms=1))
            observe(TraceEvent(node="jurist", ms=2))
        return fake_result(question=question)

    import uzlegal.core

    monkeypatch.setattr(uzlegal.core, "consult", fake)
    return calls


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #


@pytest.fixture
def client() -> Any:
    from fastapi.testclient import TestClient

    from uzlegal.api.app import app

    return TestClient(app)


def test_consult_endpoint_natijani_qaytaradi(client: Any, patched_consult: list[Any]) -> None:
    response = client.post("/v1/consult", json={"question": "Daʼvo muddati qancha"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Daʼvo muddati uch yil [C1]"
    assert body["citations"][0]["tag"] == "C1"
    assert "gate" in body and "trace" in body


def test_bosh_savol_422(client: Any) -> None:
    assert client.post("/v1/consult", json={"question": ""}).status_code == 422


def test_notogri_sana_400(client: Any, patched_consult: list[Any]) -> None:
    response = client.post("/v1/consult", json={"question": "savol", "as_of": "kecha"})
    assert response.status_code == 400
    assert "as_of" in response.json()["detail"]


def test_parametrlar_uzatiladi(client: Any, patched_consult: list[Any]) -> None:
    client.post(
        "/v1/consult",
        json={
            "question": "savol",
            "mode": "complex",
            "as_of": "2021-06-01",
            "client_position": "Meni ishdan boʻshatishdi",
            "top_k": 5,
        },
    )
    call = patched_consult[0]
    assert call["mode"] == "complex"
    assert call["as_of"].isoformat() == "2021-06-01"
    assert call["top_k"] == 5


def test_top_k_chegarasi(client: Any) -> None:
    assert client.post("/v1/consult", json={"question": "s", "top_k": 99}).status_code == 422


def test_agents_endpoint(client: Any) -> None:
    body = client.get("/v1/agents").json()
    assert {a["role"] for a in body["agents"]} == {
        "jurist",
        "advocate",
        "prosecutor",
        "professor",
        "judge",
    }
    assert body["modes"]["simple"] == ["jurist"]


# --------------------------------------------------------------------------- #
# SSE
# --------------------------------------------------------------------------- #


def _sse_events(text: str) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    for block in text.strip().split("\n\n"):
        name = payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                payload = json.loads(line[6:])
        if name is not None:
            events.append((name, payload))
    return events


def test_sse_bosqichlarni_yuboradi(client: Any, patched_consult: list[Any]) -> None:
    response = client.post("/v1/consult/stream", json={"question": "savol"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(response.text)
    names = [name for name, _ in events]
    assert names[:2] == ["step", "step"], "har bosqich alohida hodisa bo'lishi kerak"
    assert names[-2:] == ["answer", "done"]


def test_sse_javobni_bir_marta_yuboradi(client: Any, patched_consult: list[Any]) -> None:
    """Javob bo'lak-bo'lak ketmaydi — gate uni to'liq matn ustida tekshiradi."""
    events = _sse_events(client.post("/v1/consult/stream", json={"question": "s"}).text)
    answers = [payload for name, payload in events if name == "answer"]
    assert len(answers) == 1
    assert answers[0]["answer"] == "Daʼvo muddati uch yil [C1]"


def test_sse_xatoni_oqimga_chiqaradi(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import uzlegal.core

    def boom(question: str, **kwargs: Any) -> ConsultResult:
        raise RuntimeError("indeks yoʻq")

    monkeypatch.setattr(uzlegal.core, "consult", boom)
    events = _sse_events(client.post("/v1/consult/stream", json={"question": "s"}).text)
    assert ("error", {"detail": "indeks yoʻq", "status": 500}) in events


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #


class FakeTelegram:
    """Telegram API o'rniga — yuborilgan xabarlarni yig'adi."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def post(self, url: str, json: dict[str, Any]) -> Any:
        if "sendMessage" in url:
            self.sent.append(json)
        return type("R", (), {"json": lambda self: {"ok": True, "result": []}})()


def make_bot(consult: Any = None) -> tuple[Any, FakeTelegram]:
    from uzlegal.bot.telegram import TelegramBot
    from uzlegal.config import TelegramSettings

    fake = FakeTelegram()
    bot = TelegramBot(
        TelegramSettings(bot_token="test-token", chat_id="1"),
        consult=consult or (lambda q, **kw: fake_result(question=q)),
        client=fake,  # type: ignore[arg-type]
    )
    return bot, fake


def message(text: str, chat_id: int = 1) -> dict[str, Any]:
    return {"message_id": 7, "chat": {"id": chat_id}, "text": text}


def test_bot_savolga_javob_beradi() -> None:
    bot, fake = make_bot()
    assert bot.handle(message("Daʼvo muddati qancha"))
    body = fake.sent[-1]["text"]
    assert "uch yil" in body
    assert "Manbalar" in body
    assert "lex.uz" in body, "iqtibos havolasi bo'lishi kerak"


def test_bot_tez_buyrugi_simple_rejim() -> None:
    seen: list[Any] = []
    bot, _ = make_bot(lambda q, **kw: seen.append(kw.get("mode")) or fake_result(question=q))
    bot.handle(message("/tez Daʼvo muddati"))
    assert seen == ["simple"]


def test_bot_ruxsatsiz_chatga_javob_bermaydi() -> None:
    from uzlegal.bot.telegram import TelegramBot
    from uzlegal.config import TelegramSettings

    fake = FakeTelegram()
    bot = TelegramBot(
        TelegramSettings(bot_token="t", chat_id="1", allowed_chats=["1"]),
        consult=lambda q, **kw: fake_result(),
        client=fake,  # type: ignore[arg-type]
    )
    assert not bot.handle(message("savol", chat_id=999))
    assert fake.sent == []


def test_bot_start_buyrugi() -> None:
    bot, fake = make_bot()
    bot.handle(message("/start"))
    assert "UzLegal-AI" in fake.sent[-1]["text"]


def test_bot_xatoni_koresatadi() -> None:
    def boom(question: str, **kwargs: Any) -> ConsultResult:
        raise RuntimeError("model yoʻq")

    bot, fake = make_bot(boom)
    bot.handle(message("savol"))
    assert "model yoʻq" in fake.sent[-1]["text"]


def test_uzun_xabar_bolinadi() -> None:
    from uzlegal.bot.telegram import MAX_MESSAGE, _split_message

    parts = _split_message("\n".join(f"{i}-satr" * 20 for i in range(400)))
    assert len(parts) > 1
    assert all(len(p) <= MAX_MESSAGE for p in parts)


def test_token_yoq_bolsa_aniq_xato() -> None:
    from uzlegal.bot.telegram import TelegramBot, TelegramError
    from uzlegal.config import TelegramSettings

    with pytest.raises(TelegramError, match="UZLEGAL_TELEGRAM_BOT_TOKEN"):
        TelegramBot(TelegramSettings())


def test_gate_ochirgani_botda_korinadi() -> None:
    bot, fake = make_bot(
        lambda q, **kw: fake_result(gate=GateReport(kept=["a"], dropped=["b", "c"]))
    )
    bot.handle(message("savol"))
    assert "2 daʼvo oʻchirildi" in fake.sent[-1]["text"]


# --------------------------------------------------------------------------- #
# MCP
# --------------------------------------------------------------------------- #


def rpc(method: str, **params: Any) -> dict[str, Any]:
    from uzlegal.mcp.server import handle

    result = handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    assert result is not None
    return result


def test_mcp_initialize() -> None:
    result = rpc("initialize")["result"]
    assert result["serverInfo"]["name"] == "uzlegal"
    assert "tools" in result["capabilities"]


def test_mcp_vositalar_royxati() -> None:
    tools = rpc("tools/list")["result"]["tools"]
    assert {t["name"] for t in tools} == {
        "uzlegal_search",
        "uzlegal_consult",
        "uzlegal_status",
    }
    assert all("inputSchema" in t for t in tools)


def test_mcp_bildirishnomaga_javob_yoq() -> None:
    """`id` yo'q so'rov — bildirishnoma, javob talab qilinmaydi."""
    from uzlegal.mcp.server import handle

    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_mcp_notanish_metod_xato() -> None:
    assert rpc("nimadir/boshqa")["error"]["code"] == -32601


def test_mcp_notanish_vosita_natija_sifatida_xato() -> None:
    """Vosita xatosi protokolni buzmaydi — mijoz modeli uni o'qiy oladi."""
    result = rpc("tools/call", name="yoq_vosita", arguments={})["result"]
    assert result["isError"] is True
    assert "yoq_vosita" in result["content"][0]["text"]


def test_mcp_consult_vositasi(monkeypatch: pytest.MonkeyPatch) -> None:
    import uzlegal.core

    monkeypatch.setattr(uzlegal.core, "consult", lambda q, **kw: fake_result(question=q))
    text = rpc("tools/call", name="uzlegal_consult", arguments={"question": "savol"})["result"][
        "content"
    ][0]["text"]
    assert "uch yil" in text
    assert "150-modda" in text


def test_mcp_vosita_xatosi_tutiladi(monkeypatch: pytest.MonkeyPatch) -> None:
    import uzlegal.core

    def boom(q: str, **kw: Any) -> ConsultResult:
        raise RuntimeError("indeks yoʻq")

    monkeypatch.setattr(uzlegal.core, "consult", boom)
    result = rpc("tools/call", name="uzlegal_consult", arguments={"question": "s"})["result"]
    assert result["isError"] is True
    assert "indeks yoʻq" in result["content"][0]["text"]


# --------------------------------------------------------------------------- #
# SDK
# --------------------------------------------------------------------------- #


def test_sdk_ichki_rejim(patched_consult: list[Any]) -> None:
    from uzlegal.sdk import UzLegal

    assert UzLegal().ask("Daʼvo muddati qancha") == "Daʼvo muddati uch yil [C1]"


def test_sdk_masofaviy_rejim_http_chaqiradi() -> None:
    from uzlegal.sdk import UzLegal

    captured: dict[str, Any] = {}

    class FakeClient:
        def post(self, url: str, json: dict[str, Any]) -> Any:
            captured["url"] = url
            captured["json"] = json
            return type(
                "R", (), {"status_code": 200, "json": lambda self: fake_result().model_dump()}
            )()

    uz = UzLegal(base_url="http://localhost:8080/")
    uz._client = FakeClient()
    result = uz.consult("savol", mode=ConsultMode.COMPLEX)

    assert captured["url"] == "http://localhost:8080/v1/consult"
    assert captured["json"]["mode"] == "complex"
    assert result.answer == "Daʼvo muddati uch yil [C1]"


def test_sdk_http_xatosi_aniq_xabar() -> None:
    from uzlegal.sdk import UzLegal, UzLegalError

    class FakeClient:
        def post(self, url: str, json: dict[str, Any]) -> Any:
            return type(
                "R",
                (),
                {"status_code": 409, "json": lambda self: {"detail": "model yoʻq"}},
            )()

    uz = UzLegal(base_url="http://localhost:8080")
    uz._client = FakeClient()
    with pytest.raises(UzLegalError, match="model yoʻq"):
        uz.consult("savol")


def test_sdk_search_masofaviy_rejimda_yoq() -> None:
    from uzlegal.sdk import UzLegal, UzLegalError

    with pytest.raises(UzLegalError, match="ichki rejimda"):
        UzLegal(base_url="http://x").search("savol")


def test_sdk_sana_satri_qabul_qilinadi(patched_consult: list[Any]) -> None:
    from uzlegal.sdk import UzLegal

    UzLegal().consult("savol", as_of="2021-06-01")
    assert patched_consult[0]["as_of"].isoformat() == "2021-06-01"
