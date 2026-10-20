FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd --create-home classroom
COPY . .
RUN mkdir -p /data/storage && chown -R classroom:classroom /data /app
USER classroom
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--no-access-log", "--ws-max-size", "2097152", "--ws-max-queue", "8", "--timeout-keep-alive", "5"]
