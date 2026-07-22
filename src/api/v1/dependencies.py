"""
FastAPI-зависимости для роутеров
"""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from computation.contracts import CoordinateCalculator
from db.postgres import get_db_session
from db.redis import get_redis_client
from services.calculation_service import CalculationService
from services.export_service import ExportService


def get_coordinate_calculator(request: Request) -> CoordinateCalculator:
    return request.app.state.calculator  # type: ignore[no-any-return]


def get_calculation_service(
    calculator: CoordinateCalculator = Depends(get_coordinate_calculator),
    db_session: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
) -> CalculationService:
    return CalculationService(calculator, db_session, redis_client)


def get_export_service(
    db_session: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
) -> ExportService:
    return ExportService(db_session, redis_client)


CalculationServiceDepend = Annotated[CalculationService, Depends(get_calculation_service)]
ExportServiceDepend = Annotated[ExportService, Depends(get_export_service)]
