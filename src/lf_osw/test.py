#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 30 23:18:38 2025

@author: Francesco Ceccarelli

Test script for basic functionality of the Lfiber OSW.

This file performs a sequential check of:
- General communication and status
- Channel control

It is intended for manual testing and verification of driver methods.
"""

from core import LF_OSW

osw = LF_OSW('ASRL3::INSTR', switching_delay=0.1, verbose=True)

# ------------------------------------------------------------------
# General communication and status
# ------------------------------------------------------------------
osw.idn()
osw.reset()

# ------------------------------------------------------------------
# Channel control
# ------------------------------------------------------------------
osw.get_channel()
osw.set_channel(5)
osw.get_channel()

osw.close()
