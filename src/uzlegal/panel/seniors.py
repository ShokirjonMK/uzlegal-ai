"""O'nta senior yurist — trening namunalarini tekshirish kengashi (docs/26).

## Nima uchun bu modul bor

`docs/05 § 3` yuridik tekshiruvni **qisqartirib bo'lmaydigan** qadam deb
belgilaydi va bu to'g'ri: tekshirilmagan yuridik trening ma'lumoti modelni
*ishonch bilan* xato qilishga o'rgatadi.

Lekin «qisqartirib bo'lmaydi» degani «tezlashtirib bo'lmaydi» degani emas.
Yurist vaqtining katta qismi **aniq yaxshi** va **aniq yomon** namunalarni
ajratishga ketadi. Kengash aynan shuni bajaradi va yuristga faqat
**chinakam noaniq** namunani qoldiradi.

## Chegara — qat'iy va kod darajasida

Kengash `TrainingSample.verified` bayrog'iga **hech qachon tegmaydi**.
U faqat `TrainingSample.panel` ni to'ldiradi. `is_trainable` esa
`verified` ni talab qiladi, ya'ni kengash xulosasi bilan trening
boshlanmaydi. Imzo odamniki.

## Nima uchun aynan o'nta va aynan shu bo'linish

Bo'linish `doc_type` bo'yicha emas, **huquq sohasi** bo'yicha: bir modda
bir necha kodeksga tegishi mumkin, lekin uni baholaydigan mutaxassislik
bitta. O'nta soha O'zbekiston kodekslarini to'liq qoplaydi va har
namunaga ularning **hammasi emas, uchtasi** yuboriladi (§ `select`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Senior yurist ta'rifi
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Senior:
    """Bitta senior yurist — mutaxassislik va tekshiruv nuqtai nazari."""

    key: str
    name: str
    field_of_law: str
    #: Shu sohaga tegishli kodeks va hujjat nomlaridagi kalit so'zlar.
    #: Marshrutlash shular bo'yicha ishlaydi (`select`).
    keywords: tuple[str, ...]
    #: Bu senior nimaga alohida e'tibor beradi. Promptga tushadi va
    #: kengashdagi **nuqtai nazar xilma-xilligini** ta'minlaydi: bir xil
    #: savolga uch xil linza bilan qaralsa, xato topilish ehtimoli ortadi.
    lens: str
    lang_terms: tuple[str, ...] = field(default_factory=tuple)


SENIORS: tuple[Senior, ...] = (
    Senior(
        key="fuqarolik",
        name="Fuqarolik huquqi bo'yicha senior yurist",
        field_of_law="Fuqarolik huquqi — mulk, majburiyat, shartnoma, meros, vindikatsiya",
        keywords=("fuqarolik", "mulk", "shartnoma", "majburiyat", "meros", "ijara", "garov"),
        lens=(
            "Majburiyatning yuzaga kelish asosi to'g'ri ko'rsatilganmi va "
            "da'vo muddati hisobga olinganmi"
        ),
    ),
    Senior(
        key="jinoyat",
        name="Jinoyat huquqi bo'yicha senior yurist",
        field_of_law="Jinoyat huquqi va jinoyat-ijroiya huquqi",
        keywords=("jinoyat", "jazo", "javobgarlik", "qamoq", "jinoyat-ijroiya"),
        lens=(
            "Jinoyat tarkibining to'rt elementi ajratilganmi va jazo chegarasi "
            "moddaning sanksiyasiga mos keladimi"
        ),
    ),
    Senior(
        key="mehnat",
        name="Mehnat huquqi bo'yicha senior yurist",
        field_of_law="Mehnat huquqi va ijtimoiy ta'minot",
        keywords=("mehnat", "ish haqi", "shartnoma", "xodim", "ish beruvchi", "ta'til"),
        lens=(
            "Xodim foydasiga talqin qoidasi qo'llanilganmi va ish beruvchining "
            "majburiyati aniq ko'rsatilganmi"
        ),
    ),
    Senior(
        key="oila",
        name="Oila huquqi bo'yicha senior yurist",
        field_of_law="Oila huquqi — nikoh, ajrim, aliment, bolalar huquqi",
        keywords=("oila", "nikoh", "ajrashish", "aliment", "farzand", "vasiylik"),
        lens="Bolaning manfaati ustuvorligi hisobga olinganmi",
    ),
    Senior(
        key="mamuriy",
        name="Ma'muriy huquq bo'yicha senior yurist",
        field_of_law="Ma'muriy huquq va ma'muriy javobgarlik",
        keywords=("ma'muriy", "mamuriy", "javobgarlik", "jarima", "davlat organi", "litsenziya"),
        lens=(
            "Ma'muriy javobgarlik jinoiy javobgarlikdan to'g'ri ajratilganmi va "
            "muddatlar ko'rsatilganmi"
        ),
    ),
    Senior(
        key="protsessual",
        name="Protsessual huquq bo'yicha senior yurist",
        field_of_law="Fuqarolik, jinoyat, iqtisodiy va ma'muriy sud ishlarini yuritish",
        keywords=("protsessual", "sud", "da'vo", "shikoyat", "apellyatsiya", "kassatsiya"),
        lens=(
            "Sud idorasi va sudlov taalluqliligi to'g'ri aniqlanganmi, "
            "protsessual muddat ko'rsatilganmi"
        ),
    ),
    Senior(
        key="soliq",
        name="Soliq va bojxona huquqi bo'yicha senior yurist",
        field_of_law="Soliq, budjet va bojxona huquqi",
        keywords=("soliq", "budjet", "bojxona", "boj", "aksiz", "qqs"),
        lens="Soliq bazasi va stavkasi aniq ko'rsatilganmi, imtiyoz shartlari to'liqmi",
    ),
    Senior(
        key="korporativ",
        name="Korporativ huquq bo'yicha senior yurist",
        field_of_law="Tadbirkorlik, korporativ huquq va intellektual mulk",
        keywords=(
            "tadbirkorlik",
            "korxona",
            "jamiyat",
            "aksiya",
            "intellektual",
            "tovar belgisi",
            "raqobat",
        ),
        lens="Yuridik shaxs shakli va vakolat chegarasi to'g'ri ko'rsatilganmi",
    ),
    Senior(
        key="yer",
        name="Yer va tabiiy resurslar huquqi bo'yicha senior yurist",
        field_of_law="Yer, suv, shaharsozlik va ekologiya huquqi",
        keywords=("yer", "suv", "shaharsozlik", "qurilish", "ekologiya", "uy-joy"),
        lens="Yer uchastkasiga bo'lgan huquq turi aniq ajratilganmi",
    ),
    Senior(
        key="konstitutsiyaviy",
        name="Konstitutsiyaviy huquq bo'yicha senior yurist",
        field_of_law="Konstitutsiyaviy huquq, normalar ierarxiyasi va kolliziya",
        keywords=("konstitutsiya", "saylov", "davlat hokimiyati", "inson huquqlari"),
        lens=("Normalar ierarxiyasi buzilmaganmi — quyi hujjat yuqorisiga zid talqin qilinmaganmi"),
    ),
)

BY_KEY: dict[str, Senior] = {s.key: s for s in SENIORS}

#: Har namunani nechta senior ko'radi. Uchtasi — ikkita mutaxassis va bitta
#: **boshqa sohadan** tekshiruvchi (§ `select`).
PANEL_SIZE = 3

#: Marshrutlash hech narsa topmasa shu senior ishlaydi: normalar ierarxiyasi
#: har qanday huquqiy matnga taalluqli.
FALLBACK = "konstitutsiyaviy"


def _score(senior: Senior, text: str) -> int:
    """Matnda senior kalit so'zlari necha marta uchraydi."""
    low = text.casefold()
    return sum(low.count(word) for word in senior.keywords)


def select(text: str, *, size: int = PANEL_SIZE) -> list[Senior]:
    """Namuna uchun kengash tarkibini tanlaydi.

    ## Nima uchun hammasi emas

    O'nala senior har namunani ko'rsa, 2 000 namunali to'plam uchun
    20 000 model chaqiruvi kerak bo'ladi. Foydasi esa chiziqli emas:
    mehnat nizosini bojxona bo'yicha senior baholashi shovqin qo'shadi,
    signal emas.

    ## Nima uchun oxirgisi boshqa sohadan

    Ikkita mutaxassis matnga bir xil tomondan qaraydi va bir xil narsani
    o'tkazib yuborishi mumkin. Uchinchisi **ataylab boshqa sohadan**
    olinadi: u domen tafsilotini bilmaydi, lekin mantiq uzilishini,
    asossiz da'voni va iqtibos bilan matn o'rtasidagi nomuvofiqlikni
    o'z sohasidagi ko'z bilan emas, **toza ko'z bilan** ko'radi.

    Bu «nuqtai nazar xilma-xilligi» naqshi: bir xil linzali uchta
    tekshiruvchi bitta linzali uchta tekshiruvchiga teng.
    """
    if size <= 0:
        return []

    ranked = sorted(SENIORS, key=lambda s: (-_score(s, text), s.key))
    top = [s for s in ranked if _score(s, text) > 0][: max(1, size - 1)]
    if not top:
        top = [BY_KEY[FALLBACK]]

    chosen = list(top)
    if len(chosen) < size:
        # Tashqi ko'z: eng past ball olgan, ya'ni mavzuga eng uzoq senior.
        outsider = next((s for s in reversed(ranked) if s not in chosen), None)
        if outsider is not None:
            chosen.append(outsider)
    return chosen[:size]
