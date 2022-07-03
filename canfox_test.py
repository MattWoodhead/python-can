# -*- coding: utf-8 -*-
"""
Created on Sat Jul  2 20:36:51 2022

@author: matth
"""

import can
from can import Message
from can.interfaces.sontheim import devices
from threading import Timer
from time import ctime

import cProfile

DONE = False

prof = cProfile.Profile()


with can.Bus(interface="sontheim", channel=devices.CanFox.CAN1, bitrate=250000, echo=False) as bus:

    prof.enable()

    def timeout():
        global DONE
        DONE = True

    msg = Message(
        arbitration_id=0xC0FFEF,
        is_extended_id=True,
        data=[0xDE, 0xAD, 0xBE, 0xEF, 0xDE, 0xAD, 0xBE, 0xEF],
    )

    task = bus.send_periodic(msg, 1)
    t = Timer(10, timeout)
    t.start()
    print(f"timer started: {ctime()}")

    while not DONE:
        pass
    else:
        task.stop()
        print(f"Done: {ctime()}")

    prof.disable()

prof.dump_stats("profile1.result")
