import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import speed_test
from speed_test import Measurement, summarize


class MeasurementTest(unittest.TestCase):
    def test_speed_is_size_over_time(self):
        measurement = Measurement(size_bytes=2 * speed_test.MIB, elapsed_s=2.0)
        self.assertAlmostEqual(measurement.speed_mib_s, 1.0)

    def test_zero_time_gives_zero_speed(self):
        measurement = Measurement(size_bytes=1024, elapsed_s=0.0)
        self.assertEqual(measurement.speed_mib_s, 0.0)


class SummarizeTest(unittest.TestCase):
    def test_totals_and_aggregate_speed(self):
        measurements = [
            Measurement(size_bytes=1 * speed_test.MIB, elapsed_s=1.0),
            Measurement(size_bytes=3 * speed_test.MIB, elapsed_s=3.0),
        ]
        text = summarize(measurements)
        self.assertIn("Requests:        2", text)
        self.assertIn("Total size:      4.00 MiB (4194304 bytes)", text)
        self.assertIn("Total time:      4.000 s", text)
        self.assertIn("Average request: 2.000 s", text)
        self.assertIn("Download speed:  1.00 MiB/s (8.39 Mbit/s)", text)

    def test_empty_list_does_not_crash(self):
        text = summarize([])
        self.assertIn("Requests:        0", text)


class RunTest(unittest.TestCase):
    def test_requests_are_sequential_and_fully_read(self):
        closed: list[int] = []
        opened: list[int] = []

        def fake_urlopen(request, timeout):
            self.assertEqual(len(closed), len(opened))
            opened.append(len(opened))
            response = io.BytesIO(b"x" * (speed_test.CHUNK_SIZE + 1))
            original_close = response.close

            def close():
                closed.append(len(closed))
                original_close()

            response.close = close
            return response

        with mock.patch.object(
            speed_test.urllib.request, "urlopen", side_effect=fake_urlopen
        ) as urlopen, redirect_stdout(io.StringIO()):
            measurements = speed_test.run("http://example.test/file", 2, 5.0)

        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(
            [item.size_bytes for item in measurements],
            [speed_test.CHUNK_SIZE + 1] * 2,
        )
        self.assertEqual(len(closed), 2)


class ParseArgsTest(unittest.TestCase):
    def test_rejects_non_positive_requests(self):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                speed_test.parse_args(["http://example.test", "-n", "0"])


if __name__ == "__main__":
    unittest.main()
