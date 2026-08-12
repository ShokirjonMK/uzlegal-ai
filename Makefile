.DEFAULT_GOAL := help
.PHONY: help setup-mac setup-linux doctor lint test test-e2e eval-smoke eval-full serve ingest index train bench clean

help:  ## Buyruqlar ro'yxati
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup-mac:  ## Apple Silicon muhitini o'rnatish (MLX)
	brew install python@3.11
	uv venv --python 3.11 .venv
	. .venv/bin/activate && uv pip install -e ".[mac,dev,rag]"
	@echo ""
	@echo "GPU chegarasini oshirish uchun (bir marta):"
	@echo "  sudo sysctl iogpu.wired_limit_mb=20480"

setup-linux:  ## Linux muhitini o'rnatish (model Ollama yoki vLLM da)
	uv venv --python 3.11 .venv
	. .venv/bin/activate && uv pip install -e ".[dev,rag]"
	@echo ""
	@echo "Model serveri kerak. Eng osoni:"
	@echo "  curl -fsSL https://ollama.com/install.sh | sh"
	@echo "  ollama pull gemma3:12b && uzlegal models use ollama-gemma3-12b"

doctor:  ## Muhit diagnostikasi
	uzlegal doctor

lint:  ## ruff + mypy --strict + import-linter
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy --strict src/uzlegal
	lint-imports

test:  ## unit + integration testlar
	pytest tests/unit tests/integration -v --cov=src/uzlegal --cov-report=term-missing

test-e2e:  ## e2e testlar (mini-kb fixture bilan)
	pytest tests/e2e -v

eval-smoke:  ## Tez sifat tekshiruvi (50 savol, ~5 daq)
	uzlegal eval run --suite smoke-50 --fail-under 0.75
	uzlegal eval safety --suite traps-30 --max-failures 2
	uzlegal eval citations --strict

eval-full:  ## To'liq baholash (gold-500, ~2 soat)
	uzlegal eval run --suite gold-500 --out reports/eval-full.md
	uzlegal eval compare --baseline releases/current

serve:  ## API + Web (local-dev)
	uzlegal serve --profile local-dev

ingest:  ## Bilim bazasini qurish — 20 ustuvor kodeks (~7 daqiqa)
	uzlegal kb sync
	uzlegal index build

ingest-full:  ## To'liq korpus — lex.uz katalogini kashf qilib yuklash
	@echo "DIQQAT: robots.txt Crawl-delay 20 s. 40 000 hujjat ≈ 17 kun."
	uzlegal kb discover
	uzlegal kb sync
	uzlegal index build

index-update:  ## Inkremental yangilash — faqat o'zgarganlari
	uzlegal kb sync
	uzlegal index build

train:  ## Rol adapterini o'qitish — make train ROLE=advocate
	uzlegal train lora --role $(ROLE) --config configs/training/role-lora.yaml

bench:  ## Baza model nomzodlarini solishtirish (Faza 0)
	uzlegal models bench --suite bench-uz-legal-v0 --out reports/model-selection.md

clean:  ## Vaqtinchalik fayllarni tozalash
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
