"""Validatsiya — docs/03 § 3.8.

Quvurning oxirgi darvozasi. Bu yerdan o'tmagan narsa indeksga tushmaydi.

| Tekshiruv | Muvaffaqiyatsizlik → |
|-----------|---------------------|
| `article` maydoni bo'sh emas | karantin |
| `hierarchy` izchil (bob hujjatda mavjud) | karantin |
| `valid_from` ≤ bugun, sanalar mantiqiy | karantin |
| Matn uzunligi > 20 belgi | tashlab yuborish |
| Kirill qoldig'i yo'q | ogohlantirish |
| Apostroflar kanonik | avtomatik tuzatish |
| PII detektori toza | karantin |
| Konsolidatsiyalangan versiya bilan mos | karantin |

## Nima uchun kod muhim, daraja emas

`ValidationIssue.severity` faqat «xato / ogohlantirish» ni ajratadi, lekin
jadvalda **uch xil harakat** bor: karantin, tashlab yuborish va avtomatik
tuzatish. Ular kod bo'yicha aniqlanadi — `QUARANTINE_CODES`, `DROP_CODES`,
`AUTOFIX_CODES`. Chaqiruvchi shu to'plamlarga qarab qaror qabul qiladi.

## Bajarilmaydigan tekshiruv

Jadvaldagi «konsolidatsiyalangan versiya bilan mos» tekshiruvi uchun
mustaqil ikkinchi manba kerak (o'zgartiruvchi hujjatni qo'llab, natijani
lex.uz matni bilan solishtirish). Hozircha o'zgartiruvchi hujjatlar
yig'ilmagan, shuning uchun uning o'rniga **kuzatilishi mumkin** bo'lgan
belgilar tekshiriladi: bekor qilingan modda matnda qolib ketganmi va
tahrir izohi qaysi moddaga tegishli ekani mos keladimi.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import cyrillic_ratio, fold
from uzlegal.ingest.redact import detect_pii
from uzlegal.ingest.types import ParsedDocument, ValidationIssue
from uzlegal.ingest.versioning import build_versions

log = logging.getLogger(__name__)

MIN_BODY_CHARS = 20
MAX_CYRILLIC_RATIO = 0.02

# Harakat kodlar bo'yicha aniqlanadi (modul docstringiga qarang)
QUARANTINE_CODES = {
    "modda_raqami_yoq",
    "modda_takrorlanadi",
    "ierarxiya_nomuvofiq",
    "sana_kelajakda",
    "sana_mantiqsiz",
    "pii_topildi",
    "bekor_qilingan_matnda",
}
DROP_CODES = {"matn_qisqa"}
AUTOFIX_CODES = {"apostrof_nokanonik"}

# Kanonik bo'lmagan apostrof variantlari (normalize.canonical ularni tuzatadi)
_NON_CANONICAL_APOS = re.compile(r"['‘’`´′]")


class ValidationSummary(BaseModel):
    """Bir necha hujjat bo'yicha yig'ma natija."""

    documents: int = 0
    articles: int = 0
    issues: list[ValidationIssue] = Field(default_factory=list)
    quarantined: list[str] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def quarantine_rate(self) -> float:
        """docs/03 § 5 maqsadi: ≤ 5%."""
        return len(self.quarantined) / self.articles if self.articles else 0.0

    def by_code(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.code] = counts.get(issue.code, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def validate_document(
    doc: ParsedDocument, *, today: date | None = None, check_pii: bool = True
) -> list[ValidationIssue]:
    """Hujjatni tekshiradi. Bo'sh ro'yxat — hammasi joyida."""
    issues: list[ValidationIssue] = []
    now = (today or date.today()).isoformat()

    # Taqqoslash `fold()` shaklida: `Element.path` xom sarlavhani saqlaydi,
    # sarlavha elementining `title` si esa kanonik shaklda — to'g'ridan-to'g'ri
    # tenglashtirish butun hujjatni yolg'on «nomuvofiq» deb belgilardi.
    headers = {fold(e.title) for e in doc.elements if e.level != "article"}
    seen: dict[str, str] = {}

    for element in doc.articles:
        eid = element.element_id
        number = element.article_number

        if not number:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="modda_raqami_yoq",
                    message=f"Modda raqami yo'q: {element.title[:60]!r}",
                    element_id=eid,
                )
            )
        elif number in seen:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="modda_takrorlanadi",
                    message=f"{number}-modda ikki marta uchradi (avvalgisi {seen[number]})",
                    element_id=eid,
                )
            )
        else:
            seen[number] = eid

        # Ierarxiya yo'lidagi har bir bo'g'in hujjatda haqiqatan bormi
        for step in element.path:
            if fold(step) not in headers:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="ierarxiya_nomuvofiq",
                        message=f"Ierarxiya bo'g'ini hujjatda topilmadi: {step[:50]!r}",
                        element_id=eid,
                    )
                )
                break

        issues += _check_dates(element.valid_from, element.valid_to, now, eid)

        if len(element.body.strip()) < MIN_BODY_CHARS:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="matn_qisqa",
                    message=f"{number or eid}: matn {len(element.body.strip())} belgi "
                    f"(kamida {MIN_BODY_CHARS})",
                    element_id=eid,
                )
            )
            continue

        if doc.lang == "uz" and cyrillic_ratio(element.body) > MAX_CYRILLIC_RATIO:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="kirill_qoldigi",
                    message=f"{number or eid}: kirill qoldig'i "
                    f"({cyrillic_ratio(element.body):.0%}) — transliteratsiya ishlamagan",
                    element_id=eid,
                )
            )

        if _NON_CANONICAL_APOS.search(element.body):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="apostrof_nokanonik",
                    message=f"{number or eid}: kanonik bo'lmagan apostrof — canonical() qayta ishlasin",
                    element_id=eid,
                )
            )

        if check_pii and (found := detect_pii(element.body)):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="pii_topildi",
                    message=f"{number or eid}: {len(found)} ta PII nomzodi "
                    f"({found[0].category}: {found[0].original[:30]!r})",
                    element_id=eid,
                )
            )

    issues += _check_consolidation(doc, today=today)
    return issues


def _check_dates(
    valid_from: str | None, valid_to: str | None, now: str, element_id: str
) -> list[ValidationIssue]:
    """Sanalar mantiqiy va kelajakda emasligini tekshiradi.

    Kelajakdagi `valid_from` — jimgina nosozlik: modda amalda, lekin versiya
    filtri uni qidiruvdan chiqarib yuboradi va foydalanuvchi «norma yo'q»
    degan javob oladi.
    """
    issues: list[ValidationIssue] = []
    if valid_from and valid_from > now:
        issues.append(
            ValidationIssue(
                severity="error",
                code="sana_kelajakda",
                message=f"valid_from kelajakda: {valid_from}",
                element_id=element_id,
            )
        )
    if valid_from and valid_to and valid_from >= valid_to:
        issues.append(
            ValidationIssue(
                severity="error",
                code="sana_mantiqsiz",
                message=f"valid_from ({valid_from}) ≥ valid_to ({valid_to})",
                element_id=element_id,
            )
        )
    return issues


def _check_consolidation(doc: ParsedDocument, *, today: date | None) -> list[ValidationIssue]:
    """Bekor qilingan modda konsolidatsiyalangan matnda qolib ketganmi.

    lex.uz bekor qilingan moddani matndan olib tashlaydi. Agar izoh moddani
    bekor qilingan desa-yu, matnda u hali turgan bo'lsa — yo izoh noto'g'ri
    o'qilgan, yo matn eskirgan. Ikkalasi ham qo'lda ko'rib chiqishni talab
    qiladi.
    """
    report = build_versions(doc, today=today)
    present = {a.article_number: a for a in doc.articles if a.article_number}
    issues: list[ValidationIssue] = []

    for number, version in report.versions.items():
        element = present.get(number)
        if element is None or version.status != "repealed":
            continue
        issues.append(
            ValidationIssue(
                severity="error",
                code="bekor_qilingan_matnda",
                message=f"{number}-modda {version.valid_to} da bekor qilingan, "
                f"lekin matnda turibdi",
                element_id=element.element_id,
            )
        )
    return issues


def validate_documents(
    docs: list[ParsedDocument], *, today: date | None = None, check_pii: bool = True
) -> ValidationSummary:
    """Bir necha hujjatni tekshirib, yig'ma hisobot qaytaradi."""
    summary = ValidationSummary(documents=len(docs))
    for doc in docs:
        summary.articles += len(doc.articles)
        for issue in validate_document(doc, today=today, check_pii=check_pii):
            summary.issues.append(issue)
            key = f"{doc.doc_id}:{issue.element_id}"
            if issue.code in QUARANTINE_CODES and key not in summary.quarantined:
                summary.quarantined.append(key)
            elif issue.code in DROP_CODES and key not in summary.dropped:
                summary.dropped.append(key)
    return summary
