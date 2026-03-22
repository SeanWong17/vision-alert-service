# 生产镜像：多阶段构建，精简最终镜像体积
ARG MMCV_VERSION=2.1.0
ARG MMCV_WHEEL_INDEX=https://download.openmmlab.com/mmcv/dist/cu121/torch2.1.0/index.html

# ---- 构建阶段：安装依赖并编译 wheel ----
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY docker/requirements.runtime.txt ./requirements.runtime.txt
RUN python -m pip install --upgrade pip && \
    python -m pip wheel --wheel-dir=/build/wheels -r requirements.runtime.txt

# ---- 运行阶段：仅安装预编译 wheel ----
FROM python:3.10-slim AS runtime
ARG MMCV_VERSION
ARG MMCV_WHEEL_INDEX

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 安装 OpenCV / mmcv 运行依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    tzdata \
    libxrender1 \
    libxext6 \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制预编译 wheel 并安装
COPY --from=builder /build/wheels /tmp/wheels
COPY docker/requirements.runtime.txt ./requirements.runtime.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-index --find-links=/tmp/wheels -r requirements.runtime.txt && \
    python -m pip install --no-cache-dir --no-deps -f "${MMCV_WHEEL_INDEX}" "mmcv==${MMCV_VERSION}" && \
    python -c "import mmcv; print(mmcv.__version__)" && \
    apt-get purge -y --auto-remove build-essential git && \
    rm -rf /tmp/wheels /root/.cache/pip /root/.cache/mim

COPY app ./app
COPY main.py ./
COPY pyproject.toml ./

# 预创建运行目录，避免首次启动目录不存在
RUN mkdir -p /root/.ai_alerting/log \
    /root/.ai_alerting/images/upload \
    /root/.ai_alerting/images/result \
    /root/.ai_alerting/models

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/healthz')" || exit 1

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8011"]

# ---- 测试阶段：安装 CI 依赖，在容器内运行 pytest ----
FROM python:3.10-slim AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

COPY requirements-ci.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements-ci.txt

COPY . .

CMD ["python", "-m", "pytest"]
