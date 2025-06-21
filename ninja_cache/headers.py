import abc
import typing

from ninja_cache.types import HeaderType


class BaseHeader(abc.ABC):
    """Base class for HTTP headers."""

    @abc.abstractmethod
    def get_headers(self) -> HeaderType:
        raise NotImplementedError("Subclasses must implement get_headers method.")


class CacheControlHeader(BaseHeader):
    def __init__(
        self,
        max_age: typing.Optional[int] = None,
        public: bool = True,
    ):
        self._max_age = max_age
        self._public = public

    def get_headers(self) -> HeaderType:
        values = (
            "public" if self._public else "private",
            f"max-age={self._max_age}" if self._max_age is not None else None,
        )
        values = [value for value in values if value is not None]
        headers = {
            "Cache-Control": ", ".join(values),
        }
        return headers
