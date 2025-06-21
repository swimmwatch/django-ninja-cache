import collections
import typing
from urllib.parse import parse_qs

from ninja_cache.types import URLParamsType


def join_url_params(params: URLParamsType, reverse: bool = False) -> str:
    """
    Join URL parameters into a string. Sorts the parameters by key.

    :param params: Dictionary of URL parameters.
    :param reverse: If True, sort the parameters in reverse order.
    :return: Joined string of URL parameters.
    """
    return "&".join(
        (
            f"{k}={v}"
            if not isinstance(v, collections.Iterable)
            else "&".join(f"{k}={val}" for val in sorted(v, reverse=reverse))
        )
        for k, v in sorted(params.items(), reverse=reverse)
    )


def sort_url_params(url_params: str) -> str:
    """
    Sort URL parameters in alphabetic order.

    :param url_params: URL parameters string.
    :return: Sorted URL parameters string.
    """
    params = parse_qs(url_params)
    return join_url_params(params)
