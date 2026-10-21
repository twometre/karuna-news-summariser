FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Non-root user
RUN useradd -m -u 1000 karuna && \
    chown -R karuna:karuna /app
USER karuna

EXPOSE 8768

CMD ["python", "main.py"]
