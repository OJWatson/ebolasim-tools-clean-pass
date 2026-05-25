import pytest

from ebolasim_tools import ParameterSet, tiny_parameter_set
from ebolasim_tools.params import ParameterFormatError


def test_parameter_set_round_trip(tmp_path):
    path = tmp_path / "params.txt"
    params = ParameterSet({"A": 1, "B": [2, 3], "C": "hello"})
    params.write(path)
    loaded = ParameterSet.read(path)
    assert list(loaded) == ["A", "B", "C"]
    assert loaded["B"] == "2 3"
    assert loaded.to_text() == "[A]\n1\n[B]\n2 3\n[C]\nhello\n"


def test_parameter_set_update_returns_copy():
    params = ParameterSet({"A": 1})
    updated = params.update_values({"A": 2, "B": 3})
    assert params["A"] == "1"
    assert updated["A"] == "2"
    assert updated["B"] == "3"


def test_parameter_numbers():
    params = ParameterSet({"A": "1 2.5 3"})
    assert params.get_int("A") == 1
    assert params.get_float("A") == 1.0
    assert params.get_numbers("A") == [1.0, 2.5, 3.0]


def test_parameter_format_rejects_value_before_header():
    with pytest.raises(ParameterFormatError):
        ParameterSet.from_text("1\n[A]\n2\n")


def test_parameter_name_validation():
    params = ParameterSet()
    with pytest.raises(ValueError):
        params[""] = 1
    with pytest.raises(ValueError):
        params["bad[name]"] = 1


def test_tiny_parameter_set_contains_required_runtime_keys():
    params = tiny_parameter_set()
    for key in ["Update timestep", "Sampling timestep", "Population size", "Reproduction number"]:
        assert key in params
    assert params.get_int("Population size") == 24
    assert len(params) > 60
