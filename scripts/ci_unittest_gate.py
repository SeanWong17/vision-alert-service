"""CI 单测闸门：执行 unittest 并校验最小有效执行数与跳过比例。"""

from __future__ import annotations

import os
import sys
import unittest


def main() -> int:
    min_executed = int(os.getenv("CI_MIN_EXECUTED_TESTS", "10"))
    max_skip_ratio = float(os.getenv("CI_MAX_SKIP_RATIO", "0.40"))

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = int(result.testsRun)
    skipped = len(result.skipped)
    executed = total - skipped
    skip_ratio = (skipped / total) if total else 1.0

    print(
        f"\n[ci-gate] total={total} executed={executed} skipped={skipped} "
        f"skip_ratio={skip_ratio:.2%} min_executed={min_executed} max_skip_ratio={max_skip_ratio:.2%}"
    )

    if not result.wasSuccessful():
        print("[ci-gate] failing because unittest result is not successful")
        return 1
    if total == 0:
        print("[ci-gate] failing because no tests were discovered")
        return 1
    if executed < min_executed:
        print("[ci-gate] failing because executed tests are below threshold")
        return 1
    if skip_ratio > max_skip_ratio:
        print("[ci-gate] failing because skip ratio is above threshold")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
