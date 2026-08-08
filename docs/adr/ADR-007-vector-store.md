# ADR-007: LanceDB (local) / Qdrant (server)

**Holat:** ✅ Qabul qilindi
**Sana:** 2026-08-08

## Kontekst

~250 000 chunk uchun vektor saqlash kerak. Asosiy cheklov `local-dev` profilidan keladi:

> **`local-dev` da hech qanday alohida server jarayoni ishlamasligi kerak.**

Sabab: MacBook da ishlaydigan tizim `docker compose up` talab qilmasligi, oflayn ishlashi va bitta buyruq bilan ishga tushishi kerak. Bu `air-gapped` profil uchun ham muhim.

Talablar:
- Metadata bo'yicha filtrlash (versiya filtri — kritik)
- Gibrid qidiruv qo'llab-quvvatlashi yoki BM25 bilan yonma-yon ishlashi
- 250k × 1024 o'lchamli vektor (~1 GB fp16)
- Server profilida masshtablanish

## Ko'rib chiqilgan variantlar

| Variant | Server kerakmi | Metadata filtr | Masshtab | Local qulaylik |
|---------|:--------------:|:--------------:|:--------:|:--------------:|
| **LanceDB** | ❌ Yo'q (kutubxona) | ✅ Kuchli (SQL-ga o'xshash) | O'rta | ✅ Ideal |
| Qdrant | ✅ Ha | ✅ Kuchli | ✅ Yuqori | ⚠️ Docker |
| Weaviate | ✅ Ha | ✅ | ✅ | ⚠️ Og'ir |
| Chroma | ❌ Yo'q | ⚠️ Cheklangan | Past | ✅ |
| FAISS | ❌ Yo'q | ❌ **Yo'q** | ✅ | ⚠️ Metadata qo'lda |
| pgvector | ✅ Ha | ✅ | O'rta | ⚠️ Postgres |

### FAISS nima uchun rad etildi

FAISS eng tez, lekin **metadata filtrlashni qo'llab-quvvatlamaydi**. Versiya filtri bu loyihada majburiy va u qidiruv vaqtida qo'llanishi kerak. FAISS bilan variantlar:
- Filtrlashdan keyin qidirish → indeksni har safar qayta qurish, imkonsiz
- Qidirishdan keyin filtrlash → top-50 dan keyin 5 tasi qolishi mumkin, recall tushadi

Ikkalasi ham yaroqsiz.

### Chroma nima uchun rad etildi

Local uchun qulay, lekin metadata filtrlash cheklangan va 250k chunk da ishlash ko'rsatkichlari past. Prototip uchun mos, mahsulot uchun emas.

## Qaror

**`local-dev` / `workstation` / `air-gapped` → LanceDB**
**`server` / `server-scale` → Qdrant**

Ikkalasi bitta protokol orqasida:

```python
class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: NDArray) -> None: ...
    def search(self, vector: NDArray, k: int,
               filters: dict | None = None) -> list[ScoredChunk]: ...
    def delete(self, chunk_ids: list[str]) -> None: ...
    def stats(self) -> IndexStats: ...
```

Profil qaysi implementatsiya yuklanishini belgilaydi. Yuqori qatlamlar farqni bilmaydi.

### Nima uchun LanceDB

- **Kutubxona, server emas** — `pip install lancedb`, tayyor
- Lance formati — ustunli (columnar), `mmap` orqali o'qiladi, RAM ni to'ldirmaydi
- Metadata filtrlash SQL-ga o'xshash sintaksis bilan:
  ```python
  tbl.search(qvec).where("valid_to IS NULL AND status = 'in_force'").limit(50)
  ```
- Versiyalash o'rnatilgan — KB snapshotlari tabiiy
- Fayl asosida → zaxira nusxa = papkani nusxalash

### Nima uchun Qdrant server uchun

- Gorizontal masshtablash, replikatsiya
- Yuqori concurrency (50+ foydalanuvchi)
- Payload indeksi — filtrlash tez
- Yetuk operatsion vositalar (monitoring, snapshot)

## Leksik indeks (alohida qaror)

BM25 uchun:

| Profil | Yechim |
|--------|--------|
| `local-dev` | **Tantivy** (Rust, Python binding) — fayl asosida, server yo'q |
| `server` | Elasticsearch yoki Qdrant sparse vektorlari |

Muqobil: **BGE-M3 ning sparse rejimi** — u bitta modelda dense va sparse beradi, ya'ni BM25 ni butunlay almashtirishi mumkin. Bu Faza 2 da o'lchanadi:

> Agar BGE-M3 sparse rejimi o'zbek tilida Tantivy BM25 dan yomon bo'lmasa — Tantivy olib tashlanadi va stek soddalashadi.

Bu ochiq savol va u ma'lumot bilan hal qilinadi.

## Oqibatlari

### Ijobiy
- `local-dev` bitta buyruq bilan ishga tushadi, Docker kerak emas
- `air-gapped` profil tabiiy ishlaydi
- KB snapshotlari — oddiy papkalar, versiyalash oson
- Serverda masshtablanadi

### Salbiy

| Salbiy | Yumshatish |
|--------|------------|
| Ikki implementatsiyani saqlash | Protokol tor (4 metod); integratsiya testlari ikkalasida |
| Local→server migratsiya kerak | `uzlegal index migrate --from lancedb --to qdrant` |
| LanceDB Qdrant dan kamroq yetuk | Ma'lumot xom arxivdan qayta qurilishi mumkin — yo'qotish xavfi past |

## Migratsiya

```bash
uzlegal index migrate --from lancedb://kb/current --to qdrant://qdrant:6333/uzlegal
```

Chunk metadata bir xil sxemada (`schemas/chunk.schema.json`), shuning uchun migratsiya — oddiy qayta yozish. Embedding qayta hisoblanmaydi.
