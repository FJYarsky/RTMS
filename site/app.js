/**
 * RTMS — Real-Time Multicam System
 * Script de cliente para la landing page oficial
 * Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
 *
 * Motor bilingüe (Español por defecto / Inglés con bandera de UK),
 * resolución dinámica de releases vía API de GitHub y utilidades UI.
 */

// Diccionario de Traducciones Oficiales
const TRANSLATIONS = {
    es: {
        meta_title: "RTMS — Real-Time Multicam System | Servidor de Streaming de Baja Latencia para Windows",
        meta_desc: "Servidor de video multicámara de ultra-baja latencia para Windows vía SRT y MediaMTX hacia OBS Studio y vMix. Captura DirectShow, aceleración GPU y telemetría en tiempo real.",
        brand_sub: "Real-Time Multicam System",
        nav_resolve: "Qué Resuelve",
        nav_features: "Características",
        nav_security: "Seguridad",
        nav_quickstart: "Inicio Rápido",
        nav_faq: "FAQ",
        nav_tech: "Tecnologías",
        nav_download: "Descargar",
        skip_to_content: "Saltar al contenido principal",
        s3_tip_label: "Consejo de producción:",
        hero_pill: "Servidor Multicámara Nativo para Windows",
        hero_title_1: "Streaming de Ultra-Baja Latencia",
        hero_title_2: "Directo a tu OBS Studio y vMix",
        hero_subtitle: "Captura tus cámaras web, capturadoras HDMI y dispositivos virtuales en DirectShow. Transmite flujos independientes en red local mediante <strong>MediaMTX</strong> y <strong>SRT</strong> con latencia inferior a 100 ms y telemetría en vivo.",
        download_btn: "Descargar RTMS para Windows",
        meta_ver: "Versión:",
        meta_size: "Tamaño:",
        meta_date: "Fecha:",
        meta_type: "ZIP Portable",
        sublink_notes: "Notas de lanzamiento",
        sublink_obs: "Guía de configuración en OBS",
        spec_os: "Windows 10 / 11 (64-bit)",
        spec_portable: "Ejecutable nativo rtms.exe (Portable)",
        spec_dpapi: "Cifrado DPAPI Nativo",
        spec_latency: "MediaMTX Ingestion (&lt;100 ms)",
        hud_streams: "2 Activos",
        cam1_name: "Logitech C920 Pro HD",
        cam1_type: "Dispositivo Físico DirectShow",
        cam_live: "● EN VIVO",
        cam_stopped: "DETENIDO",
        cam_encoder_label: "Codificador:",
        cam_res_label: "Resolución & FPS:",
        cam_dest_label: "Destino SRT:",
        cam2_name: "Elgato Cam Link 4K",
        cam2_type: "Capturadora HDMI Externa",
        cam3_name: "NVIDIA Broadcast",
        cam3_type: "Cámara Virtual IA (Aislada)",
        cam3_status_label: "Estado:",
        cam3_status_val: "Reposo (0% CPU/GPU)",
        cam3_port_label: "Puerto asignado:",
        cam3_port_val: "Puerto 8890",
        cam3_policy_label: "Política:",
        cam3_policy_val: "Sin autoinicio forzado",
        resolve_tag: "Desafíos del DirectShow en Windows",
        resolve_title: "Qué Resuelve RTMS",
        resolve_desc: "Diseñado específicamente para eliminar los tres dolores de cabeza más comunes en transmisiones en vivo con múltiples cámaras.",
        prob1_title: "Desconexión Física de USB (Hotplug)",
        prob1_bad: "<strong>El problema clásico:</strong> Un tirón de cable USB en vivo congela la fuente en OBS para siempre o bloquea el controlador de video en Windows.",
        prob1_good: "<strong>La solución RTMS:</strong> Intercepta de inmediato los errores de hardware, marca el dispositivo en reposo y, al volver a enchufarlo, reanuda la transmisión limpia en menos de 5 segundos.",
        prob2_title: "Microcortes y Fluctuaciones de Red",
        prob2_bad: "<strong>El problema clásico:</strong> El streaming UDP crudo pierde paquetes en redes WiFi o switches congestionados, generando cuadros rotos y pixelación.",
        prob2_good: "<strong>La solución RTMS:</strong> Implementa SRT (Secure Reliable Transport) nativo con retransmisión ultrarrápida ante pérdidas y buffer ajustable en microsegundos.",
        prob3_title: "Saturación del Procesador (CPU)",
        prob3_bad: "<strong>El problema clásico:</strong> Codificar 3 o más cámaras simultáneas por software en CPU (`libx264`) degrada los FPS y satura la máquina.",
        prob3_good: "<strong>La solución RTMS:</strong> Autodetecta aceleración por silicio (NVIDIA NVENC, Intel QSV, AMD AMF) y solo conmuta a CPU como mecanismo de emergencia sin interrupción.",
        bento_tag: "Capacidades del Sistema",
        bento_title: "Con Qué Cuenta RTMS",
        bento_desc: "Funcionalidades diseñadas para estabilidad industrial en estudios de streaming y producciones en vivo.",
        b1_title: "Telemetría de Hardware en Vivo",
        b1_desc: "Monitoreo continuo de latencia, tasa de cuadros por segundo, porcentaje de uso de CPU, tráfico total de red y telemetría nativa de tarjeta gráfica NVIDIA vía NVML directo (`nvml.dll`) con tiempo de consulta inferior a 1 milisegundo.",
        b1_tag: "NVML Nativo &bull; Cero sobrecarga",
        b2_title: "Ingesta Desacoplada MediaMTX",
        b2_desc: "Servidor local integrado que independiza la captura del receptor. OBS o vMix pueden conectarse o desconectarse sin detener a FFmpeg ni causar reinicios de hardware en las cámaras.",
        b2_tag: "MediaMTX v1.9.3 &bull; Múltiples clientes",
        b3_title: "Aceleración Multi-Vendor",
        b3_desc: "Soporte nativo para codificación por hardware en tarjetas NVIDIA (`nvenc`), procesadores Intel Core/Arc (`qsv`) y tarjetas AMD Radeon (`amf`), con fallback automático a CPU.",
        b3_tag: "NVENC &bull; QSV &bull; AMF &bull; libx264",
        b4_title: "Blindaje de Kernel con Win32 Job Objects",
        b4_desc: "Aislamiento y control estricto del árbol de procesos a nivel de sistema operativo. Al cerrar RTMS, el kernel de Windows liquida al instante cualquier proceso subordinado de FFmpeg o MediaMTX sin dejar tareas huérfanas consumiendo GPU o puertos en segundo plano.",
        b4_tag: "Cero procesos huérfanos en memoria",
        b5_title: "Reconexión PnP & Watchdog",
        b5_desc: "Watchdog optimizado que detecta congelamiento de cuadros a 0 FPS y sondeo automático DirectShow cada 5 segundos para reanudar transmisiones tras desconexión física.",
        b5_tag: "Resiliencia desatendida",
        b6_title: "Persistencia ACID en SQLite",
        b6_desc: "Almacenamiento transaccional de alta concurrencia mediante SQLite con modo WAL (Write-Ahead Logging), garantizando integridad ante cierres repentinos sin archivos JSON corruptos.",
        b6_tag: "Integridad transaccional &bull; WAL",
        sec_tag: "Seguridad por Diseño",
        sec_title: "Arquitectura y Política de Seguridad",
        sec_c1_title: "Cifrado Nativo DPAPI",
        sec_c1_desc: "Las contraseñas de transmisión SRT se almacenan protegidas mediante las API criptográficas del usuario de Windows. Cero almacenamiento en texto plano.",
        sec_c2_title: "Sanitización de URLs y Logs",
        sec_c2_desc: "Ocultamiento automático de contraseñas SRT y tokens de sesión en consola, memoria y archivos de registro para prevenir fugas accidentales en capturas de pantalla.",
        sec_c3_title: "Panel Web Air-Gapped",
        sec_c3_desc: "Interfaz 100% offline sin dependencias en CDNs externas, con cabeceras estrictas de seguridad (CSP, X-Frame-Options, nosniff) y restricción de origen a 127.0.0.1.",
        sec_c4_title: "Tickets Criptográficos Efímeros",
        sec_c4_desc: "Tokens temporales de un solo uso para previsualizaciones MJPEG en vivo, evitando exponer credenciales globales a terceros en la red local.",
        sec_policy_btn: "Consultar Política de Seguridad Oficial (SECURITY.md)",
        sec_report_btn: "Reportar Vulnerabilidad Responsable (Email)",
        step_tag: "Puesta en Marcha en 2 Minutos",
        step_title: "De la Descarga a OBS en 3 Pasos",
        step_desc: "Sin comandos complejos ni instaladores intrusivos. Listo para transmitir de inmediato.",
        s1_title: "Descomprimir el Archivo ZIP",
        s1_desc: "Descarga el archivo portable y descomprime el contenido en cualquier carpeta de tu disco (por ejemplo en tu escritorio o disco secundario).",
        s1_box: "Carpeta limpia",
        s2_title: "Iniciar RTMS",
        s2_desc: "Haz doble clic en <code>rtms.exe</code> para iniciar el servidor. Se abrirá automáticamente la ventana nativa de control y telemetría.",
        s2_box: "Ejecutable nativo",
        s3_title: "Conectar en OBS Studio o vMix",
        s3_desc: "En OBS Studio o vMix, agrega una <strong>Fuente multimedia</strong> (desmarcando <em>Archivo local</em>). Cada cámara en RTMS genera su URL directa, o puedes guiarte con la siguiente <strong>plantilla de conexión</strong>:",
        s3_tag: "Plantilla de Conexión (Ejemplo)",
        s3_sample_url: "srt://127.0.0.1:8890?streamid=read:<span class=\"code-param\">&lt;ID_CAMARA&gt;</span>&amp;latency=120000",
        s3_copy_btn: "Copiar plantilla",
        s3_hint: "💡 <strong>Tip:</strong> Dentro de RTMS puedes copiar el enlace exacto de cada cámara con un clic. Reemplaza <code>&lt;ID_CAMARA&gt;</code> por el identificador de tu cámara y <code>127.0.0.1</code> por la IP local si transmites hacia otra PC en tu red.",
        tech_tag: "Ecosistema & Silicio",
        tech_title: "Tecnologías que Incluye",
        tech_desc: "Construido sobre estándares industriales de video, telecomunicaciones y seguridad de bajo nivel.",
        footer_brand_desc: "Estación de transmisión multicámara de alta fidelidad y ultra-baja latencia para Windows vía SRT y UDP hacia OBS Studio, vMix y VLC.",
        footer_col_project: "Proyecto",
        footer_repo: "Repositorio en GitHub",
        footer_releases: "Todos los Releases",
        footer_changelog: "Historial de Cambios",
        footer_license: "Licencia MIT",
        footer_col_docs: "Documentación",
        footer_faq: "Preguntas Frecuentes",
        footer_hw: "Compatibilidad de Hardware",
        footer_trouble: "Resolución de Problemas",
        footer_brand_guide: "Identidad Visual & Branding",
        footer_sec: "Política de Seguridad",
        footer_bug: "Reportar un Bug",
        footer_col_author: "Autor & Contacto",
        footer_profile: "Perfil de GitHub",
        footer_license_text: "Distribuido bajo la",
        footer_credit: "Desarrollado con pasión para la comunidad de streaming por",
        faq_tag: "Dudas Frecuentes",
        faq_title: "Preguntas Frecuentes sobre RTMS",
        faq_desc: "Todo lo que necesitas saber sobre compatibilidad, configuración y arquitectura de streaming.",
        faq_q1: "¿Qué es RTMS y cómo se conecta con OBS Studio o vMix?",
        faq_a1: "RTMS (Real-Time Multicam System) es un servidor local para Windows que captura dispositivos DirectShow (cámaras web, capturadoras HDMI, cámaras virtuales) y los transmite como flujos SRT independientes a través de MediaMTX. En OBS Studio o vMix, simplemente agregas una \"Fuente Multimedia\", desmarcas \"Archivo local\" y pegas la URL SRT generada (ej. <code>srt://127.0.0.1:8890?streamid=read:cam_1</code>).",
        faq_q2: "¿Qué diferencia a RTMS de capturar cámaras directamente en OBS o usar NDI?",
        faq_a2: "Capturar múltiples cámaras DirectShow directamente en OBS suele congelar el software si un cable USB se desconecta y satura el bus USB. NDI consume gran ancho de banda de red (100-150 Mbps por cámara) y exige licencias propietarias. RTMS desacopla la captura del receptor mediante MediaMTX, cuenta con reconexión automática PnP ante desconexiones físicas, y utiliza SRT con compresión por hardware (NVENC/QSV/AMF), logrando latencia inferior a 100 ms con mínimo consumo de CPU.",
        faq_q3: "¿Qué tarjetas gráficas y códecs de aceleración soporta RTMS?",
        faq_a3: "RTMS soporta codificación por hardware nativa: NVIDIA NVENC (<code>h264_nvenc</code>), Intel Quick Sync Video (<code>h264_qsv</code>) y AMD AMF (<code>h264_amf</code>). Si el equipo no cuenta con GPU compatible, activa automáticamente un fallback transparente a CPU (<code>libx264</code>).",
        faq_q4: "¿Qué sucede si una cámara USB se desenchufa durante una transmisión en vivo?",
        faq_a4: "El watchdog y el monitor DirectShow de RTMS interceptan la desconexión sin congelar OBS ni bloquear los controladores de Windows. El stream entra en reposo y, en cuanto vuelves a conectar el USB, RTMS reanuda el flujo de video automáticamente en menos de 5 segundos sin reiniciar la aplicación ni interrumpir tu directo.",
        faq_q5: "¿RTMS es gratuito, seguro y de código abierto?",
        faq_a5: "Sí. RTMS es 100% de código abierto bajo la Licencia MIT. Su código fuente está auditado en GitHub, no recopila telemetría externa, funciona de forma totalmente aislada (\"air-gapped\") en red local y cifra credenciales sensibles mediante Windows DPAPI."
    },
    en: {
        meta_title: "RTMS — Real-Time Multicam System | Ultra-Low Latency Streaming Server for Windows",
        meta_desc: "Ultra-low latency multicamera video server for Windows via SRT and MediaMTX to OBS Studio and vMix. DirectShow capture, GPU acceleration, and live telemetry.",
        brand_sub: "Real-Time Multicam System",
        nav_resolve: "What it Solves",
        nav_features: "Features",
        nav_security: "Security",
        nav_quickstart: "Quickstart",
        nav_faq: "FAQ",
        nav_tech: "Tech Stack",
        nav_download: "Download",
        skip_to_content: "Skip to main content",
        s3_tip_label: "Production Tip:",
        hero_pill: "Native Windows Multicam Server",
        hero_title_1: "Ultra-Low Latency Streaming",
        hero_title_2: "Directly to your OBS Studio & vMix",
        hero_subtitle: "Capture webcams, HDMI capture cards, and virtual devices via DirectShow. Stream independent feeds across your LAN using <strong>MediaMTX</strong> and <strong>SRT</strong> with sub-100ms latency and live telemetry.",
        download_btn: "Download RTMS for Windows",
        meta_ver: "Version:",
        meta_size: "Size:",
        meta_date: "Date:",
        meta_type: "Portable ZIP",
        sublink_notes: "Release notes",
        sublink_obs: "OBS setup guide",
        spec_os: "Windows 10 / 11 (64-bit)",
        spec_portable: "Native executable rtms.exe (Portable)",
        spec_dpapi: "Native DPAPI Encryption",
        spec_latency: "MediaMTX Ingestion (&lt;100 ms)",
        hud_streams: "2 Active",
        cam1_name: "Logitech C920 Pro HD",
        cam1_type: "DirectShow Physical Device",
        cam_live: "● LIVE",
        cam_stopped: "STOPPED",
        cam_encoder_label: "Encoder:",
        cam_res_label: "Resolution & FPS:",
        cam_dest_label: "SRT Destination:",
        cam2_name: "Elgato Cam Link 4K",
        cam2_type: "External HDMI Capture Card",
        cam3_name: "NVIDIA Broadcast",
        cam3_type: "AI Virtual Camera (Isolated)",
        cam3_status_label: "Status:",
        cam3_status_val: "Idle (0% CPU/GPU)",
        cam3_port_label: "Assigned port:",
        cam3_port_val: "Port 8890",
        cam3_policy_label: "Policy:",
        cam3_policy_val: "No forced autostart",
        resolve_tag: "DirectShow Challenges on Windows",
        resolve_title: "What RTMS Solves",
        resolve_desc: "Engineered specifically to eliminate the three most common bottlenecks in multicamera live streaming.",
        prob1_title: "Physical USB Disconnection (Hotplug)",
        prob1_bad: "<strong>The classic problem:</strong> An accidental USB cable pull freezes the OBS feed indefinitely or locks up the Windows video driver.",
        prob1_good: "<strong>The RTMS solution:</strong> Instantly intercepts hardware errors, marks the stream idle, and resumes cleanly within 5 seconds upon reconnecting.",
        prob2_title: "Network Jitter & Micro-Drops",
        prob2_bad: "<strong>The classic problem:</strong> Raw UDP streaming drops packets over WiFi or congested switches, causing broken frames and artifacts.",
        prob2_good: "<strong>The RTMS solution:</strong> Implements native SRT (Secure Reliable Transport) with ultra-fast packet retransmission and microsecond-level adaptive buffer.",
        prob3_title: "CPU Saturation & Overheating",
        prob3_bad: "<strong>The classic problem:</strong> Encoding 3 or more simultaneous cameras by software on CPU (`libx264`) degrades frame rates and saturates system cores.",
        prob3_good: "<strong>The RTMS solution:</strong> Auto-detects silicon hardware acceleration (NVIDIA NVENC, Intel QSV, AMD AMF) with seamless CPU fallback fail-safe.",
        bento_tag: "System Capabilities",
        bento_title: "RTMS Key Features",
        bento_desc: "Industrial-grade features built for live broadcast studios and production environments.",
        b1_title: "Live Hardware Telemetry",
        b1_desc: "Real-time monitoring of latency, framerate, CPU load, network traffic, and native NVIDIA GPU metrics via direct NVML (`nvml.dll`) with sub-millisecond polling.",
        b1_tag: "Native NVML &bull; Zero Overhead",
        b2_title: "Decoupled MediaMTX Ingestion",
        b2_desc: "Embedded local media server that decouples capture from client playback. OBS or vMix can disconnect or reconnect without resetting FFmpeg or hardware.",
        b2_tag: "MediaMTX v1.9.3 &bull; Multiple Viewers",
        b3_title: "Multi-Vendor Acceleration",
        b3_desc: "Native hardware encoding for NVIDIA GPUs (`nvenc`), Intel Core/Arc processors (`qsv`), and AMD Radeon (`amf`), with automatic CPU fallback.",
        b3_tag: "NVENC &bull; QSV &bull; AMF &bull; libx264",
        b4_title: "Kernel Shielding with Win32 Job Objects",
        b4_desc: "OS-level process tree isolation. When RTMS exits, the Windows kernel terminates all subordinate FFmpeg and MediaMTX child processes immediately without leftover background tasks.",
        b4_tag: "Zero orphan processes in memory",
        b5_title: "PnP Reconnection & Watchdog",
        b5_desc: "Optimized watchdog that detects 0 FPS frame stalls and polls DirectShow hardware every 5 seconds to resume streams automatically after USB disconnection.",
        b5_tag: "Unattended resilience",
        b6_title: "ACID Persistence in SQLite",
        b6_desc: "High-concurrency transactional database storage powered by SQLite with WAL (Write-Ahead Logging) mode, ensuring configuration integrity against sudden crashes.",
        b6_tag: "Transactional integrity &bull; WAL",
        sec_tag: "Security by Design",
        sec_title: "Security Architecture & Policy",
        sec_c1_title: "Native DPAPI Encryption",
        sec_c1_desc: "SRT stream passphrases are stored encrypted using Windows user-level cryptographic DPAPI. Zero plaintext credentials.",
        sec_c2_title: "URL & Log Sanitization",
        sec_c2_desc: "Automatic masking of SRT passphrases and session tokens in console output, memory, and log files to prevent accidental leaks in screenshots.",
        sec_c3_title: "Air-Gapped Web Panel",
        sec_c3_desc: "100% offline user interface with zero external CDN dependencies, strict security headers (CSP, X-Frame-Options, nosniff), and localhost-only CORS.",
        sec_c4_title: "Ephemeral Crypto Tickets",
        sec_c4_desc: "Single-use temporary cryptographic tokens for live MJPEG previews, avoiding exposure of global session credentials across the local network.",
        sec_policy_btn: "View Official Security Policy (SECURITY.md)",
        sec_report_btn: "Report Vulnerability Responsibly (Email)",
        step_tag: "Get Running in 2 Minutes",
        step_title: "From Download to OBS in 3 Steps",
        step_desc: "No complex terminal commands or intrusive installers. Ready to broadcast out of the box.",
        s1_title: "Extract the ZIP Package",
        s1_desc: "Download the portable archive and extract its contents into any folder on your drive (e.g. your Desktop or secondary drive).",
        s1_box: "Clean folder",
        s2_title: "Launch RTMS",
        s2_desc: "Double-click <code>rtms.exe</code> to start the server. The native control window and telemetry dashboard will open automatically.",
        s2_box: "Native executable",
        s3_title: "Connect in OBS Studio or vMix",
        s3_desc: "In OBS Studio or vMix, add a <strong>Media Source</strong> (unchecking <em>Local File</em>). Each active camera inside RTMS generates its own direct link, or you can reference this <strong>connection template</strong>:",
        s3_tag: "Connection Template (Example)",
        s3_sample_url: "srt://127.0.0.1:8890?streamid=read:<span class=\"code-param\">&lt;CAMERA_ID&gt;</span>&amp;latency=120000",
        s3_copy_btn: "Copy template",
        s3_hint: "💡 <strong>Tip:</strong> Inside RTMS, each active camera displays its exact link ready to copy with a single click. Replace <code>&lt;CAMERA_ID&gt;</code> with your camera identifier and <code>127.0.0.1</code> with your server's local IP if streaming to another PC.",
        tech_tag: "Ecosystem & Silicon",
        tech_title: "Included Technologies",
        tech_desc: "Built on top of industry-standard video, telecom, and low-level system security protocols.",
        footer_brand_desc: "High-fidelity, ultra-low latency multicamera streaming station for Windows via SRT and UDP to OBS Studio, vMix, and VLC.",
        footer_col_project: "Project",
        footer_repo: "GitHub Repository",
        footer_releases: "All Releases",
        footer_changelog: "Changelog",
        footer_license: "MIT License",
        footer_col_docs: "Documentation",
        footer_faq: "Frequently Asked Questions",
        footer_hw: "Hardware Compatibility",
        footer_trouble: "Troubleshooting Guide",
        footer_brand_guide: "Brand Identity & Guidelines",
        footer_sec: "Security Policy",
        footer_bug: "Report an Issue",
        footer_col_author: "Author & Contact",
        footer_profile: "GitHub Profile",
        footer_license_text: "Distributed under the",
        footer_credit: "Built with passion for the streaming community by",
        faq_tag: "Frequently Asked Questions",
        faq_title: "Frequently Asked Questions about RTMS",
        faq_desc: "Everything you need to know about compatibility, setup, and streaming architecture.",
        faq_q1: "What is RTMS and how does it connect to OBS Studio or vMix?",
        faq_a1: "RTMS (Real-Time Multicam System) is a local Windows server that captures DirectShow devices (webcams, HDMI capture cards, virtual cameras) and streams them as independent SRT feeds via MediaMTX. In OBS Studio or vMix, simply add a 'Media Source', uncheck 'Local File', and paste the generated SRT URL (e.g., <code>srt://127.0.0.1:8890?streamid=read:cam_1</code>).",
        faq_q2: "How does RTMS differ from direct OBS capture or NDI?",
        faq_a2: "Direct DirectShow capture in OBS often crashes or locks up video sources if a USB cable gets pulled and saturates the USB controller bus. NDI uses excessive network bandwidth (100-150 Mbps per camera) and requires proprietary licenses. RTMS decouples capture from playback via MediaMTX, provides automatic PnP hardware reconnection on cable drops, and leverages SRT with hardware compression (NVENC/QSV/AMF), achieving sub-100ms latency with minimal CPU overhead.",
        faq_q3: "What GPUs and hardware encoders are supported by RTMS?",
        faq_a3: "RTMS supports native hardware encoding for NVIDIA NVENC (<code>h264_nvenc</code>), Intel Quick Sync Video (<code>h264_qsv</code>), and AMD AMF (<code>h264_amf</code>). If no supported GPU is available, it transparently falls back to CPU encoding (<code>libx264</code>).",
        faq_q4: "What happens if a USB camera gets disconnected during a live broadcast?",
        faq_a4: "RTMS's watchdog and DirectShow monitor intercept the drop cleanly without crashing OBS or locking Windows drivers. The stream pauses into idle, and as soon as you plug the USB back in, RTMS resumes the feed automatically in under 5 seconds without restarting the app.",
        faq_q5: "Is RTMS free, secure, and open-source?",
        faq_a5: "Yes. RTMS is 100% open-source under the MIT License. Its source code is audited on GitHub, collects zero external telemetry, operates fully air-gapped on your LAN, and encrypts sensitive credentials using Windows DPAPI."
    }
};

// SVG de Banderas Oficiales
const ICONS = {
    uk: `<svg class="flag-icon" viewBox="0 0 60 30" width="20" height="12" xmlns="http://www.w3.org/2000/svg">
        <clipPath id="uk-clip"><path d="M0,0 v30 h60 v-30 z"/></clipPath>
        <clipPath id="uk-diag"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z"/></clipPath>
        <g clip-path="url(#uk-clip)">
            <path d="M0,0 v30 h60 v-30 z" fill="#012169"/>
            <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/>
            <path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#uk-diag)" stroke="#C8102E" stroke-width="4"/>
            <path d="M30,0 v30 M0,15 h60" stroke="#fff" stroke-width="10"/>
            <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" stroke-width="6"/>
        </g>
    </svg>`,
    argentina: `<svg class="flag-icon" viewBox="0 0 60 36" width="20" height="12" xmlns="http://www.w3.org/2000/svg">
        <rect width="60" height="12" fill="#74ACDF"/>
        <rect y="12" width="60" height="12" fill="#FFFFFF"/>
        <rect y="24" width="60" height="12" fill="#74ACDF"/>
        <polygon points="35.2,18.0 32.9,18.6 34.8,20.0 32.5,19.7 33.7,21.7 31.7,20.5 32.0,22.8 30.6,20.9 30.0,23.2 29.4,20.9 28.0,22.8 28.3,20.5 26.3,21.7 27.5,19.7 25.2,20.0 27.1,18.6 24.8,18.0 27.1,17.4 25.2,16.0 27.5,16.3 26.3,14.3 28.3,15.5 28.0,13.2 29.4,15.1 30.0,12.8 30.6,15.1 32.0,13.2 31.7,15.5 33.7,14.3 32.5,16.3 34.8,16.0 32.9,17.4" fill="#F6B40E" stroke="#85340A" stroke-width="0.3"/>
        <circle cx="30" cy="18" r="2.6" fill="#F6B40E" stroke="#85340A" stroke-width="0.5"/>
        <circle cx="28.9" cy="17.4" r="0.4" fill="#85340A"/>
        <circle cx="31.1" cy="17.4" r="0.4" fill="#85340A"/>
        <path d="M29.2,19 Q30,19.8 30.8,19" fill="none" stroke="#85340A" stroke-width="0.4" stroke-linecap="round"/>
    </svg>`
};

let currentLang = 'es';
let latestReleaseData = null;

document.addEventListener('DOMContentLoaded', () => {
    initLanguage();
    initDynamicRelease();
    initCopyButtons();
    initNavbarScroll();
    initSmoothScrollAndAnchors();
    initActiveNavSpy();
    initMobileMenu();
});

/**
 * Inicializa el sistema de traducción y el botón toggle con bandera.
 */
function initLanguage() {
    const savedLang = localStorage.getItem('rtms_lang') || 'es';
    const langBtn = document.getElementById('lang-toggle-btn');

    setLanguage(savedLang);

    if (langBtn) {
        langBtn.addEventListener('click', () => {
            const newLang = currentLang === 'es' ? 'en' : 'es';
            setLanguage(newLang);
        });
    }
}

/**
 * Aplica el idioma especificado en toda la página.
 */
function setLanguage(lang) {
    if (!TRANSLATIONS[lang]) return;
    currentLang = lang;
    localStorage.setItem('rtms_lang', lang);
    document.documentElement.lang = lang;

    const t = TRANSLATIONS[lang];

    // Actualizar metadatos del documento
    document.title = t.meta_title;
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) metaDesc.setAttribute('content', t.meta_desc);

    // Traducir todos los elementos con data-i18n
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key] !== undefined) {
            el.innerHTML = t[key];
        }
    });

    // Actualizar el botón de alternancia de idioma con la bandera correspondiente
    const langBtn = document.getElementById('lang-toggle-btn');
    if (langBtn) {
        if (lang === 'es') {
            // Actualmente en español -> mostrar bandera UK para cambiar a inglés
            langBtn.innerHTML = `${ICONS.uk} <span>EN</span>`;
            langBtn.setAttribute('title', 'Switch to English');
            langBtn.setAttribute('aria-label', 'Switch to English');
        } else {
            // Actualmente en inglés -> mostrar bandera Argentina para volver a español
            langBtn.innerHTML = `${ICONS.argentina} <span>ES</span>`;
            langBtn.setAttribute('title', 'Cambiar a Español');
            langBtn.setAttribute('aria-label', 'Cambiar a Español');
        }
    }

    // Actualizar atributos de accesibilidad según el idioma
    const githubLink = document.querySelector('.btn-github');
    if (githubLink) {
        const ghLabel = lang === 'es' ? 'Repositorio de RTMS en GitHub' : 'RTMS GitHub Repository';
        githubLink.setAttribute('aria-label', ghLabel);
        githubLink.setAttribute('title', ghLabel);
    }
    const brandLink = document.querySelector('.brand');
    if (brandLink) {
        brandLink.setAttribute('aria-label', lang === 'es' ? 'RTMS — Inicio' : 'RTMS — Home');
    }
    const copyBtn = document.querySelector('.btn-copy');
    if (copyBtn) {
        copyBtn.setAttribute('title', lang === 'es' ? 'Copiar plantilla de ejemplo' : 'Copy sample template');
        copyBtn.setAttribute('aria-label', lang === 'es' ? 'Copiar plantilla de conexión SRT al portapapeles' : 'Copy SRT connection template to clipboard');
    }

    // Actualizar fecha dinámica según el idioma seleccionado
    if (latestReleaseData && latestReleaseData.published_at) {
        updateDynamicDate(latestReleaseData.published_at);
    }
}

/**
 * Consulta la API de GitHub para obtener la última versión oficial publicada,
 * su tamaño en MB, fecha de publicación y el link directo al archivo zip de Windows.
 */
async function initDynamicRelease() {
    const downloadBtn = document.getElementById('primary-download-btn');
    const downloadSize = document.getElementById('download-size');
    const downloadTag = document.getElementById('download-tag');

    const REPO_OWNER = 'FJYarsky';
    const REPO_NAME = 'RTMS';
    const API_URL = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`;
    const FALLBACK_URL = `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/latest`;

    try {
        const response = await fetch(API_URL, {
            headers: { 'Accept': 'application/vnd.github.v3+json' }
        });

        if (!response.ok) {
            throw new Error(`GitHub API HTTP ${response.status}`);
        }

        const release = await response.json();
        latestReleaseData = release;
        const tagName = release.tag_name || 'v2.7.0';

        // Actualizar badge de versión en la sección de descarga
        if (downloadTag) downloadTag.textContent = tagName;

        // Buscar el archivo ZIP de Windows x64 en los assets del release
        const zipAsset = release.assets?.find(asset => 
            /RTMS-.*-Windows-x64\.zip/i.test(asset.name) || asset.name.endsWith('.zip')
        );

        if (zipAsset) {
            if (downloadBtn) {
                downloadBtn.href = zipAsset.browser_download_url;
                downloadBtn.setAttribute('title', `Descargar ${zipAsset.name}`);
            }

            if (downloadSize && zipAsset.size) {
                const sizeMB = (zipAsset.size / (1024 * 1024)).toFixed(1);
                downloadSize.textContent = `${sizeMB} MB`;
            }

            if (release.published_at) {
                updateDynamicDate(release.published_at);
            }
        } else {
            if (downloadBtn) downloadBtn.href = release.html_url || FALLBACK_URL;
        }

    } catch (err) {
        console.warn('No se pudo consultar la API de GitHub, utilizando fallback canónico:', err);
        if (downloadBtn) downloadBtn.href = FALLBACK_URL;
        if (downloadTag) downloadTag.textContent = 'v2.7.0';
        if (downloadSize) downloadSize.textContent = '~52 MB';
        const downloadDate = document.getElementById('download-date');
        if (downloadDate) downloadDate.textContent = currentLang === 'es' ? 'Oficial' : 'Official';
    }
}

/**
 * Formatea la fecha de release según el idioma activo.
 */
function updateDynamicDate(isoDateStr) {
    const downloadDate = document.getElementById('download-date');
    if (!downloadDate) return;

    const pubDate = new Date(isoDateStr);
    const locale = currentLang === 'es' ? 'es-ES' : 'en-US';
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    downloadDate.textContent = pubDate.toLocaleDateString(locale, options);
}

/**
 * Permite copiar cadenas de texto (como la URL de OBS) con un solo clic y feedback visual.
 */
function initCopyButtons() {
    document.querySelectorAll('[data-copy-target]').forEach(button => {
        button.addEventListener('click', async () => {
            const targetId = button.getAttribute('data-copy-target');
            const targetEl = document.getElementById(targetId);
            if (!targetEl) return;

            const textToCopy = targetEl.textContent.trim();
            let success = false;

            // Intento primario: Clipboard API (requiere Secure Context: HTTPS o localhost)
            if (navigator.clipboard && navigator.clipboard.writeText) {
                try {
                    await navigator.clipboard.writeText(textToCopy);
                    success = true;
                } catch (_) { /* Fallback abajo */ }
            }

            // Fallback: execCommand para contextos no seguros (file://)
            if (!success) {
                try {
                    const ta = document.createElement('textarea');
                    ta.value = textToCopy;
                    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0';
                    document.body.appendChild(ta);
                    ta.select();
                    success = document.execCommand('copy');
                    document.body.removeChild(ta);
                } catch (_) { /* Silencioso */ }
            }

            if (success) {
                const originalHtml = button.innerHTML;
                const feedbackText = currentLang === 'es' ? '¡Plantilla copiada!' : 'Template copied!';
                button.classList.add('copied');
                button.innerHTML = `
                    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span class="btn-copy-label">${feedbackText}</span>
                `;

                setTimeout(() => {
                    button.classList.remove('copied');
                    button.innerHTML = originalHtml;
                }, 2200);
            } else {
                console.error('No se pudo copiar al portapapeles en este entorno.');
            }
        });
    });
}


/**
 * Detecta el scroll vertical para aplicar elevación y sombra al navbar fijo.
 */
function initNavbarScroll() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    const handleScroll = () => {
        if (window.scrollY > 15) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
}

/**
 * Centra perfectamente cada sección al hacer clic en las etiquetas de navegación,
 * compensando exactamente la altura del header fijo y aplicando foco accesible.
 */
function initSmoothScrollAndAnchors() {
    const navAnchors = document.querySelectorAll('a[href^="#"]');
    const navbar = document.querySelector('.navbar');

    navAnchors.forEach(anchor => {
        anchor.addEventListener('click', (e) => {
            const href = anchor.getAttribute('href');
            if (!href || href === '#') {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: 'smooth' });
                closeMobileMenu();
                return;
            }

            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                const navHeight = navbar ? navbar.offsetHeight : 64;
                const extraPadding = 18; // Margen de respiración estética
                const elementPosition = target.getBoundingClientRect().top + window.pageYOffset;
                const offsetPosition = elementPosition - navHeight - extraPadding;

                window.scrollTo({
                    top: Math.max(0, offsetPosition),
                    behavior: 'smooth'
                });

                // Actualizar historial URL de forma limpia sin salto brusco
                if (history.pushState) {
                    history.pushState(null, null, href);
                } else {
                    location.hash = href;
                }

                // Accesibilidad: transferir foco al elemento de destino
                target.setAttribute('tabindex', '-1');
                target.focus({ preventScroll: true });

                closeMobileMenu();
            }
        });
    });
}

/**
 * Resalta en tiempo real la etiqueta del navbar correspondiente a la sección visible.
 */
function initActiveNavSpy() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-menu .nav-link');
    if (!sections.length || !navLinks.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const currentId = entry.target.getAttribute('id');
                navLinks.forEach(link => {
                    if (link.getAttribute('href') === `#${currentId}`) {
                        link.classList.add('active');
                        link.setAttribute('aria-current', 'true');
                    } else {
                        link.classList.remove('active');
                        link.removeAttribute('aria-current');
                    }
                });
            }
        });
    }, {
        rootMargin: '-20% 0px -65% 0px',
        threshold: 0
    });

    sections.forEach(sec => observer.observe(sec));
}

/**
 * Controla el menú hamburguesa accesible en dispositivos móviles y tablets.
 */
function initMobileMenu() {
    const toggleBtn = document.getElementById('nav-toggle-btn');
    const navMenu = document.getElementById('nav-menu');
    if (!toggleBtn || !navMenu) return;

    toggleBtn.addEventListener('click', () => {
        const isOpen = navMenu.classList.toggle('open');
        toggleBtn.classList.toggle('active', isOpen);
        toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        toggleBtn.setAttribute('aria-label', isOpen ? 
            (currentLang === 'es' ? 'Cerrar menú de navegación' : 'Close navigation menu') : 
            (currentLang === 'es' ? 'Abrir menú de navegación' : 'Open navigation menu')
        );
    });

    // Cerrar al presionar Escape para accesibilidad
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && navMenu.classList.contains('open')) {
            closeMobileMenu();
            toggleBtn.focus();
        }
    });

    // Cerrar al hacer clic fuera del menú
    document.addEventListener('click', (e) => {
        if (navMenu.classList.contains('open') && !navMenu.contains(e.target) && !toggleBtn.contains(e.target)) {
            closeMobileMenu();
        }
    });
}

function closeMobileMenu() {
    const toggleBtn = document.getElementById('nav-toggle-btn');
    const navMenu = document.getElementById('nav-menu');
    if (navMenu) navMenu.classList.remove('open');
    if (toggleBtn) {
        toggleBtn.classList.remove('active');
        toggleBtn.setAttribute('aria-expanded', 'false');
        toggleBtn.setAttribute('aria-label', currentLang === 'es' ? 'Abrir menú de navegación' : 'Open navigation menu');
    }
}
