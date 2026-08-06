#!/usr/bin/env bash

set -euo pipefail

readonly PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly IMAGE_NAME="${IMAGE_NAME:-dota2wardmap-back}"

cd "$PROJECT_ROOT"

require_env_file() {
    if [[ ! -f .env ]]; then
        cp .env-example .env
        echo "Created .env from .env-example. Add OPENDOTA_API_KEY if higher API limits are needed."
    fi
}
