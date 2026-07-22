"""
Pydantic-схемы запроса/ответа расчета координат.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .satellite_info import SatelliteInput


class CoordinateCalculationRequest(BaseModel):
    satellite: SatelliteInput
    start: datetime
    stop: datetime
    step_seconds: float = Field(..., gt=0)


class CoordinateCalculationResponse(BaseModel):
    """Не сами координаты, только подтверждение расчёта"""

    norad_id: int
    points_calculated: int
    start: datetime
    stop: datetime
