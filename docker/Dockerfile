FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project before editable install so package sources exist.
COPY pyproject.toml README.md LICENSE ./
COPY runner ./runner
COPY schemas ./schemas
COPY requirements.txt* ./

RUN pip install --no-cache-dir -e .

COPY . .

RUN mkdir -p /app/evidence/certs /app/evidence/logs /app/evidence/reports

ENV PYTHONPATH=/app
ENV MORPH_API_KEY=""

CMD ["replay-runner", "--help"]
