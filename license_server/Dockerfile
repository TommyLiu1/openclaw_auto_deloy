# License 授权服务容器化部署
# 在项目根目录构建: docker build -t openclaw-license-server -f license_server/Dockerfile .
# 运行: docker run -d -p 8080:8080 -v license-data:/data --name openclaw-license openclaw-license-server

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    OPENCLAW_LICENSE_DATA=/data

RUN mkdir -p /data

COPY license_server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个 license_server 包，保持 python -m license_server.app 可用
COPY license_server/ /app/license_server/

ENV PYTHONPATH=/app

EXPOSE 8080

VOLUME ["/data"]

CMD ["python", "-m", "license_server.app", "--host", "0.0.0.0", "--port", "8080"]
