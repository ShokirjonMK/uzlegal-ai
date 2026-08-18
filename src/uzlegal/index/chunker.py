"""Yuridik matnni bo'laklarga ajratish.

## Nima uchun oddiy chunking yaramaydi

Odatiy RAG «har 500 token» deb kesadi. Yuridik matnda bu halokatli:

    …mulkdor talab qilishga haqli, agar mulk vijdonsiz oluv[KESILDI]
    [YANGI CHUNK]chi qo'lida bo'lsa. Bundan mustasno holatlar…

Kesilgan joydan «bundan mustasno» qismi yo'qoladi va model normani
**teskari** talqin qiladi. Iqtibos ham noto'g'ri bo'ladi: chunk qaysi
moddaga tegishli ekani noaniq.

## Qoida

**Chunk chegarasi = tuzilma chegarasi.** Modda o'rtasidan hech qachon
kesilmaydi. Modda juda uzun bo'lsa — qismlarga, keyin bandlarga bo'linadi,
lekin har doim to'liq mantiqiy birlik saqlanadi.

| Modda hajmi | Strategiya |
|-------------|------------|
| < 800 token | Bitta chunk = bitta modda |
| 800–2000 | Qismlarga (1., 2., …) |
| > 2000 | Bandlarga (a), b), …) |
| < 100 token | Qo'shni moddalar bilan birlashtiriladi (bir bob ichida) |

## Kontekstual sarlavha

Har bir chunk o'z o'rnini biladigan sarlavha oladi:

    [Fuqarolik kodeksi > II bo'lim > 11-bob > 234-modda > 1-qism]

Bu retrieval sifatini sezilarli oshiradi — model chunk qayerdan kelganini
ko'radi va iqtibosni to'g'ri shakllantiradi.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import fold
from uzlegal.ingest.types import Element, ParsedDocument, unit_label

# Chegara qiymatlari — docs/03 § 3.6
MAX_CHUNK_TOKENS = 800
SPLIT_TO_PARTS_ABOVE = 800
SPLIT_TO_ITEMS_ABOVE = 2000
MERGE_BELOW_TOKENS = 100
MIN_CHUNK_CHARS = 20

# Embedding modeli sig'dira oladigan eng katta chunk.
#
# NEGA BU CHEGARA KERAK. Quyida «bo'linmasa uzun bo'lsa ham butun
# qoldiramiz — to'liqlik uzunlikdan muhimroq» degan qoida bor va u
# to'g'ri. Lekin uning oqibati hisobga olinmagan edi: BGE-M3 ning
# oynasi 8192 token va u undan uzun matnni **jimgina kesib tashlaydi**.
#
# Amalda o'lchandi (20 kodeks, 8 631 chunk): eng katta chunk 63 888
# belgi ≈ 18 000 token. Ya'ni o'sha moddaning matnidan ~60% embeddingga
# umuman tushmagan va qidiruvda ko'rinmas bo'lib qolgan. «To'liqlik»
# maqsadi aynan shu joyda o'z aksiga aylanadi.
#
# Ustiga bu tezlikni ham buzadi: e'tibor mexanizmi O(n²), va 8 GB
# VRAM da bitta uzun to'plam butun indekslashni soatlarga cho'zadi
# (o'lchandi: 8 631 chunk 4 daqiqa o'rniga 77+ daqiqa).
#
# 6000 token — 8192 lik oynadan xavfsizlik zaxirasi bilan pastda
# (sarlavha va maxsus tokenlar ham joy oladi).
HARD_MAX_TOKENS = 6000

# Belgi bo'yicha ikkinchi chegara.
#
# NEGA IKKITA CHEGARA. `estimate_tokens()` = so'zlar × 2 — bu **taxmin**,
# va u matn zichligiga bog'liq. Jadval yoki ro'yxatga o'xshash matnda
# bo'sh joy kam bo'ladi, so'z soni past chiqadi va taxmin haqiqiy token
# sonidan ikki barobar past bo'lishi mumkin. Amalda ko'rildi: faqat
# token taxminiga tayanganda 63 888 belgilik matn ikkita 27 000 belgilik
# bo'lakka bo'lindi — ikkalasi ham baribir oynadan oshib ketardi.
#
# Belgi soni esa aniq o'lchanadi. O'zbek va rus matnida BGE-M3 uchun
# taxminan 3 belgi = 1 token, ya'ni 15 000 belgi ≈ 5 000 token —
# ishonchli zaxira bilan oyna ichida.
HARD_MAX_CHARS = 15_000


def _oversized(text: str) -> bool:
    """Matn embedding oynasiga sig'maydimi — ikkala mezon bo'yicha."""
    return estimate_tokens(text) > HARD_MAX_TOKENS or len(text) > HARD_MAX_CHARS


# Ketma-ket bo'laklar orasidagi ustma-ustlik — chegarada qolgan gap
# ikkala bo'lakda ham ko'rinsin. Busiz «bundan mustasno» kabi
# davomlar chegaraga tushib qolsa ma'no teskarisiga o'zgaradi.
SPLIT_OVERLAP_TOKENS = 100

# O'zbek/rus matnida token ≈ so'z × 2 (agglyutinatsiya va kirill tufayli)
TOKENS_PER_WORD = 2


def estimate_tokens(text: str) -> int:
    return len(text.split()) * TOKENS_PER_WORD


# --------------------------------------------------------------------------- #
# Qism va band chegaralari
# --------------------------------------------------------------------------- #

# "1. Matn…"  yoki  "1) Matn…"
_PART_RE = re.compile(r"(?m)^\s*(\d{1,2})\s*[.)]\s+")

# "a) matn…"  yoki  "а) matn…" (kirill a)
_ITEM_RE = re.compile(r"(?m)^\s*([a-zа-яʻʼ]{1,2})\s*\)\s+")


# Gap chegarasi — nuqta, undov, so'roq va yangi qatordan keyin.
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+|\n+")


def _split_oversized(text: str) -> list[str]:
    """Embedding oynasiga sig'maydigan matnni gap chegarasida bo'ladi.

    Matn chegaradan pastda bo'lsa — **o'sha obyektning o'zi** qaytadi
    (nusxa emas). Chaqiruvchi shunga qarab bo'lak raqami qo'shish
    kerak-kerakmasligini biladi va oddiy holatda `chunk_id` o'zgarmaydi.

    Bo'lish qoidalari:

    * chegara faqat **gap oxirida** — norma o'rtasidan hech qachon;
    * qo'shni bo'laklar `SPLIT_OVERLAP_TOKENS` cha ustma-ust keladi,
      shunda chegaraga tushgan shart («…bundan mustasno…») ikkala
      bo'lakda ham qoladi;
    * bitta gapning o'zi chegaradan uzun bo'lsa u **kesilmaydi** —
      bunday gap yuridik matnda deyarli uchramaydi va uni kesish
      ma'noni buzardi.
    """
    if not _oversized(text):
        return [text]

    sentences = [s for s in _SENTENCE_RE.split(text) if s.strip()]
    if len(sentences) <= 1:
        return [text]

    pieces: list[str] = []
    current: list[str] = []

    for sentence in sentences:
        if current and _oversized(" ".join([*current, sentence])):
            pieces.append(" ".join(current))
            current = _tail(current, SPLIT_OVERLAP_TOKENS)
        current.append(sentence)

    if current:
        pieces.append(" ".join(current))
    return pieces


def _tail(sentences: list[str], max_tokens: int) -> list[str]:
    """Ustma-ustlik uchun oxirgi gaplar.

    Byudjet **ikkala mezon** bo'yicha cheklanadi — bo'lishning o'zidagi
    kabi. Faqat token bo'yicha cheklansa zich matnda ustma-ustlikning
    o'zi chegaradan oshib ketardi: bir «gap» 300 belgi, lekin atigi
    2 token bo'lsa, 100 tokenlik byudjetga 50 ta gap ≈ 15 000 belgi
    sig'adi va keyingi bo'lak boshlanishidayoq to'lib bo'ladi.

    Hech bo'lmasa bitta gap qaytmasligi mumkin: oxirgi gapning o'zi
    byudjetdan katta bo'lsa bo'sh ro'yxat qaytadi va keyingi bo'lak
    ustma-ustliksiz boshlanadi. Bu to'g'ri — aks holda bitta ulkan gap
    har bo'lakda takrorlanib, bo'lish umuman yaqinlashmasdi.
    """
    max_chars = HARD_MAX_CHARS // 10
    kept: list[str] = []
    tokens = 0
    chars = 0
    for sentence in reversed(sentences):
        tokens += estimate_tokens(sentence)
        chars += len(sentence) + 1
        if tokens > max_tokens or chars > max_chars:
            break
        kept.insert(0, sentence)
    return kept


def _enforce_limit(chunks: list[Chunk]) -> list[Chunk]:
    """Chegarani **chiqish nuqtasida** kafolatlaydi.

    ## Nima uchun bu yerda, tarmoqlarda emas

    Birinchi urinishda chegara `_chunk_article()` ning ikkita tarmogʻiga
    qoʻyilgan edi. Lekin chunk yaratadigan yoʻl **beshta**:

    1. kichik modda — butunligicha (chegara YOʻQ edi)
    2. qismlarga boʻlish (chegara YOʻQ edi)
    3. qism → `_split_oversized` ✓
    4. band → `_split_oversized` ✓
    5. `_merge_tiny()` — ikki chunkni **qoʻshadi**, yaʼni yangi
       chegaradan oshgan chunk yasashi mumkin

    Amalda oʻlchandi (863 hujjat): eng uzun chunk **48 561 belgi**
    boʻlib chiqdi — chegaradan uch barobar katta. Natijada indeks
    qurish yana 195 daqiqaga choʻzildi va tugamadi.

    Har tarmoqqa alohida tekshiruv qoʻyish — unutib boʻladigan
    yondashuv. Bitta chiqish nuqtasida kafolat berish esa yangi tarmoq
    qoʻshilganda ham ishlaydi.

    Faqat oshib ketganlarga tegadi: qolgan chunklar **oʻsha obyektning
    oʻzi** boʻlib qoladi.
    """
    out: list[Chunk] = []
    for chunk in chunks:
        pieces = _split_oversized(chunk.content)
        if len(pieces) == 1:
            out.append(chunk)
            continue
        for i, piece in enumerate(pieces, start=1):
            out.append(
                chunk.model_copy(
                    update={
                        "chunk_id": f"{chunk.chunk_id}:{i}",
                        "content": piece,
                        "token_count": estimate_tokens(piece),
                    }
                )
            )
    return out


DUP_SUFFIX = "#"


def _enforce_unique_ids(chunks: list[Chunk]) -> list[Chunk]:
    """`chunk_id` noyobligini **chiqish nuqtasida** kafolatlaydi.

    ## Nima uchun kerak edi

    `store.load()` bo'laklarni `chunk_id` bo'yicha lug'atga yig'adi —
    takrorlangan identifikator ustiga jimgina yoziladi. Amalda
    o'lchandi (2026-08-14, 792 hujjat): 48 527 satrdan noyob
    identifikator atigi **35 708** ta, ya'ni 4 484 identifikator
    12 819 satrni bosib ketardi.

    Yo'qotishning o'zi ham yomon, lekin asosiy zarar boshqa joyda.
    Vektor jadvali ham, BM25 ham **hamma** 48 527 satr uchun
    quriladi. Qidiruv birinchi nusxaning matniga ball beradi, keyin
    `store.py:411` va `:472` o'sha identifikatorni lug'atdan
    qidiradi va **oxirgi nusxaning matnini** qaytaradi. Foydalanuvchi
    haqiqiy `source_url` bilan **boshqa normaning matnini** ko'radi.
    Iqtibosga asoslangan tizimda bu yo'qotishdan og'irroq.

    ## Nima uchun bu yerda, tarmoqlarda emas

    `_enforce_limit()` bilan bir xil sabab. Identifikator yasaydigan
    yo'l **oltita** va ularning har biri o'zicha to'qnashadi:

    1. kichik modda — `{doc}:{num}`. Ikki element bir xil
       `article_number` olsa to'qnashadi: «244-3-modda» dan parser
       `3` ni ajratadi va u haqiqiy 3-modda bilan urishadi (3 794 satr)
    2. qismlarga bo'lish — `{doc}:{num}:{mark}`. Bitta modda ichida
       `1.` `2.` raqamlash qayta-qayta boshlanadi: davlat dasturida
       `-6811936:35:2` **187 marta** uchradi (8 668 satr)
    3. band — `{doc}:{num}:{mark}:{item}`. Bir qismda `a) b) … a)`
       ro'yxati qaytadan boshlanadi (225 satr)
    5. `_merge_tiny()` — `{first}+{n}`, to'qnashuvni birinchi
       bo'lakdan meros oladi (132 satr)

    Qolgan ikkitasi — `_split_oversized()` va `_enforce_limit()` —
    tayyor identifikatorga `:{piece_no}` qo'shadi. Ular o'z-o'zicha
    to'qnashuv yasagani korpusda **o'lchanmagan**, lekin ular
    yuqoridagilardan **keyin** ishlaydi va bo'lingan har bir parcha
    to'qnashuvni meros oladi. Shuning uchun kafolat ham eng oxirida
    turadi: undan keyin identifikatorga hech kim tegmaydi.

    Har tarmoqqa alohida tekshiruv qo'yish — unutib bo'ladigan
    yondashuv. Shuning uchun kafolat `_enforce_limit()` dan **keyin**
    turadi: undan keyin hech kim identifikatorga tegmaydi.

    ## Nima uchun aynan tartib raqami

    Birinchi uchragan bo'lak identifikatorini **o'zgarishsiz**
    saqlaydi, keyingilariga `#2`, `#3` qo'shiladi. Ya'ni to'qnashmagan
    35 708 identifikator (korpusning 92%) o'z qiymatida qoladi —
    audit jurnalidagi va imzolangan pasportlardagi eski havolalar
    ishlashda davom etadi. `#` belgisi korpusda umuman uchramaydi
    (o'lchandi: 0 ta identifikator).

    Tartib hujjat ichidagi bo'lak tartibiga bog'liq, u esa parser
    chiqishi bilan bir xil — bir xil kirishdan bir xil identifikator
    chiqadi.

    ## Nima QILINMAYDI

    Bu funksiya to'qnashuvning **sababini** tuzatmaydi. «244-3-modda»
    dan `3` ajratilishi parserning alohida nuqsoni va u metama'lumot
    sifatiga ta'sir qiladi (`chunks_for_article()` noto'g'ri modda
    qaytaradi). U alohida ish sifatida qayd etilgan — bu yerda faqat
    **jimgina yo'qotish** to'xtatiladi.
    """
    seen: dict[str, int] = {}
    out: list[Chunk] = []
    for chunk in chunks:
        count = seen.get(chunk.chunk_id, 0) + 1
        seen[chunk.chunk_id] = count
        if count == 1:
            out.append(chunk)
            continue
        out.append(chunk.model_copy(update={"chunk_id": f"{chunk.chunk_id}{DUP_SUFFIX}{count}"}))
    return out


def split_by(pattern: re.Pattern[str], text: str) -> list[tuple[str | None, str]]:
    """Matnni belgilangan raqamlash bo'yicha bo'ladi.

    `(belgi, matn)` juftliklari qaytadi. Birinchi bo'lakda belgi bo'lmasligi
    mumkin (raqamlashdan oldingi kirish matni) — u `None` bilan keladi.
    """
    marks = list(pattern.finditer(text))
    if not marks:
        return [(None, text)]

    out: list[tuple[str | None, str]] = []
    if marks[0].start() > 0:
        head = text[: marks[0].start()].strip()
        if head:
            out.append((None, head))

    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.start() : end].strip()
        if body:
            out.append((m.group(1), body))
    return out


# --------------------------------------------------------------------------- #
# Chunk
# --------------------------------------------------------------------------- #


class Chunk(BaseModel):
    """Indekslanadigan eng kichik birlik."""

    chunk_id: str
    doc_id: str
    doc_title: str
    doc_type: str
    lang: str

    article: str | None = None
    part: str | None = None
    item: str | None = None
    hierarchy: list[str] = Field(default_factory=list)

    heading: str = Field(description="Kontekstual sarlavha — modelga beriladi")
    content: str
    token_count: int = 0

    element_id: str | None = None
    source_url: str | None = None
    kind: Literal["article", "part", "item", "merged", "text"] = "article"

    # Versiyalash — Faza 1 ning versioning moduli to'ldiradi
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "in_force"

    @property
    def indexed_text(self) -> str:
        """Embedding va BM25 uchun matn — sarlavha bilan birga.

        Sarlavhani qo'shish muhim: «234-modda» so'rovi chunk matnida
        uchramasligi mumkin, lekin sarlavhada bor.
        """
        return f"{self.heading}\n\n{self.content}"

    @property
    def search_text(self) -> str:
        """BM25 uchun normallashtirilgan shakl (apostrof, kirill)."""
        return fold(self.indexed_text)

    @property
    def citation_label(self) -> str:
        bits = [self.doc_title]
        if self.article:
            bits.append(f"{self.article}-{unit_label(self.doc_type)}")
        if self.part:
            bits.append(f"{self.part}-qism")
        if self.item:
            bits.append(f'"{self.item}" bandi')
        return ", ".join(bits)


# --------------------------------------------------------------------------- #
# Chunker
# --------------------------------------------------------------------------- #


class Chunker:
    def __init__(
        self,
        max_tokens: int = MAX_CHUNK_TOKENS,
        merge_below: int = MERGE_BELOW_TOKENS,
        *,
        today: date | None = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.merge_below = merge_below
        # `today` faqat testlar uchun qotiriladi — `_document_valid_from()`
        # kelajak sanani shu chegaraga qarab rad etadi.
        self.today = today

    def chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        for article in doc.articles:
            chunks.extend(self._chunk_article(doc, article))
        return _enforce_unique_ids(_enforce_limit(self._merge_tiny(chunks)))

    # ------------------------------------------------------------------ #

    def _heading(self, doc: ParsedDocument, article: Element, *suffix: str) -> str:
        bits = [doc.title, *article.path, article.title, *suffix]
        return "[" + " > ".join(b.strip() for b in bits if b and b.strip()) + "]"

    def _document_valid_from(self, doc: ParsedDocument) -> str | None:
        """Hujjatning qabul sanasi — moddada sana bo'lmaganda ishlatiladi.

        Moddaning `valid_from` i faqat tahrir izohlaridan to'ladi
        (`ingest.versioning`), izohsiz hujjatda esa umuman bo'lmaydi.
        Natijada bo'lakning 74.5% ida sana yo'q edi va vaqt mashinasi
        ular ustida ishlamasdi (docs/22 § 1.1).

        **Kelajakdagi sana qaytarilmaydi.** `retrieval/hybrid.py` dagi
        `version_filter` `valid_from > bugun` bo'lgan bo'lakni chiqarib
        tashlaydi, ya'ni kelajak sanali hujjat barcha so'rovlardan
        jimgina yo'qolardi. `versioning._apply_edition` xuddi shu
        tuzoqni biladi va bunday sanani `pending_from` ga qo'yadi —
        bu yerda ham sana shunchaki yozilmaydi (docs/22 § 1.4).
        """
        adopted = doc.adopted_at
        if not adopted:
            return None
        today = (self.today or date.today()).isoformat()
        return adopted if adopted <= today else None

    def _base(self, doc: ParsedDocument, article: Element) -> dict[str, object]:
        return {
            "doc_id": doc.doc_id,
            "doc_title": doc.title,
            "doc_type": doc.doc_type,
            "lang": doc.lang,
            "article": article.article_number,
            "hierarchy": list(article.path),
            "element_id": article.element_id,
            "source_url": f"{doc.url}#{article.element_id}",
            # Versiya maydonlari `ingest.versioning.apply_versions()` dan keladi.
            # Ular bo'lmasa `version_filter` bo'sh ishlaydi va bekor qilingan
            # norma qidiruvga chiqib ketadi (docs/00 «0% deprecated»).
            # Modda sanasi bo'lmasa — hujjatning qabul sanasiga tushamiz.
            "valid_from": article.valid_from or self._document_valid_from(doc),
            "valid_to": article.valid_to,
            "status": article.status,
        }

    def _chunk_article(self, doc: ParsedDocument, article: Element) -> list[Chunk]:
        body = article.body.strip()
        if len(body) < MIN_CHUNK_CHARS:
            return []

        tokens = estimate_tokens(body)
        base = self._base(doc, article)
        num = article.article_number or article.element_id

        # 1. Kichik modda — butunligicha
        if tokens <= SPLIT_TO_PARTS_ABOVE:
            return [
                Chunk(
                    chunk_id=f"{doc.doc_id}:{num}",
                    heading=self._heading(doc, article),
                    content=body,
                    token_count=tokens,
                    kind="article",
                    **base,  # type: ignore[arg-type]
                )
            ]

        # 2. O'rta modda — qismlarga
        parts = split_by(_PART_RE, body)
        if len(parts) > 1 and tokens <= SPLIT_TO_ITEMS_ABOVE:
            return [
                Chunk(
                    chunk_id=f"{doc.doc_id}:{num}:{mark or 'kirish'}",
                    part=mark,
                    heading=self._heading(doc, article, f"{mark}-qism" if mark else "kirish"),
                    content=text,
                    token_count=estimate_tokens(text),
                    kind="part",
                    **base,  # type: ignore[arg-type]
                )
                for mark, text in parts
            ]

        # 3. Katta modda — qism, keyin band
        out: list[Chunk] = []
        for mark, part_text in parts:
            if estimate_tokens(part_text) <= self.max_tokens:
                out.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:{num}:{mark or 'kirish'}",
                        part=mark,
                        heading=self._heading(doc, article, f"{mark}-qism" if mark else "kirish"),
                        content=part_text,
                        token_count=estimate_tokens(part_text),
                        kind="part",
                        **base,  # type: ignore[arg-type]
                    )
                )
                continue

            items = split_by(_ITEM_RE, part_text)
            if len(items) == 1:
                # Band bo'yicha bo'linmaydi. Uzun bo'lsa ham butun
                # qoldiramiz — yuridik matnda to'liqlik uzunlikdan
                # muhimroq. LEKIN embedding oynasidan oshib ketsa
                # «butun qoldirish» ma'nosini yo'qotadi: model matnning
                # oxirini jimgina kesib tashlaydi va u qidiruvda umuman
                # ko'rinmaydi. Shunday holatda ustma-ustlik bilan
                # bo'lamiz — kesilgan matndan ko'ra ustma-ust matn
                # yaxshiroq.
                heading = self._heading(doc, article, f"{mark}-qism" if mark else "kirish")
                for piece_no, piece in enumerate(_split_oversized(part_text), start=1):
                    total = f":{piece_no}" if piece_no > 1 or piece is not part_text else ""
                    out.append(
                        Chunk(
                            chunk_id=f"{doc.doc_id}:{num}:{mark or 'kirish'}{total}",
                            part=mark,
                            heading=heading,
                            content=piece,
                            token_count=estimate_tokens(piece),
                            kind="part",
                            **base,  # type: ignore[arg-type]
                        )
                    )
                continue

            for item_mark, item_text in items:
                suffix = [f"{mark}-qism"] if mark else []
                if item_mark:
                    suffix.append(f'"{item_mark}" bandi')
                heading = self._heading(doc, article, *suffix)
                for piece_no, piece in enumerate(_split_oversized(item_text), start=1):
                    total = f":{piece_no}" if piece_no > 1 or piece is not item_text else ""
                    out.append(
                        Chunk(
                            chunk_id=(
                                f"{doc.doc_id}:{num}:{mark or '0'}:{item_mark or 'kirish'}{total}"
                            ),
                            part=mark,
                            item=item_mark,
                            heading=heading,
                            content=piece,
                            token_count=estimate_tokens(piece),
                            kind="item",
                            **base,  # type: ignore[arg-type]
                        )
                    )
        return out

    # ------------------------------------------------------------------ #

    def _merge_tiny(self, chunks: list[Chunk]) -> list[Chunk]:
        """Juda qisqa moddalarni qo'shnisi bilan birlashtiradi.

        «234-modda. Bekor qilingan.» kabi chunklar alohida indekslansa
        qidiruvni ifloslaydi — ular ma'no tashimaydi, lekin ball oladi.

        Birlashtirish faqat **bir bob ichida** va **bir hujjatda** bo'ladi.
        """
        if not chunks:
            return []

        out: list[Chunk] = []
        buffer: list[Chunk] = []

        def flush() -> None:
            if not buffer:
                return
            if len(buffer) == 1:
                out.append(buffer[0])
            else:
                first, last = buffer[0], buffer[-1]
                merged = Chunk(
                    chunk_id=f"{first.chunk_id}+{len(buffer)}",
                    doc_id=first.doc_id,
                    doc_title=first.doc_title,
                    doc_type=first.doc_type,
                    lang=first.lang,
                    article=f"{first.article}-{last.article}",
                    hierarchy=first.hierarchy,
                    heading=first.heading,
                    content="\n\n".join(c.content for c in buffer),
                    token_count=sum(c.token_count for c in buffer),
                    element_id=first.element_id,
                    source_url=first.source_url,
                    kind="merged",
                    valid_from=first.valid_from,
                    valid_to=first.valid_to,
                    status=first.status,
                )
                out.append(merged)
            buffer.clear()

        for chunk in chunks:
            tiny = chunk.token_count < self.merge_below and chunk.kind == "article"
            if not tiny:
                flush()
                out.append(chunk)
                continue

            # Versiyasi boshqacha bo'lgan moddalar birlashtirilmaydi: bekor
            # qilingan norma amaldagisi bilan bir chunkka tushsa, versiya
            # filtri ikkalasini ham chiqarib yuboradi yoki ikkalasini ham
            # o'tkazib yuboradi — ikkalasi ham noto'g'ri.
            same_group = (
                buffer
                and buffer[-1].doc_id == chunk.doc_id
                and buffer[-1].hierarchy == chunk.hierarchy
                and (buffer[-1].valid_from, buffer[-1].valid_to, buffer[-1].status)
                == (chunk.valid_from, chunk.valid_to, chunk.status)
            )
            if buffer and not same_group:
                flush()
            buffer.append(chunk)

        flush()
        return out
