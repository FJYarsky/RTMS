# ==============================================================================
# RTMS — Real-Time Multicam System
# Descarga y verificación de integridad de binarios multimedia.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

# Automated FFmpeg & FFplay binary setup and SHA256 integrity validation
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Forzar protocolos criptograficos TLS modernos (TLS 1.2 / TLS 1.3) para descargas seguras
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

$baseDir = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $baseDir "bin"
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"
$ffplayExe = Join-Path $binDir "ffplay.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " RTMS -- Verificador de Binarios FFmpeg y FFplay" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if ((Test-Path $ffmpegExe) -and (Test-Path $ffplayExe)) {
    Write-Host "[OK] FFmpeg y FFplay ya se encuentran instalados en: $binDir" -ForegroundColor Green
    & $ffmpegExe -version | Select-Object -First 1
    exit 0
}

Write-Host "[INFO] Binarios incompletos o ausentes en $binDir. Iniciando descarga segura..." -ForegroundColor Yellow

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

$downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$shaUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"
$zipPath = Join-Path $binDir "ffmpeg_temp.zip"
$shaPath = Join-Path $binDir "ffmpeg_temp.zip.sha256"

# 1. Descargar paquete ZIP y suma de verificacion oficial
Write-Host "[INFO] Descargando checksum SHA256 oficial desde: $shaUrl" -ForegroundColor Cyan
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    curl.exe -f -sSL -A "RTMS-Installer/2.2.6" -o $shaPath $shaUrl
} else {
    Invoke-WebRequest -Uri $shaUrl -OutFile $shaPath -UseBasicParsing
}

$expectedSha = (Get-Content -Path $shaPath -Raw).Trim().ToLower()
Write-Host "[INFO] Hash esperado: $expectedSha" -ForegroundColor Gray

Write-Host "[INFO] Descargando FFmpeg oficial desde: $downloadUrl" -ForegroundColor Cyan
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    curl.exe -f -L -A "RTMS-Installer/2.2.6" -o $zipPath $downloadUrl
} else {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
}

# 2. Verificar integridad SHA256
Write-Host "[INFO] Verificando integridad criptografica SHA256 del binario..." -ForegroundColor Cyan
$actualSha = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLower()
Write-Host "[INFO] Hash calculado: $actualSha" -ForegroundColor Gray

if ($actualSha -ne $expectedSha) {
    Write-Host "[ERROR] FALLO DE INTEGRIDAD: El hash del archivo descargado no coincide con el esperado." -ForegroundColor Red
    Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "[OK] Suma de verificacion SHA256 valida y confirmada." -ForegroundColor Green
Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue

# 3. Extraccion de binarios
Write-Host "[INFO] Extrayendo archivos..." -ForegroundColor Cyan
$extractDir = Join-Path $binDir "ffmpeg_extracted"
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

$extractedExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$extractedPlay = Get-ChildItem -Path $extractDir -Recurse -Filter "ffplay.exe" | Select-Object -First 1

if ($extractedExe) {
    Move-Item -Path $extractedExe.FullName -Destination $ffmpegExe -Force
}
if ($extractedPlay) {
    Move-Item -Path $extractedPlay.FullName -Destination $ffplayExe -Force
}

Remove-Item -Path $zipPath -Force
Remove-Item -Path $extractDir -Recurse -Force

if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffplayExe)) {
    Write-Host "[ERROR] Uno o ambos binarios no pudieron ser instalados." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] FFmpeg y FFplay instalados y verificados exitosamente en: $binDir" -ForegroundColor Green
& $ffmpegExe -version | Select-Object -First 1
& $ffplayExe -version | Select-Object -First 1
 
