# Rover V3 — Master Plan: The World's Best Network Nurturing Agent

**Author:** Daisuke (AI Engineer)  
**Date:** February 20, 2026  
**Status:** In Progress  

---

## Vision

Rover isn't a CRM. It's your **relationship intelligence engine** — an AI that doesn't just store contacts, it actively nurtures your network, surfaces opportunities before you see them, and makes you the best-connected person in every room.

**The difference:**
- CRM = You manage contacts
- Rover = Rover manages your relationships FOR you

---

## Current State Assessment (V2.2)

### What's Good ✅
- Solid Telegram interface with multi-input (voice, photo, text, CSV)
- Clean Python codebase with good separation of concerns
- Airtable backend (accessible, shareable)
- Matchmaker concept is strong
- Deferred saving + conversation state machine works
- Enrichment pipeline exists

### What's Holding It Back ❌
1. **No actual "nurturing"** — It's contact storage, not relationship management
2. **Dumb agent** — GPT-4o-mini with a giant prompt, no memory across sessions
3. **CrewAI overhead** — 7 agents for what could be 1 smart agent with tools
4. **No proactive behavior** — Never reaches out to user unless asked
5. **Slow** — CrewAI + multiple LLM calls per simple action
6. **Single-user** — No auth system
7. **No relationship intelligence** — No interaction tracking, no decay, no signals
8. **Enrichment is shallow** — Basic web search, no real LinkedIn data
9. **Matchmaker is a one-shot** — Should be continuous and learning
10. **No integrations** — No calendar, no email inbox monitoring, no social tracking

---

## V3 Architecture: The Overhaul

### Philosophy
- **Speed first** — Every interaction should feel instant (<2s response)
- **Proactive, not reactive** — Rover should message YOU before you ask
- **Intelligence, not storage** — Every feature should surface insights
- **Simple internals** — Kill CrewAI overhead, use direct OpenAI function calling
- **Event-driven** — Background jobs for enrichment, reminders, matching

### New Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      TELEGRAM INTERFACE                          │
│  • Natural conversation (text, voice, photo, documents)         │
│  • Inline keyboards for quick actions                           │
│  • Proactive messages (reminders, insights, suggestions)        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ROVER BRAIN (Single Agent)                  │
│  • GPT-4o with function calling (not 4o-mini)                   │
│  • Conversation memory (last 20 messages per user)              │
│  • Context-aware system prompt (compact, not bloated)           │
│  • 15+ tools for all operations                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────────┐ ┌──────────┐ ┌──────────────────┐
│  CORE SERVICES   │ │  ASYNC   │ │  INTELLIGENCE    │
│                  │ │  WORKERS │ │  ENGINE          │
│  • Contacts      │ │          │ │                  │
│  • Enrichment    │ │ • Enrich │ │ • Relationship   │
│  • Matchmaker    │ │ • Match  │ │   Scoring        │
│  • Outreach      │ │ • Remind │ │ • Decay Tracking │
│  • Search        │ │ • Digest │ │ • Opportunity    │
│  • Import        │ │ • News   │ │   Detection      │
│                  │ │          │ │ • Smart Matching  │
└────────┬─────────┘ └────┬─────┘ └────────┬─────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
│  • Airtable (Contacts, Matches, Drafts, Interactions)           │
│  • SQLite (Analytics, Conversation History, Job Queue)          │
│  • In-Memory Cache (Active sessions, recent contacts)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feature Roadmap

### 🔴 Phase 1: Foundation Fixes (Week 1)
*Make what exists work beautifully*

#### 1.1 Kill CrewAI, Upgrade Agent Brain
- **Remove CrewAI entirely** — it adds latency and complexity for no real benefit
- **Upgrade to GPT-4o** for the main agent (smarter, faster than 4o-mini)
- **Compact the system prompt** — current one is ~4000 tokens of rules. Reduce to ~1500 focused tokens
- **Add conversation memory** — store last 20 messages per user in SQLite, inject into context
- **Result:** 3-5x faster responses, much smarter reasoning

#### 1.2 Fix the Conversation Flow
- **Instant acknowledgment** — Send "typing..." indicator immediately, respond async
- **Smarter intent detection** — Use the agent's function calling instead of a separate Gemini classification step
- **Remove double-processing** — Currently: Gemini classifies intent → then OpenAI agent processes. Just use the agent directly
- **Batch rapid messages** — If user sends 3 messages in 5 seconds, combine before processing

#### 1.3 Airtable Schema Upgrade
Add new fields to Contacts table:
- `relationship_score` (0-100) — How strong is this relationship?
- `last_interaction_date` — When did you last interact?
- `interaction_count` — How many times have you interacted?
- `follow_up_date` — When should you follow up?
- `follow_up_reason` — Why follow up?
- `tags` — Comma-separated tags
- `introduced_by` — Who introduced you?
- `introduced_to` — Who have you introduced them to?
- `warm_intro_available` — Boolean
- `priority` — high/medium/low
- `relationship_stage` — new/building/strong/dormant/lost

#### 1.4 Input Processing Overhaul
- **Parallel processing** — Download + transcribe + parse in parallel, not sequential
- **Better OCR** — Use GPT-4o Vision (not 4V) for business cards — much better extraction
- **Multi-card support** — Handle photos with multiple business cards
- **vCard import** — Parse .vcf files
- **LinkedIn profile URL** — When user pastes a LinkedIn URL, auto-scrape basic info

---

### 🟡 Phase 2: Relationship Intelligence (Week 2)
*This is what makes Rover unique*

#### 2.1 Interaction Tracking
Every time you mention or interact with a contact, Rover logs it:
- Contact added/updated/viewed/enriched
- Note added
- Email sent
- Match created
- Manual log: `/met John at Web Summit` or `/called Sarah about deal`

New commands:
- `/met <name> [context]` — Log that you met/spoke with someone
- `/intro <name1> to <name2>` — Log an introduction you made
- `/interactions <name>` — View interaction history

#### 2.2 Relationship Decay & Health Scores
```
Relationship Score Algorithm:
- Base: 50 (new contact)
- +20 if enriched (you invested time to learn about them)
- +10 per interaction (capped at +40)
- +15 if you've introduced them to someone
- +10 if they've been introduced to you by someone
- -5 per week of no interaction (decay)
- -20 if >3 months dormant
- Minimum: 10 (never fully lost)
```

Rover calculates scores nightly and alerts you:
```
🔔 Relationship Alert:
3 contacts are going cold:
• Sarah Chen (Score: 35↓) — Last contact: 6 weeks ago
• Mike Johnson (Score: 28↓) — Last contact: 2 months ago
• Lisa Park (Score: 22↓) — Last contact: 3 months ago

Reply with a name to get a suggested follow-up message.
```

#### 2.3 Smart Follow-Up Suggestions
When a relationship is decaying, Rover suggests WHY and HOW to reconnect:
```
User: Sarah Chen
Rover: Sarah Chen — CTO at DataFlow (Score: 35↓)

Last interaction: Jan 5 (you met at Web Summit)
She mentioned: interested in AI infrastructure deals

Suggested follow-up:
"Hey Sarah! Hope you've been well since Web Summit. 
Saw DataFlow just raised their Series B — congrats! 
I recently met someone building in AI infra that 
might be interesting for your portfolio. Coffee soon?"

Send this? (yes/edit/skip)
```

#### 2.4 Proactive Daily/Weekly Digest
Rover sends a digest without being asked:

**Daily (morning):**
```
☀️ Good morning Ahmed! Here's your network pulse:

📥 New today: 0 contacts added
🤝 Follow up today: 2 contacts
   • John Smith — promised to send deck (3 days ago)
   • Lisa Park — coffee meeting scheduled
📈 Hot lead: TechCo just raised Series A (you know their CTO)
🔗 New match: Sarah Chen ↔ Mike Fund (Score: 82)
```

**Weekly (Sunday):**
```
📊 Weekly Network Report:
• Contacts added: 5
• Interactions logged: 12
• Introductions made: 2
• Relationships strengthening: 8 ↑
• Relationships cooling: 3 ↓
• Top connection this week: Sarah Chen (5 interactions)
• Suggested focus: Re-engage dormant investors
```

#### 2.5 Network Graph Intelligence
- Track **who knows who** in your network
- Suggest **warm intro paths**: "You → Sarah → Mike → Target Person"
- Detect **clusters**: "You have 8 fintech founders but only 2 fintech investors"
- Find **gaps**: "You have no connections in healthcare — here's why you might want some"

---

### 🟢 Phase 3: Supercharged Features (Week 3)
*10x the existing features*

#### 3.1 Continuous Matchmaker (Not One-Shot)
Current: User runs `/match`, gets results once.
New: Matchmaker runs continuously:
- Every time a new contact is added, check against existing contacts
- Score changes trigger re-matching
- New matches are surfaced proactively
- Match quality improves over time (feedback loop)

```
🔗 New Match Detected!
Ahmed Khan (Founder, Fintech) ↔ Sarah Fund (Investor, Fintech Focus)
Score: 87/100

Key reasons:
• Sector: Both deep in fintech
• Stage: Sarah invests Seed-A, Ahmed is raising Seed
• Geo: Both MENA-based
• Thesis: Sarah's thesis on embedded finance matches Ahmed's product

Want me to draft an intro email? (yes/no)
```

#### 3.2 Smart Enrichment 2.0
Current: Basic web search via Tavily/SerpAPI.
New:
- **Apollo.io / Hunter.io integration** for verified emails
- **Crunchbase API** for funding data
- **News monitoring** — Track when contacts' companies are in the news
- **Social signals** — Twitter/X activity, LinkedIn posts (via RSS)
- **Auto re-enrichment** — Re-enrich contacts every 30 days for fresh data
- **Enrichment confidence scores** — Rate data quality

#### 3.3 Outreach 2.0
Current: Generate email drafts from matches.
New:
- **Multi-channel outreach** — Email, LinkedIn message, WhatsApp, Twitter DM templates
- **Follow-up sequences** — Automated follow-up if no response (1 day, 3 days, 7 days)
- **A/B subject lines** — Generate 2 options, track which performs better
- **Email tracking** — Open rates, click rates (via pixel or link tracking)
- **Template library** — Save and reuse successful email templates
- **Tone matching** — Analyze the contact's communication style and match it

#### 3.4 Natural Language Everything
Remove most slash commands. Just talk naturally:
```
"I just met Sarah at Web Summit, she's CTO at DataFlow, 
here's her card [photo]. She's interested in AI deals. 
Set a reminder to follow up next week."

Rover:
✅ Added Sarah — CTO at DataFlow
📸 Extracted from card: email, phone, LinkedIn
🏷️ Tagged: Web Summit, AI, Investor interest
⏰ Reminder set: Follow up Feb 27
🔍 Enriching in background...
```

#### 3.5 Voice-First Mode
Make Rover work great in voice-only mode:
- User sends voice note → Rover processes → Rover replies with voice note
- Great for logging contacts while walking/driving
- "Hey Rover, I just met John Smith from TechCorp. He's their CEO and he's raising a Series A. Get me his LinkedIn."

---

### 🔵 Phase 4: Platform Features (Week 4+)
*Scale and differentiate*

#### 4.1 Multi-User Support
- User authentication via Telegram user ID (already have this)
- Separate Airtable bases per user OR filtered views
- Team mode: Share contacts within a team, track who knows who

#### 4.2 Web Dashboard
- React/Next.js dashboard for viewing network graph
- Visual relationship map
- Drag-and-drop contact management
- Analytics and reporting
- Settings and configuration

#### 4.3 Calendar Integration
- Google Calendar sync
- Auto-detect meetings with contacts → log interaction
- Pre-meeting briefs: "You're meeting Sarah in 1 hour. Here's what you should know..."
- Post-meeting prompts: "How did your meeting with Sarah go? Any updates?"

#### 4.4 Email Inbox Monitoring
- Connect Gmail/Outlook
- Auto-detect emails from contacts → log interaction
- Surface important emails: "Sarah replied to your intro email!"
- Track email response times

#### 4.5 LinkedIn Integration (Proper)
- LinkedIn API for basic profile data
- Track when contacts change jobs
- Surface mutual connections
- Auto-suggest connections to make

#### 4.6 Mobile App (React Native)
- Quick contact capture (photo, voice, text)
- Push notifications for follow-ups
- Business card scanner with AR
- Location-aware: "You're at Web Summit — here are your contacts attending"

---

## Technical Improvements

### Performance
1. **Async everything** — Use asyncio properly throughout
2. **Response streaming** — Stream agent responses for perceived speed
3. **Background processing** — Enrichment, matching, scoring all run async
4. **Caching** — Redis or in-memory cache for frequent Airtable reads
5. **Connection pooling** — Reuse HTTP connections to APIs

### Reliability
1. **Retry logic** — Exponential backoff on API failures
2. **Queue system** — Use Celery or simple job queue for background tasks
3. **Health checks** — Monitor API quotas, Airtable limits
4. **Graceful degradation** — If enrichment fails, still save contact
5. **Error recovery** — Resume interrupted operations

### Code Quality
1. **Type hints everywhere** — Full mypy compliance
2. **Tests** — Unit tests for services, integration tests for agent
3. **CI/CD** — GitHub Actions for lint, test, deploy
4. **Docker** — Proper multi-stage Dockerfile
5. **Environment management** — Proper .env handling with validation

---

## Implementation Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Kill CrewAI, upgrade agent | 🔥🔥🔥 | Medium | P0 |
| Conversation memory | 🔥🔥🔥 | Low | P0 |
| Compact system prompt | 🔥🔥 | Low | P0 |
| Remove double-processing | 🔥🔥🔥 | Medium | P0 |
| Interaction tracking | 🔥🔥🔥 | Medium | P1 |
| Relationship scoring | 🔥🔥🔥 | Medium | P1 |
| Follow-up reminders | 🔥🔥🔥 | Low | P1 |
| Daily digest | 🔥🔥 | Low | P1 |
| Continuous matchmaker | 🔥🔥 | High | P2 |
| Smart follow-up suggestions | 🔥🔥 | Medium | P2 |
| Enrichment 2.0 | 🔥🔥 | High | P2 |
| Natural language everything | 🔥🔥 | Medium | P2 |
| Web dashboard | 🔥 | Very High | P3 |
| Calendar integration | 🔥🔥 | High | P3 |
| Mobile app | 🔥 | Very High | P4 |

---

## What I'm Building Tonight (Phase 1 Start)

1. ✅ Study entire codebase
2. 🔨 Refactor agent.py — compact prompt, add conversation memory
3. 🔨 Remove the Gemini intent classification layer (conversation_ai.py bypass)
4. 🔨 Add interaction tracking to schema + Airtable
5. 🔨 Add relationship scoring foundation
6. 🔨 Add follow-up reminder system
7. 🔨 Create new tools: log_interaction, set_reminder, get_relationship_health

---

## Success Metrics

How we'll know Rover V3 is world-class:

1. **Response time** < 2 seconds for 90% of interactions
2. **Zero missed follow-ups** — Every relationship gets attention
3. **Match quality** > 80% user approval rate
4. **Daily active usage** — User checks Rover every day
5. **Network growth** — 10+ new contacts per week processed smoothly
6. **Relationship health** — Average score stays above 50
7. **Introductions made** — Rover surfaces 5+ intro opportunities per week

---

*"The best networkers don't have the most contacts. They have the strongest relationships."*

— Rover V3 Philosophy
