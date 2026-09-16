# ==============================================================================
# RTMS — Real-Time Multicam System
# Tests de protección y desprotección criptográfica de credenciales mediante Windows DPAPI
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

import sys
import pytest
from core.secrets_mgr import (
    protect_secret,
    unprotect_secret,
    SecretEncryptionError,
    _HAS_DPAPI
)

def test_protect_and_unprotect_empty_or_none():
    """Valida que cadenas vacías o None no intenten cifrarse ni descifrarse."""
    assert protect_secret("") == ""
    assert unprotect_secret("") == ""

def test_protect_secret_idempotency():
    """Valida que un secreto ya protegido con prefijo 'dpapi:' no se vuelva a cifrar."""
    already_protected = "dpapi:AQAAANCMnd8BFdERjHoAwE/Cl+sBAAA..."
    assert protect_secret(already_protected) == already_protected

def test_unprotect_plaintext_backward_compatibility():
    """Valida que cadenas sin prefijo 'dpapi:' se retornen intactas."""
    plaintext = "mi_clave_sin_cifrar_123"
    assert unprotect_secret(plaintext) == plaintext

def test_protect_and_unprotect_roundtrip():
    """Valida el ciclo completo de cifrado y descifrado de credenciales."""
    secret = "PassphraseUltraSegura2026!#"
    ciphertext = protect_secret(secret)

    if sys.platform == "win32" and _HAS_DPAPI:
        assert ciphertext.startswith("dpapi:")
        assert ciphertext != secret
        decrypted = unprotect_secret(ciphertext)
        assert decrypted == secret
    else:
        # En entornos sin DPAPI (ej. CI Linux), se preserva el texto plano
        assert ciphertext == secret
        assert unprotect_secret(ciphertext) == secret

def test_unprotect_corrupted_dpapi_string():
    """Valida que un payload DPAPI inválido o corrupto no produzca crash y retorne cadena vacía."""
    corrupted = "dpapi:este_no_es_un_blob_valido_base64@@@!!!"
    res = unprotect_secret(corrupted)
    assert res == ""

def test_strict_security_policy_rejection(monkeypatch):
    """Valida que en Windows sin flag de dev se levante SecretEncryptionError si DPAPI falla."""
    if sys.platform == "win32":
        monkeypatch.setattr("core.secrets_mgr._HAS_DPAPI", False)
        monkeypatch.delenv("RTMS_DEV_MODE", raising=False)
        with pytest.raises(SecretEncryptionError):
            protect_secret("mi_clave_secreta", require_secure=True)
