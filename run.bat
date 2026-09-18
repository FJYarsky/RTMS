@echo off
REM ==============================================================================
REM RTMS — Real-Time Multicam System
REM Lanzador de inicio en segundo plano de la aplicación.
REM Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
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
 
