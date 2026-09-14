# ==============================================================================
# RTMS v2.0.3 — Descargador y Verificador de Binarios FFmpeg
# Descarga FFmpeg con soporte DirectShow, NVENC y SRT (Gyan.dev Release Essentials)
# ==============================================================================

$ErrorActionPreference = "Stop"

$baseDir = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $baseDir "bin"
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " RTMS v2.0.3 — Verificador de Binarios FFmpeg" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path $ffmpegExe) {
    Write-Host "[OK] FFmpeg ya se encuentra instalado en: $ffmpegExe" -ForegroundColor Green
    & $ffmpegExe -version | Select-Object -First 1
    exit 0
}

Write-Host "[INFO] FFmpeg no encontrado en $binDir. Iniciando descarga automatica..." -ForegroundColor Yellow

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

$downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$zipPath = Join-Path $binDir "ffmpeg_temp.zip"

Write-Host "[INFO] Descargando FFmpeg oficial desde: $downloadUrl" -ForegroundColor Cyan
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

Write-Host "[INFO] Extrayendo archivos..." -ForegroundColor Cyan
$extractDir = Join-Path $binDir "ffmpeg_extracted"
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

$extractedExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$extractedPlay = Get-ChildItem -Path $extractDir -Recurse -Filter "ffplay.exe" | Select-Object -First 1

if ($extractedExe) {
    Move-Item -Path $extractedExe.FullName -Destination $ffmpegExe -Force
}
if ($extractedPlay) {
    Move-Item -Path $extractedPlay.FullName -Destination (Join-Path $binDir "ffplay.exe") -Force
}

Remove-Item -Path $zipPath -Force
Remove-Item -Path $extractDir -Recurse -Force

Write-Host "[OK] FFmpeg instalado exitosamente en: $ffmpegExe" -ForegroundColor Green
& $ffmpegExe -version | Select-Object -First 1
