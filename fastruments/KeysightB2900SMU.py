# Mattia Bossi 11/12/2025

"""
KeysightSM B2900 Series
Precision Source/Measure Unit

This module provides a high-level Python interface for controlling Tektronix
KeysightSM B2900 Series Precision Source/Measure Unit via USB using the PyVISA library.

Implements the core SCPI command set derived from the Keysight
B2900A Programming Manual.

The `KeysightSM` class allows to set input Current/Voltage and measure output 
Current/Voltage/Resistance, designed for laboratory automation
in photonic and electronic testing setups.
"""
import pyvisa
from Instrument import Instrument


class KeysightSM(Instrument):
    """
    High-level interface for the KeysightSM B2900 Series
    Precision Source/Measure Unit.

    Parameters
    ----------
    resource : str
        VISA resource string (e.g. ``'USB0::0x0957::0xCE18::MY51143784::INSTR'``)
        specifying the connected instrument.
    timeout : int, optional
        Communication timeout in milliseconds (default: ``5000``).
    channel: int
        Number of the output channel of the sourcemeter
        
    Attributes
    ----------
    inst : pyvisa.Resource
        Active VISA session object.
    model : str
        Model name retrieved from the identification query.

    """

    __CURR_LIMIT = {
        6.0: 3.03,  # If |V| <= 6.0 V   -> I max = 3.03 A
        21.0: 1.515,  # If |V| <= 21.0 V  -> I max = 1.515 A
        210.0: 0.105  # If |V| <= 210.0 V -> I max = 0.105 A
    }

    __VOLT_LIMIT = {
        0.105: 210.0,  # If |I| <= 0.105 A -> V max = 210.0 V
        1.515: 21.0,  # If |I| <= 1.515 A -> V max = 21.0 V
        3.03: 6.0  # If |I| <= 3.03 A  -> V max = 6.0 V
    }

    __MAX_LIMITS = {
        "VOLT": 210.0,
        "CURR": 3.03
    }

    def __init__(self, timeout: int = 5000, channel: int = 1) -> None:
        """
        Initialize communication with the KeysightSM B2900 instrument.
        """
        self.name = "USB0::0x0957::0xCE18::MY51143784::INSTR"
        self._channel = channel
        self.timeout = timeout

    # ------------------------------------------------------------------
    # General communication and status
    # ------------------------------------------------------------------

    def connect(self) -> None:

        """
        Establish the VISA connection with the SMU.

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

    def idn(self) -> str:
        """
        Query the instrument identification string.

        Returns
        -------
        str
            Full identification string.
        """
        idn = self.instrument.query("*IDN?").strip()
        return idn

    def clear(self) -> None:
        """
        Clear the status and event registers.
        """
        self.instrument.write("*CLS")
        print("Status registers cleared.")

    def close(self) -> None:
        """
        Closes the connection with the Keysight object.
        TODO: implement this in an higher order object
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
    def channel(self) -> int:
        """Getter for channel"""
        return self._channel

    @channel.setter
    def channel(self, value):
        if not isinstance(value, int):
            raise TypeError("Channel value has to be an integer number")
        if value not in (1, 2):
            raise ValueError("Channel value can be either 1 or 2")
        self._channel = value

    @property
    def measurement_mode(self):
        """Getter of the measurement mode for the specified channel"""
        return self.instrument.query(f':SENS{self.channel}:FUNC:ON?')

    @measurement_mode.setter
    def measurement_mode(self, mode: str) -> None:
        """
        Enables the specified measurement function on the selected channel of the instrument.
        :param mode: selects the parameter to be measured. It can either be a voltage, a current or a resistance

        """
        if not isinstance(mode, str):
            raise TypeError("'mode' parameter has to be a string")
        elif mode not in ('VOLT', 'CURR', 'RES'):
            raise ValueError("'mode' parameter can only be set to 'VOLT' for voltage, "
                             "'CURR' for current or 'RES' for resistance")
        self.instrument.write(f':SENS{self._channel}:FUNC "{mode}"; :FORM:ELEM:SENS {mode}')
        print(f"Measurement mode set to {mode}")

    def set_source_value(self, source: str, value: float) -> None:
        """
        Changes the output level of the selected source channel immediately.
        :param source: selects the source of which you want to change the value. It can be either voltage or current.
        :param value: the desired output value of the selected source.
        """
        if not isinstance(source, str):
            raise TypeError("'mode' parameter has to be a string")
        elif source not in ("VOLT", "CURR"):
            raise ValueError("'source' parameter can only be set to 'VOLT' for voltage, 'CURR' for current")
        max_limit = self.__MAX_ABS_LIMITS[source]
        if abs(value) > max_limit:
            raise ValueError(f"Cannot apply {source} over ±{max_limit}. Requested: {value}")
        self.instrument.write(f':SOURCE{self._channel}:{source}:LEV:IMM:AMPL {value}')
        print(f"{source} source value set to {value}")

    def set_compliance(self, source: str, value: float) -> None:
        """
        Sets the compliance value of the specified channel.
        The setting value is applied to both positive and negative sides.
        :param source: selects the source of which you want to set the compliance. It can be either voltage or current.
        :param value: the desired compliance value of the selected source

        Note that if you set a voltage source value, you can set a compliance on the current and viceversa.
        """
        if not isinstance(source, str):
            raise TypeError("'mode' parameter has to be a string")
        elif source not in ('VOLT', 'CURR'):
            raise ValueError("'source' parameter can only be set to 'VOLT' for voltage, 'CURR' for current")

        abs_value = abs(value)

        if source == 'CURR':
            current_volt = float(self.instrument.query(f":SOUR{self._channel}:VOLT?"))
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
            current_curr = float(self.instrument.query(f":SOUR{self._channel}:CURR?"))
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

        trip_status = int(self.instrument.query(f":SENS{self._channel}:{source}:PROT:TRIP?"))
        if trip_status == 0:
            print(
                "Attention: the selected source was not in compliance state. "
                "You may want to set the source value on the other parameter."
            )

        self.instrument.write(f":SENS{self._channel}:{source}:PROT {abs_value}")
        print(f"Compliance of the {source} source set to {abs_value}")

    @property
    def integration_time(self):
        """Getter for the integration time of the instrument"""
        return self.instrument.query(':SENS:CURR:DC:APER?')

    @integration_time.setter
    def integration_time(self, time: float):
        """
        Sets the integration time for one point measurement on the selected channel of the instrument
        :param channel: Select the channel
        :param time: the desired integration time. Minimum value is 8e-6 seconds, maximum is 2 seconds
        """
        if 8 * 10 ** -6 < time < 2:
            raise ValueError("Integration time cannot be smaller than 8e-6 or greater than 2 seconds")

        self.instrument.write(f':SENS{self._channel}:CURR:APER {time}')

    def measure(self, channel: int):
        """
        Executes a spot (one-shot) measurement on the selected channel of the instrument
        :param channel: selects the channel
        :return: The measurement value, along with its time stamp
        """
        self.channel = channel
        result = self.instrument.query(f":MEAS? (@{channel})")
        return float(result)


if __name__ == "__main__":
    print('inizio')
    test = KeysightSM()
    test.clear()
    test.measurement_mode(mode='CURR')
    test.set_source_value('VOLT', 2)
    test.set_compliance('CURR', 0.1)
    print(test.measure(1))
    test.close()
    print('fine')
