# Setup Guide

This guide walks you through setting up the Telegram Network Nurturing Agent.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- A Google Cloud account
- API keys for various services

## Step 1: Telegram Bot Setup

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow prompts to name your bot
4. Copy the API token provided
5. Save it as `TELEGRAM_BOT_TOKEN` in your `.env` file

## Step 2: Google Sheets Setup

### Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the following APIs:
   - Google Sheets API
   - Google Drive API

### Create Service Account

1. Go to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
3. Name it (e.g., "network-agent-bot")
4. Grant "Editor" role
5. Click "Create Key" → JSON
6. Download the JSON file
7. Rename to `credentials.json` and place in project root

### Set Up Google Sheet

1. Create a new Google Sheet
2. Copy the URL
3. Share the sheet with your service account email (found in credentials.json)
4. Grant "Editor" access

## Step 3: API Keys

### SerpAPI (Web Search)

1. Go to [SerpAPI](https://serpapi.com/)
2. Create an account
3. Get your API key from dashboard
4. Save as `SERPAPI_KEY` in `.env`

### OpenAI API

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an account
3. Generate an API key
4. Save as `OPENAI_API_KEY` in `.env`

### Gemini API (Optional)

1. Go to [Google AI Studio](https://makersuite.google.com/)
2. Create an API key
3. Save as `GEMINI_API_KEY` in `.env`

## Step 4: Installation

```bash
# Navigate to project
cd Rover_Network_agent

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 5: Configuration

1. Copy template:
```bash
cp .env.template .env
```

2. Edit `.env` with your values:
```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_token_here

# Google Sheets
GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GOOGLE_CREDENTIALS_FILE=credentials.json

# APIs
SERPAPI_KEY=your_serpapi_key
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key

# Settings
BOT_NAME=NetworkNurturingBot
DEBUG_MODE=false
LOG_LEVEL=INFO
```

## Step 6: Run the Bot

```bash
python main.py
```

You should see:
```
INFO - Starting Telegram Network Nurturing Agent...
INFO - Configuration validated successfully
INFO - Registering handlers...
INFO - All handlers registered
INFO - Bot is starting... (@NetworkNurturingBot)
```

## Step 7: Test the Bot

1. Open Telegram
2. Find your bot by username
3. Send `/start` to verify it's working
4. Try `/help` to see available commands

## Troubleshooting

### "TELEGRAM_BOT_TOKEN is required"
- Ensure `.env` file exists
- Check the token is correct (no extra spaces)

### "Google Sheets service failed to initialize"
- Verify `credentials.json` exists
- Check service account has access to the sheet
- Ensure Google Sheets URL is correct

### "Could not transcribe voice message"
- Verify OpenAI API key is valid
- Check you have credits in your OpenAI account

### Bot not responding
- Check terminal for error messages
- Verify bot token is correct
- Ensure no other instance is running

## Running in Production

### Using systemd (Linux)

Create `/etc/systemd/system/network-agent.service`:

```ini
[Unit]
Description=Telegram Network Agent
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Rover_Network_agent
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable network-agent
sudo systemctl start network-agent
```

### Using Docker (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Build and run:
```bash
docker build -t network-agent .
docker run -d --env-file .env network-agent
```
