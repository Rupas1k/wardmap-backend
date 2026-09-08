import pytest
from d2wm_parser import parse_replay, parse_vision


@pytest.mark.parametrize("parse", [parse_replay, parse_vision])
@pytest.mark.parametrize("data", [b"", b"not a replay"])
def test_invalid_replay_is_reported_as_python_exception(parse, data):
    with pytest.raises(Exception, match="Error while parsing"):
        parse(data)
