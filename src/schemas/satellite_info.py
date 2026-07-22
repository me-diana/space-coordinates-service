"""
Pydantic-схемы входных орбитальных данных: TLE или JSON с параметрами
орбиты
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sgp4.io import verify_checksum

from computation.contracts import OrbitalElements, TleData


class OrbitFormat(str, Enum):
    TLE = "tle"
    ORBITAL_ELEMENTS = "orbital_elements"


@dataclass(frozen=True, slots=True)
class SatelliteMetadata:
    """Метаданные КА для сохранения в PostgreSQL"""

    name: str | None
    norad_id: int
    international_designator: str | None
    classification: str | None


def _international_designator_from_object_id(object_id: str | None) -> str | None:
    """Приводит COSPAR ID из формата (`"1998-067UQ"`) к TLE-формату (`"98067UQ"`)"""
    if object_id is None:
        return None
    return object_id[2:].replace("-", "")


class TlePayload(BaseModel):
    line1: str = Field(..., min_length=69, max_length=69)
    line2: str = Field(..., min_length=69, max_length=69)
    satellite_name: str | None = None

    @field_validator("line1", "line2")
    @classmethod
    def _validate_tle_line(cls, value: str) -> str:
        try:
            verify_checksum(value)
        except ValueError as exc:
            raise ValueError("Invalid TLE checksum") from exc
        return value


class TleInput(BaseModel):
    format: Literal[OrbitFormat.TLE]
    data: TlePayload

    def to_computation_orbit(self) -> TleData:
        return TleData(
            line1=self.data.line1,
            line2=self.data.line2,
        )

    def to_satellite_metadata(self) -> SatelliteMetadata:
        # Данные из фиксированного формата TLE
        return SatelliteMetadata(
            name=self.data.satellite_name,
            norad_id=int(self.data.line1[2:7]),
            international_designator=self.data.line1[9:17].rstrip() or None,
            classification=self.data.line1[7] or "U",
        )


class OrbitalElementsPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    epoch: datetime = Field(..., alias="EPOCH")
    inclination_deg: float = Field(..., ge=0, le=180, alias="INCLINATION")
    raan_deg: float = Field(..., ge=0, lt=360, alias="RA_OF_ASC_NODE")
    eccentricity: float = Field(..., ge=0, lt=1, alias="ECCENTRICITY")
    arg_perigee_deg: float = Field(..., ge=0, lt=360, alias="ARG_OF_PERICENTER")
    mean_anomaly_deg: float = Field(..., ge=0, lt=360, alias="MEAN_ANOMALY")
    mean_motion_rev_per_day: float = Field(..., gt=0, alias="MEAN_MOTION")
    bstar: float = Field(0.0, alias="BSTAR")
    mean_motion_dot: float = Field(0.0, alias="MEAN_MOTION_DOT")
    mean_motion_ddot: float = Field(0.0, alias="MEAN_MOTION_DDOT")
    satellite_name: str | None = Field(None, alias="OBJECT_NAME")
    norad_cat_id: int = Field(..., alias="NORAD_CAT_ID")
    object_id: str | None = Field(None, alias="OBJECT_ID")
    classification_type: str | None = Field(None, alias="CLASSIFICATION_TYPE")


class OrbitalElementsInput(BaseModel):
    format: Literal[OrbitFormat.ORBITAL_ELEMENTS]
    data: OrbitalElementsPayload

    def to_computation_orbit(self) -> OrbitalElements:
        return OrbitalElements(
            epoch=self.data.epoch,
            inclination_deg=self.data.inclination_deg,
            raan_deg=self.data.raan_deg,
            eccentricity=self.data.eccentricity,
            arg_perigee_deg=self.data.arg_perigee_deg,
            mean_anomaly_deg=self.data.mean_anomaly_deg,
            mean_motion_rev_per_day=self.data.mean_motion_rev_per_day,
            bstar=self.data.bstar,
            mean_motion_dot=self.data.mean_motion_dot,
            mean_motion_ddot=self.data.mean_motion_ddot,
            norad_id=self.data.norad_cat_id,
        )

    def to_satellite_metadata(self) -> SatelliteMetadata:
        return SatelliteMetadata(
            name=self.data.satellite_name,
            norad_id=self.data.norad_cat_id,
            international_designator=_international_designator_from_object_id(self.data.object_id),
            classification=self.data.classification_type,
        )


SatelliteInput = Annotated[
    TleInput | OrbitalElementsInput,
    Field(discriminator="format"),
]
