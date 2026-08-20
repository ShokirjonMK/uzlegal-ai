# 26 — Senior yurist kengashi

**Sana:** 2026-08-20
**Manba:** strategiya, S2 — «yurist soati muhandislik bilan qisqartiriladigan
o'zgaruvchi». Bu hujjat shu siljishning amalga oshirilishi.

---

## 1. Muammo raqamda

`docs/05 § 3` yurist vaqtini shunday hisoblagan:

| Iteratsiya | Namuna | Yurist vaqti |
|---|---:|---:|
| v0.1 | 2 000 | ~70 soat |
| v1.0 | 25 000 | ~300 soat |

Bu raqamlar **«2 daqiqa × namuna»** dan chiqqan. Ikki daqiqa esa
CLI da bitta-bitta tekshirishni nazarda tutadi — `uzlegal train verify`
hozir aynan shunday ishlaydi.

Lekin o'sha ikki daqiqaning katta qismi qaror qabul qilishga emas,
**saralashga** ketadi: namunani o'qib chiqib, «bu aniq yaxshi» yoki
«bu aniq axlat» deyish. Yuridik hukm esa faqat **noaniq** namunalarda
kerak bo'ladi.

Kengash aynan shu saralashni bajaradi.

---

## 2. Chegara — birinchi navbatda aytiladi

`docs/05 § 3` qat'iy: **bu qadamni qisqartirib bo'lmaydi.**
Tekshirilmagan yuridik trening ma'lumoti modelni *ishonch bilan*
xato qilishga o'rgatadi va bu tekshirilmagan modeldan ham yomonroq.

Kengash bu qoidani **buzmaydi** va buzolmaydi:

```python
class TrainingSample:
    verified: bool = False        # odam imzosi
    panel: dict | None = None     # kengash xulosasi

    @property
    def is_trainable(self) -> bool:
        return self.verified and self.rejection_reason is None
        #      ^^^^^^^^^^^^^ `panel` bu yerda YO'Q — ataylab
```

Kengash `panel` maydonini to'ldiradi, `verified` ga esa **hech qachon
tegmaydi**. Ya'ni kengash ma'qullagan namuna treningga tushmaydi.

Bu `tests/unit/test_panel.py::test_kengash_verified_ga_tegmaydi` bilan
qo'riqlanadi. Test buzilsa — mashina tekshiruvi odam tekshiruvi o'rniga
o'tgan bo'ladi va loyihaning markaziy xavfsizlik qoidasi yo'qoladi.

---

## 3. Kengash tarkibi

O'nta senior yurist, huquq sohasi bo'yicha bo'lingan:

| Kalit | Soha |
|---|---|
| `fuqarolik` | Mulk, majburiyat, shartnoma, meros, vindikatsiya |
| `jinoyat` | Jinoyat va jinoyat-ijroiya huquqi |
| `mehnat` | Mehnat va ijtimoiy ta'minot |
| `oila` | Nikoh, ajrim, aliment, bolalar huquqi |
| `mamuriy` | Ma'muriy huquq va ma'muriy javobgarlik |
| `protsessual` | FPK, JPK, IPK, ma'muriy sud ishlari |
| `soliq` | Soliq, budjet, bojxona |
| `korporativ` | Tadbirkorlik, korporativ, intellektual mulk |
| `yer` | Yer, suv, shaharsozlik, ekologiya |
| `konstitutsiyaviy` | Normalar ierarxiyasi va kolliziya |

Bo'linish `doc_type` bo'yicha **emas**: bir modda bir necha kodeksga
tegishi mumkin, lekin uni baholaydigan mutaxassislik bitta.

### 3.1 Har seniorning o'z linzasi bor

Mutaxassislikdan tashqari har senior **nimaga alohida e'tibor
berishini** biladi. Masalan:

| Senior | Linza |
|---|---|
| `fuqarolik` | Da'vo muddati hisobga olinganmi |
| `jinoyat` | Jinoyat tarkibining to'rt elementi ajratilganmi |
| `mehnat` | Xodim foydasiga talqin qoidasi qo'llanilganmi |
| `konstitutsiyaviy` | Quyi hujjat yuqorisiga zid talqin qilinmaganmi |

Bu bezak emas. Bir xil linzali uchta tekshiruvchi amalda **bitta**
tekshiruvchiga teng: ular bir xil narsani ko'radi va bir xil narsani
o'tkazib yuboradi. Xilma-xil linza qamrovni kengaytiradi.

---

## 4. Marshrutlash — o'ntadan uchtasi

O'nala senior har namunani ko'rsa, 2 000 namunali to'plam
**20 000 model chaqiruvini** talab qiladi. Foydasi esa chiziqli emas:
mehnat nizosini bojxona bo'yicha senior baholashi signal emas,
shovqin qo'shadi.

Shuning uchun har namunaga **uchta** senior tanlanadi:

```
2 mutaxassis  (kalit so'z mosligi bo'yicha)
1 tashqi ko'z (mavzuga eng UZOQ senior)
```

### 4.1 Nima uchun uchinchisi ataylab boshqa sohadan

Ikkita mutaxassis matnga bir tomondan qaraydi. Uchinchisi domen
tafsilotini bilmaydi — va aynan shuning uchun foydali: u mantiq
uzilishini, asossiz da'voni va iqtibos bilan matn o'rtasidagi
nomuvofiqlikni **toza ko'z bilan** ko'radi.

```
$ uzlegal panel route "Ish beruvchi mehnat shartnomasini bekor qildi…"

  1. mehnat      Mehnat huquqi va ijtimoiy ta'minot
  2. fuqarolik   Mulk, majburiyat, shartnoma…
  3. yer         Yer, suv, shaharsozlik      (tashqi ko'z)
```

---

## 5. Kelishuv qoidalari

| Holat | Yo'nalish | Odam vaqti |
|---|---|---|
| Kamida yarmi «noto'g'ri» | `rad` | **yo'q** |
| Hammasi «to'g'ri» va ishonch ≥ 0.75 | `kengash-ma'qulladi` | namunaviy |
| Qolgan hamma holat | `noaniq` | to'liq |

**Rad etish ko'pchilik bilan.** Bu yerda xato qilish arzon: yaxshi
namunani yo'qotish generatsiyani qayta yugurtirish bilan tuzatiladi,
yomon namunani o'tkazib yuborish esa modelga kiradi.

**Ma'qullash bir ovozdan.** Bittasi ham shubha bildirsa — odamga
boradi. Kengashning maqsadi odam o'rniga qaror qabul qilish emas,
**odam ko'radigan oqimni tozalash**.

**Past ishonchli kelishuv kelishuv emas.** Hammasi «to'g'ri» desa ham,
eng past ishonch 0.75 dan past bo'lsa namuna noaniq deb belgilanadi.

---

## 6. Namunaviy tekshiruv nol bo'lmaydi — va bu muhim

Kengash ma'qullagan namunalarning **15%** i baribir yuristga
ko'rsatiladi. Bu ehtiyot chorasi emas, **metodologik zarurat**.

Sabab: kengash agentlari va namunani yaratgan generator **bir xil baza
modelda** ishlaydi. Ya'ni ularning xatolari **bog'liq**: generator
qanday adashsa, tekshiruvchi ham xuddi shunday adashishi mumkin.
Bunday sharoitda kelishuv to'g'rilikning dalili emas — u faqat
**bir xil fikrlashning** dalili.

Namunaviy tekshiruv shu bog'liqlikni o'lchash imkonini beradi:
odam ma'qullanganlarning 15% ini ko'rib, kengash qanchalik
ishonchli ekanini **raqam bilan** biladi. Bu raqam yomon chiqsa —
`MIN_CONFIDENCE` ko'tariladi yoki kengash hajmi oshiriladi.

Tanlash **deterministik**: har 7-namuna. Tasodifiy tanlash bir xil
to'plamda har safar boshqa natija berardi va tekshiruvni takrorlab
bo'lmasdi.

---

## 7. Kutilayotgan samara — va u hali o'lchanmagan

Nazariy hisob:

```
1 000 namuna
  ~300 rad etiladi        → yuristga BORMAYDI
  ~500 ma'qullanadi       → 75 tasi namunaviy tekshiruvga
  ~200 noaniq             → to'liq ko'riladi

Yurist ko'radigan: 275 / 1 000  ≈  28%
```

Ustiga noaniq namunalar **kelishmovchilik bilan** ko'rsatiladi:
yurist «bu yerda muddat ko'rsatilmagan» degan aniq da'voni tekshiradi,
namunani boshidan o'qimaydi.

**Bu raqamlar o'lchanmagan.** Ular kengash taqsimoti haqidagi
taxminga asoslangan va haqiqiy taqsimot birinchi yurish natijasida
ma'lum bo'ladi. Shuning uchun `docs/05` dagi 70 va 300 soat
raqamlari **o'zgartirilmadi** — ular birinchi o'lchovdan keyin
qayta hisoblanadi.

Loyihaning o'z naqshini takrorlamaslik uchun buni ochiq yozamiz:
*e'lon qilingan raqam amaldagi raqam emas* — bu safar e'lon
qilinayotgan raqam yo'q.

---

## 8. Foydalanish

```bash
uzlegal panel seniors                    # kengash tarkibi
uzlegal panel route "savol matni"        # kim ko'radi (modelsiz)
uzlegal panel review --dataset X --dry-run   # marshrutlash taqsimoti
uzlegal panel review --dataset X         # haqiqiy tekshiruv
uzlegal train verify --dataset X         # ODAM imzosi — alohida qadam
```

---

## 9. Bu ishga kirmaydi

| # | Nima | Nega |
|---|---|---|
| **K1** | Yurist tekshiruv paneli (veb) | Strategiya E2 — alohida ish |
| **K2** | Kengash ishonchliligini o'lchash | Birinchi yurishdan keyin (§ 6) |
| **K3** | Kengash tuzatilgan javob taklif qilsin | Hozir faqat baholaydi; tuzatish taklifi yurist ishini tezlashtirishi mumkin, lekin xato tuzatish taklifi uni sekinlashtiradi — o'lchov kerak |
| **K4** | Adapterli seniorlar | Rol adapterlari hali o'qitilmagan |
