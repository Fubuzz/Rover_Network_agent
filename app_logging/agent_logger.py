"""
Agent activity logging.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from .logger import get_agents_logger, log_with_data
from data.storage import get_analytics_db


class AgentLogger:
    """Logs agent activities and interactions."""
    
    def __init__(self):
        self._logger = None
        self._db = None
    
    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = get_agents_logger()
        return self._logger
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_analytics_db()
        return self._db
    
    def log_agent_action(self, agent_name: str, action: str,
                        tool_used: str = None, duration_ms: int = 0,
                        success: bool = True, operation_id: int = None):
        """Log an agent action."""
        data = {
            "event": "agent_action",
            "agent_name": agent_name,
            "action": action,
            "tool_used": tool_used,
            "duration_ms": duration_ms,
            "success": success,
            "operation_id": operation_id,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO if success else logging.WARNING,
            f"Agent {agent_name}: {action}",
            data
        )
        
        # Also record to database
        self.db.record_agent_activity(
            agent_name=agent_name,
            action=action,
            tool_used=tool_used,
            duration_ms=duration_ms,
            success=success,
            operation_id=operation_id
        )
    
    def log_agent_decision(self, agent_name: str, decision: str,
                          reasoning: str = None, context: Dict = None):
        """Log an agent decision."""
        data = {
            "event": "agent_decision",
            "agent_name": agent_name,
            "decision": decision,
            "reasoning": reasoning,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.DEBUG,
            f"Agent {agent_name} decided: {decision}",
            data
        )
    
    def log_agent_tool_usage(self, agent_name: str, tool_name: str,
                            input_data: Dict = None, output_data: Dict = None,
                            duration_ms: int = 0, success: bool = True):
        """Log agent tool usage."""
        data = {
            "event": "agent_tool_usage",
            "agent_name": agent_name,
            "tool_name": tool_name,
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO if success else logging.WARNING,
            f"Agent {agent_name} used tool {tool_name}",
            data
        )
    
    def log_agent_interaction(self, from_agent: str, to_agent: str,
                             interaction_type: str, message: str = None):
        """Log interaction between agents."""
        data = {
            "event": "agent_interaction",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "interaction_type": interaction_type,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.DEBUG,
            f"Agent interaction: {from_agent} -> {to_agent} ({interaction_type})",
            data
        )
    
    def log_crew_start(self, crew_name: str, agents: list,
                      task_description: str = None):
        """Log crew execution start."""
        data = {
            "event": "crew_start",
            "crew_name": crew_name,
            "agents": agents,
            "task_description": task_description,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO,
            f"Crew started: {crew_name} with agents {agents}",
            data
        )
    
    def log_crew_complete(self, crew_name: str, duration_ms: int,
                          result: Dict = None, success: bool = True):
        """Log crew execution completion."""
        data = {
            "event": "crew_complete",
            "crew_name": crew_name,
            "duration_ms": duration_ms,
            "result": result,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        log_with_data(
            self.logger,
            logging.INFO if success else logging.ERROR,
            f"Crew completed: {crew_name} ({duration_ms}ms)",
            data
        )


# Global instance
_agent_logger: Optional[AgentLogger] = None


def get_agent_logger() -> AgentLogger:
    """Get or create agent logger instance."""
    global _agent_logger
    if _agent_logger is None:
        _agent_logger = AgentLogger()
    return _agent_logger
