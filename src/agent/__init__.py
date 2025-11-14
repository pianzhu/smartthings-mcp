"""
SmartThings Agent Package

A comprehensive AI agent for controlling SmartThings devices using Claude AI and MCP.
"""

# Core components that don't require external dependencies
from .context_manager import ConversationContext, DeviceMemory
from .planner import WorkflowPlanner, Intent, Workflow, WorkflowStep
from .error_handler import ErrorHandler, AgentError, ErrorType, FallbackStrategy
from .prompts import AGENT_SYSTEM_PROMPT

# Optional import - requires anthropic SDK
try:
    from .client import SmartThingsAgent
    _has_client = True
except ImportError:
    SmartThingsAgent = None
    _has_client = False

__all__ = [
    "ConversationContext",
    "DeviceMemory",
    "WorkflowPlanner",
    "Intent",
    "Workflow",
    "WorkflowStep",
    "ErrorHandler",
    "AgentError",
    "ErrorType",
    "FallbackStrategy",
    "AGENT_SYSTEM_PROMPT",
]

if _has_client:
    __all__.append("SmartThingsAgent")

__version__ = "1.0.0"
