FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml requirements.txt* ./
RUN pip install --no-cache-dir -e .

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p /app/evidence/certs /app/evidence/logs /app/evidence/reports

# Set environment variables
ENV PYTHONPATH=/app
ENV MORPH_API_KEY=""

# Default command
CMD ["replay-runner", "--help"]
