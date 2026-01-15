#!/usr/bin/env python3
"""
Test script for the conversation AI with new system instructions.
Tests pronoun resolution, entity disambiguation, correction handling, etc.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from services.conversation_ai import analyze_message, Intent
from data.schema import Contact


async def test_conversation():
    """Test the conversation AI with various scenarios."""

    print("=" * 60)
    print("TESTING CONVERSATION AI WITH NEW SYSTEM INSTRUCTIONS")
    print("=" * 60)

    # Test 1: Basic contact addition
    print("\n--- Test 1: Basic Contact Addition ---")
    result = await analyze_message(
        "Add Mohamed Abaza as the head of growth at synapse analytics"
    )
    print(f"Input: Add Mohamed Abaza as the head of growth at synapse analytics")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")

    # Test 2: Pronoun resolution (his/her)
    print("\n--- Test 2: Pronoun Resolution ---")
    current_contact = Contact(
        full_name="Ahmed Abbas",
        title="CRO",
        company="SAIB"
    )
    result = await analyze_message(
        "Add his email as aabbas@saib.com",
        current_contact=current_contact
    )
    print(f"Input: Add his email as aabbas@saib.com")
    print(f"Current Contact: {current_contact.name}")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")

    # Test 3: Correction override
    print("\n--- Test 3: Correction Override ---")
    current_contact = Contact(
        full_name="Ziad",
        phone="0111"
    )
    result = await analyze_message(
        "Sorry phone is 0112",
        current_contact=current_contact
    )
    print(f"Input: Sorry phone is 0112")
    print(f"Current Contact: {current_contact.name}")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")
    print(f"Action Request: {result.action_request}")

    # Test 4: Contact type extraction
    print("\n--- Test 4: Contact Type Extraction ---")
    current_contact = Contact(
        full_name="Khaled",
        company="Algebra Ventures"
    )
    result = await analyze_message(
        "Yes, he is a Partner",
        current_contact=current_contact
    )
    print(f"Input: Yes, he is a Partner")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")

    # Test 5: Title correction
    print("\n--- Test 5: Title Correction ---")
    current_contact = Contact(
        full_name="Hoda",
        title="Founder",
        company="Breadfast"
    )
    result = await analyze_message(
        "Wait, she is not the founder, she is Head of People",
        current_contact=current_contact
    )
    print(f"Input: Wait, she is not the founder, she is Head of People")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")

    # Test 6: Search request
    print("\n--- Test 6: Search Request ---")
    current_contact = Contact(
        full_name="Farook Hassan",
        title="CEO",
        company="Fimple"
    )
    result = await analyze_message(
        "go ahead",
        current_contact=current_contact
    )
    print(f"Input: go ahead")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")

    # Test 7: Adding investor type
    print("\n--- Test 7: Investor Type ---")
    result = await analyze_message(
        "Add Sarah from Apex Ventures. They write $500k checks."
    )
    print(f"Input: Add Sarah from Apex Ventures. They write $500k checks.")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")

    # Test 8: Enabler type
    print("\n--- Test 8: Enabler Type ---")
    current_contact = Contact(
        full_name="Ibz",
        company="WideBot"
    )
    result = await analyze_message(
        "add him as type enabler",
        current_contact=current_contact
    )
    print(f"Input: add him as type enabler")
    print(f"Intent: {result.intent}")
    print(f"Target: {result.target_contact}")
    print(f"Entities: {result.entities}")

    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_conversation())
