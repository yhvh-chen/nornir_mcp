# Dockerfile (Updated to install uv via pip)

# Use a specific Python version matching your pyproject.toml requirement (>=3.10)
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install uv using pip
# It's good practice to upgrade pip first
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv

# Copy the dependency definition file
COPY pyproject.toml ./

# Install dependencies using the uv command (now installed via pip)
# uv can read dependencies directly from pyproject.toml
# Using --system to install globally in the container's Python environment
# Using --no-cache to avoid uv's own cache within the RUN layer
RUN uv pip install --system --no-cache .

# Copy the application source code
COPY nornir_ops.py server.py ./

# Copy the Nornir configuration files into the expected 'conf' directory
COPY conf/ /app/conf/

# Expose the port the FastMCP server will run on (default is often 8000)
# Adjust if your server.py uses a different port
EXPOSE 8000

# Command to run the application when the container starts
# Assumes server.py is the entry point and listens on 0.0.0.0 (required for Docker)
CMD ["python", "server.py"]