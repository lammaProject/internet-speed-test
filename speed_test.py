"""Measure download speed by fetching the same URL sequentially."""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

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
            raise RuntimeError(
                f"request {index}/{count} failed: {exc}"
            ) from exc
        measurements.append(measurement)
        print(
            f"{index:2d}/{count}  "
            f"{measurement.size_bytes / MEGABYTE:8.2f} MB  "
            f"{measurement.elapsed_s:7.3f} s  "
            f"{measurement.speed_mb_s:7.2f} MB/s"
        )
    return measurements


def summarize(measurements: list[Measurement], total_time: float) -> str:
    total_bytes = sum(item.size_bytes for item in measurements)
    request_time = sum(item.elapsed_s for item in measurements)
    count = len(measurements)
    average_time = request_time / count if count else 0.0
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


def execute(url: str) -> str | None:
    print(f"URL:      {url}")
    print(f"Requests: {DEFAULT_REQUESTS}, timeout: {DEFAULT_TIMEOUT:g} s")
    print()
    started = time.perf_counter()
    try:
        measurements = run(url, DEFAULT_REQUESTS, DEFAULT_TIMEOUT)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None
    wall_time = time.perf_counter() - started
    print()
    summary = summarize(measurements, wall_time)
    print(summary)
    return summary


def validate_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    has_space = any(char.isspace() for char in url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or has_space:
        raise ValueError(
            f"{url!r} is not a valid URL. The script needs a full address "
            "starting with http:// or https:// to know which file to "
            "download, e.g. https://example.com/image.jpg"
        )
    return url


def read_url() -> str | None:
    while True:
        try:
            value = input("URL (empty to exit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not value:
            return None
        try:
            return validate_url(value)
        except ValueError as exc:
            print(f"error: {exc}")


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


def interactive() -> int:
    url = read_url()
    previous_url: str | None = None
    previous_summary: str | None = None
    while url:
        if url == previous_url and previous_summary is not None:
            print()
            print("Previous result:")
            print(previous_summary)
            print()
        summary = execute(url)
        if summary is not None:
            previous_url = url
            previous_summary = summary
        choice = ask_choice()
        if choice == "1":
            continue
        if choice == "2":
            url = read_url()
            continue
        break
    return 0


def main() -> int:
    return interactive()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(
            "error: this script takes no arguments; enter the URL when prompted",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(main())
