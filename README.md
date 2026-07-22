# Cервис расчёта координат космических аппаратов

Прототип сервиса, рассчитывающего координаты космических аппаратов (широта,
долгота, высота, WGS84) по орбитальным данным (TLE или JSON с параметрами
орбиты) на заданном временном интервале, и отдающего рассчитанные координаты
на выгрузку.

## Запуск

Перед первым запуском скопировать `.env.example` в `.env` и заполнить
значения (для тестов уже есть отдельный `.env.test`, ничего копировать не
нужно).

- **`make up`** - Запуск в prod режиме.
- **`make dev-up`** - Запуск в dev режиме.
- **`make down`** / **`make dev-down`** - остановить соответствующее окружение.
- **`make test`** - интеграционные тесты в изолированном окружении.

После `make up`/`make dev-up` сервис доступен на `http://localhost:${APP_PORT}`
(по умолчанию 8000), Swagger UI на `/docs`.

### Без make

Если `make` не установлен, запуск напрямую через `docker compose`.

Prod:

```bash
docker compose -f docker-compose.yml build --no-cache
docker compose -f docker-compose.yml up -d --remove-orphans
```

Dev:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --remove-orphans
```

## Архитектура

### Модульный монолит с границей через Protocol

Сейчас всё работает в одном процессе, но вычислительная часть (`computation/`
- расчёт координат) отделена от HTTP-слоя (`api/`) чёткой границей:
`api/` обращается к расчёту только через интерфейс `CoordinateCalculator`
(`Protocol` в `computation/contracts.py`), не через его внутренние классы.
Если нагрузка на расчёты вырастет и их понадобится масштабировать отдельно
от остального приложения, `computation/` можно вынести в отдельный сервис и
ходить к нему по gRPC. В этом случае, поменять придётся только реализацию 
интерфейса, а код `api/` и всё остальное приложение не тронутся. Заводить два 
сервиса сразу, без реальной нагрузки это лишняя сложность, поэтому сейчас один
процесс, но с границей, уже готовой к разделению.

### Хранение координат в Redis

Временной ряд координат на один КА хранится как Sorted Set (ключ
`coords:{norad_id}`, score - unix-timestamp точки). Такая структура даёт
поддержку запросов по диапазонам времени через `ZRANGEBYSCORE`. А это
как раз то, что нужно для выгрузки координат за период.

Пример: для КА с NORAD ID 69677, если посчитаны координаты на 14:22:51 и
14:52:51 UTC 21.07.2026, ключ `coords:69677` содержит:

| score (timestamp) | member |
| --- | --- |
| `1784643771.0096` | `{"ts": "2026-07-21T14:22:51.009600+00:00", "lat": -2.6057912560236552e-05, "lon": -105.34681833682214, "alt": 373.9475131664141}` |
| `1784645571.0096` | `{"ts": "2026-07-21T14:52:51.009600+00:00", "lat": 61.72905876232677, "lon": 80.82586042165502, "alt": 381.30752764399114}` |

### NumPy / Polars

NumPy - векторизация самого SGP4-расчёта и перевода ECI → WGS84 (все
точки интервала пакетно, за один вызов, а не циклом).
Polars - сборка таблицы выгрузки (CSV/Parquet): быстрее и без промежуточного
Python-объекта на каждую строку по сравнению с ручной сборкой через
`csv`/pandas на больших объёмах точек.

### Известное ограничение: блокировка event loop

`POST /v1/calculate_coordinates` выполняет SGP4-расчёт синхронно, внутри
обработки запроса `propagate()` на время расчёта блокирует event loop 
FastAPI целиком. Пока считается один запрос с большим интервалом, 
сервер не может параллельно обработать другие. Пути улучшение:
вынести вызов `propagate()` в отдельный поток через
`asyncio.run_in_executor()` или полноценная очередь задач на расчет
с отдельным воркер-сервисом.

## Экспорт

### Один эндпоинт, обязательный `format`

`GET /v1/export` выгружает координаты в CSV или Parquet через обязательный
параметр `format` (без значения по умолчанию), JSON как формат выгрузки не
поддерживается. `POST /v1/calculate_coordinates` сами координаты не
возвращает, только подтверждение расчёта, координаты читаются отдельно
через `/export`.

### Формат выгрузки

CSV/Parquet с колонками `timestamp`, `latitude_deg`, `longitude_deg`,
`altitude_km`. Одна строка на точку временного ряда.

## Примеры API-запросов

Данные взяты с Celestrak.

### `POST /v1/calculate_coordinates` - запуск расчёта, на вход TLE

```bash
curl -X POST http://localhost:8000/v1/calculate_coordinates \
  -H "Content-Type: application/json" \
  -d '{
    "satellite": {
      "format": "tle",
      "data": {
        "line1": "1 69677U 26145A   26202.59920150 -.00220234  00000+0 -22387-2 0  9994",
        "line2": "2 69677  97.2844  49.7323 0000685  66.9134 293.2198 15.65787759  4184",
        "satellite_name": "STARLINK-38005"
      }
    },
    "start": "2026-07-21T14:22:51.009600Z",
    "stop": "2026-07-21T14:52:51.009600Z",
    "step_seconds": 1800
  }'
```

Ответ:

```json
{"norad_id": 69677, "points_calculated": 2, "start": "2026-07-21T14:22:51.009600Z", "stop": "2026-07-21T14:52:51.009600Z"}
```

### `POST /v1/calculate_coordinates` - тот же КА, на вход JSON (`orbital_elements`)

Тот же объект, но параметры орбиты переданы явными полями вместо TLE.
JSON взят так же из Celestrak.

```bash
curl -X POST http://localhost:8000/v1/calculate_coordinates \
  -H "Content-Type: application/json" \
  -d '{
    "satellite": {
      "format": "orbital_elements",
      "data": {
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
        "MEAN_MOTION_DDOT": 0
      }
    },
    "start": "2026-07-21T14:22:51.009600Z",
    "stop": "2026-07-21T14:52:51.009600Z",
    "step_seconds": 1800
  }'
```

### `GET /v1/export?format=csv` - выгрузка CSV

```bash
curl -G http://localhost:8000/v1/export \
  -d norad_id=69677 \
  -d start=2026-07-21T14:22:51.009600Z \
  -d stop=2026-07-21T14:52:51.009600Z \
  -d format=csv \
  -o export_69677.csv
```

### `GET /v1/export?format=parquet` - выгрузка Parquet

```bash
curl -G http://localhost:8000/v1/export \
  -d norad_id=69677 \
  -d start=2026-07-21T14:22:51.009600Z \
  -d stop=2026-07-21T14:52:51.009600Z \
  -d format=parquet \
  -o export_69677.parquet
```
