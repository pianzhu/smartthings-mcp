# Agent 与 MCP 工具的参数传递机制

## 概览

SmartThings Agent 通过 Claude AI 作为中介来调用 MCP 工具。参数传递流程如下：

```
User Input → Agent → Claude API → Tool Use → MCP Executor → MCP Server → Tool Result → Agent → User
```

## 详细流程

### 1. 工具定义阶段

**MCP Server** (`src/server.py`) 定义工具和参数：

```python
@mcp.tool(
    description="""Search devices by natural language query...""",
    annotations=ToolAnnotations(...)
)
def search_devices(query: str, limit: int = 5) -> List[dict]:
    """Search devices by natural language query."""
    logger.info(f"Searching devices with query: {query}, limit: {limit}")
    return location.search_devices(query, limit)
```

FastMCP 自动将这个函数签名转换为 Anthropic Tool Schema：

```json
{
  "name": "search_devices",
  "description": "Search devices by natural language query...",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language search query"
      },
      "limit": {
        "type": "integer",
        "default": 5,
        "description": "Maximum number of results"
      }
    },
    "required": ["query"]
  }
}
```

### 2. Agent 初始化阶段

**Agent Client** (`src/agent/client.py`) 接收工具定义：

```python
agent = SmartThingsAgent(
    api_key="your-api-key",
    model="claude-sonnet-4-5-20250929",
    mcp_tools=[...tool_schemas...]  # ← 工具定义列表
)
```

或者通过 `set_mcp_tools()` 方法：

```python
agent.set_mcp_tools(tools)
```

### 3. 用户请求处理

用户发送自然语言请求：

```python
response = agent.chat("打开客厅的灯", mcp_executor=execute_mcp_tool)
```

**Agent 的处理流程**：

```python
# src/agent/client.py: chat()
def chat(self, user_message: str, mcp_executor: Optional[callable] = None) -> str:
    # 1. 添加用户消息到对话历史
    self.messages.append({"role": "user", "content": user_message})

    # 2. 调用 Claude API
    response = self._call_claude_api()

    # 3. 处理 Claude 的响应
    assistant_message = self._process_claude_response(response, mcp_executor)

    return assistant_message
```

### 4. Claude API 调用

**Agent 将工具定义传递给 Claude**：

```python
# src/agent/client.py: _call_claude_api()
def _call_claude_api(self) -> Any:
    kwargs = {
        "model": self.model,
        "max_tokens": 4096,
        "system": system_messages,
        "messages": self.messages,
    }

    # 添加工具定义
    if self.mcp_tools:
        kwargs["tools"] = self.mcp_tools  # ← 工具 schema 列表

    response = self.client.messages.create(**kwargs)
    return response
```

**Claude 接收到**：
- 用户消息: "打开客厅的灯"
- 可用工具: `search_devices`, `execute_commands`, etc.
- 系统提示: AGENT_SYSTEM_PROMPT（包含工具使用指南）

### 5. Claude 决定使用工具

Claude AI 分析请求后决定使用工具，返回 `tool_use` 响应：

```python
{
  "stop_reason": "tool_use",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_01ABC123",
      "name": "search_devices",
      "input": {                    # ← Claude 生成的参数
        "query": "客厅 灯",
        "limit": 5
      }
    }
  ]
}
```

**关键点**: Claude AI 根据：
- 用户的自然语言输入
- 工具的 `description` 和 `input_schema`
- System prompt 中的指导

来**自动生成合适的参数值**。

### 6. Agent 执行工具调用

**Agent 提取工具调用信息并执行**：

```python
# src/agent/client.py: _process_claude_response()
def _process_claude_response(self, response, mcp_executor):
    if response.stop_reason == "tool_use":
        # 提取所有工具调用
        tool_uses = [block for block in response.content if block.type == "tool_use"]

        for tool_use in tool_uses:
            # 调用 MCP executor
            result = mcp_executor(
                tool_use.name,    # ← 工具名称: "search_devices"
                tool_use.input    # ← 参数字典: {"query": "客厅 灯", "limit": 5}
            )

            # 收集结果
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result)
            })
```

### 7. MCP Executor 调用实际工具

**MCP Executor** 是用户提供的函数，负责实际调用 MCP server：

```python
def mcp_executor(tool_name: str, parameters: dict) -> Any:
    """
    执行 MCP 工具

    Args:
        tool_name: 工具名称，如 "search_devices"
        parameters: 参数字典，如 {"query": "客厅 灯", "limit": 5}

    Returns:
        工具执行结果
    """
    # 方式 1: 直接调用 MCP server 函数
    if tool_name == "search_devices":
        return search_devices(**parameters)  # ← 展开参数字典

    elif tool_name == "execute_commands":
        return execute_commands(**parameters)

    # 方式 2: 通过 MCP 客户端调用
    # return mcp_client.call_tool(tool_name, parameters)
```

### 8. MCP Server 执行工具

**MCP Server 接收参数并执行**：

```python
# src/server.py
def search_devices(query: str, limit: int = 5) -> List[dict]:
    """
    参数由 MCP executor 传入
    """
    logger.info(f"Searching devices with query: {query}, limit: {limit}")
    return location.search_devices(query, limit)
```

### 9. 结果返回给 Agent

工具执行结果返回给 Agent：

```python
result = [
    {
        "id": "abc123",
        "fullId": "full-uuid-abc123",
        "name": "客厅吸顶灯",
        "room": "客厅",
        "type": "switch",
        "capabilities": ["switch", "switchLevel"],
        "relevance_score": 15.0
    }
]
```

Agent 将结果转换为工具结果消息：

```python
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01ABC123",
            "content": '[{"id": "abc123", "name": "客厅吸顶灯", ...}]'
        }
    ]
}
```

### 10. 继续对话获取最终响应

Agent 将工具结果添加到对话历史，再次调用 Claude：

```python
# 对话历史现在包含：
# 1. User: "打开客厅的灯"
# 2. Assistant: [tool_use: search_devices]
# 3. User: [tool_result: 找到客厅吸顶灯]

# Claude 继续决定下一步
final_response = self._call_claude_api()
# Claude 可能会：
# - 调用 execute_commands 工具
# - 返回文本响应
```

## 完整示例

### 用户请求: "打开客厅的灯"

```python
# 1. 用户调用
response = agent.chat("打开客厅的灯", mcp_executor=execute_mcp_tool)

# 2. Agent → Claude (第一次调用)
# messages = [{"role": "user", "content": "打开客厅的灯"}]
# tools = [search_devices_schema, execute_commands_schema, ...]

# 3. Claude → Agent (工具使用)
# {
#   "stop_reason": "tool_use",
#   "content": [{
#     "type": "tool_use",
#     "name": "search_devices",
#     "input": {"query": "客厅 灯", "limit": 5}
#   }]
# }

# 4. Agent → MCP Executor
result = mcp_executor("search_devices", {"query": "客厅 灯", "limit": 5})
# result = [{"id": "abc123", "name": "客厅吸顶灯", ...}]

# 5. Agent → Claude (第二次调用，带工具结果)
# messages = [
#   {"role": "user", "content": "打开客厅的灯"},
#   {"role": "assistant", "content": [tool_use]},
#   {"role": "user", "content": [tool_result]}
# ]

# 6. Claude → Agent (继续使用工具)
# {
#   "stop_reason": "tool_use",
#   "content": [{
#     "type": "tool_use",
#     "name": "execute_commands",
#     "input": {
#       "device_id": "full-uuid-abc123",
#       "commands": [{
#         "component": "main",
#         "capability": "switch",
#         "command": "on"
#       }]
#     }
#   }]
# }

# 7. Agent → MCP Executor
result = mcp_executor("execute_commands", {
    "device_id": "full-uuid-abc123",
    "commands": [...]
})
# result = {"status": "ACCEPTED"}

# 8. Agent → Claude (第三次调用，带第二个工具结果)
# Claude 返回最终文本响应

# 9. Agent → User
# "已成功打开客厅吸顶灯"
```

## 参数传递的关键点

### 1. **Claude AI 是参数生成器**

Agent 不直接生成参数。Claude AI 根据：
- 用户的自然语言输入
- 工具的 schema 定义
- System prompt 指导

来智能生成参数。

### 2. **工具 Schema 的重要性**

工具定义中的 `description` 和 `input_schema` 非常重要：

```python
@mcp.tool(description="""
Clear description of what the tool does.

[WHEN TO USE]:
- Specific scenarios

[EXAMPLE]:
User: "打开客厅的灯"
Step 1: search_devices("客厅 灯")
""")
def search_devices(query: str, limit: int = 5):
    pass
```

好的 description 帮助 Claude 正确生成参数。

### 3. **Type Hints 自动转换为 Schema**

FastMCP 自动将 Python type hints 转换为 JSON Schema：

```python
def search_devices(
    query: str,           # → {"type": "string"}
    limit: int = 5        # → {"type": "integer", "default": 5}
) -> List[dict]:          # → 返回类型文档
```

### 4. **MCP Executor 的职责**

MCP Executor 是连接 Agent 和 MCP Server 的桥梁：

```python
def mcp_executor(tool_name: str, parameters: dict) -> Any:
    """
    职责：
    1. 接收 Claude 生成的工具名和参数
    2. 调用实际的 MCP server 工具
    3. 返回执行结果
    """
    # 参数已经由 Claude 生成好了
    # 直接调用对应的工具即可
    return call_mcp_tool(tool_name, **parameters)
```

### 5. **参数验证**

参数验证发生在多个层次：

1. **Claude API**: 验证参数符合 tool schema
2. **MCP Server**: Python 类型检查（运行时）
3. **实际 API**: SmartThings API 验证

## 自定义 MCP Executor 示例

### 简单版本

```python
from src.server import search_devices, execute_commands, get_device_commands

def simple_mcp_executor(tool_name: str, parameters: dict):
    """直接调用本地 MCP 工具"""
    tools = {
        "search_devices": search_devices,
        "execute_commands": execute_commands,
        "get_device_commands": get_device_commands,
    }

    if tool_name in tools:
        return tools[tool_name](**parameters)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

# 使用
agent.chat("打开客厅的灯", mcp_executor=simple_mcp_executor)
```

### 带日志和错误处理

```python
import logging

logger = logging.getLogger(__name__)

def robust_mcp_executor(tool_name: str, parameters: dict):
    """带日志和错误处理的 MCP executor"""
    logger.info(f"Executing tool: {tool_name}")
    logger.debug(f"Parameters: {parameters}")

    try:
        tools = {
            "search_devices": search_devices,
            "execute_commands": execute_commands,
            "get_device_commands": get_device_commands,
        }

        if tool_name not in tools:
            return {"error": f"Unknown tool: {tool_name}"}

        result = tools[tool_name](**parameters)
        logger.info(f"Tool executed successfully: {tool_name}")
        return result

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {"error": str(e)}

# 使用
agent.chat("打开客厅的灯", mcp_executor=robust_mcp_executor)
```

### 通过 MCP 客户端（远程调用）

```python
from mcp import ClientSession

async def remote_mcp_executor(tool_name: str, parameters: dict):
    """通过 MCP 客户端远程调用工具"""
    async with ClientSession(server_url="http://localhost:8001") as session:
        result = await session.call_tool(tool_name, parameters)
        return result

# 使用（需要 async）
import asyncio
asyncio.run(agent.chat("打开客厅的灯", mcp_executor=remote_mcp_executor))
```

## 调试参数传递

### 查看 Claude 生成的参数

在 `_process_claude_response` 中添加日志：

```python
for tool_use in tool_uses:
    logger.info(f"Tool: {tool_use.name}")
    logger.info(f"Parameters: {json.dumps(tool_use.input, indent=2)}")

    result = mcp_executor(tool_use.name, tool_use.input)
```

### 查看工具执行结果

```python
result = mcp_executor(tool_use.name, tool_use.input)
logger.info(f"Result: {json.dumps(result, indent=2)}")
```

### 完整调试示例

```python
def debug_mcp_executor(tool_name: str, parameters: dict):
    """调试版本的 executor"""
    print(f"\n{'='*60}")
    print(f"🔧 Tool Call: {tool_name}")
    print(f"{'='*60}")
    print(f"📥 Parameters:")
    print(json.dumps(parameters, indent=2, ensure_ascii=False))

    # 执行工具
    result = tools[tool_name](**parameters)

    print(f"\n📤 Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"{'='*60}\n")

    return result
```

## 总结

参数传递流程的核心特点：

1. **声明式**: 通过 tool schema 声明参数类型和约束
2. **智能生成**: Claude AI 自动从自然语言生成参数
3. **类型安全**: Python type hints + JSON Schema 双重验证
4. **解耦设计**: Agent ↔ Claude ↔ MCP Server 各层分离
5. **灵活执行**: MCP executor 可以是本地或远程调用

这种设计的优点：
- ✅ Agent 不需要硬编码参数生成逻辑
- ✅ Claude 负责理解用户意图并生成参数
- ✅ MCP Server 专注于工具实现
- ✅ 易于添加新工具（只需定义 schema）
- ✅ 支持复杂的多轮工具调用
