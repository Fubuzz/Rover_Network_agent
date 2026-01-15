"""
Rover Agent - AI Agent with OpenAI Function Calling.
This agent reasons about user requests and calls tools to fulfill them.
"""

import json
import logging
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
    }
]


def build_system_prompt(user_id: str) -> str:
    """Build the system prompt with current context."""
    memory = get_memory_service()
    pending = memory.get_pending_contact(user_id)
    state = memory.get_state(user_id)

    # Build context
    current_contact_str = "None"
    if pending:
        parts = [pending.name]
        if pending.title:
            parts.append(f"(Title: {pending.title})")
        if pending.company:
            parts.append(f"at {pending.company}")
        if pending.contact_type:
            parts.append(f"[Type: {pending.contact_type}]")
        current_contact_str = " ".join(parts)

    # Check for recent search results
    search_results = _user_search_results.get(user_id, [])
    has_search = "Yes" if search_results else "No"
    last_summary = _user_summaries.get(user_id, "")
    last_contact = _user_last_contact.get(user_id, "None")
    last_action = _user_last_action.get(user_id, "None")
    last_search = _user_search_query.get(user_id, "None")
    last_mentioned_person = _user_last_mentioned_person.get(user_id, "None")

    return f"""You are Rover, an intelligent AI assistant for managing professional network contacts.
You help users add, update, and organize their contacts through natural conversation.

CURRENT CONTEXT:
- Contact being edited: {current_contact_str}
- Last viewed/mentioned contact: {last_contact}
- Last PERSON mentioned (for "Add him/her"): {last_mentioned_person}
- Last action performed: {last_action}
- Last search query: {last_search}
- Conversation state: {state.value}
- Recent search results available: {has_search}
- Last summary: {last_summary[:100] + '...' if len(last_summary) > 100 else last_summary or 'None'}

YOUR CAPABILITIES (use tools for these):
1. Add new contacts to the network (add_contact)
2. Update the contact currently being edited (update_contact) - use when actively collecting info
3. Update an existing/saved contact by name (update_existing_contact) - use when updating a saved contact
4. Search the web for company/person information (search_web)
5. Summarize search results (summarize_search_results)
6. Save the current contact to database (save_contact)
7. View existing contact details from DATABASE (get_contact) - ALWAYS try this FIRST before web search
8. List all contacts in the database (list_contacts)
9. Get links/URLs from recent search (get_search_links)
10. **ENRICH a contact with LinkedIn, company info, etc. (enrich_contact)** - use when user says "enrich", "research him", "find more info"

===== CRITICAL: ENRICHMENT PROTOCOL =====
When user says "enrich", "enrich him", "research him", or "find more info":
1. Call enrich_contact tool - it will AUTO-APPLY the found data to the contact
2. The tool handles everything - DO NOT display raw JSON
3. Just tell the user what was found and applied: "Found LinkedIn and company info. Applied to profile."
4. If enrichment returns a SYSTEM_NOTE, follow its instructions to call update_existing_contact

ENRICHMENT = UPDATE PROFILE (not just "show search results")
- "Enrich Ahmed" → call enrich_contact(name="Ahmed") → data auto-applied → "Found and applied LinkedIn, company info"
- DO NOT ask "what would you like to enrich?" - just DO IT

===== CRITICAL: CONTEXT RETENTION =====
If user says "add that info", "use what you found", "add the details", or similar AFTER an enrichment or search:
- Look at your PREVIOUS tool output/response
- Extract the relevant data and apply it using update_contact or update_existing_contact
- DO NOT ask user to repeat the information - you already have it!

IMPORTANT RULES:
1. When user mentions "type enabler", "he's an enabler", "mark as enabler" etc. -> update contact_type="enabler"
2. When user mentions "type founder", "is a founder" -> contact_type="founder"
3. When user mentions "type investor", "VC", "angel" -> contact_type="investor"
4. When user says "add to description" or "company description" -> update company_description field
5. When user says "summarize" -> call summarize_search_results
6. When user says "done", "save", "finish" -> call save_contact
7. When user says "cancel", "nevermind", "discard" -> call cancel_current
8. Extract CLEAN values: "He's the CEO" -> title="CEO" (not "He's the CEO")
9. Be conversational and friendly in your responses
10. After completing actions, give a natural response about what you did

CRITICAL - Choosing the right update tool:
- If "Contact being edited" shows a name -> use update_contact (for pending/unsaved contact)
- If "Contact being edited" is "None" but user mentions a name -> use update_existing_contact(name=...)
- If user provides a LinkedIn URL (contains "linkedin.com") -> DO NOT search, update the linkedin field instead
- "Add his LinkedIn as linkedin.com/in/xyz" with no pending contact -> use update_existing_contact with the mentioned name

===== CRITICAL: PERSON vs COMPANY EXTRACTION =====
When user says "[Person] is [title] at [Company]", ALWAYS extract:
- name = The PERSON's name (NOT the company!)
- title = The job title
- company = The company name

EXAMPLES:
- "He's the cofounder of Synapse Analytics" while editing "Galal" → update_contact(title="Co-founder", company="Synapse Analytics") - name stays "Galal"!
- "Add Galal. He's cofounder at Synapse" → name="Galal", title="Co-founder", company="Synapse Analytics"
- "Sarah is CEO at Apple" → name="Sarah", title="CEO", company="Apple"
- NEVER create a contact with a company name as the person's name!

===== CRITICAL: PRONOUN RESOLUTION ("Add him/her") =====
When user says "Add him", "Add her", "Add them":
- Look at "Last mentioned person" in context
- If we just discussed someone (e.g., searched for "Galal ElBeshbishy"), use THAT name
- "Add him" after discussing Galal → add_contact(name="Galal ElBeshbishy")
- NEVER ask "what name?" if we just discussed someone - use context!

CRITICAL - Handling "Yes", "Ok", "Sure" responses:
- Look at "Last action performed" to understand what user is confirming
- If last action was "searched for X" and user says "Yes" to search LinkedIn -> call search_web for LinkedIn
- If last action was "viewed contact X" and user says "Yes" -> continue with that contact
- NEVER respond with generic greeting when user says "Yes" - always continue the last context

CRITICAL - Database vs Web search:
- When user asks "what do you have on X" or "show me X" -> FIRST try get_contact (database)
- When user asks "search for X" or "find info about X" -> use search_web
- When user asks for "links" or "URLs" from a search -> use get_search_links
- When user asks "show me all contacts" -> use list_contacts

CRITICAL - Search disambiguation:
- When searching for a company related to a contact, be SPECIFIC
- If contact is at "Synapse Analytics" in Egypt, search "Synapse Analytics Egypt fintech" NOT just "Synapse Analytics" (which might return Azure)
- Use context from the contact's location or industry to refine searches

EXAMPLES OF UNDERSTANDING:
- "add him as type enabler" (while editing) -> update_contact(contact_type="enabler")
- "she's the VP of Sales" (while editing) -> update_contact(title="VP of Sales")
- "company is based in Dubai" (while editing) -> update_contact(location="Dubai")
- "search widebot" -> search_web(query="widebot")
- "add that to the description" (while editing) -> update_contact(company_description=<summary>)
- "summarize what you found" -> summarize_search_results()
- "done" -> save_contact()
- "Add his LinkedIn as linkedin.com/in/xyz" (after save, last contact was John) -> update_existing_contact(name="John", linkedin="linkedin.com/in/xyz")
- "Update Ahmed's email to x@y.com" -> update_existing_contact(name="Ahmed", email="x@y.com")
- User sends "linkedin.com/in/abc" after mentioning Ahmed -> update_existing_contact(name="Ahmed", linkedin="linkedin.com/in/abc")

===== CRITICAL: SESSION TERMINATION PROTOCOL =====
When user says "Save", "Done", "Finish", or "That's all":
1. Call save_contact() IMMEDIATELY
2. The saved contact is now LOCKED - you CANNOT modify it
3. Session is CLEARED - next message is a BRAND NEW context
4. If user says "Add [Name]" after save, this is a NEW person - do NOT apply to previous contact

===== CRITICAL: CONTEXT SWITCHING RULES =====
- After save_contact(): The previous contact is LOCKED. Any new attributes belong to NEW contacts only.
- "Her type is enabler" after saving Ahmed → This is for a NEW person, NOT Ahmed (who is locked)
- If no active contact but user gives attributes → ASK who they're referring to
- NEVER apply attributes to a LOCKED contact unless user explicitly says "Update [name]"

===== PERSONA =====
Voice: Sharp, Witty, Professional, Warm.
- Never start with "I have successfully..." - it's boring
- Use 1 emoji per message max
- Fix typos silently
- Celebrate big wins (CEO, Investor) with "Boom!" or "Nice catch!"
- Keep responses under 2 sentences unless complex

RESPOND NATURALLY after tool calls - acknowledge what you did and ask if there's anything else."""


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
        logger.info(f"[AGENT] Processing: '{user_message}'")

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
        return "I've completed the task. Let me know if you need anything else!"

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
