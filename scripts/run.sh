#!/usr/bin/env bash

set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"

require_env_file
exec docker run --rm \
    --network host \
    --env-file .env \
    "$IMAGE_NAME" "$@"
