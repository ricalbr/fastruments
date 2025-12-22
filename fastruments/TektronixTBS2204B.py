"""
TEKTRONIX TBS2000

This module provides a high-level Python interface for controlling Tektronix
TBS2000 series digital oscilloscopes via USB connection using the PyVISA
library.

The `TBS2204B` class enables configuration, measurement, and waveform
acquisition using standard SCPI commands, according to the official
Tektronix TBS2000 Programmer Manual (document 077-1149-02).

It is designed for laboratory automation and testing setups where direct
Python control of oscilloscopes is required, e.g. in integrated photonics
and optoelectronic experiments.
"""

import numpy as np
import pyvisa
from Instrument import Instrument


class TBS2204B(Instrument):
    """
    High-level interface for Tektronix TBS2204B Digital Oscilloscope.

    Provides a Pythonic abstraction for communicating with the TBS2204B
    using SCPI commands via USB. Supports waveform acquisition, configuration
    of channels, timebase, and trigger settings, and includes automation
    utilities for experimental setups.

    Parameters
    ----------
    resource : str
        VISA resource string of the connected oscilloscope.
        Example: ``'USB::0x0699::0x03C7::C010302::INSTR'``.
    timeout : int, optional
        Communication timeout in milliseconds (default: ``20000``).
    verbose : bool, optional
        If ``True``, prints diagnostic and status messages (default: ``True``).

    Attributes
    ----------
    inst : pyvisa.Resource
        Active VISA resource representing the instrument connection.
    verbose : bool
        Verbosity flag controlling console output.
    timeout : int
        VISA communication timeout (milliseconds).

    Examples
    --------
    >>> from lib.instruments.tbs2204b.core import TBS2204B
    >>> scope = TBS2204B('USB::0x0699::0x03C7::C010302::INSTR', verbose=True)
    [TBS2204B] IDN: TEKTRONIX,TBS2204B,C010302,CF:91.1CT FV:v1.27.19; FPGA:v2.18;.
    [TBS2204B] Connected successfully.
    >>> scope.autoset()
    [TBS2204B] Autoset executed successfully.
    >>> scope.set_channel_scale(1, 0.5)
    [TBS2204B] CH1 scale set to 0.5 V/div.
    >>> scope.single_acquisition()
    [TBS2204B] Single-sequence acquisition started.
    [TBS2204B] Single-sequence acquisition completed.
    >>> t, v = scope.get_waveform(1)
    [TBS2204B] Donwloading data points from CH1...
    [TBS2204B] Acquired 2000 points from CH1.
    >>> scope.close()
    [TBS2204B] Connection closed.
    """

    __NUM_CHANNELS = 4

    __TIMEBASE_SCALES = {
        2e-9,
        5e-9,
        10e-9,
        20e-9,
        50e-9,
        100e-9,
        200e-9,
        500e-9,
        1e-6,
        2e-6,
        5e-6,
        10e-6,
        20e-6,
        50e-6,
        100e-6,
        200e-6,
        500e-6,
        1e-3,
        2e-3,
        5e-3,
        10e-3,
        20e-3,
        50e-3,
        0.1,
        0.2,
        0.5,
        1,
        2,
        5,
        10,
        20,
        50,
        100,
    }

    __COUPLING_MODES = {"AC", "DC", "GND"}

    __TRIGGER_MODES = {"AUTO", "NORM"}

    __TRIGGER_SLOPES = {"RISE", "FALL"}

    __RECORD_LENGTHS = {1_000, 2_000, 20_000, 200_000, 2_000_000, 5_000_000}

    __VERTICAL_GAINS = {
        0.001,
        0.002,
        0.005,
        0.01,
        0.02,
        0.05,
        0.1,
        0.2,
        0.5,
        1,
        2,
        5,
        10,
        20,
        50,
        100,
        200,
        500,
        1000,
    }

    __VERTICAL_POSITION_RANGE = (-5.0, 5.0)

    __VERTICAL_SCALES = (
        {  # This is valid only for gain = 1, otherwise it scales accordingly.
            2e-3,
            5e-3,
            1e-2,
            2e-2,
            5e-2,
            1e-1,
            2e-1,
            5e-1,
            1.0,
            2.0,
            5.0,
        }
    )

    __BANDWIDTHS = {20_000_000, 200_000_000}

    def __init__(
        self, resource: str, timeout: int = 20000, verbose: bool = True
    ) -> None:
        """
        Initialize connection to the Tektronix TBS2204B oscilloscope.

        Raises
        ------
        ConnectionError
            If the VISA resource cannot be opened.
        RuntimeError
            If querying the instrument identification (IDN) fails.
        """
        self.verbose = verbose
        self.timeout = timeout
        self.resource = resource
        self.connect()

    # ------------------------------------------------------------------
    # General communication and status
    # ------------------------------------------------------------------
    def connect(self) -> None:
        try:
            rm = pyvisa.ResourceManager()
            self.inst = rm.open_resource(self.resource)
            self.inst.timeout = self.timeout
        except Exception as e:
            raise ConnectionError(
                f"[TBS2204B][ERROR] Could not connect to oscilloscope: {e}"
            )
        try:
            self.idn()
            if self.verbose:
                print("[TBS2204B] Connected successfully.")
        except Exception as e:
            raise RuntimeError(f"[TBS2204B][ERROR] Failed to query IDN: {e}")

    def idn(self) -> str:
        """
        Query the oscilloscope identification string.

        Returns
        -------
        str
            Full identification string.
        """
        idn = self.inst.query("*IDN?").strip()
        if self.verbose:
            print(f"[TBS2204B] IDN: {idn}.")
        return idn

    def clear(self) -> None:
        """
        Clear all status registers of the oscilloscope.
        """
        self.inst.write("*CLS")
        if self.verbose:
            print("[TBS2204B] Status registers cleared.")

    def reset(self) -> None:
        """
        Reset the oscilloscope to factory default configuration.
        """
        self.inst.write("*RST")
        if self.verbose:
            print("[TBS2204B] Instrument reset to defaults.")

    def autoset(self) -> None:
        """
        Automatically configure the oscilloscope for a stable waveform display.
        """
        self.inst.write(":AUTOS EXEC")
        if self.verbose:
            print("[TBS2204B] Autoset executed successfully.")

    def close(self) -> None:
        """
        Close the VISA connection to the instrument.

        Notes
        -----
        Should always be called before program termination to release the USB resource.

        Raises
        ------
        RuntimeError
            If the resource cannot be cleanly closed.
        """
        try:
            self.inst.close()
            if self.verbose:
                print("[TBS2204B] Connection closed.")
        except Exception as e:
            raise RuntimeError(f"[TBS2204B][ERROR] Failed to close connection: {e}")

    # ------------------------------------------------------------------
    # Channel control
    # ------------------------------------------------------------------
    def set_channel_display(self, channel: int, state: bool) -> None:
        """
        Enable or disable a specific channel display.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.
        state : bool
            ``True`` to enable display, ``False`` to disable.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        self.inst.write(f":SEL:CH{channel} {'ON' if state else 'OFF'}")
        if self.verbose:
            print(f"[TBS2204B] CH{channel} display set to {'ON' if state else 'OFF'}.")

    def set_channel_scale(self, channel: int, scale: float) -> None:
        """
        Set vertical scale for a specific channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__NUM_CHANNELS`.
        scale : float
            Vertical scale (V/div). The valid values depend on the channel gain.
            See Notes.

        Notes
        -----
        The valid vertical scales are not absolute. The oscilloscope enforces
        discrete scale values defined in `__VERTICAL_SCALES` *after* the
        channel gain is applied.

        A scale value is valid only if:

            scale * gain ∈ __VERTICAL_SCALES

        where the gain is obtained from `get_channel_gain(channel)`.

        Therefore:
            - changing the channel gain modifies the valid scale values
            - setting the scale may fail if the gain was changed beforehand
            - recommended workflow: **set gain first, then set scale**.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
            If the requested vertical scale is not valid for the channel’s current gain.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        gain = self.get_channel_gain(channel)
        if scale * gain not in self.__VERTICAL_SCALES:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid scale {scale} V/div for gain {gain}. "
                f"Valid vertical scales are: {sorted(self.__VERTICAL_SCALES/gain)}."
            )
        self.inst.write(f":CH{channel}:SCA {scale}")
        if self.verbose:
            print(f"[TBS2204B] CH{channel} scale set to {scale} V/div.")

    def set_channel_coupling(self, channel: int, mode: str) -> None:
        """
        Set the coupling mode for a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.
        mode : str
            Coupling mode. Valid values are those listed in
            `__COUPLING_MODES`.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
            If the coupling mode is not supported.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        mode = mode.upper()
        if mode not in self.__COUPLING_MODES:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid coupling mode '{mode}'. "
                f"Valid options: {sorted(self.__COUPLING_MODES)}."
            )
        self.inst.write(f":CH{channel}:COUP {mode}")
        if self.verbose:
            print(f"[TBS2204B] CH{channel} coupling set to {mode}.")

    def set_channel_position(self, channel: int, position: float) -> None:
        """
        Set vertical position for a specific channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.
        position : float
            Vertical position in divisions. Valid range (min, max) is defined in
            `__VERTICAL_POSITION_RANGE`. Choose negative values for strictly
            positive signals and vice versa.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
            If the vertical position is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        low, high = self.__VERTICAL_POSITION_RANGE
        if not (low <= position <= high):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid CH{channel} position {position}. "
                f"Valid range: [{low}, {high}] div."
            )
        self.inst.write(f":CH{channel}:POS {position}")
        if self.verbose:
            print(f"[TBS2204B] CH{channel} vertical position set to {position} div.")

    def set_channel_gain(self, channel: int, gain: float) -> None:
        """
        Set the vertical gain for a specific channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.
        gain : float
            Vertical gain multiplier (e.g. 10x must be set as 0.1). Valid
            values are those listed in `__VERTICAL_GAINS`.

        Notes
        ----------
            This method will affect also the channel vertical scale.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
            If the gain value is not one of the supported values.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )

        if gain not in self.__VERTICAL_GAINS:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid gain {gain}. "
                f"Valid values: {sorted(self.__VERTICAL_GAINS)}."
            )

        self.inst.write(f":CH{channel}:PRO:GAIN {gain}")
        if self.verbose:
            print(f"[TBS2204B] CH{channel} gain set to {gain}.")

    def set_channel_bandwidth(self, channel: int, bandwidth: float) -> None:
        """
        Set the analog bandwidth limit for a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.
        bandwidth : float
            Bandwidth limit in Hz. Valid values are those listed in
            `__CHANNEL_BANDWIDTHS`.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
            If the bandwidth value is not supported.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )

        if bandwidth not in self.__BANDWIDTHS:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid bandwidth {bandwidth}. "
                f"Valid values: {sorted(self.__BANDWIDTHS)}."
            )
        self.inst.write(f":CH{channel}:BAN {bandwidth}")
        if self.verbose:
            print(f"[TBS2204B] CH{channel} bandwidth set to {bandwidth/1e6} MHz.")

    def get_channel_position(self, channel: int) -> float:
        """
        Get vertical position of a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        float
            Vertical position in divisions.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        pos = float(self.inst.query(f":CH{channel}:POS?"))
        if self.verbose:
            print(f"[TBS2204B] CH{channel} vertical position is {pos} div.")
        return pos

    def get_channel_display(self, channel: int) -> bool:
        """
        Get display status of a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        bool
            ``True`` if channel display is enabled, ``False`` otherwise.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        state = self.inst.query(f":SEL:CH{channel}?").strip()
        if self.verbose:
            print(
                f"[TBS2204B] CH{channel} display is {'ON' if state == '1' else 'OFF'}."
            )
        return state == "1"

    def get_channel_scale(self, channel: int) -> float:
        """
        Get vertical scale of a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        float
            Vertical scale in V/div.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(f"[TBS2204B][ERROR] Invalid channel {channel}.")
        scale = float(self.inst.query(f":CH{channel}:SCA?"))
        if self.verbose:
            print(f"[TBS2204B] CH{channel} scale is {scale} V/div.")
        return scale

    def get_channel_coupling(self, channel: int) -> str:
        """
        Get coupling mode of a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        str
            Coupling mode as in `__COUPLING_MODES`.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(f"[TBS2204B][ERROR] Invalid channel {channel}.")
        coupling = self.inst.query(f":CH{channel}:COUP?").strip()
        if self.verbose:
            print(f"[TBS2204B] CH{channel} coupling is {coupling}.")
        return coupling

    def get_channel_gain(self, channel: int) -> float:
        """
        Get the vertical gain of a specific channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        float
            Vertical gain multiplier (e.g. 10x corresponds to 0.1).

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        gain = float(self.inst.query(f":CH{channel}:PRO:GAIN?"))
        if self.verbose:
            print(f"[TBS2204B] CH{channel} gain is {gain}.")
        return gain

    def get_channel_bandwidth(self, channel: int) -> float:
        """
        Get the analog bandwidth limit for a channel.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        float
            Bandwidth in hertz.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        bandwidth = float(self.inst.query(f":CH{channel}:BAN?"))
        if self.verbose:
            print(f"[TBS2204B] CH{channel} bandwidth is {bandwidth/1e6} MHz.")
        return bandwidth

    # ------------------------------------------------------------------
    # Timebase configuration
    # ------------------------------------------------------------------
    def set_timebase_scale(self, scale: float) -> None:
        """
        Set horizontal timebase scale.

        Parameters
        ----------
        scale : float
            Time scale per division (s/div). Valid values are in
            `__TIMEBASE_SCALES`.

        Notes
        -----
        Changing the timebase affects the waveform returned by `get_waveform()`
        only if the oscilloscope adjusts its sampling rate accordingly. When the
        horizontal scale is within a range where the instrument remains at its
        maximum sampling rate (1 GSa/s), the sample interval (``XINCR``) does not
        change. As a consequence, the downloaded waveform may look identical even
        if different timebase settings were applied.

        Raises
        ------
        ValueError
            If the requested timebase scale is not supported by the instrument.
        """
        if scale not in self.__TIMEBASE_SCALES:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid timebase scale {scale}. "
                f"Valid values are: {sorted(self.__TIMEBASE_SCALES)}."
            )
        self.inst.write(f":HOR:SCA {scale}")
        if self.verbose:
            print(f"[TBS2204B] Timebase scale set to {scale} s/div.")

    def set_timebase_position(self, position: float) -> None:
        """
        Set the horizontal timebase position.

        Parameters
        ----------
        position : float
            Horizontal timebase offset as percentage (0 to 100).

        Raises
        ------
        ValueError
            If the timebase position is outside the valid range.
        """
        if not (0 <= position <= 100):
            raise ValueError(
                "[TBS2204B][ERROR] Timebase position must be between 0 and 100%."
            )
        self.inst.write(
            ":HOR:DEL:MOD OFF"
        )  # Changing the position does not work when a delay is applied
        self.inst.write(f":HOR:POS {position}")
        if self.verbose:
            print(f"[TBS2204B] Timebase position set to {position}%.")

    def get_timebase_scale(self) -> float:
        """
        Get horizontal timebase scale.

        Returns
        -------
        float
            Time scale per division in s/div.

        """
        scale = float(self.inst.query(":HOR:SCA?"))
        if self.verbose:
            print(f"[TBS2204B] Timebase scale is {scale} s/div.")
        return scale

    def get_timebase_position(self) -> float:
        """
        Get the horizontal timebase position.

        Returns
        -------
        float
            Horizontal timebase offset in percentage of the waveform displayed.
        """
        pos = float(self.inst.query(":HOR:DEL:POS?"))
        if self.verbose:
            print(f"[TBS2204B] Timebase position is {pos}%.")
        return pos

    # ------------------------------------------------------------------
    # Trigger settings
    # ------------------------------------------------------------------
    def set_trigger_mode(self, mode: str) -> None:
        """
        Configure trigger mode.

        Parameters
        ----------
        mode : str
            Trigger mode string. Valid values are those listed in
            `__TRIGGER_MODES`.

        Raises
        ------
        ValueError
            If the trigger mode is not supported.
        """
        mode = mode.upper()
        if mode not in self.__TRIGGER_MODES:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid trigger mode '{mode}'. "
                f"Valid options: {sorted(self.__TRIGGER_MODES)}."
            )
        self.inst.write(f":TRIG:A:MOD {mode}")
        if self.verbose:
            print(f"[TBS2204B] Trigger mode set to {mode}.")

    def set_trigger_source(self, channel: int) -> None:
        """
        Select trigger source channel.

        Parameters
        ----------
        source : str
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Raises
        ------
        ValueError
            If the trigger source channel number is outside the valid range.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid source channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        self.inst.write(f":TRIG:A:EDGE:SOU CH{channel}")
        if self.verbose:
            print(f"[TBS2204B] Trigger source set to CH{channel}.")

    def set_trigger_level(self, level: float) -> None:
        """
        Set trigger voltage level.

        Parameters
        ----------
        level : float
            Trigger level in volts. The valid range depends on the trigger source
            channel vertical scale and vertical position. See Notes.

        Notes
        -----
        The valid trigger level range is not fixed. It depends on the current
        configuration of the trigger source channel and is dynamically computed as:
            - the active trigger source is obtained from
            `get_trigger_source()`
            - the vertical scale (V/div) of that channel is obtained from
            `get_channel_scale()`
            - the vertical position (divisions) of that channel is obtained from
            `get_channel_position()`

        The oscilloscope internally limits the trigger point to a maximum vertical
        span of ±4.96 divisions from the center. Therefore, the valid level range is:

            [(−4.96 − position) * scale,  (4.96 − position) * scale]

        Any change in channel scale or vertical position modifies the admissible
        trigger level range. It is therefore recommended to re-validate the trigger
        level after adjusting vertical settings.

        Raises
        ------
        ValueError
            If the trigger level is outside the valid range for the current trigger source settings.
        """
        source = self.get_trigger_source()
        scale = self.get_channel_scale(source)
        position = self.get_channel_position(source)
        min_allowed = -(4.96 + position) * scale
        max_allowed = +(4.96 - position) * scale
        if not (min_allowed <= level <= max_allowed):
            raise ValueError(
                f"[TBS2204B][ERROR] Trigger level {level} V exceeds valid range "
                f"[{min_allowed}, {max_allowed}] V for source {source}."
            )
        self.inst.write(f":TRIG:A:LEV {level}")
        if self.verbose:
            print(f"[TBS2204B] Trigger level set to {level} V.")

    def set_trigger_slope(self, slope: str) -> None:
        """
        Set the trigger slope mode.

        Parameters
        ----------
        slope : str
            Trigger slope mode. Valid values are those listed in
            `__TRIGGER_SLOPES`.

        Raises
        ------
        ValueError
            If the trigger slope mode is not supported.
        """
        slope = slope.upper()
        if slope not in self.__TRIGGER_SLOPES:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid trigger slope '{slope}'. "
                f"Valid options: {sorted(self.__TRIGGER_SLOPES)}."
            )
        self.inst.write(f":TRIG:A:EDGE:SLO {slope}")
        if self.verbose:
            print(f"[TBS2204B] Trigger slope set to {slope}.")

    def get_trigger_mode(self) -> str:
        """
        Get trigger mode.

        Returns
        -------
        str
            Trigger mode as in `__TRIGGER_MODES`.
        """
        mode = self.inst.query(":TRIG:A:MOD?").strip()
        if self.verbose:
            print(f"[TBS2204B] Trigger mode is {mode}.")
        return mode

    def get_trigger_source(self) -> int:
        """
        Get trigger source channel.

        Returns
        -------
        int
            Trigger source channel.
        """
        source = self.inst.query(":TRIG:A:EDGE:SOU?").strip()
        if source.startswith("CH"):
            channel = int(source.replace("CH", ""))
        else:
            channel = None
        if self.verbose:
            print(f"[TBS2204B] Trigger source is CH{channel}.")
        return channel

    def get_trigger_level(self) -> float:
        """
        Get trigger voltage level.

        Returns
        -------
        float
            Trigger level in volts.
        """
        level = float(self.inst.query(":TRIG:A:LEV?"))
        if self.verbose:
            print(f"[TBS2204B] Trigger level is {level} V.")
        return level

    def get_trigger_slope(self) -> str:
        """
        Get trigger slope mode.

        Returns
        -------
        str
            Slope mode as in `__TRIGGER_SLOPES`.
        """
        slope = self.inst.query(":TRIG:A:EDGE:SLO?").strip()
        if self.verbose:
            print(f"[TBS2204B] Trigger slope is {slope}.")
        return slope

    # ------------------------------------------------------------------
    # Waveform acquisition
    # ------------------------------------------------------------------
    def get_waveform(self, channel: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Acquire waveform data from a specified channel and return both the
        time axis and the waveform.

        Parameters
        ----------
        channel : int
            Channel number. Valid values are between 1 and `__MAX_CHANNELS`.

        Returns
        -------
        x : numpy.ndarray
            Time axis in seconds.
        y : numpy.ndarray
            Waveform samples in volts.

        Raises
        ------
        ValueError
            If the channel number is outside the valid range.
            If the channel display is OFF when attempting to acquire a waveform.
        """
        if not (1 <= channel <= self.__NUM_CHANNELS):
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid channel {channel}. Must be between 1 and {self.__NUM_CHANNELS}."
            )
        if not self.get_channel_display(channel):
            raise ValueError(
                f"[TBS2204B][ERROR] CH{channel} is OFF. "
                "Enable it with set_channel_display(channel, True) before acquiring waveforms."
            )
        self.inst.write(":DAT:ENC ASCI")  # Set data encoding to ASCII
        self.inst.write(f":DAT:SOU CH{channel}")  # Set channel
        self.inst.write(":DAT:STAR 1")  # Get entire record (left)
        self.inst.write(
            f":DAT:STOP {np.max(self.__RECORD_LENGTHS)}"
        )  # Get entire record (right)
        if self.verbose:
            print(f"[TBS2204B] Donwloading data points from CH{channel}...")
        raw_data = self.inst.query(":CURV?")  # Get raw data
        raw = np.fromstring(raw_data, sep=",")
        ymult = float(self.inst.query(":WFMO:YMULT?"))  # Get Y parameters
        yoff = float(self.inst.query(":WFMO:YOFF?"))
        yzero = float(self.inst.query(":WFMO:YZERO?"))
        y = (raw - yoff) * ymult + yzero  # Convert to voltage
        xincr = float(self.inst.query(":WFMO:XINCR?"))  # Get X parameters
        xzero = float(self.inst.query(":WFMO:XZERO?"))
        n = len(raw)  # Convert to time
        x = np.arange(n) * xincr + xzero
        if self.verbose:
            print(f"[TBS2204B] {n} points downloaded from CH{channel}.")
        return x, y

    def start_acquisition(self) -> None:
        """
        Start continuous acquisition (RUN mode).

        Notes
        -----
        This sets the oscilloscope to continuous acquisition mode and
        starts waveform acquisition. It is not suited for acquisition from PC.
        """
        self.inst.write(":ACQ:STOPA RUNST")
        self.inst.write(":ACQ:STATE RUN")
        if self.verbose:
            print("[TBS2204B] Acquisition started (continuous mode).")

    def single_acquisition(self) -> None:
        """
        Perform a single-sequence acquisition.

        Notes
        -----
        After completing the acquisition the oscilloscope stops automatically.
        This is the method of choice for acquiring data from a PC. Remember
        that once you have changed the measurement parameters it is always a
        good idea to acquire again the sequence.
        """
        self.inst.write(":ACQ:STOPA SEQ")
        if self.verbose:
            print("[TBS2204B] Single-sequence acquisition started.")
        self.inst.write(":ACQ:STATE RUN")
        self.inst.query("*OPC?")
        if self.verbose:
            print("[TBS2204B] Single-sequence acquisition completed.")

    def stop_acquisition(self) -> None:
        """
        Stop waveform acquisition.
        """
        self.inst.write(":ACQ:STATE STOP")
        if self.verbose:
            print("[TBS2204B] Acquisition stopped.")

    def get_acquisition_state(self) -> bool:
        """
        Query the current acquisition state.

        Returns
        -------
        bool
            ``True`` if acquisition is running, ``False`` if stopped.
        """
        state = self.inst.query(":ACQ:STATE?").strip()
        if self.verbose:
            print(
                f"[TBS2204B] Acquisition state: {'RUNNING' if state == '1' else 'STOPPED'}."
            )
        return state == "1"

    def set_record_length(self, length: int) -> None:
        """
        Set the acquisition record length.

        Parameters
        ----------
        length : int
            Record length in points. Valid values are those listed in
            `__RECORD_LENGTHS`.

        Raises
        ------
        ValueError
            If the record length is not supported by the instrument.
        """
        if length not in self.__RECORD_LENGTHS:
            raise ValueError(
                f"[TBS2204B][ERROR] Invalid record length {length}. "
                f"Valid options: {self.__RECORD_LENGTHS}."
            )
        self.inst.write(f":HOR:RECO {length}")
        if self.verbose:
            print(f"[TBS2204B] Record length set to {length} points.")

    def get_record_length(self) -> int:
        """
        Get the current acquisition record length.

        Returns
        -------
        int
            Record length in points.
        """
        length = int(self.inst.query("HOR:RECO?"))
        if self.verbose:
            print(f"[TBS2204B] Record length is {length} points.")
        return length


if __name__ == "__main__":

    import matplotlib.pyplot as plt

    scope = TBS2204B("USB::0x0699::0x03C7::C010302::INSTR", verbose=True)

    # General communication and status
    scope.idn()
    scope.clear()
    scope.reset()
    scope.autoset()

    # Channel control
    scope.set_channel_display(2, True)
    scope.get_channel_display(2)
    scope.set_channel_coupling(2, "DC")
    scope.get_channel_coupling(2)
    scope.set_channel_position(2, 0)
    scope.get_channel_position(2)
    scope.set_channel_gain(2, 1)
    scope.get_channel_gain(2)
    scope.set_channel_bandwidth(2, 20e6)
    scope.get_channel_bandwidth(2)
    scope.set_channel_scale(2, 1)
    scope.get_channel_scale(2)

    # Timebase configuration
    scope.set_timebase_position(7.5)
    scope.get_timebase_position()
    scope.set_timebase_scale(0.001)
    scope.get_timebase_scale()

    # Trigger settings
    scope.set_trigger_mode("AUTO")
    scope.get_trigger_mode()
    scope.set_trigger_slope("FALL")
    scope.get_trigger_slope()
    scope.set_trigger_source(2)
    scope.get_trigger_source()
    scope.set_trigger_level(1.5)
    scope.get_trigger_level()

    # Waveform acquisition
    scope.set_record_length(2e3)
    scope.get_record_length()
    scope.get_acquisition_state()
    scope.stop_acquisition()
    scope.get_acquisition_state()
    scope.start_acquisition()
    scope.get_acquisition_state()
    scope.single_acquisition()
    scope.get_acquisition_state()
    t, v = scope.get_waveform(2)
    plt.plot(t, v)
    plt.show()

    scope.close()
