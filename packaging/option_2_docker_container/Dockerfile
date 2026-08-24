# Option 2: Production Multi-Platform Dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system GIS libraries, GDAL binaries, and Python 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    python3-gdal \
    gdal-bin \
    libgdal-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application source
COPY app/ /app/app/
COPY run_server.py /app/

# Create data directories
RUN mkdir -p /app/data /app/outputs

EXPOSE 8000

CMD ["python3", "run_server.py"]
