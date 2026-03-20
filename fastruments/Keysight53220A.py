"""
KEYSIGHT 55220A

This module provides a high-level Python interface for controlling Keysight 
55220A Universal frequency counter / timer via USB using the PyVISA library.

Implements the core SCPI command set derived from the ...
manual

The `AFG3011C` class allows for ...

"""

import pyvisa
from Instrument import Instrument

class KEYSIGHT53220A(Instrument):
    
    def __init__(self, resource: str):
        self.resource = resource
        self.connect()
        
    def connect(self):
        rm = pyvisa.ResourceManager()
        # self.inst = rm.open_resource(self.resource)
        self.inst = rm.open_resource('USB0::0x0957::0x1807::MY63260252::INSTR')
        # try identifica
        self.idn()
        print("[53220A] Connected successfully.")
    
    def idn(self):
        idn = self.inst.query("*IDN?").strip()
        print(f"[53220A] IDN: {idn}.")
        return idn

    def close(self):
        self.inst.close()
    
    def reset(self):
        self.inst.write("*RST")
        print("[53220A] Instrument reset to defaults.")
        
    def clear(self):
        self.inst.write("*CLS")
        print("[53220A] Status registers cleared.")
        
    def beep(self):
        self.inst.write("SYST:BEEP")
        print("[53220A] Beep command sent.")
        
    
    """
    -------------------
    OPERAZIONI
    -------------------
    
    """
    
    def impedance(self, imp: float):
        self.inst.write(f"INP:IMP {imp}")
        print(f"Impedance at {imp} ohm")
        
    """
    FUNZIONI DA IMPLEMENTARE
    coupling AC DC
    autoset
    """
