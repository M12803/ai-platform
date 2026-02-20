# AI Platform
Production-ready on-premise AI orchestration platform built with FastAPI and local LLM runtime.
# AI Platform – Production Deployment Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Installation – Ubuntu 22.04 / 24.04](#installation--ubuntu-2204--2404)
4. [Installation – AlmaLinux 8 / 9](#installation--almalinux-8--9)
5. [Model Preparation](#model-preparation)
6. [Configuration](#configuration)
7. [Systemd Service Setup](#systemd-service-setup)
8. [Nginx Configuration](#nginx-configuration)
9. [Firewall Rules](#firewall-rules)
10. [Security Considerations](#security-considerations)
11. [API Reference with Examples](#api-reference-with-examples)
12. [Architecture Deep-Dive](#architecture-deep-dive)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │    Nginx        │  Rate limiting, TLS, headers
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI App    │  API Key auth, request logging
                    └────────┬────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │         API Layer (routes_*)         │  Validation, HTTP mapping
          └──────────────────┬──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │      Application Layer               │  OperationService
          └──────────────────┬──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │      Orchestration Layer             │  OrchestrationService
          │  - Model selection                  │
          │  - Limit enforcement                │
          │  - Error handling                   │
          └────────┬─────────────────┬──────────┘
                   │                 │
     ┌─────────────▼─────┐   ┌───────▼──────────────┐
     │   Model Runtime   │   │   Limit/Usage Layer  │
     │  - ModelLoader    │   │  - LimitService       │
     │  - ModelRegistry  │   │  - SQLite via ORM     │
     │  - InferenceEng.  │   └──────────────────────┘
     └───────────────────┘
```

### Layer Responsibilities

| Layer | Module | Responsibility |
|-------|--------|----------------|
| API | `routes_operations.py` | HTTP request/response, HTTP error mapping |
| Application | `operation_service.py` | Thin façade, future middleware hooks |
| Orchestration | `orchestration_service.py` | Model selection, limit checks, centralized error handling |
| Model Runtime | `model_loader.py`, `model_registry.py`, `inference_engine.py` | Local model loading, inference execution |
| Limit/Usage | `limit_service.py` + SQLite | Daily rate enforcement, token tracking |
| Infrastructure | `database.py`, `config.py` | DB init, settings |
| Logging | `core/logging.py` | Rotating file + console handlers |
| Health | `health_check.py` | System metrics, model status |

---

## Prerequisites

- CPU: 8+ cores (GPU strongly recommended for production)
- RAM: 16 GB minimum; 32+ GB for multi-model loading
- Disk: 50+ GB SSD for model weights
- OS: Ubuntu 22.04 LTS / AlmaLinux 9 (or equivalent RHEL-based)
- Python: 3.11+
- Nginx 1.18+

---

## Installation – Ubuntu 22.04 / 24.04

```bash
# 1. System dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    build-essential git nginx sqlite3 curl

# 2. Create dedicated system user
sudo useradd --system --shell /sbin/nologin --home /opt/ai_platform aiplatform

# 3. Create application directory
sudo mkdir -p /opt/ai_platform
sudo chown aiplatform:aiplatform /opt/ai_platform

# 4. Copy project files
sudo cp -r /path/to/ai_platform/* /opt/ai_platform/
sudo chown -R aiplatform:aiplatform /opt/ai_platform

# 5. Create virtual environment
sudo -u aiplatform python3.11 -m venv /opt/ai_platform/venv

# 6. Install Python dependencies
sudo -u aiplatform /opt/ai_platform/venv/bin/pip install --upgrade pip wheel
sudo -u aiplatform /opt/ai_platform/venv/bin/pip install -r /opt/ai_platform/requirements.txt

# 7. Configure environment
sudo -u aiplatform cp /opt/ai_platform/.env.example /opt/ai_platform/.env
sudo -u aiplatform nano /opt/ai_platform/.env
# Edit: SECRET_KEY, VALID_API_KEYS

# 8. Create required directories
sudo -u aiplatform mkdir -p /opt/ai_platform/logs /opt/ai_platform/models
```

---

## Installation – AlmaLinux 8 / 9

```bash
# 1. Enable EPEL and development tools
sudo dnf install -y epel-release
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y python3.11 python3.11-devel nginx sqlite curl

# 2. Create dedicated system user
sudo useradd --system --shell /sbin/nologin --home /opt/ai_platform aiplatform

# 3. Create application directory
sudo mkdir -p /opt/ai_platform
sudo chown aiplatform:aiplatform /opt/ai_platform

# 4. Copy project files
sudo cp -r /path/to/ai_platform/* /opt/ai_platform/
sudo chown -R aiplatform:aiplatform /opt/ai_platform

# 5. Create virtual environment
sudo -u aiplatform python3.11 -m venv /opt/ai_platform/venv

# 6. Install Python dependencies
sudo -u aiplatform /opt/ai_platform/venv/bin/pip install --upgrade pip wheel
sudo -u aiplatform /opt/ai_platform/venv/bin/pip install -r /opt/ai_platform/requirements.txt

# 7. Configure environment
sudo -u aiplatform cp /opt/ai_platform/.env.example /opt/ai_platform/.env
sudo -u aiplatform nano /opt/ai_platform/.env

# 8. SELinux – allow Nginx to proxy to local port
sudo setsebool -P httpd_can_network_connect 1

# 9. Create required directories
sudo -u aiplatform mkdir -p /opt/ai_platform/logs /opt/ai_platform/models
```

---

## Model Preparation

The platform requires model weights to be present **before** starting the service.
No internet downloads occur at runtime.

```bash
# Directory structure expected:
/opt/ai_platform/models/
├── qwen-summarize/        ← model folder for summarize operation
│   ├── config.json
│   ├── tokenizer.json
│   ├── tokenizer_config.json
│   └── model.safetensors  (or pytorch_model.bin shards)
├── qwen-translate/
└── qwen-classify/

# Download models on an internet-connected machine, then transfer:
# (On internet-connected machine)
pip install huggingface-hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen2.5-7B-Instruct',
    local_dir='./qwen-summarize',
    local_dir_use_symlinks=False
)
"

# Transfer to production server (no internet required on prod):
rsync -avz ./qwen-summarize user@prod-server:/opt/ai_platform/models/

# You can use the same model folder for all operations and just symlink:
ln -s /opt/ai_platform/models/qwen-summarize /opt/ai_platform/models/qwen-translate
ln -s /opt/ai_platform/models/qwen-summarize /opt/ai_platform/models/qwen-classify

# Or configure separate models per operation in .env:
# OPERATION_MODEL_MAP={"summarize":"qwen2-7b","translate":"qwen2-7b","classify":"qwen2-7b"}
```

---

## Configuration

Edit `/opt/ai_platform/.env`:

```env
APP_NAME="AI Platform"
SECRET_KEY=your-64-char-random-string-here
VALID_API_KEYS=["key-for-service-a","key-for-service-b"]
LOG_LEVEL=INFO
DEFAULT_DAILY_LIMIT=1000
OPERATION_MODEL_MAP={"summarize":"qwen2-7b","translate":"qwen2-7b","classify":"qwen2-7b"}
```

---

## Systemd Service Setup

```bash
# Copy service file
sudo cp /opt/ai_platform/systemd/ai-platform.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable ai-platform

# Start service
sudo systemctl start ai-platform

# Check status
sudo systemctl status ai-platform

# View live logs
sudo journalctl -u ai-platform -f

# Restart after config change
sudo systemctl restart ai-platform
```

---

## Nginx Configuration

```bash
# Ubuntu
sudo cp /opt/ai_platform/nginx/ai-platform.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/ai-platform.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# AlmaLinux / RHEL
sudo cp /opt/ai_platform/nginx/ai-platform.conf /etc/nginx/conf.d/

# Test configuration
sudo nginx -t

# Enable and start Nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# Reload after changes
sudo systemctl reload nginx
```

---

## Firewall Rules

### Ubuntu (ufw)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx HTTP'
# If using HTTPS:
# sudo ufw allow 'Nginx HTTPS'
sudo ufw deny 8000/tcp   # Block direct uvicorn access; all traffic through Nginx
sudo ufw enable
sudo ufw status
```

### AlmaLinux (firewalld)

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
# Block direct uvicorn port from external access
sudo firewall-cmd --permanent --add-rich-rule='rule port port="8000" protocol="tcp" source address="127.0.0.1" accept'
sudo firewall-cmd --permanent --add-rich-rule='rule port port="8000" protocol="tcp" reject'
sudo firewall-cmd --reload
sudo firewall-cmd --list-all
```

---

## Security Considerations

1. **API Keys**: Store in `.env`, never in code. Rotate regularly. Use long random strings (32+ chars).
2. **TLS**: Enable HTTPS in Nginx for production. Use Let's Encrypt (offline: use internal CA).
3. **systemd Hardening**: The service file uses `PrivateTmp`, `ProtectSystem=strict`, `NoNewPrivileges`.
4. **Model Isolation**: The `aiplatform` system user has no shell and cannot write outside its designated directories.
5. **Nginx Rate Limiting**: `limit_req_zone` blocks brute-force against the API key header.
6. **Input Validation**: All inputs are validated by Pydantic with strict types and hard-coded max lengths before reaching the model.
7. **No Outbound Network**: Models are loaded `local_files_only=True`. The server can be fully airgapped.
8. **SQLite Permissions**: The DB file is owned by `aiplatform` with mode 600. Only the service process can read/write it.
9. **Log Rotation**: Python `RotatingFileHandler` prevents disk exhaustion.
10. **Audit Trail**: Every request is logged with timestamp, operation, duration, and token count.

---

## API Reference with Examples

All requests require the header: `X-API-Key: <your-key>`

### POST /operations/summarize

```bash
curl -X POST http://ai-platform.local/operations/summarize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key-001" \
  -d '{
    "text": "Artificial intelligence is transforming industries worldwide. Machine learning models can now recognize images, translate languages, and generate human-like text with unprecedented accuracy. Organizations are investing billions of dollars in AI research and deployment, expecting significant productivity gains.",
    "max_sentences": 2,
    "language": "en",
    "request_id": "req-001"
  }'
```

**Response:**
```json
{
  "summary": "AI is revolutionizing industries through advanced ML models capable of image recognition, translation, and text generation. Organizations are investing heavily in AI, anticipating major productivity improvements.",
  "sentence_count": 2,
  "meta": {
    "operation": "summarize",
    "model_used": "qwen-summarize",
    "input_chars": 318,
    "output_tokens": 42,
    "execution_time_ms": 1240.5,
    "request_id": "req-001",
    "timestamp": "2025-01-15T10:30:00.000Z"
  }
}
```

### POST /operations/translate

```bash
curl -X POST http://ai-platform.local/operations/translate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key-001" \
  -d '{
    "text": "The quarterly earnings report exceeded all analyst expectations.",
    "source_language": "en",
    "target_language": "ar",
    "request_id": "req-002"
  }'
```

**Response:**
```json
{
  "translated_text": "تجاوز تقرير الأرباح الفصلية جميع توقعات المحللين.",
  "source_language": "en",
  "target_language": "ar",
  "meta": {
    "operation": "translate",
    "model_used": "qwen-translate",
    "input_chars": 62,
    "output_tokens": 18,
    "execution_time_ms": 890.3,
    "request_id": "req-002",
    "timestamp": "2025-01-15T10:31:00.000Z"
  }
}
```

### POST /operations/classify

```bash
curl -X POST http://ai-platform.local/operations/classify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key-001" \
  -d '{
    "text": "My internet connection keeps dropping and the router shows a red light.",
    "categories": ["billing", "technical_support", "sales", "general_inquiry"],
    "request_id": "req-003"
  }'
```

**Response:**
```json
{
  "label": "technical_support",
  "confidence": 0.92,
  "scores": {
    "billing": 0.027,
    "technical_support": 0.92,
    "sales": 0.027,
    "general_inquiry": 0.027
  },
  "meta": {
    "operation": "classify",
    "model_used": "qwen-classify",
    "input_chars": 72,
    "output_tokens": 12,
    "execution_time_ms": 650.1,
    "request_id": "req-003",
    "timestamp": "2025-01-15T10:32:00.000Z"
  }
}
```

### GET /health

```bash
curl http://ai-platform.local/health
```

**Response:**
```json
{
  "status": "healthy",
  "uptime_seconds": 3600.5,
  "memory_used_mb": 14500.0,
  "memory_total_mb": 32768.0,
  "cpu_percent": 12.3,
  "models": [
    {"name": "summarize (qwen-summarize)", "loaded": true, "path": "/opt/ai_platform/models/qwen-summarize"},
    {"name": "translate (qwen-translate)", "loaded": true, "path": "/opt/ai_platform/models/qwen-translate"},
    {"name": "classify (qwen-classify)",   "loaded": true, "path": "/opt/ai_platform/models/qwen-classify"}
  ],
  "timestamp": "2025-01-15T10:33:00.000Z"
}
```

### GET /limits

```bash
curl -H "X-API-Key: local-dev-key-001" http://ai-platform.local/limits
```

**Response:**
```json
{
  "limits": [
    {"operation": "summarize", "daily_limit": 1000, "max_input_chars": 8000, "max_output_tokens": 512},
    {"operation": "translate", "daily_limit": 1000, "max_input_chars": 4000, "max_output_tokens": 512},
    {"operation": "classify",  "daily_limit": 1000, "max_input_chars": 2000, "max_output_tokens": 64}
  ]
}
```

### PUT /limits

```bash
curl -X PUT http://ai-platform.local/limits \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key-001" \
  -d '{"operation": "summarize", "daily_limit": 500}'
```

### GET /limits/usage

```bash
curl -H "X-API-Key: local-dev-key-001" http://ai-platform.local/limits/usage
```

**Response:**
```json
{
  "usage": [
    {
      "operation": "summarize",
      "date": "2025-01-15",
      "request_count": 47,
      "total_tokens": 2350,
      "daily_limit": 1000,
      "remaining": 953
    }
  ],
  "generated_at": "2025-01-15T10:34:00.000Z"
}
```

### Error Response Examples

**Validation error (422):**
```json
{
  "error": "Request validation failed.",
  "detail": [
    {
      "type": "string_too_long",
      "loc": ["body", "text"],
      "msg": "String should have at most 8000 characters",
      "input": "..."
    }
  ]
}
```

**Rate limit exceeded (429):**
```json
{
  "detail": "Daily limit exceeded for operation 'summarize': 1000/1000 requests used today."
}
```

**Invalid API key (403):**
```json
{
  "detail": "Invalid or missing API key."
}
```

---

## Troubleshooting

```bash
# Service won't start
sudo journalctl -u ai-platform -n 50 --no-pager

# Check if port is listening
ss -tlnp | grep 8000

# Check model directory
ls -la /opt/ai_platform/models/

# Run manually for debugging
cd /opt/ai_platform
sudo -u aiplatform ./venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# View application logs
tail -f /opt/ai_platform/logs/platform.log

# Test API directly (bypass Nginx)
curl http://127.0.0.1:8000/health
```
