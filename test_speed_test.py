import io
import threading
import unittest
from contextlib import redirect_stdout
from unittest import mock

import speed_test
from speed_test import Measurement, summarize


class MeasurementTest(unittest.TestCase):
    def test_speed_is_size_over_time(self):
        measurement = Measurement(size_bytes=2 * speed_test.MEGABYTE, elapsed_s=2.0)
        self.assertAlmostEqual(measurement.speed_mb_s, 1.0)

    def test_zero_time_gives_zero_speed(self):
        measurement = Measurement(size_bytes=1024, elapsed_s=0.0)
        self.assertEqual(measurement.speed_mb_s, 0.0)


class SummarizeTest(unittest.TestCase):
    def test_totals_and_aggregate_speed(self):
        measurements = [
            Measurement(size_bytes=1 * speed_test.MEGABYTE, elapsed_s=1.0),
            Measurement(size_bytes=3 * speed_test.MEGABYTE, elapsed_s=3.0),
        ]
        text = summarize(measurements)
        self.assertIn("Requests:        2", text)
        self.assertIn("Total size:      4.00 MB (4000000 bytes)", text)
        self.assertIn("Total time:      4.000 s", text)
        self.assertIn("Average request: 2.000 s", text)
        self.assertIn("Download speed:  1.00 MB/s", text)

    def test_empty_list_does_not_crash(self):
        text = summarize([])
        self.assertIn("Requests:        0", text)

    def test_explicit_wall_time_drives_speed(self):
        measurements = [
            Measurement(size_bytes=1 * speed_test.MEGABYTE, elapsed_s=1.0),
            Measurement(size_bytes=1 * speed_test.MEGABYTE, elapsed_s=1.0),
        ]
        text = summarize(measurements, total_time=1.0)
        self.assertIn("Total time:      1.000 s", text)
        self.assertIn("Average request: 1.000 s", text)
        self.assertIn("Download speed:  2.00 MB/s", text)


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

    def test_streams_run_requests_concurrently(self):
        barrier = threading.Barrier(2, timeout=5)

        def fake_urlopen(request, timeout):
            barrier.wait()
            return io.BytesIO(b"x" * 10)

        with mock.patch.object(
            speed_test.urllib.request, "urlopen", side_effect=fake_urlopen
        ), redirect_stdout(io.StringIO()):
            measurements = speed_test.run(
                "http://example.test/file", 2, 5.0, streams=2
            )

        self.assertEqual([item.size_bytes for item in measurements], [10, 10])


class ParseArgsTest(unittest.TestCase):
    def test_rejects_non_positive_numbers(self):
        for option in ("-n", "-s"):
            with self.subTest(option=option):
                with redirect_stdout(io.StringIO()), mock.patch(
                    "sys.stderr", io.StringIO()
                ):
                    with self.assertRaises(SystemExit):
                        speed_test.parse_args(
                            ["http://example.test", option, "0"]
                        )


class InteractiveTest(unittest.TestCase):
    def run_main(self, answers, run_side_effect):
        self.answers = iter(answers)
        with mock.patch.object(speed_test, "run", side_effect=run_side_effect), \
                mock.patch(
                    "builtins.input",
                    side_effect=lambda prompt="": next(self.answers),
                ), \
                redirect_stdout(io.StringIO()), \
                mock.patch("sys.stderr", io.StringIO()):
            return speed_test.main([])

    def test_repeat_and_another_url_then_exit(self):
        urls = []

        def fake_run(url, count, timeout, streams=1):
            urls.append(url)
            return [Measurement(speed_test.MEGABYTE, 1.0)]

        code = self.run_main(
            ["http://a", "1", "2", "http://b", "3"],
            fake_run,
        )

        self.assertEqual(code, 0)
        self.assertEqual(urls, ["http://a", "http://a", "http://b"])

    def test_invalid_choice_is_retried(self):
        code = self.run_main(
            ["http://a", "9", "3"],
            lambda url, count, timeout, streams=1: [
                Measurement(speed_test.MEGABYTE, 1.0)
            ],
        )
        self.assertEqual(code, 0)

    def test_failed_request_returns_to_menu(self):
        code = self.run_main(
            ["http://a", "3"],
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        self.assertEqual(code, 0)

    def test_eof_at_url_prompt_exits_cleanly(self):
        with mock.patch("builtins.input", side_effect=EOFError), \
                redirect_stdout(io.StringIO()):
            code = speed_test.main([])
        self.assertEqual(code, 0)

    def test_cli_failure_returns_exit_code(self):
        with mock.patch.object(
            speed_test, "run", side_effect=RuntimeError("boom")
        ), redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            code = speed_test.main(["http://a", "-n", "1"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
