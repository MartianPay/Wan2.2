# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Wan2.2 is an open-source large-scale video generative model developed by the Alibaba Wan Team. It supports multiple video generation tasks including Text-to-Video (T2V), Image-to-Video (I2V), Text-Image-to-Video (TI2V), Speech-to-Video (S2V), and Character Animation (Animate). The project uses a Mixture-of-Experts (MoE) architecture for the A14B models and includes a lightweight 5B model for efficient deployment.

## Development Commands

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# For Speech-to-Video support
pip install -r requirements_s2v.txt

# For Character Animation support
pip install -r requirements_animate.txt

# Install with pip (editable mode for development)
pip install -e .
pip install -e .[dev]  # Include dev tools
```

**Important:** If `flash-attn` installation fails, install other packages first, then install `flash-attn` separately.

### Code Formatting
```bash
# Format code (uses black and isort profiles from pyproject.toml)
make format

# Or manually
black .
isort .
yapf -i -r *.py generate.py wan
```

### Testing
```bash
# Run tests (requires models downloaded)
bash tests/test.sh <local_model_dir> <gpu_number>
```

### Running Inference

**Single-GPU Examples:**
```bash
# TI2V-5B Text-to-Video (requires 24GB+ VRAM, e.g., RTX 4090)
python generate.py --task ti2v-5B --size 1280*704 \
  --ckpt_dir ./Wan2.2-TI2V-5B \
  --offload_model True --convert_model_dtype --t5_cpu \
  --prompt "Your prompt here"

# T2V-A14B Text-to-Video (requires 80GB VRAM)
python generate.py --task t2v-A14B --size 1280*720 \
  --ckpt_dir ./Wan2.2-T2V-A14B \
  --offload_model True --convert_model_dtype \
  --prompt "Your prompt here"

# I2V-A14B Image-to-Video (requires 80GB VRAM)
python generate.py --task i2v-A14B --size 1280*720 \
  --ckpt_dir ./Wan2.2-I2V-A14B \
  --offload_model True --convert_model_dtype \
  --image path/to/image.jpg \
  --prompt "Your prompt here"
```

**Multi-GPU Examples (using FSDP + DeepSpeed Ulysses):**
```bash
# 8-GPU T2V-A14B (faster, distributed inference)
torchrun --nproc_per_node=8 generate.py --task t2v-A14B --size 1280*720 \
  --ckpt_dir ./Wan2.2-T2V-A14B \
  --dit_fsdp --t5_fsdp --ulysses_size 8 \
  --prompt "Your prompt here"
```

**Prompt Extension:**
To improve video quality, use prompt extension with either Dashscope API or local Qwen models:
```bash
# With Dashscope API (recommended)
DASH_API_KEY=your_key python generate.py ... \
  --use_prompt_extend \
  --prompt_extend_method 'dashscope' \
  --prompt_extend_target_lang 'zh'

# With local Qwen model
python generate.py ... \
  --use_prompt_extend \
  --prompt_extend_method 'local_qwen' \
  --prompt_extend_model 'Qwen/Qwen2.5-7B-Instruct' \
  --prompt_extend_target_lang 'zh'
```

### Docker Deployment
```bash
# Build Docker image
docker-compose build

# Run container
docker-compose up -d

# Execute commands in container
docker-compose exec wan22 bash
```

See `DOCKER_GUIDE.md` for comprehensive Docker usage, AWS EC2 recommendations, and multi-GPU configurations.

## Architecture Overview

### Core Pipeline Structure

The codebase is organized into task-specific pipelines that share common components:

1. **Text Encoder (T5)**: `wan/modules/t5.py`
   - Uses `umt5_xxl` model by default
   - Encodes text prompts into embeddings (512 token length)
   - Can be placed on CPU (`--t5_cpu`) or sharded with FSDP (`--t5_fsdp`)

2. **VAE (Variational Autoencoder)**: `wan/modules/vae2_1.py` and `wan/modules/vae2_2.py`
   - `vae2_1.py`: Standard VAE for A14B models
   - `vae2_2.py`: High-compression VAE for TI2V-5B model (16×16×4 compression)
   - Encodes video frames to/from latent space

3. **DiT (Diffusion Transformer)**: `wan/modules/model.py`
   - Core denoising model with attention mechanisms (`wan/modules/attention.py`)
   - For A14B models: Uses MoE architecture with high-noise and low-noise experts
   - Supports FSDP sharding (`--dit_fsdp`) and sequence parallelism

4. **Solvers**: `wan/utils/fm_solvers.py` and `wan/utils/fm_solvers_unipc.py`
   - Flow matching solvers for denoising process
   - Options: `unipc` (default) or `dpm++`
   - Configurable sampling steps and shift factor

### Task-Specific Pipelines

Each task has its own pipeline class and entry point:

- **T2V**: `wan/text2video.py` → `WanT2V` class
- **I2V**: `wan/image2video.py` → `WanI2V` class
- **TI2V**: `wan/textimage2video.py` → `WanTI2V` class
- **S2V**: `wan/speech2video.py` → `WanS2V` class
  - Additional components: `wan/modules/s2v/audio_encoder.py`, `wan/modules/s2v/motioner.py`
- **Animate**: `wan/animate.py` → `WanAnimate` class
  - Additional components in `wan/modules/animate/`
  - Requires preprocessing: `wan/modules/animate/preprocess/preprocess_data.py`

### Configuration System

Model configurations are in `wan/configs/`:
- `shared_config.py`: Common settings (T5 model, dtypes, FPS, negative prompt)
- Task-specific configs: `wan_t2v_A14B.py`, `wan_i2v_A14B.py`, `wan_ti2v_5B.py`, etc.
- Configs define model architecture, sampling parameters, resolution support

The `generate.py` script uses `WAN_CONFIGS`, `SIZE_CONFIGS`, and `SUPPORTED_SIZES` from `wan/configs/__init__.py` to validate arguments.

### Distributed Training Components

Located in `wan/distributed/`:
- `fsdp.py`: FSDP (Fully Sharded Data Parallel) wrappers for model sharding
- `ulysses.py`: DeepSpeed Ulysses sequence parallelism implementation
- `sequence_parallel.py`: Sequence parallelism utilities
- `util.py`: Distributed group initialization

**Key distributed flags:**
- `--dit_fsdp`: Shard DiT model across GPUs
- `--t5_fsdp`: Shard T5 encoder across GPUs
- `--ulysses_size`: Number of GPUs for sequence parallelism (must equal `nproc_per_node`)

### MoE Architecture (A14B Models)

The A14B models use a two-expert MoE design:
1. **High-noise expert**: Active during early denoising (high timesteps, low SNR)
2. **Low-noise expert**: Active during later refinement (low timesteps, high SNR)
3. Switch threshold determined by SNR (signal-to-noise ratio) at `t_moe`
4. Total 27B parameters, 14B active per step

This architecture increases model capacity while keeping inference cost similar to single 14B model.

## Important Development Notes

### Memory Optimization

For single-GPU inference with limited VRAM:
- `--offload_model True`: Offload models to CPU between forward passes
- `--convert_model_dtype`: Convert model params to config.param_dtype (bf16)
- `--t5_cpu`: Keep T5 encoder on CPU

For multi-GPU: Remove above flags and use `--dit_fsdp --t5_fsdp` instead.

### Resolution Constraints

- **TI2V-5B**: 720P resolution is `1280*704` or `704*1280` (not `1280*720`)
- **A14B models**: Support both `832*480` (480P) and `1280*720` (720P)
- **I2V/S2V**: The `--size` parameter represents target area; aspect ratio follows input image
- Frame count must be `4n+1` format (e.g., 49, 81, 121)

### Prompt Extension

Prompt extension significantly improves video quality by enriching prompts with cinematic details:
- **Dashscope API**: Uses `qwen-plus` for T2V, `qwen-vl-max` for I2V
- **Local Qwen**: Specify model like `Qwen/Qwen2.5-14B-Instruct` or `Qwen/Qwen2.5-VL-7B-Instruct`
- Target language: `zh` (Chinese) or `en` (English)
- System prompts defined in `wan/utils/system_prompt.py`

### Character Animation Workflow

Wan-Animate requires two-step process:
1. **Preprocessing**: `wan/modules/animate/preprocess/preprocess_data.py`
   - Extracts pose, masks, and other control signals
   - Use `--retarget_flag` for animation mode, `--replace_flag` for replacement mode
2. **Generation**: `generate.py --task animate-14B`
   - Uses preprocessed results as input
   - `--use_relighting_lora` for replacement mode

**Important:** Do not use LoRA models trained on Wan2.2 with Wan-Animate.

### Testing and Model Downloads

Models are downloaded using:
```bash
# HuggingFace
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B --local-dir ./Wan2.2-T2V-A14B

# ModelScope
modelscope download Wan-AI/Wan2.2-T2V-A14B --local_dir ./Wan2.2-T2V-A14B
```

Available models: T2V-A14B, I2V-A14B, TI2V-5B, S2V-14B, Animate-14B

### Code Style

The project uses:
- `black` for Python formatting (line length: 88)
- `isort` with black profile
- `mypy` with strict mode (configured in pyproject.toml)
- Run `make format` before committing

### Common Pitfall: Interactive Git Commands

Never use interactive git commands like `git rebase -i` or `git add -i` as they require terminal interaction which is not supported in this environment.

## Model Weights Location Conventions

When working with model checkpoints:
- Local development: Models typically in project root (e.g., `./Wan2.2-T2V-A14B`)
- Docker/AWS: Models often on EFS mount (e.g., `/mnt/efs/models/hub/models--Wan-AI--Wan2.2-T2V-A14B`)
- Adjust `--ckpt_dir` parameter based on environment

## Common Development Patterns

### Adding a New Generation Task

1. Create config in `wan/configs/wan_<task>_<model>.py` inheriting from `shared_config`
2. Implement pipeline class in `wan/<task>.py` with `generate()` method
3. Add task to `WAN_CONFIGS` in `wan/configs/__init__.py`
4. Add argument validation in `generate.py`'s `_validate_args()`
5. Add task branch in `generate()` function

### Modifying Sampling Parameters

Default sampling parameters are in task configs:
- `sample_steps`: Number of denoising steps
- `sample_shift`: Flow matching shift factor
- `sample_guide_scale`: Classifier-free guidance scale
- Override via CLI args: `--sample_steps`, `--sample_shift`, `--sample_guide_scale`

### Debugging Distributed Code

- Check rank with `os.getenv("RANK", 0)` and `os.getenv("WORLD_SIZE", 1)`
- Logging only on rank 0 (controlled in `generate.py:_init_logging()`)
- Use `dist.barrier()` for synchronization points
- Verify Ulysses size matches world size and divides num_heads evenly
