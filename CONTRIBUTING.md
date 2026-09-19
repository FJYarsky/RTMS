# Guía de Contribución — RTMS

¡Gracias por tu interés en contribuir a **RTMS**!

## Flujo de Trabajo para Contribuciones

1. **Haz un Fork** del repositorio oficial: `https://github.com/FJYarsky/RTMS`.
2. **Crea una Rama Temática** para tu función o corrección:
   ```bash
   git checkout -b feature/mi-nueva-funcionalidad
   ```
3. **Configura el Entorno Local**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. **Ejecuta los Tests Automatizados y Linter**:
   Asegúrate de que el código cumpla con el estándar y todas las pruebas pasen antes de enviar cambios:
   ```bash
   ruff check .
   pytest tests/ -v
   ```
5. **Haz Commit de tus Cambios Conservando las Descripciones en GitHub**:
   Para mantener el explorador de archivos de GitHub limpio y sin truncamientos, RTMS sigue la **Convención Asunto / Cuerpo**:
   - **Asunto (1ª línea)**: Debe mantener la descripción canónica del archivo/módulo (<45 caracteres, en español).
   - **Cuerpo (líneas siguientes)**: Explica los detalles técnicos y notas de parches del cambio.
   
   Ejemplo manual:
   ```bash
   git commit -m "app: punto de entrada y servidor principal" -m "Detalle: optimización del ciclo de vida y reconexión."
   ```
   
   O mediante el asistente automático del proyecto:
   ```bash
   python scripts/manage_descriptions.py --commit main.py -m "Detalle: optimización del ciclo de vida y reconexión."
   ```

6. **Audita las Descripciones del Repositorio**:
   ```bash
   python scripts/manage_descriptions.py --check
   ```

7. **Envía un Pull Request** hacia la rama `main` del repositorio oficial detallando el propósito y pruebas realizadas.

---

## Estilo de Código
- Código Python conforme a directivas PEP 8.
- Tipado estricto con anotaciones de tipo (`typing`).
- Manejo explícito de excepciones evitando cláusulas `except Exception: pass` sin registro de logs.
