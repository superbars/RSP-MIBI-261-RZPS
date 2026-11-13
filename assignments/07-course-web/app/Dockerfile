FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY config.toml app.py ./
COPY templates ./templates
COPY static ./static

EXPOSE 8080

CMD ["python", "app.py"]
