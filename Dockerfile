# Dockerfile (Corrected to install dependencies explicitly)

# Use a specific Python version matching your pyproject.toml requirement (>=3.10)
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install uv using pip
# It's good practice to upgrade pip first
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv

# Copy the dependency definition file (still useful for context, though not directly used by the next command)
COPY pyproject.toml ./

# --- FIX ---
# Install ONLY the dependencies listed in pyproject.toml, not the project itself (.)
# This avoids triggering the hatchling build which requires README.md at this stage.
RUN uv pip install --system --no-cache \
    "nornir==3.5.0" \
    "nornir-napalm" \
    "fastmcp" \
    "sse-starlette"

# Now copy the application source code and the README
COPY nornir_ops.py server.py ./

# Copy the Nornir configuration files into the expected 'conf' directory
COPY conf/ /app/conf/

# Expose the port the FastMCP server will run on (default is often 8000)
EXPOSE 8000

# Command to run the application when the container starts
CMD ["python", "server.py"]