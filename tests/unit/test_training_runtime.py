"""`ru_maxrss` unit resolution, which is not portable (S04.2).

`getrusage` reports `ru_maxrss` in kibibytes on Linux and in bytes on macOS and
the BSDs, so a single unconditional multiplier over-reports peak memory by 1024x
on half the platforms a contributor might use. `runtime_facts` records that number
as a measured provenance fact, so a wrong unit is a wrong recorded fact.

These tests live here rather than beside the other runtime assertions in
`tests/integration/test_training_smoke.py` because that module is gated on
`model_is_cached`: on a machine without the 265 MB of weights cached — including
CI — everything in it skips, and a skip would report green while proving nothing.
`ru_maxrss_scale` is pure and loads no model, so it needs no gate.
"""

from __future__ import annotations

import pytest

from intentguard.training import KIBIBYTE, peak_memory_bytes, ru_maxrss_scale


@pytest.mark.parametrize("platform_name", ["darwin", "freebsd", "openbsd", "netbsd", "dragonfly"])
def test_byte_reporting_platforms_are_not_scaled(platform_name: str) -> None:
    assert ru_maxrss_scale(platform_name) == 1


@pytest.mark.parametrize("platform_name", ["linux", "linux2", "win32", "cygwin", "aix"])
def test_other_platforms_are_scaled_from_kibibytes(platform_name: str) -> None:
    # Linux is the measured case. Anything unrecognised keeps the documented POSIX
    # kibibyte reading rather than silently reporting a raw number as bytes.
    assert ru_maxrss_scale(platform_name) == KIBIBYTE


def test_the_two_platform_families_disagree() -> None:
    # The whole point of the function: if these ever matched, the bug it fixes
    # would be back and every other test here would still pass.
    assert ru_maxrss_scale("darwin") != ru_maxrss_scale("linux")


def test_a_versioned_platform_string_is_matched_by_prefix() -> None:
    # `sys.platform` is not always a bare name; historically it carried a version
    # suffix, so matching must be a prefix test rather than equality.
    assert ru_maxrss_scale("darwin21") == 1
    assert ru_maxrss_scale("freebsd14") == 1


def test_peak_memory_is_positive_and_plausible() -> None:
    measured = peak_memory_bytes()

    # A running CPython process holds more than 1 MiB and, in this suite, far less
    # than 64 GiB. The window is wide on purpose: it catches a 1024x unit error in
    # either direction without pinning a machine-specific number.
    assert 1 << 20 < measured < 1 << 36
