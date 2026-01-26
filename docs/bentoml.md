# BentoML Deployment Guide

This guide explains how to deploy Docling Serve using BentoML and BentoCloud.

## Overview

BentoML is a framework for building and deploying machine learning services. Docling Serve can be deployed as a BentoML service, which provides:

- **Unified deployment**: Package and deploy the entire application as a single Bento
- **Cloud deployment**: Deploy to BentoCloud with autoscaling and monitoring
- **Secret management**: Secure handling of API keys, tokens, and credentials
- **Containerization**: Export to Docker or other container formats

## Prerequisites

1. **BentoML installed**: `pip install bentoml>=1.2.0`
2. **BentoCloud account** (for cloud deployment): Sign up at [bentoml.com](https://www.bentoml.com)
3. **Python 3.10+** (matches project requirements)

## Project Structure

The BentoML integration adds the following files:

- `service.py` - BentoML service definition
- `bentofile.yaml` - BentoML build configuration (includes exclude patterns)
- `requirements-bentoml.txt` - Python dependencies for BentoML
- `.env.bentoml.example` - Example environment variables

## Local Development and Testing

### 1. Install Dependencies

```bash
pip install -r requirements-bentoml.txt
```

### 2. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.bentoml.example .env.bentoml
# Edit .env.bentoml with your configuration
```

**Important**: Never commit `.env.bentoml` to version control. It's already in `.gitignore`.

### 3. Build the Bento

```bash
bentoml build
```

This creates a Bento package in the `.bento/` directory.

### 4. Test Locally

```bash
bentoml serve
```

The service will be available at `http://localhost:3000` (default BentoML port).

You can test the API endpoints:

```bash
# Health check
curl http://localhost:3000/health

# Convert a document (if API key is set, include it)
curl -X POST http://localhost:3000/v1/convert/source \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-api-key" \
  -d '{
    "sources": [{"kind": "http", "url": "https://arxiv.org/pdf/2501.17887"}]
  }'
```

## BentoCloud Deployment

### 1. Login to BentoCloud

```bash
bentoml cloud login
```

### 2. Create Secrets

Sensitive values must be stored as BentoML secrets. Create them via CLI or the BentoCloud console.

#### Via CLI:

```bash
# API Key
bentoml secret create docling-api-key --stage runtime

# Redis URL (if using RQ engine)
bentoml secret create docling-redis-url --stage runtime

# KFP Token (if using KFP engine)
bentoml secret create docling-kfp-token --stage runtime
```

When prompted, enter the secret value. Use `--stage runtime` for runtime-only secrets.

#### Via BentoCloud Console:

1. Navigate to your BentoCloud organization
2. Go to **Settings** > **Secrets**
3. Click **Create Secret**
4. Enter the secret name and value
5. Select **Runtime** stage

### 3. Build and Push

```bash
# Build the Bento
bentoml build

# Push to BentoCloud
bentoml cloud push
```

### 4. Create Deployment

#### Via CLI:

```bash
bentoml deployment create \
  --name docling-serve-prod \
  --bento $(bentoml list -o json | jq -r '.[0].tag') \
  --env DOCLING_SERVE_ENABLE_UI=true \
  --env DOCLING_SERVE_LOAD_MODELS_AT_BOOT=true \
  --secret docling-api-key \
  --secret docling-redis-url
```

#### Via BentoCloud Console:

1. Navigate to **Deployments**
2. Click **Create Deployment**
3. Select your Bento
4. Configure:
   - **Name**: e.g., `docling-serve-prod`
   - **Resources**: CPU, memory, GPU (if needed)
   - **Environment Variables**: Add non-sensitive config
   - **Secrets**: Select the secrets you created
   - **Scaling**: Configure autoscaling if needed

### 5. Access Your Deployment

Once deployed, you'll receive a deployment URL. Use it to access the API:

```bash
curl https://your-deployment-url.bentoml.cloud/health
```

## Environment Variables

### Required Variables

- **None** (all have defaults)

### Recommended Variables

- `DOCLING_SERVE_LOAD_MODELS_AT_BOOT=true` - Preload models for faster first request
- `DOCLING_SERVE_ENABLE_UI=true` - Enable Gradio UI (requires `gradio` in requirements)

### Sensitive Variables (Use Secrets)

These should be stored as BentoML secrets:

- `DOCLING_SERVE_API_KEY` - API authentication key
- `DOCLING_SERVE_ENG_RQ_REDIS_URL` - Redis connection URL (if using RQ engine)
- `DOCLING_SERVE_ENG_KFP_TOKEN` - KFP authentication token (if using KFP engine)
- `DOCLING_SERVE_ENG_KFP_CA_CERT_PATH` - KFP certificate path
- `DOCLING_SERVE_ENG_KFP_SELF_CALLBACK_TOKEN_PATH` - KFP callback token path

See `.env.bentoml.example` for a complete list of available variables.

## Compute Engines

Docling Serve supports three compute engines:

### Local Engine (Default)

Processes tasks in the same process. Suitable for single-instance deployments.

```bash
# Set in deployment environment
DOCLING_SERVE_ENG_KIND=local
DOCLING_SERVE_ENG_LOC_NUM_WORKERS=2
```

### RQ Engine

Uses Redis Queue for distributed task processing. Requires Redis and separate RQ workers.

**Setup**:

1. Deploy Redis (or use managed Redis service)
2. Create secret: `DOCLING_SERVE_ENG_RQ_REDIS_URL`
3. Deploy RQ workers separately (see below)

**Configuration**:

```bash
DOCLING_SERVE_ENG_KIND=rq
DOCLING_SERVE_ENG_RQ_REDIS_URL=<secret>
DOCLING_SERVE_ENG_RQ_RESULTS_PREFIX=docling:results
DOCLING_SERVE_ENG_RQ_SUB_CHANNEL=docling:updates
```

**RQ Workers**:

RQ workers must be deployed separately. You can:

1. Deploy as a separate BentoML service
2. Run as external processes/containers
3. Use Kubernetes jobs

Example worker deployment (separate service):

```python
# rq_worker_service.py
import bentoml
from docling_serve.__main__ import rq_worker

@bentoml.service(name="docling-rq-worker")
class RQWorkerService:
    @bentoml.api
    def start(self):
        rq_worker()
```

### KFP Engine

Uses Kubeflow Pipelines for task processing. Requires KFP cluster and configuration.

**Setup**:

1. Configure KFP endpoint and authentication
2. Create secrets for tokens and certificates
3. Set `DOCLING_SERVE_ENG_KFP_EXPERIMENTAL=true` (currently experimental)

## Model Artifacts

### Option 1: Runtime Download (Recommended)

Models are downloaded at runtime to the cache directory:

```bash
DOCLING_SERVE_ARTIFACTS_PATH=/tmp/docling/models
```

**Pros**: Smaller Bento size, always latest models
**Cons**: Slower first request, requires internet access

### Option 2: Bundle Models

Include models in the Bento by adding them to `bentofile.yaml`:

```yaml
include:
  - "docling_serve/**/*.py"
  - "service.py"
  - "models/**"  # Add your models directory
```

**Pros**: Faster startup, works offline
**Cons**: Larger Bento size (models can be several GB)

## Monitoring and Observability

Docling Serve includes OpenTelemetry instrumentation:

- **Metrics**: Prometheus metrics at `/metrics`
- **Traces**: Distributed tracing (if enabled)
- **Logs**: Structured logging

Configure in deployment:

```bash
DOCLING_SERVE_OTEL_ENABLE_METRICS=true
DOCLING_SERVE_OTEL_ENABLE_TRACES=false
DOCLING_SERVE_OTEL_ENABLE_PROMETHEUS=true
DOCLING_SERVE_OTEL_SERVICE_NAME=docling-serve
```

## Scaling

### Autoscaling

Configure autoscaling in BentoCloud deployment settings:

- **Min instances**: Minimum number of instances
- **Max instances**: Maximum number of instances
- **Target concurrency**: Requests per instance before scaling

### Resource Allocation

Configure resources in `bentofile.yaml` or deployment settings:

```yaml
# In service.py
@bentoml.service(
    resources={"cpu": "2", "memory": "4Gi", "gpu": 1},  # if needed
)
```

Or in deployment:

- **CPU**: e.g., `2` or `2000m`
- **Memory**: e.g., `4Gi` or `4096Mi`
- **GPU**: e.g., `1` (if using CUDA)

## Troubleshooting

### Build Issues

**Problem**: Missing dependencies
**Solution**: Ensure `requirements-bentoml.txt` includes all needed packages

**Problem**: Large Bento size
**Solution**: Adjust the `exclude` section in `bentofile.yaml` to exclude unnecessary files, or use runtime model download

### Runtime Issues

**Problem**: Models not loading
**Solution**: 
- Check `DOCLING_SERVE_ARTIFACTS_PATH` is writable
- Verify internet access for model downloads
- Check logs for download errors

**Problem**: RQ engine not working
**Solution**:
- Verify Redis is accessible
- Check `DOCLING_SERVE_ENG_RQ_REDIS_URL` secret is set
- Ensure RQ workers are running

**Problem**: WebSocket connections failing
**Solution**: 
- Verify BentoML/ASGI server supports WebSockets (should work by default)
- Check firewall/proxy settings
- Review WebSocket endpoint logs

### Deployment Issues

**Problem**: Secrets not available
**Solution**:
- Verify secrets are created with correct names
- Check secret stage is `runtime`
- Ensure secrets are attached to deployment

**Problem**: Timeout errors
**Solution**:
- Increase timeout in `service.py`: `traffic={"timeout": 600}`
- Configure appropriate timeouts in deployment settings
- Consider using async API endpoints for long-running tasks

## Best Practices

1. **Use Secrets**: Never commit API keys, tokens, or credentials
2. **Environment-Specific Config**: Use different deployments for dev/staging/prod
3. **Resource Planning**: Allocate sufficient CPU/memory for model inference
4. **Monitoring**: Enable OpenTelemetry for production deployments
5. **Model Caching**: Use `DOCLING_SERVE_LOAD_MODELS_AT_BOOT=true` for faster responses
6. **Async Processing**: Use async endpoints (`/async`) for long-running tasks
7. **Health Checks**: Monitor `/health` endpoint for deployment health

## Migration from Direct Uvicorn

If you're currently running `docling-serve run`, migrating to BentoML:

1. **No code changes needed** - The FastAPI app works as-is
2. **Build the Bento**: `bentoml build`
3. **Test locally**: `bentoml serve`
4. **Deploy**: Use BentoCloud or export to Docker

The existing `docling-serve run` command continues to work for non-BentoML deployments.

## Additional Resources

- [BentoML Documentation](https://docs.bentoml.com/)
- [BentoCloud Guide](https://docs.bentoml.com/en/latest/get-started/cloud-deployment.html)
- [BentoML Secrets Management](https://docs.bentoml.com/en/latest/scale-with-bentocloud/manage-secrets-and-env-vars.html)
- [Docling Serve Configuration](./configuration.md)

## Support

For issues specific to:
- **BentoML**: [BentoML GitHub Issues](https://github.com/bentoml/BentoML/issues)
- **Docling Serve**: [Docling Serve GitHub Issues](https://github.com/docling-project/docling-serve/issues)
