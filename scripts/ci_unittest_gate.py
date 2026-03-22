"""CI 单测闸门：执行 unittest 并校验最小有效执行数与跳过比例。"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest


def _ensure_repo_root_on_path() -> None:
    """确保直接执行脚本时也能导入仓库内的 app/tests 包。"""

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def main() -> int:
    _ensure_repo_root_on_path()
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
