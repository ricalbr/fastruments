# Mattia Bossi 11/12/2025

"""
KeysightSM B2900 Series Precision Source/Measure Unit Interface.

This module provides a high-level Python interface for controlling the
KeysightSM B2900 Series Precision Source/Measure Unit (SMU) via USB using
the PyVISA library.

The interface implements core SCPI commands derived from the
Keysight B2900A Programming Manual and is designed for laboratory
automation in photonic and electronic testing environments.

References
----------
Keysight Technologies, *B2900A/B2910A/B2920A Programming Guide*.

Classes
-------
KeysightSM
    High-level controller for the Keysight B2900 Series SMU.
"""

import pyvisa
import Instrument


class KeysightSM(Instrument):
    """
    High-level interface for the KeysightSM B2900 Series Precision
    Source/Measure Unit (SMU).

    This class provides methods to configure sourcing and measurement
    operations on the Keysight B2900 Series SMU, including voltage/current
    sourcing, compliance settings, integration time configuration, and
    spot measurements.

    Parameters
    ----------
    timeout : int, optional
        Communication timeout in milliseconds for VISA operations.
        Default is 5000 ms.

    Attributes
    ----------
    name : str
        VISA resource string identifying the connected instrument.
    timeout : int
        Communication timeout in milliseconds.
    instrument : pyvisa.resources.Resource
        VISA instrument handle created after connecting.
    _source_type : list of str or None
        Source mode (``'VOLT'`` or ``'CURR'``) for each channel.
    _source_value : list of float or None
        Source level set for each channel.
    _compliance_value : list of float or None
        Compliance limit for each channel.
    _measurement_mode : list of str or None
        Measurement mode (``'VOLT'``, ``'CURR'``, ``'RES'``) for each channel.
    _integration_time : list of float or None
        Integration time for each channel.

    Notes
    -----
    This class assumes a two-channel SMU configuration (channels 1 and 2).


    Examples
    --------
    Example of the intended usage pattern:

    >>>     test = KeysightSM()
    ...     test.connect()
    ...     test.clear()
    ...     test.set_measurement_mode(1, 'RES')
    ...     test.set_source(1, "VOLT", 0.5)
    ...     test.set_compliance(1, "CURR", 0.006)
    ...     test.measure(1)
    ...     test.clear()
    ...     test.close()
    """

    __CURR_LIMIT = {
        6.0: 3.03,
        21.0: 1.515,
        210.0: 0.105
    }

    __VOLT_LIMIT = {
        0.105: 210.0,
        1.515: 21.0,
        3.03: 6.0
    }

    __MAX_LIMITS = {
        "VOLT": 210.0,
        "CURR": 3.03
    }

    def __init__(self, timeout: int = 5000) -> None:
        """
        Initialize the KeysightSM object.

        This method initializes internal state variables but does not
        establish communication with the instrument.

        Parameters
        ----------
        timeout : int, optional
            VISA communication timeout in milliseconds.
        """
        self.name = "USB0::0x0957::0xCE18::MY51143784::INSTR"
        self._source_type: list[str] | list[None] = [None, None]
        self._source_value: list[float] | list[None] = [None, None]
        self._compliance_value: list[float] | list[None] = [None, None]
        self._measurement_mode: list[str] | list[None] = [None, None]
        self._integration_time: list[float] | list[None] = [None, None]
        self.timeout = timeout

    # ------------------------------------------------------------------
    # General communication and status
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """
        Establish the VISA connection with the SMU.

        This method initializes the VISA resource manager, opens the USB
        instrument resource, sets the communication timeout, verifies
        communication via an identification query, and resets the instrument.

        Raises
        ------
        ConnectionError
            If the VISA resource cannot be opened.
        RuntimeError
            If the instrument does not respond to the identification query.
        """
        print('Try to connect to instrument...')
        try:
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.name)
            self.instrument.timeout = self.timeout
        except Exception as e:
            raise ConnectionError(f"Could not connect: {e}")
        print('Success!')
        try:
            print(f'Hi! I am {self.idn()}')
        except Exception as e:
            raise RuntimeError(f"Failed to query IDN: {e}")
        self.reset()
        self._integration_time[0] = float(self.instrument.query(':SENS1:CURR:DC:APER?'))
        self._integration_time[1] = float(self.instrument.query(':SENS2:CURR:DC:APER?'))

    def idn(self) -> str:
        """
        Query the instrument identification string.

        Returns
        -------
        str
            Identification string returned by the ``*IDN?`` SCPI command.
        """
        idn = self.instrument.query("*IDN?").strip()
        return idn

    def clear(self) -> None:
        """
        Clear the status and event registers of the instrument.

        This sends the ``*CLS`` SCPI command.
        """
        self.instrument.write("*CLS")
        print("Status registers cleared.")

    def reset(self) -> None:
        """
        Reset the instrument to its default configuration.

        This clears volatile settings using the ``*RST`` SCPI command.
        """
        self.instrument.write("*RST")
        print("Instrument reset completed.")

    def close(self) -> None:
        """
        Close the connection with the instrument.

        Raises
        ------
        RuntimeError
            If the instrument connection cannot be closed.
        """
        print("Closing connection with instrument...")
        try:
            self.instrument.close()
            print("Connection successfully closed!")
        except Exception as e:
            raise RuntimeError(f'Failed to close connection: {e}')

    # ------------------------------------------------------------------
    # Basic controls
    # ------------------------------------------------------------------

    @property
    def measurement_mode(self):
        """
        list of str or None

        Measurement mode for each channel.

        Each element can be ``'VOLT'``, ``'CURR'``, ``'RES'``, or ``None``
        if not configured.
        """
        return self._measurement_mode

    def set_measurement_mode(self, channel: int, mode: str) -> None:
        """
        Enable a measurement function on a specific channel.

        Parameters
        ----------
        channel : int
            Channel number (1 or 2).
        mode : {'VOLT', 'CURR', 'RES'}
            Measurement quantity: voltage, current, or resistance.

        Raises
        ------
        TypeError
            If ``channel`` or ``mode`` have invalid types.
        ValueError
            If ``channel`` or ``mode`` have invalid values.
        """
        if not isinstance(mode, str):
            raise TypeError("'mode' parameter has to be a string")
        elif mode not in ('VOLT', 'CURR', 'RES'):
            raise ValueError("'mode' parameter can only be set to 'VOLT' for voltage, "
                             "'CURR' for current or 'RES' for resistance")
        if not isinstance(channel, int):
            raise TypeError("Channel value has to be an integer number")
        if channel not in (1, 2):
            raise ValueError("Channel value can be either 1 or 2")
        self.instrument.write(':SENS:FUNC:OFF:ALL')
        self.instrument.write(f':SENS{channel}:FUNC:ON "{mode}"; :FORM:ELEM:SENS {mode}')
        # self.instrument.write(f':SENS{self._channel}:FUNC:ON "{mode}"')
        print(f"Measurement mode on channel {channel} set to {mode}")
        self._measurement_mode[channel-1] = self.instrument.query(f':SENS{channel}:FUNC:ON?')

    @property
    def source_type(self):
        """
        list of str or None

        Source mode for each channel (``'VOLT'`` or ``'CURR'``).
        """
        return self._source_type

    @property
    def source_value(self):
        """
        list of float or None

        Source output level for each channel.
        """
        return self._source_value

    @property
    def compliance_value(self):
        """
        list of float or None

        Compliance limit for each channel.
        """
        return self._compliance_value

    def set_source(self, channel: int, source: str, value: float) -> None:
        """
        Set the source mode and output level on a channel.

        Parameters
        ----------
        channel : int
            Channel number (1 or 2).
        source : {'VOLT', 'CURR'}
            Source type: voltage or current.
        value : float
            Desired output level.

        Raises
        ------
        TypeError
            If parameters have invalid types.
        ValueError
            If parameters exceed instrument limits.
        """
        if not isinstance(source, str):
            raise TypeError("'mode' parameter has to be a string")
        elif source not in ("VOLT", "CURR"):
            raise ValueError("'source' parameter can only be set to 'VOLT' for voltage, 'CURR' for current")
        if not isinstance(channel, int):
            raise TypeError("Channel value has to be an integer number")
        if channel not in (1, 2):
            raise ValueError("Channel value can be either 1 or 2")

        um = "V" if source == "VOLT" else "A"

        self.instrument.write(F':SOURCE{channel}:FUNC:MODE {source}')
        self._source_type[channel - 1] = source
        max_limit = self.__MAX_LIMITS[source]
        if abs(value) > max_limit:
            raise ValueError(f"Cannot apply {source} over ±{max_limit}. Requested: {value}")
        self._source_value[channel-1] = value
        self.instrument.write(f':SOURCE{channel}:{source}:LEV:IMM:AMPL {value}')
        print(f"{source} source value on channel {channel} set to {value} {um}")

    def set_compliance(self, channel: int, source: str, value: float) -> None:
        """
        Set the compliance limit for the selected channel.

        The compliance parameter acts as a safety limit for the
        complementary quantity (current for voltage sourcing and
        voltage for current sourcing).

        Parameters
        ----------
        channel : int
            Channel number (1 or 2).
        source : {'VOLT', 'CURR'}
            Compliance type.
        value : float
            Compliance limit.

        Raises
        ------
        ValueError
            If compliance exceeds instrument safety limits.
        """
        if not isinstance(source, str):
            raise TypeError("'mode' parameter has to be a string")
        elif source not in ('VOLT', 'CURR'):
            raise ValueError("'source' parameter can only be set to 'VOLT' for voltage, 'CURR' for current")
        if not isinstance(channel, int):
            raise TypeError("Channel value has to be an integer number")
        if channel not in (1, 2):
            raise ValueError("Channel value can be either 1 or 2")
        if source == self._source_type[channel - 1]:
            raise ValueError("You are trying to set the compliance on the source parameter. "
                             "Please change to the other one")

        abs_value = abs(value)
        um = "V" if source == "VOLT" else "A"

        if source == 'CURR':
            current_volt = float(self.instrument.query(f":SOUR{channel}:VOLT?"))
            abs_v = abs(current_volt)

            max_i = None
            for threshold in sorted(self.__CURR_LIMIT.keys()):
                if abs_v <= threshold:
                    max_i = self.__CURR_LIMIT[threshold]
                    break

            if max_i is None:
                raise ValueError(
                    f"Voltage ({current_volt} V) exceeds the maximum limit of 210 V!"
                )
            if abs_value > max_i:
                raise ValueError(
                    f"Current compliance ({value} A) too high! "
                    f"At {current_volt} V the limit is {max_i} A."
                )

        elif source == 'VOLT':
            current_curr = float(self.instrument.query(f":SOUR{channel}:CURR?"))
            abs_i = abs(current_curr)

            max_v = None
            for threshold in sorted(self.__VOLT_LIMIT.keys()):
                if abs_i <= threshold:
                    max_v = self.__VOLT_LIMIT[threshold]
                    break

            if max_v is None:
                raise ValueError(
                    f"Current ({current_curr} A) exceeds the maximum limit of 3.03 A!"
                )
            if abs_value > max_v:
                raise ValueError(
                    f"Voltage compliance ({value} V) too high! "
                    f"At {current_curr} A the limit is {max_v} V."
                )

        self._compliance_value[channel - 1] = abs_value
        self.instrument.write(f":SENS{channel}:{source}:PROT {abs_value}")
        print(f"Compliance of the {source} source on channel {channel} set to {abs_value} {um}")

    @property
    def integration_time(self):
        """
        list of float or None

        Integration time (aperture) for each channel in seconds.
        """
        return self._integration_time

    def set_integration_time(self, channel: int, time: float):
        """
        Set the integration time for the selected channel.

        Parameters
        ----------
        channel : int
            Channel number (1 or 2).
        time : float
            Integration time in seconds (8e-6 to 2).

        Raises
        ------
        ValueError
            If time is outside the allowed range.
        """
        if 8 * 10 ** -6 > time or time > 2:
            raise ValueError("Integration time cannot be smaller than 8e-6 or greater than 2 seconds")
        if not isinstance(channel, int):
            raise TypeError("Channel value has to be an integer number")
        if channel not in (1, 2):
            raise ValueError("Channel value can be either 1 or 2")

        self.instrument.write(f':SENS{channel}:CURR:APER {time}')
        self._integration_time[channel-1] = float(self.instrument.query(f':SENS{channel}:CURR:DC:APER?'))
        print(f'Integration time on channel {channel} set to {time} s')

    def measure(self, channel: int):
        """
        Perform a spot (one-shot) measurement.

        Parameters
        ----------
        channel : int
            Channel number (1 or 2).

        Returns
        -------
        float
            Measured value corresponding to the active measurement mode.
        """
        result = self.instrument.query(f":MEAS? (@{channel})")
        return float(result)

    def disable_channel(self, channel: int):
        """
        Disable the output of the selected channel.

        Parameters
        ----------
        channel : int
            Channel number (1 or 2).
        """
        if not isinstance(channel, int):
            raise TypeError("Channel value has to be an integer number")
        if channel not in (1, 2):
            raise ValueError("Channel value can be either 1 or 2")
        self.instrument.write(f':OUTP{channel}:STAT OFF')
        print(f"Channel {channel} is off")
