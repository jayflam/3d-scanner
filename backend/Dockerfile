FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip git libgl1 libglib2.0-0 \
    libegl1 libgomp1 && \
    rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir git+https://github.com/tatsy/torchmcubes.git

# Clone TripoSR source so its tsr package is on the Python path
RUN git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git /opt/triposr
ENV PYTHONPATH="/opt/triposr:${PYTHONPATH}"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
