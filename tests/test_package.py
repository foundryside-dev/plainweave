from __future__ import annotations

import charter


def test_package_exposes_version() -> None:
    assert charter.__version__ == "0.1.0"
