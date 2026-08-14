"""Havola nazorati testlari — docs/22 § 5 (B1..B5).

Doira ataylab tor: bu **ziddiyat detektori emas**. Shuning uchun testlar
ham faqat havola yaxlitligini ushlab turadi — uch sinf to'g'ri
ajratiladimi, hisobot «nomzod» tilida gapiradimi va buzuq `refs.jsonl`
da ish to'xtaydimi.

Indeks bu yerda **soxta**: `collisions` `ArticleSource` protokoliga
tayanadi, ya'ni LanceDB va BM25 fayllarini qurmasdan ham nazoratni
tekshirish mumkin. CLI testlari esa haqiqiy `KnowledgeIndex` ni oladi,
lekin `load()` yengillashtiriladi (`yengil_indeks` fikstura).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from uzlegal.index.chunker import Chunk
from uzlegal.index.collisions import (
    ISSUE_KINDS,
    KIND_LABELS,
    RefCheckReport,
    check_references,
)
from uzlegal.index.store import KnowledgeIndex
from uzlegal.ingest.linking import Reference, ReferenceGraph


def _chunk(doc_id: str, article: str, status: str = "in_force") -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}:{article}",
        doc_id=doc_id,
        doc_title="Sinov kodeksi",
        doc_type="kodeks",
        lang="uz",
        article=article,
        heading=f"[Sinov kodeksi > {article}-modda]",
        content="Mulkdor talab qilishga haqli.",
        token_count=8,
        status=status,
    )


def _ref(
    from_article: str,
    to_doc: str | None,
    to_article: str | None,
    kind: str,
    *,
    from_doc: str = "d-1",
    text: str = "",
) -> Reference:
    return Reference(
        from_doc=from_doc,
        from_article=from_article,
        to_doc=to_doc,
        to_article=to_article,
        kind=kind,
        text=text,
    )


def _graph(refs: list[Reference]) -> ReferenceGraph:
    graph = ReferenceGraph()
    for ref in refs:
        graph.add(ref)
    return graph


class SoxtaIndeks:
    """`ArticleSource` protokolining eng kichik amalga oshirilishi."""

    def __init__(
        self,
        statuses: dict[tuple[str, str], str] | None = None,
        graph: ReferenceGraph | None = None,
    ) -> None:
        self.statuses = statuses or {}
        self.graph = graph
        self.calls = 0

    def chunks_for_article(self, doc_id: str, article: str, *, limit: int = 4) -> list[Chunk]:
        self.calls += 1
        status = self.statuses.get((doc_id, article))
        return [] if status is None else [_chunk(doc_id, article, status)]

    def article_labels(self, doc_id: str) -> list[str]:
        return sorted(article for doc, article in self.statuses if doc == doc_id)

    def reference_graph(self, *, rebuild: bool = False) -> ReferenceGraph | None:
        return self.graph


# --------------------------------------------------------------------------- #
# B1 — uch sinf
# --------------------------------------------------------------------------- #


def test_uzilgan_havola_aniqlanadi() -> None:
    """Nishon modda korpusda yo'q — eng qimmatli sinf."""
    source = SoxtaIndeks(
        statuses={("d-2", "10"): "in_force"},
        graph=_graph([_ref("1", "d-2", "999", "external", text="Mehnat kodeksi 999-moddasi")]),
    )
    report = check_references(source)

    assert report.counts["uzilgan"] == 1
    issue = report.issues[0]
    assert issue.to_node == "d-2:999"
    assert issue.to_status is None
    assert issue.text == "Mehnat kodeksi 999-moddasi"


def test_bekor_qilinganga_havola_aniqlanadi() -> None:
    """Amaldagi norma bekor qilingan moddaga tayanadi."""
    source = SoxtaIndeks(
        statuses={("d-1", "5"): "repealed"},
        graph=_graph([_ref("1", "d-1", "5", "internal")]),
    )
    report = check_references(source)

    assert report.counts["bekor"] == 1
    assert report.issues[0].to_status == "repealed"


def test_hal_qilinmagan_havola_aniqlanadi() -> None:
    """`kind = unresolved` — havola matni tanildi, nishon topilmadi."""
    source = SoxtaIndeks(graph=_graph([_ref("1", None, None, "unresolved")]))
    report = check_references(source)

    assert report.counts["hal-qilinmagan"] == 1
    assert report.issues[0].to_node is None
    assert report.issues[0].ref_kind == "unresolved"


def test_amaldagi_moddaga_havola_nomzod_bo_lmaydi() -> None:
    """Sog'lom havola hisobotga umuman tushmaydi."""
    source = SoxtaIndeks(
        statuses={("d-1", "5"): "in_force", ("d-2", "10"): "in_force"},
        graph=_graph([_ref("1", "d-1", "5", "internal"), _ref("2", "d-2", "10", "external")]),
    )
    report = check_references(source)

    assert report.candidates == 0
    assert report.counts == dict.fromkeys(ISSUE_KINDS, 0)
    assert report.references == 2
    assert report.resolvable == 2


def test_uch_sinf_bir_hisobotda_ajratiladi() -> None:
    source = SoxtaIndeks(
        statuses={("d-1", "5"): "in_force", ("d-1", "6"): "repealed"},
        graph=_graph(
            [
                _ref("1", "d-1", "5", "internal"),
                _ref("2", "d-1", "6", "internal"),
                _ref("3", "d-1", "777", "internal"),
                _ref("4", None, None, "unresolved"),
            ]
        ),
    )
    report = check_references(source)

    assert report.counts == {"uzilgan": 1, "bekor": 1, "hal-qilinmagan": 1}
    assert report.references == 4
    assert report.resolvable == 3
    assert report.ref_kinds == {"internal": 3, "unresolved": 1}


def test_nishoni_yo_q_havola_hal_qilinmagan_hisoblanadi() -> None:
    """`kind` boshqacha bo'lsa ham nishonsiz havolani izlab bo'lmaydi."""
    source = SoxtaIndeks(graph=_graph([_ref("1", "d-2", None, "external")]))
    report = check_references(source)

    assert report.counts["hal-qilinmagan"] == 1
    assert source.calls == 0


def test_birlashgan_bo_lakdagi_modda_uzilgan_deb_belgilanmaydi() -> None:
    """`_merge_tiny()` «18-19» yorlig'ini beradi — 19-modda korpusda BOR."""
    source = SoxtaIndeks(
        statuses={("d-1", "18-19"): "in_force"},
        graph=_graph([_ref("1", "d-1", "19", "internal")]),
    )
    report = check_references(source)

    assert report.candidates == 0


def test_birlashgan_bo_lakning_holati_nishonga_o_tadi() -> None:
    """Oraliq bo'lak bekor qilingan bo'lsa nomzod `bekor` sinfiga tushadi."""
    source = SoxtaIndeks(
        statuses={("d-1", "111-113"): "repealed"},
        graph=_graph([_ref("1", "d-1", "112", "internal")]),
    )
    report = check_references(source)

    assert report.counts["bekor"] == 1
    assert report.issues[0].to_status == "repealed"


def test_oraliqdan_tashqaridagi_modda_uzilgan_bo_lib_qoladi() -> None:
    source = SoxtaIndeks(
        statuses={("d-1", "18-19"): "in_force"},
        graph=_graph([_ref("1", "d-1", "20", "internal")]),
    )
    report = check_references(source)

    assert report.counts["uzilgan"] == 1


def test_tireli_nishon_raqami_oraliq_deb_kengaytirilmaydi() -> None:
    """`241-9` — haqiqiy modda raqami, oraliq emas."""
    source = SoxtaIndeks(
        statuses={("d-1", "241"): "in_force", ("d-1", "9"): "in_force"},
        graph=_graph([_ref("1", "d-1", "241-9", "internal")]),
    )
    report = check_references(source)

    assert report.counts["uzilgan"] == 1


def test_takroriy_nishon_bir_marta_izlanadi() -> None:
    """Kesh bo'lmasa 47 388 havola uchun ish kvadratik bo'lardi."""
    source = SoxtaIndeks(
        statuses={("d-1", "5"): "in_force"},
        graph=_graph([_ref(str(i), "d-1", "5", "internal") for i in range(1, 21)]),
    )
    report = check_references(source)

    assert source.calls == 1
    assert report.targets == 1
    assert report.candidates == 0


# --------------------------------------------------------------------------- #
# B3 — «nomzod» tili
# --------------------------------------------------------------------------- #


def test_sinf_izohlari_ziddiyat_deb_da_vo_qilmaydi() -> None:
    """Modul lug'atida «ziddiyat» yoki «kolliziya» so'zi bo'lmasin."""
    for label in KIND_LABELS.values():
        assert "ziddiyat" not in label.lower()
        assert "kolliziya" not in label.lower()
    assert set(KIND_LABELS) == set(ISSUE_KINDS)


# --------------------------------------------------------------------------- #
# B5 — bo'sh yoki buzuq refs.jsonl
# --------------------------------------------------------------------------- #


def test_graf_tayyor_bo_lmasa_yiqilmaydi() -> None:
    """`reference_graph()` `None` qaytarsa hisobot bo'sh, lekin xato yo'q."""
    report = check_references(SoxtaIndeks(graph=None))

    assert report.graph_ready is False
    assert report.candidates == 0
    assert report.references == 0
    assert "refs.jsonl" in report.note


def test_bo_sh_graf_nol_nomzod_beradi() -> None:
    report = check_references(SoxtaIndeks(graph=_graph([])))

    assert report.graph_ready is True
    assert report.references == 0
    assert report.share == 0.0


def test_bo_sh_refs_fayli_yiqilmaydi(tmp_path: Path) -> None:
    """Bo'sh `refs.jsonl` — nol havolali graf, istisno emas."""
    index = KnowledgeIndex(tmp_path)
    index.graph_path.write_text("", encoding="utf-8")

    report = check_references(index)

    assert report.graph_ready is True
    assert report.references == 0


def test_buzuq_refs_fayli_yiqilmaydi(tmp_path: Path) -> None:
    """Yarim yozilgan JSONL — `reference_graph()` `None` qaytaradi."""
    index = KnowledgeIndex(tmp_path)
    index.graph_path.write_text('{"from_doc": "d-1", "from_art\n', encoding="utf-8")

    report = check_references(index)

    assert report.graph_ready is False
    assert report.candidates == 0


def test_maydonlari_yetishmagan_refs_yiqilmaydi(tmp_path: Path) -> None:
    """To'g'ri JSON, lekin `Reference` maydonlari yetishmaydi."""
    index = KnowledgeIndex(tmp_path)
    index.graph_path.write_text('{"from_doc": "d-1"}\n', encoding="utf-8")

    report = check_references(index)

    assert report.graph_ready is False


# --------------------------------------------------------------------------- #
# Filtr
# --------------------------------------------------------------------------- #


def _uch_sinfli_indeks() -> SoxtaIndeks:
    return SoxtaIndeks(
        statuses={("d-1", "6"): "repealed"},
        graph=_graph(
            [
                _ref("1", "d-1", "777", "internal"),
                _ref("2", "d-1", "6", "internal"),
                _ref("3", None, None, "unresolved"),
            ]
        ),
    )


def test_kind_filtri_faqat_bir_sinfni_qoldiradi() -> None:
    report = check_references(_uch_sinfli_indeks(), kind="uzilgan")

    assert [i.kind for i in report.issues] == ["uzilgan"]
    # Tur taqsimoti filtrdan qat'i nazar to'liq qoladi — B4 o'lchovi
    # aynan shundan olinadi.
    assert report.ref_kinds == {"internal": 2, "unresolved": 1}
    assert report.references == 3


def test_noma_lum_sinf_xato_beradi() -> None:
    with pytest.raises(ValueError, match="noma'lum sinf"):
        check_references(SoxtaIndeks(graph=_graph([])), kind="kolliziya")


def test_filtered_yordamchisi_sinf_bo_yicha_ajratadi() -> None:
    report = check_references(_uch_sinfli_indeks())

    assert len(report.filtered(None)) == 3
    assert len(report.filtered("bekor")) == 1
    assert report.filtered("bekor")[0].to_status == "repealed"


def test_ulush_havolalar_soniga_nisbatan_hisoblanadi() -> None:
    report = RefCheckReport(references=4, issues=[])
    assert report.share == 0.0


# --------------------------------------------------------------------------- #
# B2 — CLI
# --------------------------------------------------------------------------- #


@pytest.fixture
def yengil_indeks(monkeypatch: pytest.MonkeyPatch) -> None:
    """`KnowledgeIndex.load()` faqat `chunks.jsonl` ni o'qisin.

    Haqiqiy `load()` LanceDB jadvalini va BM25 pikelini ochadi. Havola
    nazoratiga ularning hech biri kerak emas — faqat bo'lak
    metama'lumoti kerak, shuning uchun test ularni qurmaydi.
    """

    def _load(self: KnowledgeIndex) -> None:
        if self._chunks:
            return
        for line in self.chunks_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunk = Chunk(**json.loads(line))
                self._chunks[chunk.chunk_id] = chunk

    monkeypatch.setattr(KnowledgeIndex, "load", _load)
    monkeypatch.setattr(KnowledgeIndex, "exists", lambda self: self.chunks_path.exists())


@pytest.fixture
def indeks_yo_li(tmp_path: Path) -> Path:
    """Uchta sinfni ham beradigan kichik indeks katalogi.

    «18-19» — `_merge_tiny()` yasagan birlashgan bo'lak: 19-moddaga
    havola uzilgan deb belgilanmasligi kerak.
    """
    chunks = [_chunk("d-1", "5"), _chunk("d-1", "6", "repealed"), _chunk("d-1", "18-19")]
    (tmp_path / "chunks.jsonl").write_text(
        "\n".join(c.model_dump_json() for c in chunks), encoding="utf-8"
    )
    refs = [
        _ref("1", "d-1", "5", "internal"),
        _ref("2", "d-1", "6", "internal", text="ushbu Kodeksning 6-moddasi"),
        _ref("3", "d-1", "777", "internal", text="ushbu Kodeksning 777-moddasi"),
        _ref("4", None, None, "unresolved", text="Soliq kodeksi 12-moddasi"),
        _ref("5", "d-1", "19", "internal", text="ushbu Kodeksning 19-moddasi"),
    ]
    (tmp_path / "refs.jsonl").write_text(
        "\n".join(r.model_dump_json() for r in refs), encoding="utf-8"
    )
    return tmp_path


def _cli(*args: str) -> Any:
    from typer.testing import CliRunner

    from uzlegal.cli.main import app as cli_app

    return CliRunner().invoke(cli_app, list(args))


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_buyrug_i_uch_sinfni_ko_rsatadi(indeks_yo_li: Path) -> None:
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li))

    assert result.exit_code == 0, result.output
    for name in ISSUE_KINDS:
        assert name in result.output
    assert "Nomzodlar 3" in result.output


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_hisoboti_ziddiyat_deb_da_vo_qilmaydi(indeks_yo_li: Path) -> None:
    """B3 — chiqishda «nomzod» bor, «ziddiyat topildi» yo'q."""
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li))

    assert result.exit_code == 0
    lowered = result.output.lower()
    assert "nomzod" in lowered
    assert "ziddiyat topildi" not in lowered
    assert "kolliziya" not in lowered


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_json_chiqishi_mashina_uchun(indeks_yo_li: Path) -> None:
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["references"] == 5
    assert payload["candidates"] == 3
    assert payload["counts"] == {"uzilgan": 1, "bekor": 1, "hal-qilinmagan": 1}
    assert payload["ref_kinds"] == {"internal": 4, "unresolved": 1}
    assert payload["graph_ready"] is True
    assert {i["kind"] for i in payload["issues"]} == set(ISSUE_KINDS)


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_kind_filtri_faqat_uzilganni_qoldiradi(indeks_yo_li: Path) -> None:
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--kind", "uzilgan", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["counts"] == {"uzilgan": 1, "bekor": 0, "hal-qilinmagan": 0}
    assert [i["to_article"] for i in payload["issues"]] == ["777"]


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_birlashgan_bo_lakni_uzilgan_deb_hisoblamaydi(indeks_yo_li: Path) -> None:
    """Haqiqiy `KnowledgeIndex.article_labels()` yo'li bilan."""
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--kind", "uzilgan", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [i["to_article"] for i in payload["issues"]] == ["777"]


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_nishon_holatini_ko_rsatadi(indeks_yo_li: Path) -> None:
    """Holat rich uslub tegi deb o'qilmasin.

    `[repealed]` shaklida yozilganda rich uni noma'lum uslub deb **jimgina
    yutib yuborardi** va nomzodning eng muhim dalili chiqishdan yo'qolardi.
    """
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--kind", "bekor")

    assert result.exit_code == 0, result.output
    assert result.exception is None
    assert "repealed" in result.output


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_nol_limit_hammasini_ko_rsatadi(indeks_yo_li: Path) -> None:
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--limit", "0", "--json")

    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)["issues"]) == 3


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_noma_lum_sinfda_ikki_kod_beradi(indeks_yo_li: Path) -> None:
    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--kind", "ziddiyat")

    assert result.exit_code == 2
    assert "Noma'lum sinf" in result.output


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_indeks_yo_q_bo_lsa_tort_kod_beradi(tmp_path: Path) -> None:
    result = _cli("index", "refcheck", "--path", str(tmp_path / "yo-q"))

    assert result.exit_code == 4
    assert "Indeks yo'q" in result.output


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_buzuq_refs_da_yiqilmaydi(indeks_yo_li: Path) -> None:
    """B5 — buyruq istisno bermaydi, ogohlantirish bilan tugaydi."""
    (indeks_yo_li / "refs.jsonl").write_text("{buzuq\n", encoding="utf-8")

    result = _cli("index", "refcheck", "--path", str(indeks_yo_li))

    assert result.exit_code == 0, result.output
    assert result.exception is None
    assert "tayyorlanmadi" in result.output


@pytest.mark.usefixtures("yengil_indeks")
def test_refcheck_bo_sh_refs_da_yiqilmaydi(indeks_yo_li: Path) -> None:
    (indeks_yo_li / "refs.jsonl").write_text("", encoding="utf-8")

    result = _cli("index", "refcheck", "--path", str(indeks_yo_li), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["references"] == 0
    assert payload["candidates"] == 0
