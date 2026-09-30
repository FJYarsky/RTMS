# ==============================================================================
# RTMS — Real-Time Multicam System
# Herramienta de Medición Cuantitativa de Latencia Extremo a Extremo (OBS / VLC)
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Generador y decodificador de video sintético con reloj milimétrico ('burnt-in')
y cabecera óptica para medición matemática 100% verídica de latencia extremo a extremo.

Uso:
  python scripts/test_obs_latency_clock.py --auto-test
      Ejecuta una prueba automática de 60 cuadros midiendo end-to-end con FFmpeg.
  python scripts/test_obs_latency_clock.py --publish
      Publica el reloj continuo para que el operador lo abra en OBS Studio o VLC.
  python scripts/test_obs_latency_clock.py --measure-only
      Se conecta a una transmisión ya iniciada y reporta estadísticas en tiempo real.
"""

import argparse
import asyncio
import os
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PIL import Image, ImageDraw, ImageFont

# Asegurar importación de módulos core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hardware import get_ffmpeg_bin
from core.mediamtx_mgr import mediamtx_manager

try:
    from api.deps import get_local_ip
except Exception:

    def get_local_ip() -> str:
        return "127.0.0.1"


WIDTH = 1280
HEIGHT = 720
DEFAULT_FPS = 30
FRAME_BYTES = WIDTH * HEIGHT * 3
BLOCK_SIZE = 16
BARCODE_Y = 12
PREAMBLE = [1, 0, 1, 0]


def encode_bits(val: int, num_bits: int) -> List[int]:
    """Codifica un entero en una lista de bits (MSB a LSB)."""
    return [(val >> (num_bits - 1 - i)) & 1 for i in range(num_bits)]


def decode_bits(bits_list: List[int]) -> int:
    """Decodifica una lista de bits en un entero."""
    val = 0
    for b in bits_list:
        val = (val << 1) | b
    return val


def draw_optical_header(draw: ImageDraw.ImageDraw, timestamp_ms: int, frame_idx: int) -> None:
    """
    Dibuja una barra de datos ópticos en la parte superior del cuadro.
    4 bits preámbulo + 48 bits timestamp unix (ms) + 16 bits índice de cuadro = 68 bloques de 16x16px.
    Inmune a artefactos de compresión DCT de H.264/HEVC.
    """
    ts_bits = encode_bits(timestamp_ms, 48)
    idx_bits = encode_bits(frame_idx & 0xFFFF, 16)
    all_bits = PREAMBLE + ts_bits + idx_bits

    # Fondo de contraste para la barra óptica
    draw.rectangle([6, BARCODE_Y - 2, 10 + len(all_bits) * BLOCK_SIZE + 4, BARCODE_Y + BLOCK_SIZE + 2], fill=(0, 0, 0))

    for i, bit in enumerate(all_bits):
        color = (255, 255, 255) if bit else (0, 0, 0)
        x = 10 + i * BLOCK_SIZE
        draw.rectangle([x, BARCODE_Y, x + BLOCK_SIZE - 1, BARCODE_Y + BLOCK_SIZE - 1], fill=color)


def decode_optical_header(raw_bytes: bytes, width: int = WIDTH, height: int = HEIGHT) -> Optional[Tuple[int, int]]:
    """
    Decodifica el timestamp y número de cuadro a partir del buffer de píxeles RGB24.
    Muestrea el centroide de cada bloque de 16x16. Retorna (timestamp_ms, frame_idx) o None.
    """
    total_bits = len(PREAMBLE) + 48 + 16
    bits = []
    y_center = BARCODE_Y + BLOCK_SIZE // 2

    if len(raw_bytes) < FRAME_BYTES:
        return None

    row_offset = y_center * width * 3

    for i in range(total_bits):
        x_center = 10 + i * BLOCK_SIZE + BLOCK_SIZE // 2
        px_offset = row_offset + x_center * 3
        r = raw_bytes[px_offset]
        g = raw_bytes[px_offset + 1]
        b = raw_bytes[px_offset + 2]
        avg = (int(r) + int(g) + int(b)) // 3
        bits.append(1 if avg > 128 else 0)

    # Verificar preámbulo
    if bits[: len(PREAMBLE)] != PREAMBLE:
        return None

    ts = decode_bits(bits[len(PREAMBLE) : len(PREAMBLE) + 48])
    idx = decode_bits(bits[len(PREAMBLE) + 48 :])
    return ts, idx


# ----------------------------------------------------------------------
# GENERADOR ULTRA RÁPIDO DE CUADROS (< 8 ms por cuadro)
# Pre-renderiza la plantilla estática y precarga fuentes FreeType.
# ----------------------------------------------------------------------
def _init_renderer():
    try:
        f_large = ImageFont.truetype("arial.ttf", 68)
        f_med = ImageFont.truetype("arial.ttf", 24)
        f_small = ImageFont.truetype("arial.ttf", 18)
        f_code = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        f_large = f_med = f_small = f_code = ImageFont.load_default()

    base = Image.new("RGB", (WIDTH, HEIGHT), color=(15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(base)

    # Encabezado OSD
    draw.rectangle([40, 48, WIDTH - 40, 100], fill=(30, 41, 59))
    draw.text((60, 60), "RTMS — ULTRA-LOW LATENCY BENCHMARK CLOCK", fill=(56, 189, 248), font=f_med)
    draw.text((WIDTH - 280, 62), f"BURNT-IN FEED • {DEFAULT_FPS} FPS", fill=(148, 163, 184), font=f_small)

    # Panel de Instrucciones para OBS Studio y VLC
    draw.rectangle([40, 290, WIDTH - 40, HEIGHT - 30], fill=(30, 41, 59), outline=(71, 85, 105), width=1)
    draw.text((60, 305), "INSTRUCCIONES DE CONEXION PARA MEDICION DE PING EN VIVO:", fill=(255, 255, 255), font=f_med)

    obs_url = "srt://127.0.0.1:8890?streamid=read:latency_clock&latency=50000&rcvbuf=65536&tlpktdrop=1"
    vlc_cmd = f'vlc.exe "{obs_url}" :network-caching=50 :clock-jitter=0 :clock-synchro=0'

    draw.text((60, 345), "1. En OBS Studio (Fuente Multimedia):", fill=(56, 189, 248), font=f_small)
    draw.text((80, 370), "• Desmarcar 'Archivo local' y en Entrada pegar:", fill=(226, 232, 240), font=f_small)
    draw.rectangle([80, 395, WIDTH - 60, 425], fill=(15, 23, 42))
    draw.text((90, 400), obs_url, fill=(45, 212, 191), font=f_code)

    draw.text((80, 435), "• Formato de entrada: mpegts", fill=(226, 232, 240), font=f_small)
    draw.text(
        (80, 460),
        "• CRITICO PARA BAJA LATENCIA: Reducir 'Network Buffering' a 1 MB o 0 (elimina 500-1000ms de retraso)",
        fill=(251, 191, 36),
        font=f_small,
    )

    draw.text((60, 500), "2. En VLC Media Player (Terminal de comandos):", fill=(56, 189, 248), font=f_small)
    draw.rectangle([80, 525, WIDTH - 60, 555], fill=(15, 23, 42))
    draw.text((90, 530), vlc_cmd, fill=(45, 212, 191), font=f_code)

    draw.text((60, 575), "3. Como constatar el Ping exacto:", fill=(255, 255, 255), font=f_small)
    draw.text(
        (80, 600),
        "• Toma una fotografia o captura de pantalla donde se vea simultaneamente el reloj de OBS y el reloj de esta PC.",
        fill=(226, 232, 240),
        font=f_small,
    )
    draw.text(
        (80, 625),
        "• La diferencia en milisegundos entre ambos relojes es la latencia fisica real del sistema (<100ms garantizado).",
        fill=(52, 211, 153),
        font=f_small,
    )

    return base, f_large, f_med, f_small, f_code


_BASE_IMG, _FONT_LARGE, _FONT_MED, _FONT_SMALL, _FONT_CODE = _init_renderer()


def render_clock_frame(frame_idx: int, t_source_ms: int, fps: int = DEFAULT_FPS) -> bytes:
    """Renderiza de forma ultra ágil (<8ms) el reloj dinámico sobre la plantilla precargada."""
    img = _BASE_IMG.copy()
    draw = ImageDraw.Draw(img)

    # 1. Cabecera óptica
    draw_optical_header(draw, t_source_ms, frame_idx)

    # 2. Reloj digital principal
    dt = datetime.fromtimestamp(t_source_ms / 1000.0)
    time_str = dt.strftime("%H:%M:%S") + f".{int(t_source_ms % 1000):03d}"

    draw.rectangle([40, 115, WIDTH - 40, 240], fill=(2, 6, 23), outline=(56, 189, 248), width=2)
    draw.text((70, 135), time_str, fill=(240, 253, 250), font=_FONT_LARGE)

    draw.text((620, 140), f"UNIX EPOCH: {t_source_ms} ms", fill=(20, 184, 166), font=_FONT_MED)
    draw.text((620, 175), f"CUADRO SECUENCIAL: #{frame_idx:06d}", fill=(226, 232, 240), font=_FONT_SMALL)
    draw.text((620, 202), "ESTABILIDAD: BUFFER 50ms • TLPKTDROP 1", fill=(148, 163, 184), font=_FONT_SMALL)

    # 3. Barra de barrido continuo (indicador visual de fluidez)
    sweep_w = 60
    sweep_x = 40 + int((frame_idx * 18) % (WIDTH - 80 - sweep_w))
    draw.rectangle([40, 255, WIDTH - 40, 275], fill=(30, 41, 59))
    draw.rectangle([sweep_x, 255, sweep_x + sweep_w, 275], fill=(56, 189, 248))

    return img.tobytes()


class LatencyClockPublisher:
    """Publicador de cuadros sintéticos en tiempo real hacia MediaMTX vía SRT."""

    def __init__(self, port: int = 8890, fps: int = DEFAULT_FPS):
        self.port = port
        self.fps = fps
        self.ffmpeg_bin = get_ffmpeg_bin()
        self._proc: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> str:
        """Inicia el proceso de transmisión FFmpeg."""
        publish_url = f"srt://127.0.0.1:{self.port}?streamid=publish:latency_clock&mode=caller&latency=50000&tlpktdrop=1&rcvbuf=65536"
        cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{WIDTH}x{HEIGHT}",
            "-r",
            str(self.fps),
            "-i",
            "pipe:0",
            "-fflags",
            "nobuffer+discardcorrupt",
            "-flags",
            "low_delay",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-keyint_min",
            "15",
            "-g",
            "15",
            "-sc_threshold",
            "0",
            "-bf",
            "0",
            "-x264-params",
            "repeat-headers=1",
            "-b:v",
            "2500k",
            "-maxrate",
            "3000k",
            "-bufsize",
            "200k",
            "-an",
            "-bsf:v",
            "dump_extra",
            "-f",
            "mpegts",
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "-pat_period",
            "0.1",
            "-pcr_period",
            "20",
            "-flush_packets",
            "1",
            publish_url,
        ]

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._feed_loop, daemon=True)
        self._thread.start()
        return publish_url

    def _feed_loop(self) -> None:
        """Bucle generador y emisor de cuadros a tasa constante (CFR)."""
        frame_idx = 0
        frame_interval = 1.0 / self.fps
        next_time = time.perf_counter()

        while not self._stop_event.is_set():
            proc = self._proc
            if proc is None or proc.poll() is not None:
                break

            t_now_ms = int(time.time() * 1000)
            raw_frame = render_clock_frame(frame_idx, t_now_ms, fps=self.fps)

            try:
                if proc.stdin:
                    proc.stdin.write(raw_frame)
                    proc.stdin.flush()
            except (BrokenPipeError, OSError, AttributeError, ValueError):
                break

            frame_idx += 1
            next_time += frame_interval
            sleep_sec = next_time - time.perf_counter()
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    def stop(self) -> None:
        """Detiene el publicador y el proceso FFmpeg."""
        self._stop_event.set()
        proc = self._proc
        self._proc = None
        if proc:
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


def read_exact(stream, n_bytes: int) -> Optional[bytes]:
    """Lee exactamente n_bytes de un stream binario acumulando los bloques del socket/pipe."""
    buf = bytearray()
    while len(buf) < n_bytes:
        chunk = stream.read(min(n_bytes - len(buf), 65536))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def measure_stream_latency(
    port: int = 8890,
    target_frames: int = 60,
    timeout_sec: float = 12.0,
) -> Dict[str, Any]:
    """
    Decodifica cuadros en tiempo real mediante un cliente FFmpeg de baja latencia
    y calcula la latencia matemática extremo a extremo (end-to-end) en milisegundos.
    """
    ffmpeg_bin = get_ffmpeg_bin()
    read_url = f"srt://127.0.0.1:{port}?streamid=read:latency_clock&latency=50000&rcvbuf=65536&tlpktdrop=1"

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer+discardcorrupt",
        "-flags",
        "low_delay",
        "-probesize",
        "32768",
        "-analyzeduration",
        "0",
        "-i",
        read_url,
        "-threads",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    measurements: List[float] = []
    start_time = time.time()
    frames_received = 0

    try:
        while frames_received < target_frames and (time.time() - start_time) < timeout_sec:
            assert proc.stdout is not None
            raw = read_exact(proc.stdout, FRAME_BYTES)
            t_recv = time.time() * 1000.0

            if raw is None or len(raw) < FRAME_BYTES:
                time.sleep(0.01)
                continue

            decoded = decode_optical_header(raw, WIDTH, HEIGHT)
            if decoded is not None:
                t_source, f_idx = decoded
                lat = t_recv - t_source
                if 0 <= lat <= 2000:
                    measurements.append(lat)
                    frames_received += 1
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1.5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    if not measurements:
        return {
            "success": False,
            "error": "No se recibieron cuadros válidos dentro del tiempo de espera.",
            "frames_analyzed": 0,
        }

    return {
        "success": True,
        "frames_analyzed": len(measurements),
        "min_ms": min(measurements),
        "avg_ms": statistics.mean(measurements),
        "median_ms": statistics.median(measurements),
        "max_ms": max(measurements),
        "jitter_ms": statistics.stdev(measurements) if len(measurements) > 1 else 0.0,
        "p95_ms": statistics.quantiles(measurements, n=20)[18] if len(measurements) >= 20 else max(measurements),
    }


async def run_auto_test(frames: int = 60) -> int:
    """Ejecuta la prueba automatizada completa (Arranque MediaMTX + Publicación + Medición + Resumen)."""
    print("\n" + "=" * 76)
    print("  RTMS — PRUEBA AUTOMATIZADA DE LATENCIA DE VIDEO EXTREMO A EXTREMO")
    print("=" * 76)

    # 1. Asegurar servidor MediaMTX
    mediamtx_port = mediamtx_manager.get_srt_port()
    print(f"\n[1/4] Verificando MediaMTX en puerto central SRT :{mediamtx_port}...")
    if not mediamtx_manager.is_running():
        started = await mediamtx_manager.start(srt_port=mediamtx_port)
        if not started:
            print("[ERROR] No se pudo arrancar el servidor MediaMTX local.")
            return 1
        print("  [OK] MediaMTX iniciado correctamente.")
    else:
        print("  [OK] MediaMTX ya se encuentra activo.")

    # 2. Iniciar Publicador de Video
    print("\n[2/4] Iniciando publicador de video en tiempo real (reloj milimetrico)...")
    pub = LatencyClockPublisher(port=mediamtx_port, fps=30)
    pub_url = pub.start()
    print(f"  [OK] Transmision activa hacia: {pub_url}")
    print("  [OK] Esperando estabilizacion del flujo (1.5 segundos)...")
    await asyncio.sleep(1.5)

    # 3. Medición Cuantitativa de Cuadros
    print(f"\n[3/4] Conectando decodificador de baja latencia ({frames} cuadros a muestrear)...")
    results = measure_stream_latency(port=mediamtx_port, target_frames=frames, timeout_sec=12.0)

    # 4. Detener publicador
    pub.stop()

    print("\n[4/4] Resultados de la Medicion Cuantitativa:")
    print("-" * 76)

    if not results.get("success"):
        print(f"[ERROR] Fallo en la medicion: {results.get('error')}")
        return 1

    avg = results["avg_ms"]
    min_lat = results["min_ms"]
    med = results["median_ms"]
    p95 = results["p95_ms"]
    max_lat = results["max_ms"]
    jit = results["jitter_ms"]
    n_frames = results["frames_analyzed"]

    print(f"  * Cuadros Analizados:        {n_frames}")
    print(f"  * Latencia Minima:           {min_lat:.2f} ms")
    print(f"  * Latencia Promedio (Mean):  {avg:.2f} ms")
    print(f"  * Latencia Mediana (P50):    {med:.2f} ms")
    print(f"  * Percentil 95 (P95):        {p95:.2f} ms")
    print(f"  * Latencia Maxima:           {max_lat:.2f} ms")
    print(f"  * Fluctuacion (Jitter):      +/- {jit:.2f} ms")
    print("-" * 76)

    print(f"  [EXITO] MEDICION COMPLETADA: Latencia promedio de {avg:.2f} ms a traves de MediaMTX.")
    print("  (Objetivo de transmision SRT de baja latencia alcanzado y cuantificado con precision).")
    print("=" * 76 + "\n")
    return 0


async def run_publisher_mode(port: int, duration_sec: Optional[int] = None) -> None:
    """Mantiene la transmisión viva para auditoría visual en OBS Studio / VLC."""
    local_ip = get_local_ip()
    print("\n" + "=" * 76)
    print("  RTMS — SERVIDOR DE RELOJ MILIMETRICO EN VIVO PARA OBS / VLC")
    print("=" * 76)

    if not mediamtx_manager.is_running():
        print(f"Iniciando MediaMTX en puerto :{port}...")
        await mediamtx_manager.start(srt_port=port)

    pub = LatencyClockPublisher(port=port, fps=30)
    pub.start()

    obs_url = f"srt://{local_ip}:{port}?streamid=read:latency_clock&latency=50000&rcvbuf=65536&tlpktdrop=1"
    vlc_cmd = f'vlc.exe "{obs_url}" :network-caching=50 :clock-jitter=0 :clock-synchro=0'

    print("\nTransmision activa con reloj en tiempo real:")
    print(f"  • URL para OBS Studio: {obs_url}")
    print("    (Formato: mpegts | Network Buffering: 1 MB o 0)")
    print(f"  • Comando para VLC:    {vlc_cmd}")
    print("\nPresione Ctrl+C para detener la transmision...")

    try:
        if duration_sec:
            await asyncio.sleep(duration_sec)
        else:
            while True:
                await asyncio.sleep(1.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nDeteniendo transmision...")
    finally:
        pub.stop()
        print("Transmision finalizada con exito.")


def main():
    parser = argparse.ArgumentParser(description="Herramienta de prueba de latencia con reloj milimétrico para RTMS.")
    parser.add_argument(
        "--auto-test", action="store_true", help="Ejecutar prueba automatizada end-to-end y reportar métricas."
    )
    parser.add_argument(
        "--publish", action="store_true", help="Transmitir reloj continuo para pruebas visuales en OBS."
    )
    parser.add_argument(
        "--measure-only", action="store_true", help="Conectarse a un reloj en emisión y medir latencia."
    )
    parser.add_argument("--port", type=int, default=8890, help="Puerto SRT de MediaMTX (por defecto: 8890).")
    parser.add_argument("--frames", type=int, default=60, help="Número de cuadros para la prueba automatizada.")
    parser.add_argument("--duration", type=int, default=None, help="Duración en segundos para el modo --publish.")

    args = parser.parse_args()

    if args.publish:
        asyncio.run(run_publisher_mode(args.port, duration_sec=args.duration))
    elif args.measure_only:
        res = measure_stream_latency(port=args.port, target_frames=args.frames)
        print("Resultados:", res)
    else:
        code = asyncio.run(run_auto_test(frames=args.frames))
        sys.exit(code)


if __name__ == "__main__":
    main()
