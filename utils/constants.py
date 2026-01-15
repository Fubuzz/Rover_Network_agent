"""
Constants and enums for the Telegram Network Nurturing Agent.
"""

# Bot Commands
COMMANDS = {
    # Contact Management
    "add": "Add a new contact",
    "update": "Update an existing contact",
    "view": "View contact information",
    "delete": "Delete a contact",
    "list": "List all contacts",
    "search": "Search contacts",
    
    # Enrichment
    "enrich": "Enrich contact with online search",
    "research": "Research a company",
    
    # Reporting
    "stats": "Show contact statistics",
    "report": "Generate detailed report",
    "export": "Export contacts to CSV",
    
    # Reminders & Notes
    "remind": "Set a follow-up reminder",
    "note": "Add a note to a contact",
    "tag": "Add tags to a contact",
    
    # Analytics & Evaluation
    "analytics": "Show usage analytics",
    "eval": "Show evaluation statistics",
    "dashboard": "Show real-time dashboard",
    
    # Help
    "help": "Show help message",
    "start": "Start the bot",
}

# Classification Keywords
CLASSIFICATION_KEYWORDS = {
    "founder": [
        "founder", "co-founder", "cofounder", "ceo", "chief executive",
        "started", "built", "created", "entrepreneur", "founding"
    ],
    "investor": [
        "investor", "vc", "venture capital", "angel", "partner at",
        "investment", "fund", "capital", "portfolio", "pe", "private equity"
    ],
    "enabler": [
        "advisor", "mentor", "consultant", "coach", "accelerator",
        "incubator", "community", "ecosystem", "support", "enabler"
    ],
    "professional": [
        "manager", "director", "engineer", "developer", "designer",
        "analyst", "specialist", "coordinator", "executive", "lead"
    ]
}

# Message Templates - Donna Paulsen Style 💅
MESSAGES = {
    "welcome": """
Well, well, well... look who finally decided to get organized. 💁‍♀️

I'm your Network Nurturing Agent, and yes, I'm basically Donna Paulsen for your contacts. I know everything, I remember everything, and I'm always three steps ahead.

**What I can do (because I can do everything):**
✨ Add contacts from text, voice, or business card photos
🔍 Dig up intel on anyone (legally, of course)
🏷️ Classify your network like the VIPs they are
📊 Generate reports that'll make you look brilliant
📝 Remember things you've already forgotten

I don't get coffee, but I do get results.

Type /help if you need me to spell it out for you. 😉
    """,
    
    "help": """
Alright, pay attention because I'm only explaining this once. 📋

**Contact Management** _(the basics)_
/add - Add someone to my impeccable memory
/view <name> - Pull up everything I know
/update <name> - Fix your mistakes
/delete <name> - Make them disappear ✨
/list - See everyone (you're welcome)
/search <query> - Find that person you forgot

**Research & Intel** _(my specialty)_
/enrich <name> - I'll dig up the good stuff
/research <company> - Company deep dive
/linkedin <name> - Find their LinkedIn

**Reports & Stats** _(making you look good)_
/stats - The numbers, darling
/report <name> - Full dossier on someone
/export - Everything in a neat CSV

**Stay Organized** _(because you need me)_
/remind <name> <date> - I'll remind you to follow up
/note <name> <note> - Add gossip... I mean, notes
/tag <name> <tags> - Categorize your people
/ask <question> - Ask me anything about your network

**Behind the Scenes** 🎭
/dashboard - How things are running
/analytics - Usage stats
/eval - Performance review

**Pro Tips:**
📱 Send me a voice memo - I'll transcribe it
📸 Send a business card photo - I'll read it
💬 Just type naturally - I'll figure it out

_I'm just that good._ 💅
    """,
    
    "contact_added": "Done. **{name}** is now in my vault. 📁\n\n_You're welcome._",
    "contact_updated": "**{name}** has been updated. I keep things current, unlike some people's LinkedIn profiles. 💅",
    "contact_deleted": "**{name}** has been removed. It's like they never existed. 🗑️\n\n_I won't ask questions._",
    "contact_not_found": "Hmm, I don't have anyone named **{name}** in my records. And I have *everyone*. 🤔\n\nDouble-check the spelling?",
    "contact_enriched": "I did some digging on **{name}**. 🔍\n\nYou can thank me later.",
    
    "error_generic": "Okay, that didn't work. Even I have my limits. Let's try that again. 🔄",
    "error_no_permission": "Nice try, but you don't have clearance for that. 🚫",
    "error_invalid_input": "I'm good, but I'm not a mind reader. Give me something I can work with. 💭",
    
    "processing": "On it. Give me a second... ⏳",
    "transcribing": "Listening... 🎧\n\n_Yes, I can hear you._",
    "extracting": "Analyzing this... 🔍\n\n_I see what you did there._",
    "enriching": "Doing my research... 📚\n\n_Time to see what the internet knows._",
    "classifying": "Categorizing... 🏷️\n\n_Everyone gets a label._",
    
    # New Donna-style messages
    "greeting_morning": "Good morning! Ready to network like a boss? ☕",
    "greeting_afternoon": "Afternoon! Let's get things done. 💼",
    "greeting_evening": "Evening! Still grinding? I respect that. 🌙",
    
    "empty_search": "Nothing found. Either they don't exist, or they're hiding from you. 🤷‍♀️",
    "bulk_import_start": "Bulk import? Now we're talking. Let me work my magic... ✨",
    "bulk_import_done": "Done! Imported {count} contacts. That's {count} more people who should be grateful you know them. 😏",
    
    "stats_intro": "Here's the tea on your network: ☕",
    "report_intro": "Alright, here's everything I know about **{name}**. And I know *everything*. 📋",
    
    "reminder_set": "Reminder set for **{name}** on {date}. ⏰\n\n_I'll make sure you don't forget. Unlike that time you... never mind._",
    "note_added": "Note added to **{name}**. 📝\n\n_Your secrets are safe with me._",
    "tags_added": "Tags added to **{name}**: {tags}\n\n_Organization is my middle name. Actually, it's not, but you get it._ 🏷️",
    
    "voice_received": "Got your voice memo. Let me decode what you're trying to say... 🎤",
    "image_received": "Business card detected. Reading it now... 👀\n\n_Nice font choice._",
    
    "unknown_input": """
I'm not sure what you're going for there. 🤔

Try one of these:
• Send me contact info (name, email, company...)
• Record a voice memo
• Snap a business card
• Or use /help if you're really lost

_I'm here to help, not judge._ 😉
    """,
    
    "goodbye": "Off you go then. I'll be here, keeping everything organized. As always. 👋",
}

# Regex Patterns
PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,}",
    "linkedin": r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?",
    "url": r"https?://[^\s<>\"{}|\\^`\[\]]+",
}

# API Rate Limits
RATE_LIMITS = {
    "serpapi": 100,  # requests per month (free tier)
    "openai": 60,    # requests per minute
    "gemini": 60,    # requests per minute
}

# Analytics Metrics
METRICS = {
    "success_rate_threshold": 0.9,  # 90% success rate is healthy
    "avg_response_time_threshold": 5000,  # 5 seconds
    "error_rate_threshold": 0.1,  # 10% error rate is concerning
}

# Default Values
DEFAULTS = {
    "page_size": 10,  # contacts per page
    "search_limit": 20,  # max search results
    "enrichment_timeout": 30,  # seconds
    "transcription_timeout": 60,  # seconds
}
