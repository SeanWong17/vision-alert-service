# 生产镜像：多阶段构建，精简最终镜像体积

# ---- 构建阶段：安装依赖并编译 wheel ----
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip wheel --wheel-dir=/build/wheels -r requirements.txt

# ---- 运行阶段：仅安装预编译 wheel ----
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装 OpenCV 运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制预编译 wheel 并安装
COPY --from=builder /build/wheels /tmp/wheels
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-index --find-links=/tmp/wheels -r requirements.txt && \
    rm -rf /tmp/wheels

# 若需要安装与 CUDA 匹配的 mmcv，请在镜像外或自定义阶段执行 mim install。
COPY . .

# 预创建运行目录，避免首次启动目录不存在
RUN mkdir -p /root/.ai_alerting/log \
    /root/.ai_alerting/images/upload \
    /root/.ai_alerting/images/result \
    /root/.ai_alerting/models

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/healthz')" || exit 1

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8011"]
