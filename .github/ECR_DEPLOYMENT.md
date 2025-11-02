# AWS ECR Deployment Guide

This guide explains how to use the GitHub Actions workflow to build and push the Wan2.2 Docker image to AWS ECR.

## Prerequisites

### 1. AWS Setup

You need an AWS account with permissions to:
- Create and manage ECR repositories
- Push Docker images to ECR

### 2. GitHub Secrets Configuration

Add the following secrets to your GitHub repository:

**Required Secrets:**
- `AWS_ACCESS_KEY_ID`: Your AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key

**Optional Secrets:**
- `DISCORD_WEBHOOK_URL`: Discord webhook URL for build notifications

To add secrets:
1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with the exact names listed above

### 3. AWS IAM Permissions

The AWS credentials need the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:GetRepositoryPolicy",
        "ecr:DescribeRepositories",
        "ecr:ListImages",
        "ecr:DescribeImages",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:CreateRepository"
      ],
      "Resource": "*"
    }
  ]
}
```

## Usage

### Running the Workflow

1. Go to your GitHub repository
2. Click on the **Actions** tab
3. Select **Build and Push Wan2.2 to AWS ECR** from the left sidebar
4. Click **Run workflow** button
5. Select the environment:
   - **dev**: Builds and pushes to `us-east-2` region
   - **prod**: Builds and pushes to `us-east-1` region
6. Click **Run workflow**

### What the Workflow Does

1. **Environment Configuration**: Sets AWS region based on selected environment
   - `dev` → `us-east-2`
   - `prod` → `us-east-1`

2. **ECR Repository**: Creates ECR repository if it doesn't exist
   - Repository name: `wan22-dev` or `wan22-prod`
   - Image scanning enabled
   - Mutable tags

3. **Docker Build**: Builds the Wan2.2 Docker image using the project's Dockerfile

4. **Image Tagging**: Tags the image with multiple tags:
   - Git commit SHA (e.g., `abc1234`)
   - Branch name + SHA
   - `latest` (for main branch only)

5. **Push to ECR**: Pushes all tags to the ECR repository

6. **Notifications**: Sends Discord notifications (if webhook configured)

## After the Build

### Pulling the Image

Once the build completes, you can pull the image:

```bash
# Login to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

# Pull the image
docker pull <account-id>.dkr.ecr.<region>.amazonaws.com/wan22-<env>:<tag>
```

Replace:
- `<region>`: `us-east-2` (dev) or `us-east-1` (prod)
- `<account-id>`: Your AWS account ID
- `<env>`: `dev` or `prod`
- `<tag>`: Git commit SHA or `latest`

### Using the Image

```bash
# Run the container
docker run --gpus all -it \
  -v /path/to/models:/workspace/models \
  -v /path/to/outputs:/workspace/outputs \
  <account-id>.dkr.ecr.<region>.amazonaws.com/wan22-<env>:<tag>

# Example: Run T2V generation
docker run --gpus all -it \
  -v ./models:/workspace/models \
  -v ./outputs:/workspace/outputs \
  <account-id>.dkr.ecr.<region>.amazonaws.com/wan22-dev:latest \
  python generate.py --task t2v-A14B --size 1280*720 \
    --ckpt_dir /workspace/models/Wan2.2-T2V-A14B \
    --prompt "A beautiful sunset over the ocean"
```

## Workflow Details

### Build Cache

The workflow uses GitHub Actions cache to speed up subsequent builds:
- Cache type: `gha` (GitHub Actions cache)
- Cache mode: `max` (maximum caching)

This significantly reduces build times for repeated builds.

### Build Arguments

The workflow passes the following build arguments:
- `GIT_COMMIT`: Short git commit hash
- `GIT_COMMIT_DATE`: Commit date
- `BUILDKIT_INLINE_CACHE`: Enables inline caching

### Image Tags

All built images are tagged with:
1. Full commit SHA: `<sha>`
2. Branch + SHA: `<branch>-<sha>`
3. Latest (main branch only): `latest`

## Troubleshooting

### Build Fails

1. **Check GitHub Actions logs**: Go to Actions tab and click on the failed run
2. **Verify AWS credentials**: Ensure secrets are correctly configured
3. **Check AWS permissions**: Verify IAM user has required ECR permissions
4. **Docker build errors**: Check if Dockerfile builds locally first

### Cannot Pull Image

1. **Login to ECR first**: Run `aws ecr get-login-password` command
2. **Check repository exists**: Run `aws ecr describe-repositories`
3. **Verify region**: Ensure you're using the correct AWS region
4. **Check image tag**: Run `aws ecr list-images --repository-name wan22-<env>`

### Discord Notifications Not Working

1. **Verify webhook URL**: Check if `DISCORD_WEBHOOK_URL` secret is set
2. **Test webhook**: Try sending a test message to the webhook URL
3. **Notifications are optional**: Workflow will succeed even if Discord notifications fail

## Cost Considerations

### ECR Storage Costs

- **Storage**: ~$0.10 per GB/month
- **Data Transfer**: $0.09 per GB out to internet
- **Estimate**: Each Wan2.2 image is ~15-20 GB

**Cost optimization tips:**
1. Delete old images regularly
2. Use lifecycle policies to auto-delete old tags
3. Keep only necessary tags (e.g., last 5 builds)

### GitHub Actions Costs

- **Free tier**: 2,000 minutes/month for private repos
- **Build time**: ~30-60 minutes per build (estimated)
- **Estimate**: ~30-60 builds per month on free tier

**Cost optimization tips:**
1. Build only when necessary (not on every commit)
2. Use build cache effectively
3. Build during off-peak hours if on paid plan

## Next Steps

1. **Set up lifecycle policy**: Auto-delete old images to save storage costs
2. **Configure image scanning**: Review scan results after each build
3. **Set up deployment**: Use the ECR images in ECS, EKS, or EC2
4. **Monitor costs**: Check AWS Cost Explorer regularly

## Additional Resources

- [AWS ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
