"""
Voice transcription service.
"""

from typing import Optional
import aiohttp
import io

from config import APIConfig, TelegramConfig, FeatureFlags
from services.ai_service import get_ai_service


class TranscriptionService:
    """Service for transcribing voice messages."""
    
    def __init__(self):
        self._ai_service = None
    
    @property
    def ai_service(self):
        if self._ai_service is None:
            self._ai_service = get_ai_service()
        return self._ai_service
    
    async def download_telegram_file(self, file_id: str) -> Optional[bytes]:
        """Download a file from Telegram servers."""
        try:
            bot_token = TelegramConfig.BOT_TOKEN
            
            # Get file path
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{bot_token}/getFile"
                async with session.get(url, params={"file_id": file_id}) as resp:
                    if resp.status != 200:
                        return None
                    
                    data = await resp.json()
                    if not data.get("ok"):
                        return None
                    
                    file_path = data["result"]["file_path"]
                
                # Download file
                file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                async with session.get(file_url) as resp:
                    if resp.status != 200:
                        return None
                    
                    return await resp.read()
                    
        except Exception as e:
            print(f"Error downloading file: {e}")
            return None
    
    def transcribe_with_whisper(self, audio_data: bytes, 
                                filename: str = "voice.ogg") -> Optional[str]:
        """Transcribe audio using OpenAI Whisper."""
        if not FeatureFlags.VOICE_TRANSCRIPTION:
            return None
        
        return self.ai_service.transcribe_audio(audio_data, filename)
    
    async def transcribe_voice_message(self, file_id: str) -> Optional[str]:
        """
        Transcribe a Telegram voice message.
        
        Args:
            file_id: Telegram file ID for the voice message.
        
        Returns:
            Transcribed text or None if failed.
        """
        if not FeatureFlags.VOICE_TRANSCRIPTION:
            return None
        
        # Download the voice file
        audio_data = await self.download_telegram_file(file_id)
        if not audio_data:
            return None
        
        # Transcribe using Whisper
        transcript = self.transcribe_with_whisper(audio_data)
        
        return transcript
    
    def transcribe_audio_file(self, file_path: str) -> Optional[str]:
        """
        Transcribe an audio file from disk.
        
        Args:
            file_path: Path to the audio file.
        
        Returns:
            Transcribed text or None if failed.
        """
        if not FeatureFlags.VOICE_TRANSCRIPTION:
            return None
        
        try:
            with open(file_path, "rb") as f:
                audio_data = f.read()
            
            filename = file_path.split("/")[-1]
            return self.transcribe_with_whisper(audio_data, filename)
            
        except Exception as e:
            print(f"Error transcribing file: {e}")
            return None


# Global service instance
_transcription_service: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    """Get or create transcription service instance."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service
