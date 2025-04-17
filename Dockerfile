FROM python:3.11-slim

WORKDIR /app

# Install uv for package management
RUN pip install uv

# Create and activate virtual environment
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
RUN uv pip install "nornir==4.0.0" "nornir-napalm" "fastmcp" "sse-starlette" "python-dotenv"

# Copy application files
COPY server.py nornir_ops.py /app/
COPY conf /app/conf

# Create volume mount point for configuration
VOLUME /app/conf

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the MCP server
CMD ["python", "server.py"]
