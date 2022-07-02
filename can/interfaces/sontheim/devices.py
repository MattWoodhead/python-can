"""
Device definitions module for the SIE / IFM CANfox interface

Copyright (C) 2022 Matt Woodhead
"""

from collections import namedtuple

single_channel = namedtuple("dual_channel", ["CAN1"])
dual_channel = namedtuple("dual_channel", ["CAN1", "CAN2"])


PowerPCI = dual_channel(0, 1)
PowerPCIV2 = dual_channel(0, 1)
PC104Plus = dual_channel(0, 1)
CANAS = dual_channel(0, 1)
CANUSB = dual_channel(21, 22)
CANUSB_Legacy = dual_channel(24, 25)
MobiCAN = dual_channel(90, 91)
CanFox =  single_channel(105)
Virtual_Device_1 = dual_channel(27, 28)
Virtual_Device_2 = dual_channel(30, 31)
Virtual_Device_3 = dual_channel(33, 34)
Virtual_Device_4 = dual_channel(36, 37)
Virtual_Device_5 = dual_channel(39, 40)


_net_number_lookup =
