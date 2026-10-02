<#
.SYNOPSIS
    Nazoratchini Windows vazifasi sifatida roʻyxatga oladi — tizimga
    kirilganda oʻzi ishga tushadi.

.DESCRIPTION
    NEGA XIZMAT EMAS, VAZIFA (Scheduled Task)

    Windows xizmati (`service`) administrator huquqini va alohida
    oʻram (NSSM kabi) talab qiladi. Vazifa esa oddiy foydalanuvchi
    huquqida ishlaydi va shu mashina uchun yetarli.

    Muhimi: vazifa foydalanuvchi seansida ishlaydi, yaʼni GPU va
    Ollama ga kirish odatdagidek boʻladi. Xizmat rejimida esa alohida
    seansda ishlaydi va Ollama ni koʻrmasligi mumkin — bu aynan
    shunday oʻrnatishlarda uchraydigan qiyin nosozlik.

.PARAMETER Ochirish
    Vazifani roʻyxatdan olib tashlaydi.

.EXAMPLE
    .\scripts\xizmat-ornatish.ps1
    .\scripts\xizmat-ornatish.ps1 -Ochirish
#>

[CmdletBinding()]
param([switch]$Ochirish)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$VazifaNomi = 'UzLegal-AI'
$Ildiz = Split-Path -Parent $PSScriptRoot
$Skript = Join-Path $PSScriptRoot 'xizmat.ps1'

if ($Ochirish) {
    $topildi = $false

    if (Get-ScheduledTask -TaskName $VazifaNomi -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $VazifaNomi -Confirm:$false
        Write-Host "✓ «$VazifaNomi» vazifasi oʻchirildi."
        $topildi = $true
    }

    # Yorliq ham tekshiriladi: oʻrnatish ikki yoʻldan biri bilan
    # bajarilgan boʻlishi mumkin va foydalanuvchi qaysi biri
    # ishlaganini eslamasligi tabiiy.
    $yorliq = Join-Path ([Environment]::GetFolderPath('Startup')) 'UzLegal-AI.lnk'
    if (Test-Path $yorliq) {
        Remove-Item $yorliq -Force
        Write-Host "✓ Ishga tushish yorligʻi oʻchirildi."
        $topildi = $true
    }

    if (-not $topildi) { Write-Host "Oʻrnatilgan avtoyuklash topilmadi." }
    exit 0
}

if (-not (Test-Path $Skript)) {
    Write-Error "Nazoratchi topilmadi: $Skript"
    exit 1
}

$amal = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Skript`"" `
    -WorkingDirectory $Ildiz

$boshlanish = New-ScheduledTaskTrigger -AtLogOn

# `RestartCount` — nazoratchining OʻZI yiqilsa qayta koʻtariladi.
# Nazoratchisiz qolgan tizim aynan biz tuzatmoqchi boʻlgan holatga
# qaytardi, shuning uchun bu sozlama muhim.
$sozlama = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

# Vazifa roʻyxati administrator huquqini talab qilishi mumkin. Talab
# qilsa — «Ishga tushish» papkasiga yorliq qoʻyamiz: u oddiy
# foydalanuvchi huquqida ishlaydi va bir xil natija beradi (tizimga
# kirilganda ishga tushadi). Yagona farq — nazoratchining oʻzi yiqilsa
# avtomatik qayta koʻtarilmaydi.
try {
    Register-ScheduledTask `
        -TaskName $VazifaNomi `
        -Action $amal `
        -Trigger $boshlanish `
        -Settings $sozlama `
        -Description 'UzLegal-AI xizmatlarini kuzatadi va yiqilsa qayta koʻtaradi.' `
        -Force | Out-Null

    Write-Host "✓ «$VazifaNomi» vazifasi roʻyxatga olindi."
    Write-Host ""
    Write-Host "  Hozir ishga tushirish : Start-ScheduledTask -TaskName '$VazifaNomi'"
    Write-Host "  Holatni koʻrish       : Get-ScheduledTask -TaskName '$VazifaNomi'"
    Write-Host "  Jurnal                : $Ildiz\logs\xizmat.log"
    Write-Host "  Oʻchirish             : .\scripts\xizmat-ornatish.ps1 -Ochirish"
} catch {
    Write-Host "Vazifa roʻyxatiga yozib boʻlmadi: $($_.Exception.Message)"
    Write-Host "«Ishga tushish» papkasiga yorliq qoʻyilmoqda (administrator kerak emas)…"
    Write-Host ""

    $papka = [Environment]::GetFolderPath('Startup')
    $yorliq = Join-Path $papka 'UzLegal-AI.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $l = $shell.CreateShortcut($yorliq)
    $l.TargetPath = 'powershell.exe'
    $l.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Skript`""
    $l.WorkingDirectory = $Ildiz
    $l.Description = 'UzLegal-AI nazoratchisi'
    $l.Save()

    Write-Host "✓ Yorliq qoʻyildi: $yorliq"
    Write-Host ""
    Write-Host "  Hozir ishga tushirish : .\scripts\xizmat.ps1"
    Write-Host "  Jurnal                : $Ildiz\logs\xizmat.log"
    Write-Host "  Oʻchirish             : .\scripts\xizmat-ornatish.ps1 -Ochirish"
}
