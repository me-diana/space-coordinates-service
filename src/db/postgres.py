"""
Работа с БД PostgreSQL
"""

from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings
from models.satellite import Satellite

engine: AsyncEngine = create_async_engine(get_settings().postgres_url)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


class SatelliteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_norad_id(self, norad_id: int) -> Satellite | None:
        result = await self._session.execute(
            select(Satellite).where(Satellite.norad_id == norad_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        *,
        norad_id: int,
        name: str | None,
        international_designator: str | None = None,
        classification: str | None = None,
    ) -> Satellite:
        insert_operation = (
            pg_insert(Satellite)
            .values(
                norad_id=norad_id,
                name=name,
                international_designator=international_designator,
                classification=classification,
            )
            .on_conflict_do_nothing(index_elements=[Satellite.norad_id])
            .returning(Satellite)
        )
        result = await self._session.execute(insert_operation)
        inserted = result.scalars().one_or_none()
        if inserted is not None:
            return inserted

        # Если дошли до сюда, значит строка с этим norad_id уже существует
        existing = await self.get_by_norad_id(norad_id)
        assert existing is not None
        return existing
