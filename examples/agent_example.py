"""
Example: Using SmartThings Agent

This example demonstrates how to use the SmartThings Agent to control devices
using natural language with Claude AI and the MCP server.

Prerequisites:
1. Set ANTHROPIC_API_KEY environment variable
2. Set SMARTTHINGS_PAT environment variable
3. MCP server running (or use mock MCP executor for testing)
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent import SmartThingsAgent


# Mock MCP executor for demonstration (replace with real MCP client)
def mock_mcp_executor(tool_name: str, parameters: dict):
    """
    Mock MCP tool executor for demonstration

    In production, this would be replaced with actual MCP client
    that connects to the SmartThings MCP server.
    """
    print(f"\n[MCP Tool Call] {tool_name}")
    print(f"  Parameters: {parameters}")

    # Mock responses for different tools
    if tool_name == "search_devices":
        query = parameters.get("query", "")
        # Simulate search results
        if "客厅" in query and "灯" in query:
            return [
                {
                    "id": "abc-123-def-456",
                    "name": "客厅吸顶灯",
                    "room": "living room",
                    "type": "light",
                    "fullId": "device:abc-123-def-456"
                }
            ]
        elif "卧室" in query and "空调" in query:
            return [
                {
                    "id": "xyz-789-uvw-012",
                    "name": "卧室空调",
                    "room": "bedroom",
                    "type": "air conditioner",
                    "fullId": "device:xyz-789-uvw-012"
                }
            ]
        return []

    elif tool_name == "execute_commands":
        device_id = parameters.get("device_id")
        commands = parameters.get("commands", [])
        return {
            "success": True,
            "device_id": device_id,
            "executed_commands": len(commands),
            "status": "Commands executed successfully"
        }

    elif tool_name == "get_device_status":
        device_id = parameters.get("device_id")
        # Mock status
        return {
            "deviceId": device_id,
            "components": {
                "main": {
                    "switch": {"value": "on"},
                    "switchLevel": {"value": 75}
                }
            }
        }

    elif tool_name == "get_context_summary":
        return {
            "totalDevices": 15,
            "devicesByRoom": {
                "living room": {"count": 5, "types": ["light", "tv", "sensor"]},
                "bedroom": {"count": 4, "types": ["light", "ac", "sensor"]},
                "kitchen": {"count": 3, "types": ["light", "sensor"]},
            },
            "summary": "You have 15 devices across 3 rooms"
        }

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# MCP tool definitions (these would come from MCP server)
MCP_TOOLS = [
    {
        "name": "search_devices",
        "description": "Search for devices by natural language query",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "execute_commands",
        "description": "Execute commands on a device",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "commands": {"type": "array"}
            },
            "required": ["device_id", "commands"]
        }
    },
    {
        "name": "get_device_status",
        "description": "Get current status of a device",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"}
            },
            "required": ["device_id"]
        }
    },
    {
        "name": "get_context_summary",
        "description": "Get overview of all devices",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]


def main():
    """Main example"""

    # Check if API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Please set ANTHROPIC_API_KEY environment variable")
        print("   export ANTHROPIC_API_KEY='your-api-key'")
        return

    print("=" * 60)
    print("SmartThings Agent Example")
    print("=" * 60)

    # Initialize agent
    print("\n1. Initializing agent...")
    agent = SmartThingsAgent()
    agent.set_mcp_tools(MCP_TOOLS)
    print("✓ Agent initialized")

    # Example conversation
    conversation = [
        "我有哪些设备？",
        "打开客厅的灯",
        "把它调到50%",
        "现在状态如何？",
        "关闭卧室的空调"
    ]

    print("\n2. Starting conversation...\n")

    for i, user_message in enumerate(conversation, 1):
        print(f"\n{'='*60}")
        print(f"Turn {i}")
        print(f"{'='*60}")
        print(f"👤 User: {user_message}")

        try:
            # Process message
            response = agent.chat(user_message, mcp_executor=mock_mcp_executor)
            print(f"🤖 Agent: {response}")

            # Show context
            context = agent.get_context_summary()
            print(f"\n📊 Context:")
            print(f"   Turn: {context['conversation_turn']}")
            print(f"   Current room: {context['context']['current_room']}")
            print(f"   Devices in memory: {context['context']['devices_in_memory']}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Show final statistics
    print(f"\n{'='*60}")
    print("Final Statistics")
    print(f"{'='*60}")

    token_usage = agent.get_token_usage()
    print(f"\nToken Usage:")
    print(f"  Input tokens: {token_usage['total_input_tokens']}")
    print(f"  Output tokens: {token_usage['total_output_tokens']}")
    print(f"  Cache read tokens: {token_usage['cache_read_tokens']}")
    print(f"  Total tokens: {token_usage['total_tokens']}")

    context_summary = agent.context_manager.get_summary()
    print(f"\nConversation Context:")
    print(f"  Total turns: {context_summary['current_turn']}")
    print(f"  Devices remembered: {context_summary['devices_in_memory']}")
    for device in context_summary['device_list']:
        print(f"    - {device['name']} ({device['room']})")

    print(f"\n{'='*60}")
    print("Example completed!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # For demonstration without API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠️  This is a demonstration showing the agent architecture.")
        print("    To run with actual Claude AI, set ANTHROPIC_API_KEY.\n")
        print("Agent Components Created:")
        print("  ✓ Context Manager - tracks devices and conversation state")
        print("  ✓ Workflow Planner - recognizes intents and plans tool usage")
        print("  ✓ Error Handler - handles failures with fallback strategies")
        print("  ✓ Agent Client - orchestrates everything with Claude AI")
        print("\nRun test suite to see components in action:")
        print("  python test/test_agent.py")
    else:
        main()
