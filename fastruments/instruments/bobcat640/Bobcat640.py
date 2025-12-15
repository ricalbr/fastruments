"""
Bobcat 640 (GigE) helper — direct Ethernet link capable.
- Auto-discovers via GenICam (Harvester) if available.
- If the camera shows up with a link-local/missing IP, force a static IP (persistent) and reopen.
- Opens and grabs via Xeneth SDK; setters (exposure/fps) via GenICam when available.

Usage (direct link, no DHCP):
    cam = Bobcat640(auto_discover=True,
                    desired_ip="192.168.0.2",
                    desired_mask="255.255.255.0",
                    desired_gw="0.0.0.0")
    cam.start()
    frame16 = cam.snap()
    cam.set_exposure(0.004)
    cam.set_framerate(50.0)
    cam.stop(); cam.close()
"""

import ctypes as C
import ipaddress
import os
import sys
import time
from ctypes import c_uint, c_ushort
from typing import Optional, Tuple

import numpy as np


class Bobcat640:
    # ---------------- Xeneth ctypes glue ----------------
    def _load_xeneth(self):
        # Try common Windows & Linux locations/names.
        candidates = []
        if os.name == "nt":
            candidates = [r"C:\Program Files\Common Files\XenICs\Runtime\xeneth64.dll"]
            loader = C.WinDLL
        else:
            candidates = [
                "/opt/Xeneth/lib/libXeneth.so",
                "/usr/lib/libXeneth.so",
                "libXeneth.so",
            ]
            loader = C.CDLL
        last = None
        for p in candidates:
            try:
                return loader(p)
            except OSError as e:
                last = e
                print(e)
        raise OSError(
            "Could not load Xeneth runtime. Install Xeneth SDK or add it to PATH/LD_LIBRARY_PATH."
        ) from last

    def _bind_minimal_prototypes(self):

        x = self.xeneth
        XCHANDLE = C.c_void_p
        UINT = c_uint
        USHORT = c_ushort
        PVOID = C.c_void_p

        x.XC_OpenCamera.restype = XCHANDLE

        # Prefer URL open; some older SDKs expose index-only.
        try:
            x.XC_OpenCamera.argtypes = [C.c_char_p, PVOID, PVOID]
            self._open_by_url = True
        except Exception:
            x.XC_OpenCamera.argtypes = [UINT]
            self._open_by_url = False

        x.XC_CloseCamera.argtypes = [XCHANDLE]
        x.XC_CloseCamera.restype = UINT
        x.XC_StartCapture.argtypes = [XCHANDLE]
        x.XC_StartCapture.restype = UINT
        x.XC_StopCapture.argtypes = [XCHANDLE]
        x.XC_StopCapture.restype = UINT
        x.XC_GetWidth.argtypes = [XCHANDLE]
        x.XC_GetWidth.restype = UINT
        x.XC_GetHeight.argtypes = [XCHANDLE]
        x.XC_GetHeight.restype = UINT
        x.XC_GetFrameSize.argtypes = [XCHANDLE]
        x.XC_GetFrameSize.restype = UINT
        x.XC_GetFrame.argtypes = [XCHANDLE, C.POINTER(USHORT), UINT]
        x.XC_GetFrame.restype = UINT

    # ---------------- GenICam / Harvester ----------------
    def _maybe_init_harvester(self):
        if self.h is not None:
            return
        try:
            from harvesters.core import Harvester
        except Exception:
            return
        self.h = Harvester()

        # Try to auto-load CTIs from GENICAM_GENTL64_PATH / GENICAM_GENTL32_PATH
        for env_key in ("GENICAM_GENTL64_PATH", "GENICAM_GENTL32_PATH"):
            path = os.environ.get(env_key)
            if not path:
                continue
            sep = ";" if os.name == "nt" else ":"
            for base in filter(None, path.split(sep)):
                try:
                    self.h.add_cti_file(
                        base
                    )  # Harvester will recurse and load .cti files inside
                except Exception:
                    pass

        # If none found, you can still add self.add_cti(...) from your app before calling discover()
        try:
            self.h.update()
        except Exception:
            self.h = None

    def add_cti(self, path: str):
        """Optionally add a GenTL .cti file and refresh discovery."""
        if self.h is None:
            from harvesters.core import Harvester

            self.h = Harvester()
        self.h.add_cti_file(path)
        self.h.update()

    @staticmethod
    def _is_link_local(ip: str) -> bool:
        try:
            return ipaddress.ip_address(ip).is_link_local
        except Exception:
            return False

    def _discover_device_info(self):
        """Return (info, ip) for the best Xenics/Bobcat GEV device, or (None, None)."""
        self._maybe_init_harvester()
        if self.h is None:
            return None, None

        def score(di):
            s = 0
            v = (getattr(di, "vendor", "") or "").lower()
            m = (getattr(di, "model", "") or "").lower()
            if "xenics" in v:
                s += 2
            if "bobcat" in m:
                s += 2
            if getattr(di, "tl_type", "") and di.tl_type.upper() == "GEV":
                s += 1
            return s

        items = sorted(self.h.device_info_list, key=score, reverse=True)
        for di in items:
            if getattr(di, "tl_type", "") and di.tl_type.upper() != "GEV":
                continue
            ip = getattr(di, "ipv4", None) or getattr(di, "info_dict", {}).get(
                "ip_address"
            )
            return di, ip
        return None, None

    def _force_persistent_ip(self, di, ip: str, mask: str, gw: str) -> str:
        """
        Open the device via Harvester, set persistent IP, and reboot (if DeviceReset exists).
        Returns the IP that should be used afterward.
        """
        ia = None
        try:
            ia = self.h.create_image_acquirer(di)
            nm = ia.remote_device.node_map
            # Enable persistent config if present
            for name in (
                "GevCurrentIPConfigurationPersistent",
                "GevCurrentIPConfigurationLLA",
                "GevCurrentIPConfigurationDHCP",
            ):
                try:
                    n = getattr(nm, name)
                    if name.endswith("Persistent"):
                        n.value = True
                    if name.endswith("LLA") or name.endswith("DHCP"):
                        n.value = False
                except Exception:
                    pass
            # Set persistent values
            for node, val in (
                ("GevPersistentIPAddress", ip),
                ("GevPersistentSubnetMask", mask),
                ("GevPersistentDefaultGateway", gw),
            ):
                try:
                    n = getattr(nm, node)
                    # GenICam expects integer-encoded IPv4 sometimes; try both str and int.
                    try:
                        n.value = val
                    except Exception:
                        n.value = int(ipaddress.IPv4Address(val))
                except Exception:
                    pass
            # Apply via reset if available
            try:
                nm.DeviceReset.execute()
            except Exception:
                pass
        finally:
            if ia:
                ia.destroy()

        # Give the device time to reboot and re-announce
        time.sleep(2.0)
        try:
            self.h.update()
        except Exception:
            pass
        return ip

    def discover(
        self,
        prefer_model: str = "Bobcat",
        prefer_vendor: str = "Xenics",
        desired_ip: str = "192.168.0.2",
        desired_mask: str = "255.255.255.0",
        desired_gw: str = "0.0.0.0",
    ) -> Optional[str]:
        """
        Find a Xenics/Bobcat GigE camera. If its IP is link-local/missing,
        set a persistent static IP so we can open it directly via Xeneth.
        """
        di, ip = self._discover_device_info()
        if di is None:
            return None
        # If the device already has a proper IPv4, just use it.
        if ip and not self._is_link_local(ip):
            return f"gev://{ip}"
        # Try to force a persistent IPv4 suitable for a direct link.
        try:
            new_ip = self._force_persistent_ip(di, desired_ip, desired_mask, desired_gw)
            return f"gev://{new_ip}"
        except Exception:
            # If forcing IP failed, fall back to whatever we have (may still work on LLA)
            return f"gev://{ip or desired_ip}"

    # ---------------- Lifecycle ----------------
    def __init__(
        self,
        url: Optional[str] = None,
        auto_discover: bool = True,
        desired_ip: str = "192.168.0.2",
        desired_mask: str = "255.255.255.0",
        desired_gw: str = "0.0.0.0",
    ):
        self.xeneth = self._load_xeneth()
        self._bind_minimal_prototypes()
        self.h = None
        self.cam = None
        self._w = None
        self._h = None
        self._nbytes = None
        self._url = None

        if url is None and auto_discover:
            url = self.discover(
                desired_ip=desired_ip, desired_mask=desired_mask, desired_gw=desired_gw
            )
        if url is None:
            raise RuntimeError(
                "No camera URL provided and auto-discovery unavailable.\n"
                "Pass url='gev://<camera-ip>' or install 'harvesters' + a GenTL .cti to enable discovery."
            )
        self.open(url)

    def open(self, url: str):
        assert url.startswith("gev://"), "Use a GigE Vision URL like gev://<ip>"
        self._url = url
        if self._open_by_url:
            self.cam = self.xeneth.XC_OpenCamera(url.encode("ascii"), None, None)
        else:
            self.cam = self.xeneth.XC_OpenCamera(0)
        if not self.cam:
            raise RuntimeError(f"XC_OpenCamera failed for {url}")
        self._w = int(self.xeneth.XC_GetWidth(self.cam))
        self._h = int(self.xeneth.XC_GetHeight(self.cam))
        # self._nbytes = int(self.xeneth.XC_GetFrameSize(self.cam))

    def start(self):
        err = self.xeneth.XC_StartCapture(self.cam)
        if err != 0:
            raise RuntimeError(f"XC_StartCapture failed (code {err})")

    def stop(self):
        try:
            self.xeneth.XC_StopCapture(self.cam)
        except Exception:
            pass

    def close(self):
        if self.cam:
            self.stop()
            self.xeneth.XC_CloseCamera(self.cam)
            self.cam = None
        if self.h:
            try:
                self.h.reset()
            except Exception:
                pass
            self.h = None

    # ---------------- Data I/O ----------------
    @property
    def size(self) -> Tuple[int, int]:
        return self._w, self._h

    def snap(self) -> np.ndarray:
        """Copy the latest frame from Xeneth buffer into a NumPy uint16 array."""
        frame16 = np.empty((self._h, self._w), dtype=np.uint16)
        err = self.xeneth.XC_GetFrame(
            self.cam, frame16.ctypes.data_as(C.POINTER(c_ushort)), 0
        )
        if err != 0:
            raise RuntimeError(f"XC_CopyFrameBuffer failed (code {err})")
        return frame16

    # ---------------- Setters (via GenICam) ----------------
    def _need_harvester_device(self):
        self._maybe_init_harvester()
        if self.h is None:
            raise RuntimeError(
                "GenICam setters require 'harvesters' + a GenTL Producer (.cti). "
                "Install them or set properties with Xeneth-specific APIs."
            )
        self.h.update()
        target_ip = None
        try:
            target_ip = self._url.split("://", 1)[1]
        except Exception:
            pass
        for di in self.h.device_info_list:
            if getattr(di, "tl_type", "") and di.tl_type.upper() == "GEV":
                ip = getattr(di, "ipv4", None) or getattr(di, "info_dict", {}).get(
                    "ip_address"
                )
                if (not target_ip) or (ip == target_ip):
                    return self.h.create_image_acquirer(di)
        # Fallback to first GEV
        for di in self.h.device_info_list:
            if getattr(di, "tl_type", "") and di.tl_type.upper() == "GEV":
                return self.h.create_image_acquirer(di)
        raise RuntimeError("No GigE Vision device visible to Harvester.")

    def set_exposure(self, seconds: float):
        ia = self._need_harvester_device()
        try:
            try:
                ia.remote_device.node_map.ExposureAuto.value = "Off"
            except Exception:
                pass
            usec = max(1.0, seconds * 1e6)
            for name in ("ExposureTime", "ExposureTimeAbs"):
                try:
                    n = getattr(ia.remote_device.node_map, name)
                    n.value = float(min(max(usec, n.min), n.max))
                    ia.destroy()
                    return
                except Exception:
                    continue
            ia.destroy()
            raise RuntimeError("Could not set exposure: GenICam node not found.")
        except Exception:
            try:
                ia.destroy()
            except Exception:
                pass
            raise

    def set_framerate(self, fps: float):
        ia = self._need_harvester_device()
        try:
            try:
                ia.remote_device.node_map.AcquisitionFrameRateEnable.value = True
            except Exception:
                pass
            n = ia.remote_device.node_map.AcquisitionFrameRate
            n.value = float(min(max(fps, n.min), n.max))
            ia.destroy()
        except Exception:
            try:
                ia.destroy()
            except Exception:
                pass
            raise


# end class
