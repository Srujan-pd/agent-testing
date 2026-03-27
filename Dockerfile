FROM python:3.11-slim

WORKDIR /app

# Install gcloud CLI using the NEW method (no apt-key)
# apt-key is removed in Debian Trixie — use signed-by instead
RUN apt-get update && \
    apt-get install -y curl apt-transport-https gnupg ca-certificates && \
    curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
        > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    apt-get update && \
    apt-get install -y google-cloud-cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all agent files into the container
COPY agent/ .

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Start the FastAPI server
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
