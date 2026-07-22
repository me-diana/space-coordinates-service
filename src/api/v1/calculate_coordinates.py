from fastapi import APIRouter, Depends

from middlewares.rate_limit import RateLimitMiddleware
from schemas.calculate_coordinates import (
    CoordinateCalculationRequest,
    CoordinateCalculationResponse,
)

from .dependencies import CalculationServiceDepend

router = APIRouter(tags=["coordinates"])


@router.post(
    "/calculate_coordinates",
    dependencies=[Depends(RateLimitMiddleware())],
    description="Calculate satellite coordinates",
)
async def calculate_coordinates(
    request: CoordinateCalculationRequest,
    service: CalculationServiceDepend,
) -> CoordinateCalculationResponse:
    return await service.calculate(request)
