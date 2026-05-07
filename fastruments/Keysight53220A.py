"""
KEYSIGHT 53220A Frequency Counter

High-level Python interface for controlling a Keysight 53220A
Universal Frequency Counter/Timer using PyVISA library.

Implements common SCPI commands for:
- Identification
- Reset / clear
- Input configuration (impedance, coupling, threshold)
- Trigger configuration
- Measurement functions (frequency, period, voltage, duty cycle, etc.)

Function not yet implemented (not sure how much can be useful):
    settings: INPut{1|2}:PROBe
    measurements: PHASE,    TIME INTERVAL

"""

import pyvisa
from Instrument import Instrument


class Keysight53220A(Instrument):
    """
    High-level interface for Keysight 53220A.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. 'USB0::0x0957::0x1807::MY63260252::INSTR')
        specifying the connected instrument.
    verbose : bool
        If True, prints console messages.
    
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
    >>> from fastruments.Keysight53220A import Keysight53220A
    >>> freq = Keysight53220A('USB0::0x0957::0x1807::MY63260252::INSTR')
    [53220A] IDN: Agilent Technologies,53220A,MY63260252,03.02-1924.2831-3.15-4.16-127-159-35
    [53220A] Connection successful.
    >>> freq.set_input_impedance(1,50)
    [53220A] CH1: Impedance set to 50 Ω
    >>> freq.get_input_impedance(1)
    [53220A] CH1: Current impedance: +5.00000000E+001 Ω.
    >>> freq.set_coupling(1, 'AC')
    [53220A] CH1: Coupling set to AC
    >>> freq.set_range(1, 5)
    [53220A] CH1: Input range set to 5 V.
    >>> freq.meas_volt_min(1)
    [53220A] CH1: Signal minimum voltage is -0.520525813 V
    >>> freq.measure_frequency(1, 250e-6, 50, 'POS')
    [53220A] CH1: Auto level set to ON
    [53220A] CH1: Threshold set to 50 % p2p
    [53220A] CH1: Slope sign set to POS
    [53220A] Measurement gate time set to 0.00025 s
    [53220A] CH1: Frequency = 1000000.52795438 HZ
    >>> freq.measure_totalize(1, 0.1)
    [53220A] CH1: Totalize (in 0.1 s) = 100000.0
    >>> freq.measure_risetime(1, 10, 90)
    [53220A] CH1: Rising time (10-90 %) = 3.01500183569027e-07 s
    >>> freq.close()
    [53220A] Connection closed.
    
    """
    
    __IMPEDANCE_MODES = {50, 1e6}
    
    __AUTOLEVEL_MODES = {"ON", "OFF", "ONCE"}
    
    __SLOPE_SIGN = {"POS", "NEG"}
    
    __RANGE_MODES = {5, 50}
    
    @staticmethod
    def __check_channel(channel: int) -> None:
        if channel not in [1, 2]:
            raise ValueError(
                "[53220A][ERROR] Invalid channel." 
                f"Expected values are 1 or 2, given {channel}."
                )
        return None
        
    @staticmethod
    def __check_boundary(value: float, min_val:float, max_val:float) -> None:
        if value < min_val or value > max_val:
            raise ValueError(
                "[53220A][ERROR] Invalid value." 
                f"Expected values are between {min_val} and {max_val}, given {value}."
                )
        return None
    
    @staticmethod
    def __check_edges(lower: int, upper:int) -> None:
        if lower < 10 or lower > 85:
            raise ValueError(
                "[53220A][ERROR] Invalid value." 
                f"Lower edge must be between 10% and 85%, given {lower}."
                )
        if upper < 15 or upper > 90:
            raise ValueError(
                "[53220A][ERROR] Invalid value." 
                f"Upper edge must be between 15% and 90%, given {upper}."
                )
        if upper <= lower:
            raise ValueError(
                "[53220A][ERROR] Invalid value." 
                f"Upper_edge must be bigger than lower_edge, given {lower} and {upper}."
                )
            
        return None
    
    @staticmethod
    def __check_gate_step(gate: float, step:float) -> None:
        if (gate*1e6)%10 != 0:
            raise ValueError(
                "[53220A][ERROR] Invalid gate value." 
                f"Expected values have step of {step}, given {gate}."
                )
        return None

    def __init__(self, resource: str, verbose: bool = True) -> None:
        
        """
        Initialize communication with the KEYSIGHT 53220A Frequency Counter instrument.
        """
        
        self.resource = resource
        self.verbose = verbose
        self.connect()
        
        self.freq_max = 350e6
        self.freq_min = 0.1
        
        self.period_max = 10
        self.period_min = 2.8e-9
        
        self.res_max = 1e-5
        self.res_min = 1e-15
        
        self.gate_max = 1
        self.gate_min = 100e-6
        self.gate_step = 10e-6

    # ---------------------------------------------------------
    # General communication and status
    # ---------------------------------------------------------
    def connect(self) -> None:
        """
        Establish the VISA connection and verify communication.
        """
        try:
            rm = pyvisa.ResourceManager()
            self.inst = rm.open_resource(self.resource)
        except Exception as e:
            raise ConnectionError(f"[53220A][ERROR] Failed to connect: {e}")

        try:
            self.idn()
            if self.verbose:
                print("[53220A] Connection successful.")
        except Exception as e:
            raise RuntimeError(f"[53220A][ERROR] IDN query failed: {e}")

    def idn(self) -> str:
        """
        Query the identification string.

        Returns
        -------
        str
            Full identification string.
        """
        idn = self.inst.query("*IDN?").strip()
        if self.verbose:
            print(f"[53220A] IDN: {idn}")
        return idn

    def reset(self) -> None:
        """Reset the instrument to factory defaults."""
        self.inst.write("*RST")
        if self.verbose:
            print("[53220A] Instrument reset.")

    def clear(self) -> None:
        """Clear status and error registers."""
        self.inst.write("*CLS")
        if self.verbose:
            print("[53220A] Status registers cleared.")
            
    def beep(self) -> None:
        """
        Emit a short beep sound from the instrument.
        """
        self.inst.write("SYST:BEEP")
        if self.verbose:
            print("[53220A] Beep command sent.")

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
                print("[53220A] Connection closed.")
        except Exception as e:
            raise RuntimeError(f"[53220A][ERROR] Failed to close: {e}")


    # ---------------------------------------------------------
    # Input Channel Configuration
    # ---------------------------------------------------------

    def set_input_impedance(self, channel: int, imp: int) -> None:
        """
        Set input impedance for a channel.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        imp : int
            Impedance mode: 50 or 1e6.
        """
        self.__check_channel(channel)
        
        if imp not in self.__IMPEDANCE_MODES:
            raise ValueError(
                f"[53220A][ERROR] Invalid impedance value '{imp}'. "
                f"Valid options: {sorted(self.__IMPEDANCE_MODES)}."
            )

        self.inst.write(f"INP{channel}:IMP {imp}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Impedance set to {imp} Ω")
       
    def get_input_impedance(self, channel: int) -> int:
        """
        Query the current input impedance mode.
        
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        int
            Value of impedance.
        """
        self.__check_channel(channel)
        
        val = int(float(self.inst.query(f"INP{channel}:IMP?")))
        print(f"[53220A] CH{channel}: Current impedance: {val} Ω.")
        return val

    def set_coupling(self, channel: int, mode: str) -> None:
        """
        Set input coupling.

        Parameters
        ----------
        mode : str
            "AC" or "DC"
        """
        self.__check_channel(channel)
        
        mode = mode.upper()
        if mode not in {"AC", "DC"}:
            raise ValueError("[53220A][ERROR] Invalid coupling (AC or DC).")

        self.inst.write(f"INP{channel}:COUP {mode}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Coupling set to {mode}")

    def get_coupling(self, channel: int) -> str:
        """
        Query input coupling.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        Returns
        -------
        str
                Coupling mode.
        """
        self.__check_channel(channel)
        
        mode = self.inst.query(f"INP{channel}:COUP?").strip()
        if self.verbose:
            print(f"[53220A] CH{channel}: Current coupling is {mode}")
        return mode
    
    def set_slope(self, channel: int, sign: str) -> None:
        """ 
        Set sign of the slope
        Note: This command selects the active edge of the input signal
        that will be used for measurements.
        
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        sign: str
            slope sign "POS" or "NEG"        
        """
        self.__check_channel(channel)
        
        if sign not in self.__SLOPE_SIGN:
            raise ValueError(
                f"[53220A][ERROR] Invalid sign '{sign}'. "
                f"Valid options: {sorted(self.__SLOPE_SIGN)}."
            )

        self.inst.write(f"INP{channel}:SLOP {sign}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Slope sign set to {sign}")
        
    def get_slope(self, channel: int) -> str:
        """
        Query slope sign.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        Returns
        -------
        str
                Slope sign.
        """
        self.__check_channel(channel)
        
        sign = self.inst.query(f"INP{channel}:SLOP?").strip()
        if self.verbose:
            print(f"[53220A] CH{channel}: Current slope sign is {sign}")
        return sign
        
    def set_autolevel(self, channel: int, mode: str) ->None:
        """
        Set autolevel mode.
        Note: This command enables or disables automatic setting
        of the input threshold voltage (auto-leveling)

        Parameters
        ----------
        mode : str
            "ON" or "OFF"
        channel : int
            Input channel number (1 or 2).
        """
        self.__check_channel(channel)
        
        if mode not in self.__AUTOLEVEL_MODES:
            raise ValueError(
                f"[53220A][ERROR] Invalid mode value '{mode}'. "
                f"Valid options: {sorted(self.__AUTOLEVEL_MODES)}."
            )

        self.inst.write(f"INP{channel}:LEV:AUTO {mode}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Auto level set to {mode}")
            
    def get_autolevel(self, channel: int) -> str:
        """
        Query autolevel mode.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        
        Returns
        -------
        str
                Autolevel mode.
        """
        self.__check_channel(channel)
        
        mode = self.inst.query(f"INP{channel}:LEV:AUTO?").strip()
        if self.verbose:
            if mode == '0':
                mode = 'OFF'
                print(f"[53220A] CH{channel}: current auto level mode is {mode}")
            if mode == '1':
                mode = 'ON'
                print(f"[53220A] CH{channel}: current auto level mode is {mode}")
        return mode

    def set_threshold_relative(self, channel: int, perc: int) -> None:
        """
        This command sets the input threshold as a percentage of the
        peak-to-peak input voltage when auto-leveling in enabled.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        perc : int
            Threshold in percentage.

        """
        self.__check_channel(channel)
        
        self.inst.write(f"INP{channel}:LEV:REL {perc}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Threshold set to {perc} % p2p")
            
    def get_threshold_relative(self, channel: int) -> int:
        """
        This command query the input threshold as a percentage of the
        peak-to-peak input voltage when auto-leveling in enabled.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        int
            Threshold in percentage.

        """
        self.__check_channel(channel)
        
        perc = int(float(self.inst.query(f"INP{channel}:LEV:REL?")))
        if self.verbose:
            print(f"[53220A] CH{channel}: Current threshold is {perc} % p2p")
        return perc
    
    def set_range(self, channel: int, v_range: int) -> None:
        """
        This command selects the voltage range for the input channel.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        v_range : int
            Voltage range for the input channel in volt (5 V or 50 V).
        """
        
        self.__check_channel(channel)
        
        if v_range not in self.__RANGE_MODES:
            raise ValueError(
                f"[53220A][ERROR] Invalid mode value '{v_range}'. "
                f"Valid options: {sorted(self.__RANGE_MODES)}."
            )

        self.inst.write(f"INP{channel}:RANG {v_range}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Input range set to {v_range} V.")
        
    def get_range(self, channel: int) -> int:
        """
        This command query the voltage range for the input channel.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        int
            Voltage range for the input channel in volt (5 V or 50 V).
        """
        self.__check_channel(channel)
        
        v_range = int(float(self.inst.query(f"INP{channel}:RANG?")))
        if self.verbose:
            print(f"[53220A] CH{channel}: Current input range is {v_range} V.")
        
        return v_range
    
    # ---------------------------------
    """
    At the moment the following four parameter settings are not used
    """
    
    def set_threshold_level(self, channel: int, voltage: float) -> None:
        """
        This command sets the input threshold voltage for measurements. 

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        voltage : float
            Threshold in volts.

        """
        self.__check_channel(channel)
        
        self.inst.write(f"INP{channel}:LEV {voltage}")
        if self.verbose:
            print(f"[53220A] CH{channel}: Threshold set to {voltage} V")
            
    def get_threshold_level(self, channel: int) -> float:
        """
        This command query the input threshold voltage for measurements.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        float
            Threshold in volts.

        """
        self.__check_channel(channel)
        
        lev = float(self.inst.query(f"INP{channel}:LEV?"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Current threshold level is {lev} V")
        return lev
    
    def set_gate_time(self, gate: float) -> None:        
        """
        This command selects the resolution in terms of time for gating measurements.

        Parameters
        ----------
        gate : float
            Gate time in seconds.
        """
        
        self.inst.write(f"FREQ:GATE:TIME {gate}")
        if self.verbose:
            print(f"[53220A] Measurement gate time set to {gate} s")
            
    def get_gate_time(self) -> float:
        """
        This command query the resolution in terms of time for gating measurements.

        Returns
        -------
        float
            Gate time in seconds.

        """
        
        gate = float(self.inst.query("FREQ:GATE:TIME?"))
        if self.verbose:
            print(f"[53220A] Current measurement gate time is {gate} s")
        return gate
    
    # ---------------------------------------------------------
    # Measurement Functions: Max, min and P2P voltage of the signal
    # ---------------------------------------------------------    

    def meas_volt_max(self, channel: int) -> float:
        """
        This query measures and returns the maximum voltage of the input signal.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        float
            Maximum voltage of the input signal.

        """
        
        self.__check_channel(channel)
        
        v_max = float(self.inst.query(f"INP{channel}:LEV:MAX?"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Signal maximum voltage is {v_max} V")
        
        return v_max
        
    def meas_volt_min(self, channel: int) -> float:
        """
        This query measures and returns the minimum voltage of the input signal.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        float
            minimum voltage of the input signal.

        """
        
        self.__check_channel(channel)
        
        v_min = float(self.inst.query(f"INP{channel}:LEV:MIN?"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Signal minimum voltage is {v_min} V")
        
        return v_min
            
    def meas_volt_p2p(self, channel: int) -> float:
        """
        This query measures and returns the peak-to-peak voltage of the input signal.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        float
            peak-to-peak voltage of the input signal.

        """
        
        self.__check_channel(channel)
        
        p2p = float(self.inst.query(f"INP{channel}:LEV:PTP?"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Signal peak to peak voltage is {p2p} V")
        
        return p2p
    
    # ---------------------------------------------------------
    # Measurement Functions: FREQ Family
    # ---------------------------------------------------------
    def measure_frequency(self, channel: int, gate: float, rel_th:int, slope: str) -> float:
        """
        This command measures the frequency from the selected channel

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        gate : float
            Gating time of the measurement.
            Default value from sheet 0.1 s (value from 100 us to 1 s)
        rel_th : int
            Threshold leve for the measurement in percentage.
        slope: str
            slope sign of the threshold reference for the measurement ("POS" or "NEG")
        

        Returns
        -------
        float
            Value of frequency in Hz.
            
        """
        
        self.__check_channel(channel)
        self.__check_boundary(gate, self.gate_min, self.gate_max)
        self.__check_gate_step(gate, self.gate_step)
        
        self.inst.write(f"CONF:FREQ (@{channel})")
        
        self.set_autolevel(channel, 'ON')
        self.set_threshold_relative(channel, rel_th)
        self.set_slope(channel, slope)
        self.set_gate_time(gate)
        
        val = float(self.inst.query("READ?"))
        
        if self.verbose:
            print(f"[53220A] CH{channel}: Frequency = {val} Hz")
        return val
    
    def measure_period(
            self, channel: int, gate: float, rel_th:int, slope: str) -> float:
        """
        This command measures the period from the selected channel

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        gate : float
            Gating time of the measurement.
            Default value from sheet 0.1 s (value from 100 us to 1 s)
        rel_th : int
            Threshold leve for the measurement in percentage.
        slope: str
            slope sign of the threshold reference for the measurement ("POS" or "NEG")
        

        Returns
        -------
        float
            Value of period in s.
            
        """
        
        self.__check_channel(channel)
        self.__check_boundary(gate, self.gate_min, self.gate_max)
        self.__check_gate_step(gate, self.gate_step)
        
        self.inst.write(f"CONF:PER (@{channel})")
        
        self.set_autolevel(channel, 'ON')
        self.set_threshold_relative(channel, rel_th)
        self.set_slope(channel, slope)
        self.set_gate_time(gate)
        
        val = float(self.inst.query("READ?"))
        
        if self.verbose:
            print(f"[53220A] CH{channel}: Period = {val} s")
        return val
    
    # ---------------------------------------------------------
    # Measurement Functions: TIME INTERVAL Family
    # ---------------------------------------------------------
    
    def measure_falltime(self, channel: int, upper_edge: int, lower_edge: int) -> float:
        
        
        """
        Measures the falling edge time on the selected channel,
        using custom lower/upper percentage levels, default on sheet 10-90.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        upper_edge : int
            Upper threshold percentage.
        lower_edge : int
            Lower threshold percentage.

        Returns
        -------
        float
            Falling time in seconds.
        """

        self.__check_channel(channel)
        self.__check_edges(lower_edge, upper_edge)

        val = float(self.inst.query(f"MEAS:FTIM? {lower_edge},{upper_edge},(@{channel})"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Falling time ({upper_edge}-{lower_edge} %) = {val} s")

        return val
    
    def measure_risetime(self, channel: int, lower_edge: int, upper_edge: int) -> float:
        
        """
        Measures the rising edge time on the selected channel,
        using custom lower/upper percentage levels, default on sheet 10-90.
    
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        lower_edge : int
            Lower threshold percentage.
        upper_edge : int
            Upper threshold percentage.
    
        Returns
        -------
        float
            Rising time in seconds.
        """
    
        self.__check_channel(channel)
        self.__check_edges(lower_edge, upper_edge)
    
        val = float(self.inst.query(f"MEAS:RTIM? {lower_edge},{upper_edge},(@{channel})"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Rising time ({lower_edge}-{upper_edge} %) = {val} s")
    
        return val
    
    def measure_pwidth(self, channel: int, reference: int) -> float:
        """
        Measures the POSITIVE pulse width on the selected channel.
    
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        reference: int
            Input signal reference level in percentage, default by sheet 50%.
    
        Returns
        -------
        float
            Pulse width in seconds.
        """
    
        self.__check_channel(channel)
        self.__check_boundary(reference, 10, 90)
    
        val = float(self.inst.query(f"MEAS:PWID? {reference},(@{channel})"))
    
        if self.verbose:
            print(f"[53220A] CH{channel}: Positive pulse width at reference {reference}% = {val} s")
    
        return val
    
    def measure_nwidth(self, channel: int, reference: int) -> float:
        """
        Measures the NEGATIVE pulse width on the selected channel.
    
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        reference: int
            Input signal reference level in percentage, default by sheet 50%.
    
        Returns
        -------
        float
            Pulse width in seconds.
        """
    
        self.__check_channel(channel)
        self.__check_boundary(reference, 10, 90)
    
        val = float(self.inst.query(f"MEAS:NWID? {reference},(@{channel})"))
    
        if self.verbose:
            print(f"[53220A] CH{channel}: Negative pulse width at reference {reference}% = {val} s")
    
        return val
    
    def measure_pos_dutycycle(self, channel: int, reference: int) -> float:
        """
        Measures the POSITIVE duty cycle on the selected channel.
    
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        reference: int
            Input signal reference level in percentage, default by sheet 50%.
    
        Returns
        -------
        float
            Positive duty cycle in percentage.
        """
    
        self.__check_channel(channel)
        self.__check_boundary(reference, 10, 90)
    
        val = 100*float(self.inst.query(f"MEAS:PDUT? {reference},(@{channel})"))
    
        if self.verbose:
            print(f"[53220A] CH{channel}: Positive duty cycle at reference {reference}% = {val} %")
    
        return val
    
    def measure_neg_dutycycle(self, channel: int, reference: int) -> float:
        """
        Measures the NEGATIVE duty cycle on the selected channel.
    
        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        reference: int
            Input signal reference level in percentage, default by sheet 50%.
    
        Returns
        -------
        float
            Negative duty cycle in percentage.
        """
    
        self.__check_channel(channel)
        self.__check_boundary(reference, 10, 90)
    
        val = 100*float(self.inst.query(f"MEAS:NDUT? {reference},(@{channel})"))
    
        if self.verbose:
            print(f"[53220A] CH{channel}: Negative duty cycle at reference {reference}% = {val} %")
    
        return val
    
    def measure_single_period(self, channel: int) -> float:
        """
        Measures the single-shot period on the selected channel,
        if you want average period on many cycles use command measure_period(),
        reference is automatically set at 50%.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).

        Returns
        -------
        float
            Single period measurement in seconds.
            """

        self.__check_channel(channel)

        val = float(self.inst.query(f"MEAS:SPER? (@{channel})"))

        if self.verbose:
            print(f"[53220A] CH{channel}: Single period = {val} s")
            
        return val

    # ---------------------------------------------------------
    # Measurement Functions: TOTALIZE Family
    # ---------------------------------------------------------

    def measure_totalize(self, channel: int, gate_time: float) -> float:
        """
        This command perform a timed totalize measurements immediately triggered.

        Parameters
        ----------
        channel : int
            Input channel number (1 or 2).
        gate_time : float
            Gate time for totalize measurement in seconds.
            Default value from sheet 0.1 s (value from 1 us s to 1000 s)

        Returns
        -------
        float
            gate totalize measurement.

        """
        
        self.__check_channel(channel)
        self.__check_boundary(gate_time, self.gate_min, self.gate_max)
        
        val = float(self.inst.query(f"MEAS:TOT:TIM? {gate_time},(@{channel})"))
        if self.verbose:
            print(f"[53220A] CH{channel}: Totalize (in {gate_time} s) = {val}")
        return val
    
# ---------------------------------------------------------
# Example usage
# ---------------------------------------------------------
if __name__ == "__main__":
    
    freq = None
    
    try:
        
        freq = Keysight53220A('USB0::0x0957::0x1807::MY63260252::INSTR', verbose=True)

        freq.idn()
        freq.reset()
        freq.clear()
        freq.beep()
        
        freq.set_input_impedance(1,50)
        freq.get_input_impedance(1)
        freq.set_coupling(1, 'AC')
        freq.get_coupling(1)
        freq.set_range(1, 5)
        freq.get_range(1)
        freq.set_autolevel(1, 'ON')
        freq.get_autolevel(1)
        
        freq.meas_volt_min(1)
        freq.meas_volt_max(1)
        freq.meas_volt_p2p(1)
        
        freq.measure_frequency(1, 250e-6, 50, 'POS')
        freq.measure_period(1, 1e-3, 50, 'POS')
        
        freq.measure_risetime(1, 10, 90)
        freq.measure_falltime(1, 80, 20)
        freq.measure_pwidth(1, 50)
        freq.measure_nwidth(1, 50)
        freq.measure_pos_dutycycle(1, 50)
        freq.measure_neg_dutycycle(1, 50)
        freq.measure_single_period(1)
        
        freq.measure_totalize(1, 0.1)
        

    except Exception as e:
        msg = str(e)
        if not msg.startswith("[53220A][ERROR]"):
            msg = f"[53220A][ERROR] {msg}"
        print(msg)

    finally:
        if freq is not None:
            freq.close()