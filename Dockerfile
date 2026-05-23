# AEGIS - Military-grade cybersecurity LLM merge/quantize container
# Targets Azure NC6s_v3 (V100 16GB) or AWS g4dn.xlarge (T4 16GB)
# Build: docker build -t aegis-builder .
# Run:   docker run --gpus all -v /home/x/models:/models -v $(pwd):/workspace aegis-builder

FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/hf-cache \
    TRANSFORMERS_CACHE=/models/hf-cache \
    TORCH_HOME=/models/torch-cache

# System deps + llama.cpp build prereqs
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip \
        git git-lfs curl ca-certificates \
        build-essential cmake ninja-build \
        libcurl4-openssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

RUN ln -sf /usr/bin/python3.11 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3

# ---------- Python ML stack ----------
FROM base AS python-deps

RUN pip install --break-system-packages --upgrade pip wheel setuptools
RUN pip install --break-system-packages \
        torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
RUN pip install --break-system-packages \
        transformers==4.46.3 \
        peft==0.14.0 \
        accelerate==1.2.1 \
        bitsandbytes==0.45.0 \
        safetensors==0.4.5 \
        sentencepiece==0.2.0 \
        protobuf==5.29.1 \
        huggingface_hub[cli]==0.27.0 \
        mergekit==0.0.5.2

# ---------- llama.cpp for GGUF quantization ----------
FROM python-deps AS llamacpp

WORKDIR /opt
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git && \
    cd llama.cpp && \
    cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=ON && \
    cmake --build build --config Release -j$(nproc) && \
    pip install --break-system-packages -r requirements.txt

ENV PATH="/opt/llama.cpp/build/bin:${PATH}"

# ---------- Final image ----------
FROM llamacpp AS final

WORKDIR /workspace
COPY src/ ./src/
COPY eval/ ./eval/
COPY deploy/ ./deploy/

# Healthcheck: verify GPU and ML stack
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import torch; assert torch.cuda.is_available(); print('GPU:', torch.cuda.get_device_name(0))" || exit 1

# Default: run the full pipeline
ENTRYPOINT ["/bin/bash", "-c"]
CMD ["python src/merge_adapters.py && python src/quantize.py --adapter /models/hf/aegis-v1-adapter && echo 'AEGIS build complete. GGUF at /models/aegis-v1.Q4_K_M.gguf'"]
