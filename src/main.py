from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.v1.calculate_coordinates import router as coordinates_router
from api.v1.export import router as export_router
from computation.contracts import OrbitDataError, PropagationError
from computation.sgp4_calculator import Sgp4CoordinateCalculator
from core.logging import configure_logging
from db.postgres import engine
from db.redis import redis_client
from services.export_service import SatelliteNotFoundError

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.calculator = Sgp4CoordinateCalculator()
    yield
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title="Space Coordinates Service",
    lifespan=lifespan
)
app.include_router(coordinates_router, prefix="/v1")
app.include_router(export_router, prefix="/v1")


_EXCEPTION_STATUS_MAP: dict[type[Exception], int] = {
    # Синтаксически верные TLE/JSON, но данные некорректные
    OrbitDataError: 422,
    # Прошли Pydantic-валидацию, но SGP4 не может их вычислить
    PropagationError: 422,
    # КА не найден
    SatelliteNotFoundError: 404,
}


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=_EXCEPTION_STATUS_MAP[type(exc)],
        content={"detail": str(exc)},
    )


for _exc_type in _EXCEPTION_STATUS_MAP:
    app.add_exception_handler(_exc_type, _domain_error_handler)
