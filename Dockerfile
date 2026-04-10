FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache optimization)
# Copy source before pip install — hatchling needs the package present
COPY pyproject.toml .
COPY modelmesh/ modelmesh/
RUN pip install --no-cache-dir .

# Copy config (separate layer — changes frequently)
COPY config/ config/

# Non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "modelmesh.main:app", "--host", "0.0.0.0", "--port", "8000"]
