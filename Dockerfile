FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENFRAME_DATA_DIR=/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY backend/ backend/
COPY engine/ engine/
COPY workflows/ workflows/
COPY custom_nodes/ custom_nodes/
COPY docs/ docs/
COPY recipes/ recipes/
COPY scripts/ scripts/
RUN pip install --no-cache-dir '.[cloud]'
COPY --from=frontend /build/frontend/dist frontend/dist/
RUN useradd --uid 10001 --create-home openframe && mkdir -p /data && chown openframe:openframe /data
USER openframe
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
