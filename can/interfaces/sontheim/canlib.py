"""
Ctypes wrapper module for the SIE / IFM CANfox interface

Copyright (C) 2022 Matt Woodhead
"""

from ctypes import c_int, c_long, c_ulonglong, byref
import logging
import time
import platform
import sys

from ...message import Message
from ...bus import BusABC, BusState
# from ...util import len2dlc, dlc2len
from ...exceptions import CanError, CanOperationError, CanInitializationError
from ...ctypesutil import CLibrary, HANDLE

from . import constants as const
from . import structures as struct
from . import devices

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
        # Use polling instead
        HAS_EVENTS = False


log = logging.getLogger("can.sontheim")  # Set up logging

_canlib = None
if (sys.platform == "win32" or sys.platform == "cygwin"):
    try:
        try:  # Check that python-can is being run on a 32 bit python interpreter
            assert not const.IS_PYTHON_64BIT
        except AssertionError as AE:
            raise AssertionError(
                "The Sontheim API is currently only compatible with the 32 bit python interpreter",
            ) from AE
            # The SIE MT_API DLL is 32 bit only, so cannot be run from a 64 bit process
            # TODO: develop a 64 bit wrapper for the 32 bit API similar to msl-loadlib.
        _canlib = CLibrary("C:\\Program Files (x86)\\Sontheim\\MT_Api\\SIECA132.dll")
    except Exception as e:
        log.warning("Cannot load SIE MT_API for Sontheim: %s", e)
        print("Cannot load SIE MT_API for Sontheim: %s", e)
else:
    # Will not work on other systems, but have it importable anyway for
    # tests/sphinx
    log.warning("Cannot load SIE MT_API for Sontheim does not work on %s platform, %s",
        sys.platform,
        platform.python_compiler(),
    )


def canGetSystemTime() -> int:
    """

    :raises SontheimCanOperationError:
        Raised if the Sontheim MT_API reports an error when querying the HW timestamp
    :return:
        The current system time in tenths of a millisecond (i.e divide by 10000 to get seconds)
    :rtype: int

    """

    pui64StartSysTime = c_ulonglong()
    pui64CurrSysTime = c_ulonglong()

    error_code = _canlib.canGetSystemTime(byref(pui64CurrSysTime), byref(pui64StartSysTime))

    if error_code == const.NTCAN_SUCCESS:
        return pui64CurrSysTime.value
    else:
        raise SontheimCanOperationError("Error encountered in canGetSystemTime function call")


class SontheimBus(BusABC):
    def __init__(
        self,
        channel=devices.CanFox.CAN1,
        state=BusState.ACTIVE,
        bitrate=500000,
        *args,
        **kwargs,
    ):

        self.channel = channel
        self.channel_info = str(channel)
        self.fd = False
        self._canfox_bitrate = const.CANFOX_BITRATES.get(
            int(bitrate),
            const.CANFOX_BITRATES[500000],  # default to 500 kbit/s
        )
        self._Handle = HANDLE()
        self._bus_pc_start_time_s = None
        self._bus_hw_start_timestamp = None

        if state is BusState.ACTIVE or state is BusState.PASSIVE:
            self.state = state
        else:
            raise ValueError("BusState must be Active or Passive")


        if HAS_EVENTS:
            self._receive_event = CreateEvent(None, 0, 0, "R1")
            self._error_event = CreateEvent(None, 0, 0, "E1")

        super().__init__(channel=channel, state=state, bitrate=bitrate, *args, **kwargs)

        self._can_init()


    def _can_init(self, errors=True, echo=False, tx_timeout=-1, rx_timeout=-1):

        # TODO: Check DLL status for DLL version - if it shows a value of zero, you need to unplug the adapter and plug it back in again to reset the driver

        error_code = _canlib.canOpen(
            c_long(self.channel),
            c_long(errors),
            c_long(echo),
            c_long(tx_timeout),
            c_long(rx_timeout),
            "python-can",
            "R1",
            "E1",
            byref(self._Handle),
        )
        # TODO: implement errors as exceptions
        print(error_code)

        error_code = _canlib.canSetBaudrate(self._Handle, c_int(self._canfox_bitrate))
        print(error_code)
        error_code = _canlib.canSetFilterMode(self._Handle, c_int(4))
        print(error_code)

        self._bus_pc_start_time_s = round(time.time(), 4)
        self._bus_hw_start_timestamp = canGetSystemTime()/10000


    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        # declare here, which is called by __init__()
        self._state = new_state  # pylint: disable=attribute-defined-outside-init

        if new_state is BusState.ACTIVE:
            pass  # TODO: change HW mode
            # self.m_objPCANBasic.SetValue(
            #     self.m_PcanHandle, PCAN_LISTEN_ONLY, PCAN_PARAMETER_OFF
            # )

        elif new_state is BusState.PASSIVE:
            pass  # TODO: change HW mode
            # When this mode is set, the CAN controller does not take part on active events
            # (eg. transmit CAN messages) but stays in a passive mode (CAN monitor),
            # in which it can analyse the traffic on the CAN bus used by a
            # PCAN channel. See also the Philips Data Sheet "SJA1000 Stand-alone CAN controller".
            # self.m_objPCANBasic.SetValue(
            #     self.m_PcanHandle, PCAN_LISTEN_ONLY, PCAN_PARAMETER_ON
            # )

    def shutdown(self):
        super().shutdown()
        _canlib.canClose(self._Handle)

    def _recv_internal(self, timeout):

        if HAS_EVENTS:
            # We will utilize events for the timeout handling
            timeout_ms = int(timeout * 1000) if timeout is not None else INFINITE
        elif timeout is not None:
            # Calculate max time
            end_time = time.perf_counter() + timeout

        # logger.debug("Trying to read a msg")

        msg_struct = struct.CANMsgStruct()
        error_code = None
        while error_code is None:
            error_code = _canlib.canReadNoWait(self._Handle, byref(msg_struct), byref(c_int(1)))
            if error_code == const.NTCAN_RX_TIMEOUT:
                if HAS_EVENTS:
                    error_code = None
                    val = WaitForSingleObject(self._receive_event, timeout_ms)
                    if val != WAIT_OBJECT_0:
                        return None, False
                elif timeout is not None and time.perf_counter() >= end_time:
                    return None, False
                else:
                    error_code = None
                    time.sleep(0.001)
            elif error_code != const.NTCAN_SUCCESS:
                raise SontheimCanOperationError(
                    "Error encountered whilst trying to read bus, [Error Code: %s]" % error_code,
                    )

        # logger.debug("Received a message")

        # remove bits 4 to 7 as these are reserved for other functionality
        dlc = int(msg_struct.by_len & 0x0f)

        # Use the starting timestamp
        timestamp = (
            self._bus_pc_start_time_s
            + (int(msg_struct.ul_tstamp) / 10000)
            - self._bus_hw_start_timestamp
        )

        frame_info = msg_struct.by_extended

        rx_msg = Message(
            timestamp=timestamp,
            arbitration_id=hex(msg_struct.l_id),
            is_extended_id=frame_info & 2,
            is_remote_frame=msg_struct.by_remote & 1,
            is_error_frame=frame_info & 64,
            dlc=dlc,
            data=msg_struct.aby_data,
            is_fd=False,
            # bitrate_switch=bitrate_switch,
            # error_state_indicator=error_state_indicator,
        )

        return rx_msg, False

    def send(self, msg, timeout=None):
        pass

    def canBlinkLED(self, blink_length_s=2):
        """

        :param blink_length_s: The length in seconds for how long the blinking is desired.
        :type blink_length_s: int

        """

        for i in range(int(blink_length_s/0.25) + 1):
            _canlib.canBlinkLED(self._Handle, 1, i % 2, 5)
            time.sleep(0.25)

        _canlib.canBlinkLED(self._Handle, 0, i % 2, 5)

    @staticmethod
    def _detect_available_configs():

        devices_struct = struct.CANInstalledDevicesStruct()
        error_code = _canlib.canGetDeviceList(byref(devices_struct))
        if error_code == const.NTCAN_SUCCESS:
            _devices = struct.read_struct_as_dict(devices_struct)
            if _devices:
                return [{"interface": "sontheim", "channel": _devices["Net"]}]
        return []



class SontheimError(CanError):
    """A generic error on a CANFox bus."""


class SontheimCanOperationError(CanOperationError, SontheimError):
    """Like :class:`can.exceptions.CanOperationError`, but specific to the CANFox MT_API."""


class SontheimCanInitializationError(CanInitializationError, SontheimError):
    """Like :class:`can.exceptions.CanInitializationError`, but specific to CANFox MT_API."""
