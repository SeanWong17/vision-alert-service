# 生产镜像：用于部署告警服务
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

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

# 若需要安装与 CUDA 匹配的 mmcv，请在镜像外或自定义阶段执行 mim install。
COPY . .

# 预创建运行目录，避免首次启动目录不存在
RUN mkdir -p /root/.ai_alerting/log \
    /root/.ai_alerting/images/upload \
    /root/.ai_alerting/images/result \
    /root/.ai_alerting/models

EXPOSE 8011
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8011"]
