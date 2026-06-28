FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# Copy application source
COPY app ./app
COPY migrations ./migrations

EXPOSE 8080

CMD ["python", "-m", "app.main"]
