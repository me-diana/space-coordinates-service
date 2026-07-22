# ---- base: общие для dev/prod шаги
FROM python:3.12-slim AS base

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

# ---- dev:
FROM base AS dev

RUN poetry install --no-root

COPY . .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh", "--reload"]

# ---- prod:
FROM base AS prod

RUN poetry install --no-root --only main

COPY . .
RUN chmod +x entrypoint.sh

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["./entrypoint.sh"]
