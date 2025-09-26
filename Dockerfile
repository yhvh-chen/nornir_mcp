FROM python:3.12-slim

# Keep Python output unbuffered
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install small set of OS build deps required by some Python packages (napalm/drivers may need them).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install runtime Python dependencies (pin/minimal set).
# We intentionally install the runtime deps explicitly to avoid requiring
# a full project build during image creation.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install the Python dependencies the project needs. Adjust pins as needed.
RUN pip install --no-cache-dir \
    "nornir==3.5.0" \
    "nornir-napalm" \
    "mcp[cli]==1.15.0" \
    "sse-starlette"
# Copy the project files into the image. Using a full copy makes local dev
# mounts easier (docker-compose volumes will override where needed).
COPY . /app

# Create a non-root user and fix permissions
RUN useradd -m appuser || true && chown -R appuser:appuser /app
USER appuser


# Port 8000 is now proxied externally via the proxy container in docker-compose.yml

# Default command: run the new entrypoint script. You can override with docker-compose.
CMD ["python", "run.py"]