# Loyiha imzosi — uzlegal-ai

## Muallif

```
Ism:       Shokirjon Madaminov
Taxallus:  MKdev
GitHub:    @ShokirjonMK
Telegram:  @ceoNeuron
Loyiha:    uzlegal-ai — Oʻzbekiston huquqiy AI platformasi
```

## Kriptografik imzo

Bu loyihaning barcha commitlari **Ed25519 SSH kaliti** bilan imzolangan.
Imzo faqat muallifning shaxsiy kaliti bilan yaratiladi — boshqa hech kim
(shu jumladan AI) soxtalashtira olmaydi.

### Ochiq kalit (Public Key)

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINT0Dzb7SrZOP5Z/Tqz4VA3qVRSTSCwbLTzB6P/3wrmz
```

**Fingerprint:** `SHA256:mwL9hmF/G8XF84g4ewAwlHbrAokdTzWVKixP+L8dwH0`

### Tekshirish

```bash
# Commitning imzosini tekshirish
git log --show-signature -1

# Barcha commitlarni tekshirish
git log --format='%H %G? %GK %s' | head -20
# G = good (imzo toʻgʻri), N = no signature, B = bad

# Loyiha yaxlitligini tekshirish
./scripts/verify-integrity.sh
```

### Nima uchun bu soxtalashtirish mumkin emas

1. **Ed25519** — 128-bit xavfsizlik darajasi, kvant kompyuterlar oldida ham
   bardoshli (RSA dan kuchli)
2. **Shaxsiy kalit** — faqat muallifning mashinasida (`~/.ssh/`), hech qachon
   repoga tushmaydi
3. **HMAC-SHA256** — loyiha yaxlitligi alohida sir bilan himoyalangan
4. **Git imzosi** — har bir commit alohida imzolanadi, tarixni oʻzgartirish
   imzoni buzadi
5. **GitHub Verified** — GitHub da ochiq kalit roʻyxatdan oʻtkazilsa, commitlar
   "Verified" belgisi oladi

### GitHub da "Verified" belgisi olish

```bash
# Ochiq kalitni GitHub ga qoʻshish:
# Settings → SSH and GPG keys → New SSH Key
# Key type: Signing Key
# Quyidagini joylashtiring:
cat ~/.ssh/id_ed25519_signing.pub
```
