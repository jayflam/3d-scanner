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
    # COLMAP build dependencies
    cmake ninja-build \
    libboost-program-options-dev libboost-filesystem-dev \
    libboost-graph-dev libboost-system-dev \
    libeigen3-dev libflann-dev libfreeimage-dev \
    libmetis-dev libgoogle-glog-dev libgflags-dev \
    libsqlite3-dev libglew-dev libcgal-dev libceres-dev \
    && rm -rf /var/lib/apt/lists/*

# Build COLMAP from source with CUDA support (GPU-accelerated SIFT extraction and matching).
# GUI is disabled for headless/server use. Pinned to a stable release tag.
RUN git clone --depth 1 --branch 3.9.1 https://github.com/colmap/colmap.git /opt/colmap && \
    mkdir /opt/colmap/build && \
    cmake -S /opt/colmap -B /opt/colmap/build \
        -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCUDA_ENABLED=ON \
        -DCMAKE_CUDA_ARCHITECTURES=75 \
        -DGUI_ENABLED=OFF \
        -DTESTS_ENABLED=OFF && \
    ninja -j2 -C /opt/colmap/build install && \
    rm -rf /opt/colmap

RUN ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

COPY requirements.txt .
# RUN pip install --no-cache-dir --upgrade pip && \
#     pip install --no-cache-dir -r requirements.txt && \
#     pip install --no-cache-dir git+https://github.com/tatsy/torchmcubes.git
RUN python3.11 -m pip install --no-cache-dir --upgrade pip && \
    python3.11 -m pip install --no-cache-dir -r requirements.txt && \
    python3.11 -m pip install --no-cache-dir git+https://github.com/tatsy/torchmcubes.git

# Install nerfstudio (includes ns-train, ns-export, and splatfacto/gsplat)
# Must come after torch is installed so CUDA extensions compile correctly.
RUN python3.11 -m pip install --no-cache-dir nerfstudio

# Clone TripoSR source so its tsr package is on the Python path
RUN git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git /opt/triposr
ENV PYTHONPATH="/opt/triposr:${PYTHONPATH}"

COPY . .

# Create data directories
RUN mkdir -p data/uploads data/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
