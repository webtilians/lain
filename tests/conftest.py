import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from server.world_core import database


@pytest.fixture(autouse=True)
def isolated_world_database(
    tmp_path,
    monkeypatch,
):
    test_db = (
        tmp_path
        / "world_test.db"
    )

    monkeypatch.setattr(
        database,
        "DB_PATH",
        test_db,
    )

    database.initialize_database()

    yield test_db