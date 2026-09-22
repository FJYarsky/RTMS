# Política de Seguridad — RTMS

## Versiones Soportadas

RTMS adopta una política de soporte activo restringida exclusivamente a la **última versión estable liberada**. Los parches de seguridad, correcciones de fallos críticos y mitigaciones de vulnerabilidades se publican y garantizan únicamente para la versión más reciente en producción:

| Versión | Soportada |
| ------- | --------- |
| >= 2.5.0 | :white_check_mark: |
| < 2.5.0 | :x: |

> [!IMPORTANT]
> Si estás ejecutando una versión anterior a la más reciente disponible en los [Releases oficiales de GitHub](https://github.com/FJYarsky/RTMS/releases), por favor actualiza tu instalación antes de reportar un posible problema de seguridad.

---

## Reportar una Vulnerabilidad

Si descubres una vulnerabilidad o incidente de seguridad en **RTMS**, por favor **NO** abras un Issue público en GitHub ni lo comentes en discusiones públicas.

Envía un reporte confidencial detallado a:
📧 **[joaquinyarsky@gmail.com](mailto:joaquinyarsky@gmail.com)**

Por favor incluye en tu mensaje:
1. Descripción exhaustiva de la vulnerabilidad y vector de ataque identificado.
2. Pasos detallados para reproducir el fallo o código de prueba de concepto (PoC / exploit de prueba).
3. Impacto potencial en equipos locales o redes de producción (ej. escalada de privilegios, fuga de streams SRT, denegación de servicio).
4. Versión y entorno de prueba (versión de RTMS y build de Windows).

Todas las comunicaciones se tratarán con estricta confidencialidad y se responderá en un plazo máximo de 48 horas con la evaluación técnica y el cronograma de mitigación.
