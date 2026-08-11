# uzlegal-ai — ish qoidalari

## Git: push uchun doimiy ruxsat berilgan

Repo egasi (ShokirjonMK) quyidagilarga **oldindan va doimiy ruxsat** bergan.
Bular uchun har safar soʻrash **shart emas** — soʻramasdan bajaring:

- `git add`, `git commit`
- `git push` — shu jumladan **toʻgʻridan-toʻgʻri `main` shoxiga**
- `git pull`, `git fetch`
- Yangi branch ochish va uni push qilish

Standart "push faqat soʻralganda" va "`main` da boʻlsang avval branch och"
qoidalari bu repoda **qoʻllanmaydi**. Ish tugagach oʻzingiz commit qilib
push qilavering.

Xabar berish kifoya — ruxsat soʻrash kerak emas: nima push qilinganini
qisqacha ayting (commit sarlavhasi va shox nomi).

### Baribir soʻralishi kerak boʻlgan holatlar

Ruxsat faqat yuqoridagilarga tegishli. Bular hamon tasdiq talab qiladi:

- `git push --force` / `--force-with-lease` (tarixni qayta yozish)
- `git reset --hard`, `git rebase` — push qilingan commitlar ustida
- Branch yoki tegni oʻchirish (`git push --delete`)
- Repo sozlamalarini oʻzgartirish (visibility, collaborators, secrets)
- GitHub Actions ish oqimlarini (`.github/workflows/`) oʻzgartirish
- Release yasash yoki paket nashr qilish

## Maxfiy maʼlumot

`.env`, kalitlar, tokenlar — hech qachon commitga tushmasin. `.env.example`
namuna sifatida saqlanadi, haqiqiy qiymatlar bilan emas.

Push qilishdan oldin `git status` bilan nima ketayotganini koʻring —
`data/`, `models/`, `.venv/` ichidagi katta fayllar tasodifan qoʻshilib
qolmasin.
