#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 30 11:46:08 2025

@author: Francesco Ceccarelli

Test script for basic functionality of the TBS2204B driver.

This file performs a sequential check of:
- General communication and status
- Channel control
- Timebase configuration
- Trigger settings
- Waveform acquisition

It is intended for manual testing and verification of driver methods.
"""

from core import TBS2204B
import matplotlib.pyplot as plt

scope = TBS2204B('USB::0x0699::0x03C7::C010302::INSTR', verbose=True)

# ------------------------------------------------------------------
# General communication and status
# ------------------------------------------------------------------
scope.idn()
scope.clear()
scope.reset()
scope.autoset()

# ------------------------------------------------------------------
# Channel control
# ------------------------------------------------------------------
scope.set_channel_display(2, True)
scope.get_channel_display(2)
scope.set_channel_coupling(2, "DC")
scope.get_channel_coupling(2)
scope.set_channel_position(2, 0)
scope.get_channel_position(2)
scope.set_channel_gain(2, 1)
scope.get_channel_gain(2)
scope.set_channel_bandwidth(2, 20E6)
scope.get_channel_bandwidth(2)
scope.set_channel_scale(2, 1)
scope.get_channel_scale(2)

# ------------------------------------------------------------------
# Timebase configuration
# ------------------------------------------------------------------
scope.set_timebase_position(7.5)
scope.get_timebase_position()
scope.set_timebase_scale(0.001)
scope.get_timebase_scale()    

# ------------------------------------------------------------------
# Trigger settings
# ------------------------------------------------------------------
scope.set_trigger_mode("AUTO")
scope.get_trigger_mode()
scope.set_trigger_slope("FALL")
scope.get_trigger_slope()
scope.set_trigger_source(2)
scope.get_trigger_source()
scope.set_trigger_level(1.5)
scope.get_trigger_level()

# ------------------------------------------------------------------
# Waveform acquisition
# ------------------------------------------------------------------
scope.set_record_length(2e3)
scope.get_record_length()
scope.get_acquisition_state()
scope.stop_acquisition()
scope.get_acquisition_state()
scope.start_acquisition()
scope.get_acquisition_state()
scope.single_acquisition()
scope.get_acquisition_state()
t, v = scope.get_waveform(2)
plt.plot(t, v)
plt.show()

scope.close()
