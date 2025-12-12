#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 13 15:27:01 2025

@author: Francesco Ceccarelli

This module provides low-level bindings to the OptoTest OPM150 instrument
through the vendor-supplied dynamic library `OP710M_64.dll`.

It exposes all DLL functions, argument types, and return types using
Python's `ctypes` interface, enabling higher-level control modules
(such as `core.py`) to communicate with the instrument in a safe and
explicit manner.

The interface covers power reading, wavelength configuration, temperature
queries, module selection, and general USB communication management.

Examples
--------
Typical usage involves importing this driver from a higher-level class
that wraps these functions:

>>> from lib.instruments.opm150 import op710m_dll
>>> handle = op710m_dll.c_uint64()
>>> op710m_dll.OpenUSBDevice(0, handle)
0
>>> op710m_dll.ReadPower(op710m_dll.c_double())
0
>>> op710m_dll.CloseDriver()
0

References
----------
OptoTest OP710M DLL Programmer Reference Manual
(consult manufacturer documentation for complete API details).
"""

from ctypes import (
    cdll, c_int, c_double, c_char_p, POINTER,
    c_bool, c_byte, c_uint16, c_uint64
)
import os
from enum import Enum


# ----------------------------------------------------------------------
# DLL Loading
# ----------------------------------------------------------------------
dllPath = os.path.dirname(__file__)
op_dll = cdll.LoadLibrary(os.path.join(dllPath, "OP710M_64.dll"))

# ----------------------------------------------------------------------
# DLL Function Definitions
# ----------------------------------------------------------------------
ActiveModule = op_dll.ActiveModule
ActiveModule.argtypes = [c_int]
ActiveModule.restype = c_int

Backlight = op_dll.Backlight
Backlight.argtypes = [c_int]
Backlight.restype = c_int

CloseDriver = op_dll.CloseDriver
CloseDriver.argtypes = []
CloseDriver.restype = c_int

ConvertPower = op_dll.ConvertPower
ConvertPower.argtypes = [c_int, c_int, POINTER(c_double)]
ConvertPower.restype = c_int

GetActiveChannel = op_dll.GetActiveChannel
GetActiveChannel.argtypes = [POINTER(c_int)]
GetActiveChannel.restype = c_int

GetChannelBuffer = op_dll.GetChannelBuffer
GetChannelBuffer.argtypes = []
GetChannelBuffer.restype = c_int

GetDLLRev = op_dll.GetDLLRev
GetDLLRev.argtypes = []
GetDLLRev.restype = c_int

GetDLLStatus = op_dll.GetDLLStatus
GetDLLStatus.argtypes = []
GetDLLStatus.restype = c_int

GetFWRevision = op_dll.GetFWRevision
GetFWRevision.argtypes = []
GetFWRevision.restype = c_int

GetModuleID = op_dll.GetModuleID
GetModuleID.argtypes = [POINTER(c_int)]
GetModuleID.restype = c_int

GetModuleNumber = op_dll.GetModuleNumber
GetModuleNumber.argtypes = [POINTER(c_int)]
GetModuleNumber.restype = c_int

GetTemperature = op_dll.GetTemperature
GetTemperature.argtypes = [POINTER(c_double), c_int]
GetTemperature.restype = c_int

GetUSBDeviceCount = op_dll.GetUSBDeviceCount
GetUSBDeviceCount.argtypes = [POINTER(c_int)]
GetUSBDeviceCount.restype = c_int

GetUSBDeviceDescription = op_dll.GetUSBDeviceDescription
GetUSBDeviceDescription.argtypes = [c_int, POINTER(c_char_p)]
GetUSBDeviceDescription.restype = c_int

GetUSBSerialNumber = op_dll.GetUSBSerialNumber
GetUSBSerialNumber.argtypes = [c_int, POINTER(c_char_p)]
GetUSBSerialNumber.restype = c_int

GetUSBStatus = op_dll.GetUSBStatus
GetUSBStatus.argtypes = [POINTER(c_bool)]
GetUSBStatus.restype = c_int

GetWavelength = op_dll.GetWavelength
GetWavelength.argtypes = [POINTER(c_int), POINTER(c_int), POINTER(c_int)]
GetWavelength.restype = c_int

NextWavelength = op_dll.NextWavelength
NextWavelength.argtypes = [POINTER(c_int), POINTER(c_int), POINTER(c_int)]
NextWavelength.restype = c_int

OpenDriver = op_dll.OpenDriver
OpenDriver.argtypes = [c_uint64]
OpenDriver.restype = c_int

OpenUSBDevice = op_dll.OpenUSBDevice
OpenUSBDevice.argtypes = [c_int, POINTER(c_uint64)]
OpenUSBDevice.restype = c_int

ReadAnalog = op_dll.ReadAnalog
ReadAnalog.argtypes = [POINTER(c_int), POINTER(c_int), POINTER(c_int)]
ReadAnalog.restype = c_int

ReadChannelBuffer = op_dll.ReadChannelBuffer
ReadChannelBuffer.argtypes = [c_int, POINTER(c_double)]
ReadChannelBuffer.restype = c_int

ReadChannelBufferRaw = op_dll.ReadChannelBufferRaw
ReadChannelBufferRaw.argtypes = [c_int, c_uint16, POINTER(c_byte)]
ReadChannelBufferRaw.restype = c_int

ReadLoss = op_dll.ReadLoss
ReadLoss.argtypes = [POINTER(c_double)]
ReadLoss.restype = c_int

ReadPower = op_dll.ReadPower
ReadPower.argtypes = [POINTER(c_double)]
ReadPower.restype = c_int

ReferencePower = op_dll.ReferencePower
ReferencePower.argtypes = [POINTER(c_double)]
ReferencePower.restype = c_int

RemoteMode = op_dll.RemoteMode
RemoteMode.argtypes = [c_int]
RemoteMode.restype = c_int

SelectModule = op_dll.SelectModule
SelectModule.argtypes = [c_int]
SelectModule.restype = c_int

SetAbsolute = op_dll.SetAbsolute
SetAbsolute.argtypes = []
SetAbsolute.restype = c_int

SetActiveChannel = op_dll.SetActiveChannel
SetActiveChannel.argtypes = [c_int]
SetActiveChannel.restype = c_int

SetAutoRange = op_dll.SetAutoRange
SetAutoRange.argtypes = [c_int]
SetAutoRange.restype = c_int

SetGain = op_dll.SetGain
SetGain.argtypes = [c_int]
SetGain.restype = c_int

SetOPMMode = op_dll.SetOPMMode
SetOPMMode.argtypes = [c_int]
SetOPMMode.restype = c_int

SetReference = op_dll.SetReference
SetReference.argtypes = []
SetReference.restype = c_int

SetSamplingSpeed = op_dll.SetSamplingSpeed
SetSamplingSpeed.argtypes = [c_byte]
SetSamplingSpeed.restype = c_int

SetWavelength = op_dll.SetWavelength
SetWavelength.argtypes = [c_int]
SetWavelength.restype = c_int


# ----------------------------------------------------------------------
# Enumerations
# ----------------------------------------------------------------------
class ErrorCodes(Enum):
    """Enumeration of possible DLL return codes and communication errors."""
    NO_USB_DEVICE_FOUND = -5
    COMMUNICATION_ERROR = -4
    USB_READ_ERROR = -3
    USB_WRITE_ERROR = -2
    FAIL = -1
    OK_0 = 0
    OK_1 = 1
    INVALID_HANDLE = 1
    DEVICE_NOT_FOUND = 2
    DEVICE_NOT_OPENED = 3
    IO_ERROR = 4


class ModuleID(Enum):
    """Enumeration of supported OptoTest module identifiers."""
    OP250 = 10
    OPM510 = 11
    OP710 = 12
    OP831 = 13
    OP930 = 14
    OP750 = 15
    OP815 = 16
    OP1100 = 17
    OP1021 = 18
    OP1302 = 19
    OP815D = 20
    OP720 = 21
    OP850 = 22
    OP280 = 23
    OP715 = 24
    OP712 = 25
    OP931 = 26
    OP931_FTTX = 27
    OP480 = 28


class Wavelengths(Enum):
    """Commonly supported wavelengths (in nanometers)."""
    nm850 = 850
    nm980 = 980
    nm1300 = 1300
    nm1310 = 1310
    nm1480 = 1480
    nm1550 = 1550
    nm1625 = 1625
    nm1650 = 1650
