"""Python SDK — UzLegal ni boshqa dasturdan ishlatish.

Ikki rejim, bir xil shartnoma:

```python
from uzlegal.sdk import UzLegal

# 1. Ichki — kutubxona sifatida, tarmoqsiz
uz = UzLegal()
answer = uz.ask("Daʼvo muddati qancha")

# 2. Masofaviy — ishlab turgan xizmatga
uz = UzLegal(base_url="http://127.0.0.1:8080")
answer = uz.ask("Daʼvo muddati qancha")
```

## Nima uchun ikkalasi bir interfeysda

Foydalanuvchi kodi qaysi rejimda ishlashini bilmasligi kerak: ishlab
chiqishda kutubxona, ishlab chiqarishda xizmat — kod o'zgarmaydi.
Shuning uchun `base_url` berilishi yagona farq.

## Nima qaytadi

`ConsultResult` — javob, iqtiboslar, gate hisoboti va to'liq iz. Qisqa
javob kerak bo'lsa `ask()` faqat matnni beradi.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from uzlegal.types import ConsultMode, ConsultResult

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 180.0  # `complex` rejim bir daqiqadan oshishi mumkin


class UzLegalError(RuntimeError):
    pass


class UzLegal:
    """UzLegal-AI mijozi."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self.api_key = api_key
        self._client: Any = None

    # ------------------------------------------------------------------ #
    # Asosiy amallar
    # ------------------------------------------------------------------ #

    def consult(
        self,
        question: str,
        *,
        mode: ConsultMode | str | None = None,
        as_of: date | str | None = None,
        client_position: str | None = None,
        top_k: int = 8,
    ) -> ConsultResult:
        """To'liq natija — javob, iqtiboslar, gate hisoboti, iz."""
        if self.base_url is None:
            return self._local(question, mode, as_of, client_position, top_k)
        return self._remote(question, mode, as_of, client_position, top_k)

    def ask(self, question: str, **kwargs: Any) -> str:
        """Faqat javob matni — tez foydalanish uchun."""
        return self.consult(question, **kwargs).answer

    def search(self, query: str, *, top_k: int = 8, as_of: date | str | None = None) -> list[Any]:
        """Modelsiz qidiruv — tez va arzon.

        Faqat ichki rejimda ishlaydi: qidiruv natijasi API da alohida
        endpoint sifatida ochilmagan, chunki u `consult` ichida keladi.
        """
        if self.base_url is not None:
            raise UzLegalError(
                "`search()` faqat ichki rejimda mavjud. Masofaviy rejimda `consult()` ni ishlating."
            )
        from uzlegal.index.store import KnowledgeIndex
        from uzlegal.retrieval.hybrid import HybridRetriever

        found = HybridRetriever(KnowledgeIndex()).search(
            query, top_k=top_k, as_of=_to_date(as_of)
        )
        return found.results

    def health(self) -> dict[str, Any]:
        """Tizim holati — model va bilim bazasi tayyormi."""
        if self.base_url is None:
            from uzlegal.config import get_registry
            from uzlegal.ingest.sync import SyncManager

            state = SyncManager().state
            return {
                "mode": "local",
                "model_ready": get_registry().active_id is not None,
                "active_model": get_registry().active_id,
                "kb_version": state.kb_version,
                "kb_stale": state.is_stale(),
            }
        return self._get("/v1/health")

    # ------------------------------------------------------------------ #
    # Amalga oshirish
    # ------------------------------------------------------------------ #

    def _local(
        self,
        question: str,
        mode: ConsultMode | str | None,
        as_of: date | str | None,
        client_position: str | None,
        top_k: int,
    ) -> ConsultResult:
        from uzlegal.core import consult

        return consult(
            question,
            mode=mode,
            as_of=_to_date(as_of),
            client_position=client_position,
            top_k=top_k,
        )

    def _remote(
        self,
        question: str,
        mode: ConsultMode | str | None,
        as_of: date | str | None,
        client_position: str | None,
        top_k: int,
    ) -> ConsultResult:
        parsed = _to_date(as_of)
        payload = {
            "question": question,
            "mode": mode.value if isinstance(mode, ConsultMode) else mode,
            "as_of": parsed.isoformat() if parsed else None,
            "client_position": client_position,
            "top_k": top_k,
        }
        data = self._post("/v1/consult", payload)
        return ConsultResult(**data)

    @property
    def client(self) -> Any:
        if self._client is None:
            import httpx

            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            self._client = httpx.Client(timeout=self.timeout, headers=headers)
        return self._client

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        import httpx

        try:
            response = self.client.post(f"{self.base_url}{path}", json=payload)
        except httpx.HTTPError as exc:
            raise UzLegalError(f"Xizmatga ulanib bo'lmadi ({self.base_url}): {exc}") from exc
        return self._unwrap(response)

    def _get(self, path: str) -> dict[str, Any]:
        import httpx

        try:
            response = self.client.get(f"{self.base_url}{path}")
        except httpx.HTTPError as exc:
            raise UzLegalError(f"Xizmatga ulanib bo'lmadi ({self.base_url}): {exc}") from exc
        return self._unwrap(response)

    @staticmethod
    def _unwrap(response: Any) -> dict[str, Any]:
        if response.status_code >= 400:
            detail = ""
            try:
                detail = response.json().get("detail", "")
            except Exception:
                detail = response.text[:200]
            raise UzLegalError(f"{response.status_code}: {detail}")
        return response.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> UzLegal:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _to_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


__all__ = ["ConsultMode", "ConsultResult", "UzLegal", "UzLegalError"]
