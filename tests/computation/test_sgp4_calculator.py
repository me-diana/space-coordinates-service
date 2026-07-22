from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from computation.contracts import OrbitalElements, PropagationError, TleData
from computation.sgp4_calculator import Sgp4CoordinateCalculator

# STARLINK-38005 - реальные данные с Celestrak
STARLINK_EXPECTED_LAT_LON_ALT = [
    (-0.0000, -105.3468, 373.95),
    (61.7291, 80.8259, 381.31),
    (-54.4414, 49.4124, 392.69),
    (-7.9216, -126.8303, 375.46),
    (69.2643, 64.2758, 382.74),
    (-46.6856, 29.4101, 389.70),
]

STARLINK_LINE1 = "1 69677U 26145A   26202.59920150 -.00220234  00000+0 -22387-2 0  9994"
STARLINK_LINE2 = "2 69677  97.2844  49.7323 0000685  66.9134 293.2198 15.65787759  4184"
STARLINK_EPOCH = datetime(2026, 7, 21, 14, 22, 51, 9600, tzinfo=UTC)
STARLINK_ORBITAL_ELEMENTS = OrbitalElements(
    epoch=STARLINK_EPOCH,
    inclination_deg=97.2844,
    raan_deg=49.7323,
    eccentricity=6.852e-5,
    arg_perigee_deg=66.9134,
    mean_anomaly_deg=293.2198,
    mean_motion_rev_per_day=15.65787759,
    bstar=-0.0022386932,
    mean_motion_dot=-0.00220234,
    mean_motion_ddot=0.0,
    norad_id=69677,
)


@pytest.fixture
def calculator() -> Sgp4CoordinateCalculator:
    return Sgp4CoordinateCalculator()


async def test_propagate_tle_matches_known_alues(
    calculator: Sgp4CoordinateCalculator,
) -> None:
    """
    Значения посчитаны один раз запуском кода и сохранены как эталонные
    """
    # Arrange
    step = timedelta(minutes=30)
    n_points = len(STARLINK_EXPECTED_LAT_LON_ALT)
    tolerance_deg = 1e-3
    tolerance_km = 0.1

    # Act
    points = await calculator.propagate(
        TleData(line1=STARLINK_LINE1, line2=STARLINK_LINE2),
        start=STARLINK_EPOCH,
        stop=STARLINK_EPOCH + step * (n_points - 1),
        step_seconds=step.total_seconds(),
    )

    # Assert
    assert len(points) == n_points
    for i, (point, (expected_lat, expected_lon, expected_alt_km)) in enumerate(
        zip(points, STARLINK_EXPECTED_LAT_LON_ALT, strict=True)
    ):
        assert point.timestamp == STARLINK_EPOCH + step * i
        assert point.latitude_deg == pytest.approx(expected_lat, abs=tolerance_deg)
        assert point.longitude_deg == pytest.approx(expected_lon, abs=tolerance_deg)
        assert point.altitude_km == pytest.approx(expected_alt_km, abs=tolerance_km)


async def test_tle_and_orbital_elements_give_identical_result(
    calculator: Sgp4CoordinateCalculator,
) -> None:
    """TLE и JSON с одинаковыми орбитальными данными должны давать
    практически один и тот же результат
    """
    # Arrange
    start = STARLINK_EPOCH
    stop = STARLINK_EPOCH + timedelta(minutes=20)
    step_seconds = 600.0
    tolerance_deg = 1e-3
    tolerance_km = 0.1

    # Act
    tle_points = await calculator.propagate(
        TleData(line1=STARLINK_LINE1, line2=STARLINK_LINE2), start, stop, step_seconds
    )
    elements_points = await calculator.propagate(
        STARLINK_ORBITAL_ELEMENTS, start, stop, step_seconds
    )

    # Assert
    assert len(tle_points) == len(elements_points) == 3
    for tle_point, elements_point in zip(tle_points, elements_points, strict=True):
        assert tle_point.timestamp == elements_point.timestamp
        assert tle_point.latitude_deg == pytest.approx(
            elements_point.latitude_deg, abs=tolerance_deg
        )
        assert tle_point.longitude_deg == pytest.approx(
            elements_point.longitude_deg, abs=tolerance_deg
        )
        assert tle_point.altitude_km == pytest.approx(elements_point.altitude_km, abs=tolerance_km)


async def test_propagate_start_equals_stop_returns_single_point(
    calculator: Sgp4CoordinateCalculator,
) -> None:
    """tart == stop дает ровно одну точку"""
    # Act
    points = await calculator.propagate(
        STARLINK_ORBITAL_ELEMENTS, start=STARLINK_EPOCH, stop=STARLINK_EPOCH, step_seconds=60.0
    )

    # Assert
    assert len(points) == 1
    assert points[0].timestamp == STARLINK_EPOCH


async def test_propagate_degenerate_eccentricity_raises_propagation_error(
    calculator: Sgp4CoordinateCalculator,
) -> None:
    """
    Физически невозможная орбита
    """
    # Arrange
    degenerate_orbit = replace(STARLINK_ORBITAL_ELEMENTS, eccentricity=0.9999)

    with pytest.raises(PropagationError):
        await calculator.propagate(
            degenerate_orbit,
            start=STARLINK_EPOCH,
            stop=STARLINK_EPOCH + timedelta(minutes=20),
            step_seconds=600.0,
        )
