"""
FastAPI 服务器 - 接收用户请求并分发到 GPU 集群
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import redis
import json
import uuid
from datetime import datetime

app = FastAPI(title="Wan2.2 Video Generation API")

# Redis 连接 (任务队列)
redis_client = redis.Redis(
    host='redis-cluster.default.svc.cluster.local',
    port=6379,
    decode_responses=True
)

class VideoRequest(BaseModel):
    prompt: str
    resolution: str = "1280*704"
    task_type: str = "ti2v-5B"  # ti2v-5B, t2v-A14B, i2v-A14B
    image_url: Optional[str] = None  # For I2V tasks
    priority: int = 0  # 0=normal, 1=high
    callback_url: Optional[str] = None

class TaskStatus(BaseModel):
    task_id: str
    status: str  # queued, processing, completed, failed
    progress: int  # 0-100
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

@app.post("/api/v1/generate", response_model=dict)
async def create_video_task(request: VideoRequest):
    """创建视频生成任务"""

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 构造任务数据
    task_data = {
        "task_id": task_id,
        "prompt": request.prompt,
        "resolution": request.resolution,
        "task_type": request.task_type,
        "image_url": request.image_url,
        "callback_url": request.callback_url,
        "status": "queued",
        "progress": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # 保存任务状态
    redis_client.setex(
        f"task:{task_id}",
        86400,  # 24小时过期
        json.dumps(task_data)
    )

    # 推送到对应的任务队列
    queue_name = f"queue:{request.task_type}:priority_{request.priority}"
    redis_client.lpush(queue_name, task_id)

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Task created successfully",
        "status_url": f"/api/v1/status/{task_id}"
    }

@app.get("/api/v1/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询任务状态"""

    task_data = redis_client.get(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatus(**json.loads(task_data))

@app.get("/api/v1/health")
async def health_check():
    """健康检查"""

    # 检查 Redis 连接
    try:
        redis_client.ping()
        redis_ok = True
    except:
        redis_ok = False

    # 检查队列长度
    queue_lengths = {}
    for task_type in ["ti2v-5B", "t2v-A14B", "i2v-A14B"]:
        for priority in [0, 1]:
            queue_name = f"queue:{task_type}:priority_{priority}"
            queue_lengths[queue_name] = redis_client.llen(queue_name)

    return {
        "status": "healthy" if redis_ok else "unhealthy",
        "redis": "connected" if redis_ok else "disconnected",
        "queues": queue_lengths
    }

@app.get("/api/v1/metrics")
async def get_metrics():
    """获取系统指标"""

    # 统计各状态的任务数
    stats = {
        "queued": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0
    }

    # 这里可以从监控系统获取更详细的指标
    # 例如: Prometheus, CloudWatch, etc.

    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
