from __future__ import annotations

import plainweave


def test_package_exposes_version() -> None:
    assert plainweave.__version__ == "0.0.1"
