"""
Simplified Workflow Planner for Device Control
All requests are device control - no intent classification needed
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class DeviceControlPlan:
    """Plan for controlling devices"""

    device_query: str  # Search query for devices
    command_text: str  # User's command in natural language
    is_multi_device: bool  # Whether controlling multiple devices
    device_count: int  # Estimated number of devices
    requires_interpret: bool  # Whether needs interpret_command


class DeviceControlPlanner:
    """Plans device control workflows - simplified for control-only use case"""

    def __init__(self):
        pass

    def parse_control_request(self, user_input: str) -> DeviceControlPlan:
        """
        Parse user's device control request

        Args:
            user_input: User's natural language input

        Returns:
            DeviceControlPlan with extracted information
        """
        # Extract device query and command
        device_query, command_text = self._split_device_and_command(user_input)

        # Detect multi-device operation
        is_multi, count = self._detect_multi_device(user_input)

        # Check if needs interpret_command (ambiguous commands)
        requires_interpret = self._needs_interpretation(command_text)

        return DeviceControlPlan(
            device_query=device_query,
            command_text=command_text,
            is_multi_device=is_multi,
            device_count=count,
            requires_interpret=requires_interpret
        )

    def _split_device_and_command(self, user_input: str) -> Tuple[str, str]:
        """
        Split user input into device query and command

        Examples:
            "打开客厅的灯" → ("客厅 灯", "打开")
            "让卧室的灯柔和一些" → ("卧室 灯", "柔和一些")
            "把空调调到26度" → ("空调", "调到26度")
        """
        # Remove common action words to extract device query
        command_patterns = [
            r"^(打开|关闭|开启|关掉|开|关|让|把)",
            r"(调到|设置为|设为)",
        ]

        device_query = user_input
        for pattern in command_patterns:
            device_query = re.sub(pattern, "", device_query, flags=re.IGNORECASE)

        # Extract command by removing device references
        # Simple approach: everything after device is command
        command_text = user_input

        # Clean up
        device_query = re.sub(r"的", " ", device_query)
        device_query = re.sub(r"\s+", " ", device_query).strip()

        return device_query, command_text

    def _detect_multi_device(self, user_input: str) -> Tuple[bool, int]:
        """
        Detect if user is controlling multiple devices

        Args:
            user_input: User input

        Returns:
            (is_multi_operation, estimated_device_count)
        """
        # Check for conjunction patterns
        conjunctions = ["和", "与", "及", "还有", "以及", "并且", "，", ",", "and"]

        count = 1
        for conj in conjunctions:
            count += user_input.count(conj)

        is_multi = count > 1

        return is_multi, count

    def _needs_interpretation(self, command_text: str) -> bool:
        """
        Check if command needs interpret_command tool

        Clear commands like "打开", "关闭", "turn on" don't need interpretation.
        Ambiguous commands like "柔和一些", "亮点" need interpretation.
        """
        # Clear command patterns - don't need interpretation
        clear_patterns = [
            r"^(打开|开启|turn\s+on|开)$",
            r"^(关闭|关掉|turn\s+off|关)$",
            r"^(锁上|lock)$",
            r"^(解锁|unlock)$",
            r"(调到|设置|set.*to)\s*\d+",  # Has explicit numeric value
        ]

        command_lower = command_text.lower().strip()

        for pattern in clear_patterns:
            if re.search(pattern, command_lower):
                return False  # Clear command, no interpretation needed

        # Default: needs interpretation for ambiguous commands
        return True

    def should_use_batch(self, device_count: int) -> bool:
        """
        Determine if batch_execute_commands should be used

        Args:
            device_count: Number of devices to operate on

        Returns:
            True if batch should be used
        """
        # Use batch for 4+ devices
        return device_count >= 4
