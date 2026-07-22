import io
import logging
from dataclasses import asdict, dataclass

import polars as pl
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from computation.contracts import GroundTrackPoint
from db.postgres import SatelliteRepository
from db.redis import CoordinateRepository
from schemas.export import ExportQueryParams

logger = logging.getLogger(__name__)


class SatelliteNotFoundError(Exception):
    """КА с указанным norad_i не найден"""


@dataclass(frozen=True, slots=True)
class ExportResult:
    norad_id: int
    points: list[GroundTrackPoint]


class ExportService:

    def __init__(self, db_session: AsyncSession, redis_client: Redis) -> None:
        self._satellite_repo = SatelliteRepository(db_session)
        self._coordinate_repo = CoordinateRepository(redis_client)

    async def get_coordinates(self, params: ExportQueryParams) -> ExportResult:
        logger.info(
            "get_coordinates: start norad_id=%s start=%s stop=%s",
            params.norad_id,
            params.start,
            params.stop,
        )

        satellite = await self._satellite_repo.get_by_norad_id(params.norad_id)
        if satellite is None:
            raise SatelliteNotFoundError(f"Satellite not found: norad_id={params.norad_id}")

        points = await self._coordinate_repo.get_range(
            satellite.norad_id, params.start, params.stop
        )
        result = ExportResult(norad_id=satellite.norad_id, points=points)
        logger.info(
            "get_coordinates: done norad_id=%s points=%s",
            result.norad_id,
            len(result.points),
        )
        return result

    def to_csv(self, points: list[GroundTrackPoint]) -> bytes:
        csv_text = self._to_dataframe(points).write_csv()
        assert csv_text is not None
        return csv_text.encode("utf-8")

    def to_parquet(self, points: list[GroundTrackPoint]) -> bytes:
        buffer = io.BytesIO()
        self._to_dataframe(points).write_parquet(buffer)
        return buffer.getvalue()

    @staticmethod
    def _to_dataframe(points: list[GroundTrackPoint]) -> pl.DataFrame:
        return pl.DataFrame([asdict(point) for point in points])
