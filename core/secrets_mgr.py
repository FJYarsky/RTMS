# ==============================================================================
# RTMS v2.2.2 — Real-Time Multicam System
# Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
# ==============================================================================

import sys
import os
import base64
import logging

logger = logging.getLogger("rtms.secrets_mgr")

class SecretEncryptionError(RuntimeError):
    """Excepción de seguridad levantada cuando el cifrado DPAPI falla y se rechaza el guardado en texto plano."""
    pass

class SecretDecryptionError(RuntimeError):
    """Excepción levantada cuando un secreto cifrado no puede recuperarse."""
    pass

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

def protect_secret(plaintext: str, require_secure: bool = True) -> str:
    """
    Cifra una credencial o frase de paso usando Windows DPAPI (atada al usuario de Windows).
    En entornos Windows de producción, si DPAPI falla, se levanta SecretEncryptionError
    para impedir que se persistan secretos en texto plano (P0-01).
    """
    if not plaintext:
        return ""

    # Si ya está protegido, no volver a cifrar
    if plaintext.startswith("dpapi:"):
        return plaintext

    if sys.platform == "win32":
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
                logger.error(f"Fallo al proteger secreto con DPAPI: {exc}")

        # Política de seguridad estricta en Windows
        is_dev = os.getenv("RTMS_DEV_MODE") == "1"
        if not require_secure or is_dev:
            logger.warning("DPAPI falló o no disponible. Permitiendo texto plano solo por flag de desarrollo/test.")
            return plaintext
        raise SecretEncryptionError("Fallo crítico de DPAPI al proteger credencial. Guardado en texto plano rechazado por seguridad.")

    # Entornos no Windows (CI / Testing multiplataforma)
    return plaintext

def unprotect_secret(ciphertext: str, raise_on_error: bool = False) -> str:
    """
    Descifra un secreto previamente protegido con Windows DPAPI.
    Si no está cifrado con DPAPI, lo devuelve tal cual para compatibilidad retroactiva.
    Si falla el descifrado en Windows (ej. cambio de usuario o corrupción), NUNCA devuelve
    el texto cifrado (P0-03 / Claude N1). Devuelve "" o levanta SecretDecryptionError.
    """
    if not ciphertext:
        return ""

    if ciphertext.startswith("dpapi:"):
        if _HAS_DPAPI:
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

                # CryptUnprotectData retornó 0 / FALSE
                logger.warning(
                    "CryptUnprotectData retornó FALSE: la credencial DPAPI no pudo descifrarse "
                    "(pertenece a otra cuenta de Windows o el blob está corrupto)."
                )
                if raise_on_error:
                    raise SecretDecryptionError("Fallo al descifrar secreto DPAPI: CryptUnprotectData retornó FALSE.")
                return ""
            except SecretDecryptionError:
                raise
            except Exception as exc:
                logger.warning(
                    f"Fallo al descifrar secreto DPAPI: la credencial fue cifrada con otra cuenta de usuario de Windows o está dañada: {exc}"
                )
                if raise_on_error:
                    raise SecretDecryptionError(f"Fallo de descifrado DPAPI: {exc}") from exc
                return ""
        else:
            logger.warning("No se puede descifrar secreto DPAPI en un entorno sin soporte DPAPI activo.")
            if raise_on_error:
                raise SecretDecryptionError("Entorno sin soporte DPAPI activo.")
            return ""

    return ciphertext
