FROM python:3.11-slim

WORKDIR /app

# Copy project files and requirements
COPY . /app
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# --- Add curl for healthcheck support ---
RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*


# (optional, since you already did COPY . above)
# COPY . .

EXPOSE 5555 9100 8000

ENTRYPOINT ["python", "-m", "scripts.cancel_replace_receiver", "--zmq", "tcp://*:5555"]
