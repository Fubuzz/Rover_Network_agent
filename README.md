# Rover - Your Network Nurturing Agent 🚀

*"Your AI-powered professional network manager"*

A comprehensive Telegram bot powered by CrewAI for managing and nurturing your professional network. Stores contacts in Google Sheets, enriches data through web searches, matches Founders with Investors, and generates personalized outreach emails.

**Version 2.2.0** | [Changelog](CHANGELOG.md)

### What's New in 2.2.0
- ✅ **Bulk Contact Import** - Upload CSV or Excel files to import contacts
- ✅ **Auto header detection** - Flexible column name mapping
- ✅ **Smart duplicate handling** - Updates existing contacts with new data
- ✅ **Import summary** - Shows added, updated, skipped, and failed counts

## Features

### Contact Management
- **Add contacts** from text, voice messages, images (business cards), or bulk imports
- **Update, view, delete, and search** contacts easily
- **Automatic classification** as founder, investor, enabler, or professional
- **Data validation** for emails, phones, and LinkedIn URLs

### Data Enrichment
- **Web search** for contact information via SerpAPI
- **LinkedIn profile discovery**
- **Company research** with news and background
- **AI-powered summaries** of search results

### Input Processing
- **Voice messages** - transcribed using OpenAI Whisper
- **Images** - OCR extraction from business cards using GPT-4 Vision
- **Natural language** - intelligent parsing of contact descriptions
- **Bulk import** - CSV and Excel file support with auto header detection

### Analytics & Evaluation
- **Real-time dashboard** for system monitoring
- **Operation tracking** with success/failure rates
- **Performance metrics** and trend analysis
- **Feature usage analytics**
- **Data quality assessment**

### AI-Powered Agents (CrewAI)
- **Contact Agent** - handles CRUD operations
- **Enrichment Agent** - researches contacts online
- **Input Agent** - processes various input formats
- **Classification Agent** - categorizes contacts
- **Reporting Agent** - generates statistics and reports
- **Evaluation Agent** - assesses data quality
- **Troubleshooting Agent** - handles errors

## Quick Start

### 1. Prerequisites
- Python 3.8 or higher
- A Telegram Bot token (from [@BotFather](https://t.me/BotFather))
- Google Cloud service account with Sheets API access
- API keys for OpenAI, Gemini, and SerpAPI

### 2. Installation

```bash
# Clone or navigate to the project
cd Rover_Network_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Copy the `.env.template` to `.env` and fill in your credentials:

```bash
cp .env.template .env
```

Edit `.env` with your API keys:
```
TELEGRAM_BOT_TOKEN=your_bot_token
GOOGLE_SHEETS_URL=your_sheet_url
SERPAPI_KEY=your_serpapi_key
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

### 4. Google Sheets Setup

1. Create a Google Cloud project
2. Enable the Google Sheets API
3. Create a service account and download the JSON credentials
4. Save as `credentials.json` in the project root
5. Share your Google Sheet with the service account email

**Sheet Structure:**
| Sheet | Name | Purpose |
|-------|------|---------|
| Sheet 1 | `contacts` | All network contacts (Founders, Investors, Enablers) |
| Sheet 2 | `Matches` | Founder-Investor match pairs with scores |
| Sheet 3 | `Drafts` | Email drafts for outreach |

### 5. Run the Bot

```bash
python main.py
```

## Commands

### Contact Management
| Command | Description |
|---------|-------------|
| `/add <info>` | Add a new contact |
| `/view <name>` | View contact details |
| `/update <name> <field> <value>` | Update a contact field |
| `/delete <name>` | Delete a contact |
| `/list` | List all contacts |
| `/search <query>` | Search contacts |

### Enrichment
| Command | Description |
|---------|-------------|
| `/enrich <name>` | Enrich contact with web search |
| `/research <company>` | Research a company |
| `/linkedin <name>` | Find LinkedIn profile |

### Reporting
| Command | Description |
|---------|-------------|
| `/stats` | Show contact statistics |
| `/stats by <attribute>` | Stats by attribute |
| `/report <name>` | Detailed contact report |
| `/export` | Export contacts to CSV |

### Matchmaker & Outreach
| Command | Description |
|---------|-------------|
| `/match` | Run matchmaker to pair Founders with Investors |
| `/matches` | View all saved matches |
| `/clear_matches` | Clear all matches |
| `/draft` | Generate email drafts for high-quality matches |
| `/drafts` | View all pending drafts |
| `/send` | Send approved email drafts |

### Organization
| Command | Description |
|---------|-------------|
| `/remind <name> <date>` | Set follow-up reminder |
| `/note <name> <note>` | Add note to contact |
| `/tag <name> <tags>` | Add tags to contact |
| `/ask <question>` | Ask about your network |

### Analytics & Evaluation
| Command | Description |
|---------|-------------|
| `/dashboard` | Real-time system dashboard |
| `/analytics` | Usage analytics overview |
| `/analytics operations` | Operation statistics |
| `/analytics features` | Feature usage stats |
| `/analytics performance` | Performance metrics |
| `/eval` | Evaluation summary |
| `/eval operations` | Operation evaluation |
| `/eval errors` | Error analysis |
| `/eval quality` | Data quality metrics |
| `/eval agents` | Agent performance |

### Help
| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all commands |

## Input Methods

### Text
Just type contact information naturally:
```
John Doe is the CEO at TechCorp, his email is john@techcorp.com
```

### Voice
Send a voice message describing the contact - it will be transcribed and parsed automatically.

### Image
Send a photo of a business card - OCR will extract the contact information.

### Bulk Import
Upload a CSV or TXT file with multiple contacts.

## Project Structure

```
Rover_Network_agent/
├── main.py                 # Entry point
├── config.py               # Configuration
├── requirements.txt        # Dependencies
├── .env                    # Environment variables
│
├── agents/                 # CrewAI agents
├── crews/                  # CrewAI crews
├── tools/                  # CrewAI tools
├── services/               # Core services
├── handlers/               # Telegram handlers
├── analytics/              # Analytics system
├── app_logging/            # Logging system
├── interfaces/             # Analytics interfaces
├── utils/                  # Utilities
├── data/                   # Data schemas
└── docs/                   # Documentation
```

## Configuration Options

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | Yes |
| `GOOGLE_SHEETS_URL` | Google Sheets URL | Yes |
| `GOOGLE_CREDENTIALS_FILE` | Path to credentials JSON | Yes |
| `SERPAPI_KEY` | SerpAPI key for web search | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes* |
| `OPENAI_API_KEY` | OpenAI API key | Yes* |
| `DEBUG_MODE` | Enable debug logging | No |
| `LOG_LEVEL` | Logging level | No |
| `AUTO_ENRICH_ENABLED` | Auto-enrich new contacts | No |
| `AUTO_CLASSIFY_ENABLED` | Auto-classify contacts | No |

*At least one AI API key required

## Analytics Database

The bot maintains a SQLite database for analytics:
- Operation tracking
- Feature usage statistics
- Agent activity logs
- Error logs
- Feature change history

Located at `logs/analytics.db`

## Troubleshooting

### Bot not responding
- Check that `TELEGRAM_BOT_TOKEN` is correct
- Ensure the bot is running (`python main.py`)
- Check logs in `logs/` directory

### Google Sheets not working
- Verify `GOOGLE_SHEETS_URL` is correct
- Ensure service account has edit access to the sheet
- Check `credentials.json` exists and is valid

### Enrichment not working
- Verify `SERPAPI_KEY` is valid
- Check API quota limits

### Voice/Image not working
- Ensure `OPENAI_API_KEY` is configured
- Check `VOICE_TRANSCRIPTION_ENABLED` and `IMAGE_OCR_ENABLED` in `.env`

## License

MIT License

## Support

For issues and feature requests, please open an issue on GitHub.
