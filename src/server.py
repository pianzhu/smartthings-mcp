from datetime import datetime
from os import environ
from typing import List, Literal, Optional
from uuid import UUID
import logging
from mcp.types  import ToolAnnotations

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from api import (
    Attribute,
    CapabilitiesMode,
    Capability,
    Command,
    ComponentCategory,
    ConnectionType,
    Location,
)

load_dotenv()
token = environ.get("TOKEN")
if token is None:
    raise ValueError("TOKEN environment variable must be set")
location = Location(token)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create server
mcp = FastMCP("SmartThings", port=8001)


@mcp.tool(description="Get rooms UUID and names", annotations=ToolAnnotations(
    title="Get Smart Home Rooms",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False)
)
def get_rooms() -> dict[UUID, str]:
    return location.rooms


@mcp.tool(description="""
Retrieve devices based on specified filtering criteria.

Parameters:
- capability: Optional list of capabilities that devices must have (e.g., ['switch', 'temperatureMeasurement']).
- capabilities_mode: Defines how multiple capabilities are matched ('or' returns devices matching any capability, 'and' returns devices matching all specified capabilities). Default is 'or'.
- include_restricted: Include restricted devices in the results. Default is False.
- room_id: Filter devices by a specific room identifier.
- include_status: Include device status information in the response. Default is True.
- category: Filter devices by their component category.
- connection_type: Filter devices by their connection type (e.g., Wi-Fi, Zigbee).
""", annotations=ToolAnnotations(
    title="Get Smart Home Devices",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False)
)
def get_devices(
    capability: List[Capability] | None = None,
    capabilities_mode: CapabilitiesMode | None = 'or',
    include_restricted: bool = False,
    room_id: UUID | None = None,
    include_status: bool = True,
    category: ComponentCategory | None = None,
    connection_type: ConnectionType | None = None,
):
    """Get devices in the location"""
    return location.get_devices_short(**locals())


@mcp.tool(description="Get device status", annotations=ToolAnnotations(
    title="Get Device Status",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False)
)
def get_device_status(device_id: UUID):
    logger.info(f"Getting status for device {device_id}")
    return location.device_status(device_id)


@mcp.tool(description="Execute commands on a device", annotations=ToolAnnotations(
    title="Execute Device Commands",
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False)
)
def execute_commands(device_id: UUID, commands: List[Command]):
    """Send SmartThings commands to a device.
    Hints:
        first component of a device is usually 'main', but there might be 2-3 switches.

    """
    logger.info(f"Executing commands on device {device_id}: {commands}")
    return location.device_commands(device_id, commands)


@mcp.tool(description="Answer questions about past values or trends. Use ISO8601 Duration for `delta_start` and `delta_end` (e.g. P1D for 1 day, PT1H for 1 hour).",
          annotations=ToolAnnotations(
    title="Get Device History",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False)
    )
def get_device_history(
    *,
    device_id: Optional[UUID] = None,
    room_id:   Optional[UUID] = None,
    attribute: Attribute,
    delta_start: str,
    delta_end: str | None = None,
    granularity: Literal["realtime", "5min", "hourly", "daily"] = "hourly",
    aggregate:   Literal["raw", "sum", "avg", "min", "max"]   = "raw",
) -> List[dict]:
    """
    LLM-guidance
    ------------
    • Pick **one** of `device_id` or `room_id` (not both).  
      – `device_id` → history for that device only.  
      – `room_id`   → MCP auto-aggregates across devices in the room.  
    • Use when the user asks how something has changed *over time* or wants
      an average/graph for a past period.  
    • `metric` must match a path from *Get Device Status*  
      (e.g. "powerMeter.power", "temperature.value").  
    • Cap the returned set to ≲500 points; raise `granularity` as needed.
    • Use ISO8601 Duration for `delta_start` and `delta_end` (e.g. "P1D" for 1 day, "PT1H" for 1 hour).
    • If `delta_end` is not provided, it defaults to now.

    """
    return location.history(
        device_id=device_id,
        room_id=room_id,
        attribute=attribute,
        delta_start=delta_start,
        delta_end=delta_end,
        granularity=granularity,
        aggregate=aggregate,
    )

@mcp.tool(description="Get hub time")
def get_hub_time() -> str:
    """Get the current time of the hub."""
    now = datetime.now(location.timezone)
    return f"{now} Timezone: {location.timezone}"


@mcp.tool(
    description="""
Search devices by natural language query.

[FUNCTION]: Fuzzy search devices by label, room name, or capability

[WHEN TO USE]:
- User mentions room + device type (e.g., "客厅的灯", "卧室空调")
- Need to find specific device without knowing ID
- First time user mentions a device

[DO NOT USE]:
- When device_id is already known from previous conversation
- For "list all devices" requests (use get_context_summary instead)
- When user asks for statistics only

[EXAMPLE]:
User: "打开客厅的灯"
Step 1: search_devices("客厅 灯") → Returns [{id, name, room, type, fullId}]
Step 2: execute_commands(fullId, [...])

[OUTPUT FORMAT]:
List of up to 5 devices with minimal info: {id, name, room, type, fullId}
Sorted by relevance score.
""",
    annotations=ToolAnnotations(
        title="Search Devices",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def search_devices(query: str, limit: int = 5) -> List[dict]:
    """
    Search devices by natural language query.
    Returns minimal information to reduce token usage.
    """
    logger.info(f"Searching devices with query: {query}, limit: {limit}")
    return location.search_devices(query, limit)


@mcp.tool(
    description="""
Get available commands and attributes for a device capability.

[FUNCTION]: Retrieve supported commands for a specific device capability

[WHEN TO USE]:
- Before calling execute_commands with unfamiliar commands
- To verify what commands a device supports
- To check current attribute values for a capability

[DO NOT USE]:
- When you already know the device supports the command
- For simple on/off switches (assume "on" and "off" work)

[EXAMPLE]:
User: "Can I dim the living room light?"
Step 1: search_devices("客厅 灯") → device_id
Step 2: get_device_commands(device_id, "switchLevel") → {commands: ["setLevel"], ...}
Step 3: execute_commands(device_id, [{capability: "switchLevel", command: "setLevel", arguments: [50]}])

[OUTPUT FORMAT]:
{
    "component": "main",
    "capability": "switch",
    "commands": ["on", "off"],
    "attributes": {...}
}
""",
    annotations=ToolAnnotations(
        title="Get Device Commands",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def get_device_commands(device_id: UUID, capability: Capability) -> dict:
    """
    Get available commands and attributes for a device capability.
    Use this BEFORE calling execute_commands to avoid errors.
    """
    logger.info(f"Getting commands for device {device_id}, capability {capability}")
    return location.get_device_commands(device_id, capability)


@mcp.tool(
    description="""
Get a high-level summary of the smart home setup.

[FUNCTION]: Returns ultra-compressed overview of all rooms and devices

[WHEN TO USE]:
- At the START of a conversation to understand the environment
- When user asks "what devices do I have?"
- When user asks for overall statistics

[DO NOT USE]:
- When user asks about a specific device (use search_devices)
- When detailed device info is needed (use get_devices or get_device_status)

[EXAMPLE]:
User: "What's in my home?"
Step 1: get_context_summary() → {rooms: {...}, statistics: {...}}
Response: "You have 22 devices across 5 rooms..."

[OUTPUT FORMAT]:
{
    "rooms": {
        "living_room": {"device_count": 8, "types": ["switch", "sensor"]},
        ...
    },
    "statistics": {
        "total_devices": 22,
        "by_type": {"switch": 10, "sensor": 8, ...}
    },
    "hub_time": "2025-11-12 10:30:00 UTC+8"
}

Token usage: ~50 tokens (vs ~5000 for get_devices())
""",
    annotations=ToolAnnotations(
        title="Get Context Summary",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def get_context_summary() -> dict:
    """
    Get a high-level summary of the smart home setup.
    Use this at the START of a conversation to understand the environment.
    """
    logger.info("Getting context summary")
    return location.get_context_summary()


@mcp.tool(
    description="""
Execute commands on multiple devices in a single call.

[FUNCTION]: Batch execution of commands (requires device_id)

[INPUT FORMAT]:
Only accepts device_id + commands:
[
    {"device_id": "xxx-uuid", "commands": [...]},
    {"device_id": "yyy-uuid", "commands": [...]}
]

[IMPORTANT - MULTI-OPERATION STRATEGY]:

When user requests multiple operations, YOU must orchestrate tool calls:

Strategy 1: Few operations (2-3 devices) → PARALLEL calls
Example: "打开客厅的灯，关闭卧室的空调，锁上前门"

Round 1: Call search_devices 3x IN PARALLEL
  <tool_use id="1">search_devices("客厅 灯")</tool_use>
  <tool_use id="2">search_devices("卧室 空调")</tool_use>
  <tool_use id="3">search_devices("前门")</tool_use>

Round 2: Call execute_commands 3x IN PARALLEL (or use batch)
  <tool_use id="4">execute_commands(device_id_1, [...])</tool_use>
  <tool_use id="5">execute_commands(device_id_2, [...])</tool_use>
  <tool_use id="6">execute_commands(device_id_3, [...])</tool_use>

Result: 2 rounds, ~1500 tokens

Strategy 2: Many similar operations (4+ devices) → BATCH
Example: "关闭客厅所有的灯" (5 lights)

Round 1: Search once
  <tool_use id="1">search_devices("客厅 灯", limit=10)</tool_use>

Round 2: Batch execute with all device_ids
  <tool_use id="2">batch_execute_commands([
    {"device_id": "id1", "commands": [...]},
    {"device_id": "id2", "commands": [...]},
    {"device_id": "id3", "commands": [...]},
    {"device_id": "id4", "commands": [...]},
    {"device_id": "id5", "commands": [...]}
  ])</tool_use>

Result: 2 calls, ~800 tokens

[WHEN TO USE THIS TOOL]:
- 4+ devices need the same/similar commands
- Want atomic batch execution
- Already have all device_ids from search

[WHEN NOT TO USE]:
- Single device (use execute_commands)
- 2-3 diverse devices (parallel execute_commands is better)
- Don't have device_ids yet (call search_devices first!)

[EXAMPLE WORKFLOW]:
User: "Turn off all living room lights"

Step 1 (you call):
  search_devices("客厅 灯", limit=10)

Result: [
  {"fullId": "aaa-uuid", "name": "吸顶灯"},
  {"fullId": "bbb-uuid", "name": "台灯1"},
  {"fullId": "ccc-uuid", "name": "台灯2"}
]

Step 2 (you call):
  batch_execute_commands([
    {"device_id": "aaa-uuid", "commands": [{"capability": "switch", "command": "off"}]},
    {"device_id": "bbb-uuid", "commands": [{"capability": "switch", "command": "off"}]},
    {"device_id": "ccc-uuid", "commands": [{"capability": "switch", "command": "off"}]}
  ])

[OUTPUT FORMAT]:
{
    "total": 3,
    "success": 3,
    "failed": 0,
    "results": [
        {"device_id": "aaa-uuid", "status": "success", "details": {...}},
        {"device_id": "bbb-uuid", "status": "success", "details": {...}},
        {"device_id": "ccc-uuid", "status": "success", "details": {...}}
    ]
}
""",
    annotations=ToolAnnotations(
        title="Batch Execute Commands",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False
    )
)
def batch_execute_commands(operations: List[dict]) -> dict:
    """
    Execute commands on multiple devices.
    Requires device_id for each operation.
    """
    logger.info(f"Batch executing commands on {len(operations)} devices")
    return location.batch_execute_commands(operations)


if __name__ == "__main__":
    """Run the FastMCP server."""
    mcp.run(transport="sse")

