#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
    echo "Run ./run.sh first" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

mode="${1:-}"
case "$mode" in
    correct)
        password="$DB_PASSWORD"
        ;;
    wrong)
        password="wrong-demo-password"
        ;;
    *)
        echo "Usage: $0 correct|wrong" >&2
        exit 2
        ;;
esac

docker compose exec \
    -e VAULT_ADDR=http://127.0.0.1:8200 \
    -e VAULT_TOKEN="$VAULT_DEV_ROOT_TOKEN" \
    vault vault kv put secret/pinger/database \
    username="$DB_USER" \
    password="$password" >/dev/null

echo "Stored the $mode database password in Vault."
echo "The pinger reads it again before the next database request."
docker compose logs --follow --since=5s pinger
