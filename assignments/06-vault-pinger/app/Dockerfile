FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY config.toml entrypoint.sh main.py ./

RUN useradd --create-home --uid 10001 pinger \
    && mkdir /logs \
    && chown pinger:pinger /logs \
    && chmod 0555 /app/entrypoint.sh

USER pinger

ENTRYPOINT ["/app/entrypoint.sh"]
