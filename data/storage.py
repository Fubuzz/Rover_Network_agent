"""
Data storage abstraction for analytics database.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from config import AnalyticsConfig


class AnalyticsDatabase:
    """SQLite database for analytics storage."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or AnalyticsConfig.DB_PATH
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            self._create_tables(conn)
    
    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Create all required tables."""
        cursor = conn.cursor()
        
        # Operations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER DEFAULT 0,
                agent_name TEXT,
                crew_name TEXT,
                user_id TEXT,
                command TEXT,
                error_message TEXT,
                error_type TEXT,
                input_data TEXT,
                output_data TEXT
            )
        """)
        
        # Feature usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_name TEXT NOT NULL,
                usage_count INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0
            )
        """)
        
        # Agent activity table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                action TEXT NOT NULL,
                tool_used TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                operation_id INTEGER,
                FOREIGN KEY (operation_id) REFERENCES operations(id)
            )
        """)
        
        # Error log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operation_id INTEGER,
                agent_name TEXT,
                resolved INTEGER DEFAULT 0,
                resolution TEXT,
                FOREIGN KEY (operation_id) REFERENCES operations(id)
            )
        """)
        
        # Feature changes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_type TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                description TEXT NOT NULL,
                version TEXT DEFAULT '1.0.0',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                author TEXT,
                files_changed TEXT
            )
        """)
        
        conn.commit()
    
    # Operations methods
    def record_operation(self, operation_type: str, status: str, 
                        duration_ms: int = 0, agent_name: str = None,
                        crew_name: str = None, user_id: str = None,
                        command: str = None, error_message: str = None,
                        error_type: str = None, input_data: Dict = None,
                        output_data: Dict = None) -> int:
        """Record an operation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO operations (
                    operation_type, status, duration_ms, agent_name, crew_name,
                    user_id, command, error_message, error_type, input_data, output_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                operation_type, status, duration_ms, agent_name, crew_name,
                user_id, command, error_message, error_type,
                json.dumps(input_data) if input_data else None,
                json.dumps(output_data) if output_data else None
            ))
            return cursor.lastrowid
    
    def get_operations(self, limit: int = 100, offset: int = 0,
                       status: str = None, operation_type: str = None) -> List[Dict]:
        """Get operations with optional filters."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM operations WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            if operation_type:
                query += " AND operation_type = ?"
                params.append(operation_type)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_operation_stats(self, days: int = 7) -> Dict:
        """Get operation statistics for the last N days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total and success/failure counts
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) as failure,
                    AVG(duration_ms) as avg_duration,
                    MAX(duration_ms) as max_duration
                FROM operations
                WHERE timestamp >= datetime('now', ?)
            """, (f'-{days} days',))
            
            row = cursor.fetchone()
            total = row['total'] or 0
            success = row['success'] or 0
            
            return {
                'total': total,
                'success': success,
                'failure': row['failure'] or 0,
                'success_rate': success / total if total > 0 else 0,
                'avg_duration_ms': row['avg_duration'] or 0,
                'max_duration_ms': row['max_duration'] or 0
            }
    
    # Feature usage methods
    def record_feature_usage(self, feature_name: str, user_id: str = None,
                            success: bool = True):
        """Record feature usage."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if feature exists for user
            cursor.execute("""
                SELECT id, usage_count, success_count, failure_count 
                FROM feature_usage 
                WHERE feature_name = ? AND (user_id = ? OR user_id IS NULL)
            """, (feature_name, user_id))
            
            row = cursor.fetchone()
            
            if row:
                cursor.execute("""
                    UPDATE feature_usage 
                    SET usage_count = usage_count + 1,
                        last_used = CURRENT_TIMESTAMP,
                        success_count = success_count + ?,
                        failure_count = failure_count + ?
                    WHERE id = ?
                """, (1 if success else 0, 0 if success else 1, row['id']))
            else:
                cursor.execute("""
                    INSERT INTO feature_usage (
                        feature_name, user_id, success_count, failure_count
                    ) VALUES (?, ?, ?, ?)
                """, (feature_name, user_id, 1 if success else 0, 0 if success else 1))
    
    def get_feature_usage_stats(self) -> Dict[str, int]:
        """Get feature usage statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT feature_name, SUM(usage_count) as total
                FROM feature_usage
                GROUP BY feature_name
                ORDER BY total DESC
            """)
            return {row['feature_name']: row['total'] for row in cursor.fetchall()}
    
    # Agent activity methods
    def record_agent_activity(self, agent_name: str, action: str,
                             tool_used: str = None, duration_ms: int = 0,
                             success: bool = True, operation_id: int = None):
        """Record agent activity."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_activity (
                    agent_name, action, tool_used, duration_ms, success, operation_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (agent_name, action, tool_used, duration_ms, 1 if success else 0, operation_id))
    
    def get_agent_stats(self) -> Dict[str, Dict]:
        """Get agent performance statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    agent_name,
                    COUNT(*) as total,
                    SUM(success) as success_count,
                    AVG(duration_ms) as avg_duration
                FROM agent_activity
                GROUP BY agent_name
            """)
            
            result = {}
            for row in cursor.fetchall():
                total = row['total'] or 0
                success = row['success_count'] or 0
                result[row['agent_name']] = {
                    'total': total,
                    'success_count': success,
                    'success_rate': success / total if total > 0 else 0,
                    'avg_duration_ms': row['avg_duration'] or 0
                }
            return result
    
    # Error log methods
    def record_error(self, error_type: str, error_message: str,
                    stack_trace: str = None, operation_id: int = None,
                    agent_name: str = None) -> int:
        """Record an error."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO error_logs (
                    error_type, error_message, stack_trace, operation_id, agent_name
                ) VALUES (?, ?, ?, ?, ?)
            """, (error_type, error_message, stack_trace, operation_id, agent_name))
            return cursor.lastrowid
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """Get recent errors."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM error_logs
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def resolve_error(self, error_id: int, resolution: str):
        """Mark error as resolved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE error_logs
                SET resolved = 1, resolution = ?
                WHERE id = ?
            """, (resolution, error_id))
    
    # Feature changes methods
    def record_feature_change(self, change_type: str, feature_name: str,
                             description: str, version: str = "1.0.0",
                             author: str = None, files_changed: List[str] = None):
        """Record a feature change."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feature_changes (
                    change_type, feature_name, description, version, author, files_changed
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                change_type, feature_name, description, version, author,
                json.dumps(files_changed) if files_changed else None
            ))
    
    def get_change_history(self, limit: int = 50) -> List[Dict]:
        """Get feature change history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM feature_changes
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # Dashboard methods
    def get_dashboard_data(self) -> Dict:
        """Get data for real-time dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Operations today
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM operations
                WHERE date(timestamp) = date('now')
            """)
            ops_today = cursor.fetchone()['count']
            
            # Success rate
            stats = self.get_operation_stats(days=1)
            
            # Recent activity
            cursor.execute("""
                SELECT operation_type, status, timestamp
                FROM operations
                ORDER BY timestamp DESC
                LIMIT 5
            """)
            recent = [
                f"{row['operation_type']}: {row['status']}"
                for row in cursor.fetchall()
            ]
            
            # Determine status
            success_rate = stats.get('success_rate', 0)
            if success_rate >= 0.9:
                status = "healthy"
            elif success_rate >= 0.7:
                status = "warning"
            else:
                status = "critical"
            
            return {
                'status': status,
                'operations_today': ops_today,
                'success_rate': success_rate,
                'avg_response_time': stats.get('avg_duration_ms', 0),
                'recent_activity': recent,
                'total_contacts': 0  # Will be updated from Google Sheets
            }


# Global database instance
_db_instance: Optional[AnalyticsDatabase] = None


def get_analytics_db() -> AnalyticsDatabase:
    """Get or create analytics database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = AnalyticsDatabase()
    return _db_instance
