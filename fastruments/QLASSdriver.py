"""
QLASS DRIVER

This module provides a high-level Python interface for controlling the
16-channel QLASS current driver via RS-232/USB serial communication. The board
was devoleped at DEIB (contacts: Giulia Acconcia, Ivan Labanca).

It implements the custom ASCII protocol defined in the Excel report provided
by the DEIB team.

The driver supports two primary operation modes:
1. Static Mode: for setting constant DC current values.
2. Timing Mode: for composing arbitrary piecewise-constant current sequences
   within the device's operational range.
"""

import pyvisa
from Instrument import Instrument
from typing import List, Optional, Sequence, Union


class CurrentDriver(Instrument):
    """
    High-level interface for the QLASS current driver.

    This class handles the custom serial protocol developed by the DEIB team.
    TODO: implement timing mode.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. ``'COM5'``).
    timeout : int, optional
        Communication timeout in milliseconds (default: ``5000``).
    do_autoupdate : bool, optional
        If ``True``, the set_current() method will immediately call the 
        update() method, applying directly the changes in DAC values
        (default: ``False``).
    verbose : bool, optional
        If ``True``, prints informational messages (default: ``True``).

    Attributes
    ----------
    inst : pyvisa.Resource
        Active VISA resource object.
    verbose : bool
        Flag controlling console output.
    """

    def __init__(self, resource: str, timeout: int = 5000, do_autoupdate: bool = False, verbose: bool = True):
        self.resource = resource
        self.timeout = timeout
        self.verbose = verbose
        self.do_autoupdate = do_autoupdate
        self.inst = None
        self.connect()

    def connect(self) -> None:
        """
        Establish connection with the instrument using specific serial parameters.
        """
        try:
            rm = pyvisa.ResourceManager()
            if self.verbose:
                print(f'VISA backend: {rm.visalib}')
                print(f'[QLASS] Attempting connection to {self.resource} out of the following resources found by pyvisa: {rm.list_resources()}.')
            self.inst = rm.open_resource(self.resource)
            # Specific serial configuration as requested
            self.inst.baud_rate = 460800
            self.inst.data_bits = 8
            self.inst.parity = pyvisa.constants.Parity.none
            self.inst.stop_bits = pyvisa.constants.StopBits.one
            self.inst.flow_control = pyvisa.constants.ControlFlow.none
            self.inst.timeout = self.timeout
            # Dictionary containing pairings between FSR code and corresponding current compliance
            self.ranges = {0:2.77,
                           1:25,
                           2:47.72}
            # Common terminators for serial interfaces
            self.inst.read_termination = "\r"
            self.inst.write_termination = "\r"
        except Exception as e:
            raise ConnectionError(
                f"[QLASS][ERROR] Could not connect to current driver: {e}."
            )
        try:
            self.idn()
            if self.verbose:
                print("[QLASS] Connected successfully.")
        except Exception as e:
            raise RuntimeError(f"[QLASS][ERROR] Failed to query IDN: {e}.")

    def idn(self) -> str:
        """
        Query the instrument identification string.

        Returns
        -------
        str
            The identification string returned by the instrument.
        """
        try:
            # Using commands from the driver documentation:
            res = self.inst.query("$V").strip()
            if self.verbose:
                print(f"[QLASS] Identification: {res}.")
            return res
        except Exception:
            if self.verbose:
                print("[QLASS][ERROR] IDN command not supported or no response.")
            return "Unknown device."

    def reset(self) -> None:
        """
        Reset the instrument to factory default settings.
        """
        self.inst.write("$R")
        if self.verbose:
            print("[QLASS] Instrument reset.")
    
    def set_current(self,ch: int,val: float) -> str:
        """
        Sets a current value in mA to a specified channel.
        Returns the string sent by the board as response.
        Does not automatically update the provided current unless 
        self.do_autoupdate is set to True.
        
        Parameters
        ----------
        ch : int
            Channel number to which current must be applied.
        val : float
            Current in mA.

        Returns
        -------
        str
            The response string returned by the instrument.
        Raises
        ------
        ValueError
            If current exceeds the active current compliance.
            If an invalid channel number is provided.

        """
        # Retrieve current operating range
        max_current = self.range()

        #Input sanity check
        if ch >= 16 or ch<0:
            raise ValueError(f'[QLASS][ERROR] Channel number {ch} is invalid (must be between 0 and 15).')
        if val <0 or val >= max_current:
            raise ValueError(f'[QLASS][ERROR] Current value higher than currently set compliance (set value: {val}mA, current compliance: {max_current}mA).')

        #Compute DAC value to apply
        val_DAC = int(val/max_current*(2**16-1))

        #Apply current
        res = self.inst.query(f'$D{ch:02d},{val_DAC}')
        #Catch failed current application
        if res == 'Ready':
            print(f'[QLASS][ERROR] set_current_mA(ch={ch},val={val}) method failed being delivered to the board (DAC value = {val_DAC}).')
        else:
            if self.verbose:
                print(f'[QLASS] Current at channel {ch} set to {val}mA (DAC value = {val_DAC}).')
            if self.do_autoupdate:
                self.update()
        
        return res
    
    def set_current_level(self,ch: int,val: int) -> str:
        """
        Sets a current value in mA to the specified channel.
        Returns the string sent by the board as response.
        Does not automatically update the provided current unless 
        self.do_autoupdate is set to True.
        
        Parameters
        ----------
        ch : int
            Channel number to which current must be applied.
        val : int
            Current level in bits.

        Returns
        -------
        str
            The response string returned by the instrument.
        Raises
        ------
        ValueError
            If an invalid current level is provided.
            If an invalid channel number is provided.

        """
        # Retrieve current operating range
        max_current = self.range()

        #Input sanity check
        if ch >= 16 or ch<0:
            raise ValueError(f'[QLASS][ERROR] Channel number {ch} is invalid (must be between 0 and 15).')
        if val <0 or val >= 2**16:
            raise ValueError(f'[QLASS][ERROR] Cannot set {val} to DAC: level must be between 0 and 65535.')

        #Compute DAC value to apply
        val_mA = int(val*max_current/(2**16-1))

        #Apply current
        res = self.inst.query(f'$D{ch:02d},{val}')
        #Catch failed current application
        if res == 'Ready':
            print(f'[QLASS][ERROR] set_current_level(ch={ch},val={val}) method failed being delivered to the board (DAC value = {val}).')
        else:
            if self.verbose:
                print(f'[QLASS] Current at channel {ch} set to {val_mA}mA (DAC value = {val}).')
            if self.do_autoupdate:
                self.update()
        
        return res

    def update(self) -> str:
        """
        Updates DAC values that have been changed since the last launch of this method
        or since the initialization of this instrument.
        Returns the string sent by the board as response.
        This method gets called automatically if the attribute self.do_autoupdate is True
        whenever the set_current_level or set_current method is run successfully.

        
        Returns
        -------
        str
            The response string returned by the instrument. (Should be 'Done' if no errors occur)
        """
        res = self.inst.query("$U")
        if res == 'Done':
            if self.verbose:
                print('[QLASS] DAC values updated.')
        else:
            print(f'[QLASS][ERROR] DAC values update failed; response = {res}')
        return res

    def close(self) -> None:
        """
        Close the VISA connection to the instrument.

        Notes
        -----
        Should always be called before program termination to release the COM resource.

        Raises
        ------
        RuntimeError
            If the resource cannot be cleanly closed.
        """
        try:
            self.inst.close()
            if self.verbose:
                print("[QLASS] Connection closed.")
        except Exception as e:
            raise RuntimeError(f"[QLASS][ERROR] Failed to close connection: {e}.")
        
    # ------------------------------------------------------------------
    # Properties: instantaneous device state
    # ------------------------------------------------------------------
    @property
    def current(self) -> List[float]:
        """
        Instantaneous currents (mA).
        """
        i = []
        imax = self.range
        for ch in range(16):
            level_ch = float(self.query(f'$D{ch}?'))
            i.append(imax*level_ch/(65535))        
        return i


    @property
    def range(self) -> float:
        """
        Current range currently employed (mA).
        (Corresponding codes: 0 -> 2mA, 1 -> 20mA, 2 -> 47.72mA)
        """
        
        res = self.inst.query("$F?")
        code = int(res)
        if code not in [0,1,2]:
            raise RuntimeError(f'[QLASS][ERROR] Invalid FSR code retrieved: code retrieved is {res} (type: {type(res)})')
            
        else:
            return self.ranges[code]

    @property
    def voltage(self) -> List[float]:
        """
        Instantaneous voltages (V).
        """
        pass #TODO: implement

    @property
    def power(self) -> List[float]:
        """
        Instantaneous electrical power (mW).
        """
        pass #TODO: remove this when the self.voltage property is introduced
        #return [v * i for v, i in zip(self.voltage, self.current)]

    @property
    def resistance(self) -> List[Optional[float]]:
        """
        Instantaneous electrical resistance (Ohm) or None on division errors.
        """
        pass #TODO: remove this when the self.voltage property is introduced
        # R = []
        # for v, i in zip(self.voltage, self.current):
        #     try:
        #         R.append(1000.0 * v / i)
        #     except Exception:
        #         R.append(None)
        # return R


if __name__ == "__main__":

    drv = None

    try:
        # Initialization on COM5
        drv = CurrentDriver('ASRL6::INSTR', timeout=2000, verbose=True)

        # Basic identification
        drv.idn()

        # Placeholder for future core operations
        # drv.set_current(10.0)
        drv.reset()

    except Exception as e:
        print(f"{e}")

    finally:
        if drv is not None:
            drv.close()
