"""Oʻzbekiston qonunchiligi boʻyicha oʻquv dasturi — fanlar va mavzular.

MUHIM QAROR: bu yerda **modda raqamlari yozilmagan**.

Vasvasa aniq edi: har mavzuga «Fuqarolik kodeksining 234-moddasi» deb
yozib qoʻyish. Lekin bu raqamlar tekshirilmagan boʻlardi va bilim bazasi
yangilanganda jimgina notoʻgʻri boʻlib qolardi — modda raqamlari
tahrirlar bilan siljiydi. Notoʻgʻri modda raqami esa talabaga
oʻrgatiladigan eng yomon narsa.

Shuning uchun har mavzu **qidiruv soʻrovlarini** olib yuradi
(`search_queries`) va haqiqiy normalar bilim bazasidan RAG orqali
topiladi (`lecture.py`). Modda raqami faqat bazada haqiqatan mavjud
boʻlgan matndan keladi.

Hujjat identifikatorlari — lex.uz raqamlari, yaʼni ular tekshirib
koʻriladigan haqiqiy qiymatlar.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Asosiy tushunchalar
# --------------------------------------------------------------------------- #


class Branch(StrEnum):
    """Huquq sohasi (fan)."""

    CIVIL = "civil"
    CRIMINAL = "criminal"
    CONSTITUTIONAL = "constitutional"
    LABOR = "labor"
    FAMILY = "family"
    ADMINISTRATIVE = "administrative"
    INTERNATIONAL = "international"


class Level(StrEnum):
    """Mavzuning murakkabligi."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Topic(BaseModel):
    """Bitta dars mavzusi."""

    topic_id: str = Field(description="Barqaror identifikator, masalan `labor.contract`")
    title: str
    branch: Branch
    level: Level = Level.BASIC
    summary: str = ""

    search_queries: list[str] = Field(
        default_factory=list,
        description="Bilim bazasidan normalarni topish uchun soʻrovlar",
    )
    doc_ids: list[str] = Field(
        default_factory=list,
        description="Mavzu tegishli boʻlgan hujjatlar (lex.uz identifikatori)",
    )
    prerequisites: list[str] = Field(
        default_factory=list, description="Oldin oʻzlashtirilishi kerak boʻlgan mavzular"
    )

    @property
    def primary_query(self) -> str:
        """Qidiruv uchun asosiy soʻrov — boʻlmasa sarlavhaning oʻzi."""
        return self.search_queries[0] if self.search_queries else self.title


class Subject(BaseModel):
    """Fan — mavzular toʻplami."""

    branch: Branch
    title: str
    description: str = ""
    doc_ids: list[str] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)

    def topic(self, topic_id: str) -> Topic | None:
        return next((t for t in self.topics if t.topic_id == topic_id), None)


# --------------------------------------------------------------------------- #
# Hujjatlar — lex.uz identifikatorlari
# --------------------------------------------------------------------------- #
#
# Nomlar bazadagi `doc_title` bilan bir xil emas (bazada baʼzilari bosh
# harflar bilan). Bu yerda oʻqishga qulay shakl turadi, bogʻlanish esa
# identifikator orqali — u oʻzgarmaydi.

DOC_CIVIL = "-180552"  # Fuqarolik kodeksi
DOC_CIVIL_OLD = "-111189"  # Fuqarolik kodeksi (eski tahrir)
DOC_CIVIL_PROC = "-3517337"  # Fuqarolik protsessual kodeksi
DOC_CRIMINAL = "-111453"  # Jinoyat kodeksi
DOC_CRIMINAL_PROC = "-111460"  # Jinoyat-protsessual kodeksi
DOC_CRIMINAL_EXEC = "-163629"  # Jinoyat-ijroiya kodeksi
DOC_LABOR = "-6257288"  # Mehnat kodeksi
DOC_FAMILY = "-104720"  # Oila kodeksi
DOC_ADMIN = "-97664"  # Maʼmuriy javobgarlik toʻgʻrisidagi kodeks
DOC_ADMIN_PROC = "-3527353"  # Maʼmuriy sud ishlarini yuritish toʻgʻrisidagi kodeks
DOC_ELECTION = "-4386848"  # Saylov kodeksi
DOC_TAX = "-4674902"  # Soliq kodeksi
DOC_ECONOMIC_PROC = "-3523891"  # Iqtisodiy protsessual kodeksi
DOC_CUSTOMS = "-2876354"  # Bojxona kodeksi
DOC_LAND = "-152653"  # Yer kodeksi
DOC_HOUSING = "-106136"  # Uy-joy kodeksi


# --------------------------------------------------------------------------- #
# Dastur
# --------------------------------------------------------------------------- #


def _topic(
    topic_id: str,
    title: str,
    branch: Branch,
    queries: list[str],
    docs: list[str],
    *,
    level: Level = Level.BASIC,
    summary: str = "",
    prerequisites: list[str] | None = None,
) -> Topic:
    return Topic(
        topic_id=topic_id,
        title=title,
        branch=branch,
        level=level,
        summary=summary,
        search_queries=queries,
        doc_ids=docs,
        prerequisites=prerequisites or [],
    )


CIVIL = Subject(
    branch=Branch.CIVIL,
    title="Fuqarolik huquqi",
    description=(
        "Mulk, shartnoma va majburiyat munosabatlari; zarar qoplash va "
        "meros. Asosiy manba — Fuqarolik kodeksi."
    ),
    doc_ids=[DOC_CIVIL, DOC_CIVIL_PROC],
    topics=[
        _topic(
            "civil.subjects",
            "Fuqarolik huquqining subyektlari",
            Branch.CIVIL,
            ["fuqarolik huquq layoqati", "yuridik shaxs tashkil etish", "muomala layoqati"],
            [DOC_CIVIL],
            summary="Jismoniy va yuridik shaxslar, ularning huquq va muomala layoqati.",
        ),
        _topic(
            "civil.property",
            "Mulk huquqi",
            Branch.CIVIL,
            ["mulk huquqi", "mulkdorning huquqlari", "mulk huquqining vujudga kelishi"],
            [DOC_CIVIL, DOC_LAND, DOC_HOUSING],
            summary="Egalik qilish, foydalanish va tasarruf etish huquqi.",
        ),
        _topic(
            "civil.contract",
            "Shartnoma huquqi",
            Branch.CIVIL,
            ["shartnoma tuzish tartibi", "shartnoma erkinligi", "shartnomani oʻzgartirish"],
            [DOC_CIVIL],
            level=Level.INTERMEDIATE,
            summary="Shartnoma tuzish, oʻzgartirish va bekor qilish qoidalari.",
            prerequisites=["civil.subjects"],
        ),
        _topic(
            "civil.obligations",
            "Majburiyat huquqi",
            Branch.CIVIL,
            ["majburiyatning bajarilishi", "majburiyatni taʼminlash", "neustoyka"],
            [DOC_CIVIL],
            level=Level.INTERMEDIATE,
            prerequisites=["civil.contract"],
        ),
        _topic(
            "civil.damages",
            "Zarar yetkazishdan kelib chiqadigan majburiyatlar",
            Branch.CIVIL,
            ["zarar qoplash", "yetkazilgan zarar uchun javobgarlik", "maʼnaviy zarar"],
            [DOC_CIVIL],
            level=Level.ADVANCED,
        ),
        _topic(
            "civil.inheritance",
            "Meros huquqi",
            Branch.CIVIL,
            ["merosxoʻrlik tartibi", "vasiyatnoma", "meros ochilishi"],
            [DOC_CIVIL],
            level=Level.INTERMEDIATE,
        ),
    ],
)

CRIMINAL = Subject(
    branch=Branch.CRIMINAL,
    title="Jinoyat huquqi",
    description=(
        "Jinoyat tushunchasi, jazo tizimi va jinoyat javobgarligi. Asosiy "
        "manbalar — Jinoyat kodeksi va Jinoyat-protsessual kodeksi."
    ),
    doc_ids=[DOC_CRIMINAL, DOC_CRIMINAL_PROC, DOC_CRIMINAL_EXEC],
    topics=[
        _topic(
            "criminal.crime",
            "Jinoyat tushunchasi va tarkibi",
            Branch.CRIMINAL,
            ["jinoyat tushunchasi", "jinoyat tarkibi", "ijtimoiy xavflilik"],
            [DOC_CRIMINAL],
        ),
        _topic(
            "criminal.liability",
            "Jinoiy javobgarlik",
            Branch.CRIMINAL,
            ["jinoiy javobgarlik yoshi", "javobgarlikdan ozod qilish", "aybdorlik"],
            [DOC_CRIMINAL],
            prerequisites=["criminal.crime"],
        ),
        _topic(
            "criminal.punishment",
            "Jazo tizimi",
            Branch.CRIMINAL,
            ["jazo turlari", "jazo tayinlash", "jazoni yengillashtiruvchi holatlar"],
            [DOC_CRIMINAL, DOC_CRIMINAL_EXEC],
            level=Level.INTERMEDIATE,
            prerequisites=["criminal.liability"],
        ),
        _topic(
            "criminal.property_crimes",
            "Mulkka qarshi jinoyatlar",
            Branch.CRIMINAL,
            ["oʻgʻirlik", "talonchilik", "firibgarlik"],
            [DOC_CRIMINAL],
            level=Level.INTERMEDIATE,
        ),
        _topic(
            "criminal.procedure",
            "Jinoyat protsessining asoslari",
            Branch.CRIMINAL,
            ["dastlabki tergov", "ayblanuvchining huquqlari", "sud muhokamasi tartibi"],
            [DOC_CRIMINAL_PROC],
            level=Level.ADVANCED,
        ),
    ],
)

CONSTITUTIONAL = Subject(
    branch=Branch.CONSTITUTIONAL,
    title="Konstitutsion huquq",
    description=(
        "Davlat tuzilishi, inson huquqlari va saylov tizimi. DIQQAT: "
        "Konstitutsiyaning oʻzi bilim bazasida yoʻq — hozircha faqat "
        "Saylov kodeksi mavjud."
    ),
    doc_ids=[DOC_ELECTION],
    topics=[
        _topic(
            "constitutional.rights",
            "Inson huquq va erkinliklari",
            Branch.CONSTITUTIONAL,
            ["inson huquqlari", "fuqarolarning konstitutsiyaviy huquqlari"],
            [],
            summary="Konstitutsiyaviy huquq va erkinliklar tizimi.",
        ),
        _topic(
            "constitutional.state",
            "Davlat hokimiyati tizimi",
            Branch.CONSTITUTIONAL,
            ["hokimiyat boʻlinishi", "Oliy Majlis vakolatlari"],
            [],
            level=Level.INTERMEDIATE,
        ),
        _topic(
            "constitutional.elections",
            "Saylov huquqi",
            Branch.CONSTITUTIONAL,
            ["saylov huquqi", "saylovchilar roʻyxati", "ovoz berish tartibi"],
            [DOC_ELECTION],
            level=Level.INTERMEDIATE,
        ),
    ],
)

LABOR = Subject(
    branch=Branch.LABOR,
    title="Mehnat huquqi",
    description="Mehnat shartnomasi, ish vaqti, mehnat haqi va mehnat nizolari.",
    doc_ids=[DOC_LABOR],
    topics=[
        _topic(
            "labor.contract",
            "Mehnat shartnomasi",
            Branch.LABOR,
            ["mehnat shartnomasi tuzish", "sinov muddati", "mehnat shartnomasi shartlari"],
            [DOC_LABOR],
            summary="Mehnat shartnomasini tuzish, oʻzgartirish va bekor qilish.",
        ),
        _topic(
            "labor.termination",
            "Mehnat shartnomasini bekor qilish",
            Branch.LABOR,
            [
                "ishdan boʻshatish asoslari",
                "mehnat shartnomasini bekor qilish",
                "ishdan boʻshatish",
            ],
            [DOC_LABOR],
            level=Level.INTERMEDIATE,
            prerequisites=["labor.contract"],
        ),
        _topic(
            "labor.worktime",
            "Ish vaqti va dam olish vaqti",
            Branch.LABOR,
            ["ish vaqti davomiyligi", "taʼtil berish tartibi", "tungi ish"],
            [DOC_LABOR],
        ),
        _topic(
            "labor.wages",
            "Mehnatga haq toʻlash",
            Branch.LABOR,
            ["ish haqi toʻlash muddati", "eng kam ish haqi", "ish haqidan ushlab qolish"],
            [DOC_LABOR],
        ),
        _topic(
            "labor.disputes",
            "Mehnat nizolari",
            Branch.LABOR,
            ["mehnat nizolarini koʻrish", "individual mehnat nizosi"],
            [DOC_LABOR, DOC_CIVIL_PROC],
            level=Level.ADVANCED,
            prerequisites=["labor.termination"],
        ),
    ],
)

FAMILY = Subject(
    branch=Branch.FAMILY,
    title="Oila huquqi",
    description="Nikoh, er-xotin munosabatlari, bolalar huquqi va aliment.",
    doc_ids=[DOC_FAMILY],
    topics=[
        _topic(
            "family.marriage",
            "Nikoh tuzish va bekor qilish",
            Branch.FAMILY,
            ["nikoh tuzish sharti", "nikohni bekor qilish", "nikoh yoshi"],
            [DOC_FAMILY],
        ),
        _topic(
            "family.property",
            "Er-xotinning mol-mulki",
            Branch.FAMILY,
            ["er-xotinning umumiy mulki", "mulkni boʻlish", "nikoh shartnomasi"],
            [DOC_FAMILY, DOC_CIVIL],
            level=Level.INTERMEDIATE,
            prerequisites=["family.marriage"],
        ),
        _topic(
            "family.children",
            "Ota-ona va bolalar munosabatlari",
            Branch.FAMILY,
            ["ota-onalik huquqi", "bolaning huquqlari", "otalikni belgilash"],
            [DOC_FAMILY],
        ),
        _topic(
            "family.alimony",
            "Aliment majburiyatlari",
            Branch.FAMILY,
            ["aliment undirish", "aliment miqdori", "voyaga yetmagan bolani taʼminlash"],
            [DOC_FAMILY],
            level=Level.INTERMEDIATE,
            prerequisites=["family.children"],
        ),
    ],
)

ADMINISTRATIVE = Subject(
    branch=Branch.ADMINISTRATIVE,
    title="Maʼmuriy huquq",
    description="Maʼmuriy javobgarlik, jarima va maʼmuriy sud ishlari.",
    doc_ids=[DOC_ADMIN, DOC_ADMIN_PROC],
    topics=[
        _topic(
            "admin.offence",
            "Maʼmuriy huquqbuzarlik tushunchasi",
            Branch.ADMINISTRATIVE,
            ["maʼmuriy huquqbuzarlik", "maʼmuriy javobgarlik asoslari"],
            [DOC_ADMIN],
        ),
        _topic(
            "admin.penalties",
            "Maʼmuriy jazolar",
            Branch.ADMINISTRATIVE,
            ["jarima solish", "maʼmuriy jazo turlari", "maʼmuriy qamoq"],
            [DOC_ADMIN],
            prerequisites=["admin.offence"],
        ),
        _topic(
            "admin.procedure",
            "Maʼmuriy ish yuritish",
            Branch.ADMINISTRATIVE,
            ["maʼmuriy ish yuritish tartibi", "qarorni ustidan shikoyat qilish"],
            [DOC_ADMIN, DOC_ADMIN_PROC],
            level=Level.INTERMEDIATE,
        ),
        _topic(
            "admin.tax_customs",
            "Soliq va bojxona sohasidagi javobgarlik",
            Branch.ADMINISTRATIVE,
            ["soliq huquqbuzarligi", "bojxona qoidalarini buzish"],
            [DOC_TAX, DOC_CUSTOMS, DOC_ADMIN],
            level=Level.ADVANCED,
        ),
    ],
)

INTERNATIONAL = Subject(
    branch=Branch.INTERNATIONAL,
    title="Xalqaro huquq",
    description=(
        "Xalqaro shartnomalar va ularning milliy qonunchilikdagi oʻrni. "
        "DIQQAT: bu fan boʻyicha bilim bazasida hujjat YOʻQ — leksiya "
        "manbasiz chiqadi."
    ),
    doc_ids=[],
    topics=[
        _topic(
            "international.treaties",
            "Xalqaro shartnomalar",
            Branch.INTERNATIONAL,
            ["xalqaro shartnoma", "xalqaro shartnomani ratifikatsiya qilish"],
            [],
            level=Level.INTERMEDIATE,
        ),
        _topic(
            "international.private",
            "Xalqaro xususiy huquq",
            Branch.INTERNATIONAL,
            ["chet el elementi bilan munosabatlar", "qoʻllaniladigan huquqni tanlash"],
            [DOC_CIVIL],
            level=Level.ADVANCED,
        ),
        _topic(
            "international.human_rights",
            "Inson huquqlari boʻyicha xalqaro standartlar",
            Branch.INTERNATIONAL,
            ["inson huquqlari boʻyicha xalqaro majburiyatlar"],
            [],
            level=Level.ADVANCED,
        ),
    ],
)


SUBJECTS: dict[Branch, Subject] = {
    Branch.CIVIL: CIVIL,
    Branch.CRIMINAL: CRIMINAL,
    Branch.CONSTITUTIONAL: CONSTITUTIONAL,
    Branch.LABOR: LABOR,
    Branch.FAMILY: FAMILY,
    Branch.ADMINISTRATIVE: ADMINISTRATIVE,
    Branch.INTERNATIONAL: INTERNATIONAL,
}


# --------------------------------------------------------------------------- #
# Foydalanish
# --------------------------------------------------------------------------- #


def subject(branch: Branch | str) -> Subject:
    """Fanni sohasi boʻyicha qaytaradi."""
    key = Branch(branch)
    return SUBJECTS[key]


def all_topics() -> list[Topic]:
    """Barcha fanlarning mavzulari, dastur tartibida."""
    return [t for s in SUBJECTS.values() for t in s.topics]


def find_topic(topic_id: str) -> Topic | None:
    """Mavzuni identifikatori boʻyicha topadi."""
    return next((t for t in all_topics() if t.topic_id == topic_id), None)


def search_topics(text: str) -> list[Topic]:
    """Sarlavha, xulosa va qidiruv soʻrovlari boʻyicha mavzu izlaydi."""
    needle = text.strip().lower()
    if not needle:
        return []
    found = []
    for t in all_topics():
        haystack = " ".join([t.title, t.summary, *t.search_queries]).lower()
        if needle in haystack:
            found.append(t)
    return found


def learning_path(topic_id: str) -> list[Topic]:
    """Mavzuga yetib borish yoʻli: avval shartlar, oxirida mavzuning oʻzi.

    Rekursiv — shart mavzuning oʻz sharti ham qoʻshiladi. Takrorlar
    olib tashlanadi, tartib saqlanadi.
    """
    order: list[Topic] = []
    seen: set[str] = set()

    def visit(tid: str, guard: frozenset[str]) -> None:
        if tid in seen or tid in guard:
            # `guard` — halqadan himoya: dasturda xato bogʻlanish boʻlsa
            # rekursiya cheksiz ketmasin.
            return
        node = find_topic(tid)
        if node is None:
            return
        for prereq in node.prerequisites:
            visit(prereq, guard | {tid})
        if tid not in seen:
            seen.add(tid)
            order.append(node)

    visit(topic_id, frozenset())
    return order


def coverage(available_doc_ids: set[str]) -> dict[Branch, float]:
    """Har fan hujjatlarining nechasi bilim bazasida bor.

    NEGA KERAK. Dasturda yetti fan bor, bilim bazasida esa hozircha faqat
    kodekslar. Konstitutsiya va xalqaro shartnomalar yoʻq — bu fanlar
    boʻyicha leksiya manbasiz chiqadi. Bu funksiya buni OLDINDAN
    koʻrsatadi, talaba boʻsh leksiya olib hayron boʻlmasin.

    Qiymat: 0.0 — bitta ham hujjat yoʻq, 1.0 — hammasi bor.
    Hujjat talab qilmaydigan fan uchun ham 0.0 qaytadi.
    """
    out: dict[Branch, float] = {}
    for branch, subj in SUBJECTS.items():
        if not subj.doc_ids:
            out[branch] = 0.0
            continue
        have = sum(1 for d in subj.doc_ids if d in available_doc_ids)
        out[branch] = have / len(subj.doc_ids)
    return out
