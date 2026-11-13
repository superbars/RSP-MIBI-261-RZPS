#!/bin/sh
set -eu

# file with secret id and role id, chechk can we read it
credentials_file=/vault-credentials/approle.env

if [ ! -r "$credentials_file" ]; then
    echo "Vault AppRole credentials file is unavailable" >&2
    exit 1
fi

# exec/read env in current shell
set -a
. "$credentials_file"
set +a

# python app get those tokens
exec python main.py
