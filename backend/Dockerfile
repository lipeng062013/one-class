FROM python:3.11-slim

WORKDIR /app

# Install deps first for better layer cache.
# Use Aliyun PyPI mirror (Docker Hub Hub 已加速时，pip 仍常卡在 pypi.org).
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt

COPY app ./app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# SQLite + uploads live under /app/data (compose mounts a host volume here)
RUN mkdir -p /app/data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
