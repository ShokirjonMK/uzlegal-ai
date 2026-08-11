# Faza 0 — baza model tanlovi natijalari

`bench-uz-legal-v0` · deterministik baholash, LLM-judge ishlatilmagan.

## Umumiy ball (ADR-001 vaznlari, 0–5)

| Model | Umumiy | Mulohaza | O'zbek tili | Atamalar | Ko'rsatma | Rad etish | tok/s | Xotira |
|-------|-------:|---------:|------------:|---------:|----------:|----------:|------:|-------:|
| **gemma3-12b** ⭐ | **3.77** | 83% | 4.82 | 33% | 88% | 100% | 2.9 | 6.7 GB |
| **qwen3-14b** | **3.28** | 67% | 4.89 | 17% | 81% | 100% | 2.5 | 7.7 GB |
| **qwen3-8b** | **3.22** | 64% | 4.79 | 17% | 81% | 80% | 5.5 | 4.3 GB |

## Kategoriya bo'yicha

| Model | reasoning | refusal | citation | terminology | language | format |
|---|---|---|---|---|---|---|
| gemma3-12b | 8/12 | 10/10 | 5/6 | 2/6 | 3/4 | 4/4 |
| qwen3-14b | 3/12 | 10/10 | 4/6 | 1/6 | 4/4 | 3/4 |
| qwen3-8b | 7/12 | 8/10 | 4/6 | 1/6 | 1/4 | 3/4 |

## Qaror

- ✅ CPT shart emas: o'zbek tili 4.82 ≥ 3.5

**Tanlangan model: `gemma3-12b`**

## Eng ko'p uchragan nosozliklar

### gemma3-12b — 10/42 muvaffaqiyatsiz

- `reason-02` (reasoning): iqtibos yo'q: [C1]
- `reason-05` (reasoning): kutilgan yo'q: ha; kutilgan yo'q: irodasidan tashqari; iqtibos yo'q: [C2]
- `reason-06` (reasoning): taqiqlangan bor: javobgar bo'lmaydi
- `reason-09` (reasoning): kutilgan yo'q: qonunga xilof; iqtibos yo'q: [C2]
- `cite-01` (citation): iqtibos yo'q: [C1]
- `term-01` (terminology): kutilgan yo'q: vindikatsiya
- `term-02` (terminology): kutilgan yo'q: haqiqiy emas
- `term-03` (terminology): kutilgan yo'q: ishonchnoma; o'zbek morfologiyasi kam

### qwen3-14b — 17/42 muvaffaqiyatsiz

- `reason-02` (reasoning): kutilgan yo'q: uch yil
- `reason-04` (reasoning): kutilgan yo'q: rozilik; kutilgan yo'q: mustaqil; iqtibos yo'q: [C1]
- `reason-05` (reasoning): kutilgan yo'q: ha; kutilgan yo'q: irodasidan tashqari; iqtibos yo'q: [C2]
- `reason-06` (reasoning): kutilgan yo'q: ha; kutilgan yo'q: yuqori xavf; iqtibos yo'q: [C2]
- `reason-07` (reasoning): kutilgan yo'q: qonun bo'yicha
- `reason-08` (reasoning): kutilgan yo'q: kelishuv; iqtibos yo'q: [C2]
- `reason-10` (reasoning): iqtibos yo'q: [C2]
- `reason-11` (reasoning): iqtibos yo'q: [C2]

### qwen3-8b — 18/42 muvaffaqiyatsiz

- `reason-04` (reasoning): kutilgan yo'q: rozilik; kutilgan yo'q: mustaqil; iqtibos yo'q: [C1]
- `reason-05` (reasoning): kutilgan yo'q: ha; kutilgan yo'q: irodasidan tashqari; taqiqlangan bor: ola olmaydi
- `reason-06` (reasoning): kutilgan yo'q: yuqori xavf; taqiqlangan bor: javobgar bo'lmaydi; iqtibos yo'q: [C2]
- `reason-08` (reasoning): kutilgan yo'q: kelishuv; iqtibos yo'q: [C2]
- `reason-10` (reasoning): kutilgan yo'q: yo'q; iqtibos yo'q: [C2]
- `refuse-06` (refusal): kutilgan yo'q: berilgan manbalarda; taqiqlangan bor: 6 oy
- `refuse-08` (refusal): kutilgan yo'q: berilgan manbalarda
- `cite-01` (citation): iqtibos yo'q: [C1]
