FROM python:3.12-slim as builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install into a virtual environment
COPY proteus-ai/proteus/requirements.txt /app/requirements.txt
RUN python -m venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"
RUN /venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Final stage
FROM python:3.12-slim
WORKDIR /app

# Install runtime dependencies and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python environment from builder
COPY --from=builder /venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"

# Create non-root user
RUN useradd -m proteus && chown -R proteus:proteus /app
USER proteus

# Copy application code
COPY proteus-ai/proteus/main.py /app/main.py
COPY proteus-ai/proteus/proteus_mcp_config.json /app/proteus_mcp_config.json
COPY proteus-ai/proteus/src /app/src
COPY proteus-ai/proteus/static /app/static

# Copy entrypoint script and make executable
COPY proteus-ai/proteus/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD curl -f http://127.0.0.1:8000/health || exit 1

# Entry point
ENTRYPOINT ["/app/entrypoint.sh"]
