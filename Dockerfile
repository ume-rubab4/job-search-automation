# ---- Stage 1: build the React front end ----
FROM node:22-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- Stage 2: the Python service ----
FROM python:3.13-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/
COPY api.py config.yaml ./
COPY data/ ./data/

COPY --from=frontend /build/dist ./web/dist

RUN useradd --create-home appuser \
    && mkdir -p /app/logs \
    && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "api.py"]