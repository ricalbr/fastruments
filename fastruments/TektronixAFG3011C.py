"""
TEKTRONIX AFG3000

This module provides a high-level Python interface for controlling Tektronix
AFG3011C function generators via USB using the PyVISA library.

Implements the core SCPI command set derived from the Tektronix
AFG3000/AFG3000C Series Programmer Manual (document 071-1639-04).

The `AFG3011C` class allows for standard waveform configuration and control
(sine, square, ramp, pulse, noise, DC), designed for laboratory automation
in photonic and electronic testing setups.
"""

import pyvisa
from Instrument import Instrument


class AFG3011C(Instrument):
    """
    High-level interface for the Tektronix AFG3011C Function Generator.

    This class provides an abstraction layer to communicate with the instrument
    using SCPI commands via PyVISA. It supports configuration of waveform type,
    frequency, amplitude, offset, impedance, and output control.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. ``'USB::0x0699::0x034F::C020348::INSTR'``)
        specifying the connected instrument.
    timeout : int, optional
        Communication timeout in milliseconds (default: ``5000``).
    verbose : bool, optional
        If ``True``, prints informational messages (default: ``True``).

    Attributes
    ----------
    inst : pyvisa.Resource
        Active VISA session object.
    verbose : bool
        Flag controlling console output.
    model : str
        Model name retrieved from the identification query.

    Examples
    --------
    >>> from lib.instruments.afg3011c.core import AFG3011C
    >>> afg = AFG3011C('USB::0x0699::0x034F::C020348::INSTR', verbose=True)
    [AFG3011C] IDN: TEKTRONIX,AFG3011C,C020348,SCPI:99.0 FV:1.0.9.
    [AFG3011C] Connected successfully.
    >>> afg.set_function('SIN')
    [AFG3011C] Function set to SIN.
    >>> afg.set_frequency(1e3)
    [AFG3011C] Frequency set to 1000.0 Hz.
    >>> afg.set_amplitude(2.0)
    [AFG3011C] Amplitude set to 2.0 Vpp.
    >>> afg.set_output_state(True)
    [AFG3011C] Output ON.
    >>> afg.close()
    [AFG3011C] Connection closed.
    """

    __FREQ_RANGE = {
        "SIN": (1e-6, 10e6),
        "SQU": (1e-6, 5e6),
        "RAMP": (1e-6, 100e3),
        "PULS": (1e-3, 5e6),
        "PRN": (1e-6, 10e6),
        "DC": (0, 0),  # No frequency for DC
    }  # Hz

    __V_LIMIT = {"50": 10, "INF": 20}  # V

    __AMPL_MIN = {"50": 20e-3, "INF": 40e-3}  # Vpp

    __IMPEDANCE_MODES = {"50", "INF"}

    __FUNCTIONS = {"SIN", "SQU", "RAMP", "PULS", "PRN", "DC"}

    def __init__(
        self, resource: str, timeout: int = 5000, verbose: bool = True
    ) -> None:
        """
        Initialize communication with the Tektronix AFG3011C instrument.

        See class docstring for detailed parameter descriptions.
        """
        self.verbose = verbose
        self.timeout = timeout
        self.resource = resource
        self.connect()

    # ------------------------------------------------------------------
    # General communication and status
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """
        Establish the VISA connection with the function generator.

        This method initializes the VISA Resource Manager, opens the USB 
        resource, and sets the communication timeout. It also performs an 
        initial identification query to verify the connection.

        Raises
        ------
        ConnectionError
            If the VISA resource cannot be opened.
        RuntimeError
            If the instrument fails to respond to the identification query.
        """
        try:
            rm = pyvisa.ResourceManager()
            self.inst = rm.open_resource(self.resource)
            self.inst.timeout = self.timeout
        except Exception as e:
            raise ConnectionError(
                f"[AFG3011C][ERROR] Could not connect to function generator: {e}"
            )
        try:
            self.idn()
            if self.verbose:
                print("[AFG3011C] Connected successfully.")
        except Exception as e:
            raise RuntimeError(f"[AFG3011C][ERROR] Failed to query IDN: {e}")

    def idn(self) -> str:
        """
        Query the instrument identification string.

        Returns
        -------
        str
            Full identification string.
        """
        idn = self.inst.query("*IDN?").strip()
        if self.verbose:
            print(f"[AFG3011C] IDN: {idn}.")
        return idn

    def reset(self) -> None:
        """
        Reset the instrument to factory defaults.
        """
        self.inst.write("*RST")
        if self.verbose:
            print("[AFG3011C] Instrument reset to defaults.")

    def clear(self) -> None:
        """
        Clear the status and event registers.
        """
        self.inst.write("*CLS")
        if self.verbose:
            print("[AFG3011C] Status registers cleared.")

    def beep(self) -> None:
        """
        Emit a short beep sound from the instrument.
        """
        self.inst.write("SYST:BEEP")
        if self.verbose:
            print("[AFG3011C] Beep command sent.")

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
                print("[AFG3011C] Connection closed.")
        except Exception as e:
            raise RuntimeError(f"[AFG3011C][ERROR] Failed to close connection: {e}")

    # ------------------------------------------------------------------
    # Basic waveform control
    # ------------------------------------------------------------------
    def set_function(self, func: str) -> None:
        """
        Select the output waveform type.

        Parameters
        ----------
        func : str
            Waveform type. Valid options are defined in `__FUNCTIONS`.

        Raises
        ------
        ValueError
            If the waveform type is not valid.
        """
        func = func.upper()
        if func not in self.__FUNCTIONS:
            raise ValueError(
                f"[AFG3011C][ERROR] Invalid function '{func}'. "
                f"Valid options: {sorted(self.__FUNCTIONS)}."
            )
        self.inst.write(f"SOUR1:FUNC {func}")
        if self.verbose:
            print(f"[AFG3011C] Function set to {func}.")

    def get_function(self) -> str:
        """
        Query the currently selected waveform type.

        Returns
        -------
        str
            Current waveform type as in `__FUNCTIONS`.
        """
        func = self.inst.query("SOUR1:FUNC?").strip()
        if self.verbose:
            print(f"[AFG3011C] Current function: {func}.")
        return func

    def set_frequency(self, freq: float) -> None:
        """
        Set the output frequency.

        Parameters
        ----------
        freq : float
            Frequency in hertz. Valid ranges (min, max) are defined in __FREQ_RANGE
            depending on the current waveform type.

        Raises
        ------
        ValueError
            If DC function is set.
            If the frequency is outside the allowed range.
        """
        func = self.get_function().upper()
        if func == "DC":  # Frequency makes no sense for DC
            raise ValueError(
                "[AFG3011C][ERROR] DC mode does not support frequency setting."
            )
        fmin, fmax = self.__FREQ_RANGE[func]
        if not (fmin <= freq <= fmax):  # Check range
            raise ValueError(
                f"[AFG3011C][ERROR] Frequency {freq} Hz out of range for {func}: "
                f"{fmin}–{fmax} Hz."
            )
        self.inst.write(f"SOUR1:FREQ {freq}")
        if self.verbose:
            print(f"[AFG3011C] Frequency set to {freq} Hz.")

    def get_frequency(self) -> float:
        """
        Query the current output frequency.

        Returns
        -------
        float
            Frequency in hertz.
        """
        val = float(self.inst.query("SOUR1:FREQ?"))
        if self.verbose:
            print(f"[AFG3011C] Frequency = {val} Hz.")
        return val

    def set_amplitude(self, ampl: float) -> None:
        """
        Set the output amplitude.

        Parameters
        ----------
        ampl : float
            Peak-to-peak amplitude in volts. See Notes for valid values.

        Notes
        -----
        The minimum allowed amplitude depends on the output impedance and is
        defined in `__AMPL_MIN`.

        The maximum amplitude depends on the offset because both share the same
        output voltage limit. The instrument enforces:

            | offset ± amplitude/2 |  ≤  Vlimit

        where Vlimit is defined in `__V_LIMIT`.

        Changing amplitude may restrict the valid range of offset, and vice versa.

        Raises
        ------
        ValueError
            If amplitude exceeds lower hardware limits.
            If amplitude exceeds higher hardware limits.
        """
        impedance = self.get_output_impedance().upper()
        amin = self.__AMPL_MIN[impedance]
        if not (amin <= ampl):  # Check min value
            raise ValueError(
                f"[AFG3011C][ERROR] Amplitude {ampl} Vpp lower than "
                f"{amin} Vpp for {impedance} Ω."
            )
        vpk = ampl / 2.0
        offset = self.get_offset()
        vlimit = self.__V_LIMIT[impedance]
        if (offset + vpk) > vlimit or (offset - vpk) < -vlimit:  # Check combined range
            raise ValueError(
                f"[AFG3011C][ERROR] Amplitude {ampl} Vpp with offset {offset} V "
                f"exceeds output voltage limits ±{vlimit} V for {impedance} Ω."
            )
        self.inst.write(f"SOUR1:VOLT {ampl}")
        if self.verbose:
            print(f"[AFG3011C] Amplitude set to {ampl} Vpp.")

    def get_amplitude(self) -> float:
        """
        Query the current output amplitude.

        Returns
        -------
        float
            Amplitude in volts peak-to-peak.
        """
        val = float(self.inst.query("SOUR1:VOLT?"))
        if self.verbose:
            print(f"[AFG3011C] Amplitude = {val} Vpp.")
        return val

    def set_offset(self, offset: float) -> None:
        """
        Set DC offset voltage.

        Parameters
        ----------
        offset : float
            Offset voltage in volts. See Notes for valid values.

        Notes
        -----
        The allowable offset depends on the current amplitude and output
        impedance. The instrument enforces a combined constraint:

            | offset ± amplitude/2 |  ≤  Vlimit

        where Vlimit is defined in `__V_LIMIT`.

        Because offset and amplitude share the same output voltage limit,
        changing either parameter may restrict the valid range of the other.

        Raises
        ------
        ValueError
            If offset exceeds hardware limits.
        """
        impedance = self.get_output_impedance().upper()
        ampl = self.get_amplitude()
        vpk = ampl / 2.0
        vlimit = self.__V_LIMIT[impedance]
        if (offset + vpk) > vlimit or (offset - vpk) < -vlimit:  # Check combined range
            raise ValueError(
                f"[AFG3011C][ERROR] Offset {offset} V with amplitude {ampl} Vpp "
                f"exceeds output voltage limits ±{vlimit} V for {impedance} Ω."
            )
        self.inst.write(f"SOUR1:VOLT:OFFS {offset}")
        if self.verbose:
            print(f"[AFG3011C] Offset set to {offset} V.")

    def get_offset(self) -> float:
        """
        Query the current DC offset.

        Returns
        -------
        float
            Offset voltage in volts.
        """
        val = float(self.inst.query("SOUR1:VOLT:OFFS?"))
        if self.verbose:
            print(f"[AFG3011C] Offset = {val} V.")
        return val

    # ------------------------------------------------------------------
    # Impedance control
    # ------------------------------------------------------------------
    def set_output_impedance(self, mode: str) -> None:
        """
        Set the output impedance mode.

        Parameters
        ----------
        mode : str
            Output impedance mode. Valid values are defined in `__IMPEDANCE_MODES`.

        Raises
        ------
        ValueError
            If an invalid impedance mode is provided.
        """
        mode = mode.upper()
        if mode not in self.__IMPEDANCE_MODES:
            raise ValueError(
                f"[AFG3011C][ERROR] Invalid impedance mode '{mode}'. "
                f"Valid options: {sorted(self.__IMPEDANCE_MODES)}."
            )
        self.inst.write(f"OUTP1:IMP {mode}")
        if self.verbose:
            print(f"[AFG3011C] Output impedance set to {mode} Ω.")

    def get_output_impedance(self) -> str:
        """
        Query the current output impedance mode.

        Returns
        -------
        str
            Impedance mode as in `__IMPEDANCE_MODES`.
        """
        val = self.inst.query("OUTP1:IMP?").strip()
        if val == "99.0e36":  # Tektronix uses "99.0e36" to indicate High-Z
            val = "INF"
        elif val == "50e0":
            val = "50"
        if self.verbose:
            print(f"[AFG3011C] Current output impedance: {val} Ω.")
        return val

    # ------------------------------------------------------------------
    # Output control
    # ------------------------------------------------------------------
    def set_output_state(self, state: bool) -> None:
        """
        Set the output channel state.

        Notes
        -----
        This operation should always be the last operation before starting the
        experiment since the use of *OPC? guarantees that the instrument is in
        the required state.

        Parameters
        ----------
        state : bool
            ``True`` to enable the output, ``False`` to disable it.

        """
        cmd = "ON" if state else "OFF"
        self.inst.write(f"OUTP1:STAT {cmd}")
        self.inst.query("*OPC?")
        if self.verbose:
            print(f"[AFG3011C] Output set to {cmd}.")

    def get_output_state(self) -> bool:
        """
        Query whether the output is currently enabled.

        Returns
        -------
        bool
            ``True`` if output is enabled, ``False`` otherwise.
        """
        state = self.inst.query("OUTP1:STAT?").strip()
        if self.verbose:
            print(f"[AFG3011C] Output state: {'ON' if state == '1' else 'OFF'}.")
        return state == "1"


if __name__ == "__main__":
    afg = AFG3011C("USB::0x0699::0x034F::C020348::INSTR", verbose=True)

    # General communication and status
    afg.idn()
    afg.reset()
    afg.clear()
    afg.beep()

    # Basic waveform control
    afg.set_function("SIN")
    afg.set_output_impedance("INF")
    afg.get_function()
    afg.set_frequency(200)
    afg.get_frequency()
    afg.set_offset(0.013)
    afg.get_offset()
    afg.set_amplitude(10.0005)
    afg.get_amplitude()

    # Impedance control
    afg.set_output_impedance("INF")
    afg.get_output_impedance()

    # Output control
    afg.set_output_state(True)
    afg.get_output_state()

    # Close connection
    afg.close()
