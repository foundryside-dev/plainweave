from __future__ import annotations

from pathlib import Path

import pytest

from plainweave.paths import default_project_key, plainweave_db_path
from plainweave.store import migrate


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    # Initialize a fresh local store under a temp root.
    migrate(plainweave_db_path(tmp_path), project_key=default_project_key(tmp_path))
    return tmp_path
