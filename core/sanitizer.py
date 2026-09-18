# ==============================================================================
# RTMS — Real-Time Multicam System
# Sanitización y protección de datos confidenciales en registros y comandos.
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import re
import logging
import urllib.parse
from typing import List, Union

logger = logging.getLogger("rtms.sanitizer")

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

_SENSITIVE_PARAM_KEYS = {"passphrase", "password", "secret", "token", "key", "auth"}

def sanitize_url(url: str) -> str:
    """
    Sanitiza una URL enmascarando cualquier credencial presente en los query parameters
    (passphrase, token, password, secret) o en la sección userinfo (user:pass@host).
    """
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(url)
        # 1. Enmascarar userinfo en netloc si existe
        netloc = parsed.netloc
        if "@" in netloc:
            user_part, host_part = netloc.split("@", 1)
            if ":" in user_part:
                u, _ = user_part.split(":", 1)
                netloc = f"{u}:********@{host_part}"
            else:
                netloc = f"********@{host_part}"

        # 2. Enmascarar query params sensibles
        if parsed.query:
            query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            sanitized_pairs = []
            for k, v in query_pairs:
                if k.lower() in _SENSITIVE_PARAM_KEYS and v:
                    sanitized_pairs.append((k, "********"))
                else:
                    sanitized_pairs.append((k, v))
            new_query = urllib.parse.urlencode(sanitized_pairs)
        else:
            new_query = ""

        reconstructed = urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, new_query, parsed.fragment))
        return sanitize_log_line(reconstructed)
    except Exception:
        return sanitize_log_line(url)

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
            clean_part = sanitize_url(str(part))
            if " " in clean_part and not (clean_part.startswith('"') and clean_part.endswith('"')):
                clean_parts.append(f'"{clean_part}"')
            else:
                clean_parts.append(clean_part)
        return " ".join(clean_parts)
    return sanitize_url(str(cmd))

class SecretFilter(logging.Filter):
    """
    Filtro de logging global para interceptar todo LogRecord emitido hacia los handlers
    y asegurar que ninguna contraseña, token o credencial se escriba en consola ni en archivo.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                record.msg = sanitize_log_line(record.getMessage())
                record.args = ()
            elif isinstance(record.msg, str):
                record.msg = sanitize_log_line(record.msg)
        except Exception:
            pass
        return True
