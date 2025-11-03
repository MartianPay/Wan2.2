# Dockerfile for Wan2.2 Video Generation Model
# Uses CUDA 12.2 with Ubuntu 22.04 (GLIBC 2.35)

FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda

# Install system dependencies
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
    && rm -rf /var/lib/apt/lists/*

# Set python3.10 as default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Set working directory
WORKDIR /workspace

# Copy requirements files
COPY requirements.txt requirements_s2v.txt requirements_animate.txt ./

# Install PyTorch first (required for flash_attn build)
RUN pip install --no-cache-dir \
    torch>=2.4.0 \
    torchvision>=0.19.0 \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cu121

# Install flash_attn build dependencies
RUN pip install --no-cache-dir psutil packaging ninja wheel

# Install other dependencies (excluding flash_attn)
RUN grep -v "flash_attn" requirements.txt > requirements_no_flash.txt && \
    pip install --no-cache-dir -r requirements_no_flash.txt

# Install flash_attn from source (builds against system GLIBC)
RUN pip install --no-cache-dir flash-attn --no-build-isolation --no-binary flash-attn

# Install S2V requirements (includes decord and other S2V dependencies)
RUN pip install --no-cache-dir -r requirements_s2v.txt

# Install Animate requirements (includes peft and other Animate dependencies)
RUN pip install --no-cache-dir -r requirements_animate.txt

# Copy the project code
COPY . .

# Create directories for models and outputs
RUN mkdir -p /workspace/models /workspace/outputs

# Set default command
CMD ["/bin/bash"]
