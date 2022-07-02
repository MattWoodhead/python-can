# -*- coding: utf-8 -*-
"""
Created on Sat Jun 25 17:41:14 2022

@author: matth
"""

import ctypes
from ctypes import c_char, c_int, c_uint, c_short, c_ushort, c_long, c_longlong, c_ulong, c_ulonglong, c_byte, c_ubyte, c_void_p, c_bool, byref, Structure
import platform
import sys
import time

from can.ctypesutil import CLibrary, HANDLE, PHANDLE, HRESULT as ctypes_HRESULT

try:
    # Try builtin Python 3 Windows API
    from _overlapped import CreateEvent
    from _winapi import WaitForSingleObject, WAIT_OBJECT_0, INFINITE
    HAS_EVENTS = True
except ImportError:
    try:
        # Try pywin32 package
        from win32event import CreateEvent
        from win32event import WaitForSingleObject, WAIT_OBJECT_0, INFINITE
        HAS_EVENTS = True
    except ImportError:
        HAS_EVENTS = False  # Use polling instead


IS_PYTHON_64BIT = sys.maxsize > 2 ** 32


_canlib = None
if (sys.platform == "win32" or sys.platform == "cygwin") and not IS_PYTHON_64BIT:
    try:
        _canlib = CLibrary("C:\\Program Files (x86)\\Sontheim\\MT_Api\\SIECA132.dll")
    except Exception as e:
        #log.warning("Cannot load IXXAT vcinpl library: %s", e)
        print("Cannot load SIE MT_API for CANFox: %s", e)
else:
    # Will not work on other systems, but have it importable anyway for
    # tests/sphinx
    #log.warning("IXXAT VCI library does not work on %s platform", sys.platform)
    print("Cannot load SIE MT_API for CANFox does not work on %s platform, %s", sys.platform, platform.python_compiler())



MAX_NUM_APIHANDLE = 4


def dummy_def():
    pass


def getdict(struct):
    result = {}
    #print struct
    def get_value(value):
         if (type(value) not in [int, float, bool]) and not bool(value):
             # it's a null pointer
             value = None
         elif hasattr(value, "_length_") and hasattr(value, "_type_"):
             # Probably an array
             #print value
             value = get_array(value)
         elif hasattr(value, "_fields_"):
             # Probably another struct
             value = getdict(value)
         return value
    def get_array(array):
        ar = []
        for value in array:
            value = get_value(value)
            ar.append(value)
        return ar
    for f  in struct._fields_:
         field = f[0]
         value = getattr(struct, field)
         # if the type is not a primitive and it evaluates to False ...
         value = get_value(value)
         result[field] = value
    return result


class CANMsgStruct(Structure):
    _fields_ = [
        ("l_id", c_long),
        ("by_len", c_char),
        ("by_msg_lost", c_char),
        ("by_extended", c_char),
        ("by_remote", c_char),
        ("aby_data", c_char * 8),
        ("ul_tstamp", c_ulong),
    ]  # CMSG


class CANStatusStruct(Structure):
    _fields_ = [
        ("w_hw_rev", c_ushort),
        ("w_fw_rev", c_ushort),
        ("w_drv_rev", c_ushort),
        ("w_dll_rev", c_ushort),
        ("ul_board_status", c_ulong),
        ("by_board_id", c_char),
        ("w_busoffctr", c_ushort),
        ("w_errorflag", c_ushort),
        ("w_errorframectr", c_ushort),
        ("w_netctr", c_ushort),
        ("w_baud", c_ushort),
        ("ui_epld_rev", c_uint),
    ]  # CAN_IF_STATUS


class CANInstalledDevicesStruct(Structure):
    _fields_ = [
        ("Net", c_int),
        ("Name", c_char * 20),
        ("ul_Status", c_ulong),
        ("ul_Features", c_ulong),
        ("Reserved", c_long * 18),
    ]  # T_DeviceList


def canOpen(errors=True, echo=False, tx_timeout=-1, rx_timeout=-1):

    l_netnumber = c_int(105)
    l_mode = c_int(errors)
    l_echoon = c_int(echo)
    l_txtimeout = tx_timeout
    l_rxtimeout = rx_timeout

    handle = c_void_p()  # todo - this will be a class value
    print("Opening connection")
    error_code = _canlib.canOpen(l_netnumber, l_mode, l_echoon, l_txtimeout, l_rxtimeout, "python-can", "R1", "E1", byref(handle))
    # todo - implement errors as exceptions

    return handle


def canClose(handle):
    print("Closing connection")
    error_code = _canlib.canClose(handle)
    print(error_code)
    # todo - implement errors as exceptions


def canSetBaudrate(handle, baudrate=250000):

    assert baudrate == 250000  # todo - add in other baud rates
    print("Setting baud")
    error_code = _canlib.canSetBaudrate(handle, c_int(3))
    print(error_code)
    # todo - implement errors as exceptions


def canEnableAllIds(handle, enable_all_ids=True):
    print("Enabling all CAN IDs")
    error_code = _canlib.canEnableAllIds(handle, c_bool(enable_all_ids))
    print(error_code)
    # todo - implement errors as exceptions


def canSetFilterMode(handle, filter_mode=4):
    print("Enabling all CAN IDs")
    error_code = _canlib.canSetFilterMode(handle, c_int(filter_mode))
    print(error_code)
    # todo - implement errors as exceptions


def canRead(handle):

    msg_array = CANMsgStruct()
    print("Reading messages")
    error_code = _canlib.canRead(handle, byref(msg_array), byref(c_int(1)))
    print(error_code)
    # todo - implement errors as exceptions

    return msg_array


def canStatus(handle):

    status_struct = CANStatusStruct()
    print("Reading Canfox status")
    error_code = _canlib.canStatus(handle, byref(status_struct))
    print(error_code)
    # todo - implement errors as exceptions

    return status_struct


def canGetNumberOfConnectedDevices():

    a = c_int(0)
    error_code = _canlib.canGetNumberOfConnectedDevices(byref(a))
    # todo - implement errors as exceptions

    return a.value  # .value to convert from a ctype back to a standard python int

def canGetDeviceList():

    devices_struct = CANInstalledDevicesStruct()

    error_code = _canlib.canGetDeviceList(byref(devices_struct))

    return devices_struct


def canBlinkLED(handle, blink_length_s):
    """
    A blocking function used to flash the LED on the canfox adapter. This is useful
    for identification if you have multiple adapters connected to the computer.

    Parameters
    ----------
    blink_length_s : The length in seconds for how long the blinking is desired.

    Returns
    -------
    None.

    """

    for i in range(9):
        _canlib.canBlinkLED(handle, 1, i % 2, 5)
        time.sleep(0.25)

    _canlib.canBlinkLED(handle, 0, i % 2, 5)


def canGetSystemTime():

    pui64StartSysTime = c_ulonglong()
    pui64CurrSysTime = c_ulonglong()

    error_code = _canlib.canGetSystemTime(byref(pui64CurrSysTime), byref(pui64StartSysTime))

    return pui64StartSysTime, pui64CurrSysTime



def canReadNoWait(handle):

    msg_array = CANMsgStruct()
    print("Reading messages")
    error_code = _canlib.canReadNoWait(handle, byref(msg_array), byref(c_int(1)))
    print(error_code)
    # todo - implement errors as exceptions

    return msg_array



b = canGetNumberOfConnectedDevices()

if b > 0:
    l = canGetDeviceList()
    print(l.Net)
    print(l.Name)
    # h = canOpen()
    # time.sleep(0.01)
    # canSetBaudrate(h)
    # time.sleep(0.01)
    # canSetFilterMode(h)
    # time.sleep(0.01)
    # msgs = canReadNoWait(h)
    # print(getdict(msgs))
    # print(hex(msgs.l_id))
    # print(list(hex(i) for i in msgs.aby_data))
    # print(msgs.ul_tstamp/10)
    # status = canStatus(h)
    # print(getdict(status))
    # # time.sleep(0.01)
    # # a, b = canGetSystemTime()
    # # print(a)
    # # print(b)
    # canClose(h)

time.sleep(1)
