# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# default command (overridden for demo-sender)
CMD ["python", "-m", "scripts.cancel_replace_receiver"]

