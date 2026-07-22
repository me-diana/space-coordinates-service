from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import polars as pl
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import services.export_service as export_service_module
from computation.contracts import GroundTrackPoint
from db.postgres import SatelliteRepository
from db.redis import CoordinateRepository
from schemas.export import ExportFormat, ExportQueryParams
from services.export_service import ExportResult, ExportService, SatelliteNotFoundError

START = datetime(2019, 12, 9, 16, 38, 32, tzinfo=UTC)
STOP = START + timedelta(minutes=30)

POINTS = [
    GroundTrackPoint(timestamp=START, latitude_deg=49.8, longitude_deg=-5.2, altitude_km=421.7),
    GroundTrackPoint(timestamp=STOP, latitude_deg=-30.4, longitude_deg=83.3, altitude_km=430.2),
]

FAKE_NORAD_ID = 69677


@pytest.fixture
def mock_db_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_satellite_repo() -> AsyncMock:
    return AsyncMock(spec=SatelliteRepository)


@pytest.fixture
def mock_coordinate_repo() -> AsyncMock:
    repo = AsyncMock(spec=CoordinateRepository)
    repo.get_range.return_value = POINTS
    return repo


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
    mock_db_session: AsyncMock,
    mock_redis_client: AsyncMock,
    mock_satellite_repo: AsyncMock,
    mock_coordinate_repo: AsyncMock,
) -> ExportService:
    monkeypatch.setattr(
        export_service_module, "SatelliteRepository", lambda session: mock_satellite_repo
    )
    monkeypatch.setattr(
        export_service_module, "CoordinateRepository", lambda redis_client: mock_coordinate_repo
    )
    return ExportService(mock_db_session, mock_redis_client)


async def test_get_coordinates_success(
    service: ExportService,
    mock_satellite_repo: AsyncMock,
    mock_coordinate_repo: AsyncMock,
) -> None:
    # Arrange
    mock_satellite_repo.get_by_norad_id.return_value = SimpleNamespace(norad_id=FAKE_NORAD_ID)
    params = ExportQueryParams(
        norad_id=FAKE_NORAD_ID, start=START, stop=STOP, format=ExportFormat.CSV
    )

    # Act
    result = await service.get_coordinates(params)

    # Assert
    mock_satellite_repo.get_by_norad_id.assert_awaited_once_with(FAKE_NORAD_ID)
    mock_coordinate_repo.get_range.assert_awaited_once_with(FAKE_NORAD_ID, START, STOP)
    assert result == ExportResult(norad_id=FAKE_NORAD_ID, points=POINTS)


async def test_get_coordinates_not_found(
    service: ExportService,
    mock_satellite_repo: AsyncMock,
    mock_coordinate_repo: AsyncMock,
) -> None:
    # Arrange
    mock_satellite_repo.get_by_norad_id.return_value = None
    params = ExportQueryParams(
        norad_id=FAKE_NORAD_ID, start=START, stop=STOP, format=ExportFormat.CSV
    )

    # Act + Assert
    with pytest.raises(SatelliteNotFoundError):
        await service.get_coordinates(params)

    # Assert: до чтения координат из Redis не дошло.
    mock_coordinate_repo.get_range.assert_not_awaited()


def test_to_csv_round_trip(mock_db_session: AsyncMock, mock_redis_client: AsyncMock) -> None:
    # Arrange
    service = ExportService(mock_db_session, mock_redis_client)

    # Act
    csv_bytes = service.to_csv(POINTS)

    # Assert
    assert isinstance(csv_bytes, bytes)

    df = pl.read_csv(io.BytesIO(csv_bytes), try_parse_dates=True)
    assert df.height == len(POINTS)
    for row, expected in zip(df.iter_rows(named=True), POINTS, strict=True):
        assert row["latitude_deg"] == pytest.approx(expected.latitude_deg)
        assert row["longitude_deg"] == pytest.approx(expected.longitude_deg)
        assert row["altitude_km"] == pytest.approx(expected.altitude_km)


def test_to_parquet_round_trip(mock_db_session: AsyncMock, mock_redis_client: AsyncMock) -> None:
    # Arrange
    service = ExportService(mock_db_session, mock_redis_client)

    # Act
    parquet_bytes = service.to_parquet(POINTS)

    # Assert
    assert isinstance(parquet_bytes, bytes)

    df = pl.read_parquet(io.BytesIO(parquet_bytes))
    assert df.height == len(POINTS)
    for row, expected in zip(df.iter_rows(named=True), POINTS, strict=True):
        # Parquet -- бинарный формат, float64 сохраняется точно -- прямое
        # равенство здесь осмысленно, в отличие от CSV.
        assert row["latitude_deg"] == expected.latitude_deg
        assert row["longitude_deg"] == expected.longitude_deg
        assert row["altitude_km"] == expected.altitude_km
