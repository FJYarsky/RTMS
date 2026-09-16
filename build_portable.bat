@echo off
REM ==============================================================================
REM RTMS — Real-Time Multicam System
REM Script de empaquetado portable para ejecutable nativo (pywebview / PyInstaller)
REM Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
REM ==============================================================================

echo.
echo ============================================================
echo  RTMS — Creando aplicacion nativa con PyInstaller
echo ============================================================
echo.

cd /d "%~dp0"

REM Validar presencia obligatoria de binarios multimedia
if not exist "bin\ffmpeg.exe" (
    echo [ERROR] bin\ffmpeg.exe no fue encontrado.
    echo Ejecute powershell -ExecutionPolicy Bypass -File scripts\setup_binaries.ps1 primero.
    exit /b 1
)
if not exist "bin\ffplay.exe" (
    echo [ERROR] bin\ffplay.exe no fue encontrado.
    echo Ejecute powershell -ExecutionPolicy Bypass -File scripts\setup_binaries.ps1 primero.
    exit /b 1
)

REM Detectar interprete de Python preferido
if exist "bin\python\python.exe" (
    set "PYTHON_EXE=bin\python\python.exe"
) else (
    set "PYTHON_EXE=python"
)

REM Verificar que PyInstaller este instalado
%PYTHON_EXE% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller no esta instalado. Instalando...
    %PYTHON_EXE% -m pip install pyinstaller
)

REM Limpiar builds anteriores
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist rtms.spec del /q rtms.spec

echo [INFO] Construyendo ejecutable nativo rtms.exe...
echo [INFO] Esto ocultara la consola (--noconsole) al ejecutar el programa.

%PYTHON_EXE% -m PyInstaller ^
  --clean ^
  --onedir ^
  --noconsole ^
  --icon=icon.ico ^
  --name rtms ^
  --add-data "gui\templates;gui\templates" ^
  --add-data "gui\static;gui\static" ^
  --add-data "config\config.example.json;config" ^
  --add-data "icon.ico;." ^
  --hidden-import=uvicorn ^
  --hidden-import=uvicorn.logging ^
  --hidden-import=uvicorn.loops ^
  --hidden-import=uvicorn.loops.auto ^
  --hidden-import=uvicorn.loops.asyncio ^
  --hidden-import=uvicorn.protocols ^
  --hidden-import=uvicorn.protocols.http ^
  --hidden-import=uvicorn.protocols.http.auto ^
  --hidden-import=uvicorn.protocols.http.h11_impl ^
  --hidden-import=uvicorn.protocols.websockets ^
  --hidden-import=uvicorn.protocols.websockets.auto ^
  --hidden-import=uvicorn.protocols.websockets.websockets_impl ^
  --hidden-import=uvicorn.lifespan ^
  --hidden-import=uvicorn.lifespan.on ^
  --hidden-import=uvicorn.lifespan.off ^
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
  --hidden-import=pythonnet ^
  --hidden-import=pystray ^
  --hidden-import=PIL ^
  --hidden-import=psutil ^
  --hidden-import=core.telemetry ^
  --collect-all=uvicorn ^
  --collect-all=fastapi ^
  --collect-all=starlette ^
  --collect-all=webview ^
  --collect-all=pythonnet ^
  --collect-all=pystray ^
  main.py

if errorlevel 1 (
    echo.
    echo [ERROR] El proceso de build fallo.
    pause
    exit /b 1
)

REM Copiar los binarios multimedia (ffmpeg.exe, ffplay.exe) dentro de dist/rtms/bin/
if not exist "dist\rtms\bin" mkdir "dist\rtms\bin"
if exist "bin\ffmpeg.exe" (
    echo [INFO] Copiando FFmpeg a dist\rtms\bin...
    copy /Y "bin\ffmpeg.exe" "dist\rtms\bin\" >nul
)
if exist "bin\ffplay.exe" (
    echo [INFO] Copiando FFplay a dist\rtms\bin...
    copy /Y "bin\ffplay.exe" "dist\rtms\bin\" >nul
)

REM Copiar la plantilla limpia de configuracion a dist/rtms/config/ (NUNCA config.json ni .bak)
if not exist "dist\rtms\config" mkdir "dist\rtms\config"
if exist "config\config.example.json" (
    echo [INFO] Copiando config.example.json a dist\rtms\config...
    copy /Y "config\config.example.json" "dist\rtms\config\" >nul
)

REM Copiar licencias y avisos de terceros
if exist "THIRD_PARTY_NOTICES.md" (
    copy /Y "THIRD_PARTY_NOTICES.md" "dist\rtms\" >nul
)

REM Copiar icono a las ubicaciones clave
if exist "icon.ico" (
    copy /Y "icon.ico" "dist\rtms\" >nul
    copy /Y "icon.ico" "dist\rtms\_internal\" >nul
)

REM Localizar librerías y runtimes nativos de webview/WebView2
set "WEBVIEW_LIB_DIR="
for /f "usebackq delims=" %%D in (`%PYTHON_EXE% -c "import webview, os; print(os.path.join(os.path.dirname(webview.__file__), 'lib'))" 2^>nul`) do (
    set "WEBVIEW_LIB_DIR=%%D"
)

if defined WEBVIEW_LIB_DIR (
    if exist "%WEBVIEW_LIB_DIR%" (
        echo [INFO] Copiando dependencias nativas de pywebview y WebView2...
        xcopy /E /I /Y "%WEBVIEW_LIB_DIR%\*" "dist\rtms\" >nul
        xcopy /E /I /Y "%WEBVIEW_LIB_DIR%\*" "dist\rtms\_internal\" >nul
        if not exist "dist\rtms\_internal\webview\lib" mkdir "dist\rtms\_internal\webview\lib"
        xcopy /E /I /Y "%WEBVIEW_LIB_DIR%\*" "dist\rtms\_internal\webview\lib\" >nul
    )
)

echo.
echo ============================================================
echo  [OK] Aplicacion nativa generada exitosamente en: dist\rtms\rtms.exe
echo ============================================================
echo.
