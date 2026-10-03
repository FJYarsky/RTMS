/* ==============================================================================
   RTMS — Real-Time Multicam System
   Controlador del panel web e interfaz de usuario.
   Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
============================================================================== */

let _streams = [];
let _localIp = '127.0.0.1';
let _mediamtxSrtPort = 8890;
let _logsInterval = null;
let _currentLogDevicePath = null;
let _uptimeTicker = null;
let _metricsTicker = null;
let _virtualGridVisible = false;
let _ignoredGridVisible = false;
let _lastTelemetryData = null;
let _confirmResolver = null;

// ICONOS SVG PROFESIONALES DE ALTA DEFINICIÓN
const ICONS = {
    play: `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="margin-right:4px;"><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
    stop: `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="margin-right:4px;"><rect x="5" y="5" width="14" height="14" rx="2" ry="2"/></svg>`,
    eye: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    eyeOff: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
    share: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>`,
    restart: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`,
    settings: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
    logs: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
    trash: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`,
    refresh: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`
};

// DIÁLOGO ASÍNCRONO DE CONFIRMACIÓN (REEMPLAZO TOTAL DE confirm())
function showConfirmModal({ title, message, sub = '', confirmText = null, cancelText = null, isDanger = true }) {
    return new Promise(resolve => {
        _confirmResolver = resolve;
        const modal = document.getElementById('confirm-modal');
        const titleEl = document.getElementById('confirm-modal-title');
        const msgEl = document.getElementById('confirm-modal-message');
        const subEl = document.getElementById('confirm-modal-sub');
        const confirmBtn = document.getElementById('confirm-modal-btn-confirm');
        const cancelBtn = document.getElementById('confirm-modal-btn-cancel');

        const defTitle = (typeof getTranslation === 'function') ? getTranslation('confirm_title_default') : 'Confirmar Acción';
        const defConfirm = (typeof getTranslation === 'function') ? getTranslation('btn_confirm_action') : 'Confirmar';
        const defCancel = (typeof getTranslation === 'function') ? getTranslation('btn_cancel') : 'Cancelar';

        if (titleEl) titleEl.textContent = title || defTitle;
        if (msgEl) msgEl.textContent = message || '';
        if (subEl) subEl.textContent = sub || '';
        if (confirmBtn) {
            confirmBtn.textContent = confirmText || defConfirm;
            confirmBtn.className = isDanger ? 'btn btn-danger' : 'btn btn-primary';
        }
        if (cancelBtn) cancelBtn.textContent = cancelText || defCancel;
        if (modal) modal.classList.add('active');
    });
}

function resolveConfirmModal(result) {
    const modal = document.getElementById('confirm-modal');
    if (modal) modal.classList.remove('active');
    if (_confirmResolver) {
        _confirmResolver(result);
        _confirmResolver = null;
    }
}

// PANEL DETALLADO DE TELEMETRÍA EN TIEMPO REAL
function openTelemetryModal() {
    const modal = document.getElementById('telemetry-modal');
    if (modal) {
        modal.classList.add('active');
        if (_lastTelemetryData) {
            updateTelemetryModalUI(_lastTelemetryData);
        }
    }
}

function closeTelemetryModal() {
    const modal = document.getElementById('telemetry-modal');
    if (modal) modal.classList.remove('active');
}

function updateTelemetryModalUI(data) {
    if (!data) return;
    const sys = data.system || data;
    const cpuEl = document.getElementById('tel-cpu-val');
    const gpuEl = document.getElementById('tel-gpu-val');
    const vramEl = document.getElementById('tel-vram-val');
    const ramEl = document.getElementById('tel-ram-val');
    const netEl = document.getElementById('tel-net-val');
    const brEl = document.getElementById('tel-bitrate-val');
    const gpuModel = document.getElementById('tel-gpu-model');
    const gpuDriver = document.getElementById('tel-gpu-driver');

    if (cpuEl && sys.cpu_percent !== undefined) cpuEl.textContent = `${Math.round(sys.cpu_percent)}%`;
    if (ramEl && sys.memory_percent !== undefined) ramEl.textContent = `${Math.round(sys.memory_percent)}%`;
    if (gpuEl) {
        gpuEl.textContent = (sys.gpu_available && sys.gpu_percent !== null && sys.gpu_percent !== undefined) ? `${Math.round(sys.gpu_percent)}%` : 'N/A';
    }
    if (vramEl) {
        vramEl.textContent = (sys.gpu_memory_used_mb !== null && sys.gpu_memory_used_mb !== undefined && sys.gpu_memory_total_mb !== null && sys.gpu_memory_total_mb !== undefined)
            ? `${Math.round(sys.gpu_memory_used_mb)} / ${Math.round(sys.gpu_memory_total_mb)} MB`
            : '–';
    }
    if (netEl) {
        const total = sys.net_system_total_kbps || sys.net_total_kbps || 0;
        netEl.textContent = total >= 1000 ? `${(total / 1000).toFixed(1)} Mbps` : `${Math.round(total)} kbps`;
    }
    if (brEl && sys.total_bitrate_kbps !== undefined) {
        brEl.textContent = sys.total_bitrate_kbps >= 1000 ? `${(sys.total_bitrate_kbps / 1000).toFixed(1)} Mbps` : `${Math.round(sys.total_bitrate_kbps)} kbps`;
    }
    if (gpuModel) {
        gpuModel.textContent = sys.gpu_name || 'Sin GPU dedicada detectada';
    }
    if (gpuDriver) {
        gpuDriver.textContent = sys.gpu_driver ? `Controlador: ${sys.gpu_driver}` : 'Controlador: Estándar Windows DirectShow';
    }
}

// TOKEN DE SEGURIDAD CSRF LOCAL
function getApiToken() {
    return document.querySelector('meta[name="rtms-token"]')?.content || '';
}

// FETCH HELPER SEGURO CON TOKEN X-RTMS-Token Y COOKIES DE SESIÓN
async function apiFetch(url, options = {}) {
    options.headers = options.headers || {};
    options.credentials = options.credentials || 'same-origin';
    const token = getApiToken();
    if (token) {
        options.headers['X-RTMS-Token'] = token;
    }
    return fetch(url, options);
}

// ESCAPE SEGURO DE HTML CONTRA INYECCIÓN XSS
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// NAVEGACIÓN ENTRE PÁGINAS
function navigateToPage(pageId) {
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.dataset.page === pageId) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    document.querySelectorAll('.page').forEach(page => {
        if (page.id === `page-${pageId}`) {
            page.classList.add('active');
        } else {
            page.classList.remove('active');
        }
    });

    // Cerrar sidebar en mobile al navegar
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar && sidebar.classList.contains('mobile-open')) {
        sidebar.classList.remove('mobile-open');
        if (overlay) overlay.classList.remove('active');
    }
}

// TOGGLE DEL SIDEBAR EN MOBILE
function toggleMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;
    sidebar.classList.toggle('mobile-open');
    if (overlay) overlay.classList.toggle('active');
}

// SOPORTE DE TECLADO PARA NAV-LINKS (Enter/Space) Y ESCAPE PARA MODALES
document.addEventListener('keydown', function(e) {
    // Escape cierra modales abiertos
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
        // También cerrar sidebar mobile
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar && sidebar.classList.contains('mobile-open')) {
            sidebar.classList.remove('mobile-open');
            if (overlay) overlay.classList.remove('active');
        }
    }

    // Enter/Space en nav-links con role="button"
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('nav-link')) {
        e.preventDefault();
        e.target.click();
    }
});

// NOTIFICACIONES TOAST (Sanitizado seguro sin inyección de innerHTML)
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
    const spanWrapper = document.createElement('span');
    spanWrapper.textContent = `${icon} ${message}`;
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.textContent = '×';
    closeBtn.onclick = () => toast.remove();

    toast.appendChild(spanWrapper);
    toast.appendChild(closeBtn);
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// UTILIDADES DE PORTAPAPELES
async function copyText(text, label = "") {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            const el = document.createElement('textarea');
            el.value = text;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
        }
        showToast(label ? `Copiado al portapapeles: ${label}` : "Copiado al portapapeles", "success");
    } catch (e) {
        showToast("No se pudo copiar automáticamente", "error");
    }
}

function copyMpegts() {
    copyText("mpegts", "mpegts");
}

function copyServerIp() {
    copyText(_localIp);
}

async function copyUrlByIndex(index) {
    const stream = _streams[index];
    if (!stream) return;
    const urlInput = document.getElementById(`url-input-${index}`);
    
    // Si ya tenemos la URL completa descifrada cargada
    if (urlInput && urlInput.dataset.fullUrl) {
        copyText(urlInput.dataset.fullUrl);
        showToast(`URL copiada (${stream.protocol.toUpperCase()}) lista para OBS / vMix`);
        return;
    }
    if (urlInput && urlInput.value) {
        copyText(urlInput.value);
        showToast(`URL copiada (${stream.protocol.toUpperCase()}) lista para OBS / vMix`);
        return;
    }

    try {
        const res = await apiFetch(`/api/stream/${encodeURIComponent(stream.device_path)}/connect_url`);
        if (res.ok) {
            const data = await res.json();
            if (data.connect_url) {
                copyText(data.connect_url);
                showToast(`URL copiada (${stream.protocol.toUpperCase()}) lista para OBS / vMix / VLC`);
                if (urlInput) {
                    urlInput.value = data.connect_url;
                    urlInput.dataset.fullUrl = data.connect_url;
                    urlInput.dataset.vlcUrl = data.vlc_url;
                }
                return;
            }
        }
    } catch (e) {
        console.warn('Fallo obteniendo connect_url, usando fallback local:', e);
    }
    if (urlInput) {
        copyText(urlInput.value);
        showToast('URL de transmisión copiada al portapapeles');
    }
}

async function loadConnectUrlForStream(stream, globalIndex) {
    try {
        const res = await apiFetch(`/api/stream/${encodeURIComponent(stream.device_path)}/connect_url`);
        if (res.ok) {
            const data = await res.json();
            const connectUrl = data.receive_url || data.connect_url;
            if (connectUrl) {
                stream.connect_url = connectUrl;
                stream.vlc_url = data.vlc_url;
                const urlInput = document.getElementById(`url-input-${globalIndex}`);
                const btn = document.getElementById(`toggle-pass-btn-${globalIndex}`);
                if (urlInput) {
                    urlInput.dataset.fullUrl = connectUrl;
                    urlInput.dataset.vlcUrl = data.vlc_url || '';
                    if (connectUrl.includes('passphrase=')) {
                        urlInput.value = connectUrl.replace(/passphrase=[^&]+/, 'passphrase=••••••••');
                        urlInput.dataset.masked = 'true';
                        if (btn) {
                            btn.style.display = 'inline-flex';
                            btn.innerHTML = ICONS.eye;
                            btn.title = (typeof getTranslation === 'function') ? getTranslation('passphrase_toggle_show') : 'Mostrar contraseña';
                        }
                    } else {
                        urlInput.value = connectUrl;
                        urlInput.dataset.masked = 'false';
                        if (btn) btn.style.display = 'none';
                    }
                }
            }
        }
    } catch (e) {
        console.warn('Fallo cargando connect_url para stream:', e);
    }
}

function toggleUrlPassphrase(index) {
    const input = document.getElementById(`url-input-${index}`);
    const btn = document.getElementById(`toggle-pass-btn-${index}`);
    if (!input) return;
    const fullUrl = input.dataset.fullUrl || input.value;
    input.dataset.fullUrl = fullUrl;

    if (input.dataset.masked === 'true') {
        input.value = fullUrl;
        input.dataset.masked = 'false';
        if (btn) {
            btn.innerHTML = ICONS.eyeOff;
            btn.title = (typeof getTranslation === 'function') ? getTranslation('passphrase_toggle_hide') : 'Ocultar contraseña';
        }
    } else {
        input.value = fullUrl.replace(/passphrase=[^&]+/, 'passphrase=••••••••');
        input.dataset.masked = 'true';
        if (btn) {
            btn.innerHTML = ICONS.eye;
            btn.title = (typeof getTranslation === 'function') ? getTranslation('passphrase_toggle_show') : 'Mostrar contraseña';
        }
    }
}

// FORMATO DE TIEMPO TRANSCURRIDO (UPTIME)
function formatUptime(seconds) {
    if (seconds === null || seconds === undefined) return '–';
    const s = Math.floor(seconds);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// OBTENER ESTADO GENERAL
async function fetchStatus() {
    try {
        const res = await apiFetch('/api/status');
        if (!res.ok) throw new Error("HTTP error " + res.status);
        const data = await res.json();
        
        _localIp = data.local_ip;
        _streams = data.streams;
        if (data.mediamtx_srt_port) {
            _mediamtxSrtPort = data.mediamtx_srt_port;
        }
        
        const connectIpEl = document.getElementById('connect-server-ip');
        if (connectIpEl) connectIpEl.textContent = _localIp;
        const headerIpEl = document.getElementById('header-ip-addr');
        if (headerIpEl) headerIpEl.textContent = _localIp;
        const sysIpEl = document.getElementById('sys-ip');
        if (sysIpEl) sysIpEl.textContent = _localIp;
        
        const autostartSwitch = document.getElementById('autostart-toggle-switch');
        if (autostartSwitch) {
            autostartSwitch.checked = data.autostart_enabled;
        }

        if (data.platform_info) {
            const platformEl = document.getElementById('sys-platform');
            if (platformEl && data.platform_info.summary) {
                platformEl.textContent = data.platform_info.summary;
            }
            const buildEl = document.getElementById('sys-win-build');
            if (buildEl && data.platform_info.build_number) {
                const ubr = data.platform_info.ubr ? `.${data.platform_info.ubr}` : '';
                const arch = data.platform_info.architecture ? ` (${data.platform_info.architecture})` : '';
                buildEl.textContent = `${data.platform_info.build_number}${ubr}${arch}`;
            }
            const verEl = document.getElementById('sys-win-ver');
            if (verEl && data.platform_info.display_version) {
                verEl.textContent = data.platform_info.display_version;
            }
        }

        const total = _streams.length;
        const active = _streams.filter(s => s.status.state === 'running').length;
        document.getElementById('active-streams-num').textContent = active;
        document.getElementById('total-streams-num').textContent = total;
        document.getElementById('sidebar-camera-badge').textContent = total;
        
        if (total > 0) {
            document.getElementById('sidebar-camera-badge').classList.remove('zero');
        } else {
            document.getElementById('sidebar-camera-badge').classList.add('zero');
        }

        renderConnectPage();
        renderCamerasPage();
    } catch (err) {
        console.error("Error al obtener el estado:", err);
    }
}

// HUD DE TELEMETRÍA EN TIEMPO REAL Y PROCESAMIENTO REACTIVO
function applyTelemetryData(data) {
    if (!data) return;
    _lastTelemetryData = data;
    const telModal = document.getElementById('telemetry-modal');
    if (telModal && telModal.classList.contains('active')) {
        updateTelemetryModalUI(data);
    }
    const sys = data.system || data;

    // CPU
    const cpuEl = document.getElementById('hud-cpu-val');
    if (cpuEl && sys.cpu_percent !== undefined) cpuEl.textContent = `${Math.round(sys.cpu_percent)}%`;

    // GPU
    const gpuEl = document.getElementById('hud-gpu-val');
    const gpuItem = document.getElementById('hud-gpu-item');
    if (gpuEl) {
        if (sys.gpu_available && sys.gpu_percent !== null && sys.gpu_percent !== undefined) {
            gpuEl.textContent = `${Math.round(sys.gpu_percent)}%`;
            if (gpuItem && sys.gpu_name) {
                const vram = (sys.gpu_memory_used_mb !== null && sys.gpu_memory_total_mb !== null)
                    ? ` (VRAM: ${Math.round(sys.gpu_memory_used_mb)} / ${Math.round(sys.gpu_memory_total_mb)} MB)`
                    : '';
                gpuItem.title = `${sys.gpu_name}${vram}`;
            }
        } else {
            gpuEl.textContent = 'N/A';
            if (gpuItem) gpuItem.title = 'Sin GPU dedicada detectada o métricas no disponibles';
        }
    }

    // RAM
    const ramEl = document.getElementById('hud-ram-val');
    if (ramEl && sys.memory_percent !== undefined) ramEl.textContent = `${Math.round(sys.memory_percent)}%`;

    // RED
    const netEl = document.getElementById('hud-net-val');
    const netItem = document.getElementById('hud-net-item');
    if (netEl) {
        const total = sys.net_system_total_kbps || sys.net_total_kbps || 0;
        const sent = sys.net_system_sent_kbps || sys.net_sent_kbps || 0;
        const recv = sys.net_system_recv_kbps || sys.net_recv_kbps || 0;
        if (total >= 1000) {
            netEl.textContent = `${(total / 1000).toFixed(1)} Mbps`;
        } else {
            netEl.textContent = `${Math.round(total)} kbps`;
        }
        if (netItem) {
            const sStr = sent >= 1000 ? `${(sent / 1000).toFixed(1)} Mbps` : `${Math.round(sent)} kbps`;
            const rStr = recv >= 1000 ? `${(recv / 1000).toFixed(1)} Mbps` : `${Math.round(recv)} kbps`;
            netItem.title = `Red del Sistema: ↑ ${sStr} (Subida) / ↓ ${rStr} (Bajada)`;
        }
    }

    // BITRATE
    const brEl = document.getElementById('hud-bitrate-val');
    if (brEl && sys.total_bitrate_kbps !== undefined) {
        if (sys.total_bitrate_kbps > 1000) {
            brEl.textContent = `${(sys.total_bitrate_kbps / 1000).toFixed(1)} Mbps`;
        } else {
            brEl.textContent = `${Math.round(sys.total_bitrate_kbps)} kbps`;
        }
    }

    // Actualización granular de métricas en tarjetas de cámara (10 Hz sin re-renderizar)
    if (Array.isArray(data.streams)) {
        data.streams.forEach(s => {
            const matchIndex = _streams.findIndex(item => item.device_path === s.device_path);
            if (matchIndex !== -1) {
                _streams[matchIndex].status.current_fps = s.fps;
                _streams[matchIndex].status.current_bitrate_kbps = s.bitrate_kbps;
                _streams[matchIndex].status.current_speed = s.speed;

                const liveFps = s.fps ? `${s.fps.toFixed(1)} FPS` : '–';
                const liveBitrate = s.bitrate_kbps ? `${Math.round(s.bitrate_kbps)} kbps` : '–';

                const fpsEl = document.getElementById(`live-fps-${matchIndex}`);
                if (fpsEl) fpsEl.textContent = liveFps;

                const bitrateEl = document.getElementById(`live-bitrate-${matchIndex}`);
                if (bitrateEl) bitrateEl.textContent = liveBitrate;
            }
        });
    }
}

async function fetchMetrics() {
    try {
        const res = await apiFetch('/api/system/metrics');
        if (!res.ok) return;
        const data = await res.json();
        applyTelemetryData(data);
    } catch (e) {
        // Silencioso
    }
}

// CANAL WEBSOCKET DE TELEMETRÍA REACTIVA A 10 HZ
let _telemetrySocket = null;
let _reconnectTimer = null;

function handleReactiveEvent(msg) {
    if (!msg || !msg.event) return;
    const evt = msg.event;
    const d = msg.data || {};

    if (evt === 'device_lost') {
        showToast(`Dispositivo desconectado: ${d.friendly_name || d.device_path}`, 'warning');
        fetchStatus();
    } else if (evt === 'device_recovered') {
        showToast(`Dispositivo reconectado: ${d.friendly_name || d.device_path}`, 'success');
        fetchStatus();
    } else if (evt === 'stream_started') {
        showToast(`Transmisión iniciada: ${d.friendly_name || d.device_path}`, 'success');
        fetchStatus();
    } else if (evt === 'stream_stopped') {
        fetchStatus();
    }
}

function initTelemetryWebSocket() {
    if (_telemetrySocket && (_telemetrySocket.readyState === WebSocket.OPEN || _telemetrySocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/telemetry`;

    try {
        _telemetrySocket = new WebSocket(wsUrl);

        _telemetrySocket.onopen = () => {
            console.log("[RTMS] Canal WebSocket de telemetría conectado a 10 Hz.");
            if (_metricsTicker) {
                clearInterval(_metricsTicker);
                _metricsTicker = null;
            }
        };

        _telemetrySocket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'telemetry') {
                    applyTelemetryData(msg);
                } else if (msg.type === 'event') {
                    handleReactiveEvent(msg);
                }
            } catch (e) {
                // Silencioso
            }
        };

        _telemetrySocket.onerror = (err) => {
            console.debug("[RTMS] Evento de error en WebSocket:", err);
        };

        _telemetrySocket.onclose = () => {
            console.debug("[RTMS] WebSocket cerrado. Reintentando en 3s...");
            if (!_metricsTicker) {
                _metricsTicker = setInterval(fetchMetrics, 2000);
            }
            if (_reconnectTimer) clearTimeout(_reconnectTimer);
            _reconnectTimer = setTimeout(initTelemetryWebSocket, 3000);
        };
    } catch (err) {
        console.warn("[RTMS] No se pudo inicializar WebSocket:", err);
        if (!_metricsTicker) {
            _metricsTicker = setInterval(fetchMetrics, 2000);
        }
    }
}

// RENDER: PÁGINA CONECTAR OBS/VLC
function renderConnectPage() {
    const container = document.getElementById('connect-streams-list');
    if (!container) return;
    container.innerHTML = '';
    
    const activeStreams = _streams.filter(s => s.status.state === 'running');
    
    if (activeStreams.length === 0) {
        container.innerHTML = `
            <div class="alert-box alert-warning" style="margin-bottom:0;">
                ${t('active_streams_empty')}
            </div>
        `;
        return;
    }
    
    activeStreams.forEach(stream => {
        const globalIndex = _streams.findIndex(s => s.device_path === stream.device_path);
        
        let clientUrl = '';
        let protocolLabel = '';
        const isUnicast = (stream.protocol === 'udp_unicast') || (stream.protocol === 'udp' && stream.udp_mode === 'unicast');
        const destIp = stream.udp_host || '127.0.0.1';
        const isLocalhost = (destIp === '127.0.0.1' || destIp === 'localhost');

        if (stream.protocol === 'srt') {
            protocolLabel = t('proto_srt_label');
            const srtPort = stream.mediamtx_port || _mediamtxSrtPort || 8890;
            const cleanCamId = stream.clean_cam_id || stream.id;
            clientUrl = `srt://${_localIp}:${srtPort}?streamid=read:${cleanCamId}`;
        } else if (isUnicast) {
            protocolLabel = t('proto_udp_unicast');
            clientUrl = isLocalhost ? `udp://127.0.0.1:${stream.port}` : `udp://${destIp}:${stream.port}`;
        } else {
            protocolLabel = t('proto_udp_multicast');
            const ipLastOctet = (stream.port % 200) + 1;
            clientUrl = `udp://@239.255.0.${ipLastOctet}:${stream.port}`;
        }

        const unicastInfoHtml = isUnicast
            ? `<div style="font-size: 0.72rem; color: var(--cyan); margin-top: 4px;">📡 Destino configurado: <strong>${escapeHtml(destIp)}:${stream.port}</strong> — Recibir en ${isLocalhost ? 'esta misma PC' : 'equipo receptor (' + escapeHtml(destIp) + ')'} usando <code>${clientUrl}</code></div>`
            : '';
        
        const row = document.createElement('div');
        row.style.marginBottom = '20px';
        row.style.paddingBottom = '16px';
        row.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
        row.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                <strong style="color: var(--teal); font-size: 0.95rem;">${escapeHtml(stream.friendly_name)}</strong>
                <span class="status-badge running"><span class="status-dot"></span>${t('status_transmitting')}</span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 6px;">
                ${t('cam_protocol_label')} <strong>${escapeHtml(protocolLabel)}</strong> | ${t('cam_resolution_label')} <strong>${escapeHtml(stream.resolution)} @ ${escapeHtml(stream.fps)} FPS</strong> | ${t('cam_bitrate_label')} <strong>${escapeHtml(stream.bitrate)} kbps</strong>
                ${unicastInfoHtml}
            </div>
            <div class="copy-input-grp">
                <input type="text" id="url-input-${globalIndex}" value="${escapeHtml(clientUrl)}" readonly>
                ${stream.protocol === 'srt' ? `<button class="btn btn-ghost btn-sm" id="toggle-pass-btn-${globalIndex}" title="${t('passphrase_toggle_show')}" onclick="toggleUrlPassphrase(${globalIndex})" style="padding: 4px 10px; margin-right: 4px; border: 1px solid var(--border-color); display: none; align-items: center;">${ICONS.eye}</button>` : ''}
                <button class="btn btn-ghost btn-sm" onclick="openQrModal(${globalIndex})" title="${t('btn_share_qr')}" style="padding: 4px 10px; margin-right: 4px; border: 1px solid var(--border-color); display: inline-flex; align-items: center;">${ICONS.share} <span>${t('btn_share_qr')}</span></button>
                <button class="copy-icon-btn" onclick="copyUrlByIndex(${globalIndex})">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                    <span>${t('btn_copy_url')}</span>
                </button>
            </div>
        `;
        container.appendChild(row);
        loadConnectUrlForStream(stream, globalIndex);
    });
}

// RENDER: PÁGINA CÁMARAS (CON SEPARACIÓN VIRTUAL/FÍSICA)
function renderCamerasPage() {
    const mainGrid = document.getElementById('cameras-grid-container');
    const virtualGrid = document.getElementById('virtual-cameras-grid');
    const virtualSection = document.getElementById('virtual-cameras-section');
    const virtualCountBadge = document.getElementById('virtual-count-badge');
    
    if (!mainGrid) return;
    mainGrid.innerHTML = '';
    if (virtualGrid) virtualGrid.innerHTML = '';
    
    if (_streams.length === 0) {
        mainGrid.innerHTML = `
            <div class="empty-state-card" style="grid-column: 1/-1; text-align: center; padding: 48px 24px; background: rgba(0, 0, 0, 0.2); border: 1px dashed var(--border-color); border-radius: var(--radius-lg); margin: 20px 0;">
                <div style="margin-bottom: 12px; display: inline-flex; justify-content: center; align-items: center; width: 64px; height: 64px; border-radius: 50%; background: rgba(20, 184, 166, 0.1); border: 1px solid var(--border-color); filter: drop-shadow(0 0 10px rgba(20, 184, 166, 0.3));">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                        <circle cx="12" cy="13" r="4"/>
                    </svg>
                </div>
                <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">
                    ${t('empty_cameras_title')}
                </h3>
                <p style="font-size: 0.85rem; color: var(--text-secondary); max-width: 480px; margin: 0 auto 20px auto; line-height: 1.5;">
                    ${t('empty_cameras_desc')}
                </p>
                <button class="btn btn-primary" onclick="scanHardwareDevices()">
                    ${ICONS.refresh} <span>${t('btn_scan_devices_now')}</span>
                </button>
            </div>
        `;
        if (virtualSection) virtualSection.style.display = 'none';
        return;
    }

    let virtualCount = 0;
    let liveCount = 0;
    let stoppedCount = 0;
    
    _streams.forEach((stream, index) => {
        const card = createCameraCardElement(stream, index);
        
        if (stream.status && stream.status.state === 'running') {
            liveCount++;
        } else {
            stoppedCount++;
        }

        if (stream.is_virtual) {
            virtualCount++;
            if (virtualGrid) virtualGrid.appendChild(card);
        } else {
            mainGrid.appendChild(card);
        }
    });

    // Actualizar badges de resumen superior
    const totalEl = document.getElementById('cam-summary-total');
    const liveEl = document.getElementById('cam-summary-live');
    const stoppedEl = document.getElementById('cam-summary-stopped');
    const virtualEl = document.getElementById('cam-summary-virtual');
    if (totalEl) totalEl.textContent = _streams.length;
    if (liveEl) liveEl.textContent = liveCount;
    if (stoppedEl) stoppedEl.textContent = stoppedCount;
    if (virtualEl) virtualEl.textContent = virtualCount;

    if (virtualSection) {
        if (virtualCount > 0) {
            virtualSection.style.display = 'block';
            if (virtualCountBadge) virtualCountBadge.textContent = virtualCount;
        } else {
            virtualSection.style.display = 'none';
        }
    }

    loadIgnoredDevices();
}

// CREADOR DE TARJETAS DE CÁMARA
function createCameraCardElement(stream, index) {
    const card = document.createElement('div');
    card.className = 'stream-card';
    
    const state = stream.status.state;
    let badgeClass = 'stopped';
    let badgeText = t('cam_status_stopped');
    
    if (state === 'running') { badgeClass = 'running'; badgeText = t('cam_status_running'); card.classList.add('is-running'); }
    else if (state === 'starting') { badgeClass = 'starting'; badgeText = t('cam_status_starting'); }
    else if (state === 'restarting') { badgeClass = 'restarting'; badgeText = t('cam_status_restarting'); }
    else if (state === 'error') { 
        badgeClass = 'failed'; 
        badgeText = stream.status.error_count >= 5 ? t('cam_status_permanent_fail') : t('cam_status_retrying'); 
    }
    
    const protocolName = stream.protocol === 'srt' 
        ? t('proto_srt_name')
        : (stream.udp_mode === 'unicast' ? t('proto_udp_unicast_short') : t('proto_udp_multicast_short'));
    
    let actionBtnHtml = '';
    if (state === 'running' || state === 'starting' || state === 'restarting') {
        actionBtnHtml = `<button class="btn btn-danger btn-sm" onclick="controlStream(${index}, 'stop')">${ICONS.stop} <span>${t('btn_stop')}</span></button>`;
    } else {
        actionBtnHtml = `<button class="btn btn-success btn-sm" onclick="controlStream(${index}, 'start')">${ICONS.play} <span>${t('btn_start')}</span></button>`;
    }
    
    const uptimeStr = formatUptime(stream.status.uptime_seconds);
    const liveFps = stream.status.current_fps ? `${stream.status.current_fps} FPS` : '–';
    const liveBitrate = stream.status.current_bitrate_kbps ? `${Math.round(stream.status.current_bitrate_kbps)} kbps` : '–';
    const fallbackTag = stream.status.using_fallback_cpu ? `<span style="color:var(--status-yellow); font-size:0.7rem; font-weight:700;">${t('tag_cpu_fallback')}</span>` : '';
    const autostartChecked = stream.auto_start ? 'checked' : '';

    const encText = (stream.actual_encoder && stream.actual_encoder !== 'desconocido' && stream.encoder === 'auto')
        ? `auto (${stream.actual_encoder})`
        : (stream.encoder || 'auto');

    let alertBanner = '';
    if (stream.permanent_failure) {
        alertBanner = `<div class="alert-box alert-danger" style="margin: 8px 0; padding: 6px 10px; font-size: 0.75rem; border-radius: 6px;">${t('alert_retry_limit')}</div>`;
    } else if (!stream.is_connected) {
        alertBanner = `<div class="alert-box alert-warning" style="margin: 8px 0; padding: 6px 10px; font-size: 0.75rem; border-radius: 6px;">${t('alert_device_disconnected')}</div>`;
    }

    const portDisplay = stream.protocol === 'srt'
        ? `${stream.mediamtx_port || _mediamtxSrtPort || 8890}`
        : `${stream.port} (${stream.udp_mode === 'unicast' ? 'Unicast' : 'Multicast'})`;

    const isUnicast = (stream.protocol === 'udp_unicast') || (stream.udp_mode === 'unicast');
    const streamIdLine = stream.protocol === 'srt'
        ? `<div class="stream-chip-sub"><span style="color:var(--text-muted);">Stream ID:</span> <code class="stream-code-id">read:${escapeHtml(stream.clean_cam_id || stream.id)}</code></div>`
        : (isUnicast
            ? `<div class="stream-chip-sub"><span style="color:var(--text-muted);">Destino:</span> <code class="stream-code-id">${escapeHtml(stream.udp_host || '127.0.0.1')}:${stream.port}</code></div>`
            : '');

    card.innerHTML = `
        <div class="stream-card-hdr">
            <div style="display: flex; align-items: center; gap: 10px; min-width: 0;">
                <div class="stream-camera-avatar">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                        <circle cx="12" cy="13" r="4"/>
                    </svg>
                </div>
                <div style="min-width: 0;">
                    <div class="stream-name" title="${escapeHtml(stream.friendly_name)}">${escapeHtml(stream.friendly_name)}</div>
                    ${fallbackTag}
                </div>
            </div>
            <span class="status-badge ${badgeClass}"><span class="status-dot"></span>${badgeText}</span>
        </div>
        
        ${alertBanner}

        <div class="stream-specs-dashboard">
            <div class="stream-spec-item">
                <span class="spec-label">${t('cam_protocol_label').replace(':', '')}</span>
                <span class="spec-val highlight">${escapeHtml(protocolName)} :${escapeHtml(portDisplay)}</span>
                ${streamIdLine}
            </div>
            <div class="stream-spec-item">
                <span class="spec-label">${t('cam_profile_label').replace(':', '')}</span>
                <span class="spec-val">${escapeHtml(stream.resolution)} @ ${escapeHtml(stream.fps)} FPS</span>
                <span class="stream-chip-sub">${escapeHtml(stream.bitrate)} kbps</span>
            </div>
            <div class="stream-spec-item" style="grid-column: 1 / -1;">
                <span class="spec-label">${t('cam_encoder_label').replace(':', '')}</span>
                <span class="spec-val font-mono" style="font-size: 0.78rem;">${escapeHtml(encText)}</span>
            </div>
        </div>

        <div class="stream-meta-row telemetry-hud-bar">
            <div class="telemetry-hud-box">
                <span class="hud-lbl">${t('cam_uptime_label')}</span>
                <strong class="hud-val" id="uptime-val-${index}">${uptimeStr}</strong>
            </div>
            <div class="telemetry-hud-box">
                <span class="hud-lbl">FPS</span>
                <strong class="hud-val ${stream.status.current_fps > 0 ? 'active' : ''}" id="live-fps-${index}">${liveFps}</strong>
            </div>
            <div class="telemetry-hud-box">
                <span class="hud-lbl">BITRATE</span>
                <strong class="hud-val ${stream.status.current_bitrate_kbps > 0 ? 'active' : ''}" id="live-bitrate-${index}">${liveBitrate}</strong>
            </div>
        </div>
        
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 2px 2px;">
            <label style="font-size: 0.76rem; display: inline-flex; align-items: center; gap: 8px; cursor: pointer; color: var(--text-secondary); user-select: none;">
                <input type="checkbox" ${autostartChecked} onchange="toggleCamAutostart(${index}, this.checked)" style="display:inline-block; accent-color: var(--teal); cursor: pointer;">
                <span>${t('cam_autostart_checkbox')}</span>
            </label>
        </div>

        <div class="actions-row" style="flex-wrap: wrap; gap: 6px;">
            ${actionBtnHtml}
            <button class="btn btn-primary btn-sm" onclick="openPreviewModal(${index})">${ICONS.eye} <span>${t('btn_preview')}</span></button>
            <button class="btn btn-ghost btn-sm" onclick="openQrModal(${index})" title="${t('btn_share')}">${ICONS.share} <span>${t('btn_share')}</span></button>
            <button class="btn btn-ghost btn-sm" onclick="controlStream(${index}, 'restart')">${ICONS.restart} <span>${t('btn_restart')}</span></button>
            <button class="btn btn-ghost btn-sm" onclick="configureStream(${index})">${ICONS.settings} <span>${t('btn_settings')}</span></button>
            <button class="btn btn-ghost btn-sm" onclick="viewLogs(${index})">${ICONS.logs} <span>${t('btn_logs')}</span></button>
        </div>
    `;
    
    return card;
}

// TOGGLE SECCIÓN DE CÁMARAS VIRTUALES
function toggleVirtualCamerasVisibility() {
    const grid = document.getElementById('virtual-cameras-grid');
    const chevron = document.getElementById('virtual-chevron');
    if (!grid) return;
    
    _virtualGridVisible = !_virtualGridVisible;
    if (_virtualGridVisible) {
        grid.classList.add('active');
        if (chevron) chevron.style.transform = 'rotate(90deg)';
    } else {
        grid.classList.remove('active');
        if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
}

// CARGAR Y RENDERIZAR CÁMARAS IGNORADAS / ELIMINADAS
async function loadIgnoredDevices() {
    const section = document.getElementById('ignored-cameras-section');
    const badge = document.getElementById('ignored-count-badge');
    const grid = document.getElementById('ignored-cameras-grid');
    if (!section || !grid) return;

    try {
        const res = await apiFetch('/api/devices/ignored');
        if (!res.ok) return;
        const data = await res.json();
        const devices = data.ignored_devices || [];

        if (devices.length === 0) {
            section.style.display = 'none';
            grid.innerHTML = '';
            if (badge) badge.textContent = '0';
            return;
        }

        section.style.display = 'block';
        if (badge) badge.textContent = String(devices.length);
        grid.innerHTML = '';

        devices.forEach(dev => {
            const card = document.createElement('div');
            card.className = 'stream-card';
            card.style.borderLeft = '3px solid #ef4444';
            card.style.background = 'rgba(239, 68, 68, 0.03)';

            const connBadge = dev.is_connected
                ? `<span class="status-badge running" style="font-size: 0.7rem;"><span class="status-dot"></span>${t('badge_connected_usb')}</span>`
                : `<span class="status-badge stopped" style="font-size: 0.7rem;"><span class="status-dot"></span>${t('badge_disconnected')}</span>`;

            card.innerHTML = `
                <div class="stream-card-hdr">
                    <div>
                        <div class="stream-name" style="color: #fca5a5;">${escapeHtml(dev.friendly_name)}</div>
                        <div style="font-size: 0.7rem; color: var(--text-muted); word-break: break-all; margin-top: 2px;">
                            ${escapeHtml(dev.device_path)}
                        </div>
                    </div>
                    ${connBadge}
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin: 10px 0;">
                    ${t('ignored_camera_status')}
                </div>
                <div class="actions-row">
                    <button class="btn btn-primary btn-sm" data-device-path="${escapeHtml(dev.device_path)}" onclick="unignoreCamera(this.dataset.devicePath)">
                        ${ICONS.restart} <span>${t('btn_restore_camera')}</span>
                    </button>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (err) {
        console.error("Error al cargar dispositivos ignorados:", err);
    }
}

// TOGGLE SECCIÓN DE CÁMARAS IGNORADAS
function toggleIgnoredCamerasVisibility() {
    const grid = document.getElementById('ignored-cameras-grid');
    const chevron = document.getElementById('ignored-chevron');
    if (!grid) return;

    _ignoredGridVisible = !_ignoredGridVisible;
    if (_ignoredGridVisible) {
        grid.classList.add('active');
        grid.style.display = 'grid';
        if (chevron) chevron.style.transform = 'rotate(90deg)';
    } else {
        grid.classList.remove('active');
        grid.style.display = 'none';
        if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
}

// RESTAURAR CÁMARA IGNORADA
async function unignoreCamera(devicePath) {
    try {
        const res = await apiFetch('/api/devices/unignore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_path: devicePath })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || "Cámara restaurada exitosamente", "success");
            await fetchStatus();
            await loadIgnoredDevices();
        } else {
            showToast(data.detail || "Error al restaurar cámara", "error");
        }
    } catch (err) {
        showToast("Error de comunicación con el servidor", "error");
    }
}

// RESTAURAR TODAS LAS CÁMARAS IGNORADAS
async function restoreAllIgnoredCameras() {
    const confirmed = await showConfirmModal({
        title: (typeof getTranslation === 'function') ? getTranslation('confirm_title_default') : 'Confirmar Acción',
        message: '¿Deseas restaurar todas las cámaras que fueron eliminadas u ocultadas?',
        sub: 'Volverán a aparecer en la lista de dispositivos configurados del sistema.',
        confirmText: (typeof getTranslation === 'function') ? getTranslation('btn_restore_deleted') : 'Restaurar Todas',
        cancelText: (typeof getTranslation === 'function') ? getTranslation('btn_cancel') : 'Cancelar',
        isDanger: false
    });
    if (!confirmed) {
        return;
    }
    try {
        const res = await apiFetch('/api/devices/unignore_all', {
            method: 'POST'
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || "Todas las cámaras han sido restauradas", "success");
            await fetchStatus();
            await loadIgnoredDevices();
        } else {
            showToast(data.detail || "Error al restaurar cámaras", "error");
        }
    } catch (err) {
        showToast("Error de comunicación con el servidor", "error");
    }
}

// MODAL PROMPT DESTINO UNICAST AL INICIAR POR PRIMERA VEZ
let _pendingUnicastIndex = null;

function openUnicastPrompt(index) {
    const stream = _streams[index];
    if (!stream) return;
    _pendingUnicastIndex = index;
    const ipInput = document.getElementById('unicast-prompt-ip-input');
    if (ipInput) {
        ipInput.value = stream.udp_host || '127.0.0.1';
    }
    const chipText = document.getElementById('prompt-chip-ip-text');
    if (chipText) {
        chipText.textContent = _localIp || '...';
    }
    const modal = document.getElementById('unicast-prompt-modal-overlay');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeUnicastPromptModal() {
    _pendingUnicastIndex = null;
    const modal = document.getElementById('unicast-prompt-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
    }
}

function setPromptIpValue(ip) {
    const ipInput = document.getElementById('unicast-prompt-ip-input');
    if (ipInput && ip) {
        ipInput.value = ip;
    }
}

async function confirmAndStartUnicast() {
    if (_pendingUnicastIndex === null) return;
    const index = _pendingUnicastIndex;
    const stream = _streams[index];
    if (!stream) return;

    const ipInput = document.getElementById('unicast-prompt-ip-input');
    const targetIp = (ipInput && ipInput.value.trim()) ? ipInput.value.trim() : '127.0.0.1';

    try {
        const payload = {
            device_path: stream.device_path,
            port: stream.port,
            resolution: stream.resolution,
            fps: stream.fps,
            bitrate: stream.bitrate,
            protocol: 'udp',
            udp_mode: 'unicast',
            encoder: stream.encoder,
            auto_start: stream.auto_start,
            zerolatency: stream.zerolatency,
            is_virtual: stream.is_virtual,
            srt_latency: stream.srt_latency || 120,
            srt_passphrase: stream.srt_passphrase || '',
            udp_host: targetIp
        };
        await apiFetch('/api/stream/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        localStorage.setItem('rtms_unicast_confirmed_' + (stream.device_path || index), 'true');
        stream.udp_host = targetIp;
        renderStreams();
    } catch (e) {
        console.warn('Could not persist unicast target IP:', e);
    }

    closeUnicastPromptModal();
    executeControlStream(index, 'start');
}

// ACCIONES DE CONTROL DE STREAM CON TOKEN
async function executeControlStream(index, action) {
    const stream = _streams[index];
    if (!stream) return;
    
    try {
        const res = await apiFetch('/api/stream/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_path: stream.device_path,
                action: action
            })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "success");
            fetchStatus();
        } else {
            showToast(data.detail || "Error en la acción", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Error de comunicación con el servidor", "error");
    }
}

async function controlStream(index, action) {
    const stream = _streams[index];
    if (!stream) return;

    const isUnicast = (stream.protocol === 'udp_unicast') || (stream.protocol === 'udp' && stream.udp_mode === 'unicast');
    const confirmedKey = 'rtms_unicast_confirmed_' + (stream.device_path || index);
    if (action === 'start' && isUnicast && !localStorage.getItem(confirmedKey)) {
        openUnicastPrompt(index);
        return;
    }
    await executeControlStream(index, action);
}

// TOGGLE AUTOSTART INDIVIDUAL DE CÁMARA CON TOKEN
async function toggleCamAutostart(index, enabled) {
    const stream = _streams[index];
    if (!stream) return;
    
    try {
        const res = await apiFetch('/api/stream/autostart_toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_path: stream.device_path,
                auto_start: enabled
            })
        });
        if (res.ok) {
            showToast(enabled ? "Autoarranque de cámara activado" : "Autoarranque de cámara desactivado", "info");
        }
    } catch (e) {
        showToast("Error al guardar autoarranque", "error");
    }
}

// SONDEO DE HARDWARE CON TOKEN
async function scanHardwareDevices() {
    const btn = document.getElementById('btn-scan-hw');
    btn.disabled = true;
    btn.textContent = t('toast_scanning');
    
    try {
        const res = await apiFetch('/api/hardware/scan', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(t('toast_scan_done'), "success");
            fetchStatus();
        } else {
            showToast(t('toast_scan_error'), "error");
        }
    } catch (err) {
        console.error(err);
        showToast(t('toast_scan_error'), "error");
    } finally {
        btn.disabled = false;
        btn.textContent = t('toast_scan_btn');
    }
}

// AUTOSTART DEL SISTEMA CON TOKEN
async function toggleAutostartState(enable) {
    try {
        const res = await apiFetch('/api/autostart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: enable })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(enable ? "Autoarranque en Windows activado" : "Autoarranque en Windows desactivado", "success");
        } else {
            showToast("No se pudo cambiar el autoarranque", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Error de conexión", "error");
    }
}

// DETENCIÓN GLOBAL DE TRANSMISIONES
function confirmEmergencyStop() {
    document.getElementById('emergency-modal-overlay').classList.add('active');
}

function closeEmergencyModal() {
    document.getElementById('emergency-modal-overlay').classList.remove('active');
}

async function executeEmergencyStop() {
    closeEmergencyModal();
    showToast("Ejecutando detención global de transmisiones...", "info");
    try {
        const res = await apiFetch('/api/system/emergency_stop', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "warning");
            fetchStatus();
        }
    } catch (e) {
        showToast("Error al enviar comando de detención", "error");
    }
}

// FINALIZACIÓN TOTAL DE PROCESOS
function confirmTerminateAllProcesses() {
    document.getElementById('terminate-modal-overlay').classList.add('active');
}

function closeTerminateModal() {
    document.getElementById('terminate-modal-overlay').classList.remove('active');
}

async function executeTerminateAllProcesses() {
    closeTerminateModal();
    showToast("Finalizando todos los procesos y liberando recursos...", "warning");
    try {
        await apiFetch('/api/system/shutdown', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });
        setTimeout(() => {
            window.close();
        }, 800);
    } catch (e) {
        window.close();
    }
}

// RESTABLECIMIENTO A VALORES DE FÁBRICA / LIMPIEZA DE DATOS
function confirmFactoryReset() {
    document.getElementById('reset-modal-overlay').classList.add('active');
}

function closeResetModal() {
    document.getElementById('reset-modal-overlay').classList.remove('active');
}

async function executeFactoryReset() {
    closeResetModal();
    showToast("Restableciendo valores de fábrica y limpiando temporales...", "warning");
    try {
        await apiFetch('/api/system/factory_reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirm: true })
        });
        setTimeout(() => {
            window.close();
        }, 1200);
    } catch (e) {
        window.close();
    }
}

// MODAL ACERCA DE
function openAboutModal() {
    document.getElementById('about-modal-overlay').classList.add('active');
}

function closeAboutModal() {
    document.getElementById('about-modal-overlay').classList.remove('active');
}

// CONFIGURACIÓN DE CÁMARA
function configureStream(index) {
    const stream = _streams[index];
    if (!stream) return;
    
    document.getElementById('config-modal-title').textContent = `${t('btn_settings')} — ${stream.friendly_name}`;
    document.getElementById('config-device-path').value = stream.device_path;
    document.getElementById('config-port').value = stream.port;
    document.getElementById('config-resolution').value = stream.resolution;
    document.getElementById('config-fps').value = stream.fps.toString();
    document.getElementById('config-bitrate').value = stream.bitrate;
    let protoVal = stream.protocol || 'srt';
    if (protoVal === 'udp') {
        protoVal = stream.udp_mode === 'unicast' ? 'udp_unicast' : 'udp_multicast';
    }
    document.getElementById('config-protocol').value = protoVal;
    document.getElementById('config-encoder').value = stream.encoder;
    document.getElementById('config-cam-autostart').checked = stream.auto_start;
    document.getElementById('config-zerolatency').checked = stream.zerolatency;
    document.getElementById('config-is-virtual').checked = stream.is_virtual;
    
    document.getElementById('config-srt-latency').value = stream.srt_latency || 120;
    // Mostrar enmascarada si ya existe
    document.getElementById('config-srt-passphrase').value = stream.srt_passphrase || '';

    const udpHostEl = document.getElementById('config-udp-host');
    if (udpHostEl) {
        udpHostEl.value = stream.udp_host || '127.0.0.1';
    }
    const chipText = document.getElementById('chip-local-ip-text');
    if (chipText) {
        chipText.textContent = _localIp || '...';
    }
    
    handleProtocolChange(protoVal);
    handleZerolatencyChange();
    document.getElementById('config-modal-overlay').classList.add('active');
}

function closeConfigModal() {
    document.getElementById('config-modal-overlay').classList.remove('active');
}

function setUdpHostValue(val) {
    const el = document.getElementById('config-udp-host');
    if (el && val) {
        el.value = val;
    }
}

function resetCameraConfigToDefaults() {
    // 1. Preset 'default' (720p @ 60 FPS, 3000 kbps)
    const presetEl = document.getElementById('config-preset');
    if (presetEl) {
        presetEl.value = 'default';
    }
    applyQualityPreset('default');

    // 2. Protocolo por defecto: UDP Unicast (Recomendado)
    const protoEl = document.getElementById('config-protocol');
    if (protoEl) {
        protoEl.value = 'udp_unicast';
        handleProtocolChange('udp_unicast');
    }

    // 3. Encoder 'auto'
    const encEl = document.getElementById('config-encoder');
    if (encEl) {
        encEl.value = 'auto';
    }

    // 4. Automatización y rendimiento por defecto
    const autoEl = document.getElementById('config-cam-autostart');
    if (autoEl) {
        autoEl.checked = true;
    }

    const zeroEl = document.getElementById('config-zerolatency');
    if (zeroEl) {
        zeroEl.checked = true;
        handleZerolatencyChange();
    }

    const virtEl = document.getElementById('config-is-virtual');
    if (virtEl) {
        virtEl.checked = false;
    }

    // 5. Ajustes avanzados SRT
    const latEl = document.getElementById('config-srt-latency');
    if (latEl) {
        latEl.value = 120;
    }

    const passEl = document.getElementById('config-srt-passphrase');
    if (passEl) {
        passEl.value = '';
    }

    const udpHostEl = document.getElementById('config-udp-host');
    if (udpHostEl) {
        udpHostEl.value = '127.0.0.1';
    }

    if (typeof showToast === 'function') {
        const msg = (typeof t === 'function' ? t('msg_cam_defaults_restored') : null) || 'Valores predeterminados cargados en el formulario.';
        showToast(msg, 'info');
    }
}

async function deleteCurrentCamera() {
    const dp = document.getElementById('config-device-path').value;
    if (!dp) return;
    const confirmed = await showConfirmModal({
        title: (typeof getTranslation === 'function') ? getTranslation('btn_confirm_delete') : 'Eliminar Cámara',
        message: '¿Estás seguro de que deseas eliminar permanentemente esta cámara de la configuración?',
        sub: 'Esta acción detendrá la transmisión si está activa y quitará el dispositivo de la lista principal.',
        confirmText: (typeof getTranslation === 'function') ? getTranslation('btn_confirm_delete') : 'Eliminar Permanentemente',
        cancelText: (typeof getTranslation === 'function') ? getTranslation('btn_cancel') : 'Cancelar',
        isDanger: true
    });
    if (!confirmed) {
        return;
    }
    try {
        const res = await apiFetch(`/api/stream/${encodeURIComponent(dp)}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (res.ok) {
            showToast("Cámara eliminada del panel. Puedes restaurarla en cualquier momento desde 'Cámaras Ocultadas / Eliminadas'.", 'success');
            closeConfigModal();
            fetchStatus();
            loadIgnoredDevices();
        } else {
            showToast(data.detail || 'Error al eliminar cámara', 'error');
        }
    } catch (e) {
        showToast('Error de comunicación con el servidor', 'error');
    }
}

function handleProtocolChange(protocol) {
    const advPanel = document.getElementById('config-advanced-panel');
    const advTrigger = document.querySelector('.advanced-trigger');
    const udpHostGroup = document.getElementById('group-udp-host');
    
    if (udpHostGroup) {
        udpHostGroup.style.display = (protocol === 'udp_unicast') ? 'block' : 'none';
    }
    
    if (protocol === 'srt') {
        if (advTrigger) advTrigger.style.display = 'flex';
    } else {
        if (advTrigger) advTrigger.style.display = 'none';
        if (advPanel) advPanel.classList.remove('active');
        const chev = document.getElementById('advanced-chevron');
        if (chev) chev.innerHTML = '&#9662;';
    }
}

function handleZerolatencyChange() {
    const zeroEl = document.getElementById('config-zerolatency');
    const latencyGroup = document.getElementById('group-srt-latency');
    const noticeEl = document.getElementById('notice-srt-latency-zerolatency');
    if (!zeroEl) return;
    const isZero = zeroEl.checked;
    if (latencyGroup) {
        latencyGroup.style.display = isZero ? 'none' : 'flex';
    }
    if (noticeEl) {
        noticeEl.style.display = isZero ? 'block' : 'none';
    }
}

function toggleAdvancedSettingsPanel() {
    const advPanel = document.getElementById('config-advanced-panel');
    const chevron = document.getElementById('advanced-chevron');
    const isActive = advPanel.classList.toggle('active');
    chevron.innerHTML = isActive ? '&#9652;' : '&#9662;';
}

function applyQualityPreset(preset) {
    if (preset === 'best') {
        document.getElementById('config-resolution').value = '1080p';
        document.getElementById('config-fps').value = '60';
        document.getElementById('config-bitrate').value = 6000;
    } else if (preset === 'default') {
        document.getElementById('config-resolution').value = '720p';
        document.getElementById('config-fps').value = '60';
        document.getElementById('config-bitrate').value = 3000;
    } else if (preset === 'lowest') {
        document.getElementById('config-resolution').value = '480p';
        document.getElementById('config-fps').value = '60';
        document.getElementById('config-bitrate').value = 1500;
    }
}

function resetQualityPreset() {
    document.getElementById('config-preset').value = 'custom';
}

async function submitCameraConfig(event) {
    event.preventDefault();
    
    const devicePath = document.getElementById('config-device-path').value;
    const resolution = document.getElementById('config-resolution').value;
    const fps = parseInt(document.getElementById('config-fps').value);
    const bitrate = parseInt(document.getElementById('config-bitrate').value);
    const protoVal = document.getElementById('config-protocol').value;
    const encoder = document.getElementById('config-encoder').value;
    const srtLatency = parseInt(document.getElementById('config-srt-latency').value);
    const srtPassphrase = document.getElementById('config-srt-passphrase').value.trim();
    const autoStart = document.getElementById('config-cam-autostart').checked;
    const zeroLatency = document.getElementById('config-zerolatency').checked;
    const isVirtual = document.getElementById('config-is-virtual').checked;

    let protocol = 'srt';
    let udpMode = 'multicast';
    if (protoVal === 'udp_unicast') {
        protocol = 'udp';
        udpMode = 'unicast';
    } else if (protoVal === 'udp_multicast' || protoVal === 'udp') {
        protocol = 'udp';
        udpMode = 'multicast';
    } else {
        protocol = 'srt';
    }
    
    if (protocol === 'srt' && srtPassphrase !== '' && srtPassphrase !== '••••••••') {
        if (srtPassphrase.length < 10 || srtPassphrase.length > 79) {
            showToast("La frase de paso SRT debe tener entre 10 y 79 caracteres.", "error");
            return;
        }
    }
    
    const udpHost = (document.getElementById('config-udp-host')?.value || "127.0.0.1").trim() || "127.0.0.1";
    let secretAction = "keep";
    if (srtPassphrase === "") {
        secretAction = "clear";
    } else if (srtPassphrase !== "••••••••") {
        secretAction = "set";
    }

    const payload = {
        device_path: devicePath,
        resolution: resolution,
        fps: fps,
        bitrate: bitrate,
        protocol: protocol,
        udp_mode: udpMode,
        udp_host: udpHost,
        encoder: encoder,
        srt_latency: srtLatency,
        srt_passphrase: srtPassphrase,
        secret_action: secretAction,
        auto_start: autoStart,
        zerolatency: zeroLatency,
        is_virtual: isVirtual
    };
    
    try {
        const res = await apiFetch('/api/stream/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast("Configuración guardada exitosamente", "success");
            closeConfigModal();
            fetchStatus();
        } else {
            showToast(data.detail || "Error al actualizar", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Error de comunicación", "error");
    }
}

// LOGS MODAL
function viewLogs(index) {
    const stream = _streams[index];
    if (!stream) return;
    
    _currentLogDevicePath = stream.device_path;
    document.getElementById('logs-modal-title').textContent = `${t('logs_modal_title')} — ${stream.friendly_name}`;
    document.getElementById('logs-content-box').textContent = t('logs_connecting');
    document.getElementById('logs-modal-overlay').classList.add('active');
    
    fetchLogs();
    _logsInterval = setInterval(fetchLogs, 2000);
}

async function fetchLogs() {
    if (!_currentLogDevicePath) return;
    
    try {
        const url = `/api/stream/logs?device_path=${encodeURIComponent(_currentLogDevicePath)}`;
        const res = await apiFetch(url);
        if (!res.ok) throw new Error("HTTP error " + res.status);
        const data = await res.json();
        
        const logBox = document.getElementById('logs-content-box');
        if (data.logs && data.logs.length > 0) {
            logBox.textContent = data.logs.join('\n');
            logBox.scrollTop = logBox.scrollHeight;
        } else {
            logBox.textContent = t('logs_empty');
        }
    } catch (err) {
        document.getElementById('logs-content-box').textContent = t('logs_error');
    }
}

function closeLogsModal() {
    document.getElementById('logs-modal-overlay').classList.remove('active');
    if (_logsInterval) {
        clearInterval(_logsInterval);
        _logsInterval = null;
    }
    _currentLogDevicePath = null;
}

// OPTIMIZACIONES DE ENERGÍA CON TOKEN
async function reapplySystemEnvironment() {
    const btn = document.getElementById('btn-apply-power');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Aplicando...'; }
    showToast("Aplicando directivas silenciosas de energía...", "info");
    
    try {
        const res = await apiFetch('/api/power/apply', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast("Optimizaciones de estabilidad aplicadas", "success");
            ['pwr-high-perf','pwr-sleep','pwr-hibernation','pwr-usb','pwr-hdd','pwr-network'].forEach(id => {
                const el = document.getElementById(id);
                if (el) { el.textContent = 'Aplicado'; el.style.color = 'var(--teal)'; }
            });
            const restoreBtn = document.getElementById('btn-restore-power');
            if (restoreBtn) restoreBtn.style.display = '';
        } else {
            showToast("Error al aplicar directivas de energía", "error");
        }
    } catch (err) {
        showToast("Error de conexión", "error");
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🛠️ Aplicar Optimizaciones'; }
    }
}

async function restorePowerSettings() {
    const btn = document.getElementById('btn-restore-power');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Restaurando...'; }
    showToast("Restaurando configuración original...", "info");
    
    try {
        const res = await apiFetch('/api/power/restore', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast("Configuración original restaurada", "success");
            ['pwr-high-perf','pwr-sleep','pwr-hibernation','pwr-usb','pwr-hdd','pwr-network'].forEach(id => {
                const el = document.getElementById(id);
                if (el) { el.textContent = 'Listo'; el.style.color = ''; }
            });
            if (btn) btn.style.display = 'none';
        } else {
            showToast(data.message || "Error al restaurar", "error");
        }
    } catch (err) {
        showToast("Error de conexión", "error");
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '↩️ Restaurar Configuración Original'; }
    }
}

// ADVERTENCIA AL CERRAR LA VENTANA CON FLUJOS ACTIVOS
window.addEventListener('beforeunload', (e) => {
    const activeStreams = _streams.filter(s => s.status.state === 'running');
    if (activeStreams.length > 0) {
        e.preventDefault();
        e.returnValue = 'Hay transmisiones de video en vivo activas. ¿Seguro que deseas salir?';
        return e.returnValue;
    }
});

// CONFIGURACIÓN DE MEDIAMTX (PUERTO SRT CENTRAL)
async function loadSystemSettings() {
    try {
        const res = await apiFetch('/api/system/settings');
        if (res.ok) {
            const data = await res.json();
            const portInput = document.getElementById('mediamtx-srt-port-input');
            if (portInput && data.mediamtx_srt_port) {
                portInput.value = data.mediamtx_srt_port;
            }
        }
    } catch (e) {
        console.warn("No se pudieron cargar los ajustes de sistema:", e);
    }
}

async function saveMediaMtxPort() {
    const portInput = document.getElementById('mediamtx-srt-port-input');
    const btn = document.getElementById('btn-save-mediamtx-port');
    if (!portInput) return;
    const portVal = parseInt(portInput.value, 10);
    if (isNaN(portVal) || portVal < 1024 || portVal > 65535) {
        showToast("Puerto inválido. Debe estar entre 1024 y 65535.", "error");
        return;
    }
    if (btn) btn.disabled = true;
    try {
        const res = await apiFetch('/api/system/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mediamtx_srt_port: portVal })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Puerto central SRT actualizado a ${portVal}. MediaMTX listo.`, "success");
            fetchStatus();
        } else {
            showToast(data.detail || "Error actualizando el puerto", "error");
        }
    } catch (e) {
        showToast("Error de conexión al guardar puerto", "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// INICIALIZACIÓN
window.addEventListener('DOMContentLoaded', () => {
    if (typeof initI18n === 'function') {
        initI18n();
    }
    fetchStatus();
    fetchMetrics();
    loadSystemSettings();
    loadIgnoredDevices();
    initTelemetryWebSocket();
    
    setInterval(fetchStatus, 3000);
    _metricsTicker = setInterval(fetchMetrics, 2000);
    
    _uptimeTicker = setInterval(() => {
        _streams.forEach((stream, index) => {
            if (stream.status.state === 'running' && stream.status.uptime_seconds !== null) {
                stream.status.uptime_seconds += 1;
                const uptimeEl = document.getElementById(`uptime-val-${index}`);
                if (uptimeEl) {
                    uptimeEl.textContent = formatUptime(stream.status.uptime_seconds);
                }
            }
        });
    }, 1000);

    apiFetch('/api/power/status').then(r => r.json()).then(data => {
        if (data.optimizations_applied) {
            ['pwr-high-perf','pwr-sleep','pwr-hibernation','pwr-usb','pwr-hdd','pwr-network'].forEach(id => {
                const el = document.getElementById(id);
                if (el) { el.textContent = 'Aplicado'; el.style.color = 'var(--teal)'; }
            });
            const restoreBtn = document.getElementById('btn-restore-power');
            if (restoreBtn) restoreBtn.style.display = '';
        }
    }).catch(() => {});
});

// EXPORTAR E IMPORTAR CONFIGURACIÓN (BACKUP / RESTORE)
async function exportConfiguration() {
    try {
        const res = await apiFetch('/api/config/export');
        if (!res.ok) throw new Error("HTTP error " + res.status);
        const data = await res.json();
        const jsonContent = JSON.stringify(data, null, 4);
        const suggestedFilename = `rtms_config_backup_${new Date().toISOString().slice(0,10)}.json`;

        // 1. Selector interactivo nativo (permite al usuario elegir carpeta y nombre de guardado)
        if (typeof window.showSaveFilePicker === 'function') {
            try {
                const fileHandle = await window.showSaveFilePicker({
                    suggestedName: suggestedFilename,
                    types: [{
                        description: 'Configuración RTMS (*.json)',
                        accept: { 'application/json': ['.json'] }
                    }]
                });
                const writable = await fileHandle.createWritable();
                await writable.write(jsonContent);
                await writable.close();
                showToast("Configuración guardada exitosamente en la ubicación elegida", "success");
                return;
            } catch (pickerErr) {
                // Si el usuario cancela deliberadamente el diálogo "Guardar como", no generar error
                if (pickerErr.name === 'AbortError') {
                    return;
                }
                console.warn("showSaveFilePicker no disponible o denegado, utilizando descarga estándar:", pickerErr);
            }
        }

        // 2. Fallback estándar para navegadores o entornos donde File System Access esté restringido
        const blob = new Blob([jsonContent], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = suggestedFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast("Configuración exportada a la carpeta de Descargas", "success");
    } catch (err) {
        showToast("Error al exportar configuración: " + (err.message || err), "error");
    }
}

function triggerImportConfiguration() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
            const text = await file.text();
            const parsed = JSON.parse(text);
            const res = await apiFetch('/api/config/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config_data: parsed })
            });
            if (res.ok) {
                showToast("Configuración importada exitosamente", "success");
                fetchStatus();
            } else {
                const errData = await res.json();
                showToast(errData.detail || "Error al importar configuración", "error");
            }
        } catch (err) {
            showToast("Archivo JSON inválido o corrupto", "error");
        }
    };
    input.click();
}

// CONTROLADOR DEL MODAL DE VISTA PREVIA ON-DEMAND (WebRTC WHEP CON FALLBACK MJPEG)
let _whepPeerConnection = null;
let _previewActiveStream = null;

async function openPreviewModal(index) {
    const stream = _streams[index];
    if (!stream) return;

    const modal = document.getElementById('preview-modal');
    const titleEl = document.getElementById('preview-modal-title');
    const imgEl = document.getElementById('preview-modal-img');
    const videoEl = document.getElementById('preview-video');
    const infoEl = document.getElementById('preview-modal-info');
    const ffplayBtn = document.getElementById('preview-ffplay-btn');
    const loader = document.getElementById('preview-loader');

    if (!modal) return;
    _previewActiveStream = stream;

    titleEl.textContent = `${t('preview_modal_title')} — ${stream.friendly_name}`;
    const isRunning = stream.status.state === 'running';
    const isVirtual = Boolean(stream.is_virtual || (stream.device_path && (stream.device_path.startsWith('virtual://') || stream.device_path.startsWith('testsrc'))));

    const portDisplay = stream.protocol === 'srt'
        ? `SRT Central :${escapeHtml(stream.mediamtx_port || _mediamtxSrtPort || 8890)}`
        : `UDP :${escapeHtml(stream.port)} (${stream.udp_mode === 'unicast' ? t('label_unicast_local') : t('label_multicast_lan')})`;
    const stoppedText = isVirtual ? t('preview_virtual_generator') : t('preview_stopped_framing');
    infoEl.innerHTML = isRunning 
        ? `<span class="status-badge running"><span class="status-dot"></span>${t('preview_live_webrtc')} (${portDisplay})</span>`
        : `<span class="status-badge stopped"><span class="status-dot"></span>${stoppedText}</span>`;

    loader.style.display = 'flex';
    if (imgEl) {
        imgEl.onload = null;
        imgEl.onerror = null;
        imgEl.style.display = 'none';
        imgEl.src = '';
    }
    if (videoEl) {
        videoEl.style.display = 'none';
        videoEl.srcObject = null;
    }
    modal.classList.add('active');

    let mjpegStarted = false;
    let mjpegHasLoaded = false;
    let mjpegRetryCount = 0;
    const MAX_MJPEG_RETRIES = 2;

    const startMjpegFallback = async () => {
        if (!modal.classList.contains('active') || _previewActiveStream !== stream) return;
        if (mjpegStarted) return;
        mjpegStarted = true;

        if (_whepPeerConnection) {
            try { _whepPeerConnection.close(); } catch (e) {}
            _whepPeerConnection = null;
        }
        if (videoEl) {
            try { videoEl.pause(); } catch (e) {}
            videoEl.srcObject = null;
            videoEl.style.display = 'none';
        }

        if (!imgEl) return;

        let ticket = null;
        try {
            const ticketRes = await apiFetch('/api/preview/ticket', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_path: stream.device_path, ttl_seconds: 60 })
            });
            if (ticketRes.ok) {
                const ticketData = await ticketRes.json();
                ticket = ticketData.ticket;
            }
        } catch (e) {
            console.warn("No se pudo obtener ticket efímero de preview, recurriendo a fallback:", e);
        }

        if (!modal.classList.contains('active') || _previewActiveStream !== stream) return;

        let previewUrl = `/api/stream/${encodeURIComponent(stream.device_path)}/preview?t=${Date.now()}`;
        if (ticket) {
            previewUrl += `&ticket=${encodeURIComponent(ticket)}`;
        }

        imgEl.onload = () => {
            if (!modal.classList.contains('active') || _previewActiveStream !== stream) return;
            mjpegHasLoaded = true;
            mjpegRetryCount = 0;
            loader.style.display = 'none';
            imgEl.style.display = 'block';
            const errTag = infoEl.querySelector('.preview-error-tag');
            if (errTag) errTag.remove();
        };

        imgEl.onerror = () => {
            // Si el modal ya fue cerrado o se cambió de cámara, ignorar el evento
            if (!modal.classList.contains('active') || _previewActiveStream !== stream) return;

            // Si la vista previa ya estaba reproduciéndose correctamente y sufre una caída transitoria, reintentar suavemente
            if (mjpegHasLoaded && mjpegRetryCount < MAX_MJPEG_RETRIES) {
                mjpegRetryCount++;
                console.info(`Reintentando conexión MJPEG (${mjpegRetryCount}/${MAX_MJPEG_RETRIES})...`);
                setTimeout(() => {
                    if (modal.classList.contains('active') && _previewActiveStream === stream) {
                        mjpegStarted = false;
                        startMjpegFallback();
                    }
                }, 800);
                return;
            }

            loader.style.display = 'none';
            if (!infoEl.querySelector('.preview-error-tag')) {
                const errSpan = document.createElement('span');
                errSpan.className = 'preview-error-tag';
                errSpan.style.color = 'var(--status-red)';
                errSpan.style.fontSize = '0.75rem';
                errSpan.style.marginLeft = '8px';
                errSpan.textContent = t('preview_unavailable') || '(No disponible o límite alcanzado)';
                infoEl.appendChild(errSpan);
            }
        };

        imgEl.src = previewUrl;
    };

    // 1. Intentar primero WebRTC WHEP de baja latencia (<40ms) si el flujo está activo
    let whepStarted = false;
    if (isRunning && videoEl && window.RTCPeerConnection) {
        try {
            if (_whepPeerConnection) {
                try { _whepPeerConnection.close(); } catch (e) {}
                _whepPeerConnection = null;
            }

            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });
            _whepPeerConnection = pc;

            pc.onconnectionstatechange = () => {
                if (!modal.classList.contains('active') || _previewActiveStream !== stream) return;
                if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                    console.warn(`WebRTC connectionState: ${pc.connectionState}. Fallback automático a MJPEG...`);
                    startMjpegFallback();
                }
            };

            pc.oniceconnectionstatechange = () => {
                if (!modal.classList.contains('active') || _previewActiveStream !== stream) return;
                if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                    console.warn(`WebRTC iceConnectionState: ${pc.iceConnectionState}. Fallback automático a MJPEG...`);
                    startMjpegFallback();
                }
            };

            pc.addTransceiver('video', { direction: 'recvonly' });

            pc.ontrack = (event) => {
                if (event.streams && event.streams[0]) {
                    videoEl.srcObject = event.streams[0];
                } else {
                    videoEl.srcObject = new MediaStream([event.track]);
                }
                videoEl.onloadedmetadata = () => {
                    videoEl.play().catch(() => {});
                    loader.style.display = 'none';
                    videoEl.style.display = 'block';
                };
            };

            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            const whepRes = await apiFetch(`/api/stream/${encodeURIComponent(stream.device_path)}/whep`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: offer.sdp
            });

            if (whepRes.ok) {
                const answerSdp = await whepRes.text();
                await pc.setRemoteDescription(new RTCSessionDescription({
                    type: 'answer',
                    sdp: answerSdp
                }));
                whepStarted = true;
            } else {
                console.debug("WHEP endpoint returned non-OK, falling back to MJPEG.");
            }
        } catch (webrtcErr) {
            console.debug("WebRTC WHEP no disponible, utilizando generador MJPEG fallback:", webrtcErr);
            if (_whepPeerConnection) {
                try { _whepPeerConnection.close(); } catch (e) {}
                _whepPeerConnection = null;
            }
        }
    }

    // 2. Fallback a MJPEG si WebRTC no se pudo iniciar o la cámara está detenida
    if (!whepStarted) {
        startMjpegFallback();
    }

    if (ffplayBtn) {
        ffplayBtn.onclick = () => launchFFplayExternal(stream.device_path);
    }
}

function closePreviewModal() {
    const modal = document.getElementById('preview-modal');
    const imgEl = document.getElementById('preview-modal-img');
    const videoEl = document.getElementById('preview-video');
    const infoEl = document.getElementById('preview-modal-info');
    _previewActiveStream = null;

    if (modal) {
        modal.classList.remove('active');
    }
    if (_whepPeerConnection) {
        try { _whepPeerConnection.close(); } catch (e) {}
        _whepPeerConnection = null;
    }
    if (videoEl) {
        try { videoEl.pause(); } catch (e) {}
        videoEl.srcObject = null;
        videoEl.style.display = 'none';
    }
    if (imgEl) {
        imgEl.onload = null;
        imgEl.onerror = null;
        imgEl.src = '';
        imgEl.style.display = 'none';
    }
    if (infoEl) {
        const errTag = infoEl.querySelector('.preview-error-tag');
        if (errTag) errTag.remove();
    }
}

async function launchFFplayExternal(devicePath) {
    try {
        const res = await apiFetch(`/api/stream/${encodeURIComponent(devicePath)}/ffplay`, {
            method: 'POST'
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, 'success');
        } else {
            showToast(data.detail || 'Error al iniciar FFplay', 'error');
        }
    } catch (e) {
        showToast('Error al conectar con el servidor', 'error');
    }
}

// CONTROLADOR DEL MODAL DE CÓDIGO QR PARA REPRODUCCIÓN EN CELULAR Y REPRODUCTORES
let _currentQrCodeInstance = null;
let _currentModalStream = null;

async function openQrModal(index) {
    const stream = _streams[index];
    if (!stream) return;
    _currentModalStream = stream;

    const modal = document.getElementById('qr-modal-overlay');
    const nameEl = document.getElementById('qr-stream-name');
    const badgeEl = document.getElementById('qr-protocol-badge');
    const modalTitleEl = document.getElementById('qr-modal-title');
    const destInfoEl = document.getElementById('qr-dest-info');
    const destIpEl = document.getElementById('qr-dest-ip');
    const destPortEl = document.getElementById('qr-dest-port');
    const obsHintEl = document.getElementById('qr-obs-hint');
    const urlInput = document.getElementById('qr-url-input');
    const vlcCmdInput = document.getElementById('qr-vlc-cmd-input');
    const qrContainer = document.getElementById('qr-code-display');

    if (!modal || !qrContainer) return;

    nameEl.textContent = `${stream.friendly_name}`;

    const isUnicast = (stream.protocol === 'udp_unicast') || (stream.udp_mode === 'unicast');
    const destIp = stream.udp_host || '127.0.0.1';
    const isLocalhost = (destIp === '127.0.0.1' || destIp === 'localhost');

    if (modalTitleEl) {
        if (isUnicast) {
            modalTitleEl.textContent = t('unicast_share_title');
        } else if (stream.protocol === 'srt') {
            modalTitleEl.textContent = t('srt_share_title');
        } else {
            modalTitleEl.textContent = t('mcast_share_title');
        }
    }

    if (badgeEl) {
        if (stream.protocol === 'srt') {
            const srtPort = stream.mediamtx_port || _mediamtxSrtPort || 8890;
            badgeEl.innerHTML = `<span class="badge" style="background:rgba(20,184,166,0.15); border:1px solid var(--teal); color:var(--teal); font-weight:700; padding:3px 10px; border-radius:var(--radius-full); font-size:0.75rem;">🔒 SRT Media Server (Puerto ${srtPort})</span>`;
        } else if (isUnicast) {
            badgeEl.innerHTML = `<span class="badge" style="background:rgba(59,130,246,0.15); border:1px solid var(--blue); color:var(--cyan); font-weight:700; padding:3px 10px; border-radius:var(--radius-full); font-size:0.75rem;">📡 UDP Unicast (Destino: ${destIp}:${stream.port})</span>`;
        } else {
            badgeEl.innerHTML = `<span class="badge" style="background:rgba(16,185,129,0.15); border:1px solid var(--status-green); color:var(--status-green); font-weight:700; padding:3px 10px; border-radius:var(--radius-full); font-size:0.75rem;">🌐 UDP Multicast LAN (Puerto ${stream.port})</span>`;
        }
    }

    if (destInfoEl) {
        if (isUnicast) {
            destInfoEl.style.display = 'block';
            if (destIpEl) destIpEl.textContent = destIp;
            if (destPortEl) destPortEl.textContent = stream.port;
        } else {
            destInfoEl.style.display = 'none';
        }
    }

    // Obtener la URL más actualizada con autenticación/passphrase y comando VLC
    let targetUrl = '';
    let obsUrl = '';
    let vlcCmd = '';
    try {
        const res = await apiFetch(`/api/stream/${encodeURIComponent(stream.device_path)}/connect_url`);
        if (res.ok) {
            const data = await res.json();
            targetUrl = data.receive_url || data.vlc_url || data.connect_url || '';
            obsUrl = data.receive_url || data.connect_url || targetUrl;
            vlcCmd = data.vlc_command || '';
        }
    } catch (e) {
        console.warn('Fallo obteniendo URL para QR, usando fallback:', e);
    }

    if (!targetUrl) {
        if (stream.protocol === 'srt') {
            const srtPort = stream.mediamtx_port || _mediamtxSrtPort || 8890;
            const cleanCamId = stream.clean_cam_id || stream.id;
            targetUrl = `srt://${_localIp}:${srtPort}?streamid=read:${cleanCamId}`;
            obsUrl = targetUrl;
        } else if (isUnicast) {
            targetUrl = isLocalhost ? `udp://127.0.0.1:${stream.port}` : `udp://${destIp}:${stream.port}`;
            obsUrl = targetUrl;
        } else {
            const p = parseInt(stream.port);
            const ipLastOctet = (p >= 9000 && p <= 9200) ? ((p - 9000) + 1) : (((p - 1024) % 250) + 1);
            targetUrl = `udp://@239.255.0.${ipLastOctet}:${stream.port}`;
            obsUrl = targetUrl;
        }
    }

    if (!vlcCmd) {
        vlcCmd = `vlc.exe "${targetUrl}" :network-caching=300 :drop-late-frames :skip-frames`;
    }

    if (obsHintEl) {
        if (isUnicast) {
            obsHintEl.textContent = isLocalhost 
                ? 'ℹ️ Pega esta URL en OBS (Fuente multimedia) en esta misma PC.' 
                : `ℹ️ Pega esta URL en OBS (Fuente multimedia) en el equipo receptor (${destIp}).`;
        } else {
            obsHintEl.textContent = '';
        }
    }

    const obsInput = document.getElementById('qr-obs-url-input');
    if (obsInput) obsInput.value = obsUrl || targetUrl;
    if (urlInput) urlInput.value = targetUrl;
    if (vlcCmdInput) vlcCmdInput.value = vlcCmd;
    qrContainer.innerHTML = '';

    if (typeof QRCode !== 'undefined') {
        _currentQrCodeInstance = new QRCode(qrContainer, {
            text: targetUrl,
            width: 220,
            height: 220,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M
        });
    } else {
        qrContainer.innerHTML = '<p style="color:#000; font-size:0.8rem;">Generador QR no cargado.</p>';
    }

    modal.classList.add('active');
}

function closeQrModal() {
    const modal = document.getElementById('qr-modal-overlay');
    if (modal) modal.classList.remove('active');
    const qrContainer = document.getElementById('qr-code-display');
    if (qrContainer) qrContainer.innerHTML = '';
}

function copyQrUrl() {
    const urlInput = document.getElementById('qr-url-input');
    if (urlInput && urlInput.value) {
        copyText(urlInput.value, "URL copiada al portapapeles");
        showToast("URL limpia copiada para VLC Mobile");
    }
}

function copyObsUrl() {
    const obsInput = document.getElementById('qr-obs-url-input');
    if (obsInput && obsInput.value) {
        copyText(obsInput.value, "URL copiada al portapapeles");
        showToast("URL copiada para OBS Studio / vMix");
    }
}

async function launchVlcCurrentModalStream() {
    if (!_currentModalStream) return;
    try {
        const dp = _currentModalStream.device_path;
        showToast("Lanzando VLC Media Player en baja latencia...");
        const res = await apiFetch(`/api/stream/${encodeURIComponent(dp)}/launch_vlc`, { method: "POST" });
        if (res.ok) {
            showToast("VLC Player iniciado exitosamente (300ms de búfer)");
        } else {
            const err = await res.json().catch(() => ({}));
            showToast("Aviso: " + (err.detail || "No se pudo iniciar VLC"), "error");
        }
    } catch (e) {
        showToast("Error lanzando VLC: " + e.message, "error");
    }
}

async function downloadXspfCurrentModalStream() {
    if (!_currentModalStream) return;
    try {
        const dp = _currentModalStream.device_path;
        const res = await apiFetch(`/api/stream/${encodeURIComponent(dp)}/vlc_playlist.xspf`);
        if (!res.ok) {
            showToast("Error generando playlist VLC", "error");
            return;
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        const safeName = (_currentModalStream.friendly_name || "rtms_stream").replace(/[^a-zA-Z0-9_-]/g, "_");
        a.download = `${safeName}_baja_latencia.xspf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        showToast("Playlist .xspf descargada (Búfer 300ms)");
    } catch (e) {
        showToast("Error descargando playlist: " + e.message, "error");
    }
}

function copyVlcCmd() {
    const input = document.getElementById("qr-vlc-cmd-input");
    if (input && input.value) {
        copyText(input.value, "Comando VLC copiado");
        showToast("Comando VLC de baja latencia copiado");
    }
}

function openLatencyBenchmarkModal() {
    const modal = document.getElementById("latency-bench-modal-overlay");
    if (modal) modal.classList.add("active");
}

function closeLatencyBenchmarkModal() {
    const modal = document.getElementById("latency-bench-modal-overlay");
    if (modal) modal.classList.remove("active");
}

async function runLatencyBenchmarkTest() {
    const btn = document.getElementById("btn-run-latency-bench");
    const indicator = document.getElementById("bench-status-indicator");
    const container = document.getElementById("bench-results-container");

    if (btn) btn.disabled = true;
    if (indicator) {
        indicator.textContent = "Evaluando paquetes y pipeline...";
        indicator.style.color = "var(--teal)";
    }

    try {
        showToast("Iniciando benchmark de latencia de red y pipeline...");
        const res = await apiFetch("/api/system/latency_benchmark?udp_samples=50&video_duration=2.5", {
            method: "POST"
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Error en el benchmark");
        }
        const data = await res.json();
        const bench = data.benchmark || {};
        const phases = bench.phases || {};

        if (container) container.style.display = "block";

        // 1. Socket UDP Ping
        const udp = phases.udp_socket_ping || {};
        const udpPingEl = document.getElementById("metric-udp-ping");
        const udpDetailsEl = document.getElementById("metric-udp-details");
        if (udpPingEl && udp.avg_ms !== undefined) {
            udpPingEl.textContent = `${udp.avg_ms.toFixed(3)} ms`;
            if (udpDetailsEl) {
                udpDetailsEl.textContent = `Min: ${udp.min_ms.toFixed(3)}ms | Jitter: ${udp.jitter_ms.toFixed(3)}ms | Pérdida: ${(udp.loss_rate * 100).toFixed(1)}%`;
            }
        }

        // 2. TCP Handshake Ping
        const tcp = phases.tcp_mediamtx_api_ping || {};
        const tcpPingEl = document.getElementById("metric-tcp-ping");
        const tcpDetailsEl = document.getElementById("metric-tcp-details");
        if (tcpPingEl && tcp.avg_ms !== undefined) {
            tcpPingEl.textContent = `${tcp.avg_ms.toFixed(3)} ms`;
            if (tcpDetailsEl) {
                tcpDetailsEl.textContent = `Min: ${tcp.min_ms.toFixed(3)}ms | p95: ${tcp.p95_ms.toFixed(3)}ms`;
            }
        }

        // 3. Video Pipeline TTFF
        const video = phases.srt_pipeline || {};
        const videoTtffEl = document.getElementById("metric-video-ttff");
        const videoFpsEl = document.getElementById("metric-video-fps");
        if (videoTtffEl && video.time_to_first_frame_ms !== undefined) {
            videoTtffEl.textContent = `${video.time_to_first_frame_ms.toFixed(1)} ms`;
            if (videoFpsEl) {
                videoFpsEl.textContent = `FPS: ${video.fps_measured.toFixed(1)} | Jitter: ${video.inter_frame_jitter_ms.toFixed(2)}ms`;
            }
        }

        // 4. VLC Cache
        const rec = bench.recommendations || {};
        const vlcCacheEl = document.getElementById("metric-vlc-cache");
        if (vlcCacheEl) {
            vlcCacheEl.textContent = `${rec.optimal_vlc_caching_ms || 300} ms`;
        }

        if (indicator) {
            indicator.textContent = "Completado exitosamente";
            indicator.style.color = "var(--status-green)";
        }
        showToast("Diagnóstico de latencia completado con éxito");
    } catch (e) {
        if (indicator) {
            indicator.textContent = "Fallo en diagnóstico";
            indicator.style.color = "#ef4444";
        }
        showToast("Error ejecutando diagnóstico: " + e.message, "error");
    } finally {
        if (btn) btn.disabled = false;
    }
}

