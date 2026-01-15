"""
CrewAI tool for voice transcription.
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

from services.transcription import get_transcription_service
from services.ai_service import get_ai_service


class TranscribeFileInput(BaseModel):
    """Input schema for transcribing a file."""
    file_path: str = Field(..., description="Path to the audio file to transcribe")


class TranscribeTelegramInput(BaseModel):
    """Input schema for transcribing Telegram voice."""
    file_id: str = Field(..., description="Telegram file ID of the voice message")


class ParseVoiceInput(BaseModel):
    """Input schema for parsing voice transcript."""
    transcript: str = Field(..., description="Voice transcript text to parse for contact info")


class TranscribeFileTool(BaseTool):
    """Tool for transcribing audio files."""
    
    name: str = "transcribe_audio_file"
    description: str = """Transcribe an audio file to text using OpenAI Whisper.
    Supports common audio formats like MP3, WAV, OGG."""
    args_schema: Type[BaseModel] = TranscribeFileInput
    
    def _run(self, file_path: str) -> str:
        """Transcribe an audio file."""
        try:
            transcription = get_transcription_service()
            text = transcription.transcribe_audio_file(file_path)
            
            if text:
                return f"**Transcription:**\n\n{text}"
            else:
                return "Could not transcribe the audio file."
                
        except Exception as e:
            return f"Error transcribing audio: {str(e)}"


class ParseVoiceTranscriptTool(BaseTool):
    """Tool for parsing contact info from voice transcripts."""
    
    name: str = "parse_voice_transcript"
    description: str = """Parse a voice transcript to extract contact information.
    Handles common speech patterns and extracts structured data."""
    args_schema: Type[BaseModel] = ParseVoiceInput
    
    def _run(self, transcript: str) -> str:
        """Parse contact info from voice transcript."""
        try:
            from utils.parsers import parse_contact_from_voice
            
            result = parse_contact_from_voice(transcript)
            
            if not result or not any(result.values()):
                # Try AI parsing
                ai_service = get_ai_service()
                result = ai_service.parse_contact_info(transcript)
            
            if not result:
                return "Could not extract contact information from the transcript."
            
            lines = ["**Extracted from Voice:**", ""]
            
            field_names = {
                "name": "Name",
                "job_title": "Job Title",
                "company": "Company",
                "phone": "Phone",
                "email": "Email",
                "linkedin_url": "LinkedIn",
                "location": "Location"
            }
            
            found_any = False
            for field, label in field_names.items():
                value = result.get(field)
                if value:
                    lines.append(f"**{label}:** {value}")
                    found_any = True
            
            if not found_any:
                return "Could not extract any contact fields from the transcript."
            
            # Also guess classification
            classification = result.get("classification")
            if classification:
                lines.append(f"**Suggested Classification:** {classification}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error parsing voice transcript: {str(e)}"


class ExtractFromImageTool(BaseTool):
    """Tool for extracting contact info from images."""
    
    name: str = "extract_from_image"
    description: str = """Extract contact information from an image (business card, document).
    Uses OCR to read text and then parses for contact details."""
    
    def _run(self, image_path: str = None, image_data: bytes = None) -> str:
        """Extract contact info from an image."""
        try:
            ai_service = get_ai_service()
            
            # Read image file if path provided
            if image_path and not image_data:
                with open(image_path, "rb") as f:
                    image_data = f.read()
            
            if not image_data:
                return "No image data provided."
            
            # Determine image type
            image_type = "image/jpeg"
            if image_path:
                if image_path.lower().endswith(".png"):
                    image_type = "image/png"
                elif image_path.lower().endswith(".webp"):
                    image_type = "image/webp"
            
            result = ai_service.extract_from_image(image_data, image_type)
            
            if not result:
                return "Could not extract contact information from the image."
            
            lines = ["**Extracted from Image:**", ""]
            
            field_names = {
                "name": "Name",
                "job_title": "Job Title",
                "company": "Company",
                "phone": "Phone",
                "email": "Email",
                "linkedin_url": "LinkedIn",
                "location": "Location"
            }
            
            for field, label in field_names.items():
                value = result.get(field)
                if value:
                    lines.append(f"**{label}:** {value}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Error extracting from image: {str(e)}"
