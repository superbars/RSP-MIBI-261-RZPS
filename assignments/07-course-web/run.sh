#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Создан .env из .env.example"
fi

docker compose up --build --detach --wait

set -a
# shellcheck disable=SC1091
source ./.env
set +a

