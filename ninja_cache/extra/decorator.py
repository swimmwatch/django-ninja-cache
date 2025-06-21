import logging
import typing
from email.utils import parsedate_to_datetime
from functools import wraps

from django.http import HttpResponse
from django.http import HttpResponseNotModified

from ninja_cache.base import BaseCacheDecorator
from ninja_cache.headers import CacheControlHeader

logger = logging.getLogger(__name__)


class NinjaCacheExtraDecorator(BaseCacheDecorator):
    def __init__(
        self,
        timeout: int,
        url_name: str,
        per_user: bool = False,
        cache_control: typing.Optional[CacheControlHeader] = None,
        expired: bool = False,
    ):
        super().__init__(
            timeout,
            url_name,
            per_user,
            cache_control,
            expired,
        )

    def _set_cache_control_headers(
        self,
        context: typing.Optional[typing.Union[RouteContext, HttpResponse]],
    ):
        """
        Set cache control headers in the response context.

        :param context: The RouteContext to set headers in.
        """
        if context is None:
            logger.warning("Context is None, cannot set Cache-Control headers.")
            return

        if isinstance(context, HttpResponse):
            # If context is a HttpResponse, we can set headers directly
            context_response = context
        else:
            context_response = context.response

        if self._cache_control is not None:
            headers = self._cache_control.get_headers()
            for key, value in headers.items():
                context_response.headers[key] = value

            logger.info(f"Cache-Control headers set: {headers}")

    def __call__(self):
        """
        Decorator to cache the response of a function.

        :return: Decorator function.
        """

        def decorator(func: typing.Callable[..., typing.Any]):
            @wraps(func)
            def wrapper(
                request_or_controller: typing.Union[ControllerBase, HttpRequest],
                *args: typing.Any,
                **kw: typing.Any,
            ):
                is_router_context = isinstance(request_or_controller.context, RouteContext)
                has_context = hasattr(request_or_controller, "context")
                if has_context and is_router_context:
                    context = request_or_controller.context
                    request = request_or_controller.context.request
                else:
                    context = None
                    request = request_or_controller

                func_kwargs = dict(**kw)
                user = getattr(request, "user", getattr(request, "auth", None))

                if self._per_user and user is None:
                    raise ValueError("User-specific caching is not supported in this context.")

                query_string = request.META.get("QUERY_STRING", "")
                cache_key = self._generate_cache_key(
                    request.path,
                    query_string,
                    user,
                )
                logger.info(f"Cache key {cache_key}")

                last_modified = self._get_or_set_last_modified(cache_key, self._timeout)

                if self._expired:
                    expired_dt = self.get_expired()  # TODO: pass path params
                    if expired_dt is not None:
                        logger.debug(f"Expired datetime found in cache: {expired_dt}. Setting Expires header.")
                    else:
                        logger.debug("No expired datetime found in cache. Not setting Expires header.")
                else:
                    expired_dt = None

                has_cached_response = self._CACHE.has_key(cache_key)
                if has_cached_response:
                    logger.debug(f"Cache hit for {cache_key}")

                    if_modified_since = request.META.get("HTTP_IF_MODIFIED_SINCE")
                    if if_modified_since:
                        if_modified_since = parsedate_to_datetime(if_modified_since)
                        if if_modified_since >= last_modified:
                            logger.debug("Response not modified since last request: %s", if_modified_since)

                            response = HttpResponseNotModified()

                            self._set_last_modified_response(response, last_modified)
                            self._set_cache_control_headers(response)
                            if expired_dt is not None:
                                self._set_expired_response(response, expired_dt)

                            return response

                    cached_response = self._CACHE.get(cache_key)

                    self._set_last_modified_response(context, last_modified)
                    self._set_cache_control_headers(context)
                    if expired_dt is not None:
                        self._set_expired_response(context, expired_dt)

                    logger.debug("Response modified since last request: %s", if_modified_since)
                    return cached_response

                logger.debug(f"Cache miss for {cache_key}")

                response = func(request_or_controller, *args, **func_kwargs)

                self._set_cache_control_headers(context)
                self._set_last_modified_response(context, last_modified)
                if expired_dt is not None:
                    self._set_expired_response(context, expired_dt)

                if context is not None:
                    context_response = context.response
                    if context_response.streaming or context_response.status_code not in (200, 304):
                        logger.debug("Response is streaming or not 200/304, skipping cache.")
                        return response

                if response is None:
                    logger.debug("Response is None, skipping cache.")
                    return response

                self._CACHE.set(cache_key, response, self._timeout)
                logger.debug(f"Cache set for key {cache_key}")

                return response

            return wrapper

        return decorator
