# FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
# Upgraded to CUDA 12.1: PyTorch 2.1+ dropped CUDA 11.8 support,
# so torchmcubes CMake fails with "PyTorch requires CUDA 12.0 or above".
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    # python3.11 python3.11-venv python3-pip git libgl1 libglib2.0-0 \
    python3.11 python3.11-venv python3.11-dev python3-pip git libgl1 libglib2.0-0 \
    libegl1 libgomp1 \
    ffmpeg \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

COPY requirements.txt .
# RUN pip install --no-cache-dir --upgrade pip && \
#     pip install --no-cache-dir -r requirements.txt && \
#     pip install --no-cache-dir git+https://github.com/tatsy/torchmcubes.git
RUN python3.11 -m pip install --no-cache-dir --upgrade pip && \
    python3.11 -m pip install --no-cache-dir -r requirements.txt && \
    python3.11 -m pip install --no-cache-dir git+https://github.com/tatsy/torchmcubes.git

# Clone TripoSR source so its tsr package is on the Python path
RUN git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git /opt/triposr
ENV PYTHONPATH="/opt/triposr:${PYTHONPATH}"

COPY . .

# Create data directories
RUN mkdir -p data/uploads data/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
