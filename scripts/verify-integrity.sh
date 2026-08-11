#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# uzlegal-ai — Loyiha yaxlitligini tekshirish
# Muallif: ShokirjonMK (MKdev) @ceoNeuron
#
# Bu skript loyiha fayllarining HMAC-SHA256 imzosini tekshiradi.
# Soxtalashtirish mumkin EMAS — HMAC siri faqat muallif mashinasida.
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MANIFEST="$PROJECT_DIR/.integrity-manifest.sig"
SECRET_FILE="$HOME/.ssh/.uzlegal-signing-secret"

# ── Loyiha banner ──────────────────────────────────────────────────────
echo -e "${CYAN}"
cat << 'BANNER'
  ╔═══════════════════════════════════════════════════════════════╗
  ║                                                               ║
  ║   ██╗   ██╗███████╗██╗     ███████╗ ██████╗  █████╗ ██╗      ║
  ║   ██║   ██║╚══███╔╝██║     ██╔════╝██╔════╝ ██╔══██╗██║      ║
  ║   ██║   ██║  ███╔╝ ██║     █████╗  ██║  ███╗███████║██║      ║
  ║   ██║   ██║ ███╔╝  ██║     ██╔══╝  ██║   ██║██╔══██║██║      ║
  ║   ╚██████╔╝███████╗███████╗███████╗╚██████╔╝██║  ██║███████╗ ║
  ║    ╚═════╝ ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ║
  ║                                                               ║
  ║   Muallif: ShokirjonMK · MKdev · @ceoNeuron                  ║
  ║   Ed25519 + HMAC-SHA256 kriptografik himoya                   ║
  ║                                                               ║
  ╚═══════════════════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# ── Funksiyalar ────────────────────────────────────────────────────────

compute_manifest() {
    cd "$PROJECT_DIR"
    find src/ configs/ scripts/ docs/ -type f \
        -not -path '*.pyc' \
        -not -path '*__pycache__*' \
        -not -path '*.egg-info*' \
        2>/dev/null | sort | while read -r f; do
        sha256sum "$f" 2>/dev/null || shasum -a 256 "$f"
    done
}

sign_manifest() {
    if [[ ! -f "$SECRET_FILE" ]]; then
        echo -e "${RED}XATO: Imzolash siri topilmadi: $SECRET_FILE${NC}"
        echo "Bu faqat muallif mashinasida mavjud."
        exit 1
    fi

    local secret
    secret=$(cat "$SECRET_FILE")

    echo -e "${YELLOW}Manifest hisoblanmoqda...${NC}"
    local manifest_hash
    manifest_hash=$(compute_manifest | openssl dgst -sha256 -hmac "$secret" -hex 2>/dev/null | awk '{print $NF}')

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local git_hash
    git_hash=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "uncommitted")

    cat > "$MANIFEST" << SIGEOF
# uzlegal-ai integrity manifest
# Soxtalashtirish mumkin emas — HMAC-SHA256 siri faqat muallif mashinasida
#
# Muallif:     ShokirjonMK (MKdev) @ceoNeuron
# Vaqt:        $timestamp
# Git commit:  $git_hash
# Algoritm:    HMAC-SHA256
# Kalit:       Ed25519 SHA256:R4s0AF7cVC018xjK1s3jLusb67r/JoLXFqYKo2WlHkI
#
HMAC=$manifest_hash
TIMESTAMP=$timestamp
COMMIT=$git_hash
SIGNER=ShokirjonMK:MKdev:@ceoNeuron
KEY_FINGERPRINT=SHA256:R4s0AF7cVC018xjK1s3jLusb67r/JoLXFqYKo2WlHkI
SIGEOF

    echo -e "${GREEN}Manifest imzolandi: $MANIFEST${NC}"
    echo -e "  HMAC:   ${manifest_hash:0:16}...${manifest_hash: -16}"
    echo -e "  Commit: $git_hash"
    echo -e "  Vaqt:   $timestamp"
}

verify_manifest() {
    if [[ ! -f "$MANIFEST" ]]; then
        echo -e "${RED}XATO: Manifest topilmadi: $MANIFEST${NC}"
        echo "Avval imzolang: $0 sign"
        exit 1
    fi

    if [[ ! -f "$SECRET_FILE" ]]; then
        echo -e "${RED}XATO: Imzolash siri topilmadi — faqat muallif tekshira oladi${NC}"
        echo ""
        echo "Agar siz muallif bo'lmasangiz, git imzosini tekshiring:"
        echo "  git log --show-signature -1"
        exit 1
    fi

    local secret
    secret=$(cat "$SECRET_FILE")

    echo -e "${YELLOW}Yaxlitlik tekshirilmoqda...${NC}"

    local saved_hmac
    saved_hmac=$(grep "^HMAC=" "$MANIFEST" | cut -d= -f2)

    local current_hmac
    current_hmac=$(compute_manifest | openssl dgst -sha256 -hmac "$secret" -hex 2>/dev/null | awk '{print $NF}')

    echo ""
    if [[ "$saved_hmac" == "$current_hmac" ]]; then
        echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✅ YAXLITLIK TASDIQLANDI                 ║${NC}"
        echo -e "${GREEN}║  Fayllar o'zgartirilmagan                 ║${NC}"
        echo -e "${GREEN}║  Imzo: ShokirjonMK · MKdev · @ceoNeuron   ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
    else
        echo -e "${RED}╔═══════════════════════════════════════════╗${NC}"
        echo -e "${RED}║  ❌ YAXLITLIK BUZILGAN!                   ║${NC}"
        echo -e "${RED}║  Fayllar imzolangandan keyin o'zgargan     ║${NC}"
        echo -e "${RED}║  Qayta imzolang: ./scripts/verify-integrity.sh sign ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════╝${NC}"
        echo ""
        echo "Saqlangan HMAC:  ${saved_hmac:0:16}..."
        echo "Hozirgi HMAC:    ${current_hmac:0:16}..."
        exit 1
    fi
}

verify_git_signatures() {
    echo ""
    echo -e "${CYAN}Git commit imzolari:${NC}"
    echo "─────────────────────────────────────────"

    local total=0
    local signed=0
    local unsigned=0

    while IFS=' ' read -r hash status rest; do
        total=$((total + 1))
        if [[ "$status" == "G" ]]; then
            signed=$((signed + 1))
            echo -e "  ${GREEN}✅ ${hash:0:8}${NC} $rest"
        else
            unsigned=$((unsigned + 1))
            echo -e "  ${YELLOW}⚠️  ${hash:0:8}${NC} $rest (imzosiz)"
        fi
    done < <(git -C "$PROJECT_DIR" log --format='%H %G? %s' -20 2>/dev/null)

    echo "─────────────────────────────────────────"
    echo -e "  Jami: $total | ${GREEN}Imzolangan: $signed${NC} | ${YELLOW}Imzosiz: $unsigned${NC}"
}

# ── Asosiy ─────────────────────────────────────────────────────────────

case "${1:-verify}" in
    sign)
        sign_manifest
        verify_git_signatures
        ;;
    verify)
        verify_manifest
        verify_git_signatures
        ;;
    git)
        verify_git_signatures
        ;;
    *)
        echo "Foydalanish: $0 [sign|verify|git]"
        echo ""
        echo "  sign   — Loyiha manifestini imzolash (faqat muallif)"
        echo "  verify — Yaxlitlikni tekshirish (faqat muallif)"
        echo "  git    — Git commit imzolarini tekshirish (hamma)"
        ;;
esac
