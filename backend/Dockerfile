FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data/static/avatars

ENV DATABASE_URL=sqlite:////data/crm.db
ENV STATIC_DIR=/data/static
ENV SECRET_KEY=change-me-in-production
ENV CORS_ORIGINS=http://localhost:8080,http://localhost

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
