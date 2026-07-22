"""
Pydantic-схемы запроса/ответа выгрузки координат.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ExportFormat(str, Enum):
    CSV = "csv"
    PARQUET = "parquet"


class ExportQueryParams(BaseModel):
    norad_id: int
    start: datetime
    stop: datetime
    format: ExportFormat
