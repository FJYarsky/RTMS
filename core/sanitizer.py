# ==============================================================================
# RTMS — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import re
from typing import List, Union

# Patrones de secretos a enmascarar en logs y comandos
_PASSPHRASE_PATTERN = re.compile(r"(passphrase=)([^& \r\n\"']+)", re.IGNORECASE)
_TOKEN_PATTERN = re.compile(r"((?:X-RTMS-Token|token)[:=]\s*)([a-fA-F0-9]{16,})", re.IGNORECASE)

def sanitize_log_line(text: str) -> str:
    """
    Sanitiza una línea de log o mensaje de error eliminando credenciales SRT,
    tokens de seguridad y secretos antes de guardarse en archivo o memoria.
    """
    if not text:
        return ""
    sanitized = _PASSPHRASE_PATTERN.sub(r"\1********", text)
    sanitized = _TOKEN_PATTERN.sub(r"\1********", sanitized)
    return sanitized

def sanitize_command_for_log(cmd: Union[List[str], str]) -> str:
    """
    Convierte una lista de argumentos de comando en un string legible para logs
    asegurando que cualquier contraseña o secreto quede enmascarado.
    """
    if isinstance(cmd, list):
        # Sanitizar cada argumento individualmente
        clean_parts = []
        for part in cmd:
            clean_part = sanitize_log_line(str(part))
            if " " in clean_part and not (clean_part.startswith('"') and clean_part.endswith('"')):
                clean_parts.append(f'"{clean_part}"')
            else:
                clean_parts.append(clean_part)
        return " ".join(clean_parts)
    return sanitize_log_line(str(cmd))
