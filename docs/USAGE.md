# Usage Guide

This guide explains how to use the Telegram Network Nurturing Agent effectively.

## Getting Started

After setting up the bot, open Telegram and start a conversation with your bot.

### Starting the Bot

Send `/start` to receive a welcome message and overview of capabilities.

Send `/help` to see all available commands.

## Adding Contacts

### Method 1: Command

```
/add John Doe, CEO at TechCorp, john@techcorp.com, +1-555-0123
```

### Method 2: Natural Language

Just type contact information naturally:

```
I just met Sarah Johnson, she's the VP of Engineering at StartupXYZ. 
Her email is sarah@startupxyz.com and LinkedIn is linkedin.com/in/sarahjohnson
```

The bot will parse the text and extract contact details.

### Method 3: Voice Message

Record a voice message describing the contact:

> "Add a new contact, his name is Michael Chen, he's a partner at Sequoia Capital. 
> I met him at the tech conference yesterday."

### Method 4: Business Card Photo

Take a photo of a business card and send it. The bot will use OCR to extract:
- Name
- Job title
- Company
- Email
- Phone
- LinkedIn

### Method 5: Bulk Import (CSV/Excel)

Upload a CSV or Excel file to import multiple contacts at once.

**Supported Formats:**
- CSV (.csv) - Comma-separated values
- Excel (.xlsx, .xls) - Microsoft Excel files

**How to Use:**
1. Create a spreadsheet with contact data
2. Make sure the first row contains headers
3. Upload the file directly to the bot chat

**Sample CSV format:**
```csv
Name,Email,Company,Title,Phone,Type
John Doe,john@techcorp.com,TechCorp,CEO,+1-555-0123,founder
Jane Smith,jane@investco.com,InvestCo,Partner,,investor
Bob Wilson,bob@acme.com,Acme Inc,CTO,+1-555-0456,founder
```

**Flexible Header Detection:**

The bot automatically recognizes various header names:

| Field | Accepted Headers |
|-------|------------------|
| Name | Name, Full Name, Contact Name, First Name, Last Name |
| Email | Email, E-mail, Email Address, Mail |
| Company | Company, Organization, Firm, Org |
| Title | Title, Job Title, Position, Role |
| Phone | Phone, Mobile, Tel, Telephone, Cell |
| LinkedIn | LinkedIn, LinkedIn URL, LinkedIn Profile |
| Type | Type, Contact Type, Category, Classification |
| Industry | Industry, Sector |
| Notes | Notes, Note, Comments |
| Address | Location, Address, City, Country |

**Duplicate Handling:**
- If a contact with the same email already exists → **Updates** the existing record
- If a contact with the same name exists → **Updates** the existing record
- New contacts → **Added** as new rows

**Import Results:**

After import, the bot reports:
- Total rows processed
- Contacts added (new)
- Contacts updated (existing)
- Contacts skipped (invalid)
- Contacts failed (errors)
- First 5 error messages (if any)

## Viewing Contacts

### View Specific Contact
```
/view John Doe
```

Returns full contact card with all information.

### List All Contacts
```
/list
```

Shows paginated list of all contacts.

### Search Contacts
```
/search TechCorp
/search founder
/search New York
```

Searches across all fields.

## Updating Contacts

```
/update John Doe email newemail@company.com
/update John Doe phone +1-555-9999
/update John Doe company NewCorp
```

## Enriching Contacts

### Enrich a Contact
```
/enrich John Doe
```

Searches the web for:
- LinkedIn profile
- Company information
- Recent news
- Professional background

### Research a Company
```
/research TechCorp
```

Returns company research with:
- LinkedIn company page
- Recent news
- Key information

### Find LinkedIn
```
/linkedin John Doe TechCorp
```

Searches specifically for LinkedIn profile.

## Organization

### Add Tags
```
/tag John Doe ai,startup,investor
```

### Add Notes
```
/note John Doe Met at AI Summit 2024, interested in B2B SaaS
```

### Set Reminders
```
/remind John Doe next week
/remind Sarah Johnson January 15
```

## Statistics & Reports

### General Statistics
```
/stats
```

Shows:
- Total contacts
- By classification
- Top companies
- Data completeness

### Statistics by Attribute
```
/stats by company
/stats by location
/stats by classification
```

### Detailed Report
```
/report John Doe
```

Generates comprehensive report for a contact.

### Network Insights
```
/report all
```

Generates overall network analysis.

### Export Data
```
/export
```

Downloads all contacts as CSV file.

## Analytics & Monitoring

### Dashboard
```
/dashboard
```

Real-time system status showing:
- System health
- Today's operations
- Success rate
- Recent activity

### Analytics
```
/analytics                    # Overview
/analytics operations         # Operation stats
/analytics features          # Feature usage
/analytics performance       # Performance metrics
/analytics export 30         # Export 30 days of data
```

### Evaluation
```
/eval                        # Summary
/eval operations             # Operation evaluation
/eval errors                 # Error analysis
/eval quality                # Data quality metrics
/eval agents                 # Agent performance
```

## Asking Questions

Use `/ask` for natural language queries:

```
/ask Who works at TechCorp?
/ask How many founders do I know?
/ask Who did I add last week?
/ask Show me contacts in San Francisco
```

## Direct Outreach

### `/outreach` Command

Send personalized outreach emails to filtered contacts using natural language:

```
/outreach Email all investors in Egypt about a meeting March 5-12
/outreach Reach out to fintech founders to introduce Synapse
/outreach Send a warm email to my professional contacts about catching up
```

**How it works:**
1. Your request is parsed into structured filter criteria (contact type, industry, location, etc.)
2. Matching contacts are found in your network
3. A personalized email is generated for each contact using GPT
4. Drafts are saved to the Airtable Drafts table with status **PENDING**
5. Review drafts in Airtable and set `approval_status` to **APPROVED**
6. Run `/send_approved` to send the approved emails via SMTP

**Via natural conversation:**

You can also trigger outreach through the conversational agent:
```
"Can you email my fintech investors about meeting next week?"
"Draft emails to all founders in Cairo about our product launch"
```

The agent will filter contacts, generate personalized emails, and save them as pending drafts — all through the same approval pipeline.

**Notes:**
- Contacts without an email address are skipped (reported in the summary)
- Direct outreach drafts use `match_id = "DIRECT_OUTREACH"` to distinguish from match-based drafts
- The existing `/draft` command (match-based) is unchanged

## Tips & Best Practices

### Adding Contacts
1. Include as much information as possible
2. Use the enrichment feature to fill gaps
3. Voice messages work great for quick additions

### Organizing
1. Use consistent tag naming (lowercase, hyphens)
2. Add meeting notes immediately
3. Set follow-up reminders

### Data Quality
1. Check `/eval quality` regularly
2. Enrich contacts with incomplete data
3. Use the dashboard to monitor operations

### Performance
1. Use specific searches rather than browsing
2. Export periodically for backup
3. Monitor analytics for issues

## Common Workflows

### After a Meeting
1. Add contact via voice or text
2. Bot auto-classifies
3. Add meeting notes: `/note Name discussed partnership opportunities`
4. Set reminder: `/remind Name 2 weeks`

### Research Before a Meeting
1. View contact: `/view Name`
2. Enrich if needed: `/enrich Name`
3. Research company: `/research CompanyName`

### Weekly Review
1. Check dashboard: `/dashboard`
2. Review stats: `/stats`
3. Export if needed: `/export`
