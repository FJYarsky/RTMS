# ==============================================================================
# RTMS — Real-Time Multicam System
# Descarga y verificación de binarios multimedia (FFmpeg, FFplay, MediaMTX).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Forzar protocolos criptograficos TLS modernos (TLS 1.2 / TLS 1.3) para descargas seguras
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

$baseDir = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $baseDir "bin"
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"
$ffplayExe = Join-Path $binDir "ffplay.exe"
$mediamtxExe = Join-Path $binDir "mediamtx.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " RTMS -- Verificador de Binarios Multimedia (FFmpeg / MediaMTX)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

# ----------------------------------------------------------------------
# 1. APROVISIONAMIENTO DE FFMPEG & FFPLAY
# ----------------------------------------------------------------------
if ((Test-Path $ffmpegExe) -and (Test-Path $ffplayExe)) {
    Write-Host "[OK] FFmpeg y FFplay ya se encuentran instalados en: $binDir" -ForegroundColor Green
} else {
    Write-Host "[INFO] FFmpeg o FFplay ausentes en $binDir. Iniciando descarga segura..." -ForegroundColor Yellow

    $downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    $shaUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"
    $zipPath = Join-Path $binDir "ffmpeg_temp.zip"
    $shaPath = Join-Path $binDir "ffmpeg_temp.zip.sha256"

    Write-Host "[INFO] Descargando checksum SHA256 oficial de FFmpeg..." -ForegroundColor Cyan
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        curl.exe -f -sSL -A "RTMS-Installer/2.5.0" -o $shaPath $shaUrl
    } else {
        Invoke-WebRequest -Uri $shaUrl -OutFile $shaPath -UseBasicParsing
    }

    $expectedSha = (Get-Content -Path $shaPath -Raw).Trim().ToLower()
    Write-Host "[INFO] Hash esperado FFmpeg: $expectedSha" -ForegroundColor Gray

    Write-Host "[INFO] Descargando paquete oficial de FFmpeg..." -ForegroundColor Cyan
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        curl.exe -f -L -A "RTMS-Installer/2.5.0" -o $zipPath $downloadUrl
    } else {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
    }

    Write-Host "[INFO] Verificando integridad criptografica SHA256..." -ForegroundColor Cyan
    $actualSha = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLower()
    if ($actualSha -ne $expectedSha) {
        Write-Host "[ERROR] FALLO DE INTEGRIDAD: El hash de FFmpeg no coincide con el esperado." -ForegroundColor Red
        Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue
        exit 1
    }

    Write-Host "[OK] Suma de verificacion SHA256 de FFmpeg confirmada." -ForegroundColor Green
    Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue

    Write-Host "[INFO] Extrayendo FFmpeg y FFplay..." -ForegroundColor Cyan
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
}

# ----------------------------------------------------------------------
# 2. APROVISIONAMIENTO DE MEDIAMTX
# ----------------------------------------------------------------------
$mediamtxVersion = "v1.9.3"
$mediamtxSha = "af2ce0dce3201e10c39dae4e6d8e52c983d6940b1fa0fdd7f3d16c87ac764626"
$mediamtxUrl = "https://github.com/bluenviron/mediamtx/releases/download/$mediamtxVersion/mediamtx_${mediamtxVersion}_windows_amd64.zip"

if (Test-Path $mediamtxExe) {
    Write-Host "[OK] MediaMTX ya se encuentra instalado en: $mediamtxExe" -ForegroundColor Green
} else {
    Write-Host "[INFO] MediaMTX no encontrado en $binDir. Iniciando descarga segura..." -ForegroundColor Yellow
    $mtxZipPath = Join-Path $binDir "mediamtx_temp.zip"

    Write-Host "[INFO] Descargando MediaMTX $mediamtxVersion oficial desde GitHub Releases..." -ForegroundColor Cyan
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        curl.exe -f -L -A "RTMS-Installer/2.5.0" -o $mtxZipPath $mediamtxUrl
    } else {
        Invoke-WebRequest -Uri $mediamtxUrl -OutFile $mtxZipPath -UseBasicParsing
    }

    Write-Host "[INFO] Verificando integridad criptografica SHA256 de MediaMTX..." -ForegroundColor Cyan
    $mtxActualSha = (Get-FileHash -Path $mtxZipPath -Algorithm SHA256).Hash.ToLower()
    if ($mtxActualSha -ne $mediamtxSha) {
        Write-Host "[ERROR] FALLO DE INTEGRIDAD: El hash de MediaMTX no coincide con el esperado ($mediamtxSha)." -ForegroundColor Red
        Remove-Item -Path $mtxZipPath -Force -ErrorAction SilentlyContinue
        exit 1
    }

    Write-Host "[OK] Suma de verificacion SHA256 de MediaMTX confirmada." -ForegroundColor Green

    Write-Host "[INFO] Extrayendo mediamtx.exe..." -ForegroundColor Cyan
    $mtxExtractDir = Join-Path $binDir "mediamtx_extracted"
    Expand-Archive -Path $mtxZipPath -DestinationPath $mtxExtractDir -Force

    $extractedMtx = Get-ChildItem -Path $mtxExtractDir -Recurse -Filter "mediamtx.exe" | Select-Object -First 1
    if ($extractedMtx) {
        Move-Item -Path $extractedMtx.FullName -Destination $mediamtxExe -Force
    }

    Remove-Item -Path $mtxZipPath -Force
    Remove-Item -Path $mtxExtractDir -Recurse -Force
}

# ----------------------------------------------------------------------
# 3. VERIFICACION FINAL DE INTEGRIDAD DE TODOS LOS BINARIOS
# ----------------------------------------------------------------------
if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffplayExe) -or -not (Test-Path $mediamtxExe)) {
    Write-Host "[ERROR] Uno o mas binarios multimedia requeridos no pudieron ser instalados." -ForegroundColor Red
    exit 1
}

Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[EXITO] Todos los binarios multimedia estan verificados y listos:" -ForegroundColor Green
& $ffmpegExe -version | Select-Object -First 1
& $ffplayExe -version | Select-Object -First 1
& $mediamtxExe --version | Select-Object -First 1
Write-Host "============================================================" -ForegroundColor Cyan
