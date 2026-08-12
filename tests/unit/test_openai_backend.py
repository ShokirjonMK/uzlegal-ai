"""OpenAI-mos backend testlari.

Haqiqiy server ishga tushirilmaydi — `httpx.MockTransport` bilan endpoint
taqlid qilinadi. Sabab: bu testlar CI da, Ollama o'rnatilmagan mashinada
ham o'tishi kerak, aks holda ular jimgina o'tkazib yuboriladi va backend
umuman sinalmay qoladi.
"""

from __future__ import annotations

import json

import httpx
import pytest

from uzlegal.inference.backend import BackendUnavailableError
from uzlegal.inference.openai_backend import OpenAIBackend
from uzlegal.types import GenerationParams, ModelSpec


def _spec(**kwargs: object) -> ModelSpec:
    body: dict[str, object] = {
        "id": "test-model",
        "display_name": "Test",
        "backend": "openai",
        "hf_id": "gemma3:12b",
        "endpoint": "http://test-server/v1",
    }
    body.update(kwargs)
    return ModelSpec(**body)  # type: ignore[arg-type]


def _backend(handler: object, **spec_kwargs: object) -> OpenAIBackend:
    """Backend ni soxta transport bilan quradi.

    `load()` ni chetlab o'tmaymiz — u ham sinalishi kerak. Shuning uchun
    mijoz `load()` dan keyin almashtiriladi emas, balki transport
    darhol ulanadi.
    """
    backend = OpenAIBackend(_spec(**spec_kwargs))
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    backend._client = httpx.Client(base_url=backend.endpoint, transport=transport)
    return backend


# --------------------------------------------------------------------------- #
# Sozlamalar
# --------------------------------------------------------------------------- #


def test_endpoint_yozuvdan_olinadi() -> None:
    assert OpenAIBackend(_spec()).endpoint == "http://test-server/v1"


def test_endpoint_muhit_ozgaruvchisidan_olinadi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UZLEGAL_OPENAI_ENDPOINT", "http://env-server/v1/")
    assert OpenAIBackend(_spec(endpoint=None)).endpoint == "http://env-server/v1"


def test_endpoint_standarti_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UZLEGAL_OPENAI_ENDPOINT", raising=False)
    assert OpenAIBackend(_spec(endpoint=None)).endpoint == "http://localhost:11434/v1"


def test_yozuvdagi_endpoint_muhitdan_ustun(monkeypatch: pytest.MonkeyPatch) -> None:
    """YAML aniq tanlov, env esa mashinaga xos standart."""
    monkeypatch.setenv("UZLEGAL_OPENAI_ENDPOINT", "http://env-server/v1")
    assert OpenAIBackend(_spec()).endpoint == "http://test-server/v1"


def test_model_nomi_hf_id_dan_olinadi() -> None:
    assert OpenAIBackend(_spec()).model_name == "gemma3:12b"
    assert OpenAIBackend(_spec(hf_id=None)).model_name == "test-model"


# --------------------------------------------------------------------------- #
# load() — server tekshiruvi
# --------------------------------------------------------------------------- #


def _models_response(*names: str) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"id": n} for n in names]})


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    """`load()` ichida quriladigan mijozni soxta transportga o'tkazadi.

    Haqiqiy klass avval saqlanadi: `httpx.Client` ni almashtirgandan keyin
    lambda ichida unga murojaat qilish o'zini o'zi chaqirishga olib keladi.
    """
    real_client = httpx.Client

    def factory(**kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)  # type: ignore[arg-type]
        return real_client(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "Client", factory)


def test_load_server_javob_bermasa_aniq_xato(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ulanmadi")

    _patch_client(monkeypatch, handler)
    with pytest.raises(BackendUnavailableError, match="javob bermadi"):
        OpenAIBackend(_spec()).load()


def test_load_model_serverda_yoq_bolsa_xato(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _models_response("mistral:latest", "llama3:8b")

    _patch_client(monkeypatch, handler)
    with pytest.raises(BackendUnavailableError, match="ollama pull"):
        OpenAIBackend(_spec()).load()


def test_load_model_topilsa_otadi(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _models_response("gemma3:12b")

    _patch_client(monkeypatch, handler)
    backend = OpenAIBackend(_spec())
    backend.load()
    assert backend.is_loaded


def test_load_bosh_royxat_togri_deb_qabul_qilinadi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bo'sh ro'yxat «model yo'q» emas, «server aytmadi» degani.

    Eski vLLM versiyalari `/models` ni umuman bermaydi. Bunday holda
    ishga tushishni to'xtatish noto'g'ri bo'lardi.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    _patch_client(monkeypatch, handler)
    backend = OpenAIBackend(_spec())
    backend.load()
    assert backend.is_loaded


def test_load_ollama_teg_variantini_taniydi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama `gemma3:12b` ni `gemma3:12b-it-q4_K_M` deb qaytarishi mumkin."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _models_response("gemma3:12b-it-q4_K_M")

    _patch_client(monkeypatch, handler)
    backend = OpenAIBackend(_spec())
    backend.load()
    assert backend.is_loaded


# --------------------------------------------------------------------------- #
# generate()
# --------------------------------------------------------------------------- #


def test_generate_javob_matnini_qaytaradi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "Javob matni"}}]})

    assert _backend(handler).generate("savol", GenerationParams()) == "Javob matni"


def test_generate_system_promptni_yuboradi() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _backend(handler).generate("savol", GenerationParams(system="Sen advokatsan"))

    messages = seen["messages"]
    assert messages == [
        {"role": "system", "content": "Sen advokatsan"},
        {"role": "user", "content": "savol"},
    ]


def test_generate_parametrlarni_uzatadi() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _backend(handler).generate(
        "savol",
        GenerationParams(max_tokens=123, temperature=0.7, top_p=0.5, stop=["STOP"], seed=42),
    )

    assert seen["max_tokens"] == 123
    assert seen["temperature"] == 0.7
    assert seen["top_p"] == 0.5
    assert seen["stop"] == ["STOP"]
    assert seen["seed"] == 42
    assert seen["model"] == "gemma3:12b"


def test_generate_bosh_javobda_xato() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(RuntimeError, match="bo'sh javob"):
        _backend(handler).generate("savol", GenerationParams())


def test_generate_http_xatosi_aniq_xabar_beradi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="ichki xato")

    with pytest.raises(RuntimeError, match="Generatsiya xatosi"):
        _backend(handler).generate("savol", GenerationParams())


def test_yuklanmagan_backend_aniq_xato_beradi() -> None:
    with pytest.raises(RuntimeError, match="yuklanmagan"):
        OpenAIBackend(_spec()).generate("savol", GenerationParams())


# --------------------------------------------------------------------------- #
# stream()
# --------------------------------------------------------------------------- #


def _sse(*chunks: str) -> bytes:
    lines = []
    for chunk in chunks:
        payload = {"choices": [{"delta": {"content": chunk}}]}
        lines.append(f"data: {json.dumps(payload)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def test_stream_boklaklarni_ketma_ket_beradi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse("Bir ", "ikki ", "uch"))

    parts = list(_backend(handler).stream("savol", GenerationParams()))
    assert "".join(parts) == "Bir ikki uch"


def test_stream_buzuq_json_ni_otkazib_yuboradi() -> None:
    """Bitta buzuq bo'lak butun oqimni yiqitmasligi kerak."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = b"data: {buzuq\n\n" + _sse("javob")
        return httpx.Response(200, content=body)

    parts = list(_backend(handler).stream("savol", GenerationParams()))
    assert "".join(parts) == "javob"


def test_stream_stop_belgisida_toxtaydi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse("bir", "STOP", "uch"))

    parts = list(_backend(handler).stream("savol", GenerationParams(stop=["STOP"])))
    assert parts == ["bir", "STOP"]


# --------------------------------------------------------------------------- #
# Adapter va xotira
# --------------------------------------------------------------------------- #


def test_adapter_none_muammosiz_otadi() -> None:
    OpenAIBackend(_spec()).set_adapter(None)


def test_adapter_jim_otkazib_yuborilmaydi() -> None:
    """Rol adapteri so'ralib, qo'llanmagan javob — noto'g'ri javob."""
    with pytest.raises(NotImplementedError, match="adapter"):
        OpenAIBackend(_spec()).set_adapter("adapters/advocate/current")


def test_xotira_hisobi_nolga_teng() -> None:
    """Model boshqa jarayonda — bizning byudjetimizda o'rni yo'q."""
    assert OpenAIBackend(_spec()).memory_usage_gb() == 0.0


def test_prefix_cache_none_qaytaradi() -> None:
    assert OpenAIBackend(_spec()).make_prefix_cache("prefiks") is None


def test_unload_mijozni_yopadi() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    backend = _backend(handler)
    assert backend.is_loaded
    backend.unload()
    assert not backend.is_loaded
