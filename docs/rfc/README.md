# Índice de Solicitudes de Comentarios y Especificaciones Técnicas (RFC)

El proceso de **Request for Comments (RFC)** en RTMS proporciona un mecanismo formal, transparente y riguroso para proponer, especificar, revisar e implementar modificaciones sustanciales en los protocolos de streaming, arquitecturas de hardware, telemetría y diseño del sistema.

Inspirado en el modelo de estándares de ingeniería de software moderno (IETF, Rust RFCs, React RFCs).

---

## Ciclo de Vida de un RFC
1. **Borrador (Draft)**: Especificación técnica inicial en redacción y debate.
2. **En Revisión (Review)**: Propuesta abierta a auditoría técnica, pruebas de concepto y benchmarking.
3. **Aprobado (Approved)**: Especificación formalmente aceptada por el equipo de arquitectura.
4. **Implementado (Implemented)**: Protocolo totalmente codificado en el núcleo y validado con pruebas automatizadas.
5. **Retirado (Withdrawn)**: Propuesta descartada o sustituida por una alternativa superior.

---

## Índice Oficial de RFCs

| RFC # | Título de la Especificación | Estado | Fecha de Implementación | Componentes |
| :---: | :--- | :---: | :---: | :--- |
| [**RFC-0001**](file:///C:/Users/joaqu/Desktop/RTMS/docs/rfc/RFC-0001-protocolo-verificacion-e2e-y-benchmark-optico.md) | Especificación del Protocolo de Verificación E2E y Benchmark Óptico de Ping | **Implementado** | 2026-09-30 | `pipeline_verifier.py`, `e2e_pipeline_tester.py` |
| [**RFC-0002**](file:///C:/Users/joaqu/Desktop/RTMS/docs/rfc/RFC-0002-arquitectura-distribucion-multicam-baja-latencia.md) | Arquitectura de Ingestión, Codificación Concurrente y Distribución Multicámara | **Implementado** | 2026-09-25 | `command_builder.py`, `stream_manager.py`, `mediamtx_mgr.py` |

---

## Cómo Presentar una Nueva Propuesta RFC
1. Duplica [`docs/rfc/template.md`](file:///C:/Users/joaqu/Desktop/RTMS/docs/rfc/template.md) asignándole el nombre `RFC-XXXX-nombre-descriptivo.md`.
2. Completa exhaustivamente el diseño detallado, diagramas y consideraciones de seguridad y rendimiento.
3. Envía un Pull Request para revisión del equipo y discusión técnica.
