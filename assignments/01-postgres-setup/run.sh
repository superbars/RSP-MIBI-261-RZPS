#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "Ошибка: Docker не найден." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Ошибка: команда 'docker compose' недоступна." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Ошибка: Python 3 не найден." >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Создан локальный файл .env из .env.example."
    echo "Перед публикацией .env останется локальным благодаря .gitignore."
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "Создание виртуального окружения Python..."
    python3 -m venv "$VENV_DIR"
fi

echo "Установка зависимостей приложения..."
"$VENV_DIR/bin/python" -m pip install --quiet --requirement app/requirements.txt

echo "Сборка и запуск PostgreSQL..."
docker compose up --build --detach --wait

echo
echo "PostgreSQL готов."
echo "Введите значения APP_DB_USER и APP_DB_PASSWORD из локального .env."
echo

exec "$VENV_DIR/bin/python" app/main.py
