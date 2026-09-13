#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

docker compose up --build --detach --wait
echo "Services are working. Logs of pinger:"
exec docker compose logs --follow pinger
