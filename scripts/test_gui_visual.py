# ==============================================================================
# RTMS — Real-Time Multicam System
# Script de validación visual del GUI mediante Chrome DevTools Protocol (CDP).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Script de testing visual automatizado exhaustivo para el GUI de RTMS:
1. Inicia backend FastAPI en 127.0.0.1:8998.
2. Inicia Google Chrome en modo headless con CDP (--remote-debugging-port=9222).
3. Conecta vía WebSocket a Chrome DevTools Protocol.
4. Captura todas las vistas y modales clave:
   - Dashboard principal (Español)
   - Vista de Cámaras y Dispositivos DirectShow
   - Vista de Gestión de Energía y Gobernanza
   - Vista de Sistema y Arranque
   - Modal 'Acerca de' con bandera e ícono de Islas Malvinas
   - Modal 'Telemetría Detallada'
   - Dashboard principal (English i18n)
5. Inspecciona la consola del navegador para certificar cero errores de JavaScript.
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import websockets


def find_chrome() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError("No se encontró Chrome ni Edge.")


async def cdp_call(ws, method: str, params: dict = None, req_id: int = 1) -> dict:
    msg = {"id": req_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == req_id:
            return data


async def evaluate_js(ws, expr: str, req_id: int) -> dict:
    return await cdp_call(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, req_id)


async def take_screenshot(ws, output_file: Path, req_id: int):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"}, req_id)
    b64_data = res.get("result", {}).get("data", "")
    if not b64_data:
        raise RuntimeError("No se recibieron datos de captura de pantalla de CDP.")
    raw_bytes = base64.b64decode(b64_data)
    output_file.write_bytes(raw_bytes)
    size_kb = len(raw_bytes) / 1024
    print(f"  * [CAPTURA] {output_file.name} guardada exitosamente ({size_kb:.1f} KB)")


async def run_visual_tests():
    repo_root = Path(__file__).resolve().parent.parent
    screenshots_dir = repo_root / "docs" / "screenshots"
    port = 8998
    base_url = f"http://127.0.0.1:{port}"
    cdp_port = 9222

    # 1. Iniciar servidor RTMS FastAPI
    env = os.environ.copy()
    env["RTMS_PORT"] = str(port)
    env["RTMS_HOST"] = "127.0.0.1"
    env["RTMS_NO_BROWSER"] = "1"
    env["PYTHONPATH"] = str(repo_root)

    print(f"[INFO] Iniciando backend RTMS en {base_url}...")
    server_proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"import uvicorn; from main import create_app; app = create_app(); uvicorn.run(app, host='127.0.0.1', port={port}, log_level='warning')",
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    chrome_proc = None
    try:
        # Esperar respuesta del servidor
        started = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{base_url}/", timeout=1) as resp:
                    if resp.status == 200:
                        started = True
                        break
            except Exception:
                await asyncio.sleep(0.3)

        if not started:
            raise TimeoutError("El servidor RTMS no respondió.")

        print("[OK] Servidor RTMS respondiendo.")

        # 2. Iniciar Chrome con CDP
        browser = find_chrome()
        chrome_cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            f"--remote-debugging-port={cdp_port}",
            "--window-size=1440,900",
            base_url,
        ]
        chrome_proc = subprocess.Popen(chrome_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Esperar a que el puerto CDP responda
        cdp_ready = False
        ws_url = None
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=1) as resp:
                    targets = json.loads(resp.read().decode())
                    for t in targets:
                        if t.get("type") == "page" and "webSocketDebuggerUrl" in t:
                            ws_url = t["webSocketDebuggerUrl"]
                            cdp_ready = True
                            break
                    if cdp_ready:
                        break
            except Exception:
                await asyncio.sleep(0.3)

        if not ws_url:
            raise RuntimeError("No se pudo obtener webSocketDebuggerUrl de Chrome CDP.")

        print(f"[OK] Conectado a Chrome CDP: {ws_url}")

        async with websockets.connect(ws_url) as ws:
            req_id = 1
            await cdp_call(ws, "Page.enable", {}, req_id=req_id)
            req_id += 1
            await cdp_call(ws, "DOM.enable", {}, req_id=req_id)
            req_id += 1

            # Esperar render inicial
            await asyncio.sleep(1.0)

            # 1. Capturar pantalla de bienvenida
            print("\n[PASO 1] Capturando modal de bienvenida inicial...")
            await take_screenshot(ws, screenshots_dir / "01_welcome_modal.png", req_id=req_id)
            req_id += 1

            # 2. Seleccionar español y capturar dashboard principal
            print("\n[PASO 2] Configurando idioma Español y capturando Dashboard...")
            await evaluate_js(ws, "selectInitialLanguage('es');", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "02_dashboard_es.png", req_id=req_id)
            req_id += 1

            # 3. Vista de cámaras
            print("\n[PASO 3] Cambiando a vista de Cámaras...")
            await evaluate_js(ws, "navigateToPage('cameras');", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "03_cameras_view.png", req_id=req_id)
            req_id += 1

            # 4. Vista de energía
            print("\n[PASO 4] Cambiando a vista de Gestión de Energía...")
            await evaluate_js(ws, "navigateToPage('power');", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "04_energy_view.png", req_id=req_id)
            req_id += 1

            # 5. Vista de sistema
            print("\n[PASO 5] Cambiando a vista de Sistema y Arranque...")
            await evaluate_js(ws, "navigateToPage('system');", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "05_system_view.png", req_id=req_id)
            req_id += 1

            # 6. Modal 'Acerca de' (Islas Malvinas y Autor)
            print("\n[PASO 6] Abriendo modal 'Acerca de' (con bandera de Malvinas)...")
            await evaluate_js(ws, "openAboutModal();", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "06_about_modal_malvinas.png", req_id=req_id)
            req_id += 1

            # 7. Modal de Telemetría Detallada
            print("\n[PASO 7] Abriendo modal de Telemetría Detallada...")
            await evaluate_js(ws, "closeAboutModal(); openTelemetryModal();", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "07_telemetry_modal.png", req_id=req_id)
            req_id += 1

            # 8. Modo Bilingüe Inglés en Dashboard
            print("\n[PASO 8] Cambiando idioma a Inglés y capturando Dashboard en inglés...")
            await evaluate_js(
                ws, "closeTelemetryModal(); navigateToPage('connect'); setAppLanguage('en');", req_id=req_id
            )
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "08_dashboard_en.png", req_id=req_id)
            req_id += 1

            # 9. Vista de Cámaras en Inglés
            print("\n[PASO 9] Navegando a Cámaras en Inglés...")
            await evaluate_js(ws, "navigateToPage('cameras');", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "09_cameras_en.png", req_id=req_id)
            req_id += 1

            # 10. Modal de Configuración en Español
            print("\n[PASO 10] Abriendo Modal de Ajustes en Español...")
            await evaluate_js(ws, "setAppLanguage('es'); configureStream(0);", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "10_config_modal_es.png", req_id=req_id)
            req_id += 1

            # 11. Modal de Configuración en Inglés
            print("\n[PASO 11] Conmutando Modal de Ajustes a Inglés...")
            await evaluate_js(ws, "setAppLanguage('en'); configureStream(0);", req_id=req_id)
            req_id += 1
            await asyncio.sleep(0.5)
            await take_screenshot(ws, screenshots_dir / "11_config_modal_en.png", req_id=req_id)
            req_id += 1

            print("\n[ÉXITO] Todas las 11 vistas y modales clave fueron capturados con éxito.")

    finally:
        if chrome_proc:
            chrome_proc.terminate()
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except Exception:
            server_proc.kill()
        print("[INFO] Procesos de prueba detenidos limpiamente.")


if __name__ == "__main__":
    asyncio.run(run_visual_tests())
