import unittest
from unittest import mock

from ovb_rc003 import chromecast_client


class ChromecastClientTelemetryTests(unittest.TestCase):
    def test_repetitive_telemetry_is_debug_only_when_diagnostics_are_off(self):
        client = chromecast_client.Client(
            "a" * 64, mode="run", on_edge=lambda _: None,
            telemetry_enabled=lambda: False,
        )
        logger = mock.Mock()
        client._log_telemetry(logger, "routine telemetry")
        logger.debug.assert_called_once_with("routine telemetry")
        logger.info.assert_not_called()

    def test_full_telemetry_remains_available_when_diagnostics_are_on(self):
        client = chromecast_client.Client(
            "a" * 64, mode="run", on_edge=lambda _: None,
            telemetry_enabled=lambda: True,
        )
        logger = mock.Mock()
        client._log_telemetry(logger, "diagnostic telemetry")
        logger.info.assert_called_once_with("diagnostic telemetry")
        logger.debug.assert_not_called()


if __name__ == "__main__":
    unittest.main()
