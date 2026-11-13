#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

# Re-run one-shot initialization so a recreated dev Vault gets a fresh AppRole.
docker compose rm --stop --force vault-init pinger >/dev/null 2>&1 || true
docker compose up --build --detach --wait

echo "Services are running. Pinger logs:"
exec docker compose logs --follow pinger
