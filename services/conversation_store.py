"""
Conversation Store - SQLite-based message history per user.
Stores last 20 messages per user for injection into system prompt.
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger('network_agent')

DB_PATH = DATA_DIR / "conversations.db"


class ConversationStore:
    """Manages conversation history in SQLite."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_timestamp (user_id, timestamp)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_message(self, user_id: str, role: str, content: str):
        """
        Add a message to conversation history.
        
        Args:
            user_id: User identifier
            role: 'user' or 'assistant'
            content: Message content
        """
        if not content or not content.strip():
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (user_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        """, (user_id, role, content.strip(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Trim to last 50 messages (keep buffer above 20 for safety)
        self._trim_old_messages(user_id, keep_last=50)
    
    def get_recent_messages(self, user_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Get recent messages for a user.
        
        Args:
            user_id: User identifier
            limit: Number of recent messages to retrieve (default 20)
        
        Returns:
            List of dicts with 'role' and 'content'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, timestamp
            FROM conversations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Reverse to get chronological order (oldest first)
        messages = [
            {"role": row[0], "content": row[1]}
            for row in reversed(rows)
        ]
        
        return messages
    
    def _trim_old_messages(self, user_id: str, keep_last: int = 50):
        """Keep only the last N messages for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM conversations
            WHERE user_id = ?
            AND id NOT IN (
                SELECT id FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
        """, (user_id, user_id, keep_last))
        
        conn.commit()
        conn.close()
    
    def clear_user_history(self, user_id: str):
        """Clear all conversation history for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
    
    def format_recent_context(self, user_id: str, limit: int = 10) -> str:
        """
        Format recent messages as context string for system prompt.
        
        Args:
            user_id: User identifier
            limit: Number of recent messages (default 10 for compact prompt)
        
        Returns:
            Formatted string of recent messages
        """
        messages = self.get_recent_messages(user_id, limit)
        
        if not messages:
            return "No recent conversation."
        
        lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Rover"
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)


# Global singleton
_conversation_store: Optional[ConversationStore] = None


def get_conversation_store() -> ConversationStore:
    """Get global conversation store instance."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
    return _conversation_store
