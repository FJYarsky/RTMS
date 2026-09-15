# Guía de Contribución — RTMS v2.2.2

¡Gracias por tu interés en contribuir a **RTMS (Real-Time Multicam System)**!

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
5. **Haz Commit de tus Cambios** siguiendo convenciones de [Conventional Commits](https://www.conventionalcommits.org/):
   ```bash
   git commit -m "feat(srt): optimizar buffer de transmision en vivo"
   ```
6. **Envía un Pull Request** hacia la rama `main` del repositorio oficial detallando el propósito y pruebas realizadas.

---

## Estilo de Código
- Código Python conforme a directivas PEP 8.
- Tipado estricto con anotaciones de tipo (`typing`).
- Manejo explícito de excepciones evitando cláusulas `except Exception: pass` sin registro de logs.

<!-- RTMS Contribution Guide v2.2.2 -->
