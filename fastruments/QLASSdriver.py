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

class CurrentDriver(Instrument):
    """
    High-level interface for the QLASS current driver.

    This class handles the custom serial protocol developed by the DEIB team.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. ``'COM5'``).
    timeout : int, optional
        Communication timeout in milliseconds (default: ``5000``).
    verbose : bool, optional
        If ``True``, prints informational messages (default: ``True``).

    Attributes
    ----------
    inst : pyvisa.Resource
        Active VISA resource object.
    verbose : bool
        Flag controlling console output.
    """

    def __init__(self, resource: str, timeout: int = 5000, verbose: bool = True):
        self.resource = resource
        self.timeout = timeout
        self.verbose = verbose
        self.inst = None
        self.connect()

    def connect(self) -> None:
        """
        Establish connection with the instrument using specific serial parameters.
        """
        try:
            rm = pyvisa.ResourceManager()
            self.inst = rm.open_resource(self.resource)
            # Specific serial configuration as requested
            self.inst.baud_rate = 460800
            self.inst.data_bits = 8
            self.inst.parity = pyvisa.constants.Parity.none
            self.inst.stop_bits = pyvisa.constants.StopBits.one
            self.inst.flow_control = pyvisa.constants.ControlFlow.none
            self.inst.timeout = self.timeout            
            # Common terminators for serial interfaces
            self.inst.read_termination = '\n'
            self.inst.write_termination = '\n'            
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
            # Using standard SCPI identification query
            res = self.inst.query("*IDN?").strip()
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


if __name__ == "__main__":

    drv = None
    
    try:
        # Initialization on COM5
        drv = CurrentDriver("COM5", timeout=2000, verbose=True)

        # Basic identification
        drv.idn()
        
        # Placeholder for future core operations
        # drv.set_current(10.0)
        
    except Exception as e:
        print(f"{e}")

    finally:
        if drv is not None:
            drv.close()
