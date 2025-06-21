import pytest

from ninja_cache.types import URLParamsType
from ninja_cache.utils import join_url_params


class TestJoinUrlParams:
    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({}, ""),
            ({"a": "1"}, "a=1"),
            ({"b": "2", "a": "1"}, "a=1&b=2"),
            ({"b": "2", "a": "1", "c": "3"}, "a=1&b=2&c=3"),
            ({"c": "3", "b": "2", "a": "1"}, "a=1&b=2&c=3"),
            ({"a": ["1", "2"]}, "a=1&a=2"),
            ({"a": ["2", "1"]}, "a=1&a=2"),
            ({"a": ["1", "2"], "b": ["3", "4"]}, "a=1&a=2&b=3&b=4"),
            ({"b": ["2", "1"], "a": ["4", "3"]}, "a=3&a=4&b=1&b=2"),
        ],
    )
    def test_success(self, params: URLParamsType, expected: str):
        result = join_url_params(params)
        assert result == expected
