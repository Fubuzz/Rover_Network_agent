"""
Training module for the Networking Assistant Agent.

This module provides:
- Training data (100 examples) for CrewAI training
- System instructions for context preservation
- Training script for running training sessions
"""

from pathlib import Path

TRAINING_DIR = Path(__file__).parent
TRAINING_DATA_PATH = TRAINING_DIR / "training_data.jsonl"
SYSTEM_INSTRUCTIONS_PATH = TRAINING_DIR / "system_instructions.json"


def get_training_data_path() -> Path:
    """Return the path to the training data file."""
    return TRAINING_DATA_PATH


def get_system_instructions_path() -> Path:
    """Return the path to the system instructions file."""
    return SYSTEM_INSTRUCTIONS_PATH
