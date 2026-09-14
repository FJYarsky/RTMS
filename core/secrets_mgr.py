# ==============================================================================
# RTMS — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com
# ==============================================================================

import sys
import base64
import logging

logger = logging.getLogger("rtms.secrets_mgr")

# Definición de estructuras para Windows DPAPI si estamos en win32
_HAS_DPAPI = False
if sys.platform == "win32":
    try:
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ('cbData', ctypes.wintypes.DWORD),
                ('pbData', ctypes.POINTER(ctypes.c_byte))
            ]

        _HAS_DPAPI = True
    except Exception as e:
        logger.warning(f"No se pudo inicializar ctypes para DPAPI: {e}")

def protect_secret(plaintext: str) -> str:
    """
    Cifra una credencial o frase de paso usando Windows DPAPI (atada al usuario de Windows).
    Si DPAPI no está disponible (ej. entornos no Windows), retorna el valor con prefijo de texto.
    """
    if not plaintext:
        return ""

    # Si ya está protegido, no volver a cifrar
    if plaintext.startswith("dpapi:"):
        return plaintext

    if _HAS_DPAPI:
        try:
            data = plaintext.encode('utf-8')
            in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
            out_blob = DATA_BLOB()
            if ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                'rtms_passphrase',
                None, None, None, 0,
                ctypes.byref(out_blob)
            ):
                res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                return "dpapi:" + base64.b64encode(res).decode('utf-8')
        except Exception as exc:
            logger.debug(f"Fallo al proteger secreto con DPAPI: {exc}")

    # Fallback seguro para desarrollo o plataformas sin DPAPI
    return plaintext

def unprotect_secret(ciphertext: str) -> str:
    """
    Descifra un secreto previamente protegido con Windows DPAPI.
    Si no está cifrado con DPAPI, lo devuelve tal cual para compatibilidad retroactiva.
    """
    if not ciphertext:
        return ""

    if ciphertext.startswith("dpapi:") and _HAS_DPAPI:
        try:
            raw = base64.b64decode(ciphertext[6:])
            in_blob = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_byte)))
            out_blob = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None, None, None, None, 0,
                ctypes.byref(out_blob)
            ):
                res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                return res.decode('utf-8')
        except Exception as exc:
            logger.error(f"Fallo al descifrar secreto DPAPI: {exc}")
            return ""

    return ciphertext
