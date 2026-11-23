FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY booking_bot ./booking_bot
RUN pip install . && useradd --create-home --uid 1000 bot && mkdir -p /app/data && chown bot /app/data

USER bot
# /app is owned by root; the database must live in the writable data directory (mount a volume there)
ENV DATABASE_PATH=/app/data/bookings.db CONFIG_PATH=/app/config.toml
VOLUME /app/data
CMD ["python", "-m", "booking_bot"]
