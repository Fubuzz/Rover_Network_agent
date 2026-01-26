# 🚀 Rover Network Agent - Deployment Plan

## Table of Contents
1. [Deployment Options](#deployment-options)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Environment Configuration](#environment-configuration)
4. [Option A: Railway (Recommended)](#option-a-railway-recommended)
5. [Option B: DigitalOcean](#option-b-digitalocean)
6. [Option C: AWS EC2](#option-c-aws-ec2)
7. [Option D: Google Cloud Run](#option-d-google-cloud-run)
8. [Option E: Render](#option-e-render)
9. [Docker Deployment](#docker-deployment)
10. [Monitoring & Logging](#monitoring--logging)
11. [Security Best Practices](#security-best-practices)
12. [Cost Estimates](#cost-estimates)
13. [Troubleshooting](#troubleshooting)

---

## Deployment Options

| Platform | Difficulty | Cost/Month | Best For |
|----------|------------|------------|----------|
| **Railway** | ⭐ Easy | $5-20 | Quick deploy, auto-scaling |
| **Render** | ⭐ Easy | $7-25 | Simple hosting, free tier |
| **DigitalOcean** | ⭐⭐ Medium | $6-24 | Full control, reliable |
| **AWS EC2** | ⭐⭐⭐ Complex | $5-50 | Enterprise, scalability |
| **Google Cloud Run** | ⭐⭐ Medium | Pay-per-use | Serverless, auto-scaling |

**Recommendation:** Start with **Railway** or **Render** for simplicity.

---

## Pre-Deployment Checklist

### ✅ Code Preparation
- [ ] All tests passing
- [ ] No hardcoded secrets in code
- [ ] `.env.example` file created
- [ ] `requirements.txt` up to date
- [ ] Error handling in place
- [ ] Logging configured properly

### ✅ API Keys Ready
- [ ] Telegram Bot Token (`TELEGRAM_BOT_TOKEN`)
- [ ] OpenAI API Key (`OPENAI_API_KEY`)
- [ ] Gemini API Key (`GEMINI_API_KEY`)
- [ ] Tavily API Key (`TAVILY_API_KEY`)
- [ ] Airtable credentials (`AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`)
- [ ] SMTP credentials (`SMTP_USER`, `SMTP_PASSWORD`)

### ✅ Infrastructure
- [ ] Domain (optional but recommended)
- [ ] SSL certificate (usually auto-provisioned)
- [ ] Backup strategy for data
- [ ] Monitoring setup

---

## Environment Configuration

Create `.env.production`:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_production_token

# AI Services
OPENAI_API_KEY=your_key
GEMINI_API_KEY=your_key
TAVILY_API_KEY=your_key

# Airtable
AIRTABLE_API_KEY=your_key
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_CONTACTS_TABLE=Contacts
AIRTABLE_MATCHES_TABLE=Matches
AIRTABLE_DRAFTS_TABLE=Drafts

# SMTP (Email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_FROM_NAME=Rover Network Agent

# Feature Flags
ANALYTICS_ENABLED=true
ENRICHMENT_ENABLED=true
EMAIL_ENABLED=true

# Production Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## Option A: Railway (Recommended)

### Why Railway?
- One-click deployment from GitHub
- Automatic builds and deploys
- Built-in environment variables
- Free tier available ($5/month credit)
- Easy scaling

### Steps

1. **Create Railway Account**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Connect Repository**
   ```bash
   # Push your code to GitHub first
   git init
   git add .
   git commit -m "Initial commit for deployment"
   git remote add origin https://github.com/yourusername/rover-network-agent.git
   git push -u origin main
   ```

3. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

4. **Configure Environment Variables**
   - Go to Variables tab
   - Add all variables from `.env.production`

5. **Configure Build Settings**
   - Start Command: `python main.py`
   - Build Command: `pip install -r requirements.txt`

6. **Deploy**
   - Railway will automatically build and deploy
   - Check logs for any errors

### Railway Configuration File

Create `railway.toml`:
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "python main.py"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

---

## Option B: DigitalOcean

### Steps

1. **Create Droplet**
   - Choose Ubuntu 22.04
   - Select $6/month plan (1GB RAM)
   - Add SSH key

2. **Initial Server Setup**
   ```bash
   # SSH into server
   ssh root@your_server_ip
   
   # Update system
   apt update && apt upgrade -y
   
   # Install Python
   apt install python3.11 python3.11-venv python3-pip -y
   
   # Create app user
   adduser roverbot
   usermod -aG sudo roverbot
   ```

3. **Deploy Application**
   ```bash
   # Switch to app user
   su - roverbot
   
   # Clone repository
   git clone https://github.com/yourusername/rover-network-agent.git
   cd rover-network-agent
   
   # Create virtual environment
   python3.11 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Create .env file
   nano .env
   # Paste your production environment variables
   ```

4. **Create Systemd Service**
   ```bash
   sudo nano /etc/systemd/system/roverbot.service
   ```
   
   Content:
   ```ini
   [Unit]
   Description=Rover Network Agent Telegram Bot
   After=network.target
   
   [Service]
   Type=simple
   User=roverbot
   WorkingDirectory=/home/roverbot/rover-network-agent
   Environment=PATH=/home/roverbot/rover-network-agent/venv/bin
   ExecStart=/home/roverbot/rover-network-agent/venv/bin/python main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

5. **Start Service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable roverbot
   sudo systemctl start roverbot
   
   # Check status
   sudo systemctl status roverbot
   
   # View logs
   sudo journalctl -u roverbot -f
   ```

---

## Option C: AWS EC2

### Steps

1. **Launch EC2 Instance**
   - AMI: Ubuntu 22.04 LTS
   - Instance type: t3.micro (free tier) or t3.small
   - Security group: Allow SSH (22)
   - Create/select key pair

2. **Install & Configure**
   ```bash
   # SSH into instance
   ssh -i your-key.pem ubuntu@your-ec2-ip
   
   # Install dependencies
   sudo apt update && sudo apt upgrade -y
   sudo apt install python3.11 python3.11-venv python3-pip git -y
   
   # Clone and setup (same as DigitalOcean)
   git clone https://github.com/yourusername/rover-network-agent.git
   cd rover-network-agent
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Create .env
   nano .env
   ```

3. **Use PM2 or Supervisor for Process Management**
   ```bash
   # Install supervisor
   sudo apt install supervisor -y
   
   # Create config
   sudo nano /etc/supervisor/conf.d/roverbot.conf
   ```
   
   Content:
   ```ini
   [program:roverbot]
   command=/home/ubuntu/rover-network-agent/venv/bin/python main.py
   directory=/home/ubuntu/rover-network-agent
   user=ubuntu
   autostart=true
   autorestart=true
   stderr_logfile=/var/log/roverbot.err.log
   stdout_logfile=/var/log/roverbot.out.log
   ```

---

## Option D: Google Cloud Run

### Steps

1. **Create Dockerfile** (see Docker section below)

2. **Build and Push to GCR**
   ```bash
   # Install gcloud CLI
   # Authenticate
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   
   # Build and push
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/rover-bot
   ```

3. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy rover-bot \
     --image gcr.io/YOUR_PROJECT_ID/rover-bot \
     --platform managed \
     --region us-central1 \
     --set-env-vars "TELEGRAM_BOT_TOKEN=xxx,OPENAI_API_KEY=xxx" \
     --memory 512Mi \
     --timeout 300
   ```

---

## Option E: Render

### Steps

1. **Create `render.yaml`**
   ```yaml
   services:
     - type: worker
       name: rover-network-agent
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: python main.py
       envVars:
         - key: TELEGRAM_BOT_TOKEN
           sync: false
         - key: OPENAI_API_KEY
           sync: false
         - key: GEMINI_API_KEY
           sync: false
         - key: TAVILY_API_KEY
           sync: false
         - key: AIRTABLE_API_KEY
           sync: false
         - key: AIRTABLE_BASE_ID
           sync: false
   ```

2. **Connect GitHub & Deploy**
   - Go to [render.com](https://render.com)
   - New > Worker
   - Connect GitHub repository
   - Add environment variables
   - Deploy

---

## Docker Deployment

### Dockerfile

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the bot
CMD ["python", "main.py"]
```

### Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  rover-bot:
    build: .
    container_name: rover-network-agent
    restart: always
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Build & Run
```bash
# Build
docker build -t rover-bot .

# Run
docker run -d --name rover-bot --env-file .env.production rover-bot

# Or with docker-compose
docker-compose up -d
```

---

## Monitoring & Logging

### 1. Application Logging

The bot already logs to console. For production, add file logging:

```python
# In config.py or a logging config file
import logging
from logging.handlers import RotatingFileHandler

def setup_production_logging():
    handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logging.getLogger().addHandler(handler)
```

### 2. Health Check Endpoint (Optional)

Add a simple HTTP health check:

```python
# health_check.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

def start_health_server(port=8080):
    server = HTTPServer(('', port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
```

### 3. External Monitoring

**Recommended Services:**
- **UptimeRobot** (Free) - Basic uptime monitoring
- **Better Uptime** - Incident management
- **Datadog** - Full observability (paid)
- **Sentry** - Error tracking

### 4. Alerts Setup

```python
# Add to error handling
import requests

def send_alert(message: str):
    """Send alert to Telegram admin."""
    admin_chat_id = os.getenv('ADMIN_CHAT_ID')
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if admin_chat_id:
        requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={'chat_id': admin_chat_id, 'text': f'🚨 Alert: {message}'}
        )
```

---

## Security Best Practices

### 1. Environment Variables
- ✅ Never commit `.env` to git
- ✅ Use different tokens for dev/prod
- ✅ Rotate API keys periodically

### 2. Access Control
```bash
# Restrict bot to specific users (add to handlers)
ALLOWED_USERS = [123456789, 987654321]  # Telegram user IDs

def restricted(func):
    async def wrapper(update, context):
        if update.effective_user.id not in ALLOWED_USERS:
            await update.message.reply_text("Unauthorized")
            return
        return await func(update, context)
    return wrapper
```

### 3. Rate Limiting
```python
from functools import wraps
from collections import defaultdict
import time

user_last_request = defaultdict(float)

def rate_limit(seconds=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context):
            user_id = update.effective_user.id
            now = time.time()
            if now - user_last_request[user_id] < seconds:
                return
            user_last_request[user_id] = now
            return await func(update, context)
        return wrapper
    return decorator
```

### 4. Server Security (VPS)
```bash
# Firewall
sudo ufw allow ssh
sudo ufw enable

# Fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban

# Automatic updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

---

## Cost Estimates

| Service | Plan | Monthly Cost | Notes |
|---------|------|--------------|-------|
| **Railway** | Starter | $5-20 | Based on usage |
| **Render** | Worker | $7 | Fixed |
| **DigitalOcean** | Droplet | $6 | 1GB RAM |
| **AWS EC2** | t3.micro | $0-10 | Free tier 1 year |
| **Cloud Run** | Serverless | $0-15 | Pay per request |

**API Costs (in addition):**
- OpenAI: ~$5-50/month depending on usage
- Tavily: Free tier or $20/month
- Airtable: Free tier or $20/month

**Total Estimated:** $15-75/month

---

## Troubleshooting

### Bot Not Responding
```bash
# Check if process is running
ps aux | grep python

# Check logs
journalctl -u roverbot -n 100

# Restart service
sudo systemctl restart roverbot
```

### API Errors
- Verify all API keys are correct
- Check rate limits
- Ensure billing is active on paid services

### Memory Issues
```bash
# Check memory usage
free -m

# If running out of memory, increase swap
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Common Errors

| Error | Solution |
|-------|----------|
| `Unauthorized` | Check TELEGRAM_BOT_TOKEN |
| `Rate limit exceeded` | Implement rate limiting |
| `Connection refused` | Check firewall, service status |
| `Out of memory` | Increase RAM or add swap |

---

## Quick Start Commands

```bash
# Local testing
python main.py

# Docker
docker-compose up -d

# Railway
railway up

# Check status
railway logs
```

---

## Post-Deployment Checklist

- [ ] Bot responds to `/start`
- [ ] Contact creation works
- [ ] Research/enrichment functions
- [ ] Email sending works
- [ ] Airtable sync works
- [ ] Error alerts configured
- [ ] Logs being captured
- [ ] Backup strategy in place

---

## Support

If you encounter issues:
1. Check the logs first
2. Verify all environment variables
3. Test API keys individually
4. Check service status pages (OpenAI, Telegram, etc.)
