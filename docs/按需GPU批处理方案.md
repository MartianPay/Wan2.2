# Wan2.2 按需 GPU 批处理方案

> **核心理念**: 零常驻成本 + Spot 实例 + 批量处理
> **成本节省**: 相比常驻集群节省 **85-95%**
> **更新日期**: 2025-11-03

---

## 📋 目录

- [1. 方案概述](#1-方案概述)
- [2. 架构设计](#2-架构设计)
- [3. 任务累积策略](#3-任务累积策略)
- [4. 按需创建实例](#4-按需创建实例)
- [5. 批量处理流程](#5-批量处理流程)
- [6. 成本分析](#6-成本分析)
- [7. 完整实现代码](#7-完整实现代码)
- [8. 监控与告警](#8-监控与告警)
- [9. 最佳实践](#9-最佳实践)

---

## 1. 方案概述

### 1.1 核心思想

**不维护常驻 GPU 集群**，而是：

1. ✅ 用户任务累积在 Redis 队列中
2. ✅ 达到触发条件（数量/时间/Spot价格）时自动创建 GPU 实例
3. ✅ 批量处理所有任务
4. ✅ 处理完成后立即销毁实例
5. ✅ **零常驻成本，用多少付多少**

### 1.2 适用场景

| 场景 | 是否适合 |
|------|---------|
| **任务不连续** (每天几十到几百个) | ✅ **非常适合** |
| **可接受延迟** (15-30分钟) | ✅ **非常适合** |
| **成本敏感** | ✅ **非常适合** |
| **任务连续** (每分钟都有) | ❌ 不适合，用常驻集群 |
| **实时响应** (< 1分钟) | ❌ 不适合，用常驻集群 |

### 1.3 成本对比

| 方案 | 月成本 | 适用场景 |
|------|--------|---------|
| **常驻集群** (2x g5.xlarge 24/7) | $1,450/月 | 任务连续，实时响应 |
| **按需批处理** (每天2小时 Spot) | **$120/月** | 任务不连续，可接受延迟 |
| **节省比例** | **92%** | - |

**示例计算:**
```
按需方案:
- 每天累积 200 个任务
- 批量处理需要 2 小时 (10 个 GPU)
- Spot 价格: g5.xlarge = $0.30/小时 (70% off)
- 日成本: 10 GPU × 2小时 × $0.30 = $6/天
- 月成本: $6 × 30 = $180/月

如果选择低谷时段 (凌晨2-4点):
- Spot 价格更低: $0.20/小时
- 月成本: 10 × 2 × $0.20 × 30 = $120/月
```

---

## 2. 架构设计

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                         用户请求层                            │
│  API Gateway (Lambda + API Gateway) - 接收任务                │
│  - 任务验证                                                   │
│  - 推送到 Redis 队列                                          │
│  - 返回 task_id                                               │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    任务队列层 (Redis)                         │
│  - ElastiCache Redis (按需付费)                              │
│  - 任务队列: List 结构                                        │
│  - 任务状态: Hash 结构                                        │
│  - 成本: $50/月 (最小配置)                                    │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                 触发器层 (Lambda / EventBridge)               │
│                                                               │
│  触发条件 (任意满足即触发):                                   │
│  1️⃣  队列任务数 >= 100                                        │
│  2️⃣  距上次处理 >= 4 小时                                     │
│  3️⃣  定时触发 (每天凌晨2点)                                   │
│  4️⃣  Spot 价格 < $0.25/小时                                  │
│                                                               │
│  动作:                                                        │
│  → 计算需要的 GPU 数量                                        │
│  → 获取当前最佳 Spot 价格                                     │
│  → 触发 Step Functions 编排                                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│            编排层 (AWS Step Functions)                        │
│                                                               │
│  Step 1: 创建 Spot Fleet                                     │
│    - Launch Template: GPU AMI + 初始化脚本                   │
│    - Spot Price: 当前最低价 + 10%                            │
│    - Instance Types: g5.xlarge, g5.2xlarge (多种提高成功率) │
│    - Target Capacity: 根据队列长度计算                       │
│                                                               │
│  Step 2: 等待实例就绪 (最多 10 分钟)                         │
│    - 轮询 EC2 状态                                            │
│    - 等待 User Data 执行完成                                 │
│                                                               │
│  Step 3: 批量处理任务                                        │
│    - 每个实例从 Redis 拉取任务                               │
│    - 并行处理                                                │
│    - 上传结果到 S3                                           │
│    - 更新任务状态                                            │
│                                                               │
│  Step 4: 监控处理进度                                        │
│    - 检查 Redis 队列长度                                     │
│    - 检查实例是否空闲                                        │
│                                                               │
│  Step 5: 清理资源                                            │
│    - 终止 Spot Fleet                                         │
│    - 删除临时安全组                                          │
│    - 发送完成通知                                            │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│              GPU 处理层 (EC2 Spot Instances)                  │
│                                                               │
│  User Data 初始化脚本:                                        │
│  1. 挂载 EFS (模型文件)                                       │
│  2. 拉取 Docker 镜像 (from ECR)                              │
│  3. 启动 GPU Worker 容器                                     │
│  4. Worker 从 Redis 获取任务                                 │
│  5. 处理完成后自动关机 (节省成本)                            │
│                                                               │
│  ┌────────────┬────────────┬────────────┬──────────┐         │
│  │ Spot GPU 1 │ Spot GPU 2 │ Spot GPU 3 │   ...    │         │
│  │ g5.xlarge  │ g5.xlarge  │ g5.xlarge  │          │         │
│  │ $0.20/hr   │ $0.20/hr   │ $0.20/hr   │          │         │
│  └────────────┴────────────┴────────────┴──────────┘         │
│                                                               │
│  自动关机条件:                                                │
│  - Redis 队列为空                                            │
│  - 空闲超过 5 分钟                                           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    存储层                                     │
│  - EFS: 模型文件 (按需付费 $0.30/GB/月)                      │
│  - S3: 生成的视频 (按需付费 $0.023/GB/月)                    │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 关键组件说明

| 组件 | 技术 | 成本 | 说明 |
|------|------|------|------|
| **API 网关** | Lambda + API Gateway | $3/月 | 接收用户请求，按调用付费 |
| **任务队列** | ElastiCache Redis (t4g.micro) | $15/月 | 最小配置，按需付费 |
| **触发器** | Lambda + EventBridge | $1/月 | 按调用付费 |
| **编排** | Step Functions | $2/月 | 按状态转换付费 |
| **GPU 计算** | EC2 Spot (按需创建/销毁) | $120/月 | **仅在处理任务时计费** |
| **存储** | EFS + S3 | $100/月 | 模型 + 视频存储 |
| **总计** | - | **$241/月** | vs 常驻集群 $1,450/月 |

**成本节省: 83%**

---

## 3. 任务累积策略

### 3.1 触发条件设计

**多重触发条件 (任意满足即触发):**

```python
# lambda/batch_trigger.py
import boto3
import json
import redis
from datetime import datetime, timedelta

redis_client = redis.Redis(host='your-redis.cache.amazonaws.com', port=6379)
ec2 = boto3.client('ec2', region_name='us-east-2')

def should_trigger_batch():
    """判断是否应该触发批处理"""

    # 条件1: 队列任务数
    queue_length = get_total_queue_length()
    if queue_length >= 100:
        return True, f"Queue length ({queue_length}) >= 100"

    # 条件2: 距离上次处理时间
    last_batch_time = get_last_batch_time()
    if datetime.now() - last_batch_time >= timedelta(hours=4):
        if queue_length >= 20:  # 至少有20个任务
            return True, f"4 hours passed, queue has {queue_length} tasks"

    # 条件3: Spot 价格低点
    spot_price = get_current_spot_price('g5.xlarge', 'us-east-2a')
    if spot_price < 0.25 and queue_length >= 50:
        return True, f"Spot price low (${spot_price}), queue has {queue_length} tasks"

    # 条件4: 定时触发 (每天凌晨2点)
    if is_scheduled_time() and queue_length >= 10:
        return True, f"Scheduled batch time, queue has {queue_length} tasks"

    return False, "No trigger condition met"

def get_total_queue_length():
    """获取所有队列的总长度"""
    total = 0
    for task_type in ['ti2v-5B', 't2v-A14B', 'i2v-A14B']:
        for priority in [0, 1]:
            queue_name = f"queue:{task_type}:priority_{priority}"
            total += redis_client.llen(queue_name)
    return total

def get_current_spot_price(instance_type, az):
    """获取当前 Spot 价格"""
    response = ec2.describe_spot_price_history(
        InstanceTypes=[instance_type],
        AvailabilityZone=az,
        ProductDescriptions=['Linux/UNIX'],
        MaxResults=1
    )
    return float(response['SpotPriceHistory'][0]['SpotPrice'])

def get_last_batch_time():
    """获取上次批处理时间"""
    last_time = redis_client.get('last_batch_time')
    if last_time:
        return datetime.fromisoformat(last_time.decode())
    return datetime.min

def is_scheduled_time():
    """检查是否到了定时批处理时间"""
    now = datetime.now()
    # 每天凌晨 2:00-2:10
    return now.hour == 2 and now.minute < 10

def lambda_handler(event, context):
    """Lambda 入口函数"""

    should_trigger, reason = should_trigger_batch()

    if should_trigger:
        print(f"✅ Triggering batch: {reason}")

        # 计算需要的 GPU 数量
        queue_length = get_total_queue_length()
        gpu_count = calculate_gpu_count(queue_length)

        # 触发 Step Functions
        sfn = boto3.client('stepfunctions')
        sfn.start_execution(
            stateMachineArn='arn:aws:states:us-east-2:123456789012:stateMachine:wan22-batch-processor',
            input=json.dumps({
                'gpu_count': gpu_count,
                'queue_length': queue_length,
                'trigger_reason': reason
            })
        )

        # 更新上次批处理时间
        redis_client.set('last_batch_time', datetime.now().isoformat())

        return {'triggered': True, 'reason': reason, 'gpu_count': gpu_count}
    else:
        print(f"⏸️  Not triggering: {reason}")
        return {'triggered': False, 'reason': reason}

def calculate_gpu_count(queue_length):
    """根据队列长度计算需要的 GPU 数量"""

    # 假设每个 GPU 每小时处理 20 个任务
    # 目标: 2 小时内处理完所有任务

    tasks_per_gpu_per_2hours = 40  # 20 tasks/hour × 2 hours
    gpu_count = (queue_length + tasks_per_gpu_per_2hours - 1) // tasks_per_gpu_per_2hours

    # 限制范围
    gpu_count = max(2, min(gpu_count, 50))  # 最少2个，最多50个

    return gpu_count
```

### 3.2 EventBridge 定时检查

```json
{
  "scheduleName": "wan22-batch-trigger-check",
  "scheduleExpression": "rate(10 minutes)",
  "target": {
    "arn": "arn:aws:lambda:us-east-2:123456789012:function:batch-trigger"
  }
}
```

每 10 分钟检查一次是否应该触发批处理。

---

## 4. 按需创建实例

### 4.1 Spot Fleet 配置

**Launch Template (启动模板):**

```json
{
  "LaunchTemplateName": "wan22-gpu-worker-template",
  "LaunchTemplateData": {
    "ImageId": "ami-0a0c8eebcdd6dcbd0",  # Deep Learning AMI (Ubuntu)
    "InstanceType": "g5.xlarge",
    "IamInstanceProfile": {
      "Arn": "arn:aws:iam::123456789012:instance-profile/wan22-gpu-worker-role"
    },
    "SecurityGroupIds": ["sg-0123456789abcdef0"],
    "BlockDeviceMappings": [
      {
        "DeviceName": "/dev/sda1",
        "Ebs": {
          "VolumeSize": 100,
          "VolumeType": "gp3",
          "DeleteOnTermination": true
        }
      }
    ],
    "TagSpecifications": [
      {
        "ResourceType": "instance",
        "Tags": [
          {"Key": "Name", "Value": "wan22-spot-worker"},
          {"Key": "Project", "Value": "wan22"},
          {"Key": "Type", "Value": "batch-worker"}
        ]
      }
    ],
    "UserData": "<base64-encoded-script>"  # 见下文
  }
}
```

**User Data 初始化脚本:**

```bash
#!/bin/bash
# User Data Script - 自动初始化 GPU Worker

set -e

# 日志记录
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "🚀 Starting GPU Worker initialization..."

# 1. 挂载 EFS (模型文件)
EFS_ID="fs-0123456789abcdef0"
sudo mkdir -p /mnt/efs
sudo mount -t efs -o tls ${EFS_ID}:/ /mnt/efs
echo "✅ EFS mounted"

# 2. 配置 Docker
sudo usermod -aG docker ubuntu

# 3. 登录 ECR
aws ecr get-login-password --region us-east-2 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-2.amazonaws.com
echo "✅ ECR login successful"

# 4. 拉取 Docker 镜像
docker pull 123456789012.dkr.ecr.us-east-2.amazonaws.com/wan22-prod:latest
echo "✅ Docker image pulled"

# 5. 获取配置
REDIS_HOST=$(aws ssm get-parameter --name /wan22/redis-host --query 'Parameter.Value' --output text --region us-east-2)
S3_BUCKET=$(aws ssm get-parameter --name /wan22/s3-bucket --query 'Parameter.Value' --output text --region us-east-2)

# 6. 启动 GPU Worker
docker run -d \
  --name wan22-worker \
  --gpus all \
  --restart unless-stopped \
  -v /mnt/efs/models:/mnt/efs/models:ro \
  -e REDIS_HOST=${REDIS_HOST} \
  -e S3_BUCKET=${S3_BUCKET} \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:128 \
  -e AUTO_SHUTDOWN=true \
  123456789012.dkr.ecr.us-east-2.amazonaws.com/wan22-prod:latest \
  python /workspace/cluster/gpu_worker.py --redis-host ${REDIS_HOST}

echo "✅ GPU Worker started"

# 7. 监控并自动关机 (节省成本)
cat > /home/ubuntu/auto-shutdown.sh << 'EOF'
#!/bin/bash
# 如果 Redis 队列为空且 Worker 空闲超过 5 分钟，自动关机

IDLE_COUNT=0
MAX_IDLE=5  # 5 次检查 = 5 分钟

while true; do
  # 检查队列长度
  QUEUE_LENGTH=$(docker exec wan22-worker python -c "
import redis
r = redis.Redis(host='${REDIS_HOST}', port=6379)
total = 0
for task_type in ['ti2v-5B', 't2v-A14B', 'i2v-A14B']:
    for priority in [0, 1]:
        total += r.llen(f'queue:{task_type}:priority_{priority}')
print(total)
  ")

  if [ "$QUEUE_LENGTH" -eq 0 ]; then
    IDLE_COUNT=$((IDLE_COUNT + 1))
    echo "Queue empty, idle count: $IDLE_COUNT/$MAX_IDLE"

    if [ "$IDLE_COUNT" -ge "$MAX_IDLE" ]; then
      echo "💤 Shutting down idle instance..."
      sudo shutdown -h now
    fi
  else
    IDLE_COUNT=0
    echo "Processing tasks, queue length: $QUEUE_LENGTH"
  fi

  sleep 60  # 每分钟检查一次
done
EOF

chmod +x /home/ubuntu/auto-shutdown.sh
nohup /home/ubuntu/auto-shutdown.sh > /var/log/auto-shutdown.log 2>&1 &

echo "✅ Auto-shutdown monitor started"
echo "🎉 Initialization complete!"
```

### 4.2 创建 Spot Fleet

```python
# lambda/create_spot_fleet.py
import boto3
import base64

def create_spot_fleet(gpu_count, max_price=0.30):
    """创建 Spot Fleet Request"""

    ec2 = boto3.client('ec2', region_name='us-east-2')

    # 读取 User Data 脚本
    with open('user-data.sh', 'r') as f:
        user_data = f.read()
    user_data_b64 = base64.b64encode(user_data.encode()).decode()

    # Spot Fleet 配置
    spot_fleet_config = {
        'AllocationStrategy': 'lowestPrice',  # 选择最低价格
        'IamFleetRole': 'arn:aws:iam::123456789012:role/aws-ec2-spot-fleet-tagging-role',
        'TargetCapacity': gpu_count,
        'SpotPrice': str(max_price),  # 最高出价
        'LaunchTemplateConfigs': [
            {
                'LaunchTemplateSpecification': {
                    'LaunchTemplateName': 'wan22-gpu-worker-template',
                    'Version': '$Latest'
                },
                'Overrides': [
                    # 多种实例类型，提高成功率
                    {
                        'InstanceType': 'g5.xlarge',
                        'SubnetId': 'subnet-0123456789abcdef0',
                        'WeightedCapacity': 1.0
                    },
                    {
                        'InstanceType': 'g5.2xlarge',
                        'SubnetId': 'subnet-0123456789abcdef0',
                        'WeightedCapacity': 2.0  # 算2个容量
                    }
                ]
            }
        ],
        'TerminateInstancesWithExpiration': True,
        'Type': 'maintain',
        'ReplaceUnhealthyInstances': True
    }

    # 创建 Spot Fleet
    response = ec2.request_spot_fleet(SpotFleetRequestConfig=spot_fleet_config)

    fleet_id = response['SpotFleetRequestId']
    print(f"✅ Spot Fleet created: {fleet_id}")

    return fleet_id

def wait_for_fleet_ready(fleet_id, timeout=600):
    """等待 Spot Fleet 就绪"""

    ec2 = boto3.client('ec2', region_name='us-east-2')
    waiter = ec2.get_waiter('instance_running')

    # 获取 Fleet 中的实例
    response = ec2.describe_spot_fleet_instances(SpotFleetRequestId=fleet_id)
    instance_ids = [i['InstanceId'] for i in response['ActiveInstances']]

    print(f"⏳ Waiting for {len(instance_ids)} instances to be ready...")

    # 等待实例运行
    waiter.wait(
        InstanceIds=instance_ids,
        WaiterConfig={'Delay': 15, 'MaxAttempts': timeout // 15}
    )

    print(f"✅ {len(instance_ids)} instances are running")
    return instance_ids
```

### 4.3 Step Functions 状态机

```json
{
  "Comment": "Wan2.2 Batch Processing State Machine",
  "StartAt": "GetSpotPrice",
  "States": {
    "GetSpotPrice": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:get-spot-price",
      "Next": "CreateSpotFleet"
    },
    "CreateSpotFleet": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:create-spot-fleet",
      "Next": "WaitForInstances",
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "NotifyFailure"
        }
      ]
    },
    "WaitForInstances": {
      "Type": "Wait",
      "Seconds": 120,
      "Next": "CheckInstancesReady"
    },
    "CheckInstancesReady": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:check-instances-ready",
      "Next": "InstancesReadyChoice"
    },
    "InstancesReadyChoice": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.allReady",
          "BooleanEquals": true,
          "Next": "MonitorProcessing"
        }
      ],
      "Default": "WaitForInstances"
    },
    "MonitorProcessing": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:monitor-processing",
      "Next": "ProcessingCompleteChoice"
    },
    "ProcessingCompleteChoice": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.queueEmpty",
          "BooleanEquals": true,
          "Next": "CleanupResources"
        }
      ],
      "Default": "WaitForProcessing"
    },
    "WaitForProcessing": {
      "Type": "Wait",
      "Seconds": 60,
      "Next": "MonitorProcessing"
    },
    "CleanupResources": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:cleanup-resources",
      "Next": "NotifySuccess"
    },
    "NotifySuccess": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:notify-success",
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-2:123456789012:function:notify-failure",
      "End": true
    }
  }
}
```

---

## 5. 批量处理流程

### 5.1 完整流程图

```
用户提交任务
    ↓
任务进入 Redis 队列
    ↓
累积到 100 个任务 (或其他触发条件)
    ↓
Lambda 触发器检测到条件
    ↓
Step Functions 开始执行
    ↓
┌─────────────────────────────────┐
│ Step 1: 获取 Spot 最佳价格       │
│ - 查询最近1小时价格历史         │
│ - 选择最低价格的 AZ             │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Step 2: 创建 Spot Fleet          │
│ - 目标容量: 根据队列计算        │
│ - 最高出价: 最低价 × 1.1        │
│ - 多实例类型: 提高成功率        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Step 3: 等待实例就绪 (5-10分钟) │
│ - Spot 请求匹配                 │
│ - 实例启动                      │
│ - User Data 初始化              │
│ - Docker 容器启动               │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Step 4: 批量处理任务             │
│ - 每个 Worker 从 Redis 拉取     │
│ - 并行处理                      │
│ - 上传结果到 S3                 │
│ - 更新任务状态                  │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Step 5: 监控进度                 │
│ - 检查队列长度                  │
│ - 检查实例健康                  │
│ - 预估剩余时间                  │
└─────────────────────────────────┘
    ↓
队列清空
    ↓
┌─────────────────────────────────┐
│ Step 6: 自动清理                 │
│ - 实例空闲 5 分钟后自动关机     │
│ - 或 Step Functions 主动终止    │
│ - 删除 Spot Fleet               │
│ - 发送完成通知                  │
└─────────────────────────────────┘
    ↓
等待下一批任务累积...
```

### 5.2 时间线示例

```
00:00  用户开始提交任务
00:30  累积 30 个任务
01:00  累积 60 个任务
01:30  累积 100 个任务 ✅ 触发批处理!
01:31  创建 5 个 Spot 实例
01:41  实例就绪，开始处理 (10分钟启动时间)
03:11  处理完成 (100 任务 ÷ 5 GPU ÷ 20 任务/小时 = 1.5小时)
03:16  实例空闲 5 分钟，自动关机
03:17  批处理结束

总用时: 1小时46分钟 (包含10分钟启动)
GPU 计费时间: 5 实例 × 1.5 小时 = 7.5 GPU-小时
成本: 7.5 × $0.25 (Spot) = $1.88
```

---

## 6. 成本分析

### 6.1 详细成本对比

**场景 1: 每天 200 个任务**

| 方案 | 配置 | 日成本 | 月成本 | 说明 |
|------|------|--------|--------|------|
| **常驻集群** | 2x g5.xlarge (24/7) | $48 | $1,450 | 大部分时间空闲 |
| **按需批处理** | 10x g5.xlarge Spot (2小时/天) | $5 | $150 | 仅计费处理时间 |
| **节省** | - | $43 | $1,300 | **89.7%** |

**场景 2: 波动负载 (工作日多，周末少)**

| 天类型 | 任务数 | GPU 数 | 处理时间 | 日成本 |
|--------|--------|--------|----------|--------|
| **工作日** | 300 | 15 | 2 小时 | $7.50 |
| **周末** | 50 | 3 | 1.5 小时 | $1.13 |
| **月平均** | - | - | - | **$168** |

vs 常驻集群 $1,450/月，节省 **88.4%**

**场景 3: 突发高峰**

| 时期 | 日任务数 | GPU 数 | 处理时间 | 日成本 |
|------|----------|--------|----------|--------|
| **平时** | 100 | 5 | 2 小时 | $2.50 |
| **活动期** | 1000 | 50 | 2 小时 | $25.00 |

**优势:** 弹性无限，按需付费

### 6.2 成本组成详解

**按需批处理方案月成本 (每天200任务):**

| 项目 | 配置 | 月成本 | 说明 |
|------|------|--------|------|
| **Redis** | ElastiCache t4g.micro | $15 | 任务队列 + 状态存储 |
| **Lambda** | API Gateway + 触发器 | $3 | 按调用付费 (~10万次/月) |
| **Step Functions** | 状态转换 | $1 | 按转换付费 (~1000次/月) |
| **EFS** | 200 GB 存储 | $60 | 模型文件 |
| **S3** | 2 TB 存储 + 传输 | $50 | 视频存储 |
| **GPU 计算** | 10x g5.xlarge Spot × 2h × 30天 | $150 | **主要成本** |
| **数据传输** | 1 TB/月 | $10 | S3 下载流量 |
| **CloudWatch** | 日志 + 指标 | $5 | 监控 |
| **总计** | - | **$294** | |

**vs 常驻集群 $1,450/月，节省 79.7%**

### 6.3 Spot 价格优化

**Spot 价格波动示例 (g5.xlarge, us-east-2):**

| 时段 | 价格 | 说明 |
|------|------|------|
| **凌晨 2-6点** | $0.18-0.22/小时 | ✅ 最佳时段 |
| **上午 9-12点** | $0.28-0.35/小时 | ⚠️  价格上涨 |
| **下午 2-5点** | $0.30-0.40/小时 | ⚠️  高峰期 |
| **晚上 8-11点** | $0.25-0.32/小时 | 中等 |
| **On-Demand** | $1.006/小时 | 对比参考 |

**策略:**
1. 优先在凌晨 2-6 点批处理 (价格最低)
2. 设置最高出价 $0.30 (避免高峰期)
3. 多 AZ 部署 (提高成功率)

---

## 7. 完整实现代码

### 7.1 项目结构

```
Wan2.2/
├── lambda/
│   ├── batch_trigger.py          # 批处理触发器
│   ├── create_spot_fleet.py      # 创建 Spot Fleet
│   ├── monitor_processing.py     # 监控处理进度
│   ├── cleanup_resources.py      # 清理资源
│   └── requirements.txt
├── step-functions/
│   └── batch-processor.json      # Step Functions 定义
├── cloudformation/
│   ├── redis.yaml                # ElastiCache Redis
│   ├── iam-roles.yaml            # IAM 角色
│   └── launch-template.yaml      # EC2 Launch Template
├── scripts/
│   ├── user-data.sh              # EC2 初始化脚本
│   ├── deploy.sh                 # 一键部署
│   └── cost-report.py            # 成本报告生成
└── cluster/
    ├── gpu_worker.py             # GPU Worker (复用)
    └── api_server.py             # API Server (复用)
```

### 7.2 部署脚本

```bash
#!/bin/bash
# deploy.sh - 一键部署按需批处理方案

set -e

REGION="us-east-2"
STACK_NAME="wan22-batch-processing"

echo "🚀 Deploying Wan2.2 On-Demand Batch Processing..."

# 1. 部署 CloudFormation 基础设施
echo "📦 Deploying infrastructure..."
aws cloudformation deploy \
  --template-file cloudformation/main.yaml \
  --stack-name $STACK_NAME \
  --region $REGION \
  --capabilities CAPABILITY_IAM

# 2. 获取输出
REDIS_HOST=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`RedisEndpoint`].OutputValue' \
  --output text)

echo "✅ Redis endpoint: $REDIS_HOST"

# 3. 存储配置到 SSM Parameter Store
aws ssm put-parameter \
  --name /wan22/redis-host \
  --value $REDIS_HOST \
  --type String \
  --overwrite \
  --region $REGION

# 4. 打包并部署 Lambda 函数
echo "📦 Deploying Lambda functions..."
cd lambda
pip install -r requirements.txt -t package/
cd package && zip -r ../lambda.zip . && cd ..
zip -g lambda.zip *.py

aws lambda update-function-code \
  --function-name batch-trigger \
  --zip-file fileb://lambda.zip \
  --region $REGION

# 5. 部署 Step Functions
echo "📦 Deploying Step Functions..."
aws stepfunctions create-state-machine \
  --name wan22-batch-processor \
  --definition file://step-functions/batch-processor.json \
  --role-arn arn:aws:iam::123456789012:role/wan22-step-functions-role \
  --region $REGION || \
aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:$REGION:123456789012:stateMachine:wan22-batch-processor \
  --definition file://step-functions/batch-processor.json

echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Upload models to EFS"
echo "2. Build and push Docker image to ECR"
echo "3. Test with: aws lambda invoke --function-name batch-trigger output.json"
```

### 7.3 监控成本脚本

```python
# scripts/cost-report.py
import boto3
from datetime import datetime, timedelta
import pandas as pd

def generate_cost_report(days=30):
    """生成成本报告"""

    ce = boto3.client('ce', region_name='us-east-1')  # Cost Explorer 只在 us-east-1

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # 获取成本数据
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': str(start_date),
            'End': str(end_date)
        },
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'TAG', 'Key': 'Project'}
        ],
        Filter={
            'Tags': {
                'Key': 'Project',
                'Values': ['wan22']
            }
        }
    )

    # 解析数据
    costs = []
    for result in response['ResultsByTime']:
        date = result['TimePeriod']['Start']
        amount = float(result['Groups'][0]['Metrics']['UnblendedCost']['Amount'])
        costs.append({'date': date, 'cost': amount})

    df = pd.DataFrame(costs)

    # 统计
    total_cost = df['cost'].sum()
    avg_daily_cost = df['cost'].mean()
    max_daily_cost = df['cost'].max()

    print(f"📊 Cost Report (Last {days} days)")
    print(f"{'='*50}")
    print(f"Total Cost:        ${total_cost:.2f}")
    print(f"Average Daily:     ${avg_daily_cost:.2f}")
    print(f"Max Daily:         ${max_daily_cost:.2f}")
    print(f"Projected Monthly: ${avg_daily_cost * 30:.2f}")
    print(f"{'='*50}")

    # 按服务分组
    response_by_service = ce.get_cost_and_usage(
        TimePeriod={
            'Start': str(start_date),
            'End': str(end_date)
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'SERVICE'}
        ],
        Filter={
            'Tags': {
                'Key': 'Project',
                'Values': ['wan22']
            }
        }
    )

    print("\nCost by Service:")
    for group in response_by_service['ResultsByTime'][0]['Groups']:
        service = group['Keys'][0]
        amount = float(group['Metrics']['UnblendedCost']['Amount'])
        if amount > 0:
            print(f"  {service:30s} ${amount:8.2f}")

if __name__ == '__main__':
    generate_cost_report()
```

---

## 8. 监控与告警

### 8.1 CloudWatch 指标

**自定义指标推送:**

```python
# lambda/publish_metrics.py
import boto3

cloudwatch = boto3.client('cloudwatch', region_name='us-east-2')

def publish_batch_metrics(gpu_count, queue_length, processing_time):
    """发布批处理指标"""

    cloudwatch.put_metric_data(
        Namespace='Wan22/BatchProcessing',
        MetricData=[
            {
                'MetricName': 'GPUCount',
                'Value': gpu_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'QueueLength',
                'Value': queue_length,
                'Unit': 'Count'
            },
            {
                'MetricName': 'ProcessingTime',
                'Value': processing_time,
                'Unit': 'Seconds'
            },
            {
                'MetricName': 'CostPerBatch',
                'Value': gpu_count * processing_time / 3600 * 0.25,  # Spot 价格
                'Unit': 'None'
            }
        ]
    )
```

### 8.2 告警规则

```yaml
# cloudformation/alarms.yaml
Resources:
  HighCostAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-high-daily-cost
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Period: 86400  # 1 day
      EvaluationPeriods: 1
      Threshold: 50  # $50/day
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSTopic

  SpotInterruptionAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-spot-interruption
      MetricName: SpotFleetRequestInterruptions
      Namespace: AWS/EC2Spot
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 1
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSTopic

  QueueBacklogAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-queue-backlog
      MetricName: QueueLength
      Namespace: Wan22/BatchProcessing
      Statistic: Average
      Period: 3600  # 1 hour
      EvaluationPeriods: 2
      Threshold: 500  # 积压500个任务
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSTopic
```

---

## 9. 最佳实践

### 9.1 成本优化

1. **选择最佳时段**
   - 凌晨 2-6 点 Spot 价格最低
   - 使用 EventBridge 定时触发

2. **多 AZ 分散**
   - 不同 AZ 价格不同
   - 自动选择最低价格的 AZ

3. **实例多样性**
   - 支持 g5.xlarge, g5.2xlarge, g5.4xlarge
   - 提高 Spot 匹配成功率

4. **自动关机**
   - 队列清空后 5 分钟自动关机
   - 避免空闲浪费

### 9.2 可靠性优化

1. **Spot 中断处理**
   ```python
   # Worker 定期保存进度
   def process_task_with_checkpoints(task_id):
       for step in range(total_steps):
           # 处理
           result = process_step(step)

           # 每10步保存一次检查点
           if step % 10 == 0:
               save_checkpoint(task_id, step, result)

       # 完成
       mark_completed(task_id)

   # 重启后从检查点恢复
   def resume_from_checkpoint(task_id):
       checkpoint = load_checkpoint(task_id)
       continue_from_step(checkpoint['step'])
   ```

2. **任务重试机制**
   ```python
   # 失败任务自动重新入队
   def on_task_failed(task_id, error):
       task_data = redis.hgetall(f"task:{task_id}")
       retry_count = int(task_data.get('retry_count', 0))

       if retry_count < 3:  # 最多重试3次
           task_data['retry_count'] = retry_count + 1
           task_data['status'] = 'queued'
           redis.hmset(f"task:{task_id}", task_data)
           redis.lpush(f"queue:{task_type}", task_id)
       else:
           task_data['status'] = 'failed'
           task_data['error'] = error
   ```

3. **健康检查**
   ```bash
   # User Data 中添加健康检查
   while true; do
     if ! docker ps | grep wan22-worker; then
       echo "Worker crashed, restarting..."
       docker start wan22-worker
     fi
     sleep 60
   done
   ```

### 9.3 性能优化

1. **预热 EFS 连接**
   ```bash
   # User Data 中预先访问 EFS
   ls -R /mnt/efs/models > /dev/null 2>&1
   ```

2. **Docker 镜像优化**
   ```dockerfile
   # 使用多阶段构建减小镜像大小
   FROM nvidia/cuda:12.2.0-devel-ubuntu22.04 AS builder
   # ... 构建步骤

   FROM nvidia/cuda:12.2.0-base-ubuntu22.04
   # 只复制必要文件
   COPY --from=builder /app /app
   ```

3. **并行拉取**
   ```bash
   # 同时拉取镜像和挂载 EFS
   (docker pull ... &)
   (mount -t efs ... &)
   wait
   ```

---

## 总结

### 核心优势

| 对比项 | 常驻集群 | 按需批处理 |
|--------|---------|-----------|
| **月成本** | $1,450 | $294 | **节省 80%** |
| **响应时间** | < 1 分钟 | 15-30 分钟 |
| **弹性** | 有上限 (需扩容) | 无限弹性 |
| **复杂度** | 高 (K8s维护) | 中等 (Serverless) |
| **适用场景** | 连续任务 | 波动任务 |

### 推荐策略

**混合方案 (成本最优):**

```
低峰期 (任务 < 50/小时):
  → 使用按需批处理 (节省成本)

高峰期 (任务 > 100/小时):
  → 启动常驻集群 (保证响应速度)

策略切换自动化:
  → EventBridge + Lambda 根据任务量自动切换
```

**成本预估:**
- 低峰时段 (20小时/天): 按需批处理
- 高峰时段 (4小时/天): 常驻集群

月成本 = $294 + ($1,450 ÷ 30 × 4小时/天 × 30天 ÷ 24小时) = $294 + $242 = **$536/月**

vs 纯常驻 $1,450/月，节省 **63%**

---

**下一步行动:**

1. ✅ 部署基础设施 (Redis + Lambda + Step Functions)
2. ✅ 配置 Launch Template
3. ✅ 测试 Spot Fleet 创建/销毁
4. ✅ 压力测试批处理性能
5. ✅ 设置成本告警
6. ✅ 监控 Spot 中断率

**预期效果:**
- 成本降低 **80-90%**
- 保持高吞吐量 (100+ 视频/小时)
- 无限弹性扩展

---

**文档版本**: v1.0
**最后更新**: 2025-11-03
**维护者**: Engineering Team
