@echo off
REM ==============================================================================
REM RTMS v2.0.2 — Lanzador Silencioso (Sin ventana de consola CMD)
REM Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
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
