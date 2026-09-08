import pytest
from d2wm_parser import parse_replay


@pytest.mark.parametrize("data", [b"", b"not a replay"])
def test_invalid_replay_is_reported_as_python_exception(data):
    with pytest.raises(Exception, match="Error while parsing"):
        parse_replay(data)
