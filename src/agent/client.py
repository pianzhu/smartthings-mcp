"""
SmartThings Agent Client
Main agent that orchestrates MCP tools using Claude AI
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from .context_manager import ConversationContext
from .planner import WorkflowPlanner, Intent
from .error_handler import ErrorHandler, AgentError, ErrorType
from .prompts import AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SmartThingsAgent:
    """
    Smart Home Agent that uses Claude AI with SmartThings MCP server

    This agent implements the three-layer architecture:
    - Context Layer: System prompt, static context (cached)
    - Planning Layer: Intent recognition, task decomposition
    - Execution Layer: Tool calls, result processing
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
        mcp_tools: Optional[List[Dict]] = None,
    ):
        """
        Initialize the agent

        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env)
            model: Claude model to use
            mcp_tools: List of MCP tool definitions (schema format)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key parameter."
            )

        self.client = Anthropic(api_key=self.api_key)
        self.model = model
        self.mcp_tools = mcp_tools or []

        # Core components
        self.context_manager = ConversationContext()
        self.planner = WorkflowPlanner()
        self.error_handler = ErrorHandler()

        # Conversation state
        self.messages: List[Dict[str, Any]] = []
        self.system_prompt = AGENT_SYSTEM_PROMPT

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cache_creation_tokens = 0

    def set_mcp_tools(self, tools: List[Dict]):
        """
        Set MCP tools available to the agent

        Args:
            tools: List of tool definitions in Anthropic tool schema format
        """
        self.mcp_tools = tools

    def chat(self, user_message: str, mcp_executor: Optional[callable] = None) -> str:
        """
        Process a user message and return agent response

        Args:
            user_message: User's natural language input
            mcp_executor: Optional function to execute MCP tools
                         Should accept (tool_name, parameters) and return result

        Returns:
            Agent's text response
        """
        # Increment turn
        self.context_manager.increment_turn()

        # Extract room context if mentioned
        room = self.context_manager.infer_room_from_input(user_message)
        if room:
            self.context_manager.current_room = room

        # Recognize intent
        intent = self.planner.intent_recognizer.recognize(user_message)
        self.context_manager.set_intent(intent.value)

        logger.info(
            f"Turn {self.context_manager.current_turn}: Intent={intent.value}, Room={room}"
        )

        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Call Claude API
        try:
            response = self._call_claude_api()
            assistant_message = self._process_claude_response(response, mcp_executor)

            # Add assistant response to history
            self.messages.append({"role": "assistant", "content": assistant_message})

            # Update token counts
            self._update_token_usage(response.usage)

            # Cleanup old devices if conversation is getting long
            if self.context_manager.current_turn > 20:
                self.context_manager.cleanup_old_devices(turns_threshold=10)

            return assistant_message

        except Exception as e:
            error_response = self.error_handler.handle_error(
                e, context={"user_message": user_message, "intent": intent.value}
            )
            logger.error(f"Error in chat: {error_response}")
            return error_response["user_message"]

    def _call_claude_api(self) -> Any:
        """
        Call Claude API with current conversation state

        Returns:
            Claude API response
        """
        # Prepare system prompt with caching
        system_messages = [
            {
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        # Add context summary if conversation is starting
        if self.context_manager.current_turn == 1:
            context_summary = (
                "This is the start of a new conversation with the user."
            )
        else:
            context_summary = self._build_context_summary()

        system_messages.append({"type": "text", "text": context_summary})

        # Call API
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_messages,
            "messages": self.messages,
        }

        # Add tools if available
        if self.mcp_tools:
            kwargs["tools"] = self.mcp_tools

        logger.debug(f"Calling Claude API with {len(self.messages)} messages")

        response = self.client.messages.create(**kwargs)

        return response

    def _process_claude_response(
        self, response: Any, mcp_executor: Optional[callable]
    ) -> str:
        """
        Process Claude's response, executing tool calls if needed

        Args:
            response: Claude API response
            mcp_executor: Function to execute MCP tools

        Returns:
            Final text response
        """
        # Check stop reason
        if response.stop_reason == "end_turn":
            # Simple text response
            return self._extract_text_from_response(response)

        elif response.stop_reason == "tool_use":
            # Claude wants to use tools
            if not mcp_executor:
                return "I need to use tools but no executor is available."

            # Extract tool calls
            tool_uses = [block for block in response.content if block.type == "tool_use"]

            logger.info(f"Executing {len(tool_uses)} tool calls")

            # Execute tools and collect results
            tool_results = []
            for tool_use in tool_uses:
                try:
                    result = mcp_executor(tool_use.name, tool_use.input)

                    # Update context based on tool results
                    self._update_context_from_tool_result(
                        tool_use.name, tool_use.input, result
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result),
                        }
                    )
                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    logger.error(error_msg)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps({"error": error_msg}),
                            "is_error": True,
                        }
                    )

            # Add tool results to conversation
            self.messages.append(
                {"role": "assistant", "content": response.content}
            )  # Claude's tool use
            self.messages.append(
                {"role": "user", "content": tool_results}
            )  # Tool results

            # Continue conversation to get final response
            final_response = self._call_claude_api()
            return self._extract_text_from_response(final_response)

        else:
            return self._extract_text_from_response(response)

    def _extract_text_from_response(self, response: Any) -> str:
        """Extract text content from Claude response"""
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(text_blocks)

    def _update_context_from_tool_result(
        self, tool_name: str, tool_input: Dict, result: Any
    ):
        """
        Update conversation context based on tool execution results

        Args:
            tool_name: Name of tool that was executed
            tool_input: Input parameters to the tool
            result: Result from tool execution
        """
        try:
            if tool_name == "search_devices" and isinstance(result, list):
                # Add devices to memory
                for device in result:
                    if "id" in device:
                        self.context_manager.add_device(
                            device_id=device["id"],
                            name=device.get("name", "Unknown"),
                            room=device.get("room"),
                            device_type=device.get("type"),
                        )

            elif tool_name == "get_device_status" and isinstance(result, dict):
                # Update device status in cache
                device_id = tool_input.get("device_id")
                if device_id and "components" in result:
                    self.context_manager.update_device_status(device_id, result)

            elif tool_name == "get_context_summary":
                # Could extract room/device info from summary
                pass

        except Exception as e:
            logger.warning(f"Failed to update context from tool result: {e}")

    def _build_context_summary(self) -> str:
        """
        Build context summary for system prompt

        Returns:
            Formatted context string
        """
        summary_parts = []

        # Add current room if known
        if self.context_manager.current_room:
            summary_parts.append(
                f"Current room context: {self.context_manager.current_room}"
            )

        # Add recently mentioned devices
        if self.context_manager.mentioned_devices:
            devices_list = []
            for device in list(self.context_manager.mentioned_devices.values())[:5]:
                devices_list.append(
                    f"- {device.name} (ID: {device.device_id}, Room: {device.room})"
                )
            summary_parts.append(
                "Recently mentioned devices:\n" + "\n".join(devices_list)
            )

        # Add last intent
        if self.context_manager.last_intent:
            summary_parts.append(f"Last intent: {self.context_manager.last_intent}")

        if summary_parts:
            return "CONVERSATION CONTEXT:\n" + "\n\n".join(summary_parts)
        else:
            return "CONVERSATION CONTEXT: No context yet."

    def _update_token_usage(self, usage):
        """Update token usage statistics"""
        self.total_input_tokens += getattr(usage, "input_tokens", 0)
        self.total_output_tokens += getattr(usage, "output_tokens", 0)

        # Cache tokens (if prompt caching is used)
        if hasattr(usage, "cache_read_input_tokens"):
            self.total_cache_read_tokens += usage.cache_read_input_tokens
        if hasattr(usage, "cache_creation_input_tokens"):
            self.total_cache_creation_tokens += usage.cache_creation_input_tokens

    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage statistics"""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "cache_read_tokens": self.total_cache_read_tokens,
            "cache_creation_tokens": self.total_cache_creation_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
        }

    def reset_conversation(self):
        """Reset conversation state"""
        self.messages = []
        self.context_manager = ConversationContext()
        logger.info("Conversation reset")

    def get_context_summary(self) -> Dict[str, Any]:
        """Get current context summary for debugging"""
        return {
            "conversation_turn": self.context_manager.current_turn,
            "context": self.context_manager.get_summary(),
            "token_usage": self.get_token_usage(),
            "message_count": len(self.messages),
        }
