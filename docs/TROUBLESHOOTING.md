# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Telegram Network Nurturing Agent.

## Quick Diagnostics

### Check System Status

```bash
# View dashboard
/dashboard
```

This shows:
- System health status
- Today's operations
- Success rate
- Recent activity

### Check Errors

```bash
# View error analysis
/eval errors
```

### Check Logs

```bash
# Main log
tail -f logs/main.log

# Errors only
tail -f logs/errors.log

# Operations
tail -f logs/operations.log
```

## Common Issues

### Bot Not Responding

**Symptoms**: Bot doesn't reply to messages

**Possible Causes & Solutions**:

1. **Bot not running**
   ```bash
   # Check if running
   ps aux | grep main.py
   
   # Restart
   python main.py
   ```

2. **Invalid token**
   - Check `TELEGRAM_BOT_TOKEN` in `.env`
   - Get new token from [@BotFather](https://t.me/BotFather)

3. **Network issues**
   - Check internet connection
   - Verify firewall allows outbound HTTPS

4. **Multiple instances**
   - Only one instance can use a token
   - Kill other instances: `pkill -f main.py`

---

### "Configuration Error" on Startup

**Symptoms**: Bot fails to start with configuration error

**Solutions**:

1. Check `.env` file exists
2. Verify all required variables are set:
   ```
   TELEGRAM_BOT_TOKEN=xxx
   GOOGLE_SHEETS_URL=xxx
   SERPAPI_KEY=xxx
   OPENAI_API_KEY=xxx
   ```
3. Remove extra spaces/quotes from values
4. Ensure no trailing newlines

---

### Google Sheets Not Working

**Symptoms**: "Failed to initialize Google Sheets" or contact operations fail

**Solutions**:

1. **Check credentials file**
   - Verify `credentials.json` exists in project root
   - Ensure it's valid JSON (no typos from copy/paste)

2. **Check sheet access**
   - Open Google Sheet manually
   - Verify service account email has Editor access
   - Service account email is in `credentials.json` under `client_email`

3. **Check sheet URL**
   - Verify `GOOGLE_SHEETS_URL` in `.env`
   - URL should be the full sheet URL

4. **API not enabled**
   - Go to Google Cloud Console
   - Enable Google Sheets API
   - Enable Google Drive API

5. **Rate limiting**
   - Google Sheets has quota limits
   - Wait a few minutes and retry

---

### Voice Transcription Fails

**Symptoms**: "Could not transcribe voice message"

**Solutions**:

1. **Check OpenAI API key**
   - Verify `OPENAI_API_KEY` in `.env`
   - Ensure key is valid and has credits

2. **Check feature flag**
   - Verify `VOICE_TRANSCRIPTION_ENABLED=true`

3. **Audio format issues**
   - Try shorter voice messages
   - Speak clearly

4. **API quota**
   - Check OpenAI usage dashboard
   - Add credits if needed

---

### Image OCR Fails

**Symptoms**: "Could not extract from image"

**Solutions**:

1. **Check OpenAI API key**
   - GPT-4 Vision requires valid OpenAI key
   - Ensure account has GPT-4 access

2. **Image quality**
   - Use clear, well-lit photos
   - Avoid blurry or dark images
   - Center the business card in frame

3. **Feature flag**
   - Verify `IMAGE_OCR_ENABLED=true`

4. **File size**
   - Telegram compresses large images
   - Try a smaller image if needed

---

### Enrichment Not Working

**Symptoms**: "Error enriching contact"

**Solutions**:

1. **Check SerpAPI key**
   - Verify `SERPAPI_KEY` in `.env`
   - Check quota at serpapi.com dashboard

2. **Contact not found**
   - Verify contact exists with `/view Name`
   - Check exact spelling

3. **No results**
   - Person may not have online presence
   - Try company research instead: `/research Company`

---

### Classification Wrong

**Symptoms**: Contacts classified incorrectly

**Solutions**:

1. **Provide more context**
   - Include job title and company when adding
   - Add notes about the person's role

2. **Manual update**
   ```
   /update John Doe classification investor
   ```

3. **Classification definitions**
   - Founder: Founders, co-founders, CEOs of startups
   - Investor: VCs, angels, investment professionals
   - Enabler: Advisors, mentors, connectors
   - Professional: Everyone else

---

### Slow Response Times

**Symptoms**: Bot takes long to respond

**Solutions**:

1. **Check performance**
   ```
   /analytics performance
   ```

2. **Reduce API calls**
   - Enrichment makes multiple API calls
   - Search operations query external APIs

3. **Check external services**
   - OpenAI status: status.openai.com
   - Google status: status.cloud.google.com

4. **Local performance**
   - Check CPU/memory usage
   - Restart bot if needed

---

### Analytics Database Issues

**Symptoms**: Analytics commands fail

**Solutions**:

1. **Check database exists**
   ```bash
   ls -la logs/analytics.db
   ```

2. **Check permissions**
   ```bash
   chmod 644 logs/analytics.db
   ```

3. **Recreate database**
   ```bash
   rm logs/analytics.db
   # Restart bot - database auto-creates
   python main.py
   ```

---

### Import/Export Issues

**Symptoms**: CSV import fails or export corrupted

**Solutions**:

1. **CSV format**
   - Use UTF-8 encoding
   - Use comma delimiter
   - First row should be headers

2. **Required fields**
   - At minimum, include "Name" column

3. **Check for errors**
   - Import shows count of successful/failed
   - Check specific errors in response

---

## Error Messages

### "Validation Error"

Data doesn't meet requirements:
- Email: must be valid format
- Phone: must contain digits
- URL: must be valid URL format

**Solution**: Check and correct the data format

### "Rate limit exceeded"

API quota exceeded.

**Solution**: Wait and retry, or check API quotas

### "Authentication failed"

API key invalid or expired.

**Solution**: Check and update API keys in `.env`

### "Contact not found"

Contact doesn't exist in database.

**Solution**: Check spelling, use `/search` to find

### "Permission denied"

File system permission issue.

**Solution**: Check file permissions, run with correct user

---

## Getting Help

### Self-Diagnosis

1. Check `/dashboard` for system status
2. Check `/eval errors` for recent errors
3. Review logs in `logs/` directory
4. Enable debug mode: `DEBUG_MODE=true`

### Collecting Debug Info

```bash
# Collect diagnostic info
echo "=== System Info ==="
python --version
pip freeze | grep -E "telegram|crewai|openai|gspread"

echo "=== Recent Errors ==="
tail -50 logs/errors.log

echo "=== Config Check ==="
cat .env | grep -v KEY | grep -v TOKEN  # Redact secrets
```

### Reporting Issues

When reporting issues, include:
1. Error message (exact text)
2. Steps to reproduce
3. Bot version
4. Python version
5. Relevant log excerpts (redact secrets!)
