<#
.SYNOPSIS
    UzLegal-AI xizmatlarini ishga tushiradi va yiqilsa qayta koʻtaradi.

.DESCRIPTION
    NEGA BU SKRIPT KERAK BOʻLDI

    2026-08-25 da kompyuter qayta yuklandi va shundan keyin HECH NARSA
    oʻzi koʻtarilmadi: yadro yoʻq, veb yoʻq, Ollama yoʻq. Ishlagan
    sozlama faqat bitta terminal sessiyasining xotirasida yashagan edi.

    Foydalanuvchi sinovini oʻchib qoladigan mahsulotda oʻtkazib
    boʻlmaydi — shuning uchun bu birinchi vazifa.

    NEGA NAZORATCHI, NEGA FAQAT ISHGA TUSHIRISH EMAS

    Uch jarayonning har biri turli sabablarga koʻra yiqilishi mumkin:
    Ollama xotira yetmasa, yadro indeks buzilsa, veb port band boʻlsa.
    Bir marta ishga tushirib qoʻyish yetarli emas — kimdir qarab
    turishi kerak. Bu skript aynan shuni qiladi.

    NIMA QILA OLMAYDI

    Litsenziyani OʻZI yarata olmaydi — u muallifning maxfiy kaliti
    bilan imzolanadi. Litsenziya yoʻq boʻlsa skript buni aniq aytadi
    va nima qilish kerakligini koʻrsatadi.

.PARAMETER Bir
    Bir marta ishga tushiradi va nazorat qilmaydi. Nosozlik qidirish uchun.

.PARAMETER IntervalSec
    Tekshirish oraligʻi (standart 30 soniya).

.EXAMPLE
    .\scripts\xizmat.ps1
    .\scripts\xizmat.ps1 -Bir
#>

[CmdletBinding()]
param(
    [switch]$Bir,
    [int]$IntervalSec = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Ildiz = Split-Path -Parent $PSScriptRoot
$LogKatalog = Join-Path $Ildiz 'logs'
if (-not (Test-Path $LogKatalog)) { New-Item -ItemType Directory -Path $LogKatalog | Out-Null }

function Yoz([string]$Daraja, [string]$Xabar) {
    $vaqt = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $qator = "$vaqt [$Daraja] $Xabar"
    Write-Host $qator
    Add-Content -Path (Join-Path $LogKatalog 'xizmat.log') -Value $qator -Encoding utf8
}

# --------------------------------------------------------------------------- #
# Muhit
#
# `.env` ildizda va u .gitignore da — litsenziya kaliti shu yerda yashaydi.
# Sabab: muhit oʻzgaruvchisi terminal yopilganda yoʻqoladi, fayl esa qoladi.
# --------------------------------------------------------------------------- #

function MuhitniOqi {
    $envFayl = Join-Path $Ildiz '.env'
    if (-not (Test-Path $envFayl)) { return }
    foreach ($qator in Get-Content $envFayl -Encoding utf8) {
        $t = $qator.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $bolinish = $t.IndexOf('=')
        if ($bolinish -lt 1) { continue }
        $nom = $t.Substring(0, $bolinish).Trim()
        $qiymat = $t.Substring($bolinish + 1).Trim().Trim('"')
        Set-Item -Path "env:$nom" -Value $qiymat
    }
    Yoz 'INFO' '.env oʻqildi'
}

function LitsenziyaBormi {
    if ($env:UZLEGAL_LICENSE) { return $true }
    if ($env:UZLEGAL_LICENSE_FILE -and (Test-Path $env:UZLEGAL_LICENSE_FILE)) { return $true }
    return (Test-Path (Join-Path $Ildiz 'license.key'))
}

# --------------------------------------------------------------------------- #
# Tiriklik tekshiruvi
#
# Jarayon MAVJUDLIGI yetarli emas: yadro qotib qolishi va portni ushlab
# turishi mumkin. Shuning uchun HTTP javobi tekshiriladi.
# --------------------------------------------------------------------------- #

function Tirikmi([string]$Url, [int]$TimeoutSec = 5) {
    try {
        $j = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing
        return $j.StatusCode -eq 200
    } catch {
        return $false
    }
}

$Xizmatlar = @(
    @{
        Nom     = 'ollama'
        Url     = 'http://localhost:11434/api/tags'
        Ishga   = { Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden }
        Majburiy = $false   # yoʻq boʻlsa qidiruv baribir ishlaydi
    },
    @{
        Nom     = 'yadro'
        Url     = 'http://localhost:8080/v1/health'
        Ishga   = {
            $exe = Join-Path $Ildiz '.venv\Scripts\uzlegal.exe'
            if (-not (Test-Path $exe)) { $exe = 'uzlegal' }
            Start-Process -FilePath $exe -ArgumentList 'serve' `
                -WorkingDirectory $Ildiz -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $LogKatalog 'yadro.log') `
                -RedirectStandardError  (Join-Path $LogKatalog 'yadro.err.log')
        }
        Majburiy = $true
    },
    @{
        Nom     = 'veb'
        Url     = 'http://localhost:3000/norma'
        Ishga   = {
            Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'start' `
                -WorkingDirectory (Join-Path $Ildiz 'web') -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $LogKatalog 'veb.log') `
                -RedirectStandardError  (Join-Path $LogKatalog 'veb.err.log')
        }
        Majburiy = $true
    }
)

function Tekshir {
    foreach ($x in $Xizmatlar) {
        if (Tirikmi $x.Url) { continue }

        if ($x.Nom -eq 'yadro' -and -not (LitsenziyaBormi)) {
            Yoz 'XATO' 'Litsenziya yoʻq — yadro ishga tushirilmaydi.'
            Yoz 'XATO' '  Yechim: `uzlegal license issue "<nom>" --out license.key`'
            Yoz 'XATO' '  yoki .env faylga UZLEGAL_LICENSE=... yozing.'
            continue
        }

        Yoz 'OGOH' "$($x.Nom) javob bermayapti — ishga tushirilmoqda"
        try {
            & $x.Ishga
        } catch {
            $daraja = if ($x.Majburiy) { 'XATO' } else { 'OGOH' }
            Yoz $daraja "$($x.Nom) ishga tushmadi: $($_.Exception.Message)"
        }
    }
}

# --------------------------------------------------------------------------- #

MuhitniOqi

if (-not (LitsenziyaBormi)) {
    Yoz 'OGOH' 'Litsenziya topilmadi. Yadro ishlamaydi, qolganlari ishga tushadi.'
}

Yoz 'INFO' "Nazoratchi boshlandi (oraliq ${IntervalSec}s, ildiz: $Ildiz)"
Tekshir

if ($Bir) {
    Yoz 'INFO' 'Bir martalik rejim — nazorat qilinmaydi.'
    exit 0
}

while ($true) {
    Start-Sleep -Seconds $IntervalSec
    Tekshir
}
