"""Ma'lumot quvuri strukturalari."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["kodeks", "qonun", "PF", "PQ", "VMQ", "plenum", "qaror", "boshqa"]


class DocumentRef(BaseModel):
    """Kashfiyot bosqichida topilgan hujjat havolasi."""

    source: str
    doc_id: str
    url: str
    title: str | None = None
    doc_type: DocType = "boshqa"


class RawDocument(BaseModel):
    """Yuklab olingan xom hujjat — **o'zgarmas arxiv**.

    Parser mantiqi yaxshilanganda butun quvur shu arxivdan qayta ishga
    tushiriladi. Shuning uchun bu yozuv hech qachon tahrirlanmaydi.
    """

    source: str
    doc_id: str
    url: str
    fetched_at: datetime
    content_sha256: str
    http_status: int
    content_type: str
    content: str = Field(repr=False)

    @property
    def size_kb(self) -> float:
        return len(self.content.encode("utf-8")) / 1024


class AmendmentNote(BaseModel):
    """Modda matniga kiritilgan o'zgartirish eslatmasi.

    lex.uz bunday eslatmalarni matn ichida beradi:

        "Обратите внимание: в статью 53 внесены изменения Законом от …"

    Bu versiyalash uchun asosiy signal — qaysi modda qachon va qaysi hujjat
    bilan o'zgartirilgani shu yerdan olinadi.
    """

    element_id: str
    raw_text: str
    target_article: str | None = None
    amending_doc: str | None = None
    effective_date: str | None = None


class Element(BaseModel):
    """Hujjatning bitta strukturaviy elementi."""

    element_id: str = Field(description="lex.uz ichki ID")
    level: Literal[
        "document", "part", "section", "subsection", "chapter", "article", "text", "amendment"
    ]
    title: str
    body: str = ""
    article_number: str | None = None
    lang: Literal["uz", "ru"] = "uz"
    path: list[str] = Field(default_factory=list, description="Ierarxiya yo'li")
    amendments: list[AmendmentNote] = Field(default_factory=list)

    @property
    def token_estimate(self) -> int:
        return len(self.body.split()) * 2  # o'zbek tili uchun taxminiy


class ParsedDocument(BaseModel):
    doc_id: str
    source: str
    url: str
    title: str
    doc_type: DocType = "boshqa"
    lang: Literal["uz", "ru"] = "uz"
    adopted_at: str | None = None
    elements: list[Element] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    amendments: list[AmendmentNote] = Field(default_factory=list)

    @property
    def articles(self) -> list[Element]:
        return [e for e in self.elements if e.level == "article"]

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.elements:
            counts[e.level] = counts.get(e.level, 0) + 1
        return counts


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    element_id: str | None = None
