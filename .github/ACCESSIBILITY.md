# Declaración y Compromiso de Accesibilidad — RTMS

En el proyecto **RTMS (Real-Time Multicam System)** consideramos que la accesibilidad digital es un pilar fundamental de la calidad del software y una condición indispensable para el desarrollo de una comunidad abierta e inclusiva.

Nos comprometemos a garantizar que tanto las interfaces de usuario del sistema (panel de control web local, visor multicámara y sitio web oficial) como nuestra documentación técnica y canales comunitarios sean accesibles para todas las personas, incluidas aquellas con discapacidades visuales, auditivas, motrices o cognitivas.

---

## 1. Estándares y Nivel de Conformidad

RTMS tiene como objetivo el cumplimiento de las pautas de accesibilidad para el contenido web **WCAG 2.2 (Web Content Accessibility Guidelines)** en su **Nivel AA**, adoptando adicionalmente las mejores prácticas de la iniciativa WAI-ARIA (*Accessible Rich Internet Applications*) y estándares de diseño inclusivo de la plataforma Windows.

| Entorno / Componente | Estándar Objetivo | Estado Actual |
| -------------------- | ----------------- | ------------- |
| **Sitio Web Oficial (`site/`)** | WCAG 2.2 Nivel AA | Conforme (Navegación por teclado, contraste alto, *skip link*, ARIA) |
| **Panel de Control y GUI (`gui/`)** | WCAG 2.2 Nivel AA | Conforme (Semántica accesible, etiquetas formales, modo oscuro nativo) |
| **Documentación Técnica (`docs/`)** | Markdown accesible | Conforme (Jerarquía estricta de encabezados, texto alternativo descriptivo) |
| **Aplicación de Escritorio Windows** | Win32 / WebView2 | Soporte nativo de Narrador de Windows y atajos de teclado |

---

## 2. Características de Accesibilidad Implementadas

### A. Navegación Completa por Teclado
- **Enlaces de Salto (*Skip Links*)**: Las interfaces web cuentan con enlaces directos (`#main-content`) que permiten omitir la cabecera y saltar de inmediato al área de trabajo principal.
- **Secuencia y Foco Visible**: El orden de tabulación sigue la estructura lógica del documento. Todos los elementos interactivos cuentan con anillos de foco visibles y de alto contraste (`:focus-visible`).
- **Prevención de Trampas de Teclado**: Ningún modal, visor o menú desplegable retiene el foco del teclado de manera irrevocable; todos los controles pueden cerrarse con la tecla `Escape`.

### B. Compatibilidad con Lectores de Pantalla y Tecnologías de Asistencia
- **Semántica Estructural**: Marcado HTML5 semántico (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`, `<dialog>`).
- **Atributos y Roles ARIA**: Uso de `aria-label`, `aria-labelledby`, `aria-describedby`, `aria-expanded` y regiones vivas (`aria-live="polite"`) para anunciar cambios de estado en streams o reconexión de cámaras.
- **Utilidades de Lectura**: Clases utilitarias accesibles (`.sr-only`) para proveer contexto descriptivo exclusivo a lectores de pantalla (como NVDA, JAWS y Narrador de Windows) sin alterar la presentación visual.

### C. Contraste Visual y Adaptabilidad
- **Ratios de Contraste**: Ratios mínimos de contraste cromático de 4.5:1 para texto normal y 3:1 para textos grandes y componentes interactivos según WCAG 1.4.3 y 1.4.11.
- **Subrayado de Enlaces**: Los hipervínculos dentro de bloques de texto incluyen subrayado explícito o diferenciación visual evidente, sin depender únicamente del color para transmitir su condición interactiva (WCAG 1.4.1).
- **Preferencia de Movimiento Reducido**: Implementación de consultas de medios `@media (prefers-reduced-motion: reduce)` para desactivar transiciones complejas o animaciones en usuarios sensibles al movimiento.
- **Esquema Oscuro Nativo**: Interfaz optimizada para reducir fatiga visual y compatible con `color-scheme: dark`.

---

## 3. Limitaciones Conocidas

Trabajamos de forma continua para identificar y resolver barreras de acceso. Entre las limitaciones actuales bajo desarrollo activo se encuentran:
1. **Flujos de Video en Tiempo Real**: Las transmisiones de video crudo (*raw*) DirectShow o SRT no incluyen generación automatizada de subtitulado en vivo dentro del panel local.
2. **Atajos Globales de Captura**: Cuando ciertas aplicaciones de terceros capturan el foco exclusivo del sistema operativo en modo pantalla completa, los atajos de teclado globales pueden requerir volver al contexto de la ventana de RTMS.

---

## 4. Reporte de Barreras y Solicitud de Mejoras

Agradecemos profundamente los comentarios, reportes y sugerencias de la comunidad para mejorar la accesibilidad de RTMS.

Si encuentras cualquier barrera de accesibilidad o experimentas dificultades para utilizar RTMS con tu tecnología de asistencia habitual:

1. **Vía GitHub Issues (Recomendado)**:
   - Abre un reporte en [GitHub Issues](https://github.com/FJYarsky/RTMS/issues).
   - Incluye la etiqueta `accessibility` o `a11y`.
   - Describe la dificultad encontrada, la tecnología de asistencia empleada (ej. NVDA 2026, Narrador de Windows) y el navegador o versión de Windows.

2. **Vía Correo Electrónico**:
   - Envía tu reporte o sugerencia a **Joaquín Yarsky**: [joaquinyarsky@gmail.com](mailto:joaquinyarsky@gmail.com).
   - Nos comprometemos a acusar recibo y evaluar cualquier reporte de accesibilidad en un plazo máximo de **48 horas laborables**, proponiendo una vía de mitigación o incorporación al plan de desarrollo.

---

## 5. Pautas para Contribuidores

Al enviar Pull Requests con cambios en la interfaz de usuario, sitio web o documentación:
- Verifica que todo nuevo control interactivo sea totalmente operable mediante teclado.
- Asegura que los formularios incluyan etiquetas asociadas (`<label for="...">`).
- No utilices el color como único medio para comunicar éxito, advertencia o error.
- Ejecuta las validaciones de linter y formato (`ruff check .` y `ruff format --check .`) antes de enviar tu contribución.
