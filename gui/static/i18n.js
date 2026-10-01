// ==============================================================================
// RTMS — Real-Time Multicam System
// Sistema de Internacionalización Bilingüe (Español 🇦🇷 / English 🇺🇸)
// Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
// ==============================================================================

const I18N_DICTIONARY = {
    es: {
        // Encabezado y Navegación
        nav_section_main: "Principal",
        nav_connect: "Conectar OBS/VLC",
        nav_section_mgmt: "Gestión",
        nav_cameras: "Cámaras",
        nav_section_sys: "Gestión del Sistema",
        nav_power: "Gestión de Energía",
        nav_system: "Sistema y Arranque",
        nav_website: "Sitio Web",
        btn_stop_all: "Detener Todo",
        btn_exit_app: "Salir / Finalizar",
        btn_about: "Acerca de / Contacto",
        developed_by_label: "Desarrollado por",
        author_support: "Soporte Oficial",
        hud_cpu: "CPU",
        hud_gpu: "GPU",
        hud_ram: "RAM",
        hud_net: "RED",
        hud_bitrate: "BITRATE",
        hud_telemetry_tooltip: "Clic para ver panel detallado de telemetría",
        hud_cpu_tooltip: "Uso actual del procesador (CPU)",
        hud_gpu_tooltip: "Uso actual de tarjeta gráfica (GPU)",
        hud_ram_tooltip: "Uso actual de memoria RAM",
        hud_net_tooltip: "Tráfico actual de red del sistema",
        hud_bitrate_tooltip: "Ancho de banda total emitido (Streams RTMS)",
        nav_about_tooltip: "Ver información del software y autor",
        nav_website_tooltip: "Sitio Web Oficial de RTMS",
        nav_emergency_tooltip: "Detener inmediatamente todas las transmisiones activas",
        nav_kill_tooltip: "Finalizar totalmente todos los procesos de RTMS y streaming",
        btn_copy_chip_tooltip: "Clic para copiar al portapapeles",
        btn_factory_reset_tooltip: "Restablecer configuración de fábrica y limpiar datos temporales",
        preview_ffplay_tooltip: "Abrir en ventana flotante externa con baja latencia",
        arg_tribute_tooltip: "Desarrollo 100% argentino con orgullo e identidad soberana",
        streams_active: "activos",
        streams_total: "total",

        // Vista de Conexión (OBS / VLC)
        connect_title: "Conexión a Software de Producción",
        connect_desc: "Conecta tus señales de video multicámara de baja latencia a OBS Studio, vMix o reproductores VLC en tu red.",
        ip_title_label: "IP del Servidor en la Red Local",
        copy_server_ip: "Copiar IP",
        active_streams_header: "Direcciones de Transmisión Activas",
        searching_active_streams: "Buscando flujos de transmisión activos...",
        active_streams_empty: "No hay transmisiones activas en este momento. Ve a la sección de <strong>Cámaras</strong> y haz clic en <strong>Iniciar</strong> para comenzar a emitir hacia OBS.",
        obs_guide_header: "Guía de Configuración Rápida en OBS Studio",
        obs_guide_alert: "<strong>Protocolo SRT Recomendado:</strong> SRT ofrece corrección automática de paquetes y latencia inferior a 100ms. Configura estas fuentes en la <strong>computadora donde corre OBS</strong>.",
        obs_step_1_title: "Crear Fuente Multimedia en OBS",
        obs_step_1_desc: "Haz clic en <strong>+</strong> en el panel de Fuentes, y elige <strong>Fuente multimedia</strong>.",
        obs_step_2_title: "Desmarcar 'Archivo local'",
        obs_step_2_desc: "Desmarca la casilla <strong>Archivo local</strong> para habilitar las opciones de red.",
        obs_step_3_title: "Pegar la URL generada",
        obs_step_3_desc: "En el campo <strong>Entrada</strong>, pega la URL de SRT copiada arriba (ej: <code>srt://192.168.1.X:8890?streamid=read:cam_id...</code>).",
        obs_step_4_title: "Formato de entrada",
        obs_step_4_label: "En el campo <strong>Formato de entrada</strong> escribe o copia:",
        obs_step_5_title: "Búfer de Red y Baja Latencia (<100ms)",
        obs_step_5_desc: "En la configuración de la Fuente multimedia en OBS, reduce <strong>Búfer de red (Network Buffering)</strong> a <strong>1 MB</strong> o 0 para erradicar retrasos de 500-1000ms. Alternativamente, utiliza <strong>Fuente de video VLC</strong> con <code>:network-caching=50</code>.",
        btn_copy_chip: "📋 Copiar",
        btn_copy_url: "Copiar",
        btn_share_qr: "Compartir QR",

        // Vista de Cámaras
        cameras_title: "Dispositivos y Flujos",
        cameras_desc: "Control individual, autoarranque y optimización de hardware para cada cámara detectada.",
        btn_scan_hardware: "Escanear Hardware",
        cam_autostart_checkbox: "Autoarranque al encender PC",
        cam_uptime_label: "Uptime:",
        cam_live_label: "En vivo:",
        btn_start: "Iniciar",
        btn_stop: "Detener",
        btn_preview: "Vista Previa",
        btn_share: "Compartir QR",
        btn_restart: "Reiniciar",
        btn_settings: "Ajustes",
        btn_logs: "Logs",
        cam_status_running: "EN TRANSMISIÓN",
        cam_status_stopped: "DETENIDO",
        cam_status_starting: "INICIANDO",
        cam_status_error: "ERROR",
        cam_status_recovering: "RECUPERANDO",
        cam_status_permanent_fail: "Fallo Permanente",
        cam_status_retrying: "Reintentando...",
        cam_port_label: "Puerto:",
        cam_protocol_label: "Protocolo:",
        cam_profile_label: "Perfil:",
        cam_encoder_label: "Codificador:",
        cam_resolution_label: "Resolución:",
        cam_bitrate_label: "Bitrate:",
        empty_cameras_title: "No se han detectado cámaras DirectShow",
        empty_cameras_desc: "Conecta tus cámaras web USB o tarjetas capturadoras HDMI/SDI y actualiza la lista de dispositivos multimedia del sistema.",
        btn_scan_devices_now: "Escanear Dispositivos Ahora",
        btn_restore_deleted: "Restaurar Todas",

        // Secciones colapsables y badges
        virtual_devices_header: "Dispositivos Ocultos / Virtuales",
        ignored_devices_header: "Cámaras Ocultadas / Eliminadas",
        click_to_toggle: "Haz clic para mostrar u ocultar",
        click_to_restore: "Clic para ver y restaurar",
        badge_connected_usb: "Conectada (USB)",
        badge_disconnected: "Desconectada",
        ignored_camera_status: "Estado: Cámara oculta o eliminada. No transmitirá hasta que sea restaurada.",
        btn_restore_camera: "Restaurar Cámara",

        // Protocolos y etiquetas dinámicas
        proto_srt_label: "SRT Media Server (Reconexión Instantánea)",
        proto_udp_unicast: "UDP Unicast (Localhost / Misma PC)",
        proto_udp_multicast: "UDP Multicast (Red LAN)",
        proto_srt_name: "SRT Media Server",
        proto_udp_unicast_short: "UDP Unicast (Localhost)",
        proto_udp_multicast_short: "UDP Multicast (LAN)",
        status_transmitting: "Transmitiendo",
        tag_cpu_fallback: "(Modo CPU Fallback)",
        alert_retry_limit: "⚠️ Superado límite de reintentos. Verifique si el dispositivo está en uso o desconectado.",
        alert_device_disconnected: "🔌 Dispositivo desconectado físicamente. En espera de reconexión.",
        cam_srt_port_label: "Puerto SRT:",
        cam_central_server_label: "(Servidor Central)",
        cam_udp_port_label: "Puerto UDP:",
        label_unicast_local: "Unicast Local",
        label_multicast_lan: "Multicast LAN",
        passphrase_toggle_show: "Mostrar contraseña",
        passphrase_toggle_hide: "Ocultar contraseña",

        // Gestión de Energía
        power_title: "Gestión Profesional de Energía (Broadcast)",
        power_desc: "Optimiza la estabilidad de transmisión previniendo suspensión de puertos USB, ahorro en tarjetas de red y reposo de Windows.",
        power_header: "Estado de Optimización Energética",
        power_alert: "<strong>Estabilidad para Vivo:</strong> Estas optimizaciones evitan que Windows suspenda puertos USB de las cámaras o apague adaptadores de red. Se aplican de forma 100% silenciosa sin consolas visibles.",
        power_status_ready: "Listo",
        power_card_scheme_title: "Conmutación a Alto Rendimiento",
        power_card_scheme_desc: "Activa automáticamente el esquema de Alto Rendimiento durante transmisiones y restaura el original al finalizar.",
        power_card_awake_title: "Prevenir Suspensión del Sistema",
        power_card_awake_desc: "Mantiene el procesador y la pantalla activos en tiempo real durante la producción (SetThreadExecutionState).",
        power_card_hibernation_title: "Hibernación",
        power_card_hibernation_desc: "Desactiva el archivo de hibernación para evitar bloqueos.",
        power_card_usb_title: "Desactivar Suspensión Selectiva USB",
        power_card_usb_desc: "Evita que Windows apague los concentradores USB de tus webcams por supuesta inactividad.",
        power_card_hdd_title: "Apagado de HDD / Discos",
        power_card_hdd_desc: "Evita desactivación de unidades de almacenamiento.",
        power_card_nic_title: "Desactivar Ahorro en Red (NICs)",
        power_card_nic_desc: "Mantiene los adaptadores Ethernet y Wi-Fi en máxima respuesta para evitar pérdida de paquetes SRT/UDP.",
        btn_apply_power: "Aplicar Optimizaciones",
        btn_restore_power: "Restaurar Configuración Original",

        // Sistema y Arranque
        system_title: "Ajustes Generales del Sistema",
        system_desc: "Control de persistencia, puertos del servidor MediaMTX embebido y mantenimiento de base de datos.",
        sys_autostart_card_header: "Autoarranque con Windows (Modo Desatendido)",
        sys_autostart_alert: "Inicia RTMS silenciosamente al encender el equipo sin consolas negras abiertas. Las cámaras con la opción de <strong>Autoarranque</strong> activa comenzarán a transmitir automáticamente.",
        sys_autostart_title: "Iniciar RTMS al arrancar Windows",
        sys_autostart_desc: "Permite tolerancia a reinicios accidentales o cortes de energía.",
        sys_mediamtx_card_header: "Media Server Interno (MediaMTX) y Puerto Central SRT",
        sys_mediamtx_alert: "MediaMTX centraliza la ingesta de todas las cámaras. Clientes externos como OBS Studio y vMix se conectan a este puerto central SRT único (por defecto <strong>8890</strong>) indicando la cámara mediante <code>streamid=read:{cam_id}</code>. Las desconexiones o reinicios de clientes no interrumpen la ingesta local de FFmpeg.",
        sys_mediamtx_port_label: "Puerto SRT de MediaMTX (Listener LAN):",
        btn_save_port: "Guardar Puerto MediaMTX",
        sys_server_info_header: "Información del Servidor y Entorno",
        sys_table_version: "Versión RTMS",
        sys_table_version_val: "v2.8.1 (Compilación Oficial)",
        sys_table_os: "Sistema Operativo",
        sys_table_build: "Compilación Windows",
        sys_table_release: "Versión de Lanzamiento",
        sys_table_ip: "IP del Servidor",
        sys_table_author: "Desarrollador",
        sys_backup_title: "Copia de Seguridad y Migración",
        sys_backup_desc: "Exporta la configuración completa del sistema para respaldo o impórtala desde un archivo JSON validado.",
        btn_export_json: "Exportar Configuración (JSON)",
        btn_import_json: "Importar Configuración",
        sys_zone_maint_header: "Zona de Mantenimiento y Control de Procesos",
        sys_zone_maint_desc: "Herramientas de emergencia y saneamiento del entorno. Finaliza de raíz cualquier proceso remanente en memoria o restaura el software a su estado virgen de fábrica.",
        btn_kill_all_procs: "Finalizar Todos los Procesos",
        btn_factory_reset: "Restablecer a Valores de Fábrica",

        // Modal Configuración de Cámara
        config_modal_title: "Configuración de Cámara",
        cfg_preset_label: "Perfil Predefinido de Transmisión",
        cfg_fps_label: "FPS (Fotogramas por Segundo)",
        cfg_bitrate_label: "Tasa de Bits / Bitrate (kbps)",
        cfg_udp_host_label: "IP de Destino Unicast (PC o Dispositivo Remoto)",
        cfg_udp_host_placeholder: "Ej: 192.168.1.100 o 127.0.0.1",
        cfg_udp_host_desc: "Ingrese la dirección IP del dispositivo receptor en su red local (o 127.0.0.1 si es en este mismo equipo).",
        cfg_auto_opts: "Opciones de Automatización y Rendimiento",
        cfg_cam_autostart: "Iniciar transmisión automáticamente al arrancar RTMS",
        cfg_zerolatency: "Modo de baja latencia zerolatency (<100ms real sin buffers)",
        cfg_is_virtual: "Clasificar como cámara virtual o secundaria (ocultar del panel principal)",
        cfg_srt_adv: "Ajustes Avanzados de Transmisión (SRT)",
        cfg_srt_latency: "Latencia de Buffer SRT (ms)",
        cfg_srt_pass: "Frase de Paso / Passphrase SRT (Opcional)",
        cfg_srt_pass_placeholder: "Entre 10 y 79 caracteres",
        btn_reset_cam_defaults: "Restablecer por Defecto",
        btn_reset_cam_defaults_tooltip: "Restablecer configuración a valores predeterminados (720p, 30 FPS, 3000 kbps, SRT)",
        msg_cam_defaults_restored: "Valores predeterminados cargados en el formulario. Haz clic en 'Guardar y Aplicar' para persistir.",
        btn_save_apply: "Guardar y Aplicar",

        // Opciones de Preset
        opt_preset_custom: "Personalizado...",
        opt_preset_best: "Alta Calidad / Broadcast (1080p @ 60 FPS — 6000 kbps)",
        opt_preset_default: "Estándar Equilibrado (720p @ 30 FPS — 3000 kbps)",
        opt_preset_lowest: "Bajo Ancho de Banda (480p @ 24 FPS — 1500 kbps)",

        // Opciones de Protocolo
        opt_protocol_srt: "SRT Media Server (Desacoplado, baja latencia — Recomendado)",
        opt_protocol_udp_multicast: "UDP Multicast (Emisión a múltiples receptores en red LAN)",
        opt_protocol_udp_unicast: "UDP Unicast LAN (Hacia otra PC o Celular — VLC sin caídas)",

        // Opciones y Grupos de Codificador
        opt_enc_auto: "Detección Automática de GPU (Conmutación suave a CPU)",
        optgrp_h264: "H.264 / AVC (Máxima compatibilidad)",
        opt_enc_h264_nvenc: "NVIDIA NVENC H.264 (Acelerado por GPU)",
        opt_enc_h264_qsv: "Intel QuickSync QSV H.264 (Acelerado por GPU)",
        opt_enc_h264_amf: "AMD AMF H.264 (Acelerado por GPU)",
        opt_enc_libx264: "libx264 (CPU — Universal)",
        optgrp_hevc: "H.265 / HEVC (Alta Eficiencia)",
        opt_enc_hevc_nvenc: "NVIDIA NVENC HEVC (H.265 GPU)",
        opt_enc_hevc_qsv: "Intel QuickSync QSV HEVC (H.265 GPU)",
        opt_enc_hevc_amf: "AMD AMF HEVC (H.265 GPU)",
        opt_enc_libx265: "libx265 (CPU — H.265)",
        optgrp_av1: "AV1 Next-Gen (Mínimo Ancho de Banda)",
        opt_enc_av1_nvenc: "NVIDIA NVENC AV1 (Acelerado por GPU)",
        opt_enc_av1_qsv: "Intel QuickSync QSV AV1 (Acelerado por GPU)",
        opt_enc_av1_amf: "AMD AMF AV1 (Acelerado por GPU)",

        // Modal Acerca de
        about_title: "Acerca de RTMS",
        about_subtitle: "Estación de Ingesta y Transmisión Multicámara de Baja Latencia",
        about_version_tag: "v2.8.1 • Producción y Streaming",
        arg_tribute_made: "Hecho en Argentina",
        arg_tribute_malvinas: "Las Malvinas son argentinas",
        official_website_btn: "Sitio Web Oficial",
        third_party_label: "Atribuciones y Componentes de Terceros:",
        btn_understood: "Entendido",

        // Modal de Bienvenida
        welcome_title: "Bienvenido a RTMS",
        welcome_sub: "Estación de Ingesta Multicámara de Baja Latencia para Windows",
        welcome_select_lang: "Selecciona tu idioma para continuar / Select your language to continue:",
        lang_btn_es: "Español",
        lang_btn_en: "English",

        // Modal de Telemetría Detallada
        telemetry_title: "Telemetría del Sistema y Silicio en Tiempo Real",
        telemetry_desc: "Métricas de rendimiento en vivo proporcionadas por NVML nativo, subprocesos FFmpeg y kernel de Windows.",
        telemetry_cpu: "CPU Total",
        telemetry_gpu_engine: "Motor GPU / NVENC:",
        telemetry_gpu_mem: "Memoria VRAM:",
        telemetry_ram: "Memoria RAM",
        telemetry_lan: "Tráfico Red LAN",
        telemetry_bitrate: "Bitrate RTMS",
        telemetry_primary_gpu: "Dispositivo Gráfico Primario",
        telemetry_driver: "Controlador: Estándar Windows DirectShow",
        btn_close: "Cerrar",

        // Modal Compartir / QR
        qr_title: "Compartir enlace QR",
        qr_desc: "Escanea con la cámara de tu teléfono para abrir la transmisión en VLC o reproducir en la red local.",
        qr_obs_label: "URL para OBS Studio / vMix:",
        qr_vlc_label: "URL limpia para VLC Mobile:",
        qr_vlc_launch: "Abrir en VLC (~50ms)",
        qr_vlc_download: "Playlist .xspf",
        qr_vlc_cmd_label: "Comando de terminal VLC de baja latencia:",
        qr_vlc_hint: "Copia y ejecuta el comando de terminal provisto arriba para reproducir en VLC con <code>:network-caching=50 :clock-jitter=0 :clock-synchro=0</code> de forma fluida y sin caídas de FPS.",

        // Modal Diagnóstico de Ping y Latencia
        nav_latency_ping: "Ping & Latencia",
        nav_ping_tooltip: "Diagnosticar Ping y Latencia de Video en esta PC",
        bench_card_title: "Diagnóstico de Ping y Latencia de Video",
        bench_card_desc: "Herramienta de auditoría para medir tiempos de tránsito de socket UDP, handshake local con MediaMTX, fluctuación (jitter) y compatibilidad de buffers de baja latencia con VLC Media Player.",
        btn_open_latency_bench: "Abrir Diagnóstico de Latencia",
        bench_modal_title: "Diagnóstico de Ping y Latencia de Video",
        bench_modal_desc: "Evalúa en tiempo real el tiempo de ida y vuelta (RTT) a nivel de socket en bucle local (127.0.0.1), el retardo de conexión con MediaMTX y la latencia de entrega de cuadros de video (TTFF).",
        btn_run_benchmark: "Ejecutar Diagnóstico",

        // Modal Vista Previa
        preview_modal_title: "Vista Previa de Video",
        preview_loading: "Iniciando monitor de video WebRTC...",
        btn_ffplay: "Abrir Visor Nativo FFplay",
        preview_hardware_note: "Consumo de hardware: 0.00% al cerrar este visor",
        preview_live_webrtc: "En Vivo WebRTC",
        preview_stopped_framing: "Encuadre DirectShow (Detenido)",
        preview_virtual_generator: "Generador Virtual",
        preview_unavailable: "(No disponible o límite alcanzado)",

        // Modal Logs
        logs_modal_title: "Logs de FFmpeg",
        logs_connecting: "Conectando al log de FFmpeg...",
        logs_empty: "No hay registros disponibles para este flujo en este momento.",
        logs_error: "Error al leer los logs del servidor.",

        // Modales de Confirmación y Emergencia
        confirm_title_default: "Confirmar Acción",
        btn_cancel: "Cancelar",
        btn_confirm_action: "Confirmar",
        btn_confirm_delete: "Eliminar Cámara",
        emergency_modal_title: "Confirmar Detención Global",
        emergency_modal_desc1: "¿Estás seguro de que deseas ejecutar la <strong>Detención Global</strong>?",
        emergency_modal_desc2: "Esto detendrá de forma ordenada todas las transmisiones activas y liberará los recursos de red y captura.",
        btn_stop_all_confirm: "Detener Todas las Transmisiones",
        terminate_modal_title: "Finalización Total de Procesos",
        terminate_modal_desc1: "¿Deseas <strong>cerrar RTMS y forzar la finalización de todos los procesos</strong>?",
        terminate_modal_desc2: "Esto cerrará el programa de inmediato y garantizará la eliminación de cualquier proceso hijo en ejecución (como FFmpeg o FFplay), liberando por completo los recursos de hardware y la memoria RAM.",
        btn_terminate_all_confirm: "Finalizar Todo Ahora",
        reset_modal_title: "Restablecer a Valores de Fábrica",
        reset_modal_desc1: "¿Confirmas que deseas <strong>limpiar todos los datos y restaurar la configuración original</strong>?",
        reset_modal_desc2: "Se eliminará permanentemente la configuración personalizada (<code>config.json</code>), respaldos automáticos, archivos de registro (<code>rtms.log</code>) y archivos temporales.",
        reset_modal_warn: "⚠️ El programa se cerrará automáticamente al finalizar la limpieza. La próxima vez que lo inicies, arrancará como si fuera su primera ejecución.",
        btn_factory_reset_confirm: "Borrar Datos y Salir",

        // Mensajes Toast y Notificaciones
        toast_copied_url: "URL copiada lista para OBS / vMix",
        toast_copied_clipboard: "Copiado al portapapeles",
        toast_copy_failed: "No se pudo copiar automáticamente",
        toast_device_lost: "Dispositivo desconectado",
        toast_device_recovered: "Dispositivo reconectado",
        toast_stream_started: "Transmisión iniciada",
        toast_stream_stopped: "Transmisión detenida",
        toast_cam_restored: "Cámara restaurada exitosamente",
        toast_all_restored: "Todas las cámaras han sido restauradas",
        toast_comm_error: "Error de comunicación con el servidor",
        toast_scan_done: "Escaneo de hardware completado",
        toast_scan_error: "Error al escanear hardware",
        toast_scanning: "⌛ Escaneando...",
        toast_scan_btn: "🔄 Escanear Hardware"
    },

    en: {
        // Header & Navigation
        nav_section_main: "MAIN",
        nav_connect: "Connect OBS/VLC",
        nav_section_mgmt: "MANAGEMENT",
        nav_cameras: "Cameras",
        nav_section_sys: "SYSTEM MANAGEMENT",
        nav_power: "Power Management",
        nav_system: "System & Startup",
        nav_website: "Website",
        btn_stop_all: "Stop All",
        btn_exit_app: "Exit / Terminate",
        btn_about: "About / Contact",
        developed_by_label: "DEVELOPED & DESIGNED BY",
        author_support: "Official Support",
        hud_cpu: "CPU",
        hud_gpu: "GPU",
        hud_ram: "RAM",
        hud_net: "NET",
        hud_bitrate: "BITRATE",
        hud_telemetry_tooltip: "Click to open detailed telemetry dashboard",
        hud_cpu_tooltip: "Current CPU utilization",
        hud_gpu_tooltip: "Current GPU utilization",
        hud_ram_tooltip: "Current RAM memory usage",
        hud_net_tooltip: "Current system network throughput",
        hud_bitrate_tooltip: "Total outgoing stream bitrate (RTMS streams)",
        nav_about_tooltip: "View software and author information",
        nav_website_tooltip: "RTMS Official Website",
        nav_emergency_tooltip: "Immediately stop all active streams",
        nav_kill_tooltip: "Force-terminate all RTMS and streaming processes",
        btn_copy_chip_tooltip: "Click to copy to clipboard",
        btn_factory_reset_tooltip: "Reset factory configuration and purge temporary files",
        preview_ffplay_tooltip: "Open in external floating window with low latency",
        arg_tribute_tooltip: "100% Argentine development with pride and sovereign identity",
        streams_active: "active",
        streams_total: "total",

        // Connect Page (OBS / VLC)
        connect_title: "Production Software Connection",
        connect_desc: "Connect your low-latency multicamera video feeds to OBS Studio, vMix, or VLC players across your LAN.",
        ip_title_label: "LOCAL NETWORK SERVER IP",
        copy_server_ip: "Copy IP",
        active_streams_header: "Active Broadcast Feeds",
        searching_active_streams: "Searching for active broadcast feeds...",
        active_streams_empty: "No active streams at this moment. Go to the <strong>Cameras</strong> section and click <strong>Start</strong> to begin streaming to OBS.",
        obs_guide_header: "Quick Setup Guide for OBS Studio",
        obs_guide_alert: "<strong>Recommended Protocol: SRT:</strong> SRT provides automated packet recovery and sub-100ms latency. Configure these sources on the <strong>computer running OBS</strong>.",
        obs_step_1_title: "Create Media Source in OBS",
        obs_step_1_desc: "Click <strong>+</strong> in the Sources panel, then choose <strong>Media Source</strong>.",
        obs_step_2_title: "Uncheck 'Local File'",
        obs_step_2_desc: "Uncheck the <strong>Local file</strong> checkbox to enable network stream options.",
        obs_step_3_title: "Paste Generated URL",
        obs_step_3_desc: "In the <strong>Input</strong> field, paste the copied SRT URL above (e.g. <code>srt://192.168.1.X:8890?streamid=read:cam_id...</code>).",
        obs_step_4_title: "Input Format",
        obs_step_4_label: "In the <strong>Input Format</strong> field, type or copy:",
        obs_step_5_title: "Network Buffering & Ultra-Low Latency (<100ms)",
        obs_step_5_desc: "In OBS Media Source, reduce <strong>Network Buffering</strong> to <strong>1 MB</strong> or 0 to eliminate 500-1000ms delays, or use a <strong>VLC Video Source</strong> with <code>:network-caching=50</code>.",
        btn_copy_chip: "📋 Copy",
        btn_copy_url: "Copy",
        btn_share_qr: "Share QR",

        // Cameras Page
        cameras_title: "Devices & Broadcast Feeds",
        cameras_desc: "Individual control, autostart, and hardware optimization for each detected camera.",
        btn_scan_hardware: "Scan Hardware",
        cam_autostart_checkbox: "Autostart on PC boot",
        cam_uptime_label: "Uptime:",
        cam_live_label: "Live:",
        btn_start: "Start",
        btn_stop: "Stop",
        btn_preview: "Live Preview",
        btn_share: "Share QR",
        btn_restart: "Restart",
        btn_settings: "Settings",
        btn_logs: "Logs",
        cam_status_running: "BROADCASTING",
        cam_status_stopped: "STOPPED",
        cam_status_starting: "STARTING",
        cam_status_error: "ERROR",
        cam_status_recovering: "RECOVERING",
        cam_status_permanent_fail: "Permanent Failure",
        cam_status_retrying: "Retrying...",
        cam_port_label: "Port:",
        cam_protocol_label: "Protocol:",
        cam_profile_label: "Profile:",
        cam_encoder_label: "Encoder:",
        cam_resolution_label: "Resolution:",
        cam_bitrate_label: "Bitrate:",
        empty_cameras_title: "No DirectShow cameras detected",
        empty_cameras_desc: "Connect your USB webcams or HDMI/SDI capture cards and scan system multimedia devices.",
        btn_scan_devices_now: "Scan Devices Now",
        btn_restore_deleted: "Restore All",

        // Collapsible sections and badges
        virtual_devices_header: "Hidden / Virtual Devices",
        ignored_devices_header: "Hidden / Deleted Cameras",
        click_to_toggle: "Click to show or hide",
        click_to_restore: "Click to view and restore",
        badge_connected_usb: "Connected (USB)",
        badge_disconnected: "Disconnected",
        ignored_camera_status: "Status: Camera hidden or deleted. Will not broadcast until restored.",
        btn_restore_camera: "Restore Camera",

        // Dynamic Protocols and Labels
        proto_srt_label: "SRT Media Server (Instant Reconnection)",
        proto_udp_unicast: "UDP Unicast (Localhost / Same PC)",
        proto_udp_multicast: "UDP Multicast (LAN Network)",
        proto_srt_name: "SRT Media Server",
        proto_udp_unicast_short: "UDP Unicast (Localhost)",
        proto_udp_multicast_short: "UDP Multicast (LAN)",
        status_transmitting: "Broadcasting",
        tag_cpu_fallback: "(CPU Fallback Mode)",
        alert_retry_limit: "⚠️ Retry limit exceeded. Check if the device is busy or disconnected.",
        alert_device_disconnected: "🔌 Device physically disconnected. Waiting for reconnection.",
        cam_srt_port_label: "SRT Port:",
        cam_central_server_label: "(Central Server)",
        cam_udp_port_label: "UDP Port:",
        label_unicast_local: "Local Unicast",
        label_multicast_lan: "LAN Multicast",
        passphrase_toggle_show: "Show passphrase",
        passphrase_toggle_hide: "Hide passphrase",

        // Power Management
        power_title: "Broadcast Power Management",
        power_desc: "Optimizes live broadcast stability by preventing USB camera suspension, NIC energy saving, and Windows sleep mode.",
        power_header: "Energy Optimization Status",
        power_alert: "<strong>Broadcast Stability:</strong> These optimizations prevent Windows from suspending camera USB ports or sleeping network adapters. Applied 100% silently with zero visible consoles.",
        power_status_ready: "Active",
        power_card_scheme_title: "Auto High Performance Switching",
        power_card_scheme_desc: "Automatically engages Windows High Performance power scheme while streaming and restores user defaults on stop.",
        power_card_awake_title: "Prevent System Sleep",
        power_card_awake_desc: "Keeps CPU and displays active in real-time during live productions (SetThreadExecutionState).",
        power_card_hibernation_title: "Hibernation",
        power_card_hibernation_desc: "Disables the hibernation file to eliminate disk write freezes.",
        power_card_usb_title: "Disable USB Selective Suspend",
        power_card_usb_desc: "Prevents Windows from idling or suspending USB camera hubs during quiet scenes.",
        power_card_hdd_title: "HDD / Disk Spin-Down",
        power_card_hdd_desc: "Prevents mechanical and external storage drives from spinning down.",
        power_card_nic_title: "Disable Network Card Power Saving",
        power_card_nic_desc: "Keeps Ethernet and Wi-Fi adapters in ultra-responsive states to prevent SRT/UDP packet drops.",
        btn_apply_power: "Apply Recommended Optimizations",
        btn_restore_power: "Restore Windows Defaults",

        // System & Startup
        system_title: "System & Core Settings",
        system_desc: "Persistence controls, embedded MediaMTX server ports, and database management.",
        sys_autostart_card_header: "Autostart with Windows (Unattended Mode)",
        sys_autostart_alert: "Starts RTMS silently on PC boot with no black console windows. Cameras configured with <strong>Autostart</strong> will automatically begin broadcasting.",
        sys_autostart_title: "Launch RTMS on Windows startup",
        sys_autostart_desc: "Provides fault tolerance against accidental reboots or power outages.",
        sys_mediamtx_card_header: "Internal Media Server (MediaMTX) & Central SRT Port",
        sys_mediamtx_alert: "MediaMTX centralizes multi-camera ingest. External clients like OBS Studio and vMix connect to this single central SRT port (default <strong>8890</strong>) specifying the camera via <code>streamid=read:{cam_id}</code>. Client disconnects or restarts never interrupt FFmpeg local capture.",
        sys_mediamtx_port_label: "MediaMTX SRT Port (LAN Listener):",
        btn_save_port: "Save MediaMTX Port",
        sys_server_info_header: "Server & Runtime Environment Information",
        sys_table_version: "RTMS Version",
        sys_table_version_val: "v2.8.1 (Official Build)",
        sys_table_os: "Operating System",
        sys_table_build: "Windows Build",
        sys_table_release: "Release Version",
        sys_table_ip: "Server IP",
        sys_table_author: "Developer",
        sys_backup_title: "Configuration Backup & Transfer",
        sys_backup_desc: "Export full system configuration for backup or import from a validated JSON file.",
        btn_export_json: "Export Configuration (JSON)",
        btn_import_json: "Import Configuration",
        sys_zone_maint_header: "Maintenance & Process Governance Zone",
        sys_zone_maint_desc: "Emergency management and environment cleanup. Force-terminate any orphan processes in memory or reset RTMS to factory state.",
        btn_kill_all_procs: "Terminate All Processes",
        btn_factory_reset: "Reset to Factory Defaults",

        // Camera Configuration Modal
        config_modal_title: "Camera Configuration",
        cfg_preset_label: "Preset Broadcast Profile",
        cfg_fps_label: "FPS (Frames Per Second)",
        cfg_bitrate_label: "Bitrate (kbps)",
        cfg_udp_host_label: "Unicast Destination IP (PC or Remote Device)",
        cfg_udp_host_placeholder: "e.g., 192.168.1.100 or 127.0.0.1",
        cfg_udp_host_desc: "Enter the IP address of the receiving device on your local network (or 127.0.0.1 if on this PC).",
        cfg_auto_opts: "Automation & Performance Options",
        cfg_cam_autostart: "Start broadcast automatically on RTMS launch",
        cfg_zerolatency: "Low-latency zerolatency mode (<100ms real without buffers)",
        cfg_is_virtual: "Classify as virtual or secondary camera (hide from main dashboard)",
        cfg_srt_adv: "Advanced Broadcast Settings (SRT)",
        cfg_srt_latency: "SRT Buffer Latency (ms)",
        cfg_srt_pass: "SRT Passphrase (Optional)",
        cfg_srt_pass_placeholder: "Between 10 and 79 characters",
        btn_reset_cam_defaults: "Reset to Defaults",
        btn_reset_cam_defaults_tooltip: "Reset settings to default values (720p, 30 FPS, 3000 kbps, SRT)",
        msg_cam_defaults_restored: "Default values loaded into form. Click 'Save & Apply' to persist.",
        btn_save_apply: "Save & Apply",

        // Preset options
        opt_preset_custom: "Custom...",
        opt_preset_best: "High Quality / Broadcast (1080p @ 60 FPS — 6000 kbps)",
        opt_preset_default: "Balanced Standard (720p @ 30 FPS — 3000 kbps)",
        opt_preset_lowest: "Low Bandwidth (480p @ 24 FPS — 1500 kbps)",

        // Protocol options
        opt_protocol_srt: "SRT Media Server (Decoupled, low latency — Recommended)",
        opt_protocol_udp_multicast: "UDP Multicast (Broadcast to multiple receivers on LAN)",
        opt_protocol_udp_unicast: "UDP Unicast LAN (To another PC or Mobile — VLC drop-free)",

        // Encoder options and groups
        opt_enc_auto: "Automatic GPU Detection (Smooth fallback to CPU)",
        optgrp_h264: "H.264 / AVC (Maximum Compatibility)",
        opt_enc_h264_nvenc: "NVIDIA NVENC H.264 (GPU Accelerated)",
        opt_enc_h264_qsv: "Intel QuickSync QSV H.264 (GPU Accelerated)",
        opt_enc_h264_amf: "AMD AMF H.264 (GPU Accelerated)",
        opt_enc_libx264: "libx264 (CPU — Universal)",
        optgrp_hevc: "H.265 / HEVC (High Efficiency)",
        opt_enc_hevc_nvenc: "NVIDIA NVENC HEVC (H.265 GPU)",
        opt_enc_hevc_qsv: "Intel QuickSync QSV HEVC (H.265 GPU)",
        opt_enc_hevc_amf: "AMD AMF HEVC (H.265 GPU)",
        opt_enc_libx265: "libx265 (CPU — H.265)",
        optgrp_av1: "AV1 Next-Gen (Minimum Bandwidth)",
        opt_enc_av1_nvenc: "NVIDIA NVENC AV1 (GPU Accelerated)",
        opt_enc_av1_qsv: "Intel QuickSync QSV AV1 (GPU Accelerated)",
        opt_enc_av1_amf: "AMD AMF AV1 (GPU Accelerated)",

        // About Modal
        about_title: "About RTMS",
        about_subtitle: "Real-Time Low-Latency Multicamera Ingestion & Streaming Station",
        about_version_tag: "v2.8.1 • Production & Streaming",
        arg_tribute_made: "Made in Argentina",
        arg_tribute_malvinas: "The Malvinas Islands are Argentine",
        official_website_btn: "Official Website",
        third_party_label: "Third-Party Attributions & Licenses:",
        btn_understood: "Understood",

        // Welcome Modal
        welcome_title: "Welcome to RTMS",
        welcome_sub: "Real-Time Low-Latency Multicamera Streaming Station for Windows",
        welcome_select_lang: "Select your language to continue / Selecciona tu idioma para continuar:",
        lang_btn_es: "Español",
        lang_btn_en: "English",

        // Telemetry Modal
        telemetry_title: "Real-Time System & Silicon Telemetry",
        telemetry_desc: "Live performance metrics directly read from NVML, FFmpeg sub-pipes, and the Windows kernel.",
        telemetry_cpu: "Total CPU",
        telemetry_gpu_engine: "GPU / NVENC Engine:",
        telemetry_gpu_mem: "GPU VRAM:",
        telemetry_ram: "System RAM",
        telemetry_lan: "LAN Network Traffic",
        telemetry_bitrate: "RTMS Stream Bitrate",
        telemetry_primary_gpu: "Primary GPU Device",
        telemetry_driver: "Driver: Windows DirectShow Standard",
        btn_close: "Close",

        // Share / QR Modal
        qr_title: "Share QR Link",
        qr_desc: "Scan with your phone's camera to open the stream in VLC or view across your local network.",
        qr_obs_label: "URL for OBS Studio / vMix:",
        qr_vlc_label: "Clean URL for VLC Mobile:",
        qr_vlc_launch: "Open in VLC (~50ms)",
        qr_vlc_download: ".xspf Playlist",
        qr_vlc_cmd_label: "Low-latency VLC terminal command:",
        qr_vlc_hint: "Copy and run the terminal command provided above to play in VLC with <code>:network-caching=50 :clock-jitter=0 :clock-synchro=0</code> smoothly without dropping FPS.",

        // Ping & Latency Diagnostics Modal
        nav_latency_ping: "Ping & Latency",
        nav_ping_tooltip: "Diagnose Ping and Video Latency on this PC",
        bench_card_title: "Ping & Video Latency Diagnostics",
        bench_card_desc: "Audit tool to benchmark UDP socket transit times, local MediaMTX handshake, inter-frame jitter, and low-latency buffer stability with VLC Media Player.",
        btn_open_latency_bench: "Open Latency Diagnostics",
        bench_modal_title: "Ping & Video Latency Diagnostics",
        bench_modal_desc: "Evaluates in real-time socket loopback RTT (127.0.0.1), MediaMTX handshake response, and video frame delivery latency (TTFF).",
        btn_run_benchmark: "Run Diagnostics",

        // Video Preview Modal
        preview_modal_title: "Video Preview",
        preview_loading: "Starting WebRTC video monitor...",
        btn_ffplay: "Open Native FFplay Viewer",
        preview_hardware_note: "Hardware consumption: 0.00% upon closing this viewer",
        preview_live_webrtc: "Live WebRTC",
        preview_stopped_framing: "DirectShow Framing (Stopped)",
        preview_virtual_generator: "Virtual Generator",
        preview_unavailable: "(Unavailable or limit reached)",

        // Logs Modal
        logs_modal_title: "FFmpeg Logs",
        logs_connecting: "Connecting to FFmpeg log stream...",
        logs_empty: "No logs available for this stream at this moment.",
        logs_error: "Error reading server logs.",

        // Modals Confirmation and Emergency
        confirm_title_default: "Confirm Action",
        btn_cancel: "Cancel",
        btn_confirm_action: "Confirm",
        btn_confirm_delete: "Delete Camera",
        emergency_modal_title: "Confirm Global Stop",
        emergency_modal_desc1: "Are you sure you want to execute <strong>Global Stop</strong>?",
        emergency_modal_desc2: "This will cleanly stop all active streams and release network and capture resources.",
        btn_stop_all_confirm: "Stop All Broadcasts",
        terminate_modal_title: "Terminate All Processes",
        terminate_modal_desc1: "Do you want to <strong>exit RTMS and force termination of all processes</strong>?",
        terminate_modal_desc2: "This will close the application immediately and terminate all child processes (like FFmpeg or FFplay), completely freeing hardware resources and system RAM.",
        btn_terminate_all_confirm: "Terminate Everything Now",
        reset_modal_title: "Reset to Factory Defaults",
        reset_modal_desc1: "Confirm that you want to <strong>wipe all data and restore original configuration</strong>?",
        reset_modal_desc2: "Custom settings (<code>config.json</code>), automated backups, log files (<code>rtms.log</code>), and temporary files will be permanently deleted.",
        reset_modal_warn: "⚠️ The program will exit automatically upon reset. The next time you launch it, it will start as a fresh install.",
        btn_factory_reset_confirm: "Wipe Data & Exit",

        // Toasts & Notifications
        toast_copied_url: "URL copied ready for OBS / vMix",
        toast_copied_clipboard: "Copied to clipboard",
        toast_copy_failed: "Could not copy automatically",
        toast_device_lost: "Device disconnected",
        toast_device_recovered: "Device reconnected",
        toast_stream_started: "Stream started",
        toast_stream_stopped: "Stream stopped",
        toast_cam_restored: "Camera successfully restored",
        toast_all_restored: "All cameras have been restored",
        toast_comm_error: "Server communication error",
        toast_scan_done: "Hardware scan completed",
        toast_scan_error: "Hardware scan error",
        toast_scanning: "⌛ Scanning...",
        toast_scan_btn: "🔄 Scan Hardware"
    }
};

let _currentLanguage = "es";

function getTranslation(key) {
    if (!key || typeof key !== "string") return "";
    const langDict = I18N_DICTIONARY[_currentLanguage] || I18N_DICTIONARY["es"];
    if (Object.prototype.hasOwnProperty.call(langDict, key)) {
        return langDict[key];
    }
    if (Object.prototype.hasOwnProperty.call(I18N_DICTIONARY["es"], key)) {
        return I18N_DICTIONARY["es"][key];
    }
    return key;
}

// Helper corto global
function t(key) {
    return getTranslation(key);
}

function setAppLanguage(lang, persist = true) {
    if (lang !== "es" && lang !== "en") lang = "es";
    _currentLanguage = lang;
    if (persist) {
        try {
            localStorage.setItem("rtms_language", lang);
        } catch (e) {
            console.warn("No se pudo guardar idioma en localStorage:", e);
        }
    }
    applyI18nToDOM();
    updateLanguageButtons();

    // Re-renderizar páginas dinámicas para sincronizar traducciones en vivo
    if (typeof renderConnectPage === "function") {
        renderConnectPage();
    }
    if (typeof renderCamerasPage === "function") {
        renderCamerasPage();
    } else if (typeof renderCameras === "function") {
        renderCameras();
    }

    // Disparar evento para componentes externos
    window.dispatchEvent(new CustomEvent("rtmsLanguageChanged", { detail: { lang } }));
}

/**
 * Asigna de forma segura el contenido traducido a un elemento del DOM.
 * Si el texto no contiene etiquetas HTML en línea, se asigna directamente mediante textContent.
 * Si contiene etiquetas permitidas (strong, code, em, b, i), se construyen nodos DOM
 * sin invocar ningún parser HTML ni sink (sin innerHTML ni llamadas a parsers externos),
 * erradicando cualquier riesgo de XSS (CodeQL js/xss-through-dom, CWE-079 / CWE-116).
 *
 * @param {HTMLElement} el - Elemento del DOM donde se inyectará el texto traducido.
 * @param {string} content - Cadena traducida.
 */
function setSafeTranslatedContent(el, content) {
    if (!el || content === null || content === undefined) return;
    const str = String(content);

    // Caso general y seguro: texto plano sin marcado HTML
    if (!/<(?:strong|code|em|b|i)\b/i.test(str)) {
        el.textContent = str;
        return;
    }

    // Limpiar contenido existente
    while (el.firstChild) {
        el.removeChild(el.firstChild);
    }

    // Construcción de nodos segura sin intermediación de parsers HTML ni elementos dinámicos
    const tagRegex = /<(strong|code|em|b|i)>([\s\S]*?)<\/\1>/gi;
    let lastIndex = 0;
    let match;

    while ((match = tagRegex.exec(str)) !== null) {
        // Texto plano previo a la etiqueta
        if (match.index > lastIndex) {
            el.appendChild(document.createTextNode(str.slice(lastIndex, match.index)));
        }
        const tagName = match[1].toLowerCase();
        const tagText = match[2];
        let safeEl = null;

        if (tagName === "strong") {
            safeEl = document.createElement("strong");
        } else if (tagName === "code") {
            safeEl = document.createElement("code");
        } else if (tagName === "em") {
            safeEl = document.createElement("em");
        } else if (tagName === "b") {
            safeEl = document.createElement("b");
        } else if (tagName === "i") {
            safeEl = document.createElement("i");
        }

        if (safeEl) {
            safeEl.textContent = tagText;
            el.appendChild(safeEl);
        } else {
            el.appendChild(document.createTextNode(match[0]));
        }
        lastIndex = tagRegex.lastIndex;
    }

    // Texto plano posterior a la última etiqueta
    if (lastIndex < str.length) {
        el.appendChild(document.createTextNode(str.slice(lastIndex)));
    }
}

function applyI18nToDOM() {
    const elements = document.querySelectorAll("[data-i18n]");
    elements.forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (!key || typeof key !== "string") return;
        const langDict = I18N_DICTIONARY[_currentLanguage] || I18N_DICTIONARY["es"];
        if (Object.prototype.hasOwnProperty.call(langDict, key)) {
            setSafeTranslatedContent(el, langDict[key]);
        } else if (Object.prototype.hasOwnProperty.call(I18N_DICTIONARY["es"], key)) {
            setSafeTranslatedContent(el, I18N_DICTIONARY["es"][key]);
        } else {
            el.textContent = key;
        }
    });

    const attrElements = document.querySelectorAll("[data-i18n-attr]");
    attrElements.forEach(el => {
        const config = el.getAttribute("data-i18n-attr");
        if (!config || typeof config !== "string") return;
        const pairs = config.split(",");
        pairs.forEach(pair => {
            const [attr, key] = pair.split(":").map(s => s.trim());
            if (attr && key) {
                const langDict = I18N_DICTIONARY[_currentLanguage] || I18N_DICTIONARY["es"];
                let translation = "";
                if (Object.prototype.hasOwnProperty.call(langDict, key)) {
                    translation = langDict[key];
                } else if (Object.prototype.hasOwnProperty.call(I18N_DICTIONARY["es"], key)) {
                    translation = I18N_DICTIONARY["es"][key];
                }
                if (translation) {
                    el.setAttribute(attr, translation);
                }
            }
        });
    });

    // Actualizar atributo html lang
    document.documentElement.lang = _currentLanguage;
}

function updateLanguageButtons() {
    const btnEs = document.getElementById("lang-btn-es");
    const btnEn = document.getElementById("lang-btn-en");
    if (btnEs) btnEs.classList.toggle("active", _currentLanguage === "es");
    if (btnEn) btnEn.classList.toggle("active", _currentLanguage === "en");
}

function initI18n() {
    let savedLang = null;
    try {
        savedLang = localStorage.getItem("rtms_language");
    } catch (e) {}

    if (savedLang === "es" || savedLang === "en") {
        setAppLanguage(savedLang, false);
    } else {
        // Primer arranque: Mostrar modal de bienvenida
        setAppLanguage("es", false);
        const welcomeModal = document.getElementById("welcome-modal");
        if (welcomeModal) {
            welcomeModal.classList.add("active");
        }
    }
}

function selectInitialLanguage(lang) {
    setAppLanguage(lang, true);
    const welcomeModal = document.getElementById("welcome-modal");
    if (welcomeModal) {
        welcomeModal.classList.remove("active");
    }
}
