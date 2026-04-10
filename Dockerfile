FROM python:3.13-slim

WORKDIR /app

# Create a non-root user with a home directory (required by gunicorn's control server)
RUN groupadd --system app && useradd --system --gid app --create-home app

# Install dependencies first (layer-cached independently of app code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY templates/ templates/

# Switch to non-root user
USER app

EXPOSE 5000

# Use gunicorn for production; 2 workers is appropriate for a low-traffic diagnostic tool
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
