#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 8 17:30:00 2025

@author: Francesco Ceccarelli

This module provides a high-level Python interface for controlling Lfiber
Optical Switches (1xN Series) via RS-232/USB using the PyVISA library.

It implements the custom ASCII protocol defined in the Lfiber User Manuals,
supporting channel switching, queries, and automatic parsing of instrument
capabilities (wavelength range, fiber type, channel count).

Supported models include:
- Polarization-Maintaining (PM) Fiber Switches (LF-OSW-PM Series)
- Single-Mode (SM) Fiber Switches (LF-OSW-SM Series)
"""

import pyvisa
import time


class LF_OSW:
    """
    High-level interface for Lfiber 1xN Optical Fiber Switches.

    This class handles the custom serial protocol (non-SCPI) used by Lfiber
    switches. It automatically detects the number of channels and fiber characteristics
    upon initialization.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. ``'ASRL3::INSTR'`` for Serial/USB).
    timeout : int, optional
        Communication timeout in milliseconds (default: ``5000``).
    switching_delay : float, optional
        Wait time in seconds after sending a switching command and before 
        reading the response (default: ``0.1``). This ensures the hardware 
        completes the operation.
    verbose : bool, optional
        If ``True``, prints informational messages (default: ``True``).

    Attributes
    ----------
    inst : pyvisa.Resource
        Active VISA session object.
    verbose : bool
        Flag controlling console output.
    switching_delay : float
        Wait time (seconds) utilized during channel changes.
    model_info : dict
        Dictionary containing parsed device details (Model, Channels, Wavelength, Fiber Type).

    Examples
    --------
    >>> from lib.instruments.lfiber.core import LF_OSW
    >>> osw = LF_OSW('ASRL3::INSTR', verbose=True)
    [LF_OSW] IDN: LF-OSW-1X16-1550-PMF-09-10-R-FA.
    [LF_OSW] Model string parsed: Channels: 16, Wavelength: 1550 nm, Fiber: PMF.
    [LF_OSW] Connected successfully.
    >>> osw.set_channel(1)
    [LF_OSW] Switch set to channel 01.
    >>> current = osw.get_channel()
    [LF_OSW] Current channel: 01.
    >>> osw.reset()
    [LF_OSW] Instrument reset (channel 00).
    >>> osw.close()
    [LF_OSW] Connection closed.
    """

    # Protocol constants
    __BAUD_RATE = 9600
    __DATA_BITS = 8
    __STOP_BITS = pyvisa.constants.StopBits.one
    __PARITY = pyvisa.constants.Parity.none
    __START_CHAR = "<"
    __END_CHAR = ">"

    def __init__(self, resource: str, timeout: int = 5000, switching_delay: float = 0.1, verbose: bool = True) -> None:
        """
        Initialize communication with the Lfiber Optical Switch.

        Raises
        ------
        ConnectionError
            If the VISA resource cannot be opened.
        RuntimeError
            If the instrument identification fails or protocol is invalid.
        """
        self.verbose = verbose
        self.timeout = timeout
        self.switching_delay = switching_delay
        self.model_info = {}
        try:
            rm = pyvisa.ResourceManager("@py")
            self.inst = rm.open_resource(resource)
            self.inst.timeout = timeout
            if isinstance(self.inst, pyvisa.resources.SerialInstrument):        # Configure RS-232 specific parameters as per datasheet
                self.inst.baud_rate = self.__BAUD_RATE
                self.inst.data_bits = self.__DATA_BITS
                self.inst.stop_bits = self.__STOP_BITS
                self.inst.parity = self.__PARITY
                self.inst.read_termination = self.__END_CHAR                    # Read until '>'
                self.inst.write_termination = None                              # We manually add delimiters
        except Exception as e:
            raise ConnectionError(f"[LF_OSW][ERROR] Could not connect to optical switch: {e}.")
        try:
            self.__update_info(self.idn())
            if self.verbose:
                print("[LF_OSW] Connected successfully.")
        except Exception as e:
            raise RuntimeError(f"[LF_OSW][ERROR] Failed to query IDN: {e}.")

    # ------------------------------------------------------------------
    # Internal protocol helpers
    # ------------------------------------------------------------------
    def __query_cmd(self, command_body: str) -> str:
        """
        Send a framed command to the instrument and return the raw response payload.
    
        This method implements the low-level ASCII protocol used by Lfiber optical
        switches. The command is wrapped between the required start and end
        delimiters (`__START_CHAR` and `__END_CHAR`). The instrument replies
        using the same format, and the method extracts and returns only the
        content inside the delimiters.
    
        Parameters
        ----------
        command_body : str
            The body of the command to send, without start/end delimiters.
            Example: ``"OSW_OUT_01"``.
    
        Returns
        -------
        str
            The response string without delimiters. For example, a device reply
            ``"<OSW_OUT_OK>"`` becomes ``"OSW_OUT_OK"``.
    
        Notes
        -----
        This helper abstracts the serial framing protocol and is used by all
        higher-level query and command methods (such as `idn()`, `set_channel()`,
        and `get_channel()`).
        """        
        self.inst.write(f"{self.__START_CHAR}{command_body}{self.__END_CHAR}")
        response = self.inst.read()                                             # Read response. Since read_termination is '>', we get "<RESPONSE"
        return response.lstrip(self.__START_CHAR).strip()                       # Strip the leading '<'

    def __update_info(self, idn_str: str) -> dict:
        """
        Parse the identification string (e.g., LF-OSW-1X16-1550-PMF...>) to 
        determine number of channels and fiber properties.

        Parameters
        ----------
        idn_str : str
            Response string obtained from 'idn()'.
            
        Returns
        -------
        dict
            Dictionary containing 'model', 'channels', 'wavelength', 'fiber_type'.

        Raises
        ------
        ValueError
            If the model string has unexpected format.
        """
        # 
        model_parts = idn_str.split('-')                                        # Parameter idn_str is typically Model+Config (e.g., LF-OSW-1X16-1550-PMF...)
        if len(model_parts) <= 4:                                               # Check for correct format
            raise ValueError(f"[LF_OSW][ERROR] Could not parse model information from {idn_str}.")
        self.model_info = {                                                     # Build information dictionary about the device
            "model": idn_str,
            "channels": int(model_parts[2][2:]),
            "wavelength": model_parts[3],
            "fiber_type": model_parts[4]
        }
        if self.verbose:
            print(f"[LF_OSW] Model string parsed: Channels: {self.model_info['channels']}, "
                  f"Wavelength: {self.model_info['wavelength']} nm, Fiber: {self.model_info['fiber_type']}.")
        return self.model_info

    # ------------------------------------------------------------------
    # General communication and status
    # ------------------------------------------------------------------
    def idn(self) -> str:
        """
        Query the instrument identification string.
        
        Returns
        -------
        str
            Full identification string.
            
        Raises
        ------
        RuntimeError
            If the instrument responds with unexpected format.
        """
        raw_resp = self.__query_cmd("OSW_TYPE_?")                               # Protocol query: <OSW_TYPE_?>
        prefix = "OSW_TYPE_"
        if not raw_resp.startswith(prefix):
            raise RuntimeError(f"[LF_OSW][ERROR] Unexpected response format: {raw_resp}.")
        idn_str = raw_resp.replace(prefix, "")
        if self.verbose:
            print(f"[LF_OSW] IDN: {idn_str}.")
        return idn_str

    def reset(self) -> None:
        """
        Reset the optical switch (sets to channel 00).
        
        Notes
        ------
        Reset means that the input is not connected through one of the optical
        switch output channels.

        Raises
        ------
        RuntimeError
            If the instrument fails to reset.
        """
        resp = self.__query_cmd("OSW_OUT_00")                                   # Set channel to 00 resets the switch 
        time.sleep(self.switching_delay)                                        # Wait for hardware switching
        if resp == "OSW_OUT_OK":
            if self.verbose:
                print("[LF_OSW] Instrument reset (channel 00).")
        else:
             raise RuntimeError(f"[LF_OSW][ERROR] Reset failed. Response: {resp}.")

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
                print("[LF_OSW] Connection closed.")
        except Exception as e:
            raise RuntimeError(f"[LF_OSW][ERROR] Failed to close connection: {e}.")

    # ------------------------------------------------------------------
    # Channel control
    # ------------------------------------------------------------------
    def set_channel(self, channel: int) -> None:
        """
        Switch the optical path to the specified channel.

        Parameters
        ----------
        channel : int
            Target channel number (1 to `model_info['channels']`). 
            Setting 0 is equivalent to reset (handled by `reset()`).

        Raises
        ------
        ValueError
            If the channel is outside the valid range or the intrument reports
            overflow.
        RuntimeError
            If the instrument reports an error other than overflow.
        """
        if not (1 <= channel <= self.model_info['channels']):
            raise ValueError(
                f"[LF_OSW][ERROR] Invalid channel {channel}. "
                f"Valid range: 1 to {self.model_info['channels']}."
            )
        resp = self.__query_cmd(f"OSW_OUT_{channel:02d}")                       # Format command: OSW_OUT_XX (e.g., OSW_OUT_01)
        time.sleep(self.switching_delay)                                        # Wait for hardware switching
        if resp == "OSW_OUT_OK":                                                # Validate response (success: <OSW_OUT_OK>, error: <OSW_OUT_OVERFLOW>)
            if self.verbose:
                print(f"[LF_OSW] Switch set to channel {channel:02d}.")
        elif resp == "OSW_OUT_OVERFLOW":
             raise ValueError("[LF_OSW][ERROR] Channel overflow reported by device.")
        else:
             raise RuntimeError(f"[LF_OSW][ERROR] Failed to set channel. Response: {resp}.")

    def get_channel(self) -> int:
        """
        Query the currently active channel.

        Returns
        -------
        int
            Current channel number. Returns 00 if in reset state.

        Raises
        ------
        RuntimeError
            If the instrument responds with unexpected format.
        """
        resp = self.__query_cmd("OSW_OUT_?")                                    # Protocol query: <OSW_OUT_?>, expected response: <OSW_OUT_XX>
        prefix = "OSW_OUT_"
        if not resp.startswith(prefix):
            raise RuntimeError(f"[LF_OSW][ERROR] Unexpected response format: {resp}.")
        val_str = resp.replace(prefix, "")
        channel = int(val_str)
        if self.verbose:
            print(f"[LF_OSW] Current channel: {channel:02d}.")
        return channel
