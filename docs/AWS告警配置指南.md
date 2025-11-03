# AWS SNS 告警配置完整指南

> **适用场景**: Wan2.2 GPU 集群监控告警
> **更新日期**: 2025-11-03
> **版本**: v1.0

---

## 📋 目录

- [1. SNS 支持的通知方式](#1-sns-支持的通知方式)
- [2. 短信 (SMS) 配置详解](#2-短信-sms-配置详解)
- [3. 电话 (Voice) 告警配置](#3-电话-voice-告警配置)
- [4. 常用告警场景配置](#4-常用告警场景配置)
- [5. 告警分级策略](#5-告警分级策略)
- [6. 高级配置](#6-高级配置)
- [7. 成本分析与优化](#7-成本分析与优化)
- [8. 完整配置示例](#8-完整配置示例)
- [9. 部署与测试](#9-部署与测试)
- [10. 最佳实践](#10-最佳实践)
- [11. 常见问题 FAQ](#11-常见问题-faq)

---

## 1. SNS 支持的通知方式

### 1.1 通知协议对比

| 通知方式 | 是否支持 | 成本 | 延迟 | 可靠性 | 推荐场景 |
|---------|---------|------|------|--------|---------|
| **📧 Email** | ✅ | 免费 (前1000封) | 秒级 | ⭐⭐⭐⭐ | 所有级别告警 |
| **📱 SMS (短信)** | ✅ | $0.00645/条 (中国) | 秒级 | ⭐⭐⭐⭐⭐ | Critical/High 告警 |
| **📞 Voice (电话)** | ✅ | $0.015/分钟 | 秒级 | ⭐⭐⭐⭐⭐ | 极度紧急告警 |
| **🔔 HTTP/HTTPS** | ✅ | 免费 | 秒级 | ⭐⭐⭐⭐ | Webhook 集成 |
| **📲 移动推送** | ✅ | 免费 (前100万) | 秒级 | ⭐⭐⭐⭐ | APP 通知 |
| **💬 AWS Chatbot** | ✅ | 免费 | 秒级 | ⭐⭐⭐⭐ | Slack/Teams |
| **📨 SQS** | ✅ | 免费 | 毫秒级 | ⭐⭐⭐⭐⭐ | 系统集成 |
| **λ Lambda** | ✅ | 按请求付费 | 毫秒级 | ⭐⭐⭐⭐⭐ | 自动化处理 |

### 1.2 通知方式选择建议

```
决策树:

是否需要立即处理?
├─ 是
│  └─ 是否在工作时间外?
│     ├─ 是 → SMS + 电话 (唤醒值班人员)
│     └─ 否 → SMS + Slack (快速响应)
└─ 否
   └─ Email + Slack (异步处理)
```

### 1.3 国际化支持

**SMS 支持的国家/地区:**
- ✅ 中国 (China): $0.00645/条
- ✅ 美国 (US): $0.00645/条
- ✅ 日本 (Japan): $0.07/条
- ✅ 全球 200+ 国家

**语音支持:**
- ✅ 通过 Amazon Connect 支持全球语音呼叫
- ✅ 支持多语言 TTS (文字转语音)

---

## 2. 短信 (SMS) 配置详解

### 2.1 基础配置

#### Step 1: 创建 SNS Topic

```bash
# 创建告警主题
aws sns create-topic \
  --name wan22-critical-alerts \
  --region us-east-2

# 输出:
# {
#   "TopicArn": "arn:aws:sns:us-east-2:123456789012:wan22-critical-alerts"
# }
```

#### Step 2: 添加短信订阅

```bash
# 订阅手机号 (使用国际格式)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:123456789012:wan22-critical-alerts \
  --protocol sms \
  --notification-endpoint "+8613800138000" \
  --region us-east-2

# 注意事项:
# 1. 手机号必须以 + 开头
# 2. 包含国家代码 (中国: +86)
# 3. 不需要确认 (短信订阅是自动激活的)
```

#### Step 3: 配置短信属性

```bash
# 设置短信类型为"事务型" (优先送达)
aws sns set-sms-attributes \
  --attributes \
    "DefaultSMSType=Transactional" \
    "MonthlySpendLimit=20" \
    "DefaultSenderID=Wan22" \
  --region us-east-2

# 参数说明:
# - DefaultSMSType:
#   * Transactional (事务型): 告警、验证码等,优先送达
#   * Promotional (促销型): 营销信息,成本低但可能延迟
# - MonthlySpendLimit: 每月SMS支出上限 (USD)
# - DefaultSenderID: 发件人ID (部分国家支持,中国不支持)
```

### 2.2 CloudFormation 配置

```yaml
# cloudformation/sms-topic.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: SNS Topic for SMS Alerts

Parameters:
  PhoneNumber1:
    Type: String
    Description: "Primary on-call phone number"
    Default: "+8613800138000"

  PhoneNumber2:
    Type: String
    Description: "Secondary on-call phone number"
    Default: "+8613800138001"

Resources:
  SMSAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-sms-alerts
      DisplayName: Wan22 SMS Alerts
      Subscription:
        # 主要联系人
        - Endpoint: !Ref PhoneNumber1
          Protocol: sms
        # 备用联系人
        - Endpoint: !Ref PhoneNumber2
          Protocol: sms

Outputs:
  TopicArn:
    Description: SNS Topic ARN
    Value: !Ref SMSAlertTopic
    Export:
      Name: !Sub "${AWS::StackName}-TopicArn"
```

### 2.3 发送测试短信

```bash
# 方法1: 直接发送
aws sns publish \
  --topic-arn arn:aws:sns:us-east-2:123456789012:wan22-critical-alerts \
  --message "【Wan22测试】这是一条测试短信,请忽略。" \
  --region us-east-2

# 方法2: 使用 Message Attributes (更好的格式化)
aws sns publish \
  --topic-arn arn:aws:sns:us-east-2:123456789012:wan22-critical-alerts \
  --message "【Wan22告警】\n告警: GPU内存不足\n时间: 2025-11-03 10:30\n严重程度: Critical" \
  --region us-east-2

# 方法3: 发送到单个手机号 (不通过 Topic)
aws sns publish \
  --phone-number "+8613800138000" \
  --message "【Wan22】直接发送的测试短信" \
  --region us-east-2
```

### 2.4 短信内容最佳实践

**推荐格式:**
```
【Wan22告警】
级别: Critical
事件: GPU集群成本超出预算
详情: 当前 $85/天 > 阈值 $50/天
时间: 11-03 10:30
查看: https://console.aws.amazon.com/...
```

**注意事项:**
- ✅ 使用中文【】作为标识符
- ✅ 控制长度 < 160 字符 (单条短信)
- ✅ 包含关键信息: 级别、事件、时间
- ✅ 提供操作链接
- ❌ 避免特殊符号 (可能被运营商过滤)
- ❌ 避免敏感词 (防火墙、攻击等)

### 2.5 短信发送限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| **每秒发送数** | 20条 | 可申请提升 |
| **每月预算** | $1 (默认) | 通过 MonthlySpendLimit 设置 |
| **单条长度** | 160字符 | 超过会拆分为多条 |
| **国际短信** | 支持 | 部分国家需要审批 |

**申请提额:**
```bash
# 1. 打开 AWS Support Center
# 2. 创建案例 (Case)
# 3. 选择 "Service Limit Increase"
# 4. 服务: SNS
# 5. 限制类型: SMS monthly spend limit
# 6. 新限制值: $50 (根据需求)
```

---

## 3. 电话 (Voice) 告警配置

### 3.1 架构方案

AWS SNS 本身不直接支持电话语音，需要通过 **Amazon Connect** 实现：

```
CloudWatch Alarm 触发
    ↓
SNS Topic
    ↓
Lambda Function (中转)
    ↓
Amazon Connect (拨打电话)
    ↓
Contact Flow (IVR 流程)
    ↓
用户接听并确认
```

### 3.2 创建 Amazon Connect 实例

#### Step 1: 创建 Connect 实例

```bash
# 通过 AWS Console 创建 (暂不支持 CLI 创建)
# 1. 打开 Amazon Connect 控制台
# 2. "Add an instance"
# 3. 选择 "Store users within Amazon Connect"
# 4. 添加管理员
# 5. 选择电话号码 (可选)
# 6. 创建

# 记录实例 ID: arn:aws:connect:us-east-2:123456789012:instance/abc-123-def
```

#### Step 2: 创建 Contact Flow (IVR 流程)

在 Amazon Connect 控制台中创建流程：

```
1. 登录 Connect 控制台
2. Routing → Contact flows → Create contact flow
3. 添加模块:

   [Entry] → [Play prompt]
             ↓
   "您好,这是 Wan22 系统紧急告警"
             ↓
   [Get customer input]
   "告警内容: {alarm_name}"
   "请按 1 确认收到告警"
   "按 2 重复播放"
   "按 3 转接到值班工程师"
             ↓
   [Branch on input]
   ├─ 按 1 → [Play prompt] "已确认,感谢" → [Disconnect]
   ├─ 按 2 → 返回播放
   └─ 按 3 → [Transfer to phone number]

4. 保存并发布
5. 记录 Contact Flow ID: abc-123-def-456
```

### 3.3 Lambda 函数实现

```python
# lambda/voice_alert.py
import boto3
import json
import os

connect = boto3.client('connect')

# 配置
CONNECT_INSTANCE_ID = os.environ['CONNECT_INSTANCE_ID']
CONTACT_FLOW_ID = os.environ['CONTACT_FLOW_ID']
SOURCE_PHONE_NUMBER = os.environ.get('SOURCE_PHONE_NUMBER', '+18005551234')

def lambda_handler(event, context):
    """
    SNS 触发后拨打电话告警
    """

    try:
        # 解析 SNS 消息
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])

        # 提取告警信息
        alarm_name = sns_message.get('AlarmName', 'Unknown')
        alarm_description = sns_message.get('AlarmDescription', 'No description')
        new_state = sns_message.get('NewStateValue', 'ALARM')

        # 拨打电话列表 (从环境变量读取)
        phone_numbers = os.environ['PHONE_NUMBERS'].split(',')

        results = []
        for phone_number in phone_numbers:
            phone_number = phone_number.strip()

            print(f"📞 Calling {phone_number} for alarm: {alarm_name}")

            # 拨打电话
            response = connect.start_outbound_voice_contact(
                DestinationPhoneNumber=phone_number,
                ContactFlowId=CONTACT_FLOW_ID,
                InstanceId=CONNECT_INSTANCE_ID,
                SourcePhoneNumber=SOURCE_PHONE_NUMBER,
                Attributes={
                    'alarm_name': alarm_name,
                    'alarm_description': alarm_description,
                    'alarm_state': new_state
                }
            )

            contact_id = response['ContactId']
            results.append({
                'phone': phone_number,
                'contact_id': contact_id,
                'status': 'initiated'
            })

            print(f"✅ Call initiated: Contact ID = {contact_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Voice alerts sent to {len(results)} recipients',
                'results': results
            })
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

### 3.4 部署 Lambda 函数

```yaml
# cloudformation/voice-alert-lambda.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Lambda function for voice alerts

Parameters:
  ConnectInstanceId:
    Type: String
    Description: Amazon Connect Instance ID

  ContactFlowId:
    Type: String
    Description: Contact Flow ID for voice alerts

  PhoneNumbers:
    Type: String
    Description: "Comma-separated phone numbers (e.g., +8613800138000,+8613800138001)"
    Default: "+8613800138000"

Resources:
  VoiceAlertFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: wan22-voice-alert
      Runtime: python3.10
      Handler: index.lambda_handler
      Role: !GetAtt VoiceAlertRole.Arn
      Timeout: 30
      Environment:
        Variables:
          CONNECT_INSTANCE_ID: !Ref ConnectInstanceId
          CONTACT_FLOW_ID: !Ref ContactFlowId
          PHONE_NUMBERS: !Ref PhoneNumbers
      Code:
        ZipFile: |
          # (粘贴上面的 Lambda 代码)

  VoiceAlertRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: ConnectAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - connect:StartOutboundVoiceContact
                  - connect:GetContactAttributes
                Resource: '*'

  # SNS Topic
  VoiceAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-voice-alerts
      Subscription:
        - Endpoint: !GetAtt VoiceAlertFunction.Arn
          Protocol: lambda

  # Lambda 调用权限
  VoiceAlertPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref VoiceAlertFunction
      Action: lambda:InvokeFunction
      Principal: sns.amazonaws.com
      SourceArn: !Ref VoiceAlertTopic

Outputs:
  TopicArn:
    Value: !Ref VoiceAlertTopic
    Description: Voice alert SNS topic ARN
```

### 3.5 测试语音告警

```bash
# 部署 CloudFormation
aws cloudformation deploy \
  --template-file voice-alert-lambda.yaml \
  --stack-name wan22-voice-alert \
  --parameter-overrides \
    ConnectInstanceId=abc-123-def \
    ContactFlowId=xyz-789-uvw \
    PhoneNumbers="+8613800138000,+8613800138001" \
  --capabilities CAPABILITY_IAM \
  --region us-east-2

# 获取 Topic ARN
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name wan22-voice-alert \
  --query 'Stacks[0].Outputs[?OutputKey==`TopicArn`].OutputValue' \
  --output text)

# 发送测试告警
aws sns publish \
  --topic-arn $TOPIC_ARN \
  --message '{
    "AlarmName": "测试告警",
    "AlarmDescription": "这是一个测试电话告警",
    "NewStateValue": "ALARM"
  }' \
  --region us-east-2
```

### 3.6 语音告警成本

| 项目 | 成本 | 说明 |
|------|------|------|
| **Amazon Connect** | $0.018/分钟 | 拨出电话 |
| **电话费** | 视运营商 | 国际长途可能更高 |
| **Lambda** | 免费 (前100万请求) | 几乎可忽略 |
| **单次告警** | ~$0.05 | 假设通话 2 分钟 |

**月成本预估:**
- 每月 5 次严重告警
- 每次拨打 2 个号码
- 每通电话 2 分钟
- 成本: 5 × 2 × 2 × $0.018 = **$0.36/月**

---

## 4. 常用告警场景配置

### 4.1 成本超支告警

```yaml
# cloudformation/cost-alarm.yaml
Resources:
  # SNS Topic (Email + SMS)
  CostAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-cost-alerts
      Subscription:
        # Email 通知
        - Endpoint: "finance@example.com"
          Protocol: email
        # SMS 通知 (财务负责人)
        - Endpoint: "+8613800138000"
          Protocol: sms

  # CloudWatch Alarm - 每日成本超过 $50
  DailyCostAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-daily-cost-exceeded
      AlarmDescription: "每日成本超过 $50 阈值"
      ActionsEnabled: true
      AlarmActions:
        - !Ref CostAlertTopic
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Dimensions:
        - Name: Currency
          Value: USD
      Period: 86400  # 1 天
      EvaluationPeriods: 1
      Threshold: 50
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching

  # CloudWatch Alarm - 月度成本超过 $1000
  MonthlyCostAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-monthly-cost-exceeded
      AlarmDescription: "月度成本超过 $1000 阈值"
      AlarmActions:
        - !Ref CostAlertTopic
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Dimensions:
        - Name: Currency
          Value: USD
      Period: 86400
      EvaluationPeriods: 1
      Threshold: 1000
      ComparisonOperator: GreaterThanThreshold
```

### 4.2 GPU 实例健康告警

```yaml
Resources:
  # GPU 实例状态检查失败
  GPUInstanceStatusAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-gpu-instance-unhealthy
      AlarmDescription: "GPU 实例状态检查失败"
      MetricName: StatusCheckFailed
      Namespace: AWS/EC2
      Statistic: Maximum
      Period: 300  # 5 分钟
      EvaluationPeriods: 2
      Threshold: 1
      ComparisonOperator: GreaterThanOrEqualToThreshold
      AlarmActions:
        - !Ref GPUAlertTopic

  # Spot 实例中断
  SpotInterruptionAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-spot-interrupted
      AlarmDescription: "Spot 实例被中断"
      MetricName: SpotFleetRequestInterruptions
      Namespace: AWS/EC2Spot
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 1
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref GPUAlertTopic

  # GPU 内存使用率过高
  GPUMemoryAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-gpu-memory-high
      AlarmDescription: "GPU 内存使用率超过 90%"
      MetricName: GPUMemoryUtilization
      Namespace: Wan22/GPU
      Statistic: Average
      Period: 300
      EvaluationPeriods: 2
      Threshold: 90
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref GPUAlertTopic
```

### 4.3 任务队列告警

```yaml
Resources:
  # 队列积压告警
  QueueBacklogAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-queue-backlog
      AlarmDescription: "任务队列积压超过 500 个"
      MetricName: QueueLength
      Namespace: Wan22/Queue
      Statistic: Average
      Period: 3600  # 1 小时
      EvaluationPeriods: 1
      Threshold: 500
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref QueueAlertTopic

  # 任务失败率过高
  TaskFailureRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-task-failure-rate-high
      AlarmDescription: "任务失败率超过 5%"
      Metrics:
        - Id: failure_rate
          Expression: "m1 / m2 * 100"
          Label: "Failure Rate %"

        - Id: m1
          MetricStat:
            Metric:
              Namespace: Wan22/Tasks
              MetricName: FailedTasks
            Period: 3600
            Stat: Sum
          ReturnData: false

        - Id: m2
          MetricStat:
            Metric:
              Namespace: Wan22/Tasks
              MetricName: TotalTasks
            Period: 3600
            Stat: Sum
          ReturnData: false

      EvaluationPeriods: 1
      Threshold: 5
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref QueueAlertTopic
```

### 4.4 Lambda 函数错误告警

```yaml
Resources:
  # Lambda 执行错误
  LambdaErrorAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-lambda-errors
      AlarmDescription: "Lambda 函数错误率超过 1%"
      MetricName: Errors
      Namespace: AWS/Lambda
      Dimensions:
        - Name: FunctionName
          Value: !Ref BatchTriggerFunction
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 2
      Threshold: 5  # 5 个错误
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref LambdaAlertTopic

  # Lambda 超时
  LambdaThrottleAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-lambda-throttled
      AlarmDescription: "Lambda 函数被限流"
      MetricName: Throttles
      Namespace: AWS/Lambda
      Dimensions:
        - Name: FunctionName
          Value: !Ref BatchTriggerFunction
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 1
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref LambdaAlertTopic
```

---

## 5. 告警分级策略

### 5.1 四级告警体系

| 级别 | 通知方式 | 响应时间 | 工作时间 | 非工作时间 |
|------|---------|----------|----------|-----------|
| **🔴 Critical** | SMS + 电话 + Email | 立即 (< 5分钟) | SMS + Slack | SMS + 电话 |
| **🟠 High** | SMS + Email + Slack | 15分钟 | SMS + Slack | SMS |
| **🟡 Medium** | Email + Slack | 1小时 | Slack + Email | Email |
| **🟢 Low** | Email | 4小时 | Email | Email (次日查看) |

### 5.2 告警分级示例

**Critical (🔴 严重):**
- 💰 每日成本 > $100
- 🔥 GPU 集群完全宕机
- 💾 数据丢失
- 🚨 安全事件 (未授权访问)

**High (🟠 高):**
- 💰 每日成本 > $50
- 🎮 GPU OOM (内存不足)
- 📊 Spot 实例中断率 > 20%
- ⚠️ 批处理失败

**Medium (🟡 中):**
- 📋 队列积压 > 500 个任务
- 🐌 任务平均处理时间 > 6 分钟
- 📈 API 响应时间 > 1 秒
- 🔄 Worker 重启次数 > 5 次/小时

**Low (🟢 低):**
- 📊 GPU 利用率 < 60% (资源浪费)
- 📉 流量下降 20%
- ℹ️ 日常报告和统计

### 5.3 CloudFormation 实现

```yaml
# cloudformation/alert-levels.yaml
Resources:
  # === Critical 级别 ===
  CriticalAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-critical
      DisplayName: Wan22 Critical Alerts
      Subscription:
        # SMS (CTO + 运维负责人)
        - Endpoint: "+8613800138000"
          Protocol: sms
        - Endpoint: "+8613800138001"
          Protocol: sms
        # Email
        - Endpoint: "critical@example.com"
          Protocol: email
        # Lambda (拨打电话 - 仅非工作时间)
        - Endpoint: !GetAtt ConditionalVoiceAlert.Arn
          Protocol: lambda

  # === High 级别 ===
  HighAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-high
      Subscription:
        # SMS (团队 leader)
        - Endpoint: "+8613800138000"
          Protocol: sms
        # Email
        - Endpoint: "team@example.com"
          Protocol: email
        # Slack
        - Endpoint: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
          Protocol: https

  # === Medium 级别 ===
  MediumAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-medium
      Subscription:
        # Email
        - Endpoint: "team@example.com"
          Protocol: email
        # Slack
        - Endpoint: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
          Protocol: https

  # === Low 级别 ===
  LowAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-low
      Subscription:
        # Email only
        - Endpoint: "alerts@example.com"
          Protocol: email

  # === 条件性语音告警 (仅非工作时间) ===
  ConditionalVoiceAlert:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: wan22-conditional-voice-alert
      Runtime: python3.10
      Handler: index.lambda_handler
      Role: !GetAtt VoiceAlertRole.Arn
      Code:
        ZipFile: |
          import boto3
          import json
          from datetime import datetime

          connect = boto3.client('connect')

          def lambda_handler(event, context):
              """仅在非工作时间拨打电话"""

              now = datetime.now()
              hour = now.hour
              weekday = now.weekday()  # 0=Monday, 6=Sunday

              # 工作时间: 周一到周五 9:00-18:00
              is_work_hours = (weekday < 5 and 9 <= hour < 18)

              if is_work_hours:
                  print("⏸️  工作时间,不拨打电话")
                  return {'statusCode': 200, 'suppressed': True}

              # 非工作时间,拨打电话
              print("📞 非工作时间,拨打紧急电话")
              # ... 拨打电话逻辑

              return {'statusCode': 200, 'suppressed': False}
```

---

## 6. 高级配置

### 6.1 告警抑制 (防止告警风暴)

```python
# lambda/alert_suppression.py
import boto3
import json
from datetime import datetime, timedelta
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# 配置
SUPPRESSION_TABLE = 'wan22-alert-suppression'
SUPPRESSION_WINDOW = 3600  # 1 小时

def lambda_handler(event, context):
    """
    告警抑制逻辑:
    - 相同告警 1 小时内只发送一次
    - 不同严重程度独立计数
    """

    table = dynamodb.Table(SUPPRESSION_TABLE)

    # 解析 SNS 消息
    sns_message = json.loads(event['Records'][0]['Sns']['Message'])

    alarm_name = sns_message.get('AlarmName', 'Unknown')
    severity = sns_message.get('Severity', 'MEDIUM')

    # 生成抑制 key
    suppression_key = f"{alarm_name}:{severity}"

    # 检查是否在抑制窗口内
    try:
        response = table.get_item(Key={'suppression_key': suppression_key})

        if 'Item' in response:
            last_sent = response['Item']['last_sent']
            last_sent_time = datetime.fromtimestamp(int(last_sent))

            if datetime.now() - last_sent_time < timedelta(seconds=SUPPRESSION_WINDOW):
                # 在抑制窗口内,累加计数
                suppressed_count = int(response['Item'].get('suppressed_count', 0)) + 1

                table.update_item(
                    Key={'suppression_key': suppression_key},
                    UpdateExpression='SET suppressed_count = :count',
                    ExpressionAttributeValues={':count': suppressed_count}
                )

                print(f"⏸️  抑制告警: {alarm_name} (已抑制 {suppressed_count} 次)")

                return {
                    'statusCode': 200,
                    'suppressed': True,
                    'count': suppressed_count
                }

    except Exception as e:
        print(f"⚠️  查询抑制记录失败: {e}")

    # 不在抑制窗口,发送告警
    target_topic = get_topic_by_severity(severity)

    sns.publish(
        TopicArn=target_topic,
        Subject=f"[{severity}] {alarm_name}",
        Message=json.dumps(sns_message, indent=2)
    )

    # 记录发送时间
    table.put_item(
        Item={
            'suppression_key': suppression_key,
            'last_sent': Decimal(str(int(datetime.now().timestamp()))),
            'suppressed_count': 0,
            'ttl': Decimal(str(int((datetime.now() + timedelta(days=7)).timestamp())))
        }
    )

    print(f"✅ 发送告警: {alarm_name}")

    return {
        'statusCode': 200,
        'suppressed': False
    }

def get_topic_by_severity(severity):
    """根据严重程度返回对应的 SNS Topic"""
    topics = {
        'CRITICAL': 'arn:aws:sns:us-east-2:123456789012:wan22-critical',
        'HIGH': 'arn:aws:sns:us-east-2:123456789012:wan22-high',
        'MEDIUM': 'arn:aws:sns:us-east-2:123456789012:wan22-medium',
        'LOW': 'arn:aws:sns:us-east-2:123456789012:wan22-low'
    }
    return topics.get(severity, topics['MEDIUM'])
```

**DynamoDB 表结构:**
```yaml
SuppressionTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: wan22-alert-suppression
    AttributeDefinitions:
      - AttributeName: suppression_key
        AttributeType: S
    KeySchema:
      - AttributeName: suppression_key
        KeyType: HASH
    BillingMode: PAY_PER_REQUEST
    TimeToLiveSpecification:
      Enabled: true
      AttributeName: ttl
```

### 6.2 告警聚合 (批量通知)

```python
# lambda/alert_aggregation.py
import boto3
import json
from datetime import datetime, timedelta

sqs = boto3.client('sqs')
sns = boto3.client('sns')

AGGREGATION_QUEUE = 'wan22-alert-aggregation-queue'
AGGREGATION_INTERVAL = 300  # 5 分钟

def lambda_handler(event, context):
    """
    告警聚合:
    - 收集 5 分钟内的所有告警
    - 合并为一条消息发送
    - 减少短信数量
    """

    # 从 SQS 获取待聚合的告警
    response = sqs.receive_message(
        QueueUrl=AGGREGATION_QUEUE,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=0
    )

    messages = response.get('Messages', [])

    if not messages:
        return {'statusCode': 200, 'message': 'No alerts to aggregate'}

    # 按严重程度分组
    alerts_by_severity = {
        'CRITICAL': [],
        'HIGH': [],
        'MEDIUM': [],
        'LOW': []
    }

    for msg in messages:
        alert = json.loads(msg['Body'])
        severity = alert.get('Severity', 'MEDIUM')
        alerts_by_severity[severity].append(alert)

        # 删除已处理的消息
        sqs.delete_message(
            QueueUrl=AGGREGATION_QUEUE,
            ReceiptHandle=msg['ReceiptHandle']
        )

    # 生成聚合消息
    aggregated_message = generate_aggregated_message(alerts_by_severity)

    # 发送聚合告警
    sns.publish(
        TopicArn='arn:aws:sns:us-east-2:123456789012:wan22-aggregated',
        Subject=f"Wan22 告警汇总 ({len(messages)} 条)",
        Message=aggregated_message
    )

    return {
        'statusCode': 200,
        'aggregated': len(messages)
    }

def generate_aggregated_message(alerts_by_severity):
    """生成聚合消息"""

    lines = [
        "【Wan22 告警汇总】",
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ]

    for severity, alerts in alerts_by_severity.items():
        if not alerts:
            continue

        lines.append(f"\n{severity} ({len(alerts)} 条):")
        for alert in alerts[:5]:  # 最多显示 5 条
            lines.append(f"  • {alert.get('AlarmName', 'Unknown')}")

        if len(alerts) > 5:
            lines.append(f"  ... 及其他 {len(alerts) - 5} 条")

    lines.append("\n查看详情: https://console.aws.amazon.com/cloudwatch/")

    return "\n".join(lines)
```

**示例输出:**
```
【Wan22 告警汇总】
时间: 2025-11-03 15:30

CRITICAL (2 条):
  • GPU 集群宕机
  • 数据库连接失败

HIGH (5 条):
  • GPU 内存不足
  • Spot 实例中断
  • 任务队列积压
  • API 响应超时
  • Worker 重启频繁

查看详情: https://console.aws.amazon.com/cloudwatch/
```

### 6.3 按值班时间路由

```python
# lambda/oncall_router.py
import boto3
import json
from datetime import datetime

sns = boto3.client('sns')
ssm = boto3.client('ssm')

def lambda_handler(event, context):
    """
    根据值班表路由告警到当前值班人员
    """

    # 从 Parameter Store 获取值班表
    oncall_schedule = get_oncall_schedule()

    # 获取当前值班人员
    current_oncall = get_current_oncall(oncall_schedule)

    # 解析告警
    alarm = json.loads(event['Records'][0]['Sns']['Message'])

    # 发送到值班人员
    send_to_oncall(current_oncall, alarm)

    return {'statusCode': 200}

def get_oncall_schedule():
    """从 SSM Parameter Store 获取值班表"""
    response = ssm.get_parameter(
        Name='/wan22/oncall-schedule',
        WithDecryption=True
    )
    return json.loads(response['Parameter']['Value'])

def get_current_oncall(schedule):
    """获取当前值班人员"""
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday
    hour = now.hour

    # 示例值班表格式:
    # {
    #   "weekdays": {
    #     "day": {"phone": "+8613800138000", "email": "..."},
    #     "night": {"phone": "+8613800138001", "email": "..."}
    #   },
    #   "weekends": {...}
    # }

    shift = 'day' if 9 <= hour < 21 else 'night'
    period = 'weekdays' if weekday < 5 else 'weekends'

    return schedule[period][shift]

def send_to_oncall(oncall, alarm):
    """发送告警到值班人员"""
    sns.publish(
        PhoneNumber=oncall['phone'],
        Message=f"【值班告警】{alarm['AlarmName']}"
    )

    sns.publish(
        TopicArn='arn:aws:sns:us-east-2:123456789012:wan22-oncall-email',
        Subject=f"[值班] {alarm['AlarmName']}",
        Message=json.dumps(alarm, indent=2)
    )
```

---

## 7. 成本分析与优化

### 7.1 SNS 定价 (us-east-2)

| 服务 | 前100万 | 之后 | 备注 |
|------|---------|------|------|
| **Email** | $0.00 | $0.00 | 前 1000 封免费,之后 $2/10万封 |
| **SMS (中国)** | $0.00645/条 | $0.00645/条 | 按条计费 |
| **SMS (美国)** | $0.00645/条 | $0.00645/条 | 价格相同 |
| **HTTP/HTTPS** | $0.00 | $0.00 | 前 10 万次免费 |
| **移动推送** | $0.00 | $0.50/100万 | 极低成本 |
| **SQS** | $0.00 | $0.40/100万 | 极低成本 |
| **Lambda** | $0.00 | $0.20/100万 | 极低成本 |

**Amazon Connect (语音):**
- 呼出电话: $0.018/分钟
- 呼入电话: $0.018/分钟
- DID 号码: $0.03/天 ($0.90/月)

### 7.2 月成本估算

**场景 1: 中小型项目 (每月 200 个任务)**

| 告警类型 | 频率 | 单价 | 月成本 |
|---------|------|------|--------|
| **Critical (SMS)** | 5 次 × 2 人 | $0.00645 | $0.06 |
| **High (SMS)** | 20 次 × 1 人 | $0.00645 | $0.13 |
| **Email (所有级别)** | 500 封 | 免费 | $0.00 |
| **语音告警** | 2 次 × 2 分钟 | $0.018/分钟 | $0.07 |
| **总计** | - | - | **$0.26/月** |

**场景 2: 大型项目 (每月 5000 个任务)**

| 告警类型 | 频率 | 单价 | 月成本 |
|---------|------|------|--------|
| **Critical (SMS)** | 10 次 × 3 人 | $0.00645 | $0.19 |
| **High (SMS)** | 50 次 × 2 人 | $0.00645 | $0.65 |
| **Email** | 2000 封 | 免费(前1000) + $0.02 | $0.02 |
| **语音告警** | 5 次 × 3 分钟 | $0.018/分钟 | $0.27 |
| **Slack (HTTP)** | 无限 | 免费 | $0.00 |
| **总计** | - | - | **$1.13/月** |

### 7.3 成本优化建议

#### 优化 1: 减少短信用量

```python
# 策略: Critical 用 SMS,其他用 Email/Slack

告警分级:
✅ Critical → SMS + Email
✅ High → Email + Slack
✅ Medium → Slack only
✅ Low → Email only (每日汇总)

预计节省: 60%
```

#### 优化 2: 合并告警 (聚合)

```python
# 策略: 5 分钟内的告警合并为一条短信

之前:
  5 个告警 = 5 条短信 = $0.032

之后:
  5 个告警 = 1 条短信 = $0.006

节省: 80%
```

#### 优化 3: 使用免费通道

```python
# 优先级:
1. Slack/Teams (免费,实时)
2. Email (免费,异步)
3. SMS (付费,紧急)
4. 电话 (付费,极度紧急)

策略:
- 工作时间: Slack + Email
- 非工作时间: SMS
- 生产事故: SMS + 电话

预计节省: 70-80%
```

#### 优化 4: 告警抑制

```python
# 防止告警风暴
相同告警 1 小时内只发送一次

示例:
- GPU OOM 连续触发 10 次
- 仅发送第 1 次和最后 1 次
- 节省: 8 条短信 = $0.05
```

### 7.4 实际成本案例

**案例: Wan22 GPU 集群 (月均 1000 个视频任务)**

```
告警配置:
- Critical: 5 次/月 (SMS to 2 人)
- High: 15 次/月 (SMS to 1 人)
- Medium: 50 次/月 (Slack + Email)
- Low: 200 次/月 (Email 每日汇总)

成本计算:
  Critical SMS: 5 × 2 × $0.00645 = $0.06
  High SMS: 15 × 1 × $0.00645 = $0.10
  Email: 免费 (< 1000 封)
  Slack: 免费

  总计: $0.16/月

vs 传统监控服务 (DataDog/New Relic):
  DataDog: $15-31/主机/月
  节省: 99%
```

---

## 8. 完整配置示例

### 8.1 Wan22 告警系统 CloudFormation

```yaml
# cloudformation/wan22-complete-alerts.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Complete alert system for Wan22 GPU Cluster

Parameters:
  CriticalPhoneNumbers:
    Type: String
    Description: "Critical alert phone numbers (comma-separated)"
    Default: "+8613800138000,+8613800138001"

  HighPhoneNumber:
    Type: String
    Description: "High alert phone number"
    Default: "+8613800138000"

  TeamEmail:
    Type: String
    Description: "Team email for general alerts"
    Default: "team@example.com"

  CriticalEmail:
    Type: String
    Description: "Critical alert email"
    Default: "critical@example.com"

Resources:
  # ==========================================
  # SNS Topics (分级告警)
  # ==========================================

  CriticalAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-critical
      DisplayName: Wan22 Critical Alerts
      # 订阅通过 Lambda 动态创建 (支持多个手机号)

  HighAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-high
      Subscription:
        - Endpoint: !Ref HighPhoneNumber
          Protocol: sms
        - Endpoint: !Ref TeamEmail
          Protocol: email

  MediumAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-medium
      Subscription:
        - Endpoint: !Ref TeamEmail
          Protocol: email

  LowAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: wan22-low
      Subscription:
        - Endpoint: !Ref TeamEmail
          Protocol: email

  # ==========================================
  # Lambda Functions
  # ==========================================

  # Critical 告警路由 (SMS to 多人)
  CriticalAlertRouter:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: wan22-critical-alert-router
      Runtime: python3.10
      Handler: index.lambda_handler
      Role: !GetAtt AlertLambdaRole.Arn
      Environment:
        Variables:
          PHONE_NUMBERS: !Ref CriticalPhoneNumbers
          CRITICAL_EMAIL: !Ref CriticalEmail
      Code:
        ZipFile: |
          import boto3
          import json
          import os

          sns = boto3.client('sns')

          def lambda_handler(event, context):
              phone_numbers = os.environ['PHONE_NUMBERS'].split(',')
              alarm = json.loads(event['Records'][0]['Sns']['Message'])

              message = f"【Wan22 严重告警】\n{alarm['AlarmName']}\n时间: {alarm['StateChangeTime']}"

              # 发送 SMS
              for phone in phone_numbers:
                  sns.publish(
                      PhoneNumber=phone.strip(),
                      Message=message
                  )

              # 发送 Email
              sns.publish(
                  TopicArn=os.environ.get('EMAIL_TOPIC_ARN'),
                  Subject=f"[CRITICAL] {alarm['AlarmName']}",
                  Message=json.dumps(alarm, indent=2)
              )

              return {'statusCode': 200}

  # 告警抑制
  AlertSuppressionFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: wan22-alert-suppression
      Runtime: python3.10
      Handler: index.lambda_handler
      Role: !GetAtt AlertLambdaRole.Arn
      Environment:
        Variables:
          SUPPRESSION_TABLE: !Ref SuppressionTable
      Code:
        ZipFile: |
          # (使用前面的告警抑制代码)

  AlertLambdaRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: SNSPublish
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - sns:Publish
                Resource: '*'
        - PolicyName: DynamoDBAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                Resource: !GetAtt SuppressionTable.Arn

  # DynamoDB 表 (告警抑制)
  SuppressionTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: wan22-alert-suppression
      AttributeDefinitions:
        - AttributeName: suppression_key
          AttributeType: S
      KeySchema:
        - AttributeName: suppression_key
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST
      TimeToLiveSpecification:
        Enabled: true
        AttributeName: ttl

  # ==========================================
  # CloudWatch Alarms
  # ==========================================

  # 1. 成本告警 (Critical)
  DailyCostCriticalAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-daily-cost-critical
      AlarmDescription: "每日成本超过 $100"
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Period: 86400
      EvaluationPeriods: 1
      Threshold: 100
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref CriticalAlertTopic

  # 2. 成本告警 (High)
  DailyCostHighAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-daily-cost-high
      AlarmDescription: "每日成本超过 $50"
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Statistic: Maximum
      Period: 86400
      EvaluationPeriods: 1
      Threshold: 50
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref HighAlertTopic

  # 3. Spot 中断 (High)
  SpotInterruptionAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-spot-interrupted
      AlarmDescription: "Spot 实例被中断"
      MetricName: SpotFleetRequestInterruptions
      Namespace: AWS/EC2Spot
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 1
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref HighAlertTopic

  # 4. 队列积压 (Medium)
  QueueBacklogAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: wan22-queue-backlog
      AlarmDescription: "任务队列积压 > 500"
      MetricName: QueueLength
      Namespace: Wan22/Queue
      Statistic: Average
      Period: 3600
      EvaluationPeriods: 1
      Threshold: 500
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref MediumAlertTopic

  # Lambda 权限
  CriticalAlertRouterPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref CriticalAlertRouter
      Action: lambda:InvokeFunction
      Principal: sns.amazonaws.com
      SourceArn: !Ref CriticalAlertTopic

Outputs:
  CriticalTopicArn:
    Value: !Ref CriticalAlertTopic
    Export:
      Name: Wan22-CriticalTopicArn

  HighTopicArn:
    Value: !Ref HighAlertTopic
    Export:
      Name: Wan22-HighTopicArn

  MediumTopicArn:
    Value: !Ref MediumAlertTopic
    Export:
      Name: Wan22-MediumTopicArn

  LowTopicArn:
    Value: !Ref LowAlertTopic
    Export:
      Name: Wan22-LowTopicArn
```

---

## 9. 部署与测试

### 9.1 部署步骤

```bash
#!/bin/bash
# deploy-alerts.sh - 部署告警系统

set -e

STACK_NAME="wan22-alerts"
REGION="us-east-2"

echo "🚀 Deploying Wan22 Alert System..."

# 1. 验证 CloudFormation 模板
echo "📋 Validating template..."
aws cloudformation validate-template \
  --template-body file://wan22-complete-alerts.yaml \
  --region $REGION

# 2. 部署
echo "🚢 Deploying stack..."
aws cloudformation deploy \
  --template-file wan22-complete-alerts.yaml \
  --stack-name $STACK_NAME \
  --region $REGION \
  --parameter-overrides \
    CriticalPhoneNumbers="+8613800138000,+8613800138001" \
    HighPhoneNumber="+8613800138000" \
    TeamEmail="team@example.com" \
    CriticalEmail="critical@example.com" \
  --capabilities CAPABILITY_IAM

# 3. 获取输出
echo "📤 Getting outputs..."
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs'

echo "✅ Deployment complete!"
```

### 9.2 测试告警

```bash
#!/bin/bash
# test-alerts.sh - 测试所有告警级别

REGION="us-east-2"

# 获取 Topic ARNs
CRITICAL_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name wan22-alerts \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`CriticalTopicArn`].OutputValue' \
  --output text)

HIGH_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name wan22-alerts \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`HighTopicArn`].OutputValue' \
  --output text)

echo "📱 Testing Critical Alert (SMS)..."
aws sns publish \
  --topic-arn $CRITICAL_TOPIC \
  --message '{
    "AlarmName": "测试严重告警",
    "AlarmDescription": "这是一个测试 Critical 级别告警",
    "NewStateValue": "ALARM",
    "StateChangeTime": "2025-11-03T10:00:00.000Z"
  }' \
  --region $REGION

echo "⏳ Waiting 5 seconds..."
sleep 5

echo "📧 Testing High Alert (SMS + Email)..."
aws sns publish \
  --topic-arn $HIGH_TOPIC \
  --subject "[TEST] High Alert" \
  --message "这是一个测试 High 级别告警" \
  --region $REGION

echo "✅ Test complete! Check your phone and email."
```

### 9.3 验证订阅

```bash
# 列出所有订阅
aws sns list-subscriptions \
  --region us-east-2 \
  --query 'Subscriptions[?contains(TopicArn, `wan22`)]'

# 确认待确认的订阅 (Email)
# 检查邮箱,点击确认链接
```

### 9.4 监控告警发送

```bash
# CloudWatch Logs Insights 查询
# 查看最近 1 小时的告警发送记录

fields @timestamp, @message
| filter @message like /Published message/
| sort @timestamp desc
| limit 20
```

---

## 10. 最佳实践

### 10.1 告警设计原则

1. **明确性 (Clarity)**
   - ✅ 告警内容清晰明了
   - ✅ 包含上下文信息
   - ✅ 提供操作指引

2. **可操作性 (Actionable)**
   - ✅ 每个告警都应该有对应的处理流程
   - ❌ 避免"噪音告警"(无法处理的告警)

3. **及时性 (Timeliness)**
   - ✅ Critical 告警立即发送
   - ✅ Low 告警可以批量汇总

4. **分级明确 (Severity)**
   - ✅ 严格区分告警级别
   - ❌ 避免"狼来了"效应

### 10.2 告警内容模板

**Critical 告警模板:**
```
【Wan22 严重告警】
级别: Critical
事件: {alarm_name}
描述: {description}
影响: {impact}
时间: {timestamp}
操作: {action_required}
查看: {dashboard_url}
```

**High 告警模板:**
```
【Wan22 高优先级告警】
事件: {alarm_name}
详情: {details}
时间: {timestamp}
查看: {url}
```

**Medium/Low 告警 (Email):**
```
主题: [Wan22 Alert] {alarm_name}

告警详情:
- 名称: {alarm_name}
- 级别: {severity}
- 时间: {timestamp}
- 指标: {metric_name} = {value}
- 阈值: {threshold}

建议操作:
{recommended_actions}

查看详情:
{cloudwatch_url}
```

### 10.3 值班轮换建议

```yaml
# oncall-schedule.yaml
# 存储在 SSM Parameter Store: /wan22/oncall-schedule

weekdays:
  day:  # 9:00-21:00
    primary:
      name: "张三"
      phone: "+8613800138000"
      email: "zhangsan@example.com"
    secondary:
      name: "李四"
      phone: "+8613800138001"
      email: "lisi@example.com"

  night:  # 21:00-9:00
    primary:
      name: "王五"
      phone: "+8613800138002"
      email: "wangwu@example.com"

weekends:
  all_day:
    primary:
      name: "赵六"
      phone: "+8613800138003"
      email: "zhaoliu@example.com"
```

### 10.4 文档化

每个告警都应该有对应的 Runbook:

```markdown
# Runbook: GPU 内存不足 (wan22-gpu-memory-high)

## 告警信息
- **级别**: High
- **触发条件**: GPU 内存使用率 > 90%
- **影响**: 可能导致任务失败、OOM 错误

## 处理步骤

### 1. 确认影响范围
```bash
# 查看所有 GPU 实例状态
kubectl get pods -n wan22 -l app=gpu-worker

# 查看 GPU 内存使用
kubectl exec <pod-name> -n wan22 -- nvidia-smi
```

### 2. 临时缓解
```bash
# 重启内存泄漏的 Worker
kubectl delete pod <pod-name> -n wan22

# 或扩容 GPU 节点
kubectl scale deployment gpu-worker --replicas=10 -n wan22
```

### 3. 根因分析
- 检查是否有内存泄漏
- 检查任务分辨率是否过高
- 检查模型是否正确卸载

### 4. 长期解决
- 优化模型 offloading
- 升级到更大 GPU (A100 40GB)
- 实施更严格的资源限制
```

---

## 11. 常见问题 FAQ

### Q1: 短信没有收到怎么办?

**A:** 检查清单:

1. ✅ 手机号格式正确 (国际格式: +86...)
2. ✅ SNS 订阅状态为 "Confirmed"
3. ✅ 没有被运营商拦截 (避免敏感词)
4. ✅ 检查 CloudWatch Logs 确认已发送
5. ✅ 检查 SNS 每月预算限制

```bash
# 检查 SNS 发送记录
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfMessagesSent \
  --dimensions Name=TopicName,Value=wan22-critical \
  --start-time 2025-11-03T00:00:00Z \
  --end-time 2025-11-03T23:59:59Z \
  --period 3600 \
  --statistics Sum \
  --region us-east-2
```

### Q2: 如何避免告警风暴?

**A:** 使用告警抑制和聚合:

1. ✅ 相同告警 1 小时内只发送一次
2. ✅ 5 分钟内的告警合并为一条
3. ✅ 设置合理的评估周期 (EvaluationPeriods)
4. ✅ 使用复合告警 (Composite Alarms)

### Q3: 短信成本太高怎么办?

**A:** 成本优化策略:

1. ✅ 减少 Critical 告警数量 (提高阈值)
2. ✅ 工作时间使用 Slack,非工作时间用 SMS
3. ✅ 使用告警聚合 (减少短信条数)
4. ✅ Low/Medium 告警只用 Email

### Q4: 电话告警如何配置中文语音?

**A:** Amazon Connect 支持中文 TTS:

```python
# Contact Flow 中使用中文 Polly
{
  "Type": "PlayPrompt",
  "Parameters": {
    "Text": "您好,这是 Wan22 系统紧急告警",
    "TextToSpeechType": "Neural",
    "Engine": "Neural",
    "LanguageCode": "cmn-CN",  # 中文
    "VoiceId": "Zhiyu"  # 中文女声
  }
}
```

### Q5: 如何集成钉钉/飞书?

**A:** 使用 HTTP/HTTPS 订阅:

```python
# Lambda 函数转发到钉钉
import requests

def send_to_dingtalk(message):
    webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "Wan22 告警",
            "text": f"## Wan22 告警通知\n\n{message}"
        }
    }

    requests.post(webhook_url, json=payload)
```

### Q6: 如何测试告警不打扰用户?

**A:** 使用测试 Topic:

```bash
# 创建测试 Topic (订阅测试手机号)
aws sns create-topic --name wan22-test-alerts

# 订阅测试号码
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:123456789012:wan22-test-alerts \
  --protocol sms \
  --notification-endpoint "+8613800138999"  # 测试号码

# 测试时使用测试 Topic
# 生产时切换到生产 Topic
```

---

## 总结

### 核心要点

1. ✅ **SNS 支持多种通知方式**: Email (免费), SMS ($0.006/条), 电话 ($0.018/分钟)
2. ✅ **告警分级**: Critical (SMS+电话) → High (SMS) → Medium (Email+Slack) → Low (Email)
3. ✅ **成本可控**: 合理使用每月成本 < $5
4. ✅ **高级功能**: 告警抑制、聚合、按值班表路由

### 推荐配置

**Wan22 GPU 集群最佳实践:**

```
Critical (🔴):
  → SMS to 2-3 人
  → Email to critical@
  → 电话 (非工作时间)
  → 立即响应

High (🟠):
  → SMS to 1 人
  → Email + Slack
  → 15 分钟内响应

Medium/Low:
  → Email + Slack
  → 异步处理
```

**预期成本: $0.20-1.00/月**

### 下一步

1. 📖 阅读完本文档
2. 🚀 部署基础告警 (Email + SMS)
3. 🧪 测试所有告警级别
4. 📊 监控成本和效果
5. 🔧 根据实际情况优化

---

**文档版本**: v1.0
**最后更新**: 2025-11-03
**维护者**: Engineering Team
**反馈**: 如有问题请提 Issue
