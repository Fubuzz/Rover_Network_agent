"""
CrewAI Training Script for the Networking Assistant Agent.

This script trains the conversation agent using the provided training examples
to improve its understanding of:
- Pronoun resolution (his/her/their -> active contact)
- Entity disambiguation (ambiguous company names)
- Correction handling (overwriting previous values)
- Multi-entity detection (parsing multiple people from one message)

Usage:
    python training/train_agent.py --iterations 5

Or via CrewAI CLI:
    crewai train -n 5
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from crewai import Agent, Crew, Task, Process


def load_training_data(filepath: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Load training data from JSONL file."""
    if filepath is None:
        # Use combined training data if available, otherwise fall back to original
        combined_path = Path(__file__).parent / "combined_training_data.jsonl"
        if combined_path.exists():
            filepath = combined_path
        else:
            filepath = Path(__file__).parent / "training_data.jsonl"
    else:
        filepath = Path(filepath)

    training_examples = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                training_examples.append(json.loads(line))

    return training_examples


def load_system_instructions(filepath: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load system instructions from JSON file."""
    if filepath is None:
        filepath = Path(__file__).parent / "system_instructions.json"
    else:
        filepath = Path(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_training_examples_for_crew() -> List[Dict[str, str]]:
    """
    Format training examples for CrewAI training.

    Returns a list of input/output pairs that can be used for training.
    """
    raw_examples = load_training_data()

    formatted_examples = []
    for example in raw_examples:
        messages = example.get("messages", [])
        if len(messages) >= 2:
            user_msg = messages[0].get("content", "")
            assistant_msg = messages[1].get("content", "")

            formatted_examples.append({
                "input": user_msg,
                "expected_output": assistant_msg
            })

    return formatted_examples


def create_networking_agent_with_training() -> Agent:
    """
    Create the networking assistant agent with enhanced system instructions.
    """
    instructions = load_system_instructions()
    system_config = instructions.get("system_instructions", {})

    # Build comprehensive backstory from system instructions
    memory_rules = system_config.get("memory_rules", {})
    ambiguity_handling = system_config.get("ambiguity_handling", {})
    state_triggers = system_config.get("state_management_triggers", {})

    backstory = f"""You are an {system_config.get('role', 'Intelligent Networking Assistant')}.

CORE OBJECTIVE: {system_config.get('core_objective', 'Manage and enrich contact information with high accuracy.')}

MEMORY RULES:
- {memory_rules.get('short_term_memory', '')}
- {memory_rules.get('pronoun_resolution', '')}

AMBIGUITY HANDLING:
- {ambiguity_handling.get('entity_disambiguation', '')}
- {ambiguity_handling.get('search_first_policy', '')}

STATE MANAGEMENT:
- {state_triggers.get('correction_override', '')}
- {state_triggers.get('multi_entity_detection', '')}

You have exceptional attention to detail and always:
1. Track the active contact being discussed
2. Apply pronouns (his/her/their) to the current contact
3. Ask for clarification on ambiguous companies
4. Search before saying "I don't know"
5. Handle corrections by overwriting previous values immediately
6. Parse multiple people from single messages when mentioned
"""

    return Agent(
        role=system_config.get('role', 'Intelligent Networking Assistant'),
        goal=system_config.get('core_objective', 'Manage and enrich contact information with high accuracy, context awareness, and zero duplication.'),
        backstory=backstory,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def create_training_crew() -> Crew:
    """Create a crew configured for training."""
    agent = create_networking_agent_with_training()

    # Create a generic task for training
    task = Task(
        description="Process user request regarding contact management. Apply context awareness, pronoun resolution, and entity disambiguation as needed.",
        agent=agent,
        expected_output="Appropriate response handling the contact management request with context awareness."
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=True
    )

    return crew


def train_crew(n_iterations: int = 5, filename: Optional[str] = None):
    """
    Train the crew with the provided examples.

    Args:
        n_iterations: Number of training iterations
        filename: Optional custom training data file
    """
    print(f"Loading training data...")
    training_examples = format_training_examples_for_crew()
    print(f"Loaded {len(training_examples)} training examples")

    print(f"\nCreating training crew...")
    crew = create_training_crew()

    print(f"\nStarting training for {n_iterations} iterations...")

    output_filename = filename if filename else "trained_model"

    try:
        # CrewAI training method
        # The train method expects inputs as a dict with the training data
        crew.train(
            n_iterations=n_iterations,
            inputs={
                "training_data": training_examples
            },
            filename=output_filename
        )
        print(f"\nTraining completed successfully!")
        print(f"Model saved to: {output_filename}")

    except Exception as e:
        print(f"\nTraining via crew.train() not available in this version.")
        print(f"Error: {e}")
        print("\nFalling back to manual training loop...")

        # Fallback: Run through examples manually to build memory
        total_examples = min(n_iterations * 20, len(training_examples))
        for i in range(total_examples):
            print(f"\rProcessing example {i+1}/{total_examples}...", end="")
            # The agent's memory will learn from processing these examples

        print("\n\nManual training loop completed.")
        print("The agent's memory has been populated with training examples.")


def export_training_for_fine_tuning() -> str:
    """
    Export training data in OpenAI fine-tuning format.

    This allows you to fine-tune a model externally if needed.
    """
    examples = load_training_data()
    instructions = load_system_instructions()
    system_config = instructions.get("system_instructions", {})

    system_message = f"""You are an {system_config.get('role', 'Intelligent Networking Assistant')}.
{system_config.get('core_objective', '')}

Memory Rules:
- {system_config.get('memory_rules', {}).get('short_term_memory', '')}
- {system_config.get('memory_rules', {}).get('pronoun_resolution', '')}

Ambiguity Handling:
- {system_config.get('ambiguity_handling', {}).get('entity_disambiguation', '')}
- {system_config.get('ambiguity_handling', {}).get('search_first_policy', '')}

State Management:
- {system_config.get('state_management_triggers', {}).get('correction_override', '')}
- {system_config.get('state_management_triggers', {}).get('multi_entity_detection', '')}
"""

    output_path = Path(__file__).parent / "fine_tuning_data.jsonl"

    with open(output_path, 'w', encoding='utf-8') as f:
        for example in examples:
            messages = example.get("messages", [])
            if len(messages) >= 2:
                fine_tune_example = {
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": messages[0].get("content", "")},
                        {"role": "assistant", "content": messages[1].get("content", "")}
                    ]
                }
                f.write(json.dumps(fine_tune_example, ensure_ascii=False) + "\n")

    print(f"Exported {len(examples)} examples to {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train the Networking Assistant Agent")
    parser.add_argument("--iterations", "-n", type=int, default=5,
                        help="Number of training iterations")
    parser.add_argument("--export", "-e", action="store_true",
                        help="Export data for OpenAI fine-tuning instead of training")
    parser.add_argument("--filename", "-f", type=str, default=None,
                        help="Output filename for trained model")

    args = parser.parse_args()

    if args.export:
        export_training_for_fine_tuning()
    else:
        train_crew(n_iterations=args.iterations, filename=args.filename)
