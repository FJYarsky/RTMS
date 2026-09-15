@echo off
REM RTMS v2.2.2 Windows Quick-Start Launcher
REM ==============================================================================
REM RTMS v2.2.2 — Lanzador Silencioso (Sin ventana de consola CMD)
REM Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
REM ==============================================================================

cd /d "%~dp0"

REM Verificar si existe el Python embebido en bin\python\pythonw.exe
if exist "bin\python\pythonw.exe" (
    start "" "bin\python\pythonw.exe" main.py
    exit /b 0
)

REM Fallback al pythonw del sistema
start "" pythonw main.py
exit /b 0
