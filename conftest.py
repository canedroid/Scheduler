import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def today_vault(tmp_path):
    """An isolated on-disk vault directory for scanner tests."""
    return tmp_path