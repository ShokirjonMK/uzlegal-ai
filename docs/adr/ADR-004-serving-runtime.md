# ADR-004: MLX runtime (Apple Silicon)

**Holat:** ✅ Qabul qilindi
**Sana:** 2026-08-08

## Kontekst

Ishlab chiqish va `local-dev` profili MacBook Air M4 (24 GB, Metal 3) da ishlaydi. Runtime tanlanishi kerak: u ham inference, ham LoRA trening uchun ishlatiladi.

Talablar:
1. Metal GPU dan foydalanish
2. 4-bit kvantlash
3. **LoRA trening** — inference bilan bir stekda
4. Adapter tez almashtirish
5. Prefix KV-cache

## Ko'rib chiqilgan variantlar

| Runtime | Tezlik (14B 4-bit) | LoRA trening | Adapter swap | KV-cache API | Yetuklik |
|---------|-------------------|--------------|--------------|--------------|----------|
| **MLX** | ~22 tok/s | ✅ Native (`mlx_lm.lora`) | ✅ Tez | ✅ Ochiq | Yaxshi |
| llama.cpp | ~20 tok/s | ⚠️ Cheklangan | ⚠️ Qayta yuklash | ✅ | Juda yaxshi |
| Ollama | ~19 tok/s | ❌ Yo'q | ⚠️ Modelfile | ⚠️ Yashirin | Juda yaxshi |
| PyTorch MPS | ~9 tok/s | ✅ | ✅ | ✅ | Yaxshi |
| vLLM | ❌ Metal yo'q | — | — | — | (faqat CUDA) |

## Qaror

**MLX — `local-dev` va `workstation` profillari uchun.**
**vLLM — `server` profili uchun.**
**llama.cpp/GGUF — eksport formati sifatida** (moslik uchun).

### Nima uchun MLX

Hal qiluvchi omil — **bir stekda ham inference, ham trening**. Boshqa variantlarda LoRA trening uchun alohida muhit (PyTorch/HF) kerak bo'lardi, bu:
- Ikki xil model formati
- Konvertatsiya qadamlari va ular bilan bog'liq xatolar
- Trening va inference orasidagi nomuvofiqlik xavfi

MLX bilan: `mlx_lm.lora` bilan o'qitasiz, `mlx_lm.generate` bilan ishlatasiz. Bir xil format, bir xil kod.

Qo'shimcha sabablar:
- Apple tomonidan Metal uchun yozilgan, unified memory ni to'g'ri ishlatadi (host↔device nusxa yo'q)
- Adapter almashtirish API si ochiq va tez
- KV-cache to'g'ridan-to'g'ri boshqariladi — prefix cache uchun zarur ([ADR-005](ADR-005-agent-orchestration.md))
- Faol ishlab chiqilmoqda

### Nima uchun Ollama emas

Ollama qulay, lekin:
- LoRA trening yo'q — bu loyihaning yarmini bajara olmaydi
- KV-cache boshqaruvi yashirin — prefix optimizatsiyasi qilib bo'lmaydi
- Adapter almashtirish Modelfile orqali, sekin

Ollama **tez qo'lda sinov** uchun ishlatiladi, lekin mahsulot stekiga kirmaydi.

### Nima uchun vLLM server uchun

vLLM Metal ni qo'llab-quvvatlamaydi, lekin CUDA da:
- **Multi-LoRA** — beshta adapter bir vaqtda, haqiqiy parallel agentlar
- PagedAttention — yuqori throughput
- Continuous batching — ko'p foydalanuvchi

Bu `server` profilida debate vaqtini 30 s dan 6 s ga tushiradi.

## Abstraksiya

Ikki runtime bitta protokol orqasida:

```python
class InferenceBackend(Protocol):
    def load(self, model_path: str) -> None: ...
    def set_adapter(self, adapter: str | None) -> None: ...
    def generate(self, prompt: str, *, max_tokens: int,
                 temperature: float, prefix_cache: Any = None) -> str: ...
    def stream(self, prompt: str, **kw) -> Iterator[str]: ...
    def make_cache(self, prefix: str) -> Any: ...
```

`MLXBackend` va `VLLMBackend` — ikki amalga oshirish. Profil qaysi birini yuklashni belgilaydi. Yuqori qatlamlar (agents, orchestrator) farqni bilmaydi.

Ikkita real amalga oshirish borligi abstraksiyaning haqiqatan ishlashini isbotlaydi — bitta implementatsiyali interfeys odatda noto'g'ri chegaralarga ega bo'ladi.

## Oqibatlari

### Ijobiy
- Local da to'liq ish sikli: trening → inference → baholash, hammasi bitta mashinada
- Bepul (bulut GPU shart emas)
- Oflayn ishlaydi
- Serverda avtomatik yaxshilanadi (vLLM)

### Salbiy

| Salbiy | Yumshatish |
|--------|------------|
| MLX ekotizimi PyTorch dan kichik | Asosiy funksiyalar mavjud; kerak bo'lsa PyTorch fallback |
| **Docker ichida Metal ishlamaydi** | `local-dev` da native ishga tushiriladi; Docker faqat yordamchi servislar |
| Trening sekin (~10 soat/adapter) | Bulutda A100 (~$12 barcha adapterlar); local — zaxira variant |
| Ikki backend saqlanishi kerak | Protokol qat'iy va tor; integratsiya testlari ikkalasida ham |

## Tekshirish

```bash
python -c "import mlx.core as mx; print('Metal:', mx.metal.is_available())"
uzlegal doctor
```

`uzlegal doctor` tekshiradi: Metal mavjudligi, wired limit sozlamasi, model fayllari, KB, disk joyi, Python versiyasi.
