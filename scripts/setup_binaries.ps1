# ==============================================================================
# RTMS v2.2.0 — Descargador y Verificador de Binarios FFmpeg
# Descarga FFmpeg con soporte DirectShow, NVENC y SRT (Gyan.dev Release Essentials)
# Con verificación estricta de integridad criptográfica SHA256
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

$ErrorActionPreference = "Stop"

$baseDir = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $baseDir "bin"
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " RTMS v2.2.0 — Verificador de Binarios FFmpeg" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path $ffmpegExe) {
    Write-Host "[OK] FFmpeg ya se encuentra instalado en: $ffmpegExe" -ForegroundColor Green
    & $ffmpegExe -version | Select-Object -First 1
    exit 0
}

Write-Host "[INFO] FFmpeg no encontrado en $binDir. Iniciando descarga segura..." -ForegroundColor Yellow

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

$downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$shaUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"
$zipPath = Join-Path $binDir "ffmpeg_temp.zip"
$shaPath = Join-Path $binDir "ffmpeg_temp.zip.sha256"

# 1. Descargar paquete ZIP y suma de verificación oficial
Write-Host "[INFO] Descargando checksum SHA256 oficial desde: $shaUrl" -ForegroundColor Cyan
Invoke-WebRequest -Uri $shaUrl -OutFile $shaPath

$expectedSha = (Get-Content -Path $shaPath -Raw).Trim().ToLower()
Write-Host "[INFO] Hash esperado: $expectedSha" -ForegroundColor Gray

Write-Host "[INFO] Descargando FFmpeg oficial desde: $downloadUrl" -ForegroundColor Cyan
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

# 2. Verificar integridad SHA256
Write-Host "[INFO] Verificando integridad criptográfica SHA256 del binario..." -ForegroundColor Cyan
$actualSha = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[INFO] Hash calculado: $actualSha" -ForegroundColor Gray

if ($actualSha -ne $expectedSha) {
    Write-Host "[ERROR] ¡FALLO DE INTEGRIDAD! El hash del archivo descargado ($actualSha) no coincide con el esperado ($expectedSha)." -ForegroundColor Red
    Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "[OK] Suma de verificación SHA256 válida y confirmada." -ForegroundColor Green
Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue

# 3. Extracción de binarios
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

Write-Host "[OK] FFmpeg instalado y verificado exitosamente en: $ffmpegExe" -ForegroundColor Green
& $ffmpegExe -version | Select-Object -First 1
