"""
QONTROL BOARDS

High-level Python interface for Qontrol Q8iv current/voltage controller boards.

This module provides a safe, documented wrapper around the low-level
`qontrol.QXOutput` object exposing:
- validated channel access (0-indexed),
- compliance/current/voltage guards,
- unified verbose logging and error handling consistent with AFG3011C,
  TBS2204B and LF_OSW drivers in this codebase.
"""

import time
from typing import List, Optional, Sequence, Union

import numpy as np
import qontrol
from Instrument import Instrument


class Q8iv(Instrument):
    """
    High-level interface for Qontrol Q8iv current/voltage driver boards.

    Provides simplified access to Qontrol hardware channels (typically an
    8-channel board) used for controlling thermo-optic phase shifters or
    resistive loads. It manages initialization, compliance limits, and basic
    I/V operations, with protection against overcurrent and overvoltage.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. ``'COM4'`` for Serial/USB).
    init_mode : {'i', 'v'}, optional
        Initialization mode: ``'i'`` for current control, ``'v'`` for voltage
        control (default: ``'i'``).
    imax : float, optional
        Current compliance in milliamperes (default: ``24.0``).
    vmax : float, optional
        Voltage compliance in volts (default: ``12.0``).
    transient : float, optional
        Settling wait time after write operations (default: ``0.5``).
    verbose : bool, optional
        If ``True``, prints instrument messages (default: ``True``).

    Attributes
    ----------
    _q : qontrol.QXOutput
        Low-level Qontrol communication object.
    num_channels : int
        Number of detected hardware output channels.
    imax : float
        Active current compliance limit (mA).
    vmax : float
        Active voltage compliance limit (V).
    transient : float
        Settling time applied after each write operation (s).
    verbose : bool
        Verbosity flag controlling console output.

    Notes
    -----
    - Channel numbering is **0-based**.
    - Compliance limits are enforced in software and clamped when exceeding
      hardware safe values.
    - This wrapper standardizes behaviour and error formatting to match the
      rest of the instrumentation drivers in this repository.

    Examples
    --------
    >>> from lib.instruments.qontrol.core import Q8iv
    >>> drv = Q8iv('COM4', init_mode='i', verbose=True)
    [Q8iv] Initialised Qontrol in 'i' mode with 8 channels. imax=24.0 mA, vmax=12.0 V.
    >>> drv.set_current(0, 5.0)      # Set channel 0 to 5 mA
    [Q8iv] Setting channel 0 to 5 mA.
    >>> current = drv.get_current([0, 1, 2])
    >>> print(current)
    [4.995, 0.000, 0.000]
    >>> drv.set_all_zero()
    >>> drv.close()
    [Q8iv] Successfully closed communication.
    """

    # Default compliance limits
    __IMAX_DEFAULT: float = 24.0  # mA
    __VMAX_DEFAULT: float = 12.0  # V

    def __init__(
        self,
        resource: str,
        init_mode: str = "i",
        imax: float = __IMAX_DEFAULT,
        vmax: float = __VMAX_DEFAULT,
        transient: float = 0.5,
        verbose: bool = True,
    ) -> None:
        """
        Initialise the Q8iv wrapper and connect to the Qontrol board.

        Raises
        ------
        ConnectionError
            If unable to connect to the device.
        ValueError
            If init_mode or compliance values are invalid.
        """
        self.verbose = verbose
        self.resource = resource
        self.connect()
        
        # Detect channel count
        try:
            self.__num_channels = len(self._q.i)
        except Exception:
            try:
                self.__num_channels = len(self._q.v)
            except Exception:
                self.__num_channels = 8
        # Validate init mode
        mode = init_mode.lower()
        if mode not in ("i", "v"):
            raise ValueError(
                f"[Q8iv][ERROR] Invalid init_mode '{init_mode}'. Use 'i' or 'v'."
            )
        self._init_mode = mode
        # Validate compliance
        if not (0 < imax <= self.__IMAX_DEFAULT) or not (
            0 < vmax <= self.__VMAX_DEFAULT
        ):
            raise ValueError(
                f"[Q8iv][ERROR] Compliance out of bounds: "
                f"imax<={self.__IMAX_DEFAULT}, vmax<={self.__VMAX_DEFAULT}."
            )
        self.set_compliance(imax, vmax)
        self.imax = imax
        self.vmax = vmax
        self.transient = transient
        if self.verbose:
            print(
                f"[Q8iv] Initialised Qontrol in {self._init_mode!r} mode with "
                f"{self.__num_channels} channels. imax={self.imax} mA, vmax={self.vmax} V."
            )
            
    def connect(self) -> None:
        # Connect low-level interface
        try:
            self._q = qontrol.QXOutput(serial_port_name=self.resource, response_timeout=0.1)
        except Exception as e:
            raise ConnectionError(f"[Q8iv][ERROR] Could not initialise Qontrol: {e}.")
            
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def __to_list(self, obj: Union[int, float, Sequence[Union[int, float]]]) -> List:
        """
        Convert an int/float or sequence into a Python list.
        """
        arr = np.atleast_1d(obj)
        return arr.tolist()

    def __validate_channel(self, ch: int) -> None:
        """
        Validate that channel index is within 0..num_channels-1.
        """
        if not (0 <= ch < self.__num_channels):
            raise ValueError(
                f"[Q8iv][ERROR] Invalid channel {ch}. "
                f"Valid range: 0 to {self.__num_channels - 1}."
            )

    def __validate_chans_vals(
        self, chans: Sequence[int], vals: Sequence[float]
    ) -> None:
        """
        Validate channels and values length and indices.
        """
        if len(chans) != len(vals):
            raise ValueError(
                f"[Q8iv][ERROR] Number of channels ({len(chans)}) and values ({len(vals)}) must match."
            )
        for ch in chans:
            self.__validate_channel(int(ch))

    # ------------------------------------------------------------------
    # Properties: instantaneous device state
    # ------------------------------------------------------------------
    @property
    def num_channels(self) -> int:
        """
        Number of detected channels.
        """
        return self.__num_channels

    @property
    def current(self) -> List[float]:
        """
        Instantaneous currents (mA).
        """
        return list(self._q.i[:])

    @property
    def voltage(self) -> List[float]:
        """
        Instantaneous voltages (V).
        """
        return list(self._q.v[:])

    @property
    def power(self) -> List[float]:
        """
        Instantaneous electrical power (mW).
        """
        return [v * i for v, i in zip(self.voltage, self.current)]

    @property
    def resistance(self) -> List[Optional[float]]:
        """
        Instantaneous electrical resistance (Ohm) or None on division errors.
        """
        out = []
        for v, i in zip(self.voltage, self.current):
            try:
                out.append(1000.0 * v / i)
            except Exception:
                out.append(None)
        return out

    # ------------------------------------------------------------------
    # Core I/V operations
    # ------------------------------------------------------------------
    def set_current(
        self, channel: Union[int, Sequence[int]], current: Union[float, Sequence[float]]
    ) -> None:
        """
        Set output current for one or more channels (mA).

        Raises
        ------
        ValueError
            If not in current mode, or invalid channel/value input.
        """
        if self._init_mode != "i":
            raise ValueError(
                "[Q8iv][ERROR] Attempted to set current while in voltage mode."
            )
        chans = [int(c) for c in self.__to_list(channel)]
        currents = [float(v) for v in self.__to_list(current)]
        self.__validate_chans_vals(chans, currents)
        for ch, cur in zip(chans, currents):
            if cur > self.imax or cur < 0:
                if self.verbose:
                    print(
                        f"[Q8iv] Out-of-range current on channel {ch} "
                        f"(requested {cur} mA) — clamped to 0 mA."
                    )
                cur = 0.0
            self._q.i[ch] = cur
            if self.verbose:
                print(f"[Q8iv] Setting channel {ch} to {cur:.6g} mA.")
        time.sleep(self.transient)

    def get_current(self, channel: Union[int, Sequence[int]]) -> List[float]:
        """
        Return current (mA) for one or more channels.
        """
        chans = [int(c) for c in self.__to_list(channel)]
        for ch in chans:
            self.__validate_channel(ch)
        return [float(self._q.i[ch]) for ch in chans]

    def set_voltage(
        self, channel: Union[int, Sequence[int]], voltage: Union[float, Sequence[float]]
    ) -> None:
        """
        Set output voltage for one or more channels (V).

        Raises
        ------
        ValueError
            If not in voltage mode, or invalid channel/value input.
        """
        if self._init_mode != "v":
            raise ValueError(
                "[Q8iv][ERROR] Attempted to set voltage while in current mode."
            )
        chans = [int(c) for c in self.__to_list(channel)]
        volts = [float(v) for v in self.__to_list(voltage)]
        self.__validate_chans_vals(chans, volts)
        for ch, v in zip(chans, volts):
            if v > self.vmax or v < 0:
                if self.verbose:
                    print(
                        f"[Q8iv] Out-of-range voltage on channel {ch} "
                        f"(requested {v} V) — clamped to 0 V."
                    )
                v = 0.0
            self._q.v[ch] = v
            if self.verbose:
                print(f"[Q8iv] Setting channel {ch} to {v:.6g} V.")
        time.sleep(self.transient)

    def get_voltage(self, channel: Union[int, Sequence[int]]) -> List[float]:
        """
        Return voltage (V) for one or more channels.
        """
        chans = [int(c) for c in self.__to_list(channel)]
        for ch in chans:
            self.__validate_channel(ch)
        return [float(self._q.v[ch]) for ch in chans]

    # ------------------------------------------------------------------
    # Utility operations
    # ------------------------------------------------------------------
    def set_compliance(
        self, current: float = __IMAX_DEFAULT, voltage: float = __VMAX_DEFAULT
    ) -> None:
        """
        Set current and voltage compliance limits.

        Raises
        ------
        ValueError
            If compliance exceeds hardware defaults.
        """
        if not (0 < current <= self.__IMAX_DEFAULT) or not (
            0 < voltage <= self.__VMAX_DEFAULT
        ):
            raise ValueError(
                f"[Q8iv][ERROR] Compliance out of bounds: "
                f"imax<={self.__IMAX_DEFAULT}, vmax<={self.__VMAX_DEFAULT}."
            )
        try:
            self._q.imax[:] = float(current)
            self._q.vmax[:] = float(voltage)
        except Exception:
            pass
        self.imax = float(current)
        self.vmax = float(voltage)
        if self.verbose:
            print(
                f"[Q8iv] Compliance updated: imax={self.imax} mA, vmax={self.vmax} V."
            )

    def set_all_zero(self) -> None:
        """
        Set all outputs to zero (safe shutdown).
        """
        if self.verbose:
            print("[Q8iv] Setting all outputs to zero.")
        if self._init_mode == "v":
            try:
                self._q.v[:] = 0.0
            except Exception:
                for ch in range(self.__num_channels):
                    self._q.v[ch] = 0.0
        else:
            try:
                self._q.i[:] = 0.0
            except Exception:
                for ch in range(self.__num_channels):
                    self._q.i[ch] = 0.0
        time.sleep(self.transient)

    def close(self) -> None:
        """
        Close communication and safely turn off all channels.

        Notes
        -----
        Before closing, all outputs are automatically set to zero.
        """
        try:
            if self._q is not None:
                self.set_all_zero()
                try:
                    self._q.close()
                except Exception:
                    raise RuntimeError("[Q8iv][ERROR] Low-level Qontrol close failed.")
                finally:
                    self._q = None
                if self.verbose:
                    print("[Q8iv] Successfully closed communication.")
            else:
                if self.verbose:
                    print("[Q8iv] Communication already closed.")
        except Exception as e:
            raise RuntimeError(f"[Q8iv][ERROR] Error during close(): {e}.")


if __name__ == "__main__":

    drv = Q8iv("COM4", init_mode="v", transient=0.2, verbose=True)

    # General compliance and status
    drv.set_compliance(current=24.0, voltage=12.0)

    # Core I/V operations
    # drv.set_current(0, 5.0)
    # drv.set_current([1, 2], [3.0, 7.5])
    drv.get_current([0, 1, 2])
    drv.get_voltage([0, 1, 2])
    drv.set_all_zero()
    drv.get_current([0, 1, 2])
    drv.get_voltage([0, 1, 2])

    drv.close()
