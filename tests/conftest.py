import pytest

from tests.helpers import ffx, premiere


@pytest.fixture
def premiere_file(tmp_path):
    p = tmp_path / "original.prfpset"
    p.write_bytes(premiere())
    return p


@pytest.fixture
def ffx_file(tmp_path):
    p = tmp_path / "original.ffx"
    p.write_bytes(ffx())
    return p
