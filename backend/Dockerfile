FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system horeca \
    && useradd --system --gid horeca --home-dir /app horeca

COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations

RUN python -m pip install --no-cache-dir .

USER horeca

CMD ["python", "-m", "app.api_server"]
