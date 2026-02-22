"""
MessageResponse dataclass — carries text + optional inline buttons
through the conversation pipeline without importing telegram.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MessageResponse:
    text: str
    buttons: Optional[list[list[tuple[str, str]]]] = None  # [[("label", "callback_data"), ...], ...]

    @staticmethod
    def plain(text: str) -> "MessageResponse":
        return MessageResponse(text=text)
