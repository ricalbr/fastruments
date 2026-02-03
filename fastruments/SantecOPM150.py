"""
SANTEC OPM 150

This module provides a high-level Python interface for controlling the
Santec OPM150 optical power meter through its USB interface.

It wraps the vendor’s low-level DLL interface (via `op710m_dll`) to offer
a Pythonic, lab-automation–friendly API for optical power measurements
across multiple channels.

Main features include automatic device discovery, channel-wise control of power,
wavelength, and gain, as well as access to temperature and reference power readings.
Both linear (W) and logarithmic (dBm) readout modes are supported, and a verbose
logging mode can be enabled to print detailed information about the communication
and measurements.
"""

import logging
import math
import os
import sys
import time
from ctypes import (
    POINTER,
    byref,
    c_bool,
    c_byte,
    c_char_p,
    c_double,
    c_int,
    c_uint16,
    c_uint64,
    cdll,
)
from enum import Enum
from typing import Literal, Optional
import pathlib

# DLL Loading
CWD = pathlib.Path(__file__).resolve().parent
os.add_dll_directory(CWD / "dll")
DLL_NAME = "OP710M_64.dll"
op710m_dll = cdll.LoadLibrary("OP710M_64.dll")


# DLL Function Definitions
ActiveModule = op710m_dll.ActiveModule
ActiveModule.argtypes = [c_int]
ActiveModule.restype = c_int

Backlight = op710m_dll.Backlight
Backlight.argtypes = [c_int]
Backlight.restype = c_int

CloseDriver = op710m_dll.CloseDriver
CloseDriver.argtypes = []
CloseDriver.restype = c_int

ConvertPower = op710m_dll.ConvertPower
ConvertPower.argtypes = [c_int, c_int, POINTER(c_double)]
ConvertPower.restype = c_int

GetActiveChannel = op710m_dll.GetActiveChannel
GetActiveChannel.argtypes = [POINTER(c_int)]
GetActiveChannel.restype = c_int

GetChannelBuffer = op710m_dll.GetChannelBuffer
GetChannelBuffer.argtypes = []
GetChannelBuffer.restype = c_int

GetDLLRev = op710m_dll.GetDLLRev
GetDLLRev.argtypes = []
GetDLLRev.restype = c_int

GetDLLStatus = op710m_dll.GetDLLStatus
GetDLLStatus.argtypes = []
GetDLLStatus.restype = c_int

GetFWRevision = op710m_dll.GetFWRevision
GetFWRevision.argtypes = []
GetFWRevision.restype = c_int

GetModuleID = op710m_dll.GetModuleID
GetModuleID.argtypes = [POINTER(c_int)]
GetModuleID.restype = c_int

GetModuleNumber = op710m_dll.GetModuleNumber
GetModuleNumber.argtypes = [POINTER(c_int)]
GetModuleNumber.restype = c_int

GetTemperature = op710m_dll.GetTemperature
GetTemperature.argtypes = [POINTER(c_double), c_int]
GetTemperature.restype = c_int

GetUSBDeviceCount = op710m_dll.GetUSBDeviceCount
GetUSBDeviceCount.argtypes = [POINTER(c_int)]
GetUSBDeviceCount.restype = c_int

GetUSBDeviceDescription = op710m_dll.GetUSBDeviceDescription
GetUSBDeviceDescription.argtypes = [c_int, POINTER(c_char_p)]
GetUSBDeviceDescription.restype = c_int

GetUSBSerialNumber = op710m_dll.GetUSBSerialNumber
GetUSBSerialNumber.argtypes = [c_int, POINTER(c_char_p)]
GetUSBSerialNumber.restype = c_int

GetUSBStatus = op710m_dll.GetUSBStatus
GetUSBStatus.argtypes = [POINTER(c_bool)]
GetUSBStatus.restype = c_int

GetWavelength = op710m_dll.GetWavelength
GetWavelength.argtypes = [POINTER(c_int), POINTER(c_int), POINTER(c_int)]
GetWavelength.restype = c_int

NextWavelength = op710m_dll.NextWavelength
NextWavelength.argtypes = [POINTER(c_int), POINTER(c_int), POINTER(c_int)]
NextWavelength.restype = c_int

OpenDriver = op710m_dll.OpenDriver
OpenDriver.argtypes = [c_uint64]
OpenDriver.restype = c_int

OpenUSBDevice = op710m_dll.OpenUSBDevice
OpenUSBDevice.argtypes = [c_int, POINTER(c_uint64)]
OpenUSBDevice.restype = c_int

ReadAnalog = op710m_dll.ReadAnalog
ReadAnalog.argtypes = [POINTER(c_int), POINTER(c_int), POINTER(c_int)]
ReadAnalog.restype = c_int

ReadChannelBuffer = op710m_dll.ReadChannelBuffer
ReadChannelBuffer.argtypes = [c_int, POINTER(c_double)]
ReadChannelBuffer.restype = c_int

ReadChannelBufferRaw = op710m_dll.ReadChannelBufferRaw
ReadChannelBufferRaw.argtypes = [c_int, c_uint16, POINTER(c_byte)]
ReadChannelBufferRaw.restype = c_int

ReadLoss = op710m_dll.ReadLoss
ReadLoss.argtypes = [POINTER(c_double)]
ReadLoss.restype = c_int

ReadPower = op710m_dll.ReadPower
ReadPower.argtypes = [POINTER(c_double)]
ReadPower.restype = c_int

ReferencePower = op710m_dll.ReferencePower
ReferencePower.argtypes = [POINTER(c_double)]
ReferencePower.restype = c_int

RemoteMode = op710m_dll.RemoteMode
RemoteMode.argtypes = [c_int]
RemoteMode.restype = c_int

SelectModule = op710m_dll.SelectModule
SelectModule.argtypes = [c_int]
SelectModule.restype = c_int

SetAbsolute = op710m_dll.SetAbsolute
SetAbsolute.argtypes = []
SetAbsolute.restype = c_int

SetActiveChannel = op710m_dll.SetActiveChannel
SetActiveChannel.argtypes = [c_int]
SetActiveChannel.restype = c_int

SetAutoRange = op710m_dll.SetAutoRange
SetAutoRange.argtypes = [c_int]
SetAutoRange.restype = c_int

SetGain = op710m_dll.SetGain
SetGain.argtypes = [c_int]
SetGain.restype = c_int

SetOPMMode = op710m_dll.SetOPMMode
SetOPMMode.argtypes = [c_int]
SetOPMMode.restype = c_int

SetReference = op710m_dll.SetReference
SetReference.argtypes = []
SetReference.restype = c_int

SetSamplingSpeed = op710m_dll.SetSamplingSpeed
SetSamplingSpeed.argtypes = [c_byte]
SetSamplingSpeed.restype = c_int

SetWavelength = op710m_dll.SetWavelength
SetWavelength.argtypes = [c_int]
SetWavelength.restype = c_int


# Enumerations
class ErrorCodes(Enum):
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


class ModuleID(Enum):
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


class Wavelengths(Enum):
    """Commonly supported wavelengths (in nanometers)."""

    nm850 = 850
    nm980 = 980
    nm1300 = 1300
    nm1310 = 1310
    nm1480 = 1480
    nm1550 = 1550
    nm1625 = 1625
    nm1650 = 1650


class OPM150:
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

    def __init__(self, verbose: bool = True, power_unit=1):
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
            _ret = op710m_dll.CloseDriver()
            self._check(self.get_func_name(), _ret)
            self._is_connection_open = False
            self.logger.info(f"Driver closed.")

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

        handle = op710m_dll.ActiveModule(c_int(module))
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
        handle = c_uint64()
        _ret = op710m_dll.OpenUSBDevice(c_int(dev_number), byref(handle))
        self._check(self.get_func_name(), _ret)
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
        _ret = op710m_dll.OpenDriver(c_uint64(handle))
        self._check(self.get_func_name(), _ret)
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
        _count = c_int()
        _ret = op710m_dll.GetUSBDeviceCount(byref(_count))
        self._check(self.get_func_name(), _ret)
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
        _description = c_char_p()
        _dev_number = c_int(dev_number)
        _ret = op710m_dll.GetUSBDeviceDescription(_dev_number, byref(_description))
        self._check(self.get_func_name(), _ret)
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
        _serial = c_char_p()
        _device_number = c_int(self.device_number)
        _ret = op710m_dll.GetUSBSerialNumber(_device_number, byref(_serial))
        self._check(self.get_func_name(), _ret)
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
        _have_error = c_bool()
        _device_number = c_int(self.device_number)
        _ret = op710m_dll.GetUSBStatus(_device_number, byref(_have_error))
        self._check(self.get_func_name(), _ret)
        return _have_error.value

    # @property
    # def dll_revision(self) -> int:
    #     """
    #     Return the loaded DLL revision number.

    #     Returns
    #     -------
    #     int
    #         DLL revision code.
    #     """
    #     _revision = op710m_dll.GetDLLRev()
    #     self.logger.debug(f"DLL revision: {_revision}")
    #     return _revision

    # @property
    # def fw_revision(self) -> int:
    #     """
    #     Return the device firmware revision.

    #     Returns
    #     -------
    #     int
    #         Firmware revision code.
    #     """
    #     _revision = op710m_dll.GetFWRevision()
    #     self.logger.debug(f"FW revision: {_revision}")
    #     return _revision

    # @property
    # def status(self) -> ErrorCodes:
    #     """
    #     Get the initialization/status code from the DLL.

    #     Returns
    #     -------
    #     ErrorCodes
    #         Enum representing the DLL/device status.
    #     """
    #     _status = c_int()
    #     _status = op710m_dll.GetDLLStatus()
    #     # do not raise here; caller can interpret
    #     self.logger.debug(f"DLL status code: {_status}")
    #     return ErrorCodes(_status)

    @property
    def active_channel(self) -> int:
        """
        Get the current active channel.

        Returns
        -------
        int
            Index of the currently active optical input channel.
        """
        _ch = c_int()
        _ret = op710m_dll.GetActiveChannel(byref(_ch))
        self._check(self.get_func_name(), _ret)
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
        _ret = op710m_dll.SetActiveChannel(c_int(ch))
        self._check(self.get_func_name(), _ret)
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
        temperature = c_double()
        _ret = op710m_dll.GetTemperature(byref(temperature), unit)
        self._check(self.get_func_name(), _ret)
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
        wl = c_int()
        idx = c_int()
        ct = c_int()
        _ret = op710m_dll.GetWavelength(byref(wl), byref(idx), byref(ct))
        self._check(self.get_func_name(), _ret)
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
        _wavelength = c_int(wl.value)
        _ret = op710m_dll.SetWavelength(_wavelength)
        self._check(self.get_func_name(), _ret)
        self.logger.debug(f"Wavelength set to {wl.value} nm")

    def read_analog(self) -> int:
        """
        Read the raw ADC value of the currently active OPM channel.

        Returns
        -------
        int
            Raw analog value.
        """
        _analog = c_int()
        _gain = c_int()
        _mode = c_int()
        _ret = op710m_dll.ReadAnalog(byref(_analog), byref(_gain), byref(_mode))
        self._check(self.get_func_name(), _ret)
        self.logger.debug(f"Analog: {_analog.value}, gain={_gain.value}, mode={_mode.value}")
        return _analog.value

    def _format_power(self, value_dbm: float) -> float:
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
            self.logger.debug(f"Power: {value_dbm:.3f} dBm")
            return value_dbm
        elif self.power_unit == 1:  # W
            pw = self._convert_to_linear(value_dbm)
            self.logger.debug(f"Power: {pw:.3e} W (converted)")
            return pw
        else:
            raise ValueError("power_unit must be either 0 (dBm) or 1 (W).")
    
    def convert_analog_reading(self, analog: int, gain: int) -> float:
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
        power = c_double()
        ret = op710m_dll.ConvertPower(c_int(analog), c_int(gain), byref(power))
        self._check("ConvertPower", ret)
        return self._format_power(power.value)
    
    def read_power(self) -> float:
        """
        Read optical power from the active channel.
    
        Returns
        -------
        float
            Power in dBm or W depending on self.power_unit.
        """
        power = c_double()
        ret = op710m_dll.ReadPower(byref(power))
        self._check("ReadPower", ret)
        return self._format_power(power.value)

    def update_channels_buffer(self) -> None:
        """
        Acquire power for all channels simultaneously and update internal buffers.
        """
        _ret = op710m_dll.GetChannelBuffer()
        self._check("GetChannelBuffer", _ret)
        self.logger.debug("Channel buffer updated.")

    def read_channel_buffer_power(self, ch: int) -> float:
        """
        Read buffered power measurement for a specific channel.
    
        Parameters
        ----------
        ch : int
            Channel number (1–24). `update_channels_buffer()` must be called before.
    
        Returns
        -------
        float
            Power in dBm or W depending on self.power_unit.
        """
        power = c_double()
        ret = op710m_dll.ReadChannelBuffer(c_int(ch), byref(power))
        self._check("ReadChannelBuffer", ret)
        self.logger.debug(f"Ch{ch}: {power.value:.3f} raw units")
        return self._format_power(power.value)
    
    def read_multiple_channels(
        self, channels: list[int] = [i + 1 for i in range(24)], sleep: float = 0.1
    ) -> list[float]:
        """
        Read power sequentially from a list of channels.
    
        Parameters
        ----------
        channels : list[int], default=[1..24]
            List of channels to read (1-based).
        sleep : float, default=0.1
            Delay (s) between reads, required by hardware timing.
    
        Returns
        -------
        list[float]
            Power readings for all requested channels, in dBm or W.
        """
        self.update_channels_buffer()
        time.sleep(sleep)
    
        powers = [self.read_channel_buffer_power(ch) for ch in channels]
        self.logger.debug(f"Read {len(channels)} channels: {channels}")
        return powers
    
    def read_relative_power(self) -> float:
        """
        Read relative power from the active channel.
    
        Returns
        -------
        float
            Power difference in dB if power_unit=0, or ratio if power_unit=1.
    
        Notes
        -----
        `set_reference_power()` must be called first.
        """
        loss = c_double()
        ret = op710m_dll.ReadLoss(byref(loss))
        self._check("ReadLoss", ret)
        self.logger.debug(f"Relative power raw value: {loss.value:.3f}")
    
        if self.power_unit == 0:
            self.logger.debug(f"Relative power: {loss.value:.3f} dB")
            return loss.value
        elif self.power_unit == 1:
            ratio = self._convert_to_linear_relative(loss.value)
            self.logger.debug(f"Relative power ratio: {ratio:.4f}")
            return ratio
        else:
            raise ValueError("power_unit must be 0 (dBm) or 1 (W).")

    def set_autorange_active_channel(self, autorange: bool) -> None:
        """
        Enable or disable Auto-Range for the active channel.

        Parameters
        ----------
        autorange : bool
            True to enable Auto-Range, False to hold range.

        Notes
        -----
        Auto-Range setting is shared between adjacent channels.
        """
        _range = c_int(1) if autorange else c_int(0)
        _ret = op710m_dll.SetAutoRange(_range)
        self._check(self.get_func_name(), _ret)
        self.logger.debug(f"Autorange {'enabled' if autorange else 'disabled'} on active channel.")

    def set_autorange_all_channels(self, autorange: bool) -> None:
        """
        Apply Auto-Range setting to all channels.

        Parameters
        ----------
        autorange : bool
            True to enable Auto-Range, False to disable.

        Notes
        -----
        Auto-Range applies to pairs of adjacent channels.
        A small delay (0.1 s) is inserted between each channel update.
        """
        _current = self.active_channel
        for i in range(1, 25):
            if i % 2 == 1:
                self.active_channel = i
                time.sleep(0.1)
                self.set_autorange_active_channel(autorange)
        self.active_channel = _current
        self.logger.debug(f"Autorange {'enabled' if autorange else 'disabled'} for all channels.")

    @property
    def gain(self) -> int:
        """
        Get the gain value for the active channel.

        Returns
        -------
        int
            Gain level (0–7).
        """
        _analog = c_int()
        _gain = c_int()
        _mode = c_int()
        _ret = op710m_dll.ReadAnalog(byref(_analog), byref(_gain), byref(_mode))
        self._check(self.get_func_name(), _ret)
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
        _gain = c_int(gain)
        _ret = op710m_dll.SetGain(_gain)
        self._check(self.get_func_name(), _ret)
        self.logger.debug(f"Gain set to {gain} (Auto-Range disabled)")

    def set_gain_all_channels(self, gain: Literal[0, 1, 2, 3, 4, 5, 6, 7]) -> None:
        """
        Set the gain for all channels.

        Parameters
        ----------
        gain : int
            Gain level (0–7). Automatically disables Auto-Range.
        """
        _current = self.active_channel
        for i in range(1, 25):
            if i % 2 == 1:
                self.active_channel = i
                time.sleep(0.1)
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
        _speed = c_byte(speed)
        _ret = op710m_dll.SetSamplingSpeed(_speed)
        self._check(self.get_func_name(), _ret)
        self.logger.debug(f"Sampling speed set to {speed}")

    def _convert_to_linear(self, value: float) -> float:
        """Convert power from dBm to W."""
        return math.pow(10, value / 10 - 3)

    def _convert_to_linear_relative(self, value: float) -> float:
        """Convert relative power from dB to a linear ratio."""
        return math.pow(10, value / 10)

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
        pm = OPM150(power_unit=0)
    except RuntimeError as e:
        print(f"Inizialization error: {e}")
        sys.exit(1)

    try:
        print("\n--- Device Info ---")
        print(f"USB serial number: {pm.USB_serial_number}")

        print("\n--- Temperature ---")
        temp_c = pm.temperature(unit=1)
        print(f"Temperature: {temp_c:.2f} °C")
        
        print("\n--- Wavelength ---")
        wl = pm.wavelength
        print(f"Wavelength: {wl.value} nm")
        pm.wavelength = 980
        print(f"Wavelength: {pm.wavelength.value} nm")

        print("\n--- Power on multiple channels ---")
        chs = list(range(1,25))
        powers = pm.read_multiple_channels(channels=chs, sleep=0.2)
        for ch, p in zip(chs, powers):
            print(f"CH {ch}: {p} dBm")

    except Exception as e:
        print(f"Communication Error: {e}")

    finally:
        pm.close()

