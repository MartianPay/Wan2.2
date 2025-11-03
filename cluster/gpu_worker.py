"""
GPU Worker - 从队列中获取任务并执行视频生成
支持多 GPU、自动重试、进度更新
"""
import os
import sys
import json
import time
import redis
import torch
import boto3
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/workspace')

class GPUWorker:
    def __init__(self, gpu_id=None, redis_host='redis', redis_port=6379):
        """初始化 GPU Worker

        Args:
            gpu_id: 使用的 GPU ID，None 则自动分配
            redis_host: Redis 服务器地址
            redis_port: Redis 端口
        """
        # GPU 设置
        if gpu_id is None:
            gpu_id = int(os.environ.get('CUDA_VISIBLE_DEVICES', '0').split(',')[0])

        self.gpu_id = gpu_id
        torch.cuda.set_device(self.gpu_id)

        print(f"🚀 Worker initialized on GPU {self.gpu_id}")
        print(f"   GPU: {torch.cuda.get_device_name(self.gpu_id)}")
        print(f"   VRAM: {torch.cuda.get_device_properties(self.gpu_id).total_memory / 1e9:.1f} GB")

        # Redis 连接
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # S3 客户端
        self.s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
        self.s3_bucket = os.environ.get('S3_BUCKET', 'martianpay-terraform-state')

        # 模型缓存
        self.models = {}

        # 工作目录
        self.output_dir = Path('/workspace/outputs')
        self.output_dir.mkdir(exist_ok=True)

    def load_model(self, task_type):
        """加载模型 (带缓存)"""
        if task_type in self.models:
            print(f"✅ Using cached model: {task_type}")
            return self.models[task_type]

        print(f"📦 Loading model: {task_type}")

        if task_type == "ti2v-5B":
            from wan.textimage2video import WanTI2V
            model = WanTI2V(
                ckpt_dir="/mnt/efs/models/Wan2.2-TI2V-5B",
                offload_model=False,
                convert_model_dtype=True
            )
        elif task_type == "t2v-A14B":
            from wan.text2video import WanT2V
            model = WanT2V(
                ckpt_dir="/mnt/efs/models/Wan2.2-T2V-A14B",
                offload_model=False,
                convert_model_dtype=True
            )
        elif task_type == "i2v-A14B":
            from wan.image2video import WanI2V
            model = WanI2V(
                ckpt_dir="/mnt/efs/models/Wan2.2-I2V-A14B",
                offload_model=False,
                convert_model_dtype=True
            )
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        self.models[task_type] = model
        print(f"✅ Model loaded: {task_type}")
        return model

    def update_task_status(self, task_id, status=None, progress=None, result_url=None, error=None):
        """更新任务状态"""
        task_key = f"task:{task_id}"
        task_data = self.redis.get(task_key)

        if not task_data:
            print(f"⚠️  Task {task_id} not found in Redis")
            return

        task_data = json.loads(task_data)

        if status:
            task_data['status'] = status
        if progress is not None:
            task_data['progress'] = progress
        if result_url:
            task_data['result_url'] = result_url
        if error:
            task_data['error'] = error

        task_data['updated_at'] = datetime.utcnow().isoformat()

        # 保存回 Redis
        self.redis.setex(task_key, 86400, json.dumps(task_data))

        print(f"📊 Task {task_id}: status={status}, progress={progress}%")

    def upload_to_s3(self, local_path, task_id):
        """上传视频到 S3"""
        s3_key = f"wan-videos/{task_id}/{Path(local_path).name}"

        print(f"📤 Uploading to S3: s3://{self.s3_bucket}/{s3_key}")

        self.s3.upload_file(
            str(local_path),
            self.s3_bucket,
            s3_key,
            ExtraArgs={'ContentType': 'video/mp4'}
        )

        # 生成预签名 URL (7天有效)
        url = self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.s3_bucket, 'Key': s3_key},
            ExpiresIn=604800
        )

        print(f"✅ Uploaded: {url}")
        return url

    def process_task(self, task_id, task_data):
        """处理单个任务"""
        try:
            print(f"\n{'='*60}")
            print(f"🎬 Processing task: {task_id}")
            print(f"   Prompt: {task_data['prompt'][:50]}...")
            print(f"   Type: {task_data['task_type']}")
            print(f"   Resolution: {task_data['resolution']}")
            print(f"{'='*60}\n")

            # 更新状态为处理中
            self.update_task_status(task_id, status="processing", progress=10)

            # 加载模型
            model = self.load_model(task_data['task_type'])
            self.update_task_status(task_id, progress=20)

            # 清理 GPU 缓存
            torch.cuda.empty_cache()

            # 生成视频
            print(f"🎥 Generating video...")
            output_path = self.output_dir / f"{task_id}.mp4"

            # 这里需要根据实际的 generate 方法调整
            video = model.generate(
                prompt=task_data['prompt'],
                size=task_data['resolution'],
                sample_steps=50,
                # 添加进度回调
                progress_callback=lambda step, total: self.update_task_status(
                    task_id,
                    progress=20 + int((step / total) * 60)
                )
            )

            self.update_task_status(task_id, progress=85)

            # 保存视频 (假设 video 是一个可保存的对象)
            # 实际实现需要根据 wan2.2 的输出格式调整
            # video.save(output_path)

            # 上传到 S3
            s3_url = self.upload_to_s3(output_path, task_id)
            self.update_task_status(task_id, progress=95)

            # 删除本地文件
            output_path.unlink()

            # 完成
            self.update_task_status(
                task_id,
                status="completed",
                progress=100,
                result_url=s3_url
            )

            print(f"✅ Task {task_id} completed!")
            print(f"   Video URL: {s3_url}\n")

            # 清理内存
            torch.cuda.empty_cache()

        except Exception as e:
            print(f"❌ Task {task_id} failed: {str(e)}")
            import traceback
            traceback.print_exc()

            self.update_task_status(
                task_id,
                status="failed",
                error=str(e)
            )

    def run(self, task_types=None, poll_interval=1):
        """运行 Worker 主循环

        Args:
            task_types: 处理的任务类型列表，None 则处理所有类型
            poll_interval: 轮询间隔(秒)
        """
        if task_types is None:
            task_types = ["ti2v-5B", "t2v-A14B", "i2v-A14B"]

        # 构建队列名称 (优先级1在前)
        queues = []
        for task_type in task_types:
            queues.append(f"queue:{task_type}:priority_1")  # 高优先级
        for task_type in task_types:
            queues.append(f"queue:{task_type}:priority_0")  # 普通优先级

        print(f"\n🎯 Worker started")
        print(f"   Listening to queues: {queues}")
        print(f"   Press Ctrl+C to stop\n")

        while True:
            try:
                # 从队列中获取任务 (阻塞式，超时5秒)
                result = self.redis.brpop(queues, timeout=5)

                if result is None:
                    # 没有任务，继续等待
                    continue

                queue_name, task_id = result

                # 获取任务数据
                task_data = self.redis.get(f"task:{task_id}")
                if not task_data:
                    print(f"⚠️  Task {task_id} not found, skipping")
                    continue

                task_data = json.loads(task_data)

                # 处理任务
                self.process_task(task_id, task_data)

            except KeyboardInterrupt:
                print("\n👋 Worker stopped by user")
                break
            except Exception as e:
                print(f"❌ Worker error: {str(e)}")
                import traceback
                traceback.print_exc()
                time.sleep(poll_interval)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='GPU Worker for Wan2.2')
    parser.add_argument('--gpu-id', type=int, default=None, help='GPU ID to use')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')
    parser.add_argument('--task-types', nargs='+', default=None,
                        help='Task types to process (e.g., ti2v-5B t2v-A14B)')

    args = parser.parse_args()

    worker = GPUWorker(
        gpu_id=args.gpu_id,
        redis_host=args.redis_host,
        redis_port=args.redis_port
    )

    worker.run(task_types=args.task_types)
