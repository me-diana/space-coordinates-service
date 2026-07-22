from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from models.satellite import Satellite

pytestmark = pytest.mark.integration

LINE1 = "1 69677U 26145A   26202.59920150 -.00220234  00000+0 -22387-2 0  9994"
LINE2 = "2 69677  97.2844  49.7323 0000685  66.9134 293.2198 15.65787759  4184"

ORBITAL_ELEMENTS_DATA = {
    "OBJECT_NAME": "STARLINK-38005",
    "OBJECT_ID": "2026-145A",
    "EPOCH": "2026-07-21T14:22:51.009600",
    "MEAN_MOTION": 15.65787759,
    "ECCENTRICITY": 6.852e-5,
    "INCLINATION": 97.2844,
    "RA_OF_ASC_NODE": 49.7323,
    "ARG_OF_PERICENTER": 66.9134,
    "MEAN_ANOMALY": 293.2198,
    "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U",
    "NORAD_CAT_ID": 69677,
    "ELEMENT_SET_NO": 999,
    "REV_AT_EPOCH": 418,
    "BSTAR": -0.0022386932,
    "MEAN_MOTION_DOT": -0.00220234,
    "MEAN_MOTION_DDOT": 0,
}

START = datetime(2026, 7, 21, 14, 22, 51, 9600, tzinfo=UTC)
STOP = START + timedelta(minutes=30)

NORAD_ID = 69677

# Широта/долгота/высота на START/STOP - посчитаны один раз реальным вызовом
# Sgp4CoordinateCalculator.propagate() на приведённых выше данных, дальше
# используются как эталон для обоих сценариев
# Результаты tle и json будут немного отличаться из-за разного формата
# некоторых параметров. Для этого есть tolerance
EXPECTED_COORDINATES = [
    (0.0, -105.3468, 373.95),
    (61.7291, 80.8259, 381.31),
]
TOLERANCE_DEG = 1e-3
TOLERANCE_KM = 0.1


async def _assert_stored(test_db_pool: AsyncEngine, test_redis_client: Redis) -> None:
    # Assert - запись в PostgreSQL
    async with AsyncSession(test_db_pool) as session:
        result = await session.execute(select(Satellite).where(Satellite.norad_id == NORAD_ID))
        satellite = result.scalar_one()
    assert satellite.name == "STARLINK-38005"
    assert satellite.international_designator == "26145A"
    assert satellite.classification == "U"

    # Assert - координаты в Redis, сырой ZRANGEBYSCORE
    raw_points = await test_redis_client.zrangebyscore(
        f"coords:{NORAD_ID}", START.timestamp(), STOP.timestamp()
    )
    assert len(raw_points) == 2

    decoded_points = [json.loads(raw) for raw in raw_points]
    decoded_timestamps = {point["ts"] for point in decoded_points}
    assert decoded_timestamps == {START.isoformat(), STOP.isoformat()}

    for point, (expected_lat, expected_lon, expected_alt) in zip(
        decoded_points, EXPECTED_COORDINATES, strict=True
    ):
        assert point["lat"] == pytest.approx(expected_lat, abs=TOLERANCE_DEG)
        assert point["lon"] == pytest.approx(expected_lon, abs=TOLERANCE_DEG)
        assert point["alt"] == pytest.approx(expected_alt, abs=TOLERANCE_KM)


@pytest.mark.asyncio(loop_scope="session")
async def test_calculate_coordinates_success_tle(
    client: TestClient, test_db_pool: AsyncEngine, test_redis_client: Redis
) -> None:
    # Act
    response = client.post(
        "/v1/calculate_coordinates",
        json={
            "satellite": {
                "format": "tle",
                "data": {"line1": LINE1, "line2": LINE2, "satellite_name": "STARLINK-38005"},
            },
            "start": START.isoformat(),
            "stop": STOP.isoformat(),
            "step_seconds": 1800,
        },
    )

    # Assert HTTP-ответ
    assert response.status_code == 200
    body = response.json()
    assert body["norad_id"] == NORAD_ID
    assert body["points_calculated"] == 2

    await _assert_stored(test_db_pool, test_redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_calculate_coordinates_success_orbital_elements(
    client: TestClient, test_db_pool: AsyncEngine, test_redis_client: Redis
) -> None:
    # Act
    response = client.post(
        "/v1/calculate_coordinates",
        json={
            "satellite": {"format": "orbital_elements", "data": ORBITAL_ELEMENTS_DATA},
            "start": START.isoformat(),
            "stop": STOP.isoformat(),
            "step_seconds": 1800,
        },
    )

    # Assert HTTP-ответ
    assert response.status_code == 200
    body = response.json()
    assert body["norad_id"] == NORAD_ID
    assert body["points_calculated"] == 2

    await _assert_stored(test_db_pool, test_redis_client)
