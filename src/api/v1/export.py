from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from schemas.export import ExportFormat, ExportQueryParams

from .dependencies import ExportServiceDepend

router = APIRouter(tags=["export"])


@router.get("/export")
async def export_coordinates(
    params: Annotated[ExportQueryParams, Query()],
    service: ExportServiceDepend,
) -> StreamingResponse:
    result = await service.get_coordinates(params)

    filename_stem = f"export_{result.norad_id}"

    if params.format is ExportFormat.CSV:
        data = service.to_csv(result.points)
        media_type = "text/csv"
        filename = f"{filename_stem}.csv"
    else:
        data = service.to_parquet(result.points)
        media_type = "application/octet-stream"
        filename = f"{filename_stem}.parquet"

    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
