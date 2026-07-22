"""Protocol-контракты вычислительного ядра (computation) единственная
точка, через которую `api` обращается к `computation`.
Кконтракт спроектирован так, чтобы при выносе `computation` в отдельный
gRPC-сервис, легко превратить в proto
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class TleData:
    """Орбитальные данные в формате TLE"""

    line1: str
    line2: str
    kind: Literal["tle"] = "tle"


@dataclass(frozen=True, slots=True)
class OrbitalElements:
    """Орбитальные параметры явными полями"""

    epoch: datetime
    inclination_deg: float
    raan_deg: float
    eccentricity: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_per_day: float
    norad_id: int
    bstar: float = 0.0
    mean_motion_dot: float = 0.0
    mean_motion_ddot: float = 0.0
    kind: Literal["orbital_elements"] = "orbital_elements"


OrbitDefinition = TleData | OrbitalElements


@dataclass(frozen=True, slots=True)
class GroundTrackPoint:
    """Координаты КА в момент времени, система отсчёта WGS84."""

    timestamp: datetime
    latitude_deg: float
    longitude_deg: float
    altitude_km: float


class OrbitDataError(Exception):
    """Некорректные или невалидируемые орбитальные данные (TLE/JSON)."""


class PropagationError(Exception):
    """Расчёт не удался (например, SGP4 вернул код ошибки на вырожденной орбите)."""


class CoordinateCalculator(Protocol):
    async def propagate(
        self,
        orbit: OrbitDefinition,
        start: datetime,
        stop: datetime,
        step_seconds: float,
    ) -> list[GroundTrackPoint]:
        ...
