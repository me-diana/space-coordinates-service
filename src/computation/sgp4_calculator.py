"""
Модуль расчета координат
"""

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pymap3d as pm
from sgp4.api import WGS72, Satrec, jday

from .contracts import (
    GroundTrackPoint,
    OrbitalElements,
    OrbitDataError,
    OrbitDefinition,
    PropagationError,
    TleData,
)

# Опорная эпоха sgp4init (31.12.1949)
_SGP4INIT_EPOCH = datetime(1949, 12, 31, tzinfo=UTC)

_SECONDS_PER_DAY = 86400.0

# Константы и формула из sgp4/omm.py
_NDOT_UNITS = 1036800.0 / math.pi
_NDDOT_UNITS = 2985984000.0 / 2.0 / math.pi


class Sgp4CoordinateCalculator:
    async def propagate(
        self,
        orbit: OrbitDefinition,
        start: datetime,
        stop: datetime,
        step_seconds: float,
    ) -> list[GroundTrackPoint]:
        """
        Raises:
            OrbitDataError: TLE или JSON-параметры орбиты некорректны.
            PropagationError: SGP4 не смог рассчитать позицию хотя бы в одной
                точке интервала.
        """
        satellite = _build_satrec(orbit)
        times = _build_timestamps(start, stop, step_seconds)
        jd, fr = _build_julian_dates(start, times)

        error_codes, positions_km, _velocities_km_s = satellite.sgp4_array(jd, fr)
        _check_propagation_errors(error_codes, times)

        # SGP4 отдаёт позицию в TEME в километрах, pymap3d ждёт метры.
        positions_m = positions_km * 1000.0
        x_m, y_m, z_m = positions_m[:, 0], positions_m[:, 1], positions_m[:, 2]


        lat_deg, lon_deg, alt_m = pm.eci2geodetic(x_m, y_m, z_m, times)

        # На единственной точке (start == stop) eci2geodetic возвращает скаляр,
        # не массив длины 1. Без  zip() ниже падает с TypeError.
        lat_deg, lon_deg, alt_m = np.atleast_1d(lat_deg, lon_deg, alt_m)

        return [
            GroundTrackPoint(
                timestamp=t,
                latitude_deg=float(lat),
                longitude_deg=float(lon),
                altitude_km=float(alt) / 1000.0,
            )
            for t, lat, lon, alt in zip(times, lat_deg, lon_deg, alt_m, strict=True)
        ]


def _build_timestamps(start: datetime, stop: datetime, step_seconds: float) -> list[datetime]:
    n = math.floor((stop - start).total_seconds() / step_seconds) + 1
    elapsed_seconds = np.arange(n) * step_seconds
    return [start + timedelta(seconds=float(s)) for s in elapsed_seconds]


def _build_julian_dates(start: datetime, times: list[datetime]) -> tuple[np.ndarray, np.ndarray]:
    """Разбиение интервала на точки"""

    jd0, fr0 = jday(
        start.year,
        start.month,
        start.day,
        start.hour,
        start.minute,
        start.second + start.microsecond / 1e6,
    )
    elapsed_seconds = np.array(
        [(t - start).total_seconds() for t in times],
        dtype=np.float64,
    )
    elapsed_days, remainder_seconds = np.divmod(elapsed_seconds, _SECONDS_PER_DAY)
    jd = jd0 + elapsed_days
    fr = fr0 + remainder_seconds / _SECONDS_PER_DAY
    return jd, fr


def _check_propagation_errors(error_codes: np.ndarray, times: list[datetime]) -> None:
    bad_indices = np.nonzero(error_codes)[0]
    if bad_indices.size == 0:
        return
    first_bad = int(bad_indices[0])
    code = int(error_codes[first_bad])
    raise PropagationError(
        f"SGP4 propagation failed with error code {code} at {times[first_bad].isoformat()} "
        f"(and at {bad_indices.size - 1} other point(s) in the interval)"
    )


def _build_satrec(orbit: OrbitDefinition) -> Satrec:
    if isinstance(orbit, TleData):
        return _build_satrec_from_tle(orbit)
    if isinstance(orbit, OrbitalElements):
        return _build_satrec_from_elements(orbit)
    raise OrbitDataError(f"Unsupported orbit definition type: {type(orbit)!r}")


def _build_satrec_from_tle(orbit: TleData) -> Satrec:
    try:
        return Satrec.twoline2rv(orbit.line1, orbit.line2, WGS72)
    except ValueError as exc:
        raise OrbitDataError(str(exc)) from exc


def _build_satrec_from_elements(orbit: OrbitalElements) -> Satrec:
    epoch = orbit.epoch if orbit.epoch.tzinfo is not None else orbit.epoch.replace(tzinfo=UTC)
    epoch_arg = (epoch - _SGP4INIT_EPOCH).total_seconds() / _SECONDS_PER_DAY

    # формулы из sgp4/omm.py
    no_kozai = orbit.mean_motion_rev_per_day / 720.0 * math.pi
    ndot = orbit.mean_motion_dot / _NDOT_UNITS
    nddot = orbit.mean_motion_ddot / _NDDOT_UNITS

    satellite = Satrec()
    satellite.sgp4init(
        WGS72,
        "i",
        orbit.norad_id,
        epoch_arg,
        orbit.bstar,
        ndot,
        nddot,
        orbit.eccentricity,
        math.radians(orbit.arg_perigee_deg),
        math.radians(orbit.inclination_deg),
        math.radians(orbit.mean_anomaly_deg),
        no_kozai,
        math.radians(orbit.raan_deg),
    )
    return satellite
