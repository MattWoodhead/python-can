"""
Test for Sontheim API Interface
"""

import ctypes
import unittest
from unittest import mock
from unittest.mock import Mock

import pytest
from parameterized import parameterized

import can
from can.bus import BusState
from can.exceptions import CanOperationError, CanInitializationError, CanTimeoutError
import can.interfaces.sontheim.constants as const
from can.interfaces.sontheim import SontheimBus


class TestPCANBus(unittest.TestCase):
    def setUp(self) -> None:

        patcher = mock.patch("can.interfaces.pcan.pcan.PCANBasic", spec=True)
        self.MockPCANBasic = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_sontheim = self.MockPCANBasic.return_value
        self.mock_sontheim.Initialize.return_value = const.NTCAN_SUCCESS
        self.mock_sontheim.SetValue = Mock(return_value=const.NTCAN_SUCCESS)
        self.mock_sontheim.GetValue = self._mockGetValue
        self.PCAN_API_VERSION_SIM = "4.2"

        self.bus = None

    def tearDown(self) -> None:
        if self.bus:
            self.bus.shutdown()
            self.bus = None

    # def _mockGetValue(self, channel, parameter):
    #     """
    #     This method is used as mock for GetValue method of PCANBasic object.
    #     Only a subset of parameters are supported.
    #     """
    #     if parameter == PCAN_API_VERSION:
    #         return const.NTCAN_SUCCESS, self.PCAN_API_VERSION_SIM.encode("ascii")
    #     raise NotImplementedError(
    #         f"No mock return value specified for parameter {parameter}"
    #     )

    def test_bus_creation(self) -> None:
        self.bus = can.Bus(bustype="sontheim")
        self.assertIsInstance(self.bus, SontheimBus)
        self.MockPCANBasic.assert_called_once()
        self.mock_pcan.Initialize.assert_called_once()
        self.mock_pcan.InitializeFD.assert_not_called()

    def test_bus_creation_state_error(self) -> None:
        with self.assertRaises(ValueError):
            can.Bus(bustype="sontheim", state=BusState.ERROR)

    def test_bus_creation_fd(self) -> None:
        self.bus = can.Bus(bustype="sontheim", fd=True)  # Todo - check this raises an exception (FD is not available on sontheim interfaces)
        self.assertIsInstance(self.bus, SontheimBus)
        self.MockPCANBasic.assert_called_once()
        self.mock_pcan.Initialize.assert_not_called()
        self.mock_pcan.InitializeFD.assert_called_once()

    def test_api_version_low(self) -> None:
        self.PCAN_API_VERSION_SIM = "1.0"
        with self.assertLogs("can.sontheim", level="WARNING") as cm:
            self.bus = can.Bus(bustype="pcan")
            found_version_warning = False
            for i in cm.output:
                if "version" in i and "pcan" in i:
                    found_version_warning = True
            self.assertTrue(
                found_version_warning,
                f"No warning was logged for incompatible api version {cm.output}",
            )

    # def test_api_version_read_fail(self) -> None:
    #     self.mock_pcan.GetValue = Mock(return_value=(PCAN_ERROR_ILLOPERATION, None))
    #     with self.assertRaises(CanInitializationError):
    #         self.bus = can.Bus(bustype="pcan")

    def test_status(self) -> None:
        self.bus = can.Bus(bustype="sontheim")
        self.bus.status()
        # self.mock_pcan.GetStatus.assert_called_once_with(PCAN_USBBUS1)

    @parameterized.expand(
        [("no_error", PCAN_ERROR_OK, 1), ("error", PCAN_ERROR_UNKNOWN, None)]
    )
    def test_get_device_number(self, name, status, expected_result) -> None:
        with self.subTest(name):
            self.bus = can.Bus(bustype="sontheim")
            # Mock GetValue after creation of bus to use first mock of
            # GetValue in constructor
            self.mock_pcan.GetValue = Mock(return_value=(status, 1))

            self.assertEqual(self.bus.get_device_number(), expected_result)
            self.mock_pcan.GetValue.assert_called_once_with(
                PCAN_USBBUS1, PCAN_DEVICE_NUMBER
            )

    def test_recv(self):
        data = (ctypes.c_ubyte * 8)(*[x for x in range(8)])
        msg = TPCANMsg(ID=0xC0FFEF, LEN=8, MSGTYPE=PCAN_MESSAGE_EXTENDED, DATA=data)

        timestamp = TPCANTimestamp()
        self.mock_pcan.Read = Mock(return_value=(PCAN_ERROR_OK, msg, timestamp))
        self.bus = can.Bus(bustype="pcan")

        recv_msg = self.bus.recv()
        self.assertEqual(recv_msg.arbitration_id, msg.ID)
        self.assertEqual(recv_msg.dlc, msg.LEN)
        self.assertEqual(recv_msg.is_extended_id, True)
        self.assertEqual(recv_msg.is_fd, False)
        self.assertSequenceEqual(recv_msg.data, msg.DATA)
        self.assertEqual(recv_msg.timestamp, 0)

    @pytest.mark.timeout(3.0)
    def test_recv_no_message(self):
        self.mock_pcan.Read = Mock(return_value=(PCAN_ERROR_QRCVEMPTY, None, None))
        self.bus = can.Bus(bustype="pcan")
        self.assertEqual(self.bus.recv(timeout=0.5), None)

    def test_send(self) -> None:
        self.mock_pcan.Write = Mock(return_value=PCAN_ERROR_OK)
        self.bus = can.Bus(bustype="pcan")
        msg = can.Message(
            arbitration_id=0xC0FFEF, data=[1, 2, 3, 4, 5, 6, 7, 8], is_extended_id=True
        )
        self.bus.send(msg)
        self.mock_pcan.Write.assert_called_once()
        self.mock_pcan.WriteFD.assert_not_called()

    @parameterized.expand(
        [
            (
                "standart",
                (False, False, False, False, False, False),
                PCAN_MESSAGE_STANDARD,
            ),
            (
                "extended",
                (True, False, False, False, False, False),
                PCAN_MESSAGE_EXTENDED,
            ),
            ("remote", (False, True, False, False, False, False), PCAN_MESSAGE_RTR),
            ("error", (False, False, True, False, False, False), PCAN_MESSAGE_ERRFRAME),
            ("fd", (False, False, False, True, False, False), PCAN_MESSAGE_FD),
            (
                "bitrate_switch",
                (False, False, False, False, True, False),
                PCAN_MESSAGE_BRS,
            ),
            (
                "error_state_indicator",
                (False, False, False, False, False, True),
                PCAN_MESSAGE_ESI,
            ),
        ]
    )
    def test_send_type(self, name, msg_type, expected_value) -> None:
        with self.subTest(name):
            (
                is_extended_id,
                is_remote_frame,
                is_error_frame,
                is_fd,
                bitrate_switch,
                error_state_indicator,
            ) = msg_type

            self.mock_pcan.Write = Mock(return_value=PCAN_ERROR_OK)

            self.bus = can.Bus(bustype="pcan")
            msg = can.Message(
                arbitration_id=0xC0FFEF,
                data=[1, 2, 3, 4, 5, 6, 7, 8],
                is_extended_id=is_extended_id,
                is_remote_frame=is_remote_frame,
                is_error_frame=is_error_frame,
                bitrate_switch=bitrate_switch,
                error_state_indicator=error_state_indicator,
                is_fd=is_fd,
            )
            self.bus.send(msg)
            # self.mock_m_objPCANBasic.Write.assert_called_once()
            CANMsg = self.mock_pcan.Write.call_args_list[0][0][1]
            self.assertEqual(CANMsg.MSGTYPE, expected_value.value)

    def test_send_error(self) -> None:
        self.mock_pcan.Write = Mock(return_value=PCAN_ERROR_BUSHEAVY)
        self.bus = can.Bus(bustype="pcan")
        msg = can.Message(
            arbitration_id=0xC0FFEF, data=[1, 2, 3, 4, 5, 6, 7, 8], is_extended_id=True
        )

        with self.assertRaises(PcanError):
            self.bus.send(msg)

    @parameterized.expand([("on", True), ("off", False)])
    def test_flash(self, name, flash) -> None:
        with self.subTest(name):
            self.bus = can.Bus(bustype="pcan")
            self.bus.flash(flash)
            call_list = self.mock_pcan.SetValue.call_args_list
            last_call_args_list = call_list[-1][0]
            self.assertEqual(
                last_call_args_list, (PCAN_USBBUS1, PCAN_CHANNEL_IDENTIFYING, flash)
            )

    def test_shutdown(self) -> None:
        self.bus = can.Bus(bustype="pcan")
        self.bus.shutdown()
        self.mock_pcan.Uninitialize.assert_called_once_with(PCAN_USBBUS1)

    @parameterized.expand(
        [
            ("active", BusState.ACTIVE, PCAN_PARAMETER_OFF),
            ("passive", BusState.PASSIVE, PCAN_PARAMETER_ON),
        ]
    )
    def test_state(self, name, bus_state: BusState, expected_parameter) -> None:
        with self.subTest(name):
            self.bus = can.Bus(bustype="pcan")

            self.bus.state = bus_state
            call_list = self.mock_pcan.SetValue.call_args_list
            last_call_args_list = call_list[-1][0]
            self.assertEqual(
                last_call_args_list,
                (PCAN_USBBUS1, PCAN_LISTEN_ONLY, expected_parameter),
            )

    def test_detect_available_configs(self) -> None:
        self.mock_pcan.GetValue = Mock(
            return_value=(PCAN_ERROR_OK, PCAN_CHANNEL_AVAILABLE)
        )
        configs = SontheimBus._detect_available_configs()
        self.assertEqual(len(configs), 50)


if __name__ == "__main__":
    unittest.main()
