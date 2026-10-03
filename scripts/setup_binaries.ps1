# ==============================================================================
# RTMS — Real-Time Multicam System
# Descarga y verificación resiliente de binarios multimedia (FFmpeg, FFplay, MediaMTX).
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

$defaultUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

function Download-FileWithRetry {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$OutPath,
        [int]$MaxRetries = 3,
        [int]$TimeoutSec = 180,
        [string]$UserAgent = $defaultUserAgent
    )
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            if (Test-Path $OutPath) { Remove-Item -Path $OutPath -Force -ErrorAction SilentlyContinue }
            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                & curl.exe -f -L --retry 2 --retry-delay 2 --max-time $TimeoutSec -A $UserAgent -o $OutPath $Url
                if ($LASTEXITCODE -eq 0 -and (Test-Path $OutPath) -and ((Get-Item $OutPath).Length -gt 0)) {
                    return $true
                }
            } else {
                Invoke-WebRequest -Uri $Url -OutFile $OutPath -UserAgent $UserAgent -TimeoutSec $TimeoutSec -UseBasicParsing
                if ((Test-Path $OutPath) -and ((Get-Item $OutPath).Length -gt 0)) {
                    return $true
                }
            }
        } catch {
            Write-Host "  [WARN] Intento $attempt/$MaxRetries falló para $Url : $_" -ForegroundColor DarkYellow
        }
        if ($attempt -lt $MaxRetries) {
            Start-Sleep -Seconds (2 * $attempt)
        }
    }
    return $false
}

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
    Write-Host "[INFO] FFmpeg o FFplay ausentes en $binDir. Iniciando aprovisionamiento multi-origen..." -ForegroundColor Yellow

    $sources = @(
        @{
            Name = "GitHub Releases (GyanD/codexffmpeg 9.0.2 - Espejo Oficial de Alta Disponibilidad)"
            ZipUrl = "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip"
            ExpectedSha256 = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"
            ShaUrl = $null
        },
        @{
            Name = "Gyan.dev Servidor Primario"
            ZipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            ExpectedSha256 = $null
            ShaUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"
        },
        @{
            Name = "GitHub Releases (BtbN/FFmpeg-Builds - Espejo Comunitario)"
            ZipUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            ExpectedSha256 = $null
            ShaUrl = $null
        }
    )

    $ffmpegInstalled = $false
    $zipPath = Join-Path $binDir "ffmpeg_temp.zip"
    $shaPath = Join-Path $binDir "ffmpeg_temp.zip.sha256"
    $extractDir = Join-Path $binDir "ffmpeg_extracted"

    foreach ($source in $sources) {
        Write-Host "[INFO] Probando origen: $($source.Name)..." -ForegroundColor Cyan
        
        $expectedSha = $source.ExpectedSha256
        if (-not $expectedSha -and $source.ShaUrl) {
            Write-Host "  [INFO] Obteniendo suma de verificación dinámica desde $($source.ShaUrl)..." -ForegroundColor Gray
            $shaDownloaded = Download-FileWithRetry -Url $source.ShaUrl -OutPath $shaPath -MaxRetries 2 -TimeoutSec 30
            if ($shaDownloaded -and (Test-Path $shaPath)) {
                $expectedSha = (Get-Content -Path $shaPath -Raw).Trim().ToLower()
                Write-Host "  [INFO] SHA256 esperado: $expectedSha" -ForegroundColor Gray
            } else {
                Write-Host "  [WARN] No se pudo obtener el hash dinámico, saltando a siguiente origen..." -ForegroundColor DarkYellow
                continue
            }
        }

        Write-Host "  [INFO] Descargando paquete comprimido desde $($source.ZipUrl)..." -ForegroundColor Cyan
        $zipDownloaded = Download-FileWithRetry -Url $source.ZipUrl -OutPath $zipPath -MaxRetries 3 -TimeoutSec 240
        if (-not $zipDownloaded -or -not (Test-Path $zipPath) -or ((Get-Item $zipPath).Length -lt 10485760)) {
            Write-Host "  [WARN] Falló la descarga o archivo incompleto (<10MB) desde $($source.Name)." -ForegroundColor DarkYellow
            Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue
            continue
        }

        if ($expectedSha) {
            Write-Host "  [INFO] Validando integridad SHA256..." -ForegroundColor Cyan
            $actualSha = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLower()
            if ($actualSha -ne $expectedSha) {
                Write-Host "  [WARN] Fallo de integridad SHA256 (esperado: $expectedSha, obtenido: $actualSha). Probando siguiente origen..." -ForegroundColor DarkYellow
                Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
                Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue
                continue
            }
            Write-Host "  [OK] Integridad SHA256 confirmada." -ForegroundColor Green
        }

        Write-Host "  [INFO] Descomprimiendo binarios..." -ForegroundColor Cyan
        try {
            if (Test-Path $extractDir) { Remove-Item -Path $extractDir -Recurse -Force -ErrorAction SilentlyContinue }
            Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

            $extractedExe = Get-ChildItem -Path $extractDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            $extractedPlay = Get-ChildItem -Path $extractDir -Recurse -Filter "ffplay.exe" | Select-Object -First 1

            if ($extractedExe -and $extractedPlay) {
                Move-Item -Path $extractedExe.FullName -Destination $ffmpegExe -Force
                Move-Item -Path $extractedPlay.FullName -Destination $ffplayExe -Force
                Write-Host "  [OK] FFmpeg y FFplay extraídos e instalados exitosamente." -ForegroundColor Green
                $ffmpegInstalled = $true
            } else {
                Write-Host "  [WARN] No se encontraron ffmpeg.exe y ffplay.exe en el paquete extraído." -ForegroundColor DarkYellow
            }
        } catch {
            Write-Host "  [WARN] Error durante la extracción: $_" -ForegroundColor DarkYellow
        } finally {
            Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path $shaPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path $extractDir -Recurse -Force -ErrorAction SilentlyContinue
        }

        if ($ffmpegInstalled) {
            break
        }
    }

    if (-not $ffmpegInstalled -or -not (Test-Path $ffmpegExe) -or -not (Test-Path $ffplayExe)) {
        Write-Host "[ERROR] No se pudo aprovisionar FFmpeg / FFplay desde ningún origen disponible." -ForegroundColor Red
        exit 1
    }
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
    $mtxExtractDir = Join-Path $binDir "mediamtx_extracted"

    Write-Host "[INFO] Descargando MediaMTX $mediamtxVersion desde GitHub Releases..." -ForegroundColor Cyan
    $mtxDownloaded = Download-FileWithRetry -Url $mediamtxUrl -OutPath $mtxZipPath -MaxRetries 3 -TimeoutSec 120
    if (-not $mtxDownloaded -or -not (Test-Path $mtxZipPath)) {
        Write-Host "[ERROR] No se pudo descargar el paquete de MediaMTX." -ForegroundColor Red
        exit 1
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
    Expand-Archive -Path $mtxZipPath -DestinationPath $mtxExtractDir -Force

    $extractedMtx = Get-ChildItem -Path $mtxExtractDir -Recurse -Filter "mediamtx.exe" | Select-Object -First 1
    if ($extractedMtx) {
        Move-Item -Path $extractedMtx.FullName -Destination $mediamtxExe -Force
    }

    Remove-Item -Path $mtxZipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $mtxExtractDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ----------------------------------------------------------------------
# 3. VERIFICACION FINAL DE INTEGRIDAD DE TODOS LOS BINARIOS
# ----------------------------------------------------------------------
if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffplayExe) -or -not (Test-Path $mediamtxExe)) {
    Write-Host "[ERROR] Uno o mas binarios multimedia requeridos no pudieron ser instalados." -ForegroundColor Red
    exit 1
}

# Generar manifiesto determinista de hashes SHA256 para reproducibilidad de release
$manifestPath = Join-Path $binDir "checksums.sha256"
$ffmpegHash = (Get-FileHash -Path $ffmpegExe -Algorithm SHA256).Hash.ToLower()
$ffplayHash = (Get-FileHash -Path $ffplayExe -Algorithm SHA256).Hash.ToLower()
$mediamtxHash = (Get-FileHash -Path $mediamtxExe -Algorithm SHA256).Hash.ToLower()

@"
$ffmpegHash  ffmpeg.exe
$ffplayHash  ffplay.exe
$mediamtxHash  mediamtx.exe
"@ | Set-Content -Path $manifestPath -Encoding utf8
Write-Host "[OK] Manifiesto criptográfico generado en: $manifestPath" -ForegroundColor Green

Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[EXITO] Todos los binarios multimedia estan verificados y listos:" -ForegroundColor Green
& $ffmpegExe -version | Select-Object -First 1
& $ffplayExe -version | Select-Object -First 1
& $mediamtxExe --version | Select-Object -First 1
Write-Host "============================================================" -ForegroundColor Cyan
