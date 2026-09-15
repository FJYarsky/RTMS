/* ==============================================================================
   RTMS — Real-Time Multicam System v2.2.0
   Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
   Controlador Frontend Asíncrono de SPA
============================================================================== */

let _streams = [];
let _localIp = '127.0.0.1';
let _logsInterval = null;
let _currentLogDevicePath = null;
let _uptimeTicker = null;
let _metricsTicker = null;
let _virtualGridVisible = false;

// TOKEN DE SEGURIDAD CSRF LOCAL
function getApiToken() {
    return document.querySelector('meta[name="rtms-token"]')?.content || '';
}

// FETCH HELPER SEGURO CON TOKEN X-RTMS-Token
async function apiFetch(url, options = {}) {
    options.headers = options.headers || {};
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
}

// NOTIFICACIONES TOAST (Sanitizado seguro sin inyección de innerHTML)
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';

    const spanWrapper = document.createElement('span');
    spanWrapper.style.display = 'flex';
    spanWrapper.style.alignItems = 'center';
    spanWrapper.style.gap = '8px';

    const iconSpan = document.createElement('span');
    iconSpan.textContent = icon;

    const msgSpan = document.createElement('span');
    msgSpan.textContent = String(message);

    spanWrapper.appendChild(iconSpan);
    spanWrapper.appendChild(msgSpan);

    const closeBtn = document.createElement('button');
    closeBtn.style.background = 'none';
    closeBtn.style.border = 'none';
    closeBtn.style.color = 'var(--text-secondary)';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.fontSize = '1.1rem';
    closeBtn.innerHTML = '&times;';
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
function copyText(text) {
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    showToast("Copiado al portapapeles", "success");
}

function copyServerIp() {
    copyText(_localIp);
}

function copyUrlByIndex(index) {
    const stream = _streams[index];
    if (!stream) return;
    const urlInput = document.getElementById(`url-input-${index}`);
    if (urlInput) {
        copyText(urlInput.value);
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

// HUD DE TELEMETRÍA EN TIEMPO REAL
async function fetchMetrics() {
    try {
        const res = await apiFetch('/api/system/metrics');
        if (!res.ok) return;
        const data = await res.json();
        
        // CPU
        const cpuEl = document.getElementById('hud-cpu-val');
        if (cpuEl) cpuEl.textContent = `${Math.round(data.cpu_percent)}%`;

        // GPU
        const gpuEl = document.getElementById('hud-gpu-val');
        const gpuItem = document.getElementById('hud-gpu-item');
        if (gpuEl) {
            if (data.gpu_available && data.gpu_percent !== null && data.gpu_percent !== undefined) {
                gpuEl.textContent = `${Math.round(data.gpu_percent)}%`;
                if (gpuItem && data.gpu_name) {
                    const vram = (data.gpu_memory_used_mb !== null && data.gpu_memory_total_mb !== null)
                        ? ` (VRAM: ${Math.round(data.gpu_memory_used_mb)} / ${Math.round(data.gpu_memory_total_mb)} MB)`
                        : '';
                    gpuItem.title = `${data.gpu_name}${vram}`;
                }
            } else {
                gpuEl.textContent = 'N/A';
                if (gpuItem) gpuItem.title = 'Sin GPU dedicada detectada o métricas no disponibles';
            }
        }
        
        // RAM
        const ramEl = document.getElementById('hud-ram-val');
        if (ramEl) ramEl.textContent = `${Math.round(data.memory_percent)}%`;

        // RED
        const netEl = document.getElementById('hud-net-val');
        const netItem = document.getElementById('hud-net-item');
        if (netEl) {
            const total = data.net_total_kbps || 0;
            const sent = data.net_sent_kbps || 0;
            const recv = data.net_recv_kbps || 0;
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
        if (brEl) {
            if (data.total_bitrate_kbps > 1000) {
                brEl.textContent = `${(data.total_bitrate_kbps / 1000).toFixed(1)} Mbps`;
            } else {
                brEl.textContent = `${Math.round(data.total_bitrate_kbps)} kbps`;
            }
        }
    } catch (e) {
        // Silencioso
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
                No hay transmisiones activas en este momento. Ve a la sección de <strong>Cámaras</strong> y haz clic en <strong>Iniciar</strong> para comenzar a emitir hacia OBS.
            </div>
        `;
        return;
    }
    
    activeStreams.forEach(stream => {
        const globalIndex = _streams.findIndex(s => s.device_path === stream.device_path);
        
        let clientUrl = '';
        let protocolLabel = '';
        if (stream.protocol === 'srt') {
            protocolLabel = 'SRT Caller (Ultra baja latencia)';
            // Si tiene contraseña protegida, indicarlo en la URL
            const passNotice = stream.has_passphrase ? ' [Contraseña Requerida]' : '';
            clientUrl = `srt://${_localIp}:${stream.port}?mode=caller&latency=${stream.srt_latency * 1000}`;
        } else {
            protocolLabel = 'UDP Multicast (Multipreceptor)';
            const ipLastOctet = (stream.port % 200) + 1;
            clientUrl = `udp://239.255.0.${ipLastOctet}:${stream.port}?pkt_size=1316`;
        }
        
        const row = document.createElement('div');
        row.style.marginBottom = '20px';
        row.style.paddingBottom = '16px';
        row.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
        row.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                <strong style="color: var(--teal); font-size: 0.95rem;">${escapeHtml(stream.friendly_name)}</strong>
                <span class="status-badge running"><span class="status-dot"></span>Transmitiendo</span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 6px;">
                Protocolo: <strong>${protocolLabel}</strong> | Resolución: <strong>${stream.resolution} @ ${stream.fps} FPS</strong> | Bitrate: <strong>${stream.bitrate} kbps</strong>
            </div>
            <div class="copy-input-grp">
                <input type="text" id="url-input-${globalIndex}" value="${clientUrl}" readonly>
                <button class="copy-icon-btn" onclick="copyUrlByIndex(${globalIndex})">Copiar URL</button>
            </div>
        `;
        container.appendChild(row);
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
            <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">
                <p style="font-size: 1.1rem; margin-bottom: 12px;">No se han detectado cámaras DirectShow en el sistema.</p>
                <p style="font-size: 0.85rem;">Conecta tus cámaras USB y haz clic en "Escanear Hardware".</p>
            </div>
        `;
        if (virtualSection) virtualSection.style.display = 'none';
        return;
    }

    let virtualCount = 0;
    
    _streams.forEach((stream, index) => {
        const card = createCameraCardElement(stream, index);
        
        if (stream.is_virtual) {
            virtualCount++;
            if (virtualGrid) virtualGrid.appendChild(card);
        } else {
            mainGrid.appendChild(card);
        }
    });

    if (virtualSection) {
        if (virtualCount > 0) {
            virtualSection.style.display = 'block';
            if (virtualCountBadge) virtualCountBadge.textContent = virtualCount;
        } else {
            virtualSection.style.display = 'none';
        }
    }
}

// CREADOR DE TARJETAS DE CÁMARA
function createCameraCardElement(stream, index) {
    const card = document.createElement('div');
    card.className = 'stream-card';
    
    const state = stream.status.state;
    let badgeClass = 'stopped';
    let badgeText = 'Detenido';
    
    if (state === 'running') { badgeClass = 'running'; badgeText = 'En Vivo'; }
    else if (state === 'starting') { badgeClass = 'starting'; badgeText = 'Iniciando'; }
    else if (state === 'restarting') { badgeClass = 'restarting'; badgeText = 'Reiniciando'; }
    else if (state === 'error') { 
        badgeClass = 'failed'; 
        badgeText = stream.status.error_count >= 5 ? 'Fallo Permanente' : 'Reintentando...'; 
    }
    
    const protocolName = stream.protocol === 'srt' ? 'SRT Listener' : 'UDP Multicast';
    
    let actionBtnHtml = '';
    if (state === 'running' || state === 'starting' || state === 'restarting') {
        actionBtnHtml = `<button class="btn btn-danger btn-sm" onclick="controlStream(${index}, 'stop')">⏹️ Detener</button>`;
    } else {
        actionBtnHtml = `<button class="btn btn-success btn-sm" onclick="controlStream(${index}, 'start')">▶️ Iniciar</button>`;
    }
    
    const uptimeStr = formatUptime(stream.status.uptime_seconds);
    const liveFps = stream.status.current_fps ? `${stream.status.current_fps} FPS` : '–';
    const liveBitrate = stream.status.current_bitrate_kbps ? `${Math.round(stream.status.current_bitrate_kbps)} kbps` : '–';
    const fallbackTag = stream.status.using_fallback_cpu ? '<span style="color:var(--status-yellow); font-size:0.7rem; font-weight:700;">(Modo CPU Fallback)</span>' : '';
    const autostartChecked = stream.auto_start ? 'checked' : '';

    const encText = (stream.actual_encoder && stream.actual_encoder !== 'desconocido' && stream.encoder === 'auto')
        ? `auto (${stream.actual_encoder})`
        : (stream.encoder || 'auto');

    let alertBanner = '';
    if (stream.permanent_failure) {
        alertBanner = `<div class="alert-box alert-danger" style="margin: 8px 0; padding: 6px 10px; font-size: 0.75rem; border-radius: 6px;">⚠️ Superado límite de reintentos. Verifique si el dispositivo está en uso o desconectado.</div>`;
    } else if (!stream.is_connected) {
        alertBanner = `<div class="alert-box alert-warning" style="margin: 8px 0; padding: 6px 10px; font-size: 0.75rem; border-radius: 6px;">🔌 Dispositivo desconectado físicamente. En espera de reconexión.</div>`;
    }

    card.innerHTML = `
        <div class="stream-card-hdr">
            <div>
                <div class="stream-name">${escapeHtml(stream.friendly_name)}</div>
                ${fallbackTag}
            </div>
            <span class="status-badge ${badgeClass}"><span class="status-dot"></span>${badgeText}</span>
        </div>
        
        ${alertBanner}

        <div style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.4;">
            <p>Puerto SRT/UDP: <strong>${stream.port}</strong></p>
            <p>Protocolo: <strong>${protocolName}</strong></p>
            <p>Perfil: <strong>${stream.resolution} @ ${stream.fps} FPS | ${stream.bitrate} kbps</strong></p>
            <p>Codificador: <strong>${encText}</strong></p>
            <div style="margin-top: 6px;">
                <label style="font-size: 0.75rem; display: flex; align-items: center; gap: 6px; cursor: pointer; color: var(--teal);">
                    <input type="checkbox" ${autostartChecked} onchange="toggleCamAutostart(${index}, this.checked)" style="display:inline-block;">
                    <span>Autoarranque al encender PC</span>
                </label>
            </div>
        </div>

        <div class="stream-meta-row">
            <span>Uptime: <strong id="uptime-val-${index}">${uptimeStr}</strong></span>
            <span>En vivo: <strong>${liveFps}</strong> | <strong>${liveBitrate}</strong></span>
        </div>
        
        <div class="actions-row" style="flex-wrap: wrap;">
            ${actionBtnHtml}
            <button class="btn btn-primary btn-sm" onclick="openPreviewModal(${index})">👁️ Vista Previa</button>
            <button class="btn btn-ghost btn-sm" onclick="controlStream(${index}, 'restart')">🔄 Reiniciar</button>
            <button class="btn btn-ghost btn-sm" onclick="configureStream(${index})">⚙️ Ajustes</button>
            <button class="btn btn-ghost btn-sm" onclick="viewLogs(${index})">📝 Logs</button>
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

// ACCIONES DE CONTROL DE STREAM CON TOKEN
async function controlStream(index, action) {
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
    btn.textContent = "⌛ Escaneando...";
    
    try {
        const res = await apiFetch('/api/hardware/scan', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast("Escaneo de hardware completado", "success");
            fetchStatus();
        } else {
            showToast("Error al escanear hardware", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Error de red durante el escaneo", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "🔄 Escanear Hardware";
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

// DETENCIÓN DE EMERGENCIA CON TOKEN
function confirmEmergencyStop() {
    document.getElementById('emergency-modal-overlay').classList.add('active');
}

function closeEmergencyModal() {
    document.getElementById('emergency-modal-overlay').classList.remove('active');
}

async function executeEmergencyStop() {
    closeEmergencyModal();
    showToast("Ejecutando detención de emergencia...", "info");
    try {
        const res = await apiFetch('/api/system/emergency_stop', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "error");
            fetchStatus();
        }
    } catch (e) {
        showToast("Error al enviar comando de emergencia", "error");
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
    
    document.getElementById('config-modal-title').textContent = `Ajustes — ${stream.friendly_name}`;
    document.getElementById('config-device-path').value = stream.device_path;
    document.getElementById('config-port').value = stream.port;
    document.getElementById('config-resolution').value = stream.resolution;
    document.getElementById('config-fps').value = stream.fps.toString();
    document.getElementById('config-bitrate').value = stream.bitrate;
    document.getElementById('config-protocol').value = stream.protocol || 'srt';
    document.getElementById('config-encoder').value = stream.encoder;
    document.getElementById('config-cam-autostart').checked = stream.auto_start;
    document.getElementById('config-zerolatency').checked = stream.zerolatency;
    document.getElementById('config-is-virtual').checked = stream.is_virtual;
    
    document.getElementById('config-srt-latency').value = stream.srt_latency || 120;
    // Mostrar enmascarada si ya existe
    document.getElementById('config-srt-passphrase').value = stream.srt_passphrase || '';
    
    handleProtocolChange(stream.protocol || 'srt');
    document.getElementById('config-modal-overlay').classList.add('active');
}

function closeConfigModal() {
    document.getElementById('config-modal-overlay').classList.remove('active');
}

function handleProtocolChange(protocol) {
    const advPanel = document.getElementById('config-advanced-panel');
    const advTrigger = document.querySelector('.advanced-trigger');
    
    if (protocol === 'srt') {
        if (advTrigger) advTrigger.style.display = 'flex';
    } else {
        if (advTrigger) advTrigger.style.display = 'none';
        if (advPanel) advPanel.classList.remove('active');
        const chev = document.getElementById('advanced-chevron');
        if (chev) chev.innerHTML = '&#9662;';
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
        document.getElementById('config-fps').value = '30';
        document.getElementById('config-bitrate').value = 3000;
    } else if (preset === 'lowest') {
        document.getElementById('config-resolution').value = '480p';
        document.getElementById('config-fps').value = '24';
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
    const protocol = document.getElementById('config-protocol').value;
    const encoder = document.getElementById('config-encoder').value;
    const srtLatency = parseInt(document.getElementById('config-srt-latency').value);
    const srtPassphrase = document.getElementById('config-srt-passphrase').value.trim();
    const autoStart = document.getElementById('config-cam-autostart').checked;
    const zeroLatency = document.getElementById('config-zerolatency').checked;
    const isVirtual = document.getElementById('config-is-virtual').checked;
    
    if (protocol === 'srt' && srtPassphrase !== '' && srtPassphrase !== '••••••••' && srtPassphrase.length < 10) {
        showToast("La contraseña SRT debe tener al menos 10 caracteres.", "error");
        return;
    }
    
    const payload = {
        device_path: devicePath,
        resolution: resolution,
        fps: fps,
        bitrate: bitrate,
        protocol: protocol,
        encoder: encoder,
        srt_latency: srtLatency,
        srt_passphrase: srtPassphrase,
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
    document.getElementById('logs-modal-title').textContent = `Logs de FFmpeg — ${stream.friendly_name}`;
    document.getElementById('logs-content-box').textContent = "Conectando al log de FFmpeg...";
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
            logBox.textContent = "No hay registros disponibles para este flujo en este momento.";
        }
    } catch (err) {
        document.getElementById('logs-content-box').textContent = "Error al leer los logs del servidor.";
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

// INICIALIZACIÓN
window.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    fetchMetrics();
    
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

// CONTROLADOR DEL MODAL DE VISTA PREVIA ON-DEMAND
function openPreviewModal(index) {
    const stream = _streams[index];
    if (!stream) return;

    const modal = document.getElementById('preview-modal');
    const titleEl = document.getElementById('preview-modal-title');
    const imgEl = document.getElementById('preview-modal-img');
    const infoEl = document.getElementById('preview-modal-info');
    const ffplayBtn = document.getElementById('preview-ffplay-btn');
    const loader = document.getElementById('preview-loader');

    if (!modal || !imgEl) return;

    titleEl.textContent = `Vista Previa — ${stream.friendly_name}`;
    const token = getApiToken();
    const isRunning = stream.status.state === 'running';

    infoEl.innerHTML = isRunning 
        ? `<span class="status-badge running"><span class="status-dot"></span>En Vivo (${stream.protocol.toUpperCase()}:${stream.port})</span>`
        : `<span class="status-badge stopped"><span class="status-dot"></span>Encuadre DirectShow (Stream Detenido)</span>`;

    loader.style.display = 'flex';
    imgEl.style.display = 'none';

    // Generar URL con token y cache-buster
    const previewUrl = `/api/stream/${encodeURIComponent(stream.device_path)}/preview?token=${encodeURIComponent(token)}&t=${Date.now()}`;

    imgEl.onload = () => {
        loader.style.display = 'none';
        imgEl.style.display = 'block';
    };

    imgEl.onerror = () => {
        loader.style.display = 'none';
        infoEl.innerHTML += ` <span style="color:var(--status-red); font-size:0.75rem;">(No disponible)</span>`;
    };

    imgEl.src = previewUrl;

    if (ffplayBtn) {
        ffplayBtn.onclick = () => launchFFplayExternal(stream.device_path);
    }

    modal.classList.add('active');
}

function closePreviewModal() {
    const modal = document.getElementById('preview-modal');
    const imgEl = document.getElementById('preview-modal-img');
    if (imgEl) {
        // Cortar la conexión inmediatamente para que el generador termine y libere el 100% de CPU/GPU
        imgEl.src = '';
    }
    if (modal) {
        modal.classList.remove('active');
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
