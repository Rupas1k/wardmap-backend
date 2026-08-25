#!/usr/bin/env bash

set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"

require_env_file
exec docker compose exec api \
    flask --app dota2wardmap:create_app refresh-league "$@"
