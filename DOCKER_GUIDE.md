# Docker Guide for Wan2.2

This guide helps you run Wan2.2 using Docker to avoid GLIBC compatibility issues and simplify dependency management.

## Quick Reference

| Model | Resolution | Min VRAM | Recommended AWS Instance | Speed (est.) |
|-------|-----------|----------|-------------------------|--------------|
| TI2V-5B | 720P @ 24fps | 24GB | `g5.xlarge` (A10G) | ~9 min/5s video |
| T2V-A14B | 480P/720P | 80GB | `p4de.24xlarge` (A100 80GB) | ~15 min/5s video |
| I2V-A14B | 480P/720P | 80GB | `p4de.24xlarge` (A100 80GB) | ~15 min/5s video |
| S2V-14B | 480P/720P | 80GB | `p4de.24xlarge` (A100 80GB) | Varies by audio |
| Animate-14B | 480P/720P | 80GB | `p4de.24xlarge` (A100 80GB) | ~20 min/5s video |

**Jump to:**
- [Quick Start](#quick-start)
- **Single-GPU Examples:**
  - [TI2V-5B](#ti2v-5b-text-to-video-720p--24fps) (Most popular, 24GB GPU)
  - [T2V-A14B](#t2v-a14b-text-to-video-480p720p) (80GB GPU)
  - [I2V-A14B](#i2v-a14b-image-to-video-480p720p) (80GB GPU)
  - [S2V-14B](#s2v-14b-speech-to-video-480p720p) (Speech-to-Video)
  - [Animate-14B](#animate-14b-character-animation-and-replacement) (Character animation)
- **Multi-GPU Examples:**
  - [Multi-GPU Overview](#running-inference-multi-gpu) (4-8 GPUs, 4-6x faster)
  - [TI2V-5B Multi-GPU](#ti2v-5b-multi-gpu-4-8-gpus)
  - [T2V-A14B Multi-GPU](#t2v-a14b-multi-gpu-4-8-gpus)
  - [I2V-A14B Multi-GPU](#i2v-a14b-multi-gpu-4-8-gpus)
  - [S2V-14B Multi-GPU](#s2v-14b-multi-gpu-4-8-gpus)
  - [Animate-14B Multi-GPU](#animate-14b-multi-gpu-4-8-gpus)
- [AWS EC2 Recommendations](#aws-ec2-instance-recommendations)

## Prerequisites

- Docker (>= 20.10)
- NVIDIA Docker runtime ([nvidia-docker](https://github.com/NVIDIA/nvidia-docker))
- NVIDIA GPU with CUDA support
- Docker Compose (optional, for easier management)

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# Build the image
docker-compose build

# Run the container
docker-compose up -d

# Execute commands inside the container
docker-compose exec wan22 bash
```

### Option 2: Using Docker Commands

```bash
# Build the image
docker build -t wan22:latest .

# Run the container
docker run --gpus all -it --rm \
  -v $(pwd):/workspace \
  -v /mnt/efs/models:/mnt/efs/models \
  -e DASH_API_KEY=$DASHSCOPE_API_KEY \
  --shm-size 16g \
  wan22:latest bash
```

## Running Inference (Single-GPU)

Once inside the container, you can run your commands. All examples below use single-GPU inference with memory optimization flags.

### TI2V-5B: Text-to-Video (720P @ 24fps)

**Basic T2V without prompt extension:**
```bash
time python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage."
```

**T2V with Dashscope prompt extension (Recommended):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**T2V with local Qwen prompt extension:**
```bash
time python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage." \
  --use_prompt_extend \
  --prompt_extend_method 'local_qwen' \
  --prompt_extend_model 'Qwen/Qwen2.5-7B-Instruct' \
  --prompt_extend_target_lang 'zh'
```

### TI2V-5B: Image-to-Video (720P @ 24fps)

**I2V with Dashscope prompt extension (Your example):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --image examples/i2v_input.JPG \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard. The fluffy-furred feline gazes directly at the camera with a relaxed expression. Blurred beach scenery forms the background featuring crystal-clear waters, distant green hills, and a blue sky dotted with white clouds. The cat assumes a naturally relaxed posture, as if savoring the sea breeze and warm sunlight. A close-up shot highlights the feline's intricate details and the refreshing atmosphere of the seaside." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**I2V with local VLM prompt extension:**
```bash
time python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --image examples/i2v_input.JPG \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --use_prompt_extend \
  --prompt_extend_method 'local_qwen' \
  --prompt_extend_model 'Qwen/Qwen2.5-VL-7B-Instruct' \
  --prompt_extend_target_lang 'zh'
```

**I2V without prompt (auto-generate from image):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --image examples/i2v_input.JPG \
  --prompt '' \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope'
```

### T2V-A14B: Text-to-Video (480P/720P)

**Single-GPU with memory offloading (requires 80GB VRAM):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task t2v-A14B \
  --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**480P generation (faster, less memory):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task t2v-A14B \
  --size 832*480 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "A majestic eagle soaring through mountain valleys at sunset." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

### I2V-A14B: Image-to-Video (480P/720P)

**Single-GPU I2V (requires 80GB VRAM):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task i2v-A14B \
  --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-I2V-A14B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --image examples/i2v_input.JPG \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

> **Note:** The `--size` parameter for I2V models represents the target area. The aspect ratio follows the input image.

## Running Inference (Multi-GPU)

Multi-GPU inference uses PyTorch FSDP (Fully Sharded Data Parallel) and DeepSpeed Ulysses for significantly faster generation. Use `torchrun` to launch distributed training.

### TI2V-5B: Multi-GPU (4-8 GPUs)

**4-GPU Text-to-Video with prompt extension:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=4 generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 4 \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**8-GPU Image-to-Video with prompt extension:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=8 generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8 \
  --image examples/i2v_input.JPG \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

> **Note:** For multi-GPU, remove `--offload_model`, `--convert_model_dtype`, and `--t5_cpu` flags as they are for single-GPU memory optimization.

### T2V-A14B: Multi-GPU (4-8 GPUs)

**4-GPU Text-to-Video (720P) with prompt extension:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=4 generate.py \
  --task t2v-A14B \
  --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 4 \
  --prompt "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**8-GPU Text-to-Video (720P) with prompt extension:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=8 generate.py \
  --task t2v-A14B \
  --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8 \
  --prompt "A majestic eagle soaring through mountain valleys at sunset, cinematic lighting." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**8-GPU Text-to-Video (480P) for faster generation:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=8 generate.py \
  --task t2v-A14B \
  --size 832*480 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8 \
  --prompt "A peaceful zen garden with flowing water and cherry blossoms." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

### I2V-A14B: Multi-GPU (4-8 GPUs)

**4-GPU Image-to-Video with prompt extension:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=4 generate.py \
  --task i2v-A14B \
  --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-I2V-A14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 4 \
  --image examples/i2v_input.JPG \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**8-GPU Image-to-Video without prompt (auto-generate):**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=8 generate.py \
  --task i2v-A14B \
  --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-I2V-A14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8 \
  --image examples/i2v_input.JPG \
  --prompt '' \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope'
```

### S2V-14B: Multi-GPU (4-8 GPUs)

**8-GPU Speech-to-Video with audio file:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=8 generate.py \
  --task s2v-14B \
  --size 1024*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-S2V-14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8 \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --image examples/i2v_input.JPG \
  --audio examples/talk.wav \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**8-GPU Speech-to-Video with pose-driven generation:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=8 generate.py \
  --task s2v-14B \
  --size 1024*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-S2V-14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8 \
  --prompt "a person is singing" \
  --image examples/pose.png \
  --audio examples/sing.MP3 \
  --pose_video examples/pose.mp4 \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**4-GPU with CosyVoice TTS:**
```bash
time DASH_API_KEY=$DASH_API_KEY torchrun --nproc_per_node=4 generate.py \
  --task s2v-14B \
  --size 1024*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-S2V-14B \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 4 \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --image examples/i2v_input.JPG \
  --enable_tts \
  --tts_prompt_audio examples/zero_shot_prompt.wav \
  --tts_prompt_text "希望你以后能够做的比我还好呦。" \
  --tts_text "收到好友从远方寄来的生日礼物,那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐,笑容如花儿般绽放。" \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

### Animate-14B: Multi-GPU (4-8 GPUs)

**Preprocessing (runs on single GPU, same as before):**
```bash
# For animation mode
python ./wan/modules/animate/preprocess/preprocess_data.py \
  --ckpt_path /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B/process_checkpoint \
  --video_path ./examples/wan_animate/animate/video.mp4 \
  --refer_path ./examples/wan_animate/animate/image.jpeg \
  --save_path ./examples/wan_animate/animate/process_results \
  --resolution_area 1280 720 \
  --retarget_flag \
  --use_flux
```

**8-GPU Animation Mode:**
```bash
time torchrun --nproc_per_node=8 generate.py \
  --task animate-14B \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B \
  --src_root_path ./examples/wan_animate/animate/process_results/ \
  --refert_num 1 \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8
```

**8-GPU Replacement Mode:**
```bash
time torchrun --nproc_per_node=8 generate.py \
  --task animate-14B \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B \
  --src_root_path ./examples/wan_animate/replace/process_results/ \
  --refert_num 1 \
  --replace_flag \
  --use_relighting_lora \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 8
```

**4-GPU Animation Mode (smaller setup):**
```bash
time torchrun --nproc_per_node=4 generate.py \
  --task animate-14B \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B \
  --src_root_path ./examples/wan_animate/animate/process_results/ \
  --refert_num 1 \
  --dit_fsdp \
  --t5_fsdp \
  --ulysses_size 4
```

### Multi-GPU Configuration Tips

**Ulysses Size Selection:**
- `--ulysses_size` should match `--nproc_per_node` (number of GPUs)
- Valid sizes: 2, 4, 8 (powers of 2)
- More GPUs = faster generation but higher cost

**FSDP Flags:**
- `--dit_fsdp`: Shard DiT model across GPUs
- `--t5_fsdp`: Shard T5 encoder across GPUs
- Both are recommended for multi-GPU setups

**Memory Optimization:**
- Multi-GPU removes need for `--offload_model`, `--convert_model_dtype`, `--t5_cpu`
- Each GPU uses less memory than single-GPU
- Can run larger models or higher resolutions

**Performance Expectations:**
| GPUs | Expected Speedup | Best For |
|------|-----------------|----------|
| 2 GPUs | 1.5-1.8x | Development/testing |
| 4 GPUs | 2.5-3.5x | Production (balanced) |
| 8 GPUs | 4-6x | Production (fastest) |

**Docker Multi-GPU Setup:**
```bash
# Check available GPUs
docker-compose exec wan22 nvidia-smi

# Run on specific GPUs (e.g., GPU 0,1,2,3)
CUDA_VISIBLE_DEVICES=0,1,2,3 docker-compose exec wan22 bash
torchrun --nproc_per_node=4 generate.py ...

# Run on all GPUs
docker-compose exec wan22 bash
torchrun --nproc_per_node=8 generate.py ...
```

**Recommended Multi-GPU AWS Instances:**

For multi-GPU inference, see the [Multi-GPU Recommendations](#multi-gpu-recommendations) section below for detailed instance comparisons. Quick picks:

- **Budget:** `g5.48xlarge` (8x A10G 24GB) @ ~$16/hr - Best for TI2V-5B
- **Production:** `p4d.24xlarge` (8x A100 40GB) @ ~$33/hr - Best for A14B models
- **Premium:** `p5.48xlarge` (8x H100 80GB) @ ~$98/hr - Fastest option

---

## Running Inference (Single-GPU) - Continued

### S2V-14B: Speech-to-Video (480P/720P)

> **Important:** Before running S2V, uncomment the S2V requirements line in `Dockerfile` and rebuild the container.

**Basic Speech-to-Video with audio file:**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task s2v-14B \
  --size 1024*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-S2V-14B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --image examples/i2v_input.JPG \
  --audio examples/talk.wav \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**S2V with CosyVoice TTS (Text-to-Speech synthesis):**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task s2v-14B \
  --size 1024*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-S2V-14B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard." \
  --image examples/i2v_input.JPG \
  --enable_tts \
  --tts_prompt_audio examples/zero_shot_prompt.wav \
  --tts_prompt_text "希望你以后能够做的比我还好呦。" \
  --tts_text "收到好友从远方寄来的生日礼物,那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐,笑容如花儿般绽放。" \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

**S2V with pose-driven generation:**
```bash
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task s2v-14B \
  --size 1024*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-S2V-14B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "a person is singing" \
  --image examples/pose.png \
  --audio examples/sing.MP3 \
  --pose_video examples/pose.mp4 \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

### Animate-14B: Character Animation and Replacement

> **Important:** Before running Animate, uncomment the Animate requirements line in `Dockerfile` and rebuild the container.

**Step 1: Preprocessing for Animation Mode**
```bash
python ./wan/modules/animate/preprocess/preprocess_data.py \
  --ckpt_path /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B/process_checkpoint \
  --video_path ./examples/wan_animate/animate/video.mp4 \
  --refer_path ./examples/wan_animate/animate/image.jpeg \
  --save_path ./examples/wan_animate/animate/process_results \
  --resolution_area 1280 720 \
  --retarget_flag \
  --use_flux
```

**Step 2: Run Animation (Single-GPU)**
```bash
time python generate.py \
  --task animate-14B \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B \
  --src_root_path ./examples/wan_animate/animate/process_results/ \
  --refert_num 1 \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu
```

**Step 1: Preprocessing for Replacement Mode**
```bash
python ./wan/modules/animate/preprocess/preprocess_data.py \
  --ckpt_path /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B/process_checkpoint \
  --video_path ./examples/wan_animate/replace/video.mp4 \
  --refer_path ./examples/wan_animate/replace/image.jpeg \
  --save_path ./examples/wan_animate/replace/process_results \
  --resolution_area 1280 720 \
  --iterations 3 \
  --k 7 \
  --w_len 1 \
  --h_len 1 \
  --replace_flag
```

**Step 2: Run Replacement (Single-GPU)**
```bash
time python generate.py \
  --task animate-14B \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-Animate-14B \
  --src_root_path ./examples/wan_animate/replace/process_results/ \
  --refert_num 1 \
  --replace_flag \
  --use_relighting_lora \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu
```

## AWS EC2 Instance Recommendations

Choose the right instance based on the model and your budget:

### TI2V-5B (720P @ 24fps)
**Recommended for consumer GPUs and cost-efficiency:**

| Instance Type | GPU | VRAM | Price/hr* | Best For |
|--------------|-----|------|-----------|----------|
| `g5.xlarge` | A10G | 24GB | ~$1.00 | TI2V-5B with offloading (tested on 4090-equivalent) |
| `g5.2xlarge` | A10G | 24GB | ~$1.21 | TI2V-5B, faster inference |
| `g6.xlarge` | L4 | 24GB | ~$0.78 | Budget option for TI2V-5B |

**Example usage:**
```bash
# On g5.xlarge or g6.xlarge
docker-compose exec wan22 bash
time python generate.py --task ti2v-5B --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True --convert_model_dtype --t5_cpu \
  --prompt "..." --use_prompt_extend --prompt_extend_method 'dashscope'
```

### T2V-A14B / I2V-A14B (480P/720P MoE Models)
**Requires high VRAM for single-GPU:**

| Instance Type | GPU | VRAM | Price/hr* | Best For |
|--------------|-----|------|-----------|----------|
| `p4d.24xlarge` | 8x A100 | 8x 40GB | ~$32.77 | Multi-GPU (4-8 GPUs with FSDP) |
| `p5.48xlarge` | 8x H100 | 8x 80GB | ~$98.32 | Fastest multi-GPU option |
| `g5.48xlarge` | 8x A10G | 8x 24GB | ~$16.29 | Budget multi-GPU option |
| `p3.8xlarge` | 4x V100 | 4x 16GB | ~$12.24 | Multi-GPU for 480P only |

**Single-GPU options (80GB VRAM required):**

| Instance Type | GPU | VRAM | Price/hr* | Best For |
|--------------|-----|------|-----------|----------|
| `p4de.24xlarge` | 8x A100 | 8x 80GB | ~$40.97 | Run on 1 GPU with offloading |
| `p5.48xlarge` | 8x H100 | 8x 80GB | ~$98.32 | Best performance per GPU |

**Example usage (single A100 80GB):**
```bash
# Limit to one GPU
CUDA_VISIBLE_DEVICES=0 docker-compose exec wan22 bash
time python generate.py --task t2v-A14B --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --offload_model True --convert_model_dtype --t5_cpu \
  --prompt "..." --use_prompt_extend --prompt_extend_method 'dashscope'
```

### S2V-14B / Animate-14B
**Similar requirements to A14B models:**

| Instance Type | GPU | VRAM | Price/hr* | Best For |
|--------------|-----|------|-----------|----------|
| `p4de.24xlarge` | 8x A100 | 8x 80GB | ~$40.97 | Single-GPU with 80GB VRAM |
| `p4d.24xlarge` | 8x A100 | 8x 40GB | ~$32.77 | Multi-GPU (4-8 GPUs) |
| `g5.48xlarge` | 8x A10G | 8x 24GB | ~$16.29 | Budget multi-GPU (may need more offloading) |

### Multi-GPU Recommendations

For production or faster inference, use multi-GPU with FSDP + Ulysses:

| Model | Min GPUs | Recommended Instance | Example |
|-------|----------|---------------------|---------|
| TI2V-5B | 4-8 | `g5.12xlarge` (4x A10G) | Faster 720P generation |
| T2V-A14B | 4-8 | `p4d.24xlarge` (8x A100 40GB) | Production 720P |
| I2V-A14B | 4-8 | `p4d.24xlarge` (8x A100 40GB) | Production 720P |
| S2V-14B | 4-8 | `p4d.24xlarge` (8x A100 40GB) | Speech-driven video |
| Animate-14B | 4-8 | `p4d.24xlarge` (8x A100 40GB) | Character animation |

**Multi-GPU example (8 GPUs):**
```bash
docker-compose exec wan22 bash
torchrun --nproc_per_node=8 generate.py \
  --task t2v-A14B --size 1280*720 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B \
  --dit_fsdp --t5_fsdp --ulysses_size 8 \
  --prompt "..." --use_prompt_extend --prompt_extend_method 'dashscope'
```

> **Note:** Prices are approximate US East (N. Virginia) on-demand rates as of 2025. Use Spot Instances for 60-70% cost savings.

### Cost Optimization Tips

1. **Use Spot Instances:** Save 60-70% on compute costs
2. **Start with TI2V-5B:** Most cost-effective, runs on 24GB GPUs
3. **Use EFS for models:** Share model weights across instances
4. **Batch generation:** Generate multiple videos per session
5. **Test on 480P first:** Use lower resolution for prompt/parameter testing

## Getting Started Checklist

Before running inference, make sure you have:

- [ ] Docker and NVIDIA Docker runtime installed
- [ ] AWS EC2 instance with appropriate GPU (see [recommendations](#aws-ec2-instance-recommendations))
- [ ] Model weights downloaded to `/mnt/efs/models` (or update paths in `docker-compose.yml`)
- [ ] Dashscope API key for prompt extension (optional but recommended)
- [ ] Built the Docker image (`docker-compose build`)

**Step-by-step first run:**

```bash
# 1. Clone the repo (if not already done)
git clone https://github.com/Wan-Video/Wan2.2.git
cd Wan2.2

# 2. Create .env file with your API key
echo "DASHSCOPE_API_KEY=your-api-key-here" > .env

# 3. Build the Docker image (this takes 10-15 minutes due to flash_attn compilation)
docker-compose build

# 4. Start the container
docker-compose up -d

# 5. Enter the container
docker-compose exec wan22 bash

# 6. Run your first video generation (TI2V-5B example)
time DASH_API_KEY=$DASH_API_KEY python generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /mnt/efs/models/hub/models--Wan-AI--Wan2.2-TI2V-5B \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --prompt "A serene mountain landscape at sunrise" \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'
```

## Environment Variables

### Dashscope API Key (For Prompt Extension)

Create a `.env` file in the project root:

```bash
# .env file
DASHSCOPE_API_KEY=your-api-key-here

# For Alibaba Cloud International users, also add:
# DASH_API_URL=https://dashscope-intl.aliyuncs.com/api/v1
```

Or export directly in your shell:

```bash
export DASHSCOPE_API_KEY="your-api-key-here"
```

**To get a Dashscope API key:**
- [English Guide](https://www.alibabacloud.com/help/en/model-studio/getting-started/first-api-call-to-qwen)
- [中文指南](https://help.aliyun.com/zh/model-studio/getting-started/first-api-call-to-qwen)

### Using Without Prompt Extension

If you don't have a Dashscope API key, you can:

1. **Skip prompt extension** (basic prompts):
   ```bash
   # Remove --use_prompt_extend flags
   python generate.py --task ti2v-5B ... --prompt "Your prompt"
   ```

2. **Use local Qwen models** (requires more VRAM):
   ```bash
   python generate.py --task ti2v-5B ... \
     --use_prompt_extend \
     --prompt_extend_method 'local_qwen' \
     --prompt_extend_model 'Qwen/Qwen2.5-7B-Instruct'
   ```

## Volume Mounts

The Docker setup mounts:
- Current directory to `/workspace` (source code)
- `/mnt/efs/models` to `/mnt/efs/models` (model weights)
- `./outputs` to `/workspace/outputs` (generated videos)

Adjust paths in `docker-compose.yml` as needed.

## Troubleshooting

### GPU Not Detected

Verify NVIDIA Docker runtime:
```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### Out of Memory

Increase shared memory in `docker-compose.yml`:
```yaml
shm_size: '32gb'  # Increase if needed
```

### Build Timeout for flash_attn

The flash_attn build can take 10-15 minutes. Be patient or use:
```bash
docker build --build-arg MAX_JOBS=4 -t wan22:latest .
```

## Benefits of Using Docker

1. ✅ **No GLIBC issues**: Ubuntu 22.04 has GLIBC 2.35
2. ✅ **Clean environment**: Isolated dependencies
3. ✅ **Reproducible**: Same environment across machines
4. ✅ **Easy deployment**: Share the image with your team
5. ✅ **Version control**: Pin exact dependency versions

## Advanced Usage

### Building for Different Tasks

Uncomment lines in `Dockerfile` to install additional requirements:

```dockerfile
# For Speech-to-Video
RUN pip install --no-cache-dir -r requirements_s2v.txt

# For Animate
RUN pip install --no-cache-dir -r requirements_animate.txt
```

Then rebuild:
```bash
docker-compose build
```

## Clean Up

```bash
# Stop and remove containers
docker-compose down

# Remove images
docker rmi wan22:latest

# Clean up all unused Docker resources
docker system prune -a
```
