"""
Ctypes wrapper module for IXXAT Virtual CAN Interface V4 on win32 systems

Copyright (C) 2016-2021 Giuseppe Corbelli <giuseppe.corbelli@weightpack.com>
"""

__all__ = [
    "IXXATBus",
    "canlib",
    "canlib_vcinpl",
    "canlib_vcinpl2",
    "constants",
    "exceptions",
    "get_ixxat_hwids",
    "structures",
]

from can.interfaces.ixxat.canlib import IXXATBus, get_ixxat_hwids
