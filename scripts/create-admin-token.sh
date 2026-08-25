#!/usr/bin/env bash

set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"

if [[ $# -ne 1 || -z "$1" ]]; then
    echo "Usage: $0 <owner>" >&2
    exit 2
fi

require_env_file
exec docker compose exec -T api \
    flask --app dota2wardmap:create_app keys create --owner "$1" --access admin
