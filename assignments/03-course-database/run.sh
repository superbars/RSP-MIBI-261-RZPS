#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Создан .env из .env.example"
fi

docker compose up --build --detach --wait db
docker compose build app

echo "Введите APP_DB_USER и APP_DB_PASSWORD из .env"
# remove container when exit
exec docker compose run --rm app

