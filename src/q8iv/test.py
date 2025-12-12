#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 9 11:52:00 2025

@author: Francesco Ceccarelli

Test script for basic functionality of the Qontrol Q8iv driver.

This file performs a sequential check of:
- Initialization and compliance configuration
- Current mode operations
- Voltage mode operations
- Shutdown and communication close

It is intended for manual testing and verification of driver methods.
"""

from core import Q8iv

drv = Q8iv('COM3', init_mode='i', transient=0.2, verbose=True)

# ------------------------------------------------------------------
# General compliance and status
# ------------------------------------------------------------------
drv.set_compliance(current=24.0, voltage=12.0)

# ------------------------------------------------------------------
# Core I/V operations
# ------------------------------------------------------------------
drv.set_current(0, 5.0)
drv.set_current([1, 2], [3.0, 7.5])
drv.get_current([0, 1, 2])
drv.get_voltage([0, 1, 2])
drv.set_all_zero()
drv.get_current([0, 1, 2])
drv.get_voltage([0, 1, 2])

drv.close()
