from __future__ import annotations

import plainweave


def test_package_exposes_version() -> None:
    assert isinstance(plainweave.__version__, str)
    assert plainweave.__version__  # exposed; the value is per-release, not pinned here
