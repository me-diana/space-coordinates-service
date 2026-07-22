"""
Работа с БД Redis
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime

from redis.asyncio import Redis

from computation.contracts import GroundTrackPoint
from core.config import get_settings

redis_client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_redis_client() -> Redis:
    return redis_client


class CoordinateRepository:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def save_batch(
        self,
        norad_id: int,
        start: datetime,
        stop: datetime,
        points: Sequence[GroundTrackPoint],
    ) -> None:
        """
        Сохранение данных в redis
        Заменяет диапазон [start, stop] свежими расчетами, а не добавляет к нему
        """
        key = self._key(norad_id)
        start_score = self._epoch_seconds(start)
        stop_score = self._epoch_seconds(stop)

        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, start_score, stop_score)
            if points:
                mapping = {
                    self._encode_point(point): self._epoch_seconds(point.timestamp)
                    for point in points
                }
                pipe.zadd(key, mapping)
            await pipe.execute()

    async def get_range(
        self, norad_id: int, start: datetime, stop: datetime
    ) -> list[GroundTrackPoint]:
        key = self._key(norad_id)
        raw_points = await self._client.zrangebyscore(
            key, self._epoch_seconds(start), self._epoch_seconds(stop)
        )
        return [self._decode_point(raw) for raw in raw_points]

    @staticmethod
    def _key(norad_id: int) -> str:
        return f"coords:{norad_id}"

    @staticmethod
    def _epoch_seconds(moment: datetime) -> float:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment.timestamp()

    @staticmethod
    def _encode_point(point: GroundTrackPoint) -> str:
        return json.dumps(
            {
                "ts": point.timestamp.isoformat(),
                "lat": point.latitude_deg,
                "lon": point.longitude_deg,
                "alt": point.altitude_km,
            }
        )

    @staticmethod
    def _decode_point(raw: str) -> GroundTrackPoint:
        data = json.loads(raw)
        return GroundTrackPoint(
            timestamp=datetime.fromisoformat(data["ts"]),
            latitude_deg=data["lat"],
            longitude_deg=data["lon"],
            altitude_km=data["alt"],
        )
