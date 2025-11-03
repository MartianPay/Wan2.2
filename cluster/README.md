# Wan2.2 GPU 集群部署指南

## 📋 目录

1. [架构概述](#架构概述)
2. [技术栈](#技术栈)
3. [部署步骤](#部署步骤)
4. [性能优化](#性能优化)
5. [监控告警](#监控告警)
6. [成本优化](#成本优化)

## 🏗️ 架构概述

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Application Load Balancer            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              API Server (FastAPI) x 2 replicas              │
│  - 接收用户请求                                              │
│  - 任务入队                                                  │
│  - 状态查询                                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Redis Cluster (任务队列)                   │
│  - 按任务类型分队列: ti2v-5B, t2v-A14B, i2v-A14B            │
│  - 优先级队列支持                                            │
│  - 任务状态存储                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    GPU Worker Pool                          │
│  ┌────────────────┬────────────────┬────────────────┐        │
│  │ TI2V-5B Worker │ TI2V-5B Worker │ TI2V-5B Worker │        │
│  │   (A10G 24GB)  │   (A10G 24GB)  │   (A10G 24GB)  │        │
│  │   g5.xlarge    │   g5.xlarge    │   g5.xlarge    │        │
│  └────────────────┴────────────────┴────────────────┘        │
│  ┌────────────────┬────────────────┐                         │
│  │ A14B Worker    │ A14B Worker    │                         │
│  │ (A100 40GB)    │ (A100 40GB)    │                         │
│  │ p4d.24xlarge   │ p4d.24xlarge   │                         │
│  └────────────────┴────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       共享存储                               │
│  - EFS: 模型文件共享 (1TB+)                                 │
│  - S3: 生成的视频输出                                        │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| **容器编排** | Kubernetes (EKS) | GPU 资源调度、自动扩缩容 |
| **GPU 管理** | NVIDIA GPU Operator | GPU 设备发现和管理 |
| **API 网关** | FastAPI | 接收 HTTP 请求 |
| **任务队列** | Redis | 任务分发和状态管理 |
| **Worker** | Python + PyTorch | GPU 视频生成 |
| **存储** | EFS + S3 | 模型共享 + 视频存储 |
| **监控** | Prometheus + Grafana | 系统监控 |
| **日志** | CloudWatch / ELK | 日志聚合 |
| **CI/CD** | GitHub Actions | 自动部署 |

## 📦 部署步骤

### 1. 创建 EKS 集群

```bash
# 使用 eksctl 创建集群
eksctl create cluster \
  --name wan22-cluster \
  --region us-east-2 \
  --version 1.28 \
  --node-type m5.large \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 5

# 创建 GPU 节点组 (A10G)
eksctl create nodegroup \
  --cluster wan22-cluster \
  --region us-east-2 \
  --name gpu-a10g-nodes \
  --node-type g5.xlarge \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 10 \
  --node-labels gpu-type=a10g \
  --node-taints nvidia.com/gpu=true:NoSchedule

# 创建 GPU 节点组 (A100)
eksctl create nodegroup \
  --cluster wan22-cluster \
  --region us-east-2 \
  --name gpu-a100-nodes \
  --node-type p4d.24xlarge \
  --nodes 1 \
  --nodes-min 0 \
  --nodes-max 5 \
  --node-labels gpu-type=a100 \
  --node-taints nvidia.com/gpu=true:NoSchedule
```

### 2. 安装 NVIDIA GPU Operator

```bash
# 添加 Helm repo
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# 安装 GPU Operator
helm install --wait --generate-name \
  -n gpu-operator --create-namespace \
  nvidia/gpu-operator \
  --set driver.enabled=false  # AWS GPU AMI 已包含驱动

# 验证 GPU 可用
kubectl get nodes "-o=custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu"
```

### 3. 创建 EFS 文件系统

```bash
# 使用 AWS CLI 创建 EFS
aws efs create-file-system \
  --region us-east-2 \
  --performance-mode generalPurpose \
  --throughput-mode bursting \
  --encrypted \
  --tags Key=Name,Value=wan22-models

# 记录 EFS ID (例如: fs-12345678)
EFS_ID=$(aws efs describe-file-systems --region us-east-2 --query 'FileSystems[?Name==`wan22-models`].FileSystemId' --output text)

# 安装 EFS CSI Driver
kubectl apply -k "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-1.5"
```

### 4. 上传模型到 EFS

```bash
# 挂载 EFS 到 EC2 实例
sudo mount -t efs -o tls $EFS_ID:/ /mnt/efs

# 下载模型
mkdir -p /mnt/efs/models
cd /mnt/efs/models

huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir ./Wan2.2-TI2V-5B
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B --local-dir ./Wan2.2-T2V-A14B
huggingface-cli download Wan-AI/Wan2.2-I2V-A14B --local-dir ./Wan2.2-I2V-A14B
```

### 5. 部署服务

```bash
# 更新 k8s-deployment.yaml 中的 EFS ID
sed -i "s/fs-xxxxx/$EFS_ID/g" cluster/k8s-deployment.yaml

# 创建命名空间
kubectl create namespace wan22

# 部署所有组件
kubectl apply -f cluster/k8s-deployment.yaml

# 查看部署状态
kubectl get pods -n wan22 -w
```

### 6. 获取 API 地址

```bash
# 获取 LoadBalancer 地址
kubectl get svc api-server -n wan22

# 测试 API
API_URL=$(kubectl get svc api-server -n wan22 -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

curl http://$API_URL/api/v1/health
```

## 🎯 使用示例

### 提交视频生成任务

```bash
curl -X POST http://$API_URL/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cat playing piano in a jazz club",
    "resolution": "1280*704",
    "task_type": "ti2v-5B",
    "priority": 0
  }'

# 响应
{
  "task_id": "abc123-def456-...",
  "status": "queued",
  "status_url": "/api/v1/status/abc123-def456-..."
}
```

### 查询任务状态

```bash
curl http://$API_URL/api/v1/status/abc123-def456-...

# 响应
{
  "task_id": "abc123-def456-...",
  "status": "completed",
  "progress": 100,
  "result_url": "https://s3.amazonaws.com/...",
  "created_at": "2025-11-03T10:00:00Z",
  "updated_at": "2025-11-03T10:05:30Z"
}
```

## ⚡ 性能优化

### 1. GPU 利用率优化

**批处理 (Batching)**
```python
# 在 gpu_worker.py 中实现动态批处理
class GPUWorker:
    def process_batch(self, tasks):
        """批量处理多个任务"""
        prompts = [task['prompt'] for task in tasks]

        # 批量生成 (减少模型加载开销)
        videos = model.generate_batch(prompts)

        for video, task in zip(videos, tasks):
            self.upload_to_s3(video, task['task_id'])
```

**模型预加载**
```python
# Worker 启动时预加载所有模型
worker.load_model("ti2v-5B")
worker.load_model("t2v-A14B")
```

### 2. 内存优化

```yaml
# 使用 MIG 分割 A100 (多租户)
apiVersion: v1
kind: ConfigMap
metadata:
  name: mig-config
data:
  config.yaml: |
    version: v1
    mig-configs:
      all-3g.20gb:
        - devices: [0]
          mig-devices:
            3g.20gb: 3  # 将1个A100分成3个20GB实例
```

### 3. 网络优化

```yaml
# 使用 NodeLocal DNSCache 加速 DNS 查询
# 使用 VPC Endpoints 访问 S3/ECR，避免公网流量
```

## 📊 监控告警

### 安装 Prometheus + Grafana

```bash
# 添加 Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 安装 Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

# 访问 Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# 用户名: admin, 密码: prom-operator
```

### 关键指标

| 指标 | 阈值 | 告警 |
|------|------|------|
| GPU 利用率 | < 60% | 资源浪费 |
| 队列长度 | > 100 | 需要扩容 |
| 任务失败率 | > 5% | 服务异常 |
| API 响应时间 | > 500ms | 性能下降 |
| Worker 重启次数 | > 3/hour | OOM 或崩溃 |

## 💰 成本优化

### 1. 使用 Spot 实例 (节省 70%)

```bash
eksctl create nodegroup \
  --cluster wan22-cluster \
  --name gpu-spot-nodes \
  --node-type g5.xlarge \
  --spot \
  --instance-types g5.xlarge,g5.2xlarge \
  --nodes-min 0 \
  --nodes-max 20
```

### 2. 按需扩缩容

```yaml
# Cluster Autoscaler - 根据负载自动增减节点
# HPA - 根据队列长度自动增减 Pod
# Keda - 更高级的自动扩缩容
```

### 3. 成本预估

| 配置 | 实例类型 | 成本/小时 | GPU数 | 建议用途 |
|------|---------|----------|-------|---------|
| **TI2V-5B** | g5.xlarge | $1.006 | 1x A10G | 480P/720P 视频 |
| **TI2V-5B** | g5.2xlarge | $1.212 | 1x A10G | 同上，更多CPU内存 |
| **A14B** | p4d.24xlarge | $32.77 | 8x A100 | 720P 高质量视频 |
| **A14B** | g5.12xlarge | $5.672 | 4x A10G | 多任务并行 |

**月成本估算 (24/7 运行):**
- 2x g5.xlarge (TI2V): ~$1,450/月
- 1x p4d.24xlarge (A14B): ~$23,600/月
- **Spot 实例可节省 70%**: ~$7,500/月

## 🔐 安全最佳实践

1. **IRSA**: 使用 IAM Roles for Service Accounts
2. **Secrets**: 使用 AWS Secrets Manager 存储 API Keys
3. **Network Policy**: 限制 Pod 间通信
4. **私有子网**: GPU 节点放在私有子网
5. **S3 加密**: 启用 S3 Server-Side Encryption

## 🚀 其他推荐方案

### 方案 B: Ray on Kubernetes

```python
# 使用 Ray Serve 更简单的部署
from ray import serve

@serve.deployment(num_replicas=3, ray_actor_options={"num_gpus": 1})
class Wan22Deployment:
    def __init__(self):
        self.model = load_model()

    async def __call__(self, request):
        return await self.model.generate(request.prompt)

serve.run(Wan22Deployment.bind())
```

### 方案 C: SageMaker + Lambda

- 使用 SageMaker Async Inference
- Lambda 处理 API 请求
- 成本更低，但冷启动较慢

## 📚 参考资料

- [NVIDIA GPU Operator 文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/getting-started.html)
- [EKS GPU 最佳实践](https://docs.aws.amazon.com/eks/latest/userguide/gpu-ami.html)
- [Ray 分布式计算](https://docs.ray.io/en/latest/)
- [Kubernetes HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)

---

**总结**: 推荐使用 **Kubernetes + Redis + GPU Workers** 方案，结合 Spot 实例和自动扩缩容，在保证性能的同时控制成本。
