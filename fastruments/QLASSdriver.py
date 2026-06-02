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
from pyvisa.constants import BufferOperation
from fastruments.Instrument import Instrument
from typing import List, Optional, Sequence, Union
import numpy as np
import time


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
        self.sleep = 0.010
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
                           1:25.0,
                           2:47.72}
            self._sequences = np.full((16,8,2),fill_value=-1,dtype=int)
            self._current_mode = 'constant'
            # Common terminators for serial interfaces
            self.inst.read_termination = "\n\r"
            self.inst.write_termination = "\n\r"
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
        #Reset returns three lines: b'Reset...\n\r$M=>Menu\n\rReady\n\r'
        #To ensure buffer is empty after resetting, we do this:
        res = None
        while res!= 'Ready':
            res = self.inst.read()

        self.flush_serial()
        if self.verbose:
            print("[QLASS] Instrument reset.")

    def flush_serial(self):
        """
        Flushes read serial buffer.

        Notes
        -----
        Since the serial buffer is emptied FIFO, it is best to ensure that the
        buffer is emptied via this method before sending a query in order to 
        ensure that the response is correct.
        """
        self.inst.flush(BufferOperation.discard_read_buffer)
        if self.verbose:
            print('[QLASS] Read buffer flushed.')

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
        

    # ------------------------------------------------------
    # Methods for current driver operation.
    # ------------------------------------------------------

        
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
        max_current = self.ranges[self.range]

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
            print(f'[QLASS][ERROR] set_current(ch={ch},val={val}) method failed being delivered to the board (DAC value = {val_DAC}).')
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
        max_current = self.ranges[self.range]

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
        self.flush_serial()
        res = self.inst.query("$U")
        if res.strip() == 'Done':
            if self.verbose:
                print('[QLASS] DAC values updated.')
        else:
            print(f'[QLASS][ERROR] DAC values update failed; response = {res}')
        return res
        

    # ------------------------------------------------------------------
    # Properties: instantaneous device state
    # ------------------------------------------------------------------

    @property
    def current(self) -> List[float]:
        """
        Instantaneous currents (mA).
        """

        pass # TODO implement

    @property
    def range(self) -> int:
        """
        Current range currently employed (numerical code).
        (Corresponding codes: 0 -> 2.77mA, 1 -> 25mA, 2 -> 47.72mA)
        """

        res = self.inst.query("$F?")
        # print(f'res at line 311: {res}')
        # Res is of format 'Calib.=0; FSR=N', therefore we split it
        # in two, then again around = and see which is the FSR
        parts = res.strip().split(';')
        for part in parts:
            key, value = part.strip().split('=')
            if key == "FSR":
                fsr = int(value)
        self.flush_serial()

        if fsr not in [0,1,2]:
            raise RuntimeError(f'[QLASS][ERROR] Invalid FSR code retrieved: is {res} (type: {type(res)}), should be 0, 1 or 2 (type: int)')
        else:
            if self.verbose:
                print(f'[QLASS] FSR = {fsr}.')
            return fsr

    @range.setter
    def range(self,val: int):
        """
        Sets current range (numerical code). Technically, this method is the
        setter function of the range property, and it is called whenever 
        CurrentDriver.range = N is used.
        (Corresponding codes: 0 -> 2.77mA, 1 -> 25mA, 2 -> 47.72mA)

        Raises
        ------
            ValueError: if FSR to be set is not 0, 1, or 2
        """
        # Input sanity check
        if val not in [0,1,2]:
            raise ValueError(f'[QLASS][ERROR] Tried to set invalid FSR code : is {val} (type: {type(val)}), should be 0, 1 or 2 (type: int)')
        
        # Setting the FSR
        res = self.inst.query(f"$F{val}")
        # Res is of format 'Calib.=0; FSR=N', therefore we split it
        # in two, then again around = and see which is the FSR
        parts = res.strip().split(';')
        for part in parts:
            key, value = part.strip().split('=')
            if key == "FSR":
                fsr = int(value)
        self.flush_serial()
        
        if fsr == val:
            if self.verbose:
                print(f'[QLASS] Current range set to {val} - now max current is {self.ranges[val]}mA.')
            return
        else:
            raise RuntimeError(f'[QLASS][ERROR] Current range setting to {val} failed - retrieved FSR value is {fsr}.')

    @property
    def voltage(self) -> List[int]:
        """
        Instantaneous voltages (ADC level; TODO calibrate).
        """
        self.flush_serial()
        self.inst.write('$L')
        # raw = self.inst.read_bytes(200, break_on_termchar=False)
        # print(repr(raw))
        # return [1]

        lines = [self.inst.read() for _ in range(16)]
        #The response to $L is the voltages at each channel, written as
        # V_ADC[CH]=00XYZ\r\n
        #so we can extract the ADC level of each channel as follows:
        
        out=[]
        for this_ch in lines:
            _,val = this_ch.strip().split('=')
            out.append(int(val))      
        return out

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


    # ------------------------------------------------------------------
    # Sequences mode implementation
    # ------------------------------------------------------------------
    
    @property
    def current_mode(self) -> str:
        '''
        Returns a string dictating the currently active mode:
        - 'constant' for static regime (default when starting up, after idling, or after calling $t0)
        - 'sequence' for dynamic regime (after calling $t1)
        '''
        return self._current_mode


    @current_mode.setter
    def current_mode(self,val: str) -> bool:
        '''
        Sets current mode to val.
        'timing' functions as alias of 'sequence', but will print a warning.
        'idle' will call the idle function, setting the _current_mode to 'constant' in the process.
        
        Raises
        ------
            ValueError: if provided value is not 'constant','sequence','timing', or 'idle'
            TypeError: if provided value is not a string
        '''
        valid_str = ['constant','idle','sequence','timing']
        if not isinstance(val,str):
            try:
                raise TypeError(f'[QLASS][ERROR] Provided current mode {val} must be a string, is {type(val)}.')
            except:
                raise TypeError(f'[QLASS][ERROR] Provided current mode is not a string and not convertible to one, is {type(val)}.')
        if val not in valid_str:
            raise ValueError(f'[QLASS][ERROR] Provided current mode {val} is not among valid current modes.')
        
        if val == 'constant':
            self.start_constant_mode()
        if val == 'sequence':
            self.start_sequence_mode()
        if val == 'idle':
            self.idle()
        if val == 'timing':
            self.start_sequence_mode()
            print('[QLASS][WARNING] Setting current_mode to sequences after current_mode = \'timing\' was called.')

        return
    

    @property
    def sequences(self) -> Sequence:
        '''
        Multidimensional array for indirect access to the _sequences array.
        Has shape (16,8,2):
        - 16 channels
        - 8 time steps
        - [0] for step duration, [1] for DAC value applied

        Example
        -------
        To obtain the time duration of all steps:
        sequences[:,:,0]
        To obtain the DAC values applied by pin 7:
        sequences[7,:,1]
        To see the first step duration of all channels:
        sequences[:,0,1]
        '''
        out = self._sequences.copy()
        out.setflags(write=False)
        return out

    
    def set_zero(self) -> None:
        '''
        Sets manually the current to all channels to zero.
        '''
        for i in range(16):
            self.set_current_level(i,0)


    def start_constant_mode(self) -> None:
        '''
        Start application of the saved values to the DACs in a constant 
        manner.
        '''
        self.inst.write('$t0')
        self._current_mode = 'constant'


    def start_sequence_mode(self) -> None:
        '''
        Start application of the saved sequences. 
        TODO testing
        '''
        if -1 in self._sequences:
            print('[QLASS][WARNING] Uninitialized sequence elements detected.')
        self.inst.write('$t1')
        self.flush_serial()
        self._current_mode = 'sequence'
    

    def idle(self) -> None:
        '''
        Sets the board in an idle state: constant mode + zero current at DACs.
        '''
        self.set_zero()
        self.start_constant_mode()
        self._current_mode = 'constant'


    @property
    def sequences(self):
        '''
        Multidimensional array for indirect access to the _sequences array.
        Has shape (16,8,2):
        - 16 channels
        - 8 time steps
        - [0] for step duration, [1] for DAC value applied

        This property does not have a setter element, but its value must be modified by using the methods
        set_sequence_element, set_sequence_array, and set_all_sequences. Via direct access, this property
        is set to read only, and so will probably raise an error if tried to be modified directly.

        Example
        -------
        To obtain the time duration of all steps:
        sequences[:,:,0]
        To obtain the DAC values applied by pin 7:
        sequences[7,:,1]
        To see the first step duration of all channels:
        sequences[:,0,1]
        '''
        out = self._sequences.copy()
        out.setflags(write=False)
        return out
    

    def set_sequence_element(self,ch:int,pos:int,time:int,val:int):
        '''
        Sets a single sequence element for a given pin.
        For traceability, also modifies the array _sequences.

        Parameters
        ----------
        ch : int
            The channel whose sequence needs to be changed. Goes from 0 to 15.
        pos : int
            The position in the sequence to change. Goes from 0 to 7.
        time : int
            Duration of this sequence step, in steps of 500 us.
            Goes from 0 (500 us) to 999 (500 ms).
        val : int
            Value to apply to the DAC for this step.
            As all DAC values, goes from 0 to 65535.
        '''

        if self._current_mode == 'sequence':
            print('[QLASS][WARNING] Tried to modify sequences while in sequence mode. Idling.')
            self.idle()
            

        try:
            ch = int(ch)
            pos = int(pos)
            time = int(time)
            val = int(val)
        except ValueError:
            raise ValueError('[QLASS][ERRROR] Invalid input values of set_sequence_element:\n'
                            f'ch = {ch}, pos = {pos}, time = {time}, val = {val}')
        except TypeError:
            raise TypeError('[QLASS][ERRROR] Invalid input type of set_sequence_element:\n'
                            f'ch = {type(ch)}, pos = {type(pos)}, time = {type(time)}, val = {type(val)}')

        # input sanity check
        if ch < 0 or ch >= 16:
            raise ValueError(f'[QLASS][ERROR] ch = {ch} in set_sequence_element({ch},{pos},{time},{val}): must be between 0 and 15')
        if pos < 0 or pos >= 8:
            raise ValueError(f'[QLASS][ERROR] pos = {pos} in set_sequence_element({ch},{pos},{time},{val}): must be between 0 and 7')
        if time < 0 or time >= 1000:
            raise ValueError(f'[QLASS][ERROR] time = {time} in set_sequence_element({ch},{pos},{time},{val}): must be between 0 and 999')
        if val < 0 or val >= 65536:
            raise ValueError(f'[QLASS][ERROR] val = {val} in set_sequence_element({ch},{pos},{time},{val}): must be between 0 and 65535')
        
        #send command to board
        res = self.inst.query(f'$s{ch:02d},{pos:01d},{time:03d},{val}')
        exp_res = f'ch{ch:02d} [step{pos:01d}] for {time:03d} cycles = {val}'
        # TODO check whether self.update is needed here
        
        if res.strip() != exp_res:
            self._sequences[ch,pos,0] = -1
            self._sequences[ch,pos,1] = -1
            raise RuntimeError(f'[QLASS][ERROR] Failed sequence element writing: set_sequence_element({ch},{pos},{time},{val}) -> {res}')

        #update sequences array
        self._sequences[ch,pos,0] = time
        self._sequences[ch,pos,1] = val

        if self.verbose:
            print(f'[QLASS] Element set for channel {ch}, position {pos}: val = {val} for {time} steps')
        return
    
    
    def set_sequence_array(self,ch,time_arr,val_arr):
        '''
        Sets the sequence for a whole channel.
        time_arr and val_arr must be 8 entries-long numpy arrays.

        Parameters
        ----------
        ch : int
            The channel whose sequence needs to be changed. Goes from 0 to 15.
        time_arr : List of int
            Duration of all sequence steps, in steps of 500 us.
            Goes from 0 (500 us) to 999 (500 ms).
            Must have shape (8,)
        val_arr : List of int
            Values to apply to the DAC for all steps.
            As all DAC values, goes from 0 to 65535.
            Must have shape (8,)
        '''
        # input sanity checks
        time_arr = np.squeeze(time_arr)
        val_arr = np.squeeze(val_arr)
        if time_arr.shape != (8,):
            raise ValueError(f'[QLASS][ERROR] Invalid shape for time_arr: {time_arr.shape} (must be (8,))')
        if val_arr.shape != (8,):
            raise ValueError(f'[QLASS][ERROR] Invalid shape for val_arr: {val_arr.shape} (must be (8,))')
        
        for i, (t, v) in enumerate(zip(time_arr, val_arr)):
            self.set_sequence_element(ch, i, t, v)
        
        return
    
    
    def set_all_sequences(self,time_seqs,val_seqs):
        '''
        Sets the complete sequences to the memory of the board.
        time_seqs and val_seqs must be (16,8) matrices

        Parameters
        ----------
        time_arr : List of list of int
            Duration of all sequence steps, in steps of 500 us.
            Goes from 0 (500 us) to 999 (500 ms).
            Must have shape (16,8)
        val_arr : List of list of int
            Values to apply to the DACs for all steps.
            As all DAC values, goes from 0 to 65535.
            Must have shape (16,8)
        '''

        time_seqs = np.squeeze(time_seqs)
        val_seqs = np.squeeze(val_seqs)

        if time_seqs.shape != (16,8):
            raise ValueError(f'[QLASS][ERROR] Invalid shape for time_seqs: {time_seqs.shape} (must be (16,8))')
        if val_seqs.shape != (16,8):
            raise ValueError(f'[QLASS][ERROR] Invalid shape for val_seqs: {val_seqs.shape} (must be (16,8))')
        
        for i in range(16):
            self.set_sequence_array(i,time_seqs[i],val_seqs[i])
        return
    

    def initialize_sequences(self):
        '''
        Sets the values of all elements in the sequence to 0 mA for 500 ms.
        '''
        was_verbose = self.verbose
        if was_verbose:
            print('[QLASS] Initializing sequences to zero.')
            self.verbose = False

        try:
            self.set_all_sequences(time_seqs = np.full((16,8),fill_value=999,dtype=int), val_seqs = np.zeros((16,8),dtype=int))
        finally:
            self.verbose = was_verbose

        return



if __name__ == "__main__":

    drv = None

    try:
        # Initialization on COM5
        error = None
        drv = CurrentDriver('ASRL6::INSTR', timeout=2000, verbose=True)

        # Basic identification
        drv.idn()

        # Placeholder for future core operations
        # drv.set_current(10.0)
        drv.reset()
        #drv.range=1
        drv.set_current(ch=0,val=1.0)
        drv.update()
        input('Waiting for confirmation to proceed')
        print(drv.voltage)
        drv.set_current(ch=7,val=1.2)
        drv.update()
        input('Waiting for confirmation to proceed')
        print(drv.voltage)
        drv.reset()
        
    
    except Exception as e:
        print(f"{e}")
        error = e

    finally:
        if drv is not None:
            drv.close()
        if error is not None:
            raise(error)
