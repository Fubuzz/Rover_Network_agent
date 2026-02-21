"""
Rover Agent - AI Agent with OpenAI Function Calling.
This agent reasons about user requests and calls tools to fulfill them.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from openai import OpenAI

from config import APIConfig
from services.contact_memory import get_memory_service, ConversationState
from services.agent_tools import (
    AgentTools, _user_search_results, _user_summaries,
    _user_last_contact, _user_last_action, _user_search_query,
    _user_last_mentioned_person
)


logger = logging.getLogger('network_agent')


# Tool definitions for OpenAI function calling
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_contact",
            "description": "Add a new contact to the network and start editing them. Use this when user wants to add someone new.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name of the contact (required)"},
                    "title": {"type": "string", "description": "Job title (e.g., 'CEO', 'Software Engineer')"},
                    "company": {"type": "string", "description": "Company or organization name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "linkedin": {"type": "string", "description": "LinkedIn profile URL"},
                    "contact_type": {
                        "type": "string",
                        "enum": ["founder", "investor", "enabler", "professional"],
                        "description": "Type of contact: founder, investor, enabler, or professional"
                    },
                    "company_description": {"type": "string", "description": "Description of the company"},
                    "location": {"type": "string", "description": "Location (city, country)"},
                    "notes": {"type": "string", "description": "Additional notes"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_contact",
            "description": "Update fields for the current contact being edited. Use this to add/modify information about the contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Job title"},
                    "company": {"type": "string", "description": "Company name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "linkedin": {"type": "string", "description": "LinkedIn URL"},
                    "contact_type": {
                        "type": "string",
                        "enum": ["founder", "investor", "enabler", "professional"],
                        "description": "Type: founder, investor, enabler, or professional"
                    },
                    "company_description": {"type": "string", "description": "Company description/info"},
                    "location": {"type": "string", "description": "Location"},
                    "notes": {"type": "string", "description": "Additional notes"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_contact",
            "description": "Save the current contact to the database. Use when user says 'done', 'save', 'finish', etc.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information about a company or person. Use when user asks to search, research, or find info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for (company name, person name, etc.)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_search_results",
            "description": "Create a summary of the most recent search results. Use when user asks for a summary of what was found.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contact",
            "description": "Get details about a contact by name. Use when user asks to see, show, or view a contact's info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the contact to look up"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_current",
            "description": "Cancel the current contact without saving. Use when user says 'cancel', 'discard', 'nevermind'.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_existing_contact",
            "description": "Update an existing/saved contact in the database by name. Use this when user wants to update a contact that was already saved (not currently being edited). Requires the contact name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the existing contact to update (required)"},
                    "title": {"type": "string", "description": "Job title"},
                    "company": {"type": "string", "description": "Company name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "linkedin": {"type": "string", "description": "LinkedIn URL"},
                    "contact_type": {
                        "type": "string",
                        "enum": ["founder", "investor", "enabler", "professional"],
                        "description": "Type: founder, investor, enabler, or professional"
                    },
                    "company_description": {"type": "string", "description": "Company description"},
                    "location": {"type": "string", "description": "Location"},
                    "notes": {"type": "string", "description": "Additional notes"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_contacts",
            "description": "List all contacts in the database. Use when user asks to see all contacts, show their network, or list everyone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of contacts to show (default 10)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_search_links",
            "description": "Get the links/URLs from the most recent search results. Use when user asks for links, URLs, or sources from a previous search.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enrich_contact",
            "description": "ENRICHMENT TOOL: Research and enrich a contact with LinkedIn, company info, industry, etc. Use when user says 'enrich', 'research him', 'find more info', 'look him up'. This tool AUTO-APPLIES the found data to the contact - do NOT display raw JSON, just confirm what was applied.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the contact to enrich (optional - uses current contact if not specified)"}
                }
            }
        }
    },
    # V3 New Tools - Relationship Intelligence
    {
        "type": "function",
        "function": {
            "name": "log_interaction",
            "description": "Log an interaction with a contact (met, called, emailed, introduced, messaged). Updates last_interaction_date and interaction_count in database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact name"},
                    "interaction_type": {
                        "type": "string",
                        "enum": ["met", "called", "emailed", "introduced", "messaged"],
                        "description": "Type of interaction"
                    },
                    "context": {"type": "string", "description": "Optional context about the interaction"}
                },
                "required": ["name", "interaction_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_follow_up",
            "description": "Set a follow-up reminder for a contact. Stores follow_up_date and follow_up_reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact name"},
                    "date": {"type": "string", "description": "Follow-up date in YYYY-MM-DD format"},
                    "reason": {"type": "string", "description": "Optional reason for follow-up"}
                },
                "required": ["name", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_follow_ups",
            "description": "Get all pending follow-ups sorted by date. Use when user asks 'who should I follow up with?'",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_relationship_health",
            "description": "Calculate and return relationship score (0-100) for a contact based on interaction frequency, enrichment, and decay. Use when user asks 'how's my relationship with X?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact name (optional - uses current contact if not specified)"}
                }
            }
        }
    },
    # V3 Phase 2 Tools - Introductions, Digest, Search
    {
        "type": "function",
        "function": {
            "name": "create_introduction",
            "description": "Create an introduction between two contacts. Logs it in the Introductions table and drafts an intro message. Use when user says 'introduce X to Y' or 'connect X with Y'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connector": {"type": "string", "description": "Person who can make/facilitate the intro"},
                    "target": {"type": "string", "description": "Person to be introduced"},
                    "reason": {"type": "string", "description": "Why this intro makes sense"}
                },
                "required": ["connector", "target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_introductions",
            "description": "Get all introductions, optionally filtered by status. Use when user asks 'show my introductions' or 'pending intros'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["suggested", "requested", "made", "declined"],
                        "description": "Filter by status (optional)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_introductions",
            "description": "Suggest potential introductions based on your network (industry overlap, founder-investor matches, etc). Use when user asks 'who should I introduce?' or 'suggest intros'.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_digest",
            "description": "Get your daily network briefing: follow-ups, decaying relationships, stats, suggested actions. Use when user says 'briefing', 'digest', 'morning update', 'what's happening with my network?'.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_report",
            "description": "Get a weekly network activity report with interaction counts, top relationships, and stats. Use when user asks for 'weekly report' or 'weekly summary'.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_contacts",
            "description": "Search contacts with natural language. Examples: 'who do I know at Google?', 'show me all founders', 'investors in fintech', 'people I met this month'. Use for any query about the user's network.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query about your contacts"}
                },
                "required": ["query"]
            }
        }
    },
    # V3 Phase 3 Tools
    {
        "type": "function",
        "function": {
            "name": "process_business_card",
            "description": "Extract contact info from a business card photo using OCR/Vision AI. Creates and saves the contact automatically. Use when user sends a business card image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to the business card image file"}
                },
                "required": ["image_path"]
            }
        }
    }
]


def build_system_prompt(user_id: str) -> str:
    """Build the system prompt with current context and conversation memory."""
    from services.conversation_store import get_conversation_store
    
    memory = get_memory_service()
    conversation_store = get_conversation_store()
    
    pending = memory.get_pending_contact(user_id)
    state = memory.get_state(user_id)

    # Build current contact context
    current_contact_str = "None"
    if pending:
        parts = [pending.name]
        if pending.title:
            parts.append(f"{pending.title}")
        if pending.company:
            parts.append(f"at {pending.company}")
        current_contact_str = " ".join(parts)

    # Get recent conversation context (last 10 messages for compact prompt)
    recent_context = conversation_store.format_recent_context(user_id, limit=10)

    # Check for search results
    search_results = _user_search_results.get(user_id, [])
    has_search = "Yes" if search_results else "No"
    last_contact = _user_last_contact.get(user_id, "None")
    last_action = _user_last_action.get(user_id, "None")

    return f"""You are Rover 🐕 — a sharp, witty network nurturing AI with serious swagger. Think of yourself as the user's networking wingman who actually remembers everyone and never drops the ball. You're part CRM, part relationship coach, part hype man.

**CURRENT SESSION:**
- Contact being edited: {current_contact_str}
- Last contact mentioned: {last_contact}
- Last action: {last_action}
- State: {state.value}
- Search results available: {has_search}

**RECENT CONVERSATION:**
{recent_context}

**AVAILABLE TOOLS:**
Contact Management: add_contact, update_contact, update_existing_contact, save_contact, get_contact, list_contacts, cancel_current
Research: search_web, enrich_contact, summarize_search_results, get_search_links
Relationships: log_interaction, set_follow_up, get_follow_ups, get_relationship_health
Introductions: create_introduction, get_introductions, suggest_introductions
Intelligence: get_daily_digest, get_weekly_report, search_contacts

**KEY RULES:**
1. When editing a contact, use update_contact. When updating a saved contact, use update_existing_contact(name=...)
2. "Done"/"Save"/"Finish" → call save_contact immediately
3. Enrichment AUTO-APPLIES data - just confirm what was found
4. Extract clean values: "He's the CEO" → title="CEO" (not "He's the CEO")
5. Person vs Company: "John is CEO at Apple" → name="John", title="CEO", company="Apple" (NOT name="Apple"!)
6. After save_contact(), the contact is LOCKED - new attributes belong to NEW contacts only

**RELATIONSHIP TRACKING:**
- When user says "I met X" or "I called X" → use log_interaction
- "Remind me to follow up with X" → use set_follow_up
- "Who should I follow up with?" → use get_follow_ups
- "How's my relationship with X?" → use get_relationship_health

**INTRODUCTIONS:**
- "Introduce X to Y" → use create_introduction
- "Show my introductions" → use get_introductions
- "Suggest intros" → use suggest_introductions

**INTELLIGENCE:**
- "Briefing" / "morning update" / "what's happening?" → use get_daily_digest
- "Weekly report" → use get_weekly_report
- "Who do I know at X?" / "show me founders" / any search → use search_contacts
- IMPORTANT: Today's date is {datetime.now().strftime('%Y-%m-%d')}. Always use the correct year (2026).

**PERSONALITY & VOICE:**
You're confident, fun, and sharp. Like a cool friend who's really good at networking.

Vibes:
- SHORT responses. 1-2 sentences max unless the user asks for details
- Use slang naturally: "Got it", "On it", "Locked in", "Say less"
- Celebrate big contacts: "Oh we're talking C-suite now 🔥", "That's a power move"
- Playful roasts when appropriate: "Your network's looking a bit lonely" or "When's the last time you actually followed up with anyone? 👀"
- Use emojis sparingly but with style (1-2 per message max)
- Never say "I have successfully..." or "I've completed..." — just say what happened
- Never be robotic or corporate. No "Would you like to provide additional details?" — instead: "Anything else on them?"
- When saving: "Locked in ✅" or "Done, they're in the vault" — not "Contact saved successfully"
- When enriching: "Let me dig up some intel..." not "I will now research..."
- After tool calls, be natural — don't repeat back everything the tool returned verbatim. Summarize with personality.
- If user sends something ambiguous, make your best guess and go — don't ask 5 clarifying questions

Examples of good Rover responses:
- "Boom, Sarah's in your network now. Want me to dig up more on her?" 
- "Coffee with Hesham, noted ☕ Following up Feb 26 about the partnership."
- "3 follow-ups this week. Hesham's overdue — might want to hit him up."
- "Found 4 founders in your network. Ahmed Hammouda's your strongest connection there."

Examples of BAD responses (never do this):
- "I have successfully saved the contact Sarah to your network database."
- "Would you like me to set a follow-up reminder? If so, please provide the date."
- "I've updated Hesham Ashour's email and phone number, but it seems I couldn't save the contact. Would you like to try saving again or check the details?"

Be the friend everyone wishes managed their contacts."""


class RoverAgent:
    """
    AI Agent that can reason and call tools to fulfill user requests.
    Uses OpenAI's function calling for intelligent tool selection.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tools = AgentTools(user_id)
        self.messages: List[Dict[str, Any]] = []
        self.max_iterations = 5  # Prevent infinite loops
        self._client = None

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client."""
        if not self._client:
            if not APIConfig.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            self._client = OpenAI(api_key=APIConfig.OPENAI_API_KEY)
        return self._client

    async def process(self, user_message: str) -> str:
        """
        Main agent loop - reason and act until the task is complete.

        Args:
            user_message: The user's message to process

        Returns:
            The agent's final response to the user
        """
        from services.conversation_store import get_conversation_store
        
        logger.info(f"[AGENT] Processing: '{user_message}'")
        
        # Store user message in conversation history
        conversation_store = get_conversation_store()
        conversation_store.add_message(self.user_id, "user", user_message)

        # Initialize messages with system prompt and user message
        system_prompt = build_system_prompt(self.user_id)
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Agent loop - reason and act
        for iteration in range(self.max_iterations):
            logger.info(f"[AGENT] Iteration {iteration + 1}")

            try:
                response = self._call_llm()
            except Exception as e:
                logger.error(f"[AGENT] LLM call error: {e}")
                return f"Sorry, I had trouble processing that. Please try again."

            message = response.choices[0].message

            # If no tool calls, we're done - return the response
            if not message.tool_calls:
                final_response = message.content or "Done!"
                logger.info(f"[AGENT] Final response: {final_response[:100]}...")
                
                # Store assistant response in conversation history
                conversation_store.add_message(self.user_id, "assistant", final_response)
                
                return final_response

            # Add assistant message with tool calls to history
            self.messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(f"[AGENT] Tool call: {tool_name}({arguments})")

                # Execute the tool
                result = await self.tools.execute(tool_name, arguments)

                logger.info(f"[AGENT] Tool result: {result[:100]}...")

                # Add tool result to messages
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

        # Max iterations reached
        logger.warning("[AGENT] Max iterations reached")
        final_response = "I've completed the task. Let me know if you need anything else!"
        
        # Store assistant response in conversation history
        conversation_store.add_message(self.user_id, "assistant", final_response)
        
        return final_response

    def _call_llm(self):
        """Call the OpenAI API with function calling."""
        client = self._get_client()

        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1000
        )


async def process_with_agent(user_id: str, message: str) -> str:
    """
    Process a message using the Rover Agent.
    This is the main entry point for the new agentic architecture.
    """
    agent = RoverAgent(user_id)
    return await agent.process(message)
