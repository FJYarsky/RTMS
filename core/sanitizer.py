# ==============================================================================
# RTMS v2.1.0 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import re
from typing import List, Union

# Patrones exhaustivos de secretos a enmascarar en logs, comandos y APIs (P1-06)
_SECRET_PATTERNS = [
    re.compile(r"(passphrase=)([^& \r\n\"']+)", re.IGNORECASE),
    re.compile(r"(password=)([^& \r\n\"']+)", re.IGNORECASE),
    re.compile(r"(secret=)([^& \r\n\"']+)", re.IGNORECASE),
    re.compile(r"((?:X-RTMS-Token|token)[:=]\s*)([^\r\n\"'\s]+)", re.IGNORECASE),
    re.compile(r"(Authorization:\s*(?:Bearer\s+)?)([^\r\n\"']+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([a-zA-Z0-9_\-\.]{12,})", re.IGNORECASE),
    re.compile(r"(://[^/:]+:)([^@]+)(@)", re.IGNORECASE),  # URL credentials (http://user:pass@host)
]

def sanitize_log_line(text: str) -> str:
    """
    Sanitiza una línea de log o mensaje de error eliminando credenciales SRT,
    tokens de seguridad, passwords y secrets antes de guardarse en archivo o memoria.
    """
    if not text:
        return ""
    sanitized = text
    for pattern in _SECRET_PATTERNS[:-1]:
        sanitized = pattern.sub(r"\1********", sanitized)
    # URL pattern sustituye el grupo 2
    sanitized = _SECRET_PATTERNS[-1].sub(r"\1********\3", sanitized)
    return sanitized

def sanitize_command_for_log(cmd: Union[List[str], str]) -> str:
    """
    Convierte una lista de argumentos de comando en un string legible para logs
    asegurando que cualquier contraseña o secreto quede enmascarado.
    """
    if isinstance(cmd, list):
        clean_parts = []
        for part in cmd:
            clean_part = sanitize_log_line(str(part))
            if " " in clean_part and not (clean_part.startswith('"') and clean_part.endswith('"')):
                clean_parts.append(f'"{clean_part}"')
            else:
                clean_parts.append(clean_part)
        return " ".join(clean_parts)
    return sanitize_log_line(str(cmd))
