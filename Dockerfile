# Dockerfile for Wan2.2 Video Generation Model
# Uses CUDA 12.2 with Ubuntu 22.04 (GLIBC 2.35)

FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PIP_NO_CACHE_DIR=1 \
    TMPDIR=/workspace/tmp

# Install system dependencies and clean up in one layer
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-dev \
    git \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /root/.cache

# Set working directory
WORKDIR /workspace

# Create tmp directory for pip/build operations
RUN mkdir -p /workspace/tmp

# Copy requirements files
COPY requirements.txt requirements_s2v.txt requirements_animate.txt ./

# Install PyTorch first (required for flash_attn build) and clean up
RUN pip install --no-cache-dir \
    torch>=2.4.0 \
    torchvision>=0.19.0 \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cu121 \
    && rm -rf /root/.cache/pip/* \
    && rm -rf /tmp/* \
    && find / -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install flash_attn dependencies, build flash_attn, and install other requirements
RUN pip install --no-cache-dir psutil packaging ninja wheel \
    && grep -v "flash_attn" requirements.txt > requirements_no_flash.txt \
    && pip install --no-cache-dir -r requirements_no_flash.txt \
    && pip install --no-cache-dir flash-attn --no-build-isolation --no-binary flash-attn \
    && rm -rf /root/.cache/pip/* \
    && rm -rf /tmp/* \
    && rm requirements_no_flash.txt \
    && find / -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install S2V requirements and clean up
RUN pip install --no-cache-dir -r requirements_s2v.txt \
    && rm -rf /root/.cache/pip/* \
    && rm -rf /tmp/* \
    && find / -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install Animate requirements (includes SAM-2) with aggressive cleanup
RUN pip install --no-cache-dir -r requirements_animate.txt \
    && rm -rf /root/.cache/pip/* \
    && rm -rf /tmp/* \
    && rm -rf /root/.cache/* \
    && find / -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find / -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find / -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

RUN pip install peft

# Copy the project code
COPY . .

# Create directories for models and outputs
RUN mkdir -p /workspace/models /workspace/outputs

# Set default command
CMD ["/bin/bash"]
