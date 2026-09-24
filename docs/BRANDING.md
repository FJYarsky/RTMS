# Guía de Identidad Visual y Sistema de Diseño de RTMS

> **RTMS — Real-Time Multicam System**  
> Documento técnico de especificación de marca, tokens de diseño, geometría vectorial, tipografía y catálogo de assets visuales.  
> Diseñado y desarrollado por **Joaquín Yarsky** (<joaquinyarsky@gmail.com>).

---

## 1. Visión y Fundamentos del Rediseño

La identidad visual de **RTMS** representa una estación de transmisión multicámara de ultra-baja latencia (<100ms) para entornos de producción en vivo sobre Windows (integrando MediaMTX, SRT, UDP Multicast y OBS Studio).

### Objetivos Clave de la Renovación Visual:
1. **Eliminación del fondo blanco legado**: Se sustituye el diseño anterior de fondo blanco plano por un sistema nativo *Dark Mode First*, alineado con la paleta oscura de la interfaz (`#0b0f19` y `#111827`).
2. **Pureza Geométrica (Sin Ruido Visual)**: Se descartaron las líneas de señal periféricas para enfocar toda la fuerza del símbolo en un **obturador dinámico autocontenido** de 6 aspas entrelazadas.
3. **Alto Contraste y Tipografía Sólida**: La tipografía de la marca se fijó en **Blanco Puro (`#ffffff`)** con esquinas redondeadas tecnológicas, evitando saturación de gradientes y garantizando legibilidad instantánea a cualquier escala.
4. **Diseño Nativo de Escritorio (No móvil/iOS)**: Se descartaron los bordes gruesos y brillos de tipo "app móvil de iOS" para adoptar un estilo sobrio, limpio y moderno para Windows 10/11.

---

## 2. Elementos de Identidad

El sistema de marca de RTMS está compuesto por tres manifestaciones complementarias:

### 🔹 A. Isotipo (Símbolo Gráfico Independiente)
* **Archivo**: [`gui/static/isotype.svg`](../gui/static/isotype.svg) | [`site/isotype.svg`](../site/isotype.svg)
* **Metáfora**: La lente de estudio profesional y diafragma mecánico (iris) en constante movimiento y captación de luz/video.
* **Geometría**:
  * 6 aspas poligonales con simetría rotacional de 60°.
  * Apertura interior hexagonal en su centro.
  * Costura/separador de 2.5px a 3px entre aspas para garantizar definición mecánica.
* **Color**: Gradiente continuo de **Sky Cyan (`#38bdf8`)** hacia **Neon Teal (`#14b8a6`)** y **Deep Teal (`#0d9488`)**.
* **Uso**: Icono de aplicación de escritorio, barra de tareas de Windows, System Tray, favicons y botones compactos.

### 🔹 B. Logotipo (Wordmark Tipográfico)
* **Archivo**: [`gui/static/logotype.svg`](../gui/static/logotype.svg) | [`site/logotype.svg`](../site/logotype.svg)
* **Texto**: `RTMS`
* **Tratamiento**:
  * Color: **Blanco Sólido (`#ffffff`)**.
  * Peso: `font-weight: 800` (ExtraBold).
  * Kerning: `letter-spacing: -0.025em`.
  * Geometría: Trazos limpios con vértices exteriores suavemente suavizados.
* **Uso**: Cabeceras, pie de página, menciones de autor y documentación técnica.

### 🔹 C. Imagotipo (Integración Símbolo + Nombre)
1. **Versión Horizontal (Principal)**:
   * **Archivo**: [`gui/static/imagotype.svg`](../gui/static/imagotype.svg) | [`site/logo.svg`](../site/logo.svg)
   * **Composición**: Isotipo a la izquierda (58px) + Wordmark `RTMS` (70px) + Subtítulo `REAL-TIME MULTICAM SYSTEM` (14.5px, `letter-spacing: 4.5px`, color `#9ca3af`).
   * **Uso**: Barra superior de la GUI web (`header`) y Navbar del sitio web oficial.
2. **Versión Vertical / Apilada (Splash / Modales)**:
   * **Archivo**: [`gui/static/imagotype_vertical.svg`](../gui/static/imagotype_vertical.svg)
   * **Composición**: Isotipo centrado arriba (150px) + Wordmark `RTMS` (60px) + Subtítulo centrado.
   * **Uso**: Modal *"Acerca de RTMS"*, tarjetas de presentación, banners y diálogos de información.

---

## 3. Paleta de Colores Oficial

Todos los componentes gráficos y estilos de la aplicación respetan estrictamente las siguientes variables CSS:

| Token | Código HEX | Rol y Aplicación |
| :--- | :--- | :--- |
| `--bg-dark` | `#0b0f19` | Fondo principal profundo (Obsidian Slate). |
| `--panel-bg` | `#111827` | Fondo de cabeceras, barras laterales y paneles modales. |
| `--card-bg` | `#1f2937` / `#161f30` | Fondo de tarjetas de cámaras y contenedores de ajustes. |
| `--teal` | `#14b8a6` | Color primario de marca (Teal 500), resplandores y botones de acción. |
| `--teal-hover` | `#0d9488` | Estados *hover* y sombras profundas de las aspas del obturador. |
| `--cyan` | `#38bdf8` | Acento superior de gradiente (Sky Cyan 400) y badges de red. |
| `--blue` | `#3b82f6` | Píldoras de IP, telemetría y puertos SRT/UDP. |
| `--status-green` | `#10b981` | Cámaras activas, streaming en curso y estado nominal. |
| `--status-yellow` | `#f59e0b` | Advertencias de bitrate o estados de espera. |
| `--status-red` | `#ef4444` | Grabación activa (Tally/REC) o error en flujo DirectShow. |
| `--text-primary` | `#f3f4f6` / `#ffffff` | Color del Logotipo RTMS y textos de alto contraste. |
| `--text-secondary` | `#9ca3af` | Subtítulos de marca, etiquetas de telemetría y metadatos. |
| `--text-muted` | `#6b7280` | Separadores, bordes sutiles y textos secundarios. |

---

## 4. Sistema Tipográfico

El proyecto prioriza tipografías nativas de sistema de ultra-alto rendimiento (cero latencia de descarga web font):

### Tipografía de Interfaz (UI & Branding)
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, system-ui, sans-serif;
```
* **Titulares de Marca (`RTMS`)**: `font-weight: 800`, `letter-spacing: -0.025em`, `color: #ffffff`.
* **Subtítulo Institucional**: `font-weight: 600`, `text-transform: uppercase`, `letter-spacing: 0.15em` a `0.25em`, `color: #9ca3af`.
* **Encabezados de Sección (H1, H2, H3)**: `font-weight: 700` a `800`.
* **Cuerpo de Texto y Botones**: `font-weight: 500` a `600`.

### Tipografía de Telemetría, Logs y Código
```css
font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
```
* Empleada en: Direcciones IP, puertos, latencia en ms, frames/segundo (FPS), bitrate (kbps) e identificadores de stream SRT.

---

## 5. Inventario de Assets y Rutas en el Repositorio

```text
RTMS/
├── icon.ico                             # Icono oficial Windows (Multi-res 256, 128, 64, 48, 32, 16 px RGBA)
├── gui/
│   ├── static/
│   │   ├── isotype.svg                  # Isotipo vectorial transparente (Obturador)
│   │   ├── logotype.svg                 # Logotipo vectorial blanco puro (RTMS)
│   │   ├── imagotype.svg                # Imagotipo horizontal completo
│   │   ├── imagotype_vertical.svg       # Imagotipo vertical apilado
│   │   ├── favicon.ico                  # Favicon web multi-res para el panel web
│   │   ├── logo_showcase.html           # Panel de previsualización interactiva de marca
│   │   ├── brand_assets_sheet.png       # Hoja de muestra gráfica en alta resolución
│   │   └── brand_preview.png            # Render 512px del icono de escritorio
│   └── templates/
│       └── index.html                   # Panel web (con isotype.svg en header y modal)
├── site/
│   ├── favicon.ico                      # Favicon web multi-res (64, 48, 32, 16 px)
│   ├── isotype.svg                      # Isotipo sincronizado para landing page
│   ├── logotype.svg                     # Logotipo sincronizado para landing page
│   ├── logo.svg                         # Imagotipo horizontal para landing page
│   ├── brand_preview.png                # Vista previa oficial para Open Graph y Twitter Cards
│   └── index.html                       # Landing page oficial
└── core/
    └── tray_icon.py                     # Generador nativo de icono fallback en System Tray
```

---

## 6. Especificaciones de Implementación

### A. Uso en Componentes Web (HTML / CSS)
Para mostrar el isotipo oficial en la barra superior o cabeceras con animación de resplandor interactivo:
```html
<div class="logo-section">
    <img src="/static/isotype.svg" class="logo-icon-svg" alt="RTMS">
    <div class="logo-text">RTMS <span class="version-tag">v2.0</span></div>
</div>
```

```css
.logo-icon-svg {
    width: 26px;
    height: 26px;
    filter: drop-shadow(0 0 8px rgba(20, 184, 166, 0.4));
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), filter 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.logo-section:hover .logo-icon-svg {
    transform: rotate(18deg) scale(1.08);
    filter: drop-shadow(0 0 14px rgba(56, 189, 248, 0.6));
}

.logo-text {
    font-weight: 800;
    font-size: 1.25rem;
    letter-spacing: -0.025em;
    color: #ffffff;
}
```

### B. Empaquetado Portable para Windows (PyInstaller)
El archivo [`icon.ico`](../icon.ico) ubicado en la raíz del repositorio se inyecta de forma determinista durante la compilación en [`build_portable.bat`](../build_portable.bat) mediante:
```bat
pyinstaller --noconfirm --onedir --windowed ^
  --icon=icon.ico ^
  --add-data "icon.ico;." ^
  ...
```
Garantizando que Windows Explorer, el menú Inicio, la barra de tareas y el System Tray muestren el icono nítido sin pixelación ni bordes distorsionados.
