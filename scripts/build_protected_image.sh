#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${1:-ai_alerting:protected}"

docker build -f docker/Dockerfile.protected -t "${IMAGE_NAME}" .
echo "built protected image: ${IMAGE_NAME}"
