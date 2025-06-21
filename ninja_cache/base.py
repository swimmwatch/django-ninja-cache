import abc
import datetime
import logging
import typing
from itertools import chain
from urllib.parse import parse_qs

from django.core.cache import caches
from django.http import HttpResponse
from django.urls import reverse
from django.utils.http import http_date
from django.utils.timezone import now
from ninja.conf import settings

from ninja_cache.headers import CacheControlHeader
from ninja_cache.types import PathParamsType
from ninja_cache.types import SupportsStr
from ninja_cache.types import URLParamsType
from ninja_cache.utils import join_url_params

_KEY_SEPARATOR = ":"
_DEFAULT_USER_KEY = "anon"

logger = logging.getLogger(__name__)


class BaseCacheDecorator(abc.ABC):
    """
    Base class for cache decorators.
    This class should be extended to implement specific caching strategies.
    """

    _API_VERSION = getattr(settings, "API_VERSION", "v1")
    _CACHE_NAME = getattr(settings, "NINJA_CACHE_NAME", "default")
    _GLOBAL_CACHE_PREFIX = getattr(settings, "NINJA_CACHE_PREFIX", "ninja_cache")
    _CACHE = caches[_CACHE_NAME]

    def __init__(
        self,
        timeout: int,
        url_name: str,
        per_user: bool = False,
        cache_control: typing.Optional[CacheControlHeader] = None,
        expired: bool = False,
    ):
        self._timeout = timeout
        self._url_name = url_name
        self._key_prefix = url_name
        self._per_user = per_user
        self._cache_control = cache_control
        self._expired = expired

    @property
    def url_name(self) -> str:
        """
        Get the URL name for the cache decorator.

        :return: The URL name.
        """
        return self._url_name

    @property
    def view_name(self) -> str:
        """
        Get the view name for the cache decorator.

        :return: The view name.
        """
        return f"api-{settings.API_VERSION}:{self._url_name}"

    def _reverse_url(self, **kwargs: typing.Any) -> str:
        params = None
        if "params" in kwargs:
            params = kwargs.pop("params")

        url = reverse(self.view_name, kwargs=kwargs)

        if params is not None:
            url += join_url_params(params)

        return url

    def _generate_remove_cache_key(
        self,
        user_id: typing.Optional[SupportsStr] = None,
        path_params: typing.Optional[PathParamsType] = None,
    ):
        """
        Generate a remove cache key based on the user ID and the path params (if was passed).

        :param user_id: The user ID to include in the cache key. If None, use the default user key.
        :param path_params: Optional path parameters to include in the cache key.
        :return: The generated removed cache key.
        """
        user_id: str
        if user_id is None:
            user_id = _DEFAULT_USER_KEY
        elif self._per_user:
            user_id = str(user_id)

        if path_params:
            reverse_path = self._reverse_url(**path_params)
        else:
            reverse_path = None

        keys = (
            self._GLOBAL_CACHE_PREFIX,
            self._key_prefix,
            user_id,
            reverse_path,
        )
        keys = (key for key in keys if key is not None)
        return _KEY_SEPARATOR.join(keys)

    def _generate_expired_cache_key(
        self,
        user_id: typing.Optional[SupportsStr] = None,
        path_params: typing.Optional[PathParamsType] = None,
    ) -> str:
        """
        Generate an expired cache key.

        :param user_id: The user ID to include in the cache key. If None, use the default user key.
        :param path_params: Optional path parameters to include in the cache key.
        :return: The generated expired cache key.
        """
        user_id: str
        if user_id is None:
            user_id = _DEFAULT_USER_KEY
        elif self._per_user:
            user_id = str(user_id)

        if path_params:
            reverse_path = self._reverse_url(**path_params)
        else:
            reverse_path = None

        keys = (
            self._GLOBAL_KEY_PREFIX,
            self._key_prefix,
            user_id,
            reverse_path,
            "expired",
        )
        keys = (key for key in keys if key is not None)
        return self._KEY_SEPARATOR.join(keys)

    def _generate_remove_pattern(
        self,
        user_id: typing.Optional[SupportsStr] = None,
        all_: bool = False,
        path_params: typing.Optional[PathParamsType] = None,
    ) -> str:
        """
        Generate a pattern for removing cache keys.

        :param user_id: The user ID to include in the pattern. If None, use the default user key.
        :param all_: If True, match all user IDs.
        :param path_params: Optional path parameters to include in the pattern.
        :return: The generated pattern for removing cache keys.
        """
        if all_:
            user_id = "*"

        key_str = self._generate_remove_cache_key(user_id, path_params=path_params)
        return f"*{key_str}*"

    def reset_cache(
        self,
        user_ids: typing.Optional[typing.Set[SupportsStr]] = None,
        all_: bool = False,
        path_params: typing.Optional[PathParamsType] = None,
    ) -> None:
        if user_ids is not None and not all_:
            logger.debug(f"Resetting cache for {len(user_ids)} users {user_ids!s}")

            patterns = [
                self._generate_remove_pattern(
                    user_id,
                    path_params=path_params,
                )
                for user_id in user_ids
            ]
            keys = chain.from_iterable(self._CACHE.keys(pattern) for pattern in patterns)
            keys = list(keys)

            logger.debug(f"Deleting keys from cache: {keys}")

            self._CACHE.delete_many(keys)
            return

        pattern = self._generate_remove_pattern(
            all_=all_,
            path_params=path_params,
        )
        keys = self._CACHE.keys(pattern)

        if keys:
            logger.debug(f"Resetting cache for {keys}")
            self._CACHE.delete_many(keys)
        else:
            logger.debug("No keys found in cache for pattern. Don't remove.")

    @staticmethod
    def _set_last_modified_response(context: RouteContext | HttpResponse | None, last_modified: datetime) -> None:
        if context is None:
            logger.warning("Context is None, cannot set Last-Modified header.")
            return

        if isinstance(context, HttpResponse):
            # If context is a HttpResponse, we can set headers directly
            context_response = context
        else:
            context_response = context.response

        http_date_str = http_date(last_modified.timestamp())
        context_response.headers["Last-Modified"] = http_date_str

    @staticmethod
    def _set_expired_response(context: RouteContext | HttpResponse | None, dt: datetime) -> None:
        if context is None:
            logger.warning("Context is None, cannot set Expires header.")
            return

        if isinstance(context, HttpResponse):
            # If context is a HttpResponse, we can set headers directly
            context_response = context
        else:
            context_response = context.response

        http_date_str = http_date(dt.timestamp())
        context_response.headers["Expires"] = http_date_str

    def _get_last_modified_key(
        self,
        cache_key: str,
    ) -> str:
        """
        Get the last modified key for a cache key.

        :param cache_key: The cache key to check.
        :return: The last modified key.
        """
        return f"{cache_key}:last_modified"

    def _get_or_set_last_modified(
        self,
        cache_key: str,
        timeout: int,
    ) -> typing.Tuple[datetime, bool]:
        """
        Get or set the last modified time for a cache key.

        :param cache_key: The cache key to check.
        :param timeout: Cache timeout in seconds.
        :return: The last modified time as a datetime object and created flag.
        """
        last_modified_key = self._get_last_modified_key(cache_key)
        last_modified = self._CACHE.get(last_modified_key)
        if last_modified is None:
            last_modified = now()
            last_modified = last_modified.replace(microsecond=0)
            logger.debug("Last modified not found in cache, setting new value: %s", last_modified)
            self._CACHE.set(last_modified_key, last_modified, timeout)
            return last_modified, True

        logger.debug("Last modified found in cache: %s", last_modified)
        return last_modified, False

    def _generate_cache_key(
        self,
        path: str,
        query_string: str = "",
        user: typing.Optional["User"] = None,
    ) -> str:
        """
        Generate a cache key based on the path, query string, and user ID.

        :param path: The request path.
        :param query_string: The query string of the request.
        :param user: The user making the request.
        :return: The generated cache key.
        """
        user_id = str(user.id) if (user and user.is_authenticated and self._per_user) else self._DEFAULT_USER_KEY

        logger.debug(f"User ID for cache: {user_id}")

        if query_string:
            params = parse_qs(query_string)
            query_string = "&".join(f"{k}={v[0] if isinstance(v, list) else v}" for k, v in sorted(params.items()))

        keys = (
            self._GLOBAL_KEY_PREFIX,
            self._key_prefix,
            user_id,
            path,
            query_string,
        )
        return self._KEY_SEPARATOR.join(keys)

    @abc.abstractmethod
    def __call__(self):
        """
        Decorator to cache the response of a function.

        :return: Decorator function.
        """
        raise NotImplementedError("Subclasses must implement __call__ method.")
