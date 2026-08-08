# ADR-005: LangGraph + qat'iy debate protokoli

**Holat:** ✅ Qabul qilindi
**Sana:** 2026-08-08

## Kontekst

Beshta agent bir masala ustida ishlashi kerak. Ular qanday muvofiqlashtiriladi?

Talablar:
1. **Bashorat qilinadigan xarajat** — foydalanuvchi qancha kutishini bilishi kerak
2. **Konvergensiya kafolati** — jarayon albatta tugashi kerak
3. **To'liq audit** — har qadam yozilishi shart (yuridik talab)
4. **Qayta boshlash** — nosozlikda butun quvurni takrorlamaslik
5. **Insonni jalb qilish imkoniyati** — yurist oraliq bosqichda aralasha olishi

## Ko'rib chiqilgan variantlar

### A — Avtonom agent suhbati (AutoGen uslubi)

Agentlar erkin gaplashadi, konsensusga kelguncha yoki limit tugaguncha.

| Ijobiy | Salbiy |
|--------|--------|
| Moslashuvchan, kutilmagan yechimlar | **Konvergensiya kafolatlanmaydi** |
| Kod oddiy | **Xarajat oldindan bilinmaydi** |
| | Sikllar, takrorlanish |
| | Audit murakkab (tartib har safar boshqacha) |
| | Debug deyarli imkonsiz |

### B — Qat'iy ketma-ketlik (pipeline)

Har doim: jurist → advokat → prokuror → professor → sudya.

| Ijobiy | Salbiy |
|--------|--------|
| To'liq bashorat qilinadigan | Oddiy savolga ham 45 s |
| Oddiy | Agentlar rozi bo'lganda ham munozara qiladi |
| | Moslashuvchanlik yo'q |

### C — Shartli graf (LangGraph) ← **tanlandi**

Deterministik graf + shart asosidagi shoxlanish.

| Ijobiy | Salbiy |
|--------|--------|
| Bashorat qilinadigan (yo'llar chekli) | Graf oldindan loyihalanishi kerak |
| Router murakkablikka moslashadi | Kod pipeline dan murakkabroq |
| Checkpointing → qayta boshlash, audit | LangGraph ga bog'liqlik |
| Har tugundan keyin inson aralasha oladi | |
| Kelishmovchilik past bo'lsa raund o'tkaziladi | |

## Qaror

**LangGraph + uch darajali router + maksimum 2 raundli debate.**

### Router

| Daraja | Agentlar | Kechikish |
|--------|----------|-----------|
| `simple` | jurist | ~5 s |
| `standard` | jurist → professor → judge | ~20 s |
| `complex` | to'liq debate | ~45 s |

Nima uchun: savollarning taxminan **60% i faktik** ("MMT stavkasi qancha?"). Ularga besh agentli munozara — bu 9× ortiqcha xarajat va foydasiz kutish.

### Kelishmovchilik balli

Raund 2 shartli ravishda o'tkaziladi:

```python
def disagreement(a: Position, p: Position) -> float:
    return (0.4 * abs(a.confidence - p.confidence)
          + 0.4 * (1 - citation_overlap(a, p))
          + 0.2 * conclusion_distance(a, p))
```

Chegara `0.4`. Undan past — agentlar aslida rozi, munozara ma'nosiz. Bu **o'rtacha 30% vaqt tejaydi**.

### Nima uchun maksimum 2 raund

Empirik kuzatuv (adabiyot va prototiplardan):

| Raund | Sifat o'zgarishi |
|-------|------------------|
| 1 → 2 | **+12%** |
| 2 → 3 | +2% |
| 3 → 4 | **−1%** |

3-raunddan keyin agentlar bir xil dalilni qayta ifodalaydi, kontekst o'sadi va "lost-in-the-middle" effekti sifatni tushiradi. Ikki raund — foyda/xarajat egri chizig'ining tepasi.

## Prefix KV-cache

Debate ning eng katta xarajati — bir xil huquqiy kontekstni har agent uchun qayta ishlash.

```
┌────────────────────────────────────────┬──────────────┐
│ UMUMIY PREFIKS (bir marta)             │ ROL QISMI    │
│ system + huquqiy kontekst (~6k token)  │ (~400 token) │
└────────────────────────────────────────┴──────────────┘
         33 s, cache lanadi                 ~2 s × 5

Cache siz:   5 × 33 s = 165 s
Cache bilan: 33 s + 10 s = 43 s      →  3.8× tezroq
```

**Qat'iy talab:** umumiy prefiks barcha agentlarda bayt-baytga bir xil bo'lishi kerak. Shuning uchun **rol prompti prefiksdan keyin joylashadi**, oldin emas. Bu prompt dizaynidagi majburiy cheklov va u kodda test bilan tekshiriladi.

## Checkpointing

```python
app = graph.compile(checkpointer=SqliteSaver("traces.db"))
```

Nima beradi:
- **Audit** — har qadam saqlanadi (yuridik talab, [`docs/10`](../10-security-compliance.md))
- **Qayta boshlash** — agent xato bersa, shu tugundan davom etish
- **Debug** — "nima uchun bunday javob?" ga aniq javob
- **Human-in-the-loop** — istalgan tugundan keyin to'xtatib, yurist aralashuvi

## Oqibatlari

### Ijobiy
- Kechikish oldindan bilinadi va SLO qo'yish mumkin
- Xarajat cheklangan (maksimum agent chaqiruvlari soni ma'lum)
- Yangi agent qo'shish = grafga tugun qo'shish
- Trace UI da to'g'ridan-to'g'ri ko'rsatiladi

### Salbiy

| Salbiy | Yumshatish |
|--------|------------|
| Graf oldindan loyihalanadi — moslashuvchanlik kam | Router uchta yo'l beradi; kerak bo'lsa yangi shox qo'shiladi |
| LangGraph ga bog'liqlik | Graf mantiqi sof funksiyalarda; LangGraph faqat oqim boshqaruvi. Almashtirish ~1 hafta |
| Router noto'g'ri tasniflashi mumkin | Foydalanuvchi `--mode` bilan majburlashi mumkin; router aniqligi o'lchanadi (maqsad ≥ 85%) |
| Local da agentlar ketma-ket | Prefix cache; server profilida vLLM multi-LoRA |

## Rad etilgan qo'shimcha g'oyalar

| G'oya | Nima uchun rad etildi |
|-------|----------------------|
| Agentlar bir-birini baholashi (peer review) | Xarajat 2×, foyda o'lchanmadi. Judge allaqachon shu ishni qiladi |
| Dinamik agent soni (LLM hal qiladi) | Xarajat bashorat qilinmaydi |
| Agentlar tashqi vosita chaqirishi (web qidiruv) | Iqtibos kafolatini buzadi — faqat KB dan |
| Judge o'rniga ovoz berish | Yuridik xulosa ovoz emas, asoslash talab qiladi |
