import logging
import math
import sys
import time
from typing import Literal, Optional


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

    def __init__(self, verbose: bool = True):
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
        self._is_connection_open = False

        # get device count
        _dev_count = self.USB_device_count
        if self.verbose:
            print(f"[OPM150] Device count : {_dev_count}")
        else:
            self.logger.debug(f"Device count : {_dev_count}")

        # iterate through devices to find the first OP710
        self.device_number = None
        for i in range(_dev_count):
            _description = self.get_USB_device_description(i)
            self.logger.debug(f"Description [{i}] : {_description}")
            if "OP710" in _description:
                self.device_number = i
                break

        if self.device_number is None:
            raise RuntimeError("[OPM150] No OP710 device found")

        if self.verbose:
            print(f"[OPM150] Device number : {self.device_number}")

        # open USB device and driver
        self._handle = self.open_USB_device(self.device_number)
        if self.verbose:
            print(f"[OPM150] USB Handle : {self._handle}")
        self._is_connection_open = self.open_driver(self._handle)
        if self.verbose:
            print(f"[OPM150] Is connection open : {self._is_connection_open}")

        # internal state variables
        self._remote_mode = None
        self._sampling_speed = None  # probably channel-related; untested here
        self.remote_mode = True
        # record power_unit as software flag (device cannot change unit on ours)
        self.power_unit: Literal[0, 1] = (
            0  # 0 -> dBm (default), 1 -> W (converted in software)
        )

        # available wavelengths enum from DLL
        self.available_wavelengths = op710m_dll.Wavelengths

        # ensure active_channel is set explicitly (DLL getter may reset on reopen)
        self.active_channel = 1

    def __del__(self):
        """
        Destructor: ensure the connection is closed when the object is garbage-collected.
        """
        try:
            self.close()
        except Exception:
            # keep destructor silent on errors
            pass

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
        _module = c_int(module)
        _handle = c_int()
        _handle = op710m_dll.ActiveModule(_module)
        self.logger.debug(f"ActiveModule({module}) -> {_handle}")
        return _handle

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
        _dev_number = c_int(dev_number)
        _handle = c_uint64()
        _ret = op710m_dll.OpenUSBDevice(_dev_number, byref(_handle))
        self._check(self.get_func_name(), _ret)
        return _handle.value

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
        _handle = c_uint64(handle)
        _ret = op710m_dll.OpenDriver(_handle)
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
        _ret = op710m_dll.op_dll.GetUSBDeviceCount(byref(_count))
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

    @property
    def dll_revision(self) -> int:
        """
        Return the loaded DLL revision number.

        Returns
        -------
        int
            DLL revision code.
        """
        _revision = op710m_dll.GetDLLRev()
        self.logger.debug(f"DLL revision: {_revision}")
        return _revision

    @property
    def fw_revision(self) -> int:
        """
        Return the device firmware revision.

        Returns
        -------
        int
            Firmware revision code.
        """
        _revision = op710m_dll.GetFWRevision()
        self.logger.debug(f"FW revision: {_revision}")
        return _revision

    @property
    def status(self) -> op710m_dll.ErrorCodes:
        """
        Get the initialization/status code from the DLL.

        Returns
        -------
        op710m_dll.ErrorCodes
            Enum representing the DLL/device status.
        """
        _status = c_int()
        _status = op710m_dll.GetDLLStatus()
        # do not raise here; caller can interpret
        self.logger.debug(f"DLL status code: {_status}")
        return op710m_dll.ErrorCodes(_status)

    @property
    def module_ID(self) -> op710m_dll.ModuleID:
        """
        Return the module internal ID (product code).

        Returns
        -------
        op710m_dll.ModuleID
            Enum value for the module ID.
        """
        _id = c_int()
        _ret = op710m_dll.GetModuleID(byref(_id))
        self._check(self.get_func_name(), _ret)
        return op710m_dll.ModuleID(_id.value)

    @property
    def selected_device(self) -> int:
        """
        Get the currently selected module/device number.

        Returns
        -------
        int
            Module/device number.
        """
        _number = c_int()
        _ret = op710m_dll.GetModuleNumber(byref(_number))
        self._check(self.get_func_name(), _ret)
        return _number.value

    @selected_device.setter
    def selected_device(self, device: int) -> None:
        """
        Select a device/module for subsequent USB operations.

        Parameters
        ----------
        device : int
            Module/device number to select.
        """
        _device = c_int(device)
        _ret = op710m_dll.SelectModule(_device)
        self._check(self.get_func_name(), _ret)
        if self.verbose:
            print(f"[OPM150] Selected device set to {device}")

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
        if self.verbose:
            print(f"[OPM150] Active channel: {_ch.value}")
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
        _ch = c_int(ch)
        _ret = op710m_dll.SetActiveChannel(_ch)
        self._check(self.get_func_name(), _ret)
        if self.verbose:
            print(f"[OPM150] Active channel set to {ch}")

    def read_temperature(self, unit: Literal[0, 1, 2] = 1) -> float:
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
        _temperature = c_double()
        _ret = op710m_dll.GetTemperature(byref(_temperature), unit)
        self._check(self.get_func_name(), _ret)
        if self.verbose:
            print(f"[OPM150] Temperature: {_temperature.value:.2f} (unit={unit})")
        return _temperature.value

    @property
    def wavelength(self) -> op710m_dll.Wavelengths:
        """
        Get the current measurement wavelength of the active channel.

        Returns
        -------
        op710m_dll.Wavelengths
            Enum value representing the active wavelength.
        """
        _wavelength = c_int()
        _index = c_int()
        _count = c_int()
        _ret = op710m_dll.GetWavelength(
            byref(_wavelength), byref(_index), byref(_count)
        )
        self._check(self.get_func_name(), _ret)
        if self.verbose:
            print(f"[OPM150] Wavelength: {_wavelength.value} nm (index={_index.value})")
        return op710m_dll.Wavelengths(_wavelength.value)

    @wavelength.setter
    def wavelength(self, wavelength: int) -> None:
        """
        Set the measurement wavelength for the active channel.

        Parameters
        ----------
        wavelength : int
            Wavelength value (must be one of `op710m_dll.Wavelengths`).

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
        print(f"[OPM150] Wavelength set to {wl.value} nm")

    def set_next_wavelength(self) -> op710m_dll.Wavelengths:
        """
        Advance to the next wavelength in the list of available wavelengths.

        Returns
        -------
        op710m_dll.Wavelengths
            The new wavelength value after the change.
        """
        _wavelength = c_int()
        _index = c_int()
        _count = c_int()
        _ret = op710m_dll.NextWavelength(
            byref(_wavelength), byref(_index), byref(_count)
        )
        self._check(self.get_func_name(), _ret)
        wl = op710m_dll.Wavelengths(_wavelength.value)
        print(f"[OPM150] Next wavelength set: {wl.name} ({wl.value} nm)")
        return wl

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
        if self.verbose:
            print(
                f"[OPM150] Analog: {_analog.value}, gain={_gain.value}, mode={_mode.value}"
            )
        return _analog.value

    def convert_analog_reading(self, analog: int, gain: int) -> float:
        """
        Convert raw ADC and gain values into an optical power measurement.

        Parameters
        ----------
        analog : int
            Raw ADC value (from `read_analog()`).
        gain : int
            Channel gain (0–7).

        Returns
        -------
        float
            Power in dBm or W depending on `self.power_unit`.
        """
        _analog = c_int(analog)
        _gain = c_int(gain)
        _power = c_double()
        _ret = op710m_dll.ConvertPower(_analog, _gain, byref(_power))
        self._check(self.get_func_name(), _ret)
        power_dbm = _power.value
        if self.power_unit == 0:
            if self.verbose:
                print(f"[OPM150] Power: {power_dbm:.3f} dBm")
            return power_dbm
        elif self.power_unit == 1:
            pw = self._convert_to_linear(power_dbm)
            if self.verbose:
                print(f"[OPM150] Power: {pw:.3e} W (converted)")
            return pw
        else:
            raise ValueError("power_unit must be 0 (dBm) or 1 (W).")

    def read_power(self) -> float:
        """
        Read optical power from the active channel.

        Returns
        -------
        float
            Power in [dBm] if `power_unit=0`, or [W] if `power_unit=1`.
        """
        _power = c_double()
        _ret = op710m_dll.ReadPower(byref(_power))
        self._check(self.get_func_name(), _ret)
        val = _power.value
        if self.power_unit == 0:
            print(f"[OPM150] Power: {val:.3f} dBm")
            return val
        elif self.power_unit == 1:
            pw = self._convert_to_linear(val)
            print(f"[OPM150] Power: {pw:.3e} W (converted)")
            return pw
        else:
            raise ValueError("power_unit must be 0 (dBm) or 1 (W).")

    def update_channels_buffer(self) -> None:
        """
        Acquire power for all channels simultaneously and update internal buffers.
        """
        _ret = op710m_dll.GetChannelBuffer()
        self._check(self.get_func_name(), _ret)
        if self.verbose:
            print("[OPM150] Channel buffer updated")

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
            Power in dBm or W depending on `self.power_unit`.
        """
        _ch = c_int(ch)
        _power = c_double()
        _ret = op710m_dll.ReadChannelBuffer(_ch, byref(_power))
        self._check(self.get_func_name(), _ret)
        val = _power.value
        if self.power_unit == 0:
            if self.verbose:
                print(f"[OPM150] Ch{ch}: {val:.3f} dBm")
            return val
        elif self.power_unit == 1:
            pw = self._convert_to_linear(val)
            if self.verbose:
                print(f"[OPM150] Ch{ch}: {pw:.3e} W")
            return pw
        else:
            raise ValueError("power_unit must be 0 (dBm) or 1 (W).")

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
        powers = []
        for ch in channels:
            powers.append(self.read_channel_buffer_power(ch))
        print(f"[OPM150] Read {len(channels)} channels")
        return powers

    def read_relative_power(self) -> float:
        """
        Read relative power from the active channel.

        Returns
        -------
        float
            Power difference in [dB] if `power_unit=0`,
            or dimensionless ratio if `power_unit=1`.

        Notes
        -----
        `set_reference_power()` must be called first.
        """
        _loss = c_double()
        _ret = op710m_dll.ReadLoss(byref(_loss))
        self._check(self.get_func_name(), _ret)
        val = _loss.value
        if self.power_unit == 0:
            print(f"[OPM150] Relative power: {val:.3f} dB")
            return val
        elif self.power_unit == 1:
            pw = self._convert_to_linear_relative(val)
            print(f"[OPM150] Relative power ratio: {pw:.4f}")
            return pw
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
        if self.verbose:
            print(
                f"[OPM150] Autorange {'enabled' if autorange else 'disabled'} on active channel"
            )

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
        print(
            f"[OPM150] Autorange {'enabled' if autorange else 'disabled'} for all channels"
        )

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
        if self.verbose:
            print(f"[OPM150] Gain (ch={self.active_channel}): {_gain.value}")
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
        print(f"[OPM150] Gain set to {gain} (Auto-Range disabled)")

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
        print(f"[OPM150] Gain set to {gain} for all channels")

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
        print(f"[OPM150] Sampling speed set to {speed}")

    def get_reference_power(self) -> float:
        """
        Get the stored reference power value.

        Returns
        -------
        float
            Power reference in dBm or W depending on `power_unit`.
        """
        _ref = c_double()
        _ret = op710m_dll.ReferencePower(byref(_ref))
        self._check(self.get_func_name(), _ret)
        val = _ref.value
        if self.power_unit == 0:
            if self.verbose:
                print(f"[OPM150] Reference power: {val:.3f} dBm")
            return val
        else:
            pw = self._convert_to_linear(val)
            if self.verbose:
                print(f"[OPM150] Reference power: {pw:.3e} W")
            return pw

    def set_reference_power(self) -> None:
        """
        Set the current power as the new reference value.
        """
        _ret = op710m_dll.SetReference()
        self._check(self.get_func_name(), _ret)
        print("[OPM150] Reference power updated")

    # ------------------- Internal helpers -------------------
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
        code = op710m_dll.ErrorCodes(err_code)
        if code in (op710m_dll.ErrorCodes.OK_0, op710m_dll.ErrorCodes.OK_1):
            if self.verbose:
                print(f"[OPM150] {func_name}: {code.name}")
        else:
            raise Exception(f"[OPM150] {func_name} failed: {code.name}")
