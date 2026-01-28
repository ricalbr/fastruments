import ctypes
import enum
import pathlib
from typing import Optional
from fastruments.helpers import DllBinder
import sys

import pathlib
import os

from Instrument import Instrument

CWD = pathlib.Path(__file__).resolve().parent
os.add_dll_directory(CWD / "dll")
DLL_NAME = "OP710M_64.dll"


class SantecDLL:
    """Low-level ctypes wrapper for the Santec OP150 Power Meter.

    This class is responsible for:
    - loading the DLL
    - defining function signatures
    - translating error codes into Python exceptions
    """

    def __init__(self, dll_name: str | pathlib.Path = DLL_NAME):
        self._dll_name = dll_name
        self._dll: Optional[ctypes.CDLL] = None
        self._load()

    # DLL loading and binding
    def _load(self) -> None:
        """Load the DLL and bind all functions."""
        self._dll = ctypes.CDLL(self._dll_name)
        self._bind_functions()

    def _bind_functions(self) -> None:
        """Bind all required DLL functions."""

        binder = DllBinder(self._dll)

        # Module / driver control
        binder.bind(self, "ActiveModule", ctypes.c_int, (ctypes.c_int,))
        binder.bind(self, "Backlight", ctypes.c_int, (ctypes.c_int,))
        binder.bind(self, "CloseDriver", ctypes.c_int, ())
        binder.bind(self, "OpenDriver", ctypes.c_int, (ctypes.c_uint64,))
        binder.bind(self, "RemoteMode", ctypes.c_int, (ctypes.c_int,))
        binder.bind(self, "SelectModule", ctypes.c_int, (ctypes.c_int,))

        # Conversion / configuration
        binder.bind(
            self,
            "ConvertPower",
            ctypes.c_int,
            (ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double)),
        )
        binder.bind(self, "SetAbsolute", ctypes.c_int, ())
        binder.bind(self, "SetAutoRange", ctypes.c_int, (ctypes.c_int,))
        binder.bind(self, "SetGain", ctypes.c_int, (ctypes.c_int,))
        binder.bind(self, "SetOPMMode", ctypes.c_int, (ctypes.c_int,))
        binder.bind(self, "SetReference", ctypes.c_int, ())
        binder.bind(self, "SetSamplingSpeed", ctypes.c_int, (ctypes.c_byte,))
        binder.bind(self, "SetWavelength", ctypes.c_int, (ctypes.c_int,))

        # Status / information
        binder.bind(self, "GetDLLRev", ctypes.c_int, ())
        binder.bind(self, "GetDLLStatus", ctypes.c_int, ())
        binder.bind(self, "GetFWRevision", ctypes.c_int, ())
        binder.bind(self, "GetChannelBuffer", ctypes.c_int, ())
        binder.bind(
            self, "GetUSBStatus", ctypes.c_int, (ctypes.POINTER(ctypes.c_bool),)
        )

        # Module / device info
        binder.bind(self, "GetModuleID", ctypes.c_int, (ctypes.POINTER(ctypes.c_int),))
        binder.bind(
            self, "GetModuleNumber", ctypes.c_int, (ctypes.POINTER(ctypes.c_int),)
        )
        binder.bind(
            self, "GetUSBDeviceCount", ctypes.c_int, (ctypes.POINTER(ctypes.c_int),)
        )
        binder.bind(
            self,
            "GetUSBDeviceDescription",
            ctypes.c_int,
            (ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)),
        )
        binder.bind(
            self,
            "GetUSBSerialNumber",
            ctypes.c_int,
            (ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)),
        )

        # Channel / wavelength handling
        binder.bind(
            self,
            "GetActiveChannel",
            ctypes.c_int,
            (ctypes.POINTER(ctypes.c_int),),
        )
        binder.bind(self, "SetActiveChannel", ctypes.c_int, (ctypes.c_int,))
        binder.bind(
            self,
            "GetWavelength",
            ctypes.c_int,
            (
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ),
        )
        binder.bind(
            self,
            "NextWavelength",
            ctypes.c_int,
            (
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ),
        )

        # Reading data
        binder.bind(
            self,
            "ReadAnalog",
            ctypes.c_int,
            (
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ),
        )
        binder.bind(
            self,
            "ReadChannelBuffer",
            ctypes.c_int,
            (ctypes.c_int, ctypes.POINTER(ctypes.c_double)),
        )
        binder.bind(
            self,
            "ReadChannelBufferRaw",
            ctypes.c_int,
            (ctypes.c_int, ctypes.c_uint16, ctypes.POINTER(ctypes.c_byte)),
        )
        binder.bind(self, "ReadLoss", ctypes.c_int, (ctypes.POINTER(ctypes.c_double),))
        binder.bind(self, "ReadPower", ctypes.c_int, (ctypes.POINTER(ctypes.c_double),))
        binder.bind(
            self, "ReferencePower", ctypes.c_int, (ctypes.POINTER(ctypes.c_double),)
        )

        # USB
        binder.bind(
            self,
            "OpenUSBDevice",
            ctypes.c_int,
            (ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)),
        )


# Enumerations
class ErrorCodes(enum.IntEnum):
    """Enumeration of possible DLL return codes and communication errors."""

    NO_USB_DEVICE_FOUND = -5
    COMMUNICATION_ERROR = -4
    USB_READ_ERROR = -3
    USB_WRITE_ERROR = -2
    FAIL = -1
    OK_0 = 0
    OK_1 = 1
    INVALID_HANDLE = 1
    DEVICE_NOT_FOUND = 2
    DEVICE_NOT_OPENED = 3
    IO_ERROR = 4


class ModuleID(enum.IntEnum):
    """Enumeration of supported OptoTest module identifiers."""

    OP250 = 10
    OPM510 = 11
    OP710 = 12
    OP831 = 13
    OP930 = 14
    OP750 = 15
    OP815 = 16
    OP1100 = 17
    OP1021 = 18
    OP1302 = 19
    OP815D = 20
    OP720 = 21
    OP850 = 22
    OP280 = 23
    OP715 = 24
    OP712 = 25
    OP931 = 26
    OP931_FTTX = 27
    OP480 = 28


class Wavelengths(enum.IntEnum):
    """Commonly supported wavelengths (in nanometers)."""

    nm850 = 850
    nm980 = 980
    nm1300 = 1300
    nm1310 = 1310
    nm1480 = 1480
    nm1550 = 1550
    nm1625 = 1625
    nm1650 = 1650


class OPM150(Instrument):
    """
    High-level interface for the Santec OPM150 optical power meter (USB).

    This class provides a safe and well-documented Python interface for
    controlling the OPM150 power meter via its vendor DLL (`op710m_dll`).
    It enables USB device discovery, multi-channel power measurements, and
    configuration of instrument parameters such as wavelength, gain,
    autorange, and sampling speed.

    Parameters
    ----------
    verbose : bool, optional
        If ``True``, prints detailed information and communication messages
        to the console (default is ``True``).

    Attributes
    ----------
    device_number : int
        Index of the connected USB device as detected by the DLL.
    power_unit : Literal[0, 1]
        Power readout mode (``0`` = dBm, ``1`` = W). The device itself
        cannot switch units, so conversions are performed in software.
    active_channel : int
        Currently active input channel (from 1 to 24).
    available_wavelengths : Enum
        List of discrete wavelengths supported by the instrument.
    remote_mode : bool
        Indicates whether the instrument is in remote control mode.
    sampling_speed : Optional[int]
        Current sampling speed setting (0–8, where 0 is fastest).

    Examples
    --------
    >>> from lib.instruments.opm150.core import OPM150
    >>> pm = OPM150(verbose=True)
    [OPM150] Connected to Santec OPM150 via USB.
    >>> pm.active_channel = 1
    [OPM150] Active channel set to 1.
    >>> pm.wavelength = 1550
    [OPM150] Wavelength set to 1550 nm.
    >>> power = pm.read_power()
    [OPM150] Power reading (CH1): -2.34 dBm.
    >>> pm.close()
    [OPM150] Connection closed.

    Notes
    -----
    - Channel switching requires a short delay (~0.1 s) between commands.
    - Power unit conversion (dBm ↔ W) is handled internally.
    - Autorange and gain settings are shared between adjacent channels.
    """

    def _check(self, code: int) -> None:
        try:
            err = ErrorCodes(code)
        except ValueError:
            raise RuntimeError(f"Unknown DLL error code: {code}") from None

        if err not in (ErrorCodes.OK_0, ErrorCodes.OK_1):
            raise RuntimeError(f"DLL error: {err.name}")

    def __init__(self, dll: SantecDLL = SantecDLL(), verbose: bool = True):
        super().__init__()
        self._dll = dll
        self.verbose = verbose
        self._is_connection_open = False

    def __del__(self):
        """
        Destructor: ensure the connection is closed when the object is garbage-collected.
        """
        try:
            self.close()
        except Exception:
            # keep destructor silent on errors
            pass

    def connect(self, device_index: int = 0) -> None:
        """
        Connect to a Santec OPM150 via USB.

        Parameters
        ----------
        device_index : int, optional
            USB device index to open (default: 0).
        """
        if self._is_connection_open:
            return

        # --- device count ---
        count = ctypes.c_int()
        self._check(self._dll.GetUSBDeviceCount(ctypes.byref(count)))

        if count.value == 0:
            raise RuntimeError("No Santec USB devices found")

        if device_index >= count.value:
            raise ValueError(f"device_index {device_index} out of range")

        # --- open USB device ---
        handle = ctypes.c_uint64()
        self._check(
            self._dll.OpenUSBDevice(
                ctypes.c_int(device_index),
                ctypes.byref(handle),
            )
        )

        # --- open driver ---
        self._check(self._dll.OpenDriver(handle))

        self._is_connection_open = True

        if self.verbose:
            print(f"[OPM150] Connected to USB device {device_index}")

    def get_func_name(self, n: int = 0) -> str:
        """
        Return the caller function name (used for logging/error messages).

        Parameters
        ----------
        n : int
            Stack offset (0 -> immediate caller).

        Returns
        -------
        str
            The name of the calling function.
        """
        return sys._getframe(n + 1).f_code.co_name

    def close(self) -> None:
        """
        Close the driver and release communication resources.

        Notes
        -----
        - Disables remote mode before closing.
        - After calling close, further operations will fail until reopened.
        """
        if self._is_connection_open:
            # set remote_mode off first
            try:
                self.remote_mode = False
            except Exception:
                self.logger.debug(
                    "Failed to disable remote mode during close", exc_info=True
                )
            _ret = op710m_dll.CloseDriver()
            self._check(self.get_func_name(), _ret)
            self._is_connection_open = False
            print("[OPM150] Driver closed")

    @property
    def active_channel(self) -> int:
        ch = ctypes.c_int()
        self._check(self._dll.GetActiveChannel(ctypes.byref(ch)))

        if self.verbose:
            print(f"[OPM150] Active channel: {ch.value}")

        return ch.value

    @active_channel.setter
    def active_channel(self, channel: int) -> None:
        if not (1 <= channel <= 24):
            raise ValueError("Channel must be in range 1–24")

        self._check(self._dll.SetActiveChannel(ctypes.c_int(channel)))

        if self.verbose:
            print(f"[OPM150] Active channel set to {channel}")

    @property
    def wavelength(self) -> Wavelengths:
        wl = ctypes.c_int()
        idx = ctypes.c_int()
        count = ctypes.c_int()

        self._check(
            self._dll.GetWavelength(
                ctypes.byref(wl), ctypes.byref(idx), ctypes.byref(count)
            )
        )

        wavelength = Wavelengths(wl.value)

        if self.verbose:
            print(f"[OPM150] Wavelength: {wavelength.value} nm")

        return wavelength

    @wavelength.setter
    def wavelength(self, wavelength: int | Wavelengths) -> None:
        try:
            wl = Wavelengths(wavelength)
        except ValueError:
            raise ValueError(
                f"Unsupported wavelength {wavelength}. "
                f"Available: {[w.value for w in Wavelengths]}"
            )

        self._check(self._dll.SetWavelength(ctypes.c_int(wl.value)))

        if self.verbose:
            print(f"[OPM150] Wavelength set to {wl.value} nm")

    def read_power(self) -> float:
        power = ctypes.c_double()
        self._check(self._dll.ReadPower(ctypes.byref(power)))

        value = power.value

        if self.power_unit == 0:
            if self.verbose:
                print(f"[OPM150] Power: {value:.3f} dBm")
            return value

        # convert dBm → W
        linear = 10 ** (value / 10 - 3)
        if self.verbose:
            print(f"[OPM150] Power: {linear:.3e} W")

        return linear

    def update_channel_buffer(self) -> None:
        self._check(self._dll.GetChannelBuffer())

        if self.verbose:
            print("[OPM150] Channel buffer updated")

    def read_channel_buffer_power(self, channel: int) -> float:
        if not (1 <= channel <= 24):
            raise ValueError("Channel must be in range 1–24")

        ch = ctypes.c_int(channel)
        power = ctypes.c_double()

        self._check(self._dll.ReadChannelBuffer(ch, ctypes.byref(power)))

        value = power.value

        if self.power_unit == 0:
            return value

        return 10 ** (value / 10 - 3)

    def read_all_channels(self) -> list[float]:
        self.update_channel_buffer()

        values: list[float] = []
        for ch in range(1, 25):
            values.append(self.read_channel_buffer_power(ch))

        if self.verbose:
            print("[OPM150] Read power from all channels")

        return values


if __name__ == "__main__":
    try:
        print("=== OPM150 basic test ===")

        pm = OPM150(verbose=True)

        # Basic info
        print("Active channel:", pm.active_channel)
        print("Current wavelength:", pm.wavelength)

        # Set safe defaults
        pm.active_channel = 1
        pm.wavelength = Wavelengths.nm1550

        # Read power
        power = pm.read_power()
        print(f"Measured power: {power:.3f} {'dBm' if pm.power_unit == 0 else 'W'}")

        # Read all channels (buffered)
        values = pm.read_all_channels()
        print(f"Read {len(values)} channels")
        print("First 8 channels:", values[:8])

    except Exception as exc:
        print(type(exc).__name__, exc)

    finally:
        try:
            pm.close()
        except Exception:
            pass
