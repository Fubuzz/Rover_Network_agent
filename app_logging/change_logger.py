"""
Feature change logging for CHANGELOG generation.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from .logger import get_changes_logger, log_with_data
from data.storage import get_analytics_db
from config import DOCS_DIR


class ChangeLogger:
    """Logs feature changes for changelog generation."""
    
    VERSION = "1.0.0"
    
    def __init__(self):
        self._logger = None
        self._db = None
    
    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = get_changes_logger()
        return self._logger
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def log_feature_add(self, feature_name: str, description: str,
                       version: str = None, author: str = None,
                       files_changed: List[str] = None):
        """Log a new feature addition."""
        version = version or self.VERSION
        
        data = {
            "event": "feature_added",
            "change_type": "added",
            "feature_name": feature_name,
            "description": description,
            "version": version,
            "author": author,
            "files_changed": files_changed,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Feature added: {feature_name}",
            data
        )
        
        self.db.record_feature_change(
            change_type="added",
            feature_name=feature_name,
            description=description,
            version=version,
            author=author,
            files_changed=files_changed
        )
    
    def log_feature_modify(self, feature_name: str, description: str,
                          version: str = None, author: str = None,
                          files_changed: List[str] = None):
        """Log a feature modification."""
        version = version or self.VERSION
        
        data = {
            "event": "feature_modified",
            "change_type": "modified",
            "feature_name": feature_name,
            "description": description,
            "version": version,
            "author": author,
            "files_changed": files_changed,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Feature modified: {feature_name}",
            data
        )
        
        self.db.record_feature_change(
            change_type="modified",
            feature_name=feature_name,
            description=description,
            version=version,
            author=author,
            files_changed=files_changed
        )
    
    def log_feature_remove(self, feature_name: str, description: str,
                          version: str = None, author: str = None):
        """Log a feature removal."""
        version = version or self.VERSION
        
        data = {
            "event": "feature_removed",
            "change_type": "removed",
            "feature_name": feature_name,
            "description": description,
            "version": version,
            "author": author,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Feature removed: {feature_name}",
            data
        )
        
        self.db.record_feature_change(
            change_type="removed",
            feature_name=feature_name,
            description=description,
            version=version,
            author=author
        )
    
    def get_change_history(self, limit: int = 50) -> List[Dict]:
        """Get feature change history."""
        return self.db.get_change_history(limit=limit)
    
    def generate_changelog(self) -> str:
        """Generate CHANGELOG.md content from change history."""
        changes = self.get_change_history(limit=500)
        
        if not changes:
            return "# Changelog\n\nNo changes recorded yet.\n"
        
        # Group changes by version
        by_version = {}
        for change in changes:
            version = change.get('version', 'Unreleased')
            if version not in by_version:
                by_version[version] = {
                    "added": [],
                    "modified": [],
                    "removed": [],
                    "date": change.get('timestamp', '')[:10]
                }
            
            change_type = change.get('change_type', 'modified')
            by_version[version][change_type].append({
                "feature": change.get('feature_name', ''),
                "description": change.get('description', '')
            })
        
        # Generate markdown
        lines = [
            "# Changelog",
            "",
            "All notable changes to this project will be documented in this file.",
            "",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/).",
            ""
        ]
        
        for version, data in sorted(by_version.items(), reverse=True):
            lines.append(f"## [{version}] - {data['date']}")
            lines.append("")
            
            if data['added']:
                lines.append("### Added")
                for item in data['added']:
                    lines.append(f"- **{item['feature']}**: {item['description']}")
                lines.append("")
            
            if data['modified']:
                lines.append("### Changed")
                for item in data['modified']:
                    lines.append(f"- **{item['feature']}**: {item['description']}")
                lines.append("")
            
            if data['removed']:
                lines.append("### Removed")
                for item in data['removed']:
                    lines.append(f"- **{item['feature']}**: {item['description']}")
                lines.append("")
        
        return "\n".join(lines)
    
    def save_changelog(self, path: Path = None):
        """Save generated changelog to file."""
        path = path or (DOCS_DIR / "CHANGELOG.md")
        content = self.generate_changelog()
        
        path.parent.mkdir(exist_ok=True)
        path.write_text(content)
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Changelog saved to {path}",
            {"path": str(path)}
        )


# Global instance
_change_logger: Optional[ChangeLogger] = None


def get_change_logger() -> ChangeLogger:
    """Get or create change logger instance."""
    global _change_logger
    if _change_logger is None:
        _change_logger = ChangeLogger()
    return _change_logger
