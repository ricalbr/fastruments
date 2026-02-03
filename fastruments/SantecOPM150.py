import ctypes
import enum
import pathlib
from typing import Optional
from helpers import DllBinder
import sys
import os
import logging
from typing import Literal
import time
import numpy as np

from Instrument import Instrument


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
    nm925 = 925
    nm1300 = 1300
    nm1310 = 1310
    nm1480 = 1480
    nm1550 = 1550
    nm1625 = 1625
    nm1650 = 1650

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
        binder.bind(self, "GetTemperature", ctypes.c_int, (ctypes.POINTER(ctypes.c_double), ctypes.c_int))

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
    >>> power = pm.power()
    [OPM150] Power reading (CH1): -2.34 dBm.
    >>> pm.close()
    [OPM150] Connection closed.

    Notes
    -----
    - Channel switching requires a short delay (~0.1 s) between commands.
    - Power unit conversion (dBm ↔ W) is handled internally.
    - Autorange and gain settings are shared between adjacent channels.
    """

    def __init__(self, dll: SantecDLL = SantecDLL(), verbose: bool = True, power_unit=1):
        """
        Initialize communication with the OPM150 (OP-710 family).

        Parameters
        ----------
        verbose : bool
            If True, prints important status messages prefixed with [OPM150].
            Detailed debug prints are also emitted to the logger and to stdout
            when verbose is True.

        Behaviour
        ---------
        - Discovers connected compatible USB devices and selects the first OP710 it finds.
        - Opens the USB device and initializes the DLL driver.
        - Sets `remote_mode = True` and initializes internal defaults.
        """
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        self.power_unit = power_unit
        self.device_number = None
        self.available_wavelengths = Wavelengths # available wavelengths enum from DLL
        # self.active_channel = 1 # ensure active_channel is set explicitly (DLL getter may reset on reopen)
        self._dll = dll
        
        self._is_connection_open = False
        self._sampling_speed = None  # probably channel-related; untested here
        self.remote_mode = True
        
        self.connect()
        
    def connect(self):
        device_count = self.USB_device_count
        self.logger.debug(f"Device count : {device_count}")

        self.device_number = next(
            (
                i 
                for i in range(device_count)
                if "OP710" in self.get_USB_device_description(i)
            ),
            None,
        )
        if self.device_number is None:
            raise RuntimeError("[OPM150] No OP710 device found")
        else:
            self.logger.debug(f"Device number : {self.device_number}")

        # open USB device and driver
        self._handle = self.open_USB_device(self.device_number)
        self.logger.debug(f"USB Handle : {self._handle}")
        self._is_connection_open = self.open_driver(self._handle)
        self.logger.debug(f"Is connection open : {self._is_connection_open}")


    def close(self) -> None:
        """
        Close the driver and release communication resources.

        Notes
        -----
        - Disables remote mode before closing.
        - After calling close, further operations will fail until reopened.
        """
        if self._is_connection_open:
            _ret = self._dll.CloseDriver()
            self._check("CloseDriver", _ret)
            self._is_connection_open = False
            self.logger.info("Driver closed.")

    def get_module_USB_handle(self, module: int) -> int:
        """
        Check whether the specified module is active and return its USB handle.

        Parameters
        ----------
        module : int
            Module index to check.

        Returns
        -------
        int
            USB handle if module active, otherwise returns 0 (or a module-specific value).
        """

        handle = self._dll.ActiveModule(ctypes.c_int(module))
        self.logger.debug(f"ActiveModule({module}) -> {handle}")
        return handle

    def open_USB_device(self, dev_number: int) -> int:
        """
        Open the USB device by device number and return a USB handle.

        Parameters
        ----------
        dev_number : int
            USB device index as returned by USB_device_count / discovery.

        Returns
        -------
        int
            Numeric USB handle for use with `open_driver`.
        """
        handle = ctypes.c_uint64()
        _ret = self._dll.OpenUSBDevice(ctypes.c_int(dev_number), ctypes.byref(handle))
        self._check("OpenUSBDevice", _ret)
        self.logger.debug(
             f"OpenUSBDevice(dev_number={dev_number}) -> handle={handle.value}"
         )
        return handle.value

    def open_driver(self, handle: int = 0) -> bool:
        """
        Initialize the DLL driver with the provided USB handle.

        Parameters
        ----------
        handle : int
            USB handle obtained from `open_USB_device`. Passing 0 will
            attempt to open the first detected USB device.

        Returns
        -------
        bool
            True on success, False otherwise.
        """
        _ret = self._dll.OpenDriver(ctypes.c_uint64(handle))
        self._check("OpenDriver", _ret)
        return _ret == 0

    @property
    def USB_device_count(self) -> int:
        """
        Query the number of connected compatible USB devices.

        Returns
        -------
        int
            Number of connected devices compatible with the DLL.
        """
        _count = ctypes.c_int()
        _ret = self._dll.GetUSBDeviceCount(ctypes.byref(_count))
        self._check("GetUSBDeviceCount", _ret)
        return _count.value

    def get_USB_device_description(self, dev_number: int) -> str:
        """
        Retrieve the USB device description string for the specified device.

        Parameters
        ----------
        dev_number : int
            Device index to query.

        Returns
        -------
        str
            UTF-8 decoded device description (up to 16 chars per DLL).
        """
        _description = ctypes.c_char_p()
        _dev_number = ctypes.c_int(dev_number)
        _ret = self._dll.GetUSBDeviceDescription(_dev_number, ctypes.byref(_description))
        self._check("GetUSBDeviceDescription", _ret)
        desc = _description.value.decode("UTF-8")
        self.logger.debug(f"Device[{dev_number}] description: {desc}")
        return desc

    @property
    def USB_serial_number(self) -> str:
        """
        Return the USB serial number of the currently selected device.

        Returns
        -------
        str
            Serial number string (8 characters).
        """
        _serial = ctypes.c_char_p()
        _device_number = ctypes.c_int(self.device_number)
        _ret = self._dll.GetUSBSerialNumber(_device_number, ctypes.byref(_serial))
        self._check("GetUSBSerialNumber", _ret)
        return _serial.value.decode("UTF-8")

    @property
    def USB_status(self) -> bool:
        """
        Get the USB error flag of the last operation for the currently selected device.

        Returns
        -------
        bool
            True if an error flag is set, False otherwise.
        """
        _have_error = ctypes.c_bool()
        _device_number = ctypes.c_int(self.device_number)
        _ret = self._dll.GetUSBStatus(_device_number, ctypes.byref(_have_error))
        self._check("GetUSBStatus", _ret)
        return _have_error.value

    @property
    def active_channel(self) -> int:
        """
        Get the current active channel.

        Returns
        -------
        int
            Index of the currently active optical input channel.
        """
        _ch = ctypes.c_int()
        _ret = self._dll.GetActiveChannel(ctypes.byref(_ch))
        self._check("GetActiveChannel", _ret)
        self.logger.debug(f"Active channel: {_ch.value}")
        return _ch.value

    @active_channel.setter
    def active_channel(self, ch: int) -> None:
        """
        Set the active measurement channel.

        Parameters
        ----------
        ch : int
            Channel number (1–24). Channels are 1-based, not zero-indexed.
        """
        _ret = self._dll.SetActiveChannel(ctypes.c_int(ch))
        self._check("SetActiveChannel", _ret)
        self.logger.debug(f"Active channel set to {ch}.")

    def temperature(self, unit: Literal[0, 1, 2] = 1) -> float:
        """
        Read the device internal temperature.

        Parameters
        ----------
        unit : {0, 1, 2}, default=1
            Temperature unit:
              0 → raw digital value
              1 → Celsius
              2 → Fahrenheit

        Returns
        -------
        float
            Temperature in the specified unit.
        """
        temperature = ctypes.c_double()
        _ret = self._dll.GetTemperature(ctypes.byref(temperature), unit)
        self._check("GetTemperature", _ret)
        self.logger.debug(f"Temperature: {temperature.value:.2f} (unit={unit}).")
        return temperature.value

    @property
    def wavelength(self) -> Wavelengths:
        """
        Get the current measurement wavelength of the active channel.

        Returns
        -------
        Wavelengths
            Enum value representing the active wavelength.
        """
        wl = ctypes.c_int()
        idx = ctypes.c_int()
        ct = ctypes.c_int()
        _ret = self._dll.GetWavelength(ctypes.byref(wl), ctypes.byref(idx), ctypes.byref(ct))
        self._check("GetWavelength", _ret)
        self.logger.debug(f"Wavelength: {wl.value} nm (index={idx.value}).")
        return Wavelengths(wl.value)

    @wavelength.setter
    def wavelength(self, wavelength: int) -> None:
        """
        Set the measurement wavelength for the active channel.

        Parameters
        ----------
        wavelength : int
            Wavelength value (must be one of `Wavelengths`).

        Raises
        ------
        ValueError
            If the wavelength is not valid for the instrument.
        """
        try:
            wl = self.available_wavelengths(wavelength)
        except ValueError:
            raise ValueError(
                f"Wavelength {wavelength} not supported. "
                f"Available values: {[w.value for w in self.available_wavelengths]}"
            )
        _wavelength = ctypes.c_int(wl.value)
        _ret = self._dll.SetWavelength(_wavelength)
        self._check("SetWavelength", _ret)
        self.logger.debug(f"Wavelength set to {wl.value} nm")

    def read_adc(self) -> int:
        """
        Read the raw ADC value of the currently active OPM channel.

        Returns
        -------
        int
            Raw analog value.
        """
        _analog = ctypes.c_int()
        _gain = ctypes.c_int()
        _mode = ctypes.c_int()
        _ret = self._dll.ReadAnalog(ctypes.byref(_analog), ctypes.byref(_gain), ctypes.byref(_mode))
        self._check("ReadAnalog", _ret)
        self.logger.debug(f"Analog: {_analog.value}, gain={_gain.value}, mode={_mode.value}")
        return _analog.value

    def adc_to_power(self, analog: int, gain: int) -> float:
        """
        Convert raw ADC + gain to optical power.
    
        Parameters
        ----------
        analog : int
            Raw ADC value (from read_analog).
        gain : int
            Channel gain (0–7).
    
        Returns
        -------
        float
            Power in dBm or W depending on self.power_unit.
        """
        power = ctypes.c_double()
        ret = self._dll.ConvertPower(ctypes.c_int(analog), ctypes.c_int(gain), ctypes.byref(power))
        self._check("ConvertPower", ret)
        return self._to_power_unit(power.value, dbm=True)

    def refresh_channels_buffers(self) -> None:
        """
        Acquire power for all channels simultaneously and update internal buffers.
        """
        _ret = self._dll.GetChannelBuffer()
        self._check("GetChannelBuffer", _ret)
        self.logger.debug("Channel buffer updated.")

    def buffered_power(self, ch: int) -> float:
        """
        Read buffered power measurement for a specific channel.
    
        Parameters
        ----------
        ch : int
            Channel number (1–24). `refresh_channel_buffer()` must be called before.
    
        Returns
        -------
        float
            Power in dBm or W depending on self.power_unit.
        """
        power = ctypes.c_double()
        ret = self._dll.ReadChannelBuffer(ctypes.c_int(ch), ctypes.byref(power))
        self._check("ReadChannelBuffer", ret)
        self.logger.debug(f"Ch{ch}: {power.value:.3f} raw units")
        return self._to_power_unit(power.value, dbm=True)
    
    def read_power(
        self, channels: int or list[int] = [i + 1 for i in range(24)], sleep: float = 0.1,
    ) -> list[float]:
        """
        Read power sequentially from a list of channels.
    
        Parameters
        ----------
        channels : int, list[int], default=[1..24]
            List of channels to read (1-based).
        sleep : float, default=0.1
            Delay (s) between reads, required by hardware timing.
    
        Returns
        -------
        list[float]
            Power readings for all requested channels, in dBm or W.
        """
        self.refresh_channels_buffers()
        time.sleep(sleep)
        
        if isinstance(channels, int):
            channels = [channels]
            
        powers = [self.buffered_power(ch) for ch in channels]
        self.logger.debug(f"Read {len(channels)} channels: {channels}")
        return powers
            

    def autorange(self, enabled: bool) -> None:
        """
        Enable or disable Auto-Range for the active channel.

        Parameters
        ----------
        enabled : bool
            True to enable Auto-Range, False to hold range.

        Notes
        -----
        Auto-Range setting is shared between adjacent channels.
        """
        _range = ctypes.c_int(1) if enabled else ctypes.c_int(0)
        _ret = self._dll.SetAutoRange(_range)
        self._check("SetAutoRange", _ret)
        self.logger.debug(f"Autorange {'enabled' if enabled else 'disabled'} on active channel.")

    def autorange_all(self, enabled: bool) -> None:
        """
        Apply Auto-Range setting to all channels.

        Parameters
        ----------
        enabled : bool
            True to enable Auto-Range, False to disable.

        Notes
        -----
        Auto-Range applies to pairs of adjacent channels.
        A small delay (0.05 s) is inserted between each channel update.
        """
        _current = self.active_channel
        for i in range(1, 25):
            self.active_channel = i
            time.sleep(0.05)
            self.autorange(enabled)
        self.active_channel = _current
        self.logger.debug(f"Autorange {'enabled' if enabled else 'disabled'} for all channels.")

    @property
    def gain(self) -> int:
        """
        Get the gain value for the active channel.

        Returns
        -------
        int
            Gain level (0–7).
        """
        _analog = ctypes.c_int()
        _gain = ctypes.c_int()
        _mode = ctypes.c_int()
        _ret = self._dll.ReadAnalog(ctypes.byref(_analog), ctypes.byref(_gain), ctypes.byref(_mode))
        self._check("ReadAnalog", _ret)
        self.logger.debug(f"Gain (ch={self.active_channel}): {_gain.value}")
        return _gain.value

    @gain.setter
    def gain(self, gain: Literal[0, 1, 2, 3, 4, 5, 6, 7]) -> None:
        """
        Set the gain for the active channel.

        Parameters
        ----------
        gain : int
            Gain level (0–7). Automatically disables Auto-Range.
        """
        _gain = ctypes.c_int(gain)
        _ret = self._dll.SetGain(_gain)
        self._check("SetGain", _ret)
        self.logger.debug(f"Gain set to {gain} (Auto-Range disabled)")

    def gain_all(self, gain: Literal[0, 1, 2, 3, 4, 5, 6, 7]) -> None:
        """
        Set the gain for all channels.

        Parameters
        ----------
        gain : int
            Gain level (0–7). Automatically disables Auto-Range.
        """
        _current = self.active_channel
        for i in range(1, 25):
           self.active_channel = i
           time.sleep(0.05)
           self.gain = gain
        self.active_channel = _current
        self.logger.debug(f"Gain set to {gain} for all channels")

    @property
    def sampling_speed(self) -> Optional[int]:
        """
        Get the current sampling speed setting.

        Returns
        -------
        int or None
            Speed level (0–8), or None if unset.
        """
        return self._sampling_speed

    @sampling_speed.setter
    def sampling_speed(self, speed: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8]) -> None:
        """
        Set the OPM sampling speed.

        Parameters
        ----------
        speed : int
            Speed setting (0 = fastest, 8 = slowest).
        """
        self._sampling_speed = speed
        _speed = ctypes.c_byte(speed)
        _ret = self._dll.SetSamplingSpeed(_speed)
        self._check("SetSamplingSpeed", _ret)
        self.logger.debug(f"Sampling speed set to {speed}")
        
    def _to_power_unit(self, value: float, dbm: bool=False) -> float:
        """
        Convert raw dBm to the correct unit and log the value.
    
        Parameters
        ----------
        value_dbm : float
            Power in dBm from the DLL.
    
        Returns
        -------
        float
            Power in dBm or W depending on self.power_unit.
        """
        if self.power_unit == 0:  # dBm
            self.logger.debug(f"Power: {value:.3f} dBm")
            return value
        elif self.power_unit == 1:  # W
            pw = self._db_to_linear(value, dbm=dbm)
            self.logger.debug(f"Power: {pw:.3e} W (converted)")
            return pw
        else:
            raise ValueError("power_unit must be either 0 (dBm) or 1 (W).")
            
    def _db_to_linear(self, value: float, dbm: bool = False) -> float:
        """
        Convert a power value from dB/dBm to linear units.
    
        Parameters
        ----------
        value : float
            Input value in dB (for relative power) or dBm (for absolute power).
        dbm : bool, default=False
            If True, input is in dBm and output is in Watts.
            If False, input is in dB and output is a dimensionless ratio.
    
        Returns
        -------
        float
            Linear value (Watts if dBm=True, ratio if dbm=False).
        """
        factor = -3 if dbm else 0
        return np.power(10, value / 10 + factor)

    def _check(self, func_name: str, err_code: int) -> None:
        """
        Internal error checker for DLL calls.

        Raises
        ------
        Exception
            If error code is not OK_0 or OK_1.
        """
        code = ErrorCodes(err_code)
        if code not in (ErrorCodes.OK_0, ErrorCodes.OK_1):
            raise Exception(f"[OPM150] {func_name} failed: {code.name}")
            

if __name__ == "__main__":

    try:
        pm = OPM150(power_unit=1)
    except RuntimeError as e:
        print(f"Inizialization error: {e}")
        sys.exit(1)

    try:
        print("\n--- Device Info ---")
        print(f"USB serial number: {pm.USB_serial_number}")
        temp_c = pm.temperature(unit=1)
        print(f"Temperature: {temp_c:.2f} °C")
        pm.wavelength = 925
        print(f"Wavelength: {pm.wavelength.value} nm")
        
        print("\n--- Power on multiple channels ---")
        chs = list(range(1,25))
        powers = pm.read_power(channels=chs, sleep=0.2)
        for ch, p in zip(chs, powers):
            print(f"CH {ch}:\t{p:.3e} W")
        total_power = np.sum(powers)
        print(f"Total power: {total_power:.3e} W")

    except Exception as e:
        print(f"Communication Error: {e}")

    finally:
        pm.close()

