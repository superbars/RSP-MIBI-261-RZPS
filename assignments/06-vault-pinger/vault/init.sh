#!/bin/sh
set -eu

export VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_TOKEN="${VAULT_DEV_ROOT_TOKEN:?VAULT_DEV_ROOT_TOKEN is required}"

: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"

echo "Configuring Vault for pinger..."

# Enable approle (because it's turned off by default)
vault auth enable approle >/dev/null 2>&1 || true

# we read from pinger-policy.hcl
vault policy write pinger-read /vault/config/pinger-policy.hcl >/dev/null


# vault kv put secret/data/pinger/database  (doesn't work because of v2 api specification)
# DB USER and pass are from .env 
vault kv put secret/pinger/database \
    username="$DB_USER" \
    password="$DB_PASSWORD" >/dev/null

# create approle with name pinger
# batch is just recommended because for optimization
# ttl is min time for token to be alive and max ttl are obvious 
# after expired secretid app will require a new one for auth
vault write auth/approle/role/pinger \
    token_policies="pinger-read" \
    token_type="batch" \
    token_ttl="5m" \
    token_max_ttl="15m" \
    secret_id_ttl="24h" >/dev/null

# get role id and secret id
role_id="$(vault read -field=role_id auth/approle/role/pinger/role-id)"

secret_id="$(vault write -force -field=secret_id auth/approle/role/pinger/secret-id)"

# we write secret id and role id in specified file
umask 077
credentials_tmp=/vault/credentials/approle.env.tmp
credentials_file=/vault/credentials/approle.env

{
    printf 'VAULT_ROLE_ID=%s\n' "$role_id"
    printf 'VAULT_SECRET_ID=%s\n' "$secret_id"
} > "$credentials_tmp"

# some troubles with parsing data in vault of first time, so temporary create cred file and then rename for vault format
mv "$credentials_tmp" "$credentials_file"
# only for container user
chown 10001:10001 "$credentials_file"
chmod 0400 "$credentials_file"
echo "Vault is configured: AppRole=pinger, policy=pinger-read, secret=secret/pinger/database"
