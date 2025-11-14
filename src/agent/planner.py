"""
Intent Recognition and Workflow Planner
Implements decision tree for different user intents
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re


class Intent(Enum):
    """User intent types"""

    CONTROL = "control"  # "打开客厅的灯"
    QUERY = "query"  # "客厅温度是多少？"
    ANALYSIS = "analysis"  # "过去一周的平均温度"
    DISCOVERY = "discovery"  # "我有哪些设备？"
    CONDITIONAL_CONTROL = "conditional_control"  # "如果温度>26度，打开空调"
    UNKNOWN = "unknown"


@dataclass
class WorkflowStep:
    """A single step in workflow execution"""

    tool_name: str
    parameters: Dict[str, Any]
    description: str
    depends_on: Optional[int] = None  # Index of step this depends on
    parallel_group: Optional[int] = None  # Steps with same group can run in parallel


@dataclass
class Workflow:
    """Complete workflow plan"""

    intent: Intent
    steps: List[WorkflowStep]
    description: str
    requires_confirmation: bool = False


class IntentRecognizer:
    """Recognizes user intent from natural language"""

    # Intent patterns
    CONTROL_PATTERNS = [
        r"(打开|关闭|开启|关掉|开|关|turn on|turn off|开灯|关灯)",
        r"(设置|调|调整|set|adjust)",
        r"(锁|解锁|lock|unlock)",
        r"(启动|停止|start|stop)",
    ]

    QUERY_PATTERNS = [
        r"(是多少|怎么样|如何|what|how|状态|current|现在)",
        r"(.*[吗？]$)",  # Questions ending with 吗
        r"(.*\?$)",  # Questions ending with ?
        r"(在哪|where)",
    ]

    ANALYSIS_PATTERNS = [
        r"(过去|历史|统计|平均|总共|history|statistics|average|total)",
        r"(这周|上周|今天|昨天|this week|last week|today|yesterday)",
        r"(趋势|变化|trend|change)",
    ]

    DISCOVERY_PATTERNS = [
        r"(有哪些|列出|显示所有|list|show all)",
        r"(什么设备|all devices|my devices)",
        r"(房间.*设备|devices in)",
    ]

    CONDITIONAL_PATTERNS = [
        r"(如果|假如|when|if).*?(就|then|那么|，|,)",
        r"(当|whenever).*?(时|的时候|，|,)",
    ]

    @staticmethod
    def recognize(user_input: str) -> Intent:
        """
        Recognize intent from user input

        Args:
            user_input: User's natural language input

        Returns:
            Detected Intent
        """
        user_input = user_input.lower()

        # Check conditional first (most specific)
        for pattern in IntentRecognizer.CONDITIONAL_PATTERNS:
            if re.search(pattern, user_input):
                return Intent.CONDITIONAL_CONTROL

        # Check discovery
        for pattern in IntentRecognizer.DISCOVERY_PATTERNS:
            if re.search(pattern, user_input):
                return Intent.DISCOVERY

        # Check analysis
        for pattern in IntentRecognizer.ANALYSIS_PATTERNS:
            if re.search(pattern, user_input):
                return Intent.ANALYSIS

        # Check query
        for pattern in IntentRecognizer.QUERY_PATTERNS:
            if re.search(pattern, user_input):
                return Intent.QUERY

        # Check control
        for pattern in IntentRecognizer.CONTROL_PATTERNS:
            if re.search(pattern, user_input):
                return Intent.CONTROL

        return Intent.UNKNOWN

    @staticmethod
    def extract_device_query(user_input: str) -> str:
        """
        Extract device search query from user input

        Args:
            user_input: User's input

        Returns:
            Extracted query for search_devices
        """
        # Remove common command words
        query = user_input
        remove_patterns = [
            r"^(请|帮我|帮忙|能不能|可以|可否|please|help me|can you)\s*",
            r"(打开|关闭|开启|关掉|turn on|turn off)",
            r"(查询|查看|看看|显示|show|display|check)",
        ]

        for pattern in remove_patterns:
            query = re.sub(pattern, "", query, flags=re.IGNORECASE)

        # Extract room + device type patterns
        # Example: "客厅的灯" → "客厅 灯"
        query = re.sub(r"的", " ", query)
        query = re.sub(r"\s+", " ", query).strip()

        return query


class WorkflowPlanner:
    """Plans workflow based on intent and context"""

    def __init__(self):
        self.intent_recognizer = IntentRecognizer()

    def plan(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Workflow:
        """
        Plan workflow based on user input and context

        Args:
            user_input: User's natural language input
            context: Optional context information (current room, known devices, etc.)
            intent: Optional pre-determined intent (if None, will be detected)

        Returns:
            Workflow plan
        """
        if intent is None:
            intent = self.intent_recognizer.recognize(user_input)

        context = context or {}

        # Route to specific planner based on intent
        if intent == Intent.CONTROL:
            return self._plan_control(user_input, context)
        elif intent == Intent.QUERY:
            return self._plan_query(user_input, context)
        elif intent == Intent.ANALYSIS:
            return self._plan_analysis(user_input, context)
        elif intent == Intent.DISCOVERY:
            return self._plan_discovery(user_input, context)
        elif intent == Intent.CONDITIONAL_CONTROL:
            return self._plan_conditional_control(user_input, context)
        else:
            return self._plan_unknown(user_input, context)

    def _plan_control(
        self, user_input: str, context: Dict[str, Any]
    ) -> Workflow:
        """Plan workflow for CONTROL intent"""
        steps = []

        # Check if we have device_id in context
        cached_device = context.get("cached_device")

        if cached_device:
            # Use cached device, skip search
            steps.append(
                WorkflowStep(
                    tool_name="execute_commands",
                    parameters={
                        "device_id": cached_device["device_id"],
                        "commands": [],  # Will be filled by AI
                    },
                    description=f"Execute command on {cached_device['name']}",
                )
            )
        else:
            # Need to search first
            query = self.intent_recognizer.extract_device_query(user_input)
            steps.append(
                WorkflowStep(
                    tool_name="search_devices",
                    parameters={"query": query, "limit": 5},
                    description=f"Search for devices matching '{query}'",
                )
            )
            steps.append(
                WorkflowStep(
                    tool_name="execute_commands",
                    parameters={
                        "device_id": "<from_step_0>",
                        "commands": [],
                    },
                    description="Execute command on found device",
                    depends_on=0,
                )
            )

        return Workflow(
            intent=Intent.CONTROL, steps=steps, description="Control device workflow"
        )

    def _plan_query(self, user_input: str, context: Dict[str, Any]) -> Workflow:
        """Plan workflow for QUERY intent"""
        steps = []

        cached_device = context.get("cached_device")

        if cached_device:
            # Check if we have fresh cached status
            if context.get("has_fresh_status"):
                # No need to query again, use cached
                return Workflow(
                    intent=Intent.QUERY,
                    steps=[],
                    description="Use cached status (no API call needed)",
                )
            else:
                # Query status for cached device
                steps.append(
                    WorkflowStep(
                        tool_name="get_device_status",
                        parameters={"device_id": cached_device["device_id"]},
                        description=f"Get status of {cached_device['name']}",
                    )
                )
        else:
            # Need to search first
            query = self.intent_recognizer.extract_device_query(user_input)
            steps.append(
                WorkflowStep(
                    tool_name="search_devices",
                    parameters={"query": query, "limit": 5},
                    description=f"Search for devices matching '{query}'",
                )
            )
            steps.append(
                WorkflowStep(
                    tool_name="get_device_status",
                    parameters={"device_id": "<from_step_0>"},
                    description="Get status of found device",
                    depends_on=0,
                )
            )

        return Workflow(
            intent=Intent.QUERY, steps=steps, description="Query device status workflow"
        )

    def _plan_analysis(
        self, user_input: str, context: Dict[str, Any]
    ) -> Workflow:
        """Plan workflow for ANALYSIS intent"""
        steps = []

        # Always need to search for device first
        query = self.intent_recognizer.extract_device_query(user_input)
        steps.append(
            WorkflowStep(
                tool_name="search_devices",
                parameters={"query": query, "limit": 5},
                description=f"Search for devices matching '{query}'",
            )
        )

        # Then get history
        steps.append(
            WorkflowStep(
                tool_name="get_device_history",
                parameters={
                    "device_id": "<from_step_0>",
                    "capability": "<infer_from_device>",
                },
                description="Get device history for analysis",
                depends_on=0,
            )
        )

        return Workflow(
            intent=Intent.ANALYSIS,
            steps=steps,
            description="Analyze device history workflow",
        )

    def _plan_discovery(
        self, user_input: str, context: Dict[str, Any]
    ) -> Workflow:
        """Plan workflow for DISCOVERY intent"""
        # Discovery always uses get_context_summary
        steps = [
            WorkflowStep(
                tool_name="get_context_summary",
                parameters={},
                description="Get overview of all devices",
            )
        ]

        return Workflow(
            intent=Intent.DISCOVERY,
            steps=steps,
            description="Discover devices workflow",
        )

    def _plan_conditional_control(
        self, user_input: str, context: Dict[str, Any]
    ) -> Workflow:
        """Plan workflow for CONDITIONAL_CONTROL intent"""
        steps = []

        # Parse conditional: "如果 X，那么 Y"
        # This is simplified - real parsing would be more sophisticated

        # Step 1: Search for sensor device
        steps.append(
            WorkflowStep(
                tool_name="search_devices",
                parameters={"query": "<extract_sensor_query>", "limit": 5},
                description="Search for sensor device",
            )
        )

        # Step 2: Get sensor status
        steps.append(
            WorkflowStep(
                tool_name="get_device_status",
                parameters={"device_id": "<from_step_0>"},
                description="Get sensor status",
                depends_on=0,
            )
        )

        # Step 3: (AI evaluates condition)
        # Step 4: Search for actuator device
        steps.append(
            WorkflowStep(
                tool_name="search_devices",
                parameters={"query": "<extract_actuator_query>", "limit": 5},
                description="Search for actuator device",
            )
        )

        # Step 5: Execute command if condition is met
        steps.append(
            WorkflowStep(
                tool_name="execute_commands",
                parameters={"device_id": "<from_step_2>", "commands": []},
                description="Execute command if condition is met",
                depends_on=2,
            )
        )

        return Workflow(
            intent=Intent.CONDITIONAL_CONTROL,
            steps=steps,
            description="Conditional control workflow",
            requires_confirmation=True,
        )

    def _plan_unknown(self, user_input: str, context: Dict[str, Any]) -> Workflow:
        """Plan workflow for UNKNOWN intent"""
        # Fallback: try to get context summary
        steps = [
            WorkflowStep(
                tool_name="get_context_summary",
                parameters={},
                description="Get context to help understand user request",
            )
        ]

        return Workflow(
            intent=Intent.UNKNOWN,
            steps=steps,
            description="Unknown intent - getting context",
        )

    def detect_multi_device_operation(self, user_input: str) -> Tuple[bool, int]:
        """
        Detect if user is requesting multiple device operations

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
