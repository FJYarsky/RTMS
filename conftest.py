# ==============================================================================
# RTMS v2.0.3 — Configuración de pytest
# ==============================================================================

import sys
import os

# Asegurar que el directorio raíz del proyecto esté siempre en sys.path durante los tests
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)
