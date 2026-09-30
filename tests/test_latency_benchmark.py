# ==============================================================================
# RTMS — Real-Time Multicam System
# Pruebas unitarias e integración de latencia, ping y optimización de recepción local.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Suite de pruebas para el motor de benchmark de latencia y ping local."""

import os
import socket
import subprocess
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.hardware import get_ffmpeg_bin
from core.latency_bench import (
    LatencyBenchmarkEngine,
    LocalLatencyBenchmark,
    PingStatistics,
    VideoPipelineLatencyReport,
    calculate_percentile,
)


class TestPingStatistics:
    """Pruebas unitarias para cálculo de percentiles y PingStatistics."""

    def test_calculate_percentile_empty_and_single(self):
        assert calculate_percentile([], 0.95) == 0.0
        assert calculate_percentile([42.5], 0.95) == 42.5
        assert calculate_percentile([42.5], 0.99) == 42.5

    def test_calculate_percentile_multiple(self):
        data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        # Con 10 elementos, p95 (95%) es el 10mo (100.0) y p50 es el 5to (50.0)
        p50 = calculate_percentile(data, 0.50)
        p95 = calculate_percentile(data, 0.95)
        p99 = calculate_percentile(data, 0.99)
        assert p50 == 50.0
        assert p95 == 100.0
        assert p99 == 100.0

    def test_ping_statistics_to_dict_and_summary(self):
        stats = PingStatistics(
            protocol="udp_loopback",
            target="127.0.0.1:9876",
            samples_count=100,
            min_ms=0.1234,
            avg_ms=0.4567,
            max_ms=1.2345,
            jitter_ms=0.0891,
            loss_rate=0.02,
            p95_ms=0.8123,
            p99_ms=1.1234,
            details={"test_key": "val"},
        )

        d = stats.to_dict()
        assert d["protocol"] == "udp_loopback"
        assert d["target"] == "127.0.0.1:9876"
        assert d["samples_count"] == 100
        assert d["min_ms"] == 0.1234
        assert d["avg_ms"] == 0.4567
        assert d["max_ms"] == 1.2345
        assert d["jitter_ms"] == 0.0891
        assert d["p95_ms"] == 0.8123
        assert d["p99_ms"] == 1.1234
        assert d["loss_rate"] == 0.02
        assert d["details"] == {"test_key": "val"}

        summary = stats.summary()
        assert "UDP_LOOPBACK" in summary
        assert "127.0.0.1:9876" in summary
        assert "Min: 0.12ms" in summary
        assert "p95: 0.81ms" in summary
        assert "Pérdida: 2.0%" in summary

    def test_video_pipeline_report_to_dict(self):
        rep = VideoPipelineLatencyReport(
            protocol="srt",
            url="srt://127.0.0.1:8890",
            time_to_first_frame_ms=45.2,
            fps_measured=59.94,
            frames_received=120,
            inter_frame_jitter_ms=1.25,
            buffer_underruns=0,
            recommended_vlc_caching_ms=30,
            status="OPTIMAL",
            notes=["Note 1"],
        )
        d = rep.to_dict()
        assert d["protocol"] == "srt"
        assert d["time_to_first_frame_ms"] == 45.2
        assert d["fps_measured"] == 59.94
        assert d["frames_received"] == 120
        assert d["recommended_vlc_caching_ms"] == 30
        assert d["status"] == "OPTIMAL"

    def test_alias_equivalence(self):
        assert LocalLatencyBenchmark is LatencyBenchmarkEngine


class TestLatencyBenchmarkEngineUdp:
    """Pruebas para medición de ping por sockets UDP."""

    def test_measure_udp_socket_ping_loopback_native(self):
        """Valida que el loopback interno nativo mida paquetes con cero pérdidas."""
        stats = LatencyBenchmarkEngine.measure_udp_socket_ping(port=29876, iterations=50)
        assert stats.samples_count == 50
        assert stats.loss_rate == 0.0
        assert stats.min_ms >= 0.0
        assert stats.avg_ms >= stats.min_ms
        assert stats.max_ms >= stats.avg_ms
        assert stats.p95_ms >= stats.min_ms
        assert stats.p99_ms >= stats.p95_ms

    def test_measure_udp_socket_ping_mock_echo_server(self):
        """Valida la medición contra un socket UDP servidor externo de eco."""
        stop_event = threading.Event()
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_sock.bind(("127.0.0.1", 0))
        server_port = server_sock.getsockname()[1]
        server_sock.settimeout(0.2)

        def echo_worker():
            while not stop_event.is_set():
                try:
                    data, addr = server_sock.recvfrom(512)
                    server_sock.sendto(data, addr)
                except socket.timeout:
                    continue
                except OSError:
                    break

        thread = threading.Thread(target=echo_worker, daemon=True)
        thread.start()

        try:
            stats = LatencyBenchmarkEngine.measure_udp_socket_ping(port=server_port, iterations=25, bind_receiver=False)
            assert stats.samples_count == 25
            assert stats.loss_rate == 0.0
            assert stats.avg_ms > 0.0
            assert stats.p95_ms > 0.0
        finally:
            stop_event.set()
            server_sock.close()
            thread.join(timeout=1.0)

    def test_measure_udp_socket_ping_unreachable_timeout(self):
        """Valida el manejo de puertos inalcanzables / sin escucha."""
        stats = LatencyBenchmarkEngine.measure_udp_socket_ping(
            port=58912, iterations=5, timeout=0.01, bind_receiver=False
        )
        assert stats.samples_count == 0
        assert stats.loss_rate == 1.0
        assert stats.min_ms == 0.0
        assert stats.avg_ms == 0.0

    def test_measure_udp_socket_ping_zero_iterations(self):
        """Valida que cero iteraciones retorne estructura limpia."""
        stats = LatencyBenchmarkEngine.measure_udp_socket_ping(iterations=0)
        assert stats.samples_count == 0
        assert stats.loss_rate == 0.0

    def test_measure_udp_socket_ping_send_oserror(self):
        """Valida manejo de fallo de red al enviar datagrama."""
        with patch("socket.socket.sendto", side_effect=OSError("Network unreachable")):
            stats = LatencyBenchmarkEngine.measure_udp_socket_ping(iterations=5, timeout=0.01)
            assert stats.samples_count == 0
            assert stats.loss_rate == 1.0


class TestLatencyBenchmarkEngineTcp:
    """Pruebas para medición de ping por conexión TCP SYN/ACK."""

    def test_measure_tcp_connect_ping_against_mock_server(self):
        """Valida medición de handshake TCP contra servidor local."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("127.0.0.1", 0))
        server_port = server_sock.getsockname()[1]
        server_sock.listen(10)
        stop_event = threading.Event()

        def accept_worker():
            while not stop_event.is_set():
                try:
                    server_sock.settimeout(0.2)
                    client, _ = server_sock.accept()
                    client.close()
                except socket.timeout:
                    continue
                except OSError:
                    break

        thread = threading.Thread(target=accept_worker, daemon=True)
        thread.start()

        try:
            stats = LatencyBenchmarkEngine.measure_tcp_connect_ping(port=server_port, iterations=10)
            assert stats.samples_count == 10
            assert stats.loss_rate == 0.0
            assert stats.avg_ms > 0.0
            assert stats.p95_ms >= stats.min_ms
        finally:
            stop_event.set()
            server_sock.close()
            thread.join(timeout=1.0)

    def test_measure_tcp_connect_ping_unreachable(self):
        """Valida fallo de conexión TCP en puerto cerrado."""
        stats = LatencyBenchmarkEngine.measure_tcp_connect_ping(port=59998, iterations=3, timeout=0.05)
        assert stats.samples_count == 0
        assert stats.loss_rate == 1.0
        assert stats.avg_ms == 0.0

    def test_measure_tcp_connect_ping_zero_iterations(self):
        """Valida que cero iteraciones retorne estructura limpia."""
        stats = LatencyBenchmarkEngine.measure_tcp_connect_ping(iterations=0)
        assert stats.samples_count == 0
        assert stats.loss_rate == 0.0


class TestLatencyBenchmarkEngineVlcCaching:
    """Pruebas para análisis de buffers y advertencias de VLC."""

    def test_vlc_caching_none_vlc_path(self):
        engine = LatencyBenchmarkEngine(vlc_path=None)
        engine.vlc_path = None
        res = engine.test_vlc_caching_limits("srt://127.0.0.1:8890")
        assert res == {}

    def test_vlc_caching_limits_parsing_clean(self):
        """Valida detección de flujo estable con códec decodificado y sin underruns."""
        engine = LatencyBenchmarkEngine(vlc_path="dummy_vlc.exe")
        mock_output = (
            "main demux: using access module srt\n"
            "avcodec decoder: using ffmpeg decoder h264\n"
            "main demux: received first data for pts 1000\n"
        )

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", mock_output)

        with patch("subprocess.Popen", return_value=mock_proc):
            res = engine.test_vlc_caching_limits("srt://127.0.0.1:8890", caching_values=[30, 50])
            assert 30 in res
            assert 50 in res
            assert res[30]["stable"] is True
            assert res[30]["underruns"] == 0
            assert res[30]["decoded"] is True
            assert res[30]["received_data"] is True

    def test_vlc_caching_limits_parsing_underruns_and_jitter(self):
        """Valida captura de advertencias de underrun y picture is too late."""
        engine = LatencyBenchmarkEngine(vlc_path="dummy_vlc.exe")
        mock_output = (
            "avcodec decoder: using ffmpeg decoder h264\n"
            "main warning: picture is too late to be displayed (delayed by 40 ms)\n"
            "main warning: buffer underrun (-30000 us)\n"
            "main warning: jitter detected in stream\n"
        )

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", mock_output)

        with patch("subprocess.Popen", return_value=mock_proc):
            res = engine.test_vlc_caching_limits("srt://127.0.0.1:8890", caching_values=[20])
            assert res[20]["stable"] is False
            assert res[20]["buffer_underruns"] == 1
            assert res[20]["picture_late_warnings"] == 1
            assert res[20]["underruns"] == 2
            assert res[20]["jitter_warnings"] >= 2

    def test_vlc_caching_timeout_handling(self):
        """Valida manejo de expiración de timeout en VLC."""
        engine = LatencyBenchmarkEngine(vlc_path="dummy_vlc.exe")
        mock_proc = MagicMock()
        # Primer communicate genera TimeoutExpired, el segundo tras kill entrega el log
        mock_proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="vlc", timeout=5),
            ("", "main demux: received first data h264"),
        ]

        with patch("subprocess.Popen", return_value=mock_proc):
            res = engine.test_vlc_caching_limits("srt://127.0.0.1:8890", caching_values=[50])
            mock_proc.kill.assert_called_once()
            assert res[50]["decoded"] is True

    def test_vlc_caching_oserror(self):
        """Valida manejo de error de ejecución del binario VLC."""
        engine = LatencyBenchmarkEngine(vlc_path="nonexistent_vlc.exe")
        with patch("subprocess.Popen", side_effect=OSError("Exec format error")):
            res = engine.test_vlc_caching_limits("srt://127.0.0.1:8890", caching_values=[50])
            assert res[50]["stable"] is False
            assert "error" in res[50]


@pytest.mark.asyncio
class TestLatencyBenchmarkEngineVideoPipeline:
    """Pruebas para benchmark de pipeline de video FFmpeg."""

    async def test_video_pipeline_mocked_frames_calculation(self):
        """Valida cálculo de TTFF, FPS y Jitter a partir de marcas de tiempo de showinfo."""
        engine = LatencyBenchmarkEngine(ffmpeg_bin="ffmpeg.exe")

        mock_sender = MagicMock()
        mock_sender.wait.return_value = 0

        # Simular 30 frames de salida showinfo emitidos por el receptor
        showinfo_lines = []
        for i in range(30):
            showinfo_lines.append(
                f"[Parsed_showinfo_0 @ 00000213038ea840] n:{i} pts:{i * 1000} pts_time:{i * 0.016667} pos:1024 fmt:yuv420p\n".encode(
                    "utf-8"
                )
            )
        showinfo_lines.append(b"")  # EOF

        mock_receiver = MagicMock()
        mock_receiver.stderr.readline = AsyncMock(side_effect=showinfo_lines)
        mock_receiver.wait = AsyncMock(return_value=0)

        with (
            patch("subprocess.Popen", return_value=mock_sender),
            patch("asyncio.create_subprocess_exec", return_value=mock_receiver),
        ):
            report = await engine.benchmark_video_pipeline(
                protocol="srt",
                port=8890,
                duration_sec=0.2,
            )

            assert report.frames_received == 30
            assert report.time_to_first_frame_ms > 0.0
            assert report.fps_measured > 0.0
            assert report.recommended_vlc_caching_ms in (30, 50, 100)
            assert report.buffer_underruns == 0

    async def test_video_pipeline_sender_failure(self):
        """Valida manejo de excepción cuando el emisor FFmpeg no puede iniciar."""
        engine = LatencyBenchmarkEngine(ffmpeg_bin="nonexistent_ffmpeg.exe")
        with patch("subprocess.Popen", side_effect=OSError("Binary not found")):
            report = await engine.benchmark_video_pipeline(protocol="srt")
            assert report.status == "FAILED"
            assert report.frames_received == 0
            assert report.buffer_underruns == 1

    async def test_video_pipeline_receiver_failure(self):
        """Valida manejo de fallo al iniciar el receptor FFmpeg."""
        engine = LatencyBenchmarkEngine(ffmpeg_bin="ffmpeg.exe")
        mock_sender = MagicMock()
        with (
            patch("subprocess.Popen", return_value=mock_sender),
            patch("asyncio.create_subprocess_exec", side_effect=OSError("Receiver failed")),
        ):
            report = await engine.benchmark_video_pipeline(protocol="srt")
            assert report.status == "FAILED"
            mock_sender.terminate.assert_called()

    async def test_video_pipeline_no_frames_timeout(self):
        """Valida comportamiento cuando el receptor no recibe ningún frame dentro del tiempo límite."""
        engine = LatencyBenchmarkEngine(ffmpeg_bin="ffmpeg.exe")
        mock_sender = MagicMock()
        mock_receiver = MagicMock()
        # Stream sin cuadros
        mock_receiver.stderr.readline = AsyncMock(return_value=b"")
        mock_receiver.wait = AsyncMock(return_value=0)

        with (
            patch("subprocess.Popen", return_value=mock_sender),
            patch("asyncio.create_subprocess_exec", return_value=mock_receiver),
        ):
            report = await engine.benchmark_video_pipeline(
                protocol="srt",
                duration_sec=0.1,
            )
            assert report.frames_received == 0
            assert report.status == "NO_FRAMES"
            assert report.time_to_first_frame_ms == 0.0

    async def test_video_pipeline_lightweight_real_ffmpeg(self):
        """Prueba de integración ligera con FFmpeg real usando UDP loopback."""
        ffmpeg_bin = get_ffmpeg_bin()
        if not os.path.exists(ffmpeg_bin) or os.environ.get("CI"):
            pytest.skip("Prueba de pipeline FFmpeg real omitida en entorno CI o sin binario")

        from core.port_mgr import port_manager

        engine = LatencyBenchmarkEngine(ffmpeg_bin=ffmpeg_bin)
        test_port = port_manager.allocate_port(29990)
        try:
            report = await engine.benchmark_video_pipeline(
                protocol="udp",
                port=test_port,
                duration_sec=3.5,
            )
        finally:
            port_manager.release_port(test_port)

        assert report.protocol == "udp"
        assert report.frames_received >= 3
        assert report.time_to_first_frame_ms > 0.0
