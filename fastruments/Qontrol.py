"""
QONTROL BOARDS

High-level Python interface for Qontrol Q8iv current/voltage controller boards.

This module provides a safe, documented wrapper around the low-level
`qontrol.QXOutput` object exposing:
- validated channel access (0-indexed),
- compliance/current/voltage guards,
- unified verbose logging and error handling consistent with fastruments drivers
  in this library.
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
    timeout : float, optional
        Communication timeout in seconds (default: ``0.1``).
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

    Examples
    --------
    >>> from fastruments.Qontrol import Q8iv
    >>> drv = Q8iv('COM4', init_mode='i', verbose=True)
    [Q8iv] Initialised Qontrol in 'i' mode with 8 channels. imax=24.0 mA, vmax=12.0 V.
    >>> drv.set_current(0, 5.0)
    [Q8iv] Setting channel 0 to 5 mA.
    >>> currents = drv.get_current([0, 1])
    [Q8iv] Current on channel [0, 1]: [5.0, 0.0] mA.
    >>> drv.close()
    [Q8iv] Setting all outputs to zero.
    [Q8iv] Successfully closed communication.
    """

    # Default compliance limits
    __IMAX_DEFAULT: float = 24.0  # mA
    __VMAX_DEFAULT: float = 12.0  # V

    def __init__(
        self,
        resource: str,
        timeout: float = 0.1,
        init_mode: str = "i",
        imax: float = __IMAX_DEFAULT,
        vmax: float = __VMAX_DEFAULT,
        transient: float = 0.5,
        verbose: bool = True,
    ) -> None:
        """
        Initialise the Q8iv wrapper and connect to the Qontrol board.

        See class docstring for detailed parameter descriptions.

        Raises
        ------
        ValueError
            If the provided `init_mode` is not ``'i'`` or ``'v'``.
        """
        self.verbose = verbose
        self.resource = resource
        self.timeout = timeout
        self.connect()
        # Detect channel count
        try:
            self.num_channels = len(self._q.i)
        except Exception:
            try:
                self.num_channels = len(self._q.v)
            except Exception:
                self.num_channels = 8
        # Validate init mode
        mode = init_mode.lower()
        if mode not in ("i", "v"):
            raise ValueError(
                f"[Q8iv][ERROR] Invalid init_mode '{init_mode}'. Use 'i' or 'v'."
            )
        self.init_mode = mode
        self.set_compliance(imax, vmax)
        self.transient = transient
        if self.verbose:
            print(
                f"[Q8iv] Initialised Qontrol in '{self.init_mode}' mode with "
                f"{self.num_channels} channels. imax={self.imax} mA, vmax={self.vmax} V."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def __to_list(self, obj: Union[int, float, Sequence[Union[int, float]]]) -> List:
        """
        Convert an int/float or sequence into a Python list.

        Parameters
        ----------
        obj : int, float or Sequence
            The input value or collection to convert.

        Returns
        -------
        List
            A standard Python list containing the input elements.
        """
        arr = np.atleast_1d(obj)
        return arr.tolist()

    def __validate_channel(self, chans: Sequence[int]) -> None:
        """
        Validate that channel indices exist.

        Parameters
        ----------
        chans : Sequence of int
            A sequence of channel indices to validate.

        Raises
        ------
        ValueError
            If the channel index is out of the hardware range.
        """
        for ch in chans:
            if not (0 <= ch < self.num_channels):
                raise ValueError(
                    f"[Q8iv][ERROR] Invalid channel {ch}. "
                    f"Valid range: 0 to {self.num_channels - 1}."
                )

    def __validate_chans_vals(
        self, chans: Sequence[int], vals: Sequence[float]
    ) -> None:
        """
        Validate channels and values length and indices.

        Parameters
        ----------
        chans : Sequence of int
            List of channel indices.
        vals : Sequence of float
            List of target values.

        Raises
        ------
        ValueError
            If the lengths of `chans` and `vals` do not match.
        """
        if len(chans) != len(vals):
            raise ValueError(
                f"[Q8iv][ERROR] Number of channels ({len(chans)}) and values ({len(vals)}) must match."
            )
        self.__validate_channel(chans)

    # ------------------------------------------------------------------
    # Properties: instantaneous device state
    # ------------------------------------------------------------------
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
    # General communication and status
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """
        Establish the low-level communication with the Qontrol board.

        This method initializes the `qontrol.QXOutput` interface using the
        provided serial port resource and sets a default response timeout.

        Raises
        ------
        ConnectionError
            If the Qontrol low-level driver fails to initialize.
        """
        try:
            self._q = qontrol.QXOutput(
                serial_port_name=self.resource, response_timeout=self.timeout
            )
        except Exception as e:
            raise ConnectionError(f"[Q8iv][ERROR] Could not initialise Qontrol: {e}.")

    def close(self) -> None:
        """
        Close communication and safely turn off all channels.

        Notes
        -----
        Before closing, all outputs are automatically set to zero. Should always
        be called before program termination to release the COM resource.

        Raises
        ------
        RuntimeError
            If the low-level close operation fails.
            If an error occurs during the shutdown sequence.
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
            raise RuntimeError(f"[Q8iv][ERROR] Error during shutdown sequence: {e}.")

    # ------------------------------------------------------------------
    # Core I/V operations
    # ------------------------------------------------------------------
    def set_current(
        self, channel: Union[int, Sequence[int]], current: Union[float, Sequence[float]]
    ) -> None:
        """
        Set output current for one or more channels.

        Parameters
        ----------
        channel : int or Sequence of int
            Zero-indexed channel number(s).
        current : float or Sequence of float
            Target current value(s) in mA.

        Raises
        ------
        ValueError
            If not in current mode.
            If out of current compliance limits.
        """
        if self.init_mode != "i":
            raise ValueError(
                "[Q8iv][ERROR] Attempted to set current while in voltage mode."
            )
        chans = [int(c) for c in self.__to_list(channel)]
        currents = [float(v) for v in self.__to_list(current)]
        self.__validate_chans_vals(chans, currents)
        invalid_values = [v for v in currents if not (0 <= v <= self.imax)]
        if invalid_values:
            raise ValueError(
                f"[Q8iv][ERROR] One or more values {invalid_values} are out of range. "
                f"Valid range for currents: 0 to {self.imax} mA."
            )
        for ch, val in zip(chans, currents):
            self._q.i[ch] = val
        if self.verbose:
            print(f"[Q8iv] Channels {chans} set to {currents} mA.")
        time.sleep(self.transient)

    def get_current(self, channel: Union[int, Sequence[int]]) -> List[float]:
        """
        Return current for one or more channels.

        Parameters
        ----------
        channel : int or Sequence of int
            Zero-indexed channel number(s).

        Returns
        -------
        List of float
            Measured current values in mA.
        """
        chans = [int(c) for c in self.__to_list(channel)]
        self.__validate_channel(chans)
        values = [self._q.i[ch] for ch in chans]
        if self.verbose:
            print(f"[Q8iv] Current on channel {chans}: {values} mA.")
        return values

    def set_voltage(
        self, channel: Union[int, Sequence[int]], voltage: Union[float, Sequence[float]]
    ) -> None:
        """
        Set output voltage for one or more channels (V).

        Parameters
        ----------
        channel : int or Sequence of int
            Zero-indexed channel number(s).
        voltage : float or Sequence of float
            Target voltage value(s) in volts.

        Raises
        ------
        ValueError
            If not in voltage mode.
            If out of voltage compliance limits.
        """
        if self.init_mode != "v":
            raise ValueError(
                "[Q8iv][ERROR] Attempted to set voltage while in current mode."
            )
        chans = [int(c) for c in self.__to_list(channel)]
        volts = [float(v) for v in self.__to_list(voltage)]
        self.__validate_chans_vals(chans, volts)
        invalid_values = [v for v in volts if not (0 <= v <= self.vmax)]
        if invalid_values:
            raise ValueError(
                f"[Q8iv][ERROR] One or more values {invalid_values} are out of range. "
                f"Valid range for voltages: 0 to {self.vmax} V."
            )
        for ch, val in zip(chans, volts):
            self._q.v[ch] = val
        if self.verbose:
            print(f"[Q8iv] Channels {chans} set to {volts} V.")
        time.sleep(self.transient)

    def get_voltage(self, channel: Union[int, Sequence[int]]) -> List[float]:
        """
        Return voltage for one or more channels.

        Parameters
        ----------
        channel : int or Sequence of int
            Zero-indexed channel number(s).

        Returns
        -------
        List of float
            Measured voltage values in volts.
        """
        chans = [int(c) for c in self.__to_list(channel)]
        self.__validate_channel(chans)
        values = [self._q.v[ch] for ch in chans]
        if self.verbose:
            print(f"[Q8iv] Voltage on channel {chans}: {values} V.")
        return values

    # ------------------------------------------------------------------
    # Utility operations
    # ------------------------------------------------------------------
    def set_compliance(self, imax: float, vmax: float) -> None:
        """
        Set current and voltage compliance limits.

        Parameters
        ----------
        imax : float
            Current compliance in mA.
        vmax : float
            Voltage compliance in V.

        Raises
        ------
        ValueError
            If compliance exceeds hardware limits.
        """
        if not (0 < imax <= self.__IMAX_DEFAULT) or not (
            0 < vmax <= self.__VMAX_DEFAULT
        ):
            raise ValueError(
                f"[Q8iv][ERROR] Compliance out of bounds: "
                f"imax<={self.__IMAX_DEFAULT}, vmax<={self.__VMAX_DEFAULT}."
            )
        self._q.imax[:] = float(imax)
        self._q.vmax[:] = float(vmax)
        self.imax = float(imax)
        self.vmax = float(vmax)
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
        if self.init_mode == "v":
            try:
                self._q.v[:] = 0.0
            except Exception:
                for ch in range(self.num_channels):
                    self._q.v[ch] = 0.0
        else:
            try:
                self._q.i[:] = 0.0
            except Exception:
                for ch in range(self.num_channels):
                    self._q.i[ch] = 0.0
        time.sleep(self.transient)


if __name__ == "__main__":

    drv = None

    try:
        # Initialization
        drv = Q8iv("COM4", init_mode="i", transient=0.2, verbose=True)

        # Utility operations
        drv.set_compliance(imax=20.0, vmax=10.0)

        # Core I/V operations
        drv.set_current(0, 5.0)
        drv.set_current([1, 2], [3.0, 7.5])
        drv.get_current([0, 1, 2])
        drv.get_voltage([0, 1, 2])
        drv.set_all_zero()
        drv.get_current([0, 1, 2])
        drv.get_voltage([0, 1, 2])

    except Exception as e:
        msg = str(e)
        if not msg.startswith("[Q8iv][ERROR]"):
            msg = f"[Q8iv][ERROR] {msg}"
        print(msg)

    finally:
        if drv is not None:
            drv.close()
