# ADR-003: Bitta baza model + ko'p LoRA adapter

**Holat:** ✅ Qabul qilindi
**Sana:** 2026-08-08

## Kontekst

Tizimda beshta yuridik rol bor: yurist, advokat, prokuror, professor, sudya. Har biri o'ziga xos uslub, struktura va pozitsiyaga ega bo'lishi kerak.

Cheklov: 24 GB unified memory, undan ~18 GB GPU uchun mavjud.

## Ko'rib chiqilgan variantlar

### A — Beshta alohida to'liq model

| Ijobiy | Salbiy |
|--------|--------|
| Maksimal rol ixtisoslashuvi | **~40 GB xotira — sig'maydi** |
| Rollar butunlay mustaqil | 5× trening xarajati |
| | Rollar orasida bilim nomuvofiqligi |
| | 5× yangilanish ishi |

Xotira hisobi: 5 × 8 GB (14B 4-bit) = 40 GB. Mavjud 18 GB. **Texnik jihatdan imkonsiz.**

### B — Bitta model, faqat system prompt farqi

| Ijobiy | Salbiy |
|--------|--------|
| 8 GB xotira | Rol farqlari yuzaki |
| Trening kerak emas | Model rolni "unutadi" uzun kontekstda |
| Darhol ishlaydi | Uslub izchilligi past |
| | Format rioyasi zaif |

### C — Bitta baza + rol LoRA adapterlari ← **tanlandi**

| Ijobiy | Salbiy |
|--------|--------|
| ~8.2 GB jami xotira | Adapter almashtirish kechikishi (~50 ms) |
| Chuqur rol ixtisoslashuvi | Local da haqiqiy parallellik yo'q |
| Umumiy huquqiy bilim bazasi | Adapter versiyalarini boshqarish kerak |
| Adapter 40 MB — arzon saqlash | |
| Rollarni mustaqil yangilash | |
| Yangi rol qo'shish oson | |

## Qaror

**Variant C: bitta kvantlangan baza model + beshta LoRA adapter (r=16, ~40 MB har biri).**

### Nima uchun ishlaydi

LoRA asosiy vazn matritsalarini o'zgartirmaydi, ularga past-rangli qo'shimcha qo'shadi:

```
W' = W + (B · A)      B: d×r,  A: r×k,  r=16 ≪ d,k
```

`W` (8 GB) barcha rollar uchun umumiy va o'zgarmas. `B·A` (40 MB) rolga xos. Adapter almashtirish = 40 MB ni ko'chirish, 8 GB ni emas.

### Nima uchun bu *sifat* jihatdan ham to'g'ri

Rollar bir xil huquqiy bilimni bo'lishishi **kerak**. Advokat va prokuror bir xil qonunni turlicha **talqin qiladi**, turlicha **bilmaydi**. Alohida modellar bo'lsa, ular bir xil moddani turlicha eslab qolishi mumkin edi — bu munozarani ma'nosiz qiladi.

Umumiy baza bu izchillikni **arxitektura darajasida kafolatlaydi**.

### Nima uchun rank 16

| Rank | Hajm | Sig'im |
|------|------|--------|
| 8 | 20 MB | Oddiy uslub |
| **16** | **40 MB** | **Rol uslubi + struktura** ← yetarli |
| 32 | 80 MB | Murakkab format |
| 64 | 160 MB | Yangi bilim (CPT uchun) |

Rol adapteri **yangi bilim o'rgatmaydi** — bilim RAG dan va umumiy SFT dan keladi. Adapter faqat *qanday gapirishni* o'zgartiradi. Rank 16 buning uchun yetarli; kattaroq rank overfitting va keraksiz xotira sarfi.

## Oqibatlari

### Ijobiy
- 24 GB cheklovida beshta rol ishlaydi (~8.2 GB)
- Yangi rol qo'shish: YAML config + adapter trening, kod o'zgarmaydi
- Bitta rolni yaxshilash boshqalariga ta'sir qilmaydi
- A/B test oson: `advocate/v0.2` vs `advocate/v0.3`

### Salbiy va yumshatish

| Salbiy | Yumshatish |
|--------|------------|
| Adapter global holat → local da parallellik yo'q | Prefix KV-cache (3.8× tezlashtirish); server profilida vLLM multi-LoRA |
| Baza model o'zgarsa hamma adapter qayta o'qitiladi | Baza tanlovi Faza 0 da puxta qilinadi ([ADR-001](ADR-001-base-model.md)) |
| Adapter reestrini boshqarish kerak | `adapters/registry.yaml` + versiyalash |
| Rol qulflanishi xavfi | Trening ma'lumotining 15% i "pozitsiya kuchsiz" namunalari |

## Server profilida o'zgarish

vLLM **multi-LoRA** ni qo'llab-quvvatlaydi — beshta adapter bir vaqtda faol bo'lib, so'rovlar haqiqatan parallel ishlaydi. Bu debate vaqtini ~30 s dan ~6 s ga tushiradi.

Ya'ni bu qaror **local da ishlaydi va serverda yanada yaxshi ishlaydi** — arxitektura masshtablanadi.

## Qaytarish narxi

Past. Agar kelajakda alohida modellar kerak bo'lsa (masalan katta serverda), adapterni bazaga merge qilib mustaqil model olish mumkin:

```bash
uzlegal train merge --base models/uzlegal-14b --adapter adapters/judge/current \
                    --out models/uzlegal-judge-14b
```

Ya'ni bu qaror bir tomonlama eshik emas.
