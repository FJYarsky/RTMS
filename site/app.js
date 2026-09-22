/**
 * RTMS — Real-Time Multicam System
 * Script de cliente para la landing page oficial
 * Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
 *
 * Resuelve dinámicamente el último release desde la API de GitHub
 * sin versiones fijas en el código, gestiona copiado de URLs y navegación.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDynamicRelease();
    initCopyButtons();
});

/**
 * Consulta la API de GitHub para obtener la última versión oficial publicada,
 * su tamaño en MB, fecha de publicación y el link directo al archivo zip de Windows.
 */
async function initDynamicRelease() {
    const navVersion = document.getElementById('nav-version');
    const heroVersion = document.getElementById('hero-version');
    const downloadBtn = document.getElementById('primary-download-btn');
    const downloadSize = document.getElementById('download-size');
    const downloadDate = document.getElementById('download-date');
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
        const tagName = release.tag_name || 'v2.5.0';

        // Actualizar badges de versión
        if (navVersion) navVersion.textContent = tagName;
        if (heroVersion) heroVersion.textContent = tagName;
        if (downloadTag) downloadTag.textContent = tagName;

        // Buscar el archivo ZIP de Windows x64 en los assets del release
        const zipAsset = release.assets?.find(asset => 
            /RTMS-.*-Windows-x64\.zip/i.test(asset.name) || asset.name.endsWith('.zip')
        );

        if (zipAsset) {
            // Actualizar URL directa de descarga
            if (downloadBtn) {
                downloadBtn.href = zipAsset.browser_download_url;
                downloadBtn.setAttribute('title', `Descargar ${zipAsset.name}`);
            }

            // Calcular tamaño en MB
            if (downloadSize && zipAsset.size) {
                const sizeMB = (zipAsset.size / (1024 * 1024)).toFixed(1);
                downloadSize.textContent = `${sizeMB} MB`;
            }

            // Formatear fecha
            if (downloadDate && release.published_at) {
                const pubDate = new Date(release.published_at);
                const options = { year: 'numeric', month: 'short', day: 'numeric' };
                downloadDate.textContent = pubDate.toLocaleDateString('es-ES', options);
            }
        } else {
            // Si el release existe pero no tiene assets todavía, apuntar a la página del release
            if (downloadBtn) downloadBtn.href = release.html_url || FALLBACK_URL;
        }

    } catch (err) {
        console.warn('No se pudo consultar la API de GitHub, utilizando fallback canónico:', err);
        // Fallback resiliente
        if (downloadBtn) downloadBtn.href = FALLBACK_URL;
        if (downloadTag) downloadTag.textContent = 'Última Versión';
        if (downloadSize) downloadSize.textContent = '~50 MB';
        if (downloadDate) downloadDate.textContent = 'Oficial';
    }
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
            try {
                await navigator.clipboard.writeText(textToCopy);
                
                // Feedback visual en el botón
                const originalHtml = button.innerHTML;
                button.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                `;
                button.style.color = '#10b981';

                setTimeout(() => {
                    button.innerHTML = originalHtml;
                    button.style.color = '';
                }, 2000);
            } catch (err) {
                console.error('Fallo al copiar al portapapeles:', err);
            }
        });
    });
}
