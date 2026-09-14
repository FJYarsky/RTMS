@echo off
REM ==============================================================================
REM RTMS 2.0.2 — Build Script para ejecutable nativo portable (pywebview)
REM Genera rtms.exe en la carpeta dist/
REM Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
REM ==============================================================================

echo.
echo ============================================================
echo  RTMS v2.0.2 — Creando aplicacion nativa con PyInstaller
echo ============================================================
echo.

cd /d "%~dp0"

REM Verificar que PyInstaller este instalado
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller no esta instalado. Instalando...
    pip install pyinstaller
)

REM Limpiar builds anteriores
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist rtms.spec del /q rtms.spec

echo [INFO] Construyendo ejecutable nativo rtms.exe...
echo [INFO] Esto ocultara la consola (--noconsole) al ejecutar el programa.

python -m PyInstaller ^
  --clean ^
  --onedir ^
  --noconsole ^
  --icon=icon.ico ^
  --name rtms ^
  --add-data "gui\templates;gui\templates" ^
  --add-data "gui\static;gui\static" ^
  --add-data "config;config" ^
  --add-data "icon.ico;." ^
  --hidden-import=uvicorn ^
  --hidden-import=uvicorn.logging ^
  --hidden-import=uvicorn.loops ^
  --hidden-import=uvicorn.loops.auto ^
  --hidden-import=uvicorn.protocols ^
  --hidden-import=uvicorn.protocols.http ^
  --hidden-import=uvicorn.protocols.http.auto ^
  --hidden-import=uvicorn.protocols.websockets ^
  --hidden-import=uvicorn.protocols.websockets.auto ^
  --hidden-import=uvicorn.lifespan ^
  --hidden-import=uvicorn.lifespan.on ^
  --hidden-import=fastapi ^
  --hidden-import=starlette ^
  --hidden-import=starlette.templating ^
  --hidden-import=starlette.staticfiles ^
  --hidden-import=jinja2 ^
  --hidden-import=anyio ^
  --hidden-import=anyio._backends._asyncio ^
  --hidden-import=winreg ^
  --hidden-import=webview ^
  --hidden-import=clr ^
  --hidden-import=pystray ^
  --hidden-import=PIL ^
  --hidden-import=psutil ^
  --collect-all=uvicorn ^
  --collect-all=fastapi ^
  --collect-all=webview ^
  --collect-all=pystray ^
  main.py

if errorlevel 1 (
    echo.
    echo [ERROR] El proceso de build fallo.
    pause
    exit /b 1
)

REM Copiar la carpeta bin existente dentro de dist/rtms/ para que FFmpeg este disponible
if exist bin (
    echo [INFO] Copiando binarios multimedia a dist\rtms\bin...
    xcopy /E /I /Y bin dist\rtms\bin
)

echo.
echo ============================================================
echo  [OK] Aplicacion nativa generada exitosamente en: dist\rtms\rtms.exe
echo ============================================================
echo.
pause
