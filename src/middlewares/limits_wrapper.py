from limits import RateLimitItem, RateLimitItemPerMinute
from limits.aio import storage, strategies
from redis.asyncio import Redis

from core.config import get_settings
from db.redis import redis_client


def build_throttler(redis_client: Redis) -> strategies.MovingWindowRateLimiter:
    redis_storage = storage.RedisStorage(
        get_settings().redis_url,
        implementation="redispy",
        connection_pool=redis_client.connection_pool,  # type: ignore[arg-type]
    )
    return strategies.MovingWindowRateLimiter(redis_storage)


throttler = build_throttler(redis_client)


def get_throttler() -> strategies.MovingWindowRateLimiter:
    return throttler


async def hit(key: str, rate_per_minute: int, cost: int = 1) -> bool:
    item = rate_limit_item_for(rate_per_minute=rate_per_minute)
    return await get_throttler().hit(item, key, cost=cost)


def rate_limit_item_for(rate_per_minute: int) -> RateLimitItem:
    return RateLimitItemPerMinute(rate_per_minute)
