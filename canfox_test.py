# -*- coding: utf-8 -*-
"""
Created on Sat Jul  2 20:36:51 2022

@author: matth
"""

import can
from can.interfaces.sontheim import devices

with can.Bus(interface="sontheim", channel=devices.CanFox.CAN1, bitrate=250000) as bus:
#with can.Bus(interface="serial", channel="com12", bitrate=250000) as bus:

    bus._detect_available_configs()

    for msg in bus:
        print(msg.data)
