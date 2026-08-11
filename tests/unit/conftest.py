"""Agent va orkestratsiya testlari uchun umumiy stublar.

Faza 5 testlarining asosiy talabi: **model yuklanmasdan o'tishi**. Shuning
uchun bu yerda ikkita soxta backend bor — `echo` (haqiqiy stub backend,
strukturali matn qaytaradi) va `ScriptedBackend` (oldindan yozilgan
javoblar, qayta urinishlarni sanash uchun).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar

import pytest

from uzlegal.index.chunker import Chunk
from uzlegal.index.store import ScoredChunk
from uzlegal.inference.echo_backend import EchoBackend
from uzlegal.types import Citation, GenerationParams, ModelSpec


class ScriptedBackend:
    """Har chaqiruvda ro'yxatdagi keyingi javobni qaytaradi.

    Ro'yxat tugasa oxirgi javob takrorlanadi — shunda "har doim yomon javob"
    holatini bitta element bilan ifodalash mumkin.
    """

    def __init__(self, responses: list[str], *, cache: Any = None) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.params: list[GenerationParams] = []
        self.cache = cache
        self.cache_calls = 0
        self.spec = ModelSpec(id="scripted", display_name="Scripted", backend="echo")

    # --- InferenceBackend protokoli --- #

    def load(self) -> None:
        return None

    def unload(self) -> None:
        return None

    @property
    def is_loaded(self) -> bool:
        return True

    def set_adapter(self, adapter_path: str | None) -> None:
        return None

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.prompts.append(prompt)
        self.params.append(params)
        index = min(len(self.prompts) - 1, len(self.responses) - 1)
        return self.responses[index]

    def stream(self, prompt: str, params: GenerationParams) -> Iterator[str]:
        yield self.generate(prompt, params)

    def make_prefix_cache(self, prefix: str) -> Any:
        self.cache_calls += 1
        return self.cache

    def memory_usage_gb(self) -> float:
        return 0.0

    @property
    def calls(self) -> int:
        return len(self.prompts)


class RoleBackend(ScriptedBackend):
    """Rolga qarab turli javob qaytaradi.

    Rolni promptdagi `=== ROL: … ===` sarlavhasidan aniqlaydi — bu agent
    qatlami qo'yadigan yagona barqaror belgi. Shu tufayli to'liq debate
    oqimini deterministik sinash mumkin.
    """

    MARKERS: ClassVar[dict[str, str]] = {
        "JURIST": "jurist",
        "ADVOKAT": "advocate",
        "PROKUROR": "prosecutor",
        "PROFESSOR": "professor",
        "SUDYA": "judge",
    }

    def __init__(self, by_role: dict[str, str], default: str = "javob yo'q") -> None:
        super().__init__([default])
        self.by_role = by_role
        self.roles: list[str] = []

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.prompts.append(prompt)
        self.params.append(params)
        role = next(
            (r for marker, r in self.MARKERS.items() if f"=== ROL: {marker} ===" in prompt),
            "?",
        )
        self.roles.append(role)
        return self.by_role.get(role, self.responses[0])


class CountingCache:
    """Nusxalanishini sanaydigan soxta KV-cache."""

    def __init__(self) -> None:
        self.copies = 0

    def copy(self) -> CountingCache:
        self.copies += 1
        return self


class StubRetriever:
    """Berilgan chunklarni o'zgartirmasdan qaytaradi — indekssiz test uchun."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.queries: list[str] = []

    def search(self, query: str, *, top_k: int = 8, as_of: Any = None, **kw: Any) -> Any:
        self.queries.append(query)
        return _Found(
            [ScoredChunk(chunk=c, score=1.0 - i / 100) for i, c in enumerate(self.chunks[:top_k])]
        )


class _Found:
    def __init__(self, results: list[ScoredChunk]) -> None:
        self.results = results


def make_chunk(chunk_id: str, content: str, **kw: Any) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=kw.pop("doc_id", "uz-mk-2022"),
        doc_title=kw.pop("doc_title", "Mehnat kodeksi"),
        doc_type="kodeks",
        lang="uz",
        article=kw.pop("article", "106"),
        heading=f"[Mehnat kodeksi > {kw.get('article', '106')}-modda]",
        content=content,
        token_count=len(content.split()) * 2,
        source_url="https://lex.uz/docs/142859#106",
        **kw,
    )


@pytest.fixture
def echo_backend() -> EchoBackend:
    backend = EchoBackend(ModelSpec(id="echo", display_name="Echo", backend="echo"))
    backend.load()
    return backend


@pytest.fixture
def chunks() -> list[Chunk]:
    return [
        make_chunk(
            "mk-106",
            "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinishi mumkin. "
            "Xodim o'z tashabbusi bilan mehnat shartnomasini bekor qilishga haqli.",
        ),
        make_chunk(
            "fk-234",
            "Mulkdor o'z mulkini boshqa shaxsning qonunsiz egaligidan talab qilishga haqli.",
            doc_id="uz-fk-1996",
            doc_title="Fuqarolik kodeksi",
            article="234",
        ),
    ]


@pytest.fixture
def citations() -> list[Citation]:
    return [
        Citation(
            tag="C1",
            doc_id="uz-mk-2022",
            doc_title="Mehnat kodeksi",
            article="106",
            excerpt="Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinishi mumkin.",
        ),
        Citation(
            tag="C2",
            doc_id="uz-fk-1996",
            doc_title="Fuqarolik kodeksi",
            article="234",
            excerpt="Mulkdor o'z mulkini qonunsiz egalikdan talab qilishga haqli.",
        ),
    ]
