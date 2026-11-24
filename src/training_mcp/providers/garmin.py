"""Garmin Connect Personal API provider (own data only, read-only).

Wraps Garmin's official client (``garmin-connect-personal-api-python``), which is
synchronous (``requests``). Every call runs in a worker thread so the async MCP server
never blocks its event loop.

Auth flow, handled by the library: the personal API key is exchanged for a bearer JWT
valid for up to 24 h; the token is cached on disk (mode 0600) and renewed when less than
an hour remains. There are no refresh tokens. If Garmin still answers 401 (token revoked
early) we force a new exchange and retry once.

Docs: https://developer.garmin.com/gc-developer-program/personal/personal-api
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path

import requests
from garmin_personal_api import (
    DEFAULT_BEARER_TOKEN_CACHE_FILE,
    GarminPersonalApiClient,
    GarminPersonalApiError,
    HttpError,
    PersonalApiAuthenticator,
)
from garmin_personal_api.client import JsonValue
from pydantic import SecretStr

logger = logging.getLogger(__name__)

MAX_ACTIVITIES_PER_PAGE = 100

__all__ = ["MAX_ACTIVITIES_PER_PAGE", "GarminAuthError", "GarminError", "GarminProvider", "JsonValue"]


class GarminError(Exception):
    """A Garmin call failed. The message is safe to show to an MCP client."""


class GarminAuthError(GarminError):
    """The API key was rejected (expired, deleted or wrong)."""


def _to_safe_error(exc: GarminPersonalApiError | requests.RequestException) -> GarminError:
    """Map library errors to messages without Garmin's raw response body or URLs."""
    if isinstance(exc, HttpError):
        if exc.method == "POST" and exc.status_code in (400, 401, 403):
            return GarminAuthError(
                "Garmin rejected the personal API key (expired, deleted or wrong). "
                "Create a new one in Garmin Connect > Settings > Personal API Token."
            )
        if exc.status_code == 404:
            return GarminError("Not found in Garmin Connect")
        if exc.status_code == 429:
            return GarminError("Garmin rate limit reached, try again later")
        return GarminError(f"Garmin returned HTTP {exc.status_code}")
    if isinstance(exc, requests.RequestException):
        return GarminError(f"Could not reach Garmin: {type(exc).__name__}")
    return GarminError("Unexpected response from Garmin")


class GarminProvider:
    """Async facade over the official client, limited to what our MCP tools need."""

    def __init__(
        self,
        api_key: SecretStr,
        *,
        token_cache_file: str | Path = DEFAULT_BEARER_TOKEN_CACHE_FILE,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._auth = PersonalApiAuthenticator(
            timeout=timeout, session=self._session, bearer_token_cache_file=token_cache_file
        )
        # Placeholder token; replaced before the first request.
        self._client = GarminPersonalApiClient("unset", timeout=timeout, session=self._session)
        self._token_lock = threading.Lock()

    def close(self) -> None:
        self._session.close()

    def _refresh_token(self, *, force: bool) -> None:
        with self._token_lock:
            token = self._auth.obtain_token(self._api_key.get_secret_value(), force_refresh=force)
            self._client.update_bearer_token(token.access_token)

    def _call_sync[T](self, fn: Callable[[GarminPersonalApiClient], T]) -> T:
        try:
            self._refresh_token(force=False)
            try:
                return fn(self._client)
            except HttpError as exc:
                if exc.status_code != 401:
                    raise
                logger.info("Garmin returned 401; exchanging the API key again")
                self._refresh_token(force=True)
                return fn(self._client)
        except (GarminPersonalApiError, requests.RequestException) as exc:
            raise _to_safe_error(exc) from exc

    async def _call[T](self, fn: Callable[[GarminPersonalApiClient], T]) -> T:
        return await asyncio.to_thread(self._call_sync, fn)

    async def search_activities(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        activity_type: str | None = None,
        start: int = 0,
        limit: int = 20,
    ) -> JsonValue:
        return await self._call(
            lambda c: c.search_activities(
                start=start,
                limit=min(limit, MAX_ACTIVITIES_PER_PAGE),
                start_date=start_date,
                end_date=end_date,
                activity_type=activity_type,
            )
        )

    async def get_activity(self, activity_id: int) -> JsonValue:
        return await self._call(lambda c: c.get_activity(activity_id))

    async def get_daily_sleep(self, day: date) -> JsonValue:
        return await self._call(lambda c: c.get_daily_sleep(day))

    async def get_daily_hrv(self, day: date) -> JsonValue:
        return await self._call(lambda c: c.get_daily_hrv(day))

    async def get_daily_body_battery(self, day: date) -> JsonValue:
        return await self._call(lambda c: c.get_daily_body_battery(day, day))
