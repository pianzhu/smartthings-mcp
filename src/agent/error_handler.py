"""
Error Handling and Fallback Strategies
Implements graceful degradation for agent operations
"""

from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur"""

    DEVICE_NOT_FOUND = "device_not_found"
    COMMAND_NOT_SUPPORTED = "command_not_supported"
    PARAMETER_INVALID = "parameter_invalid"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


class AgentError(Exception):
    """Base exception for agent errors"""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.context = context or {}
        self.user_message = message


class FallbackStrategy:
    """Defines fallback strategies for different error types"""

    @staticmethod
    def device_not_found_fallback(
        original_query: str, search_func: Callable
    ) -> Optional[List[Dict]]:
        """
        Fallback when device is not found

        Strategies:
        1. Remove room constraint
        2. Use fuzzy matching
        3. Broaden search terms

        Args:
            original_query: The original search query that failed
            search_func: Function to call for searching (should accept query param)

        Returns:
            List of devices if found, None otherwise
        """
        fallback_queries = []

        # Strategy 1: Remove room-specific words
        query_without_room = original_query
        for room in ["客厅", "卧室", "厨房", "浴室", "living room", "bedroom", "kitchen"]:
            query_without_room = query_without_room.replace(room, "").strip()

        if query_without_room != original_query:
            fallback_queries.append(query_without_room)

        # Strategy 2: Extract device type only
        device_types = ["灯", "空调", "锁", "传感器", "light", "ac", "lock", "sensor"]
        for device_type in device_types:
            if device_type in original_query:
                fallback_queries.append(device_type)

        # Try each fallback
        for query in fallback_queries:
            try:
                logger.info(f"Trying fallback query: {query}")
                results = search_func(query=query)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Fallback query '{query}' failed: {e}")
                continue

        return None

    @staticmethod
    def command_not_supported_fallback(
        device_id: str, capability: str, get_commands_func: Callable
    ) -> Optional[List[str]]:
        """
        Fallback when command is not supported

        Strategy: Get list of supported commands for the capability

        Args:
            device_id: Device identifier
            capability: Capability name
            get_commands_func: Function to get available commands

        Returns:
            List of supported commands, None if error
        """
        try:
            logger.info(
                f"Getting supported commands for device {device_id}, capability {capability}"
            )
            commands_info = get_commands_func(device_id=device_id, capability=capability)
            if commands_info and "commands" in commands_info:
                return commands_info["commands"]
        except Exception as e:
            logger.error(f"Failed to get supported commands: {e}")

        return None

    @staticmethod
    def parameter_invalid_fallback(
        parameter_name: str, parameter_value: Any, valid_range: Optional[tuple] = None
    ) -> Any:
        """
        Fallback when parameter is invalid

        Strategy: Clamp value to valid range

        Args:
            parameter_name: Name of parameter
            parameter_value: Invalid value
            valid_range: Tuple of (min, max) if known

        Returns:
            Corrected parameter value
        """
        if valid_range and isinstance(parameter_value, (int, float)):
            min_val, max_val = valid_range
            if parameter_value < min_val:
                logger.warning(
                    f"Parameter {parameter_name}={parameter_value} too low, clamping to {min_val}"
                )
                return min_val
            elif parameter_value > max_val:
                logger.warning(
                    f"Parameter {parameter_name}={parameter_value} too high, clamping to {max_val}"
                )
                return max_val

        return parameter_value


class ErrorHandler:
    """Handles errors and executes fallback strategies"""

    def __init__(self):
        self.error_history: List[Dict[str, Any]] = []

    def handle_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle an error and determine response

        Args:
            error: The exception that occurred
            context: Optional context about the error

        Returns:
            Dictionary with error info and suggested action
        """
        error_info = {
            "error_type": self._classify_error(error),
            "message": str(error),
            "context": context or {},
            "timestamp": None,  # Would use datetime.now() in production
        }

        # Log error
        self.error_history.append(error_info)
        logger.error(f"Error occurred: {error_info}")

        # Determine fallback strategy
        fallback = self._determine_fallback(error_info)

        return {
            "error": error_info,
            "fallback": fallback,
            "user_message": self._generate_user_message(error_info),
        }

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error into ErrorType"""
        if isinstance(error, AgentError):
            return error.error_type

        error_str = str(error).lower()

        if "not found" in error_str or "no device" in error_str:
            return ErrorType.DEVICE_NOT_FOUND
        elif "not supported" in error_str or "invalid command" in error_str:
            return ErrorType.COMMAND_NOT_SUPPORTED
        elif "invalid parameter" in error_str or "invalid value" in error_str:
            return ErrorType.PARAMETER_INVALID
        elif "timeout" in error_str:
            return ErrorType.TIMEOUT
        elif "permission" in error_str or "unauthorized" in error_str:
            return ErrorType.PERMISSION_DENIED
        elif "network" in error_str or "connection" in error_str:
            return ErrorType.NETWORK_ERROR
        else:
            return ErrorType.UNKNOWN

    def _determine_fallback(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Determine appropriate fallback strategy"""
        error_type = error_info["error_type"]

        if error_type == ErrorType.DEVICE_NOT_FOUND:
            return {
                "strategy": "broaden_search",
                "action": "Try removing room constraint or using device type only",
            }
        elif error_type == ErrorType.COMMAND_NOT_SUPPORTED:
            return {
                "strategy": "get_supported_commands",
                "action": "Call get_device_commands to see what's available",
            }
        elif error_type == ErrorType.PARAMETER_INVALID:
            return {
                "strategy": "validate_parameters",
                "action": "Check valid range or use default value",
            }
        elif error_type == ErrorType.NETWORK_ERROR or error_type == ErrorType.TIMEOUT:
            return {
                "strategy": "retry",
                "action": "Retry the operation after brief delay",
                "max_retries": 3,
            }
        elif error_type == ErrorType.PERMISSION_DENIED:
            return {
                "strategy": "inform_user",
                "action": "Ask user to check permissions",
            }
        else:
            return {
                "strategy": "ask_user",
                "action": "Ask user for clarification",
            }

    def _generate_user_message(self, error_info: Dict[str, Any]) -> str:
        """Generate user-friendly error message"""
        error_type = error_info["error_type"]
        context = error_info.get("context", {})

        if error_type == ErrorType.DEVICE_NOT_FOUND:
            query = context.get("query", "")
            return (
                f"I couldn't find a device matching '{query}'. "
                f"Let me try a broader search, or you can be more specific about the device name."
            )
        elif error_type == ErrorType.COMMAND_NOT_SUPPORTED:
            command = context.get("command", "that command")
            return (
                f"This device doesn't support {command}. "
                f"Let me check what commands are available."
            )
        elif error_type == ErrorType.PARAMETER_INVALID:
            param = context.get("parameter", "the parameter")
            return f"The value for {param} is invalid. Let me try to correct it."
        elif error_type == ErrorType.NETWORK_ERROR:
            return "I'm having trouble connecting to the SmartThings service. Let me try again."
        elif error_type == ErrorType.PERMISSION_DENIED:
            return "I don't have permission to perform this action. Please check your SmartThings app permissions."
        else:
            return (
                "I encountered an unexpected error. Could you try rephrasing your request?"
            )

    def should_retry(self, error_type: ErrorType) -> bool:
        """Determine if operation should be retried"""
        retry_types = [
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT,
            ErrorType.API_ERROR,
        ]
        return error_type in retry_types

    def get_retry_count(self, operation_id: str) -> int:
        """Get number of times an operation has been retried"""
        count = 0
        for error in self.error_history:
            if error.get("context", {}).get("operation_id") == operation_id:
                count += 1
        return count


def with_fallback(primary_func: Callable, fallback_func: Callable, max_attempts: int = 2):
    """
    Decorator to add fallback behavior to a function

    Args:
        primary_func: Primary function to try
        fallback_func: Fallback function if primary fails
        max_attempts: Maximum number of attempts

    Returns:
        Result from primary or fallback function
    """

    def wrapper(*args, **kwargs):
        for attempt in range(max_attempts):
            try:
                return primary_func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed for {primary_func.__name__}: {e}"
                )
                if attempt == max_attempts - 1:
                    # Last attempt, try fallback
                    logger.info(f"Using fallback for {primary_func.__name__}")
                    return fallback_func(*args, **kwargs)

    return wrapper
