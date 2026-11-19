"""Measure download speed by fetching the same URL sequentially."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_REQUESTS = 10
DEFAULT_TIMEOUT = 30.0
CHUNK_SIZE = 64 * 1024
MEGABYTE = 1_000_000


@dataclass(frozen=True)
class Measurement:
    size_bytes: int
    elapsed_s: float

    @property
    def speed_mb_s(self) -> float:
        if self.elapsed_s <= 0:
            return 0.0
        return self.size_bytes / MEGABYTE / self.elapsed_s


def fetch(url: str, timeout: float) -> Measurement:
    request = urllib.request.Request(url, headers={"User-Agent": "speed-test/1.0"})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        size = 0
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
    elapsed = time.perf_counter() - start
    return Measurement(size, elapsed)


def run(url: str, count: int, timeout: float) -> list[Measurement]:
    measurements: list[Measurement] = []
    for index in range(1, count + 1):
        try:
            measurement = fetch(url, timeout)
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"request {index}/{count} failed: {exc}") from exc
        measurements.append(measurement)
        print(
            f"{index:2d}/{count}  "
            f"{measurement.size_bytes / MEGABYTE:8.2f} MB  "
            f"{measurement.elapsed_s:7.3f} s  "
            f"{measurement.speed_mb_s:7.2f} MB/s"
        )
    return measurements


def summarize(measurements: list[Measurement]) -> str:
    total_bytes = sum(item.size_bytes for item in measurements)
    total_time = sum(item.elapsed_s for item in measurements)
    count = len(measurements)
    average_time = total_time / count if count else 0.0
    speed_bytes_s = total_bytes / total_time if total_time else 0.0
    return "\n".join(
        [
            f"Requests:        {count}",
            f"Total size:      {total_bytes / MEGABYTE:.2f} MB ({total_bytes} bytes)",
            f"Total time:      {total_time:.3f} s",
            f"Average request: {average_time:.3f} s",
            f"Download speed:  {speed_bytes_s / MEGABYTE:.2f} MB/s",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the same URL several times and report the speed.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL to download, e.g. a large image; omit it to start interactive mode",
    )
    parser.add_argument(
        "-n",
        "--requests",
        type=int,
        default=DEFAULT_REQUESTS,
        help=f"number of sequential requests (default: {DEFAULT_REQUESTS})",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"timeout per request in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    args = parser.parse_args(argv)
    if args.requests < 1:
        parser.error("--requests must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def execute(url: str, count: int, timeout: float) -> bool:
    print(f"URL:      {url}")
    print(f"Requests: {count}, timeout: {timeout:g} s")
    print()
    try:
        measurements = run(url, count, timeout)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return False
    print()
    print(summarize(measurements))
    return True


def read_url() -> str | None:
    try:
        url = input("URL (empty to exit): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return url or None


def ask_choice() -> str:
    print()
    print("1) repeat  2) another URL  3) exit")
    while True:
        try:
            answer = input("Choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return "3"
        if not answer:
            return "1"
        if answer in {"1", "2", "3"}:
            return answer
        print("Enter 1, 2 or 3.")


def interactive(count: int, timeout: float) -> int:
    url = read_url()
    while url:
        execute(url, count, timeout)
        choice = ask_choice()
        if choice == "1":
            continue
        if choice == "2":
            url = read_url()
            continue
        break
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.url is None:
        return interactive(args.requests, args.timeout)
    return 0 if execute(args.url, args.requests, args.timeout) else 1


if __name__ == "__main__":
    sys.exit(main())
