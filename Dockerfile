# Use Python base image (more reliable than openenv-base)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy all files first (for better caching and to ensure README.md is available)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENABLE_WEB_INTERFACE=true \
    API_BASE_URL="https://router.huggingface.co/v1" \
    MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["python", "server/app.py"]
