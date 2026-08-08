# Arxitektura qarorlari (ADR)

Har bir muhim texnik qaror shu yerda yoziladi: **nima tanlandi**, **nima uchun**, **nima rad etildi** va **oqibati nima**.

Maqsad — olti oydan keyin "nima uchun bunday qilingan?" degan savolga javob bo'lishi. ADR o'zgarmaydi; qaror bekor qilinsa, yangi ADR yoziladi va eskisi `Superseded` deb belgilanadi.

| # | Qaror | Holat |
|---|-------|-------|
| [001](ADR-001-base-model.md) | Baza modelni tanlash | 🟡 Kutilmoqda (Faza 0) |
| [002](ADR-002-lora-vs-full-finetune.md) | Pretraining emas, domenga moslashtirish | ✅ Qabul qilindi |
| [003](ADR-003-single-base-multi-adapter.md) | Bitta baza + ko'p LoRA adapter | ✅ Qabul qilindi |
| [004](ADR-004-serving-runtime.md) | MLX runtime (Apple Silicon) | ✅ Qabul qilindi |
| [005](ADR-005-agent-orchestration.md) | LangGraph + qat'iy debate protokoli | ✅ Qabul qilindi |
| [006](ADR-006-rag-first.md) | RAG birinchi, fine-tuning ikkinchi | ✅ Qabul qilindi |
| [007](ADR-007-vector-store.md) | LanceDB (local) / Qdrant (server) | ✅ Qabul qilindi |

## Shablon

```markdown
# ADR-NNN: Sarlavha

**Holat:** Taklif | Qabul qilindi | Rad etildi | Superseded by ADR-XXX
**Sana:** YYYY-MM-DD
**Qaror qabul qiluvchi:** …

## Kontekst
Qanday muammo hal qilinmoqda? Qanday cheklovlar bor?

## Ko'rib chiqilgan variantlar
| Variant | Ijobiy | Salbiy |

## Qaror
Nima tanlandi va nima uchun aynan shu.

## Oqibatlari
Ijobiy / salbiy / qaytarish narxi.
```
