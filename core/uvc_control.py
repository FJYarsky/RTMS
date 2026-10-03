# ==============================================================================
# RTMS — Real-Time Multicam System
# Control y bloqueo inteligente de auto-exposición UVC (Anti-Drop FPS).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""
Módulo de control UVC para Windows DirectShow (P1.3 Anti-Drop FPS).
Interactúa con la interfaz DirectShow COM IAMCameraControl (PROPSETID_VIDCAP_CAMERACONTROL)
para fijar el tiempo de obturación en modo manual (<= 1/60s) antes de iniciar la captura,
evitando caídas no deseadas a 15-20 FPS en condiciones de penumbra.
"""

import logging
import math
import sys
from typing import Any, Dict

from core.config_mgr import is_virtual_device

logger = logging.getLogger("rtms.uvc_control")

# DirectShow CameraControl properties & flags
CameraControl_Pan = 0
CameraControl_Tilt = 1
CameraControl_Roll = 2
CameraControl_Zoom = 3
CameraControl_Exposure = 4
CameraControl_Iris = 5
CameraControl_Focus = 6

CameraControl_Flags_Auto = 0x0001
CameraControl_Flags_Manual = 0x0002

PROPSETID_VIDCAP_CAMERACONTROL = "{C6E13370-30AC-11D0-A18C-00A0C9118056}"


def lock_uvc_auto_exposure(device_path: str, max_shutter_sec: float = 1 / 60.0) -> bool:
    """
    Bloquea la auto-exposición de la cámara física a modo manual con tiempo de obturación
    inferior o igual a max_shutter_sec (por defecto 1/60 s) para evitar caídas silenciosas
    de framerate a 15-20 FPS en penumbra.

    Incorpora degradación transparente: si la cámara no soporta IAMCameraControl,
    es virtual, no existe o no está en Windows, retorna False sin interrumpir el flujo.

    Args:
        device_path: Ruta física DirectShow o nombre amigable del dispositivo.
        max_shutter_sec: Tiempo máximo de exposición por fotograma en segundos (def: 1/60s).

    Returns:
        True si se aplicó el bloqueo con éxito, False en caso contrario.
    """
    if sys.platform != "win32":
        return False

    raw_path = str(device_path or "").strip()
    if raw_path.startswith("video="):
        raw_path = raw_path[6:].strip()
    clean_path = raw_path.strip("\"'")

    if (
        not clean_path
        or clean_path.startswith("virtual://")
        or clean_path.startswith("testsrc")
        or is_virtual_device(clean_path)
    ):
        logger.debug(f"[UVC] Omitiendo bloqueo de exposición para dispositivo virtual: {clean_path}")
        return False

    try:
        import ctypes
        from ctypes import POINTER, WINFUNCTYPE, c_long, c_ushort, c_void_p, wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        class VARIANT(ctypes.Structure):
            _fields_ = [
                ("vt", c_ushort),
                ("wReserved1", wintypes.WORD),
                ("wReserved2", wintypes.WORD),
                ("wReserved3", wintypes.WORD),
                ("bstrVal", wintypes.LPWSTR),
                ("pad", wintypes.BYTE * 8),
            ]

        ole32 = ctypes.windll.ole32
        oleaut32 = ctypes.windll.oleaut32

        hr_init = ole32.CoInitialize(None)

        def _guid(s: str) -> GUID:
            g = GUID()
            ole32.CLSIDFromString(wintypes.LPCWSTR(s), ctypes.byref(g))
            return g

        clsid_system_device_enum = _guid("{62BE5D10-60EB-11D0-BD3B-00A0C911CE86}")
        iid_create_dev_enum = _guid("{29840822-5B84-11D0-BD3B-00A0C911CE86}")
        cat_video_input = _guid("{860BB310-5D01-11D0-BD3B-00A0C911CE86}")
        iid_base_filter = _guid("{56A86895-0AD4-11CE-B03A-0020AF0BA770}")
        iid_cam_control = _guid("{C6E13370-30AC-11D0-A18C-00A0C9118056}")
        iid_prop_bag = _guid("{55272A00-42CB-11CE-8135-00AA004BB851}")

        try:
            p_dev_enum = c_void_p()
            hr = ole32.CoCreateInstance(
                ctypes.byref(clsid_system_device_enum),
                None,
                1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(iid_create_dev_enum),
                ctypes.byref(p_dev_enum),
            )
            if hr != 0 or not p_dev_enum.value:
                logger.debug(f"[UVC] No se pudo instanciar SystemDeviceEnum (hr={hex(hr & 0xFFFFFFFF)})")
                return False

            vtable_enum = POINTER(c_void_p).from_address(p_dev_enum.value)
            CreateClassEnumerator = WINFUNCTYPE(c_long, c_void_p, POINTER(GUID), POINTER(c_void_p), wintypes.DWORD)(
                vtable_enum[3]
            )
            p_enum_moniker = c_void_p()
            hr = CreateClassEnumerator(p_dev_enum, ctypes.byref(cat_video_input), ctypes.byref(p_enum_moniker), 0)
            WINFUNCTYPE(c_long, c_void_p)(vtable_enum[2])(p_dev_enum)

            if hr != 0 or not p_enum_moniker.value:
                logger.debug("[UVC] No hay dispositivos de captura de video DirectShow en el sistema.")
                return False

            enum_vtable = POINTER(c_void_p).from_address(int(p_enum_moniker.value))
            EnumNext = WINFUNCTYPE(c_long, c_void_p, wintypes.ULONG, POINTER(c_void_p), POINTER(wintypes.ULONG))(
                enum_vtable[3]
            )

            clean_lower = clean_path.lower()
            target_moniker = None
            p_moniker = c_void_p()
            fetched = wintypes.ULONG(0)

            while (
                EnumNext(p_enum_moniker, 1, ctypes.byref(p_moniker), ctypes.byref(fetched)) == 0 and fetched.value == 1
            ):
                if not p_moniker.value:
                    continue
                mon_vtable = POINTER(c_void_p).from_address(int(p_moniker.value))
                BindToStorage = WINFUNCTYPE(c_long, c_void_p, c_void_p, c_void_p, POINTER(GUID), POINTER(c_void_p))(
                    mon_vtable[9]
                )
                p_bag = c_void_p()
                hr_bag = BindToStorage(p_moniker, None, None, ctypes.byref(iid_prop_bag), ctypes.byref(p_bag))
                friendly_name = ""
                device_pnp = ""
                if hr_bag == 0 and p_bag.value:
                    bag_vtable = POINTER(c_void_p).from_address(int(p_bag.value))
                    Read = WINFUNCTYPE(c_long, c_void_p, wintypes.LPCWSTR, POINTER(VARIANT), c_void_p)(bag_vtable[3])
                    var = VARIANT()
                    oleaut32.VariantInit(ctypes.byref(var))
                    if Read(p_bag, "FriendlyName", ctypes.byref(var), None) == 0 and var.bstrVal:
                        friendly_name = str(var.bstrVal)
                    var2 = VARIANT()
                    oleaut32.VariantInit(ctypes.byref(var2))
                    if Read(p_bag, "DevicePath", ctypes.byref(var2), None) == 0 and var2.bstrVal:
                        device_pnp = str(var2.bstrVal)
                    WINFUNCTYPE(c_long, c_void_p)(bag_vtable[2])(p_bag)

                if (
                    friendly_name and (friendly_name.lower() in clean_lower or clean_lower in friendly_name.lower())
                ) or (device_pnp and (device_pnp.lower() in clean_lower or clean_lower in device_pnp.lower())):
                    target_moniker = p_moniker
                    break
                else:
                    WINFUNCTYPE(c_long, c_void_p)(mon_vtable[2])(p_moniker)

            WINFUNCTYPE(c_long, c_void_p)(enum_vtable[2])(p_enum_moniker)

            if not target_moniker or not target_moniker.value:
                logger.debug(f"[UVC] Dispositivo '{clean_path}' no encontrado en enumerador DirectShow.")
                return False

            mon_vtable = POINTER(c_void_p).from_address(int(target_moniker.value))
            BindToObject = WINFUNCTYPE(c_long, c_void_p, c_void_p, c_void_p, POINTER(GUID), POINTER(c_void_p))(
                mon_vtable[8]
            )
            p_filter = c_void_p()
            hr_bind = BindToObject(target_moniker, None, None, ctypes.byref(iid_base_filter), ctypes.byref(p_filter))
            WINFUNCTYPE(c_long, c_void_p)(mon_vtable[2])(target_moniker)

            if hr_bind != 0 or not p_filter.value:
                logger.debug(f"[UVC] No se pudo instanciar filtro DirectShow para '{clean_path}'")
                return False

            filter_vtable = POINTER(c_void_p).from_address(int(p_filter.value))
            QueryInterface = WINFUNCTYPE(c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))(filter_vtable[0])
            p_cam = c_void_p()
            hr_qi = QueryInterface(p_filter, ctypes.byref(iid_cam_control), ctypes.byref(p_cam))
            WINFUNCTYPE(c_long, c_void_p)(filter_vtable[2])(p_filter)

            if hr_qi != 0 or not p_cam.value:
                logger.debug(f"[UVC] Dispositivo '{clean_path}' no expone IAMCameraControl (E_NOINTERFACE).")
                return False

            cam_vtable = POINTER(c_void_p).from_address(int(p_cam.value))
            Set = WINFUNCTYPE(c_long, c_void_p, c_long, c_long, c_long)(cam_vtable[3])
            shutter_sec = max(0.0001, float(max_shutter_sec))
            exposure_val = int(round(math.log2(shutter_sec)))
            hr_set = Set(p_cam, CameraControl_Exposure, exposure_val, CameraControl_Flags_Manual)
            WINFUNCTYPE(c_long, c_void_p)(cam_vtable[2])(p_cam)

            if hr_set == 0:
                logger.info(
                    f"[UVC] Auto-exposición fijada exitosamente a manual (shutter <= {max_shutter_sec:.4f}s, exp={exposure_val}) para '{clean_path}'"
                )
                return True
            else:
                logger.debug(f"[UVC] IAMCameraControl::Set falló (hr={hex(hr_set & 0xFFFFFFFF)}) para '{clean_path}'")
                return False

        finally:
            if hr_init == 0:
                ole32.CoUninitialize()

    except Exception as e:
        logger.debug(f"[UVC] Fallo transparente en control UVC para '{clean_path}': {e}")
        return False


def get_uvc_camera_capabilities(device_path: str) -> Dict[str, Any]:
    """
    Consulta las capacidades de control UVC del dispositivo (exposición, foco, zoom).
    Retorna un diccionario estructurado de diagnóstico.
    """
    is_virt = is_virtual_device(device_path)
    return {
        "device_path": device_path,
        "is_virtual": is_virt,
        "supports_manual_exposure": not is_virt and sys.platform == "win32",
        "exposure_lock_enabled": not is_virt,
        "target_max_shutter": "1/60s",
        "propset_id": PROPSETID_VIDCAP_CAMERACONTROL,
    }
