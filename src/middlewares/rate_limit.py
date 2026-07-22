"""
Ограничение частоты запросов

Применяется точечно на POST /v1/calculate_coordinates -
самом дорогом по CPU эндпоинте.
"""

import typing as t

from fastapi import HTTPException, Request, status

from core.config import get_settings

from .limits_wrapper import hit


async def _default_identifier(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _default_callback(request: Request) -> t.NoReturn:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="request limit reached"
    )


async def _default_rate_provider(request: Request) -> int:
    return get_settings().rate_limit_per_minute


class RateLimitMiddleware:
    def __init__(
        self,
        identifier: t.Callable[[Request], t.Awaitable[str]] = _default_identifier,
        callback: t.Callable[[Request], t.Awaitable[t.Any]] = _default_callback,
        rate_provider: t.Callable[[Request], t.Awaitable[int]] = _default_rate_provider,
    ) -> None:
        self.identifier = identifier
        self.callback = callback
        self.rate_provider = rate_provider

    async def __call__(self, request: Request) -> None:
        key = await self.identifier(request)
        rate = await self.rate_provider(request)
        if not await hit(key=key, rate_per_minute=rate):
            await self.callback(request)
