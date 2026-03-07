#!/usr/bin/env bash
# 初始化运行目录脚本：用于本地或容器挂载前准备目录结构。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/runtime/app_data"

mkdir -p "$RUNTIME_DIR/log"
mkdir -p "$RUNTIME_DIR/images/upload"
mkdir -p "$RUNTIME_DIR/images/result"
mkdir -p "$RUNTIME_DIR/models/000001"

echo "runtime directories prepared under: $RUNTIME_DIR"
