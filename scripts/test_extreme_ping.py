import asyncio
import os
import subprocess
import sys
import time

# Añadir el path al PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.hardware import get_ffmpeg_bin
from core.mediamtx_mgr import mediamtx_manager


async def run_extreme_ping():
    print("==================================================")
    print("=  TEST DE PING EXTREMO (Latencia < 50ms) SRT    =")
    print("==================================================")

    # Iniciar MediaMTX
    print("[1] Iniciando MediaMTX local...")
    await mediamtx_manager.start(8890)
    await asyncio.sleep(2)

    ffmpeg_bin = get_ffmpeg_bin()

    # COMANDO DE INGESTA (Publisher)
    # Leemos de stdin (rawvideo rgb24 640x480) y publicamos a SRT usando NVENC / x264 optimizado
    publish_url = "srt://127.0.0.1:8890?streamid=publish:ping&latency=20000&mode=caller"
    pub_cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-s",
        "640x480",
        "-pix_fmt",
        "rgb24",
        "-r",
        "60",
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-bf",
        "0",
        "-f",
        "mpegts",
        "-muxdelay",
        "0",
        "-muxpreload",
        "0",
        "-flush_packets",
        "1",
        publish_url,
    ]

    print("[2] Iniciando Encoder Publisher...")
    pub_proc = subprocess.Popen(pub_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)

    # Dimensiones de cuadro
    frame_size = 640 * 480 * 3
    black_frame = b"\x00" * frame_size
    white_frame = b"\xff" * frame_size

    # Enviar frames negros iniciales para asentar publisher
    for _ in range(30):
        pub_proc.stdin.write(black_frame)
    pub_proc.stdin.flush()
    await asyncio.sleep(2)

    # COMANDO DE LECTURA (Receiver)
    # Leemos de SRT, decodificamos a rawvideo y escribimos en stdout
    read_url = "srt://127.0.0.1:8890?streamid=read:ping&latency=20000&mode=caller"
    rec_cmd = [
        ffmpeg_bin,
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-i",
        read_url,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-an",
        "-",
    ]

    print("[3] Iniciando Decoder Receiver...")
    rec_proc = subprocess.Popen(rec_cmd, stdout=subprocess.PIPE)

    # Dimensiones de cuadro
    frame_size = 640 * 480 * 3

    # Esperamos a que los procesos se establezcan
    await asyncio.sleep(3)
    print("[4] Procesos establecidos. Iniciando prueba de flashing (Blanco/Negro)...")

    black_frame = b"\x00" * frame_size
    white_frame = b"\xff" * frame_size

    latencies = []

    try:
        for i in range(5):
            # Enviar frames negros para asentar
            for _ in range(10):
                pub_proc.stdin.write(black_frame)
                pub_proc.stdin.flush()
                await asyncio.sleep(1 / 60)

            # Limpiar pipe de lectura
            # (En Python no es tan trivial sin select, pero asumimos que leemos a la par)

            # Flash blanco!
            send_time = time.perf_counter()
            pub_proc.stdin.write(white_frame)
            pub_proc.stdin.flush()

            # Enviar unos cuantos blancos para asegurar
            for _ in range(3):
                pub_proc.stdin.write(white_frame)
                pub_proc.stdin.flush()

            # Leer frames hasta encontrar blanco
            while True:
                raw_frame = rec_proc.stdout.read(frame_size)
                if not raw_frame or len(raw_frame) != frame_size:
                    break

                # Checkeamos el brillo (promedio)
                # Si el frame es mayormente blanco, lo detectamos
                avg_luma = sum(raw_frame[0:3000:3]) / 1000.0  # Sampleo rápido
                if avg_luma > 150:
                    recv_time = time.perf_counter()
                    ping_ms = (recv_time - send_time) * 1000
                    latencies.append(ping_ms)
                    print(f"   -> Flash {i + 1}: Detectado en {ping_ms:.2f} ms")
                    break

            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error durante el test: {e}")
    finally:
        pub_proc.terminate()
        rec_proc.terminate()
        mediamtx_manager.stop()

    if latencies:
        avg_ping = sum(latencies) / len(latencies)
        print("==================================================")
        print(f" RESULTADO: Latencia promedio (end-to-end) = {avg_ping:.2f} ms")
        if avg_ping < 50:
            print(" ¡ÉXITO! Latencia sub-50ms conseguida.")
        else:
            print(" Aviso: Latencia superior a 50ms. Verifica el hardware y SO.")
        print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_extreme_ping())
