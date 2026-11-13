#!/bin/sh
set -eu

: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=app_user="$DB_USER" \
    --set=app_password="$DB_PASSWORD" \
    --set=db_name="$POSTGRES_DB" <<'SQL'
SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'app_user',
    :'app_password'
) \gexec

GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";
SQL
