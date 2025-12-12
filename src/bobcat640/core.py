#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 13 16:12:30 2025

@author: Francesco Ceccarelli

This module provides a high-level Python interface for controlling the
Xenics Bobcat640 GigE Vision infrared camera. It interfaces with the
Xeneth SDK for image acquisition and optionally integrates with the
GenICam Harvester library for automatic discovery and parameter control.

The `Bobcat640` class enables connection management, image capture, and
configuration of camera parameters such as exposure time and frame rate.
It is designed for laboratory automation and optical characterization
setups where fast, programmable infrared imaging is required.
"""

import ctypes as C
from ctypes import c_uint, c_ushort
import numpy as np
from typing import Optional, Tuple
import time
import ipaddress
import os


class Bobcat640:
    """
    Bobcat640 (GigE) Interface
    ==========================

    This module provides a high-level Python interface for controlling the
    Xenics Bobcat640 GigE Vision infrared camera. It interfaces with the
    Xeneth SDK for image acquisition and optionally integrates with the
    GenICam Harvester library for automatic discovery and parameter control.

    The `Bobcat640` class enables connection management, image capture, and
    configuration of camera parameters such as exposure time and frame rate.
    It is designed for laboratory automation and optical characterization
    setups where fast, programmable infrared imaging is required.

    Parameters
    ----------
    url : str | None
        Camera URL (e.g. "gev://192.168.0.2"). If None, auto-discovery is used.
    auto_discover : bool
        If True, attempts device discovery using Harvester.
    desired_ip : str
        Static IP address assigned when configuring persistent networking.
    desired_mask : str
        Subnet mask for persistent IP configuration.
    desired_gw : str
        Gateway address for persistent IP configuration.
    verbose : bool
        If True, prints additional diagnostic messages.

    Attributes
    ----------
    xeneth : ctypes.CDLL
        Loaded Xeneth runtime library.
    h : harvesters.core.Harvester | None
        Harvester instance, if initialized.
    cam : ctypes.c_void_p
        Handle to the open camera.
    _w, _h : int
        Frame width and height.
    _nbytes : int
        Frame size in bytes.
    _url : str
        Camera URL.

    Examples
    --------
    >>> from lib.instruments.bobcat640.core import Bobcat640
    >>> cam = Bobcat640(auto_discover=True,
    ...                 desired_ip="192.168.0.2",
    ...                 desired_mask="255.255.255.0",
    ...                 desired_gw="0.0.0.0",
    ...                 verbose=True)
    >>> cam.start()
    >>> frame16 = cam.snap()
    >>> cam.set_exposure(0.004)
    >>> cam.set_framerate(50.0)
    >>> cam.stop()
    >>> cam.close()

    Notes
    -----
    - Requires the Xeneth SDK installed and available in PATH or LD_LIBRARY_PATH.
    - GenICam features require a valid GenTL Producer (.cti) and the 'harvesters' package.
    """

    def __init__(self,
                 url: Optional[str] = None,
                 auto_discover: bool = True,
                 desired_ip: str = "192.168.0.2",
                 desired_mask: str = "255.255.255.0",
                 desired_gw: str = "0.0.0.0",
                 verbose: bool = True):
        """
        Initialize the Bobcat640 helper.

        Parameters
        ----------
        url : str | None
            If provided, the camera will be opened directly (format "gev://<ip>").
        auto_discover : bool
            If True and url is None, will attempt discovery using Harvester.
        desired_ip, desired_mask, desired_gw : str
            Network parameters to set in case a static IP needs to be forced.
        verbose : bool
            If True, enables debug prints.
        """
        self.verbose = verbose
        print("[BOBCAT640] Initializing Bobcat640 camera interface...")

        # Load Xeneth SDK
        self.xeneth = self._load_xeneth()
        self._bind_minimal_prototypes()

        # Harvester handle
        self.h = None
        # Camera handle and metadata
        self.cam = None
        self._w = None
        self._h = None
        self._nbytes = None
        self._url = None

        if url is None and auto_discover:
            url = self.discover(desired_ip=desired_ip,
                                desired_mask=desired_mask,
                                desired_gw=desired_gw)
            if self.verbose:
                print(f"[BOBCAT640] Discovered URL: {url}")

        if url is None:
            raise RuntimeError(
                "No camera URL provided and auto-discovery unavailable.\n"
                "Pass url='gev://<camera-ip>' or install 'harvesters' + a GenTL .cti to enable discovery."
            )

        self.open(url)
        print("[BOBCAT640] Initialization complete.")

    # ----------------------------------------------------------------------
    # Xeneth library loading and binding
    # ----------------------------------------------------------------------

    def _load_xeneth(self):
        """
        Attempt to load the Xeneth runtime shared library (DLL/SO).
        """
        if self.verbose:
            print("[BOBCAT640] Loading Xeneth runtime...")

        candidates = []
        if os.name == "nt":
            candidates = [
                r"C:\\Program Files\\Common Files\\XenICs\\Runtime\\xeneth64.dll"
            ]
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
                lib = loader(p)
                print(f"[BOBCAT640] Loaded Xeneth from {p}")
                return lib
            except OSError as e:
                if self.verbose:
                    print(f"[BOBCAT640] Failed to load {p}: {e}")
                last = e

        raise OSError("Could not load Xeneth runtime. Install Xeneth SDK or add it to PATH/LD_LIBRARY_PATH.") from last

    def _bind_minimal_prototypes(self):
        """
        Bind minimal set of Xeneth functions.
        """
        if self.verbose:
            print("[BOBCAT640] Binding Xeneth function prototypes...")

        x = self.xeneth
        XCHANDLE = C.c_void_p
        UINT = c_uint
        USHORT = c_ushort
        PVOID = C.c_void_p

        # Return types and argument definitions
        x.XC_OpenCamera.restype = XCHANDLE
        try:
            x.XC_OpenCamera.argtypes = [C.c_char_p, PVOID, PVOID]
            self._open_by_url = True
            if self.verbose:
                print("[BOBCAT640] XC_OpenCamera(url) interface detected.")
        except Exception:
            x.XC_OpenCamera.argtypes = [UINT]
            self._open_by_url = False
            if self.verbose:
                print("[BOBCAT640] XC_OpenCamera(index) interface detected.")

        x.XC_CloseCamera.argtypes = [XCHANDLE];              x.XC_CloseCamera.restype  = UINT
        x.XC_StartCapture.argtypes = [XCHANDLE];             x.XC_StartCapture.restype = UINT
        x.XC_StopCapture.argtypes  = [XCHANDLE];             x.XC_StopCapture.restype  = UINT
        x.XC_GetWidth.argtypes     = [XCHANDLE];             x.XC_GetWidth.restype     = UINT
        x.XC_GetHeight.argtypes    = [XCHANDLE];             x.XC_GetHeight.restype    = UINT
        x.XC_GetFrameSizeInBytes.argtypes = [XCHANDLE];      x.XC_GetFrameSizeInBytes.restype = UINT
        x.XC_CopyFrameBuffer.argtypes = [XCHANDLE, C.POINTER(USHORT), UINT]
        x.XC_CopyFrameBuffer.restype  = UINT

        if self.verbose:
            print("[BOBCAT640] Xeneth prototypes successfully bound.")

    # ----------------------------------------------------------------------
    # Harvester (GenICam) handling and device discovery
    # ----------------------------------------------------------------------

    def _maybe_init_harvester(self):
        """
        Initialize Harvester (GenICam) if available.
        """
        if self.h is not None:
            return

        try:
            from harvesters.core import Harvester
        except Exception:
            if self.verbose:
                print("[BOBCAT640] Harvester not available — skipping GenICam integration.")
            return

        self.h = Harvester()

        # Try to auto-load CTIs from environment
        for env_key in ("GENICAM_GENTL64_PATH", "GENICAM_GENTL32_PATH"):
            path = os.environ.get(env_key)
            if not path:
                continue
            sep = ";" if os.name == "nt" else ":"
            for base in filter(None, path.split(sep)):
                try:
                    self.h.add_cti_file(base)
                    if self.verbose:
                        print(f"[BOBCAT640] Added CTI path: {base}")
                except Exception as e:
                    if self.verbose:
                        print(f"[BOBCAT640] Failed to add CTI path {base}: {e}")

        try:
            self.h.update()
            if self.verbose:
                print("[BOBCAT640] Harvester device list updated.")
        except Exception as e:
            print(f"[BOBCAT640] Harvester initialization failed: {e}")
            self.h = None

    def _discover_device_info(self):
        """
        Discover the most probable Xenics/Bobcat GigE device using Harvester.
        """
        self._maybe_init_harvester()
        if self.h is None:
            print("[BOBCAT640] Harvester unavailable. Discovery skipped.")
            return None, None

        def score(di):
            s = 0
            v = (getattr(di, "vendor", "") or "").lower()
            m = (getattr(di, "model", "") or "").lower()
            if "xenics" in v: s += 2
            if "bobcat" in m: s += 2
            if getattr(di, "tl_type", "") and di.tl_type.upper() == "GEV": s += 1
            return s

        items = sorted(self.h.device_info_list, key=score, reverse=True)
        for di in items:
            if getattr(di, "tl_type", "") and di.tl_type.upper() != "GEV":
                continue
            ip = getattr(di, "ipv4", None) or getattr(di, "info_dict", {}).get("ip_address")
            if self.verbose:
                print(f"[BOBCAT640] Found candidate: {getattr(di, 'vendor', '')} {getattr(di, 'model', '')} ({ip})")
            return di, ip
        print("[BOBCAT640] No suitable GigE device found.")
        return None, None

    def _force_persistent_ip(self, di, ip: str, mask: str, gw: str) -> str:
        """
        Program a persistent IP address on the device via GenICam nodes.
        """
        if self.verbose:
            print(f"[BOBCAT640] Forcing persistent IP {ip} / {mask} gw {gw} ...")
        ia = None
        try:
            ia = self.h.create_image_acquirer(di)
            nm = ia.remote_device.node_map

            for name in ("GevCurrentIPConfigurationPersistent", "GevCurrentIPConfigurationLLA", "GevCurrentIPConfigurationDHCP"):
                try:
                    n = getattr(nm, name)
                    if name.endswith("Persistent"): n.value = True
                    if name.endswith("LLA") or name.endswith("DHCP"): n.value = False
                except Exception:
                    if self.verbose:
                        print(f"[BOBCAT640] Could not configure {name}")

            for (node, val) in (
                ("GevPersistentIPAddress", ip),
                ("GevPersistentSubnetMask", mask),
                ("GevPersistentDefaultGateway", gw),
            ):
                try:
                    n = getattr(nm, node)
                    try:
                        n.value = val
                    except Exception:
                        n.value = int(ipaddress.IPv4Address(val))
                    if self.verbose:
                        print(f"[BOBCAT640] Set {node} to {val}")
                except Exception:
                    if self.verbose:
                        print(f"[BOBCAT640] Failed to set {node}")

            try:
                nm.DeviceReset.execute()
                print("[BOBCAT640] Device reset executed after IP change.")
            except Exception:
                print("[BOBCAT640] Device reset not supported or failed.")
        finally:
            if ia:
                ia.destroy()

        time.sleep(2.0)
        try:
            self.h.update()
        except Exception:
            pass
        return ip

    def discover(self,
                 desired_ip: str = "192.168.0.2",
                 desired_mask: str = "255.255.255.0",
                 desired_gw: str = "0.0.0.0") -> Optional[str]:
        """
        Discover the Bobcat640 device and return a 'gev://<ip>' URL.
        """
        di, ip = self._discover_device_info()
        if di is None:
            return None

        if ip and not self._is_link_local(ip):
            print(f"[BOBCAT640] Found valid device at {ip}")
            return f"gev://{ip}"

        try:
            new_ip = self._force_persistent_ip(di, desired_ip, desired_mask, desired_gw)
            return f"gev://{new_ip}"
        except Exception as e:
            print(f"[BOBCAT640] Could not set persistent IP: {e}")
            return f"gev://{ip or desired_ip}"

    # ----------------------------------------------------------------------
    # Lifecycle management
    # ----------------------------------------------------------------------

    def open(self, url: str):
        """
        Open camera connection via Xeneth.
        """
        assert url.startswith("gev://"), "Use a GigE Vision URL like gev://<ip>"
        self._url = url

        print(f"[BOBCAT640] Opening camera at {url} ...")
        if self._open_by_url:
            self.cam = self.xeneth.XC_OpenCamera(url.encode("ascii"), None, None)
        else:
            self.cam = self.xeneth.XC_OpenCamera(0)

        if not self.cam:
            raise RuntimeError(f"[BOBCAT640] XC_OpenCamera failed for {url}")

        self._w = int(self.xeneth.XC_GetWidth(self.cam))
        self._h = int(self.xeneth.XC_GetHeight(self.cam))
        self._nbytes = int(self.xeneth.XC_GetFrameSizeInBytes(self.cam))
        print(f"[BOBCAT640] Camera opened — {self._w}x{self._h} ({self._nbytes} bytes/frame)")

    def start(self):
        """Start frame capture."""
        err = self.xeneth.XC_StartCapture(self.cam)
        if err != 0:
            raise RuntimeError(f"[BOBCAT640] XC_StartCapture failed (code {err})")
        print("[BOBCAT640] Capture started.")

    def stop(self):
        """Stop frame capture."""
        try:
            self.xeneth.XC_StopCapture(self.cam)
            print("[BOBCAT640] Capture stopped.")
        except Exception as e:
            if self.verbose:
                print(f"[BOBCAT640] Stop ignored: {e}")

    def close(self):
        """Close camera and cleanup."""
        print("[BOBCAT640] Closing camera...")
        if self.cam:
            try:
                self.stop()
            except Exception:
                pass
            try:
                self.xeneth.XC_CloseCamera(self.cam)
            except Exception:
                pass
            self.cam = None
        if self.h:
            try:
                self.h.reset()
            except Exception:
                pass
            self.h = None
        print("[BOBCAT640] Camera connection closed.")

    # ----------------------------------------------------------------------
    # Data I/O
    # ----------------------------------------------------------------------

    @property
    def size(self) -> Tuple[int, int]:
        """
        Return image size (width, height).
        """
        return self._w, self._h

    def snap(self) -> np.ndarray:
        """
        Acquire a single frame from the Xeneth buffer.

        Returns
        -------
        np.ndarray
            2D uint16 array with the latest frame.
        """
        frame16 = np.empty((self._h, self._w), dtype=np.uint16)
        err = self.xeneth.XC_CopyFrameBuffer(
            self.cam,
            frame16.ctypes.data_as(C.POINTER(c_ushort)),
            self._nbytes
        )
        if err != 0:
            raise RuntimeError(f"[BOBCAT640] XC_CopyFrameBuffer failed (code {err})")

        if self.verbose:
            print("[BOBCAT640] Frame captured successfully.")
        return frame16

    # ----------------------------------------------------------------------
    # GenICam configuration setters
    # ----------------------------------------------------------------------

    def _need_harvester_device(self):
        """
        Ensure Harvester is initialized and return an image acquirer
        for the connected camera.
        """
        self._maybe_init_harvester()
        if self.h is None:
            raise RuntimeError(
                "[BOBCAT640] GenICam not available. Please install 'harvesters' and load a GenTL Producer (.cti)."
            )
        self.h.update()
        target_ip = None
        try:
            target_ip = self._url.split('://', 1)[1]
        except Exception:
            pass

        for di in self.h.device_info_list:
            if getattr(di, "tl_type", "") and di.tl_type.upper() == "GEV":
                ip = getattr(di, "ipv4", None) or getattr(di, "info_dict", {}).get("ip_address")
                if (not target_ip) or (ip == target_ip):
                    return self.h.create_image_acquirer(di)

        for di in self.h.device_info_list:
            if getattr(di, "tl_type", "") and di.tl_type.upper() == "GEV":
                return self.h.create_image_acquirer(di)

        raise RuntimeError("[BOBCAT640] No GigE Vision device found in Harvester.")

    def set_exposure(self, seconds: float):
        """
        Set the exposure time through GenICam, if supported.

        Parameters
        ----------
        seconds : float
            Exposure time in seconds.
        """
        ia = self._need_harvester_device()
        try:
            try:
                ia.remote_device.node_map.ExposureAuto.value = "Off"
            except Exception:
                if self.verbose:
                    print("[BOBCAT640] ExposureAuto node unavailable.")
            usec = max(1.0, seconds * 1e6)
            for name in ("ExposureTime", "ExposureTimeAbs"):
                try:
                    n = getattr(ia.remote_device.node_map, name)
                    n.value = float(min(max(usec, n.min), n.max))
                    print(f"[BOBCAT640] Exposure set via {name}: {n.value:.1f} µs")
                    ia.destroy()
                    return
                except Exception:
                    if self.verbose:
                        print(f"[BOBCAT640] Node {name} not usable for exposure.")
                    continue
            ia.destroy()
            raise RuntimeError("[BOBCAT640] Could not set exposure — node not found.")
        except Exception as e:
            try:
                ia.destroy()
            except Exception:
                pass
            raise RuntimeError(f"[BOBCAT640] Exposure configuration failed: {e}")

    def set_framerate(self, fps: float):
        """
        Set the acquisition frame rate through GenICam, if supported.

        Parameters
        ----------
        fps : float
            Desired frame rate in frames per second.
        """
        ia = self._need_harvester_device()
        try:
            try:
                ia.remote_device.node_map.AcquisitionFrameRateEnable.value = True
            except Exception:
                if self.verbose:
                    print("[BOBCAT640] AcquisitionFrameRateEnable not available.")
            n = ia.remote_device.node_map.AcquisitionFrameRate
            n.value = float(min(max(fps, n.min), n.max))
            print(f"[BOBCAT640] Frame rate set to {n.value:.2f} fps")
            ia.destroy()
        except Exception as e:
            try:
                ia.destroy()
            except Exception:
                pass
            raise RuntimeError(f"[BOBCAT640] Failed to set frame rate: {e}")
