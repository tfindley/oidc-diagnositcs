FROM python:3.13-slim

WORKDIR /app

# Create a non-root user with a home directory (required by gunicorn's control server)
RUN groupadd --system app && useradd --system --gid app --create-home app

# Apply OS security patches and remove packages not needed at runtime.
# ncurses-bin contains the infocmp CLI tool (CVE-2025-69720, high) — the tool
# has no purpose in a web container; the ncurses libraries remain for Python.
# tar cannot be removed (dpkg hard-dependency), so CVE-2026-5704 is residual.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get remove --purge -y --allow-remove-essential ncurses-bin \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer-cached independently of app code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Embed build timestamp (pass with --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ))
ARG BUILD_DATE=development
ENV BUILD_DATE=$BUILD_DATE

# Copy application code
COPY app.py .
COPY templates/ templates/

# Switch to non-root user
USER app

EXPOSE 5000

# Use gunicorn for production; 2 workers is appropriate for a low-traffic diagnostic tool
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
