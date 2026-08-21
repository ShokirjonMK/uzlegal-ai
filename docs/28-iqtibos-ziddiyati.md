# 28 — Iqtibosga zid da'vo

**Sana:** 2026-08-21
**Manba:** yakuniy tahlil — mahsulotdan uchta savol so'ralganda ikkitasiga
iqtibosga zid javob berildi. Bu ikkala xato turini yopadi.

---

## 1. Nima o'lchandi

Mahsulot birinchi marta **javob sifati** bo'yicha sinaldi. Ilgari
barcha baholashlar qidiruvni tekshirgan.

### 1.1 Manbaga zid son

```
SAVOL   Vindikatsiya da'vosi muddati necha yil

JAVOB   «…qonuniy muddat umumiy qoidalarga mos ravishda
         10 yil bo'lib…»  [C1]

[C1]    Fuqarolik kodeksi, 150-modda — aynan shu iqtibos:
        «Umumiy da'vo muddati — uch yil.»
```

Iqtibos **to'g'ri moddaga** ishora qiladi, matn **uch yil** deydi,
javob **10 yil** deydi. Da'vo darvozadan o'tdi.

### 1.2 Boshqa kodeks nomlanishi

```
SAVOL   Nikohdan ajrashishda mol-mulk qanday bo'linadi
JAVOB   Fuqarolik kodeksi, 225-modda
TO'G'RI Oila kodeksi, 23 va 44-modda — ikkalasi ham korpusda bor
```

Diqqat: bu holatda darvoza da'voni `[⚠ noaniq]` deb **belgilagan** edi,
ya'ni u jimgina o'tmagan. Lekin belgilangan da'vo javobda qoladi va
foydalanuvchi uni o'qiydi.

---

## 2. Nima uchun mavjud darvoza ushlamadi

`gate.support_score()` qo'llab-quvvatlanishni **so'z ustma-ustligi**
bilan o'lchaydi:

```python
claim_words = content_words(claim)
return len(claim_words & content_words(source)) / len(claim_words)
```

«Vindikatsiya da'vosi uchun qonuniy muddat umumiy qoidalarga mos
ravishda **10 yil**» va «Umumiy da'vo muddati — **uch yil**» ko'p
so'zni bo'lishadi: *da'vo, muddat, umumiy, yil*. Qoplama yuqori,
demak da'vo «asoslangan».

Farq esa aynan o'sha so'zlarda emas — u **sonda**. Leksik qoplama
son ziddiyatini **printsipial ravishda** ko'ra olmaydi.

---

## 3. Yechim — ikkita aniq tekshiruv

Ikkalasi ham `has_invented_article()` bilan bir xil oilaga tegishli:
**aniq**, taxminiy emas. Shuning uchun natija belgilash emas,
**o'chirish**.

### 3.1 Miqdor ziddiyati

`orchestrator/quantity.py`. Da'vodagi `(qiymat, birlik)` juftliklari
iqtibos matnidagilar bilan solishtiriladi.

O'zbek yuridik matnida son **so'z bilan** yoziladi, shuning uchun
normallashtirish kerak:

| Matn | Natija |
|---|---|
| `uch yil` | `(3, yil)` |
| `o'n besh kun` | `(15, kun)` |
| `yigirma besh foiz` | `(25, foiz)` |
| `10 yil` | `(10, yil)` |
| **`150-modda`** | **miqdor emas** |

Oxirgi qator eng muhim istisno: modda raqamlari matnda son bo'lib
ko'rinadi. Ular defis bilan yoziladi, naqsh esa bo'sh joy talab
qiladi — shuning uchun ular tushmaydi.

**Uchta ehtiyot chorasi:**

* da'voda miqdor yo'q → tekshirib bo'lmaydi, tegilmaydi;
* manbada **o'sha birlikda** miqdor yo'q → tegilmaydi;
* da'vodagi qiymat manbadagilar orasida **bor** → ziddiyat yo'q.

Uchinchisi amaliy: modda ko'pincha bir necha muddat sanaydi
(«uch yil … ayrim hollarda o'n yil») va javob ulardan birini
keltirishi mumkin.

### 3.2 Hujjat ziddiyati

`orchestrator/document.py`. Da'vo kodeks **nomini** aytsa va u
iqtibos qilingan hujjatlarning hech biriga mos kelmasa — da'vo
chiqariladi.

Tekshiruv **ataylab tor**:

* «ushbu kodeks», «mazkur kodeks» — bu **ishora**, nom emas va
  tekshiruvni ishga tushirmaydi;
* da'vo bir necha iqtibosga tayanishi mumkin — **bittasi** mos
  kelsa yetarli;
* iqtibosda sarlavha bo'lmasa — tekshirib bo'lmaydi.

Amalda bu tekshiruv kam ishlaydi va shunday bo'lishi kerak:
modelning ko'p javobida kodeks nomi umuman aytilmaydi.

### 3.3 Tartib

Ikkala tekshiruv leksik qoplamadan **oldin** turadi:

```
iqtibos bormi → iqtibos haqiqiymi
  → HUJJAT ziddiyati        (aniq)
  → MIQDOR ziddiyati        (aniq)
  → modda raqami            (aniq)
  → leksik qoplama          (taxminiy)
```

Aniq tekshiruv taxminiydan oldin: modda raqami yoki son noto'g'ri
bo'lsa, qoplamaning yuqori bo'lishining ahamiyati yo'q.

---

## 4. Tasdiq — deterministik

Model nobarqaror, shuning uchun tekshiruv **aynan o'sha xato matn**
bilan o'tkazildi, qayta chaqiruv bilan emas:

```
KIRISH   «…qonuniy muddat … 10 yil bo'lib…» [C1]
         [C1] excerpt: «Umumiy daʼvo muddati - uch yil.»

NATIJA   chiqarildi: 1
         sabab: da'vodagi miqdor iqtibos matniga zid
         rad etildi: True
         javob: «Ishonchli javob shakllantirilmadi…»
```

Ya'ni tizim endi noto'g'ri raqamni ko'rsatish o'rniga **rad etadi**.

To'g'ri variant tegilmaydi:

```
KIRISH   «Vindikatsiya da'vosi muddati uch yil [C1].»
NATIJA   chiqarildi: 0 · matn saqlandi
```

Testlar: `test_quantity.py` (23) va `test_document_clash.py` (11).
Ularning yarmi **«tegilmasin»** talabini qo'riqlaydi — haddan tashqari
qattiq tekshiruv to'g'ri javoblarni ham o'chiradi va buni sezish
qiyin, chunki o'chirilgan da'vo xatoga o'xshamaydi.

Butun to'plam: **1 226 test** ✅ — regressiya yo'q.

---

## 5. Nima TUZATILMADI — ochiq aytiladi

Bu ish javobni **to'g'ri qilmaydi**. U noto'g'ri javobni
**ko'rsatmaydi**. Farq muhim.

Ajrashish savoli qayta yugurtirilganda natija shunday bo'ldi:

```
JAVOB    TEGISHLI NORMALAR
         - [C1] Oila kodeksi, 44-modda
         - [C2] Fuqarolik kodeksi, 226-modda
ISHONCH  0.1
GATE     4 ta da'vo chiqarildi
```

Manbalar endi **to'g'ri** (Oila kodeksi birinchi), lekin javob matni
bo'sh. Ya'ni mahsulot «xato» holatidan «bo'sh» holatiga o'tdi.

Bu **to'g'ri yo'nalish**, lekin yetarli emas. Sabab quyi oqimda:
model iqtibosga bog'lanadigan da'vo yoza olmayapti. Uni yopadigan
narsa boshqa:

| # | Nima | Bog'liq |
|---|---|---|
| ~~Z1~~ | ~~Sifatni haqiqiy modelda o'lchash~~ | ⚠️ Qisman. Shu mashinada 100% GPU da ishlaydigan yagona model — `qwen3:8b` (o'lchandi: `ollama ps` → 6.0 GB, 100% GPU). qwen3.5 diskda 6.6 GB, xotirada 8.8 GB va 28% CPU ga to'kiladi; 14B umuman sig'maydi. Ya'ni **ishlab chiqarish sifati hamon o'lchanmagan** — lekin quvur endi to'liq ishlaydi |
| **Z2** | Rol adapterlari | A3 — yurist, 70 → 300 soat |
| **Z3** | Zid da'volar **chastotasi** | Gold set (36 → ~200) |
| **Z4** | Belgilangan da'vo chiqarilsinmi | Z3 dan keyin — chegara qarori |

Z4 alohida izohga arziydi: hozir zaif qo'llab-quvvatlangan da'vo
`[⚠ noaniq]` bilan **qoladi**. Uni chiqarish javobni yanada
bo'shatadi. Bu chegara qarori va u **o'lchovsiz qabul qilinmaydi**.
