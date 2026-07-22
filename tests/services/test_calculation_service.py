"""
Тесты CalculationService - моки, без реальных Postgres/Redis
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import services.calculation_service as calculation_service_module
from computation.contracts import (
    CoordinateCalculator,
    GroundTrackPoint,
    OrbitDataError,
    PropagationError,
)
from db.postgres import SatelliteRepository
from db.redis import CoordinateRepository
from schemas.calculate_coordinates import CoordinateCalculationRequest
from services.calculation_service import CalculationService

LINE1 = "1 69677U 26145A   26202.59920150 -.00220234  00000+0 -22387-2 0  9994"
LINE2 = "2 69677  97.2844  49.7323 0000685  66.9134 293.2198 15.65787759  4184"

START = datetime(2019, 12, 9, 16, 38, 32, tzinfo=UTC)
STOP = START + timedelta(minutes=30)

POINTS = [
    GroundTrackPoint(timestamp=START, latitude_deg=49.8, longitude_deg=-5.2, altitude_km=421.7),
    GroundTrackPoint(timestamp=STOP, latitude_deg=-30.4, longitude_deg=83.3, altitude_km=430.2),
]

def _make_request() -> CoordinateCalculationRequest:
    return CoordinateCalculationRequest.model_validate(
        {
            "satellite": {
                "format": "tle",
                "data": {"line1": LINE1, "line2": LINE2, "satellite_name": "STARLINK-38005"},
            },
            "start": START.isoformat(),
            "stop": STOP.isoformat(),
            "step_seconds": 1800,
        }
    )


@pytest.fixture
def call_log() -> list[str]:
    """Общий журнал вызовов - для проверки порядка и факта вызова"""
    return []


@pytest.fixture
def mock_calculator(call_log: list[str]) -> AsyncMock:
    calculator = AsyncMock(spec=CoordinateCalculator)

    async def propagate(*args: object, **kwargs: object) -> list[GroundTrackPoint]:
        call_log.append("propagate")
        return POINTS

    calculator.propagate.side_effect = propagate
    return calculator


@pytest.fixture
def mock_db_session(call_log: list[str]) -> AsyncMock:
    db_session = AsyncMock(spec=AsyncSession)

    async def commit() -> None:
        call_log.append("commit")

    db_session.commit.side_effect = commit
    return db_session


@pytest.fixture
def mock_satellite_repo(call_log: list[str]) -> AsyncMock:
    repo = AsyncMock(spec=SatelliteRepository)

    async def get_or_create(**kwargs: object) -> None:
        call_log.append("get_or_create")

    repo.get_or_create.side_effect = get_or_create
    return repo


@pytest.fixture
def mock_coordinate_repo(call_log: list[str]) -> AsyncMock:
    repo = AsyncMock(spec=CoordinateRepository)

    async def save_batch(*args: object, **kwargs: object) -> None:
        call_log.append("save_batch")

    repo.save_batch.side_effect = save_batch
    return repo


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
    mock_calculator: AsyncMock,
    mock_db_session: AsyncMock,
    mock_satellite_repo: AsyncMock,
    mock_coordinate_repo: AsyncMock,
) -> CalculationService:
    monkeypatch.setattr(
        calculation_service_module, "SatelliteRepository", lambda session: mock_satellite_repo
    )
    monkeypatch.setattr(
        calculation_service_module,
        "CoordinateRepository",
        lambda redis_client: mock_coordinate_repo,
    )
    return CalculationService(mock_calculator, mock_db_session, redis_client=None)  # type: ignore[arg-type]


async def test_calculate_orbit_data_error(
    service: CalculationService,
    mock_calculator: AsyncMock,
    mock_satellite_repo: AsyncMock,
    mock_db_session: AsyncMock,
    mock_coordinate_repo: AsyncMock,
    call_log: list[str],
) -> None:
    # Arrange
    mock_calculator.propagate.side_effect = OrbitDataError("invalid TLE")

    # Act + Assert
    with pytest.raises(OrbitDataError):
        await service.calculate(_make_request())

    # Assert до записи в БД/Redis не дошло.
    assert call_log == []
    mock_satellite_repo.get_or_create.assert_not_awaited()
    mock_db_session.commit.assert_not_awaited()
    mock_coordinate_repo.save_batch.assert_not_awaited()


async def test_calculate_propagation_error(
    service: CalculationService,
    mock_calculator: AsyncMock,
    mock_satellite_repo: AsyncMock,
    mock_db_session: AsyncMock,
    mock_coordinate_repo: AsyncMock,
    call_log: list[str],
) -> None:
    # Arrange
    mock_calculator.propagate.side_effect = PropagationError("degenerate orbit")

    # Act + Assert
    with pytest.raises(PropagationError):
        await service.calculate(_make_request())

    # Assert: до записи в БД/Redis не дошло.
    assert call_log == []
    mock_satellite_repo.get_or_create.assert_not_awaited()
    mock_db_session.commit.assert_not_awaited()
    mock_coordinate_repo.save_batch.assert_not_awaited()
