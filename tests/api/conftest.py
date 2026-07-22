from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.config import get_settings
from main import app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_db_pool() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_redis_client() -> AsyncIterator[Redis]:
    redis_client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        yield redis_client
    finally:
        await redis_client.aclose()
