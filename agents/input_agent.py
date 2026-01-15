"""
Input Processing Agent for handling various input types.
"""

from crewai import Agent
from typing import List

from tools.transcription_tool import (
    TranscribeFileTool,
    ParseVoiceTranscriptTool,
    ExtractFromImageTool
)
from tools.ai_tool import AIParseContactTool
from tools.validation_tool import ValidationContactTool


def create_input_agent() -> Agent:
    """Create the Input Processing Agent."""
    
    tools = [
        TranscribeFileTool(),
        ParseVoiceTranscriptTool(),
        ExtractFromImageTool(),
        AIParseContactTool(),
        ValidationContactTool()
    ]
    
    return Agent(
        role="Data Extraction Specialist",
        goal="Extract structured contact information from various input formats including text, voice messages, images, and bulk imports.",
        backstory="""You are an expert in data extraction and parsing with extensive experience handling diverse input formats.
You can transcribe voice messages, read business cards through OCR, parse natural language descriptions, and process bulk data imports.
You are meticulous about extracting every piece of relevant information and structuring it properly for storage.
You understand various formats people use to describe contacts and can intelligently parse even informal descriptions.""",
        tools=tools,
        verbose=True,
        allow_delegation=False,
        memory=True
    )


def get_input_agent_tools() -> List:
    """Get the list of tools for the input agent."""
    return [
        TranscribeFileTool(),
        ParseVoiceTranscriptTool(),
        ExtractFromImageTool(),
        AIParseContactTool(),
        ValidationContactTool()
    ]
