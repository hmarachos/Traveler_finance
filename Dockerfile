# Multi-stage build для оптимального размера образа
FROM python:3.11-slim as base

WORKDIR /app

# Установим переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Скопируем файлы приложения
COPY backend/ /app/backend/
COPY static/ /app/static/
COPY data/ /app/data/

# Установим зависимости (их нет, но лучше быть готовым)
RUN pip install --no-cache-dir --upgrade pip

# Откроем порт
EXPOSE 8080

# Рабочая директория для данных
VOLUME ["/app/data"]

# Запустим приложение
CMD ["python3", "backend/app.py"]
