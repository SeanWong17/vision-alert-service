#!/usr/bin/env bash
set -euo pipefail

# 用法：
#   ./scripts/build_protected_image.sh ai_alerting:protected
# 若不传参数，默认镜像名为 ai_alerting:protected
IMAGE_NAME="${1:-ai_alerting:protected}"

# 使用受保护 Dockerfile（PyArmor）构建镜像。
# 该流程会在构建阶段加固 Python 代码，并在最终镜像中只保留加固产物。
docker build -f docker/Dockerfile.protected -t "${IMAGE_NAME}" .
echo "built protected image: ${IMAGE_NAME}"
