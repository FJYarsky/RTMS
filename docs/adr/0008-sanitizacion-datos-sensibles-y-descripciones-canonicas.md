# ADR-0008: Sanitización Retroactiva de PII y Descripciones Canónicas de GitHub

* **Fecha**: 2026-09-29
* **Estado**: Aceptado
* **Autores**: Joaquín Yarsky (<joaquinyarsky@gmail.com>)
* **Área de Impacto**: Seguridad / Privacidad / Repositorio / Estándares
* **Revisores**: Equipo de Desarrollo RTMS

---

## 1. Contexto y Planteamiento del Problema
En repositorios públicos de código abierto en GitHub, la filtración inadvertida de Información de Identificación Personal (PII) —como números telefónicos personales, cuentas privadas de mensajería instantánea o credenciales expuestas— representa un riesgo de seguridad y privacidad directo para el mantenedor del proyecto.

Asimismo, la interfaz web de navegación de GitHub muestra junto a cada carpeta o archivo del árbol raíz el mensaje del último commit que lo modificó. En repositorios grandes, los mensajes de commit ad-hoc o generados por refactorizaciones dispersas provocan que la interfaz muestre frases truncadas o desactualizadas, degradando la presentación profesional del proyecto.

## 2. Factores Decisivos (Decision Drivers)
* **Protección Estricta de la Privacidad (PII Zero-Leak)**: Ningún número telefónico ni dato de contacto no oficial debe residir en archivos activos, plantillas de issue, metadatos ni documentación.
* **Presentación Canónica Impecable en GitHub**: Cada uno de los 32 elementos del directorio raíz del repositorio debe exhibir una descripción técnica concisa, uniforme y menor a 45 caracteres (para evitar elipsis `...` en GitHub).
* **Auditoría Automatizada**: El proceso debe ser verificable en CI y localmente mediante un script estricto sin margen de error.

## 3. Opciones Consideradas
* **Opción A (Revisión manual esporádica)**: Descartada por ser falible y no prevenir futuras reintroducciones de datos personales.
* **Opción B (Reglas de pre-commit y reescritura total destructiva de historial Git)**: Re-escribir todo el árbol Git con `git-filter-repo` invalida los hashes y forks existentes de colaboradores.
* **Opción C (Sanitización activa del árbol de trabajo + Script de auditoría estricta y sincronización canónica)**: Purgar toda PII del árbol de trabajo, actualizar los releases y diseñar scripts dedicados de verificación (`repo_sanitizer.py` y `manage_descriptions.py`).

## 4. Decisión
Se implementa la **Opción C**:
1. **Sanitización de PII**:
   - Se suprime todo número de WhatsApp o teléfono personal de todo el repositorio, plantillas `.github/ISSUE_TEMPLATE`, cabeceras de archivos y documentación, canalizando el contacto exclusivamente a través de GitHub Issues y el correo electrónico oficial `joaquinyarsky@gmail.com`.
2. **Catálogo Canónico de Descripciones**:
   - En [`scripts/manage_descriptions.py`](file:///C:/Users/joaqu/Desktop/RTMS/scripts/manage_descriptions.py) se define el diccionario inmutable `DESCRIPTIONS_CATALOG` para los 32 elementos raíz.
   - Si una modificación posterior altera el mensaje de commit de una carpeta raíz (drift), el comando `python scripts/manage_descriptions.py --restore` restaura automáticamente las descripciones canónicas mediante modificaciones neutras (`# rtms-sync` cumpliendo con las 2 líneas en blanco de PEP 8).
3. **Auditor de Salud del Repositorio**:
   - Se crea [`scripts/repo_sanitizer.py`](file:///C:/Users/joaqu/Desktop/RTMS/scripts/repo_sanitizer.py) con soporte `--strict`, el cual audita el estado de Git, linters Ruff, tipado estático Mypy, workflows de GitHub Actions y sincronización de descripciones canónicas.

## 5. Consecuencias
### Consecuencias Positivas (+)
* **Privacidad Blindada**: Eliminación total del número personal del autor en todo el código y configuración.
* **Estética de Repositorio de Nivel Enterprise**: La vista raíz de GitHub muestra un índice prolijo, limpio y comprensible.
* **Detección Automática de Deriva**: Si un commit desalinea las descripciones, el sanitizer lo detecta inmediatamente con código de salida no nulo.

### Consecuencias Negativas / Limitaciones (-)
* Cada refactorización que toque varias carpetas raíz requiere ejecutar el sincronizador de descripciones al finalizar.

## 6. Validación y Cumplimiento
* Certificado al 100% (32/32 elementos sincronizados) mediante `python scripts/repo_sanitizer.py --strict`.
* Pruebas automatizadas en [`tests/test_descriptions.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_descriptions.py) y [`tests/test_repo_sanitizer.py`](file:///C:/Users/joaqu/Desktop/RTMS/tests/test_repo_sanitizer.py).
