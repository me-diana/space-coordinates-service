import logging
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from computation.contracts import CoordinateCalculator, GroundTrackPoint
from db.postgres import SatelliteRepository
from db.redis import CoordinateRepository
from schemas.calculate_coordinates import (
    CoordinateCalculationRequest,
    CoordinateCalculationResponse,
)
from schemas.satellite_info import SatelliteMetadata

logger = logging.getLogger(__name__)


class CalculationService:
    def __init__(
        self,
        calculator: CoordinateCalculator,
        db_session: AsyncSession,
        redis_client: Redis,
    ) -> None:
        self._calculator = calculator
        self._db_session = db_session
        self._satellite_repo = SatelliteRepository(db_session)
        self._coordinate_repo = CoordinateRepository(redis_client)

    async def calculate(
        self, request: CoordinateCalculationRequest
    ) -> CoordinateCalculationResponse:
        orbit = request.satellite.to_computation_orbit()
        metadata = request.satellite.to_satellite_metadata()

        logger.info(
            "calculate: start norad_id=%s start=%s stop=%s step_seconds=%s",
            metadata.norad_id,
            request.start,
            request.stop,
            request.step_seconds,
        )

        points = await self._calculator.propagate(
            orbit, request.start, request.stop, request.step_seconds
        )
        await self._save_data(metadata, request.start, request.stop, points)

        result = CoordinateCalculationResponse(
            norad_id=metadata.norad_id,
            points_calculated=len(points),
            start=request.start,
            stop=request.stop,
        )

        logger.info(
            "calculate: done norad_id=%s points_calculated=%s",
            result.norad_id,
            result.points_calculated,
        )

        return result

    async def _save_data(
        self,
        metadata: SatelliteMetadata,
        start: datetime,
        stop: datetime,
        points: list[GroundTrackPoint],
    ) -> None:
        await self._satellite_repo.get_or_create(
            norad_id=metadata.norad_id,
            name=metadata.name,
            international_designator=metadata.international_designator,
            classification=metadata.classification,
        )
        await self._db_session.commit()

        await self._coordinate_repo.save_batch(metadata.norad_id, start, stop, points)
