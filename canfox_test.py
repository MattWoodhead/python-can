# -*- coding: utf-8 -*-
"""
Created on Sat Jul  2 20:36:51 2022

@author: matth
"""

import can
from can import Message
from can.interfaces.sontheim import devices
import time


with can.Bus(interface="sontheim", channel=devices.CanFox.CAN1, bitrate=250000, echo=True) as bus:
#with can.Bus(interface="serial", channel="com12", bitrate=250000) as bus:

    msg = Message(arbitration_id=0xC0FFEF, is_extended_id=True, data=[0xDE, 0xAD, 0xBE, 0xEF, 0xDE, 0xAD, 0xBE, 0xEF])

    start_time = time.time()

    task = bus.send_periodic(msg, 0.20)

    done = False
    while not done:
        if time.time() > start_time + 10:
            task.stop()
            done = True
            print("Done")
