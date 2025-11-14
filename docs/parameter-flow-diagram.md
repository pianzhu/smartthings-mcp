# Agent-MCP 参数传递流程图

## 整体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          用户应用层                                   │
│                                                                      │
│  user_input = "打开客厅的灯"                                         │
│  response = agent.chat(user_input, mcp_executor=execute_tool)       │
│                                                                      │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      SmartThings Agent                               │
│                    (src/agent/client.py)                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  1. 接收用户消息                                             │    │
│  │     messages.append({"role": "user", "content": user_input})│    │
│  └────────────────────────────────────────────────────────────┘    │
│                            │                                         │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │  2. 准备 Claude API 请求                                     │   │
│  │     kwargs = {                                               │   │
│  │       "model": "claude-sonnet-4-5",                          │   │
│  │       "messages": self.messages,                             │   │
│  │       "tools": self.mcp_tools  ← 工具 schema 列表            │   │
│  │     }                                                         │   │
│  └────────────────────────┬─────────────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Claude API                                    │
│                   (Anthropic Service)                                │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  接收的输入:                                                 │    │
│  │  - User message: "打开客厅的灯"                              │    │
│  │  - Available tools: [search_devices, execute_commands, ...] │    │
│  │  - System prompt: AGENT_SYSTEM_PROMPT                       │    │
│  └────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │  3. AI 推理                                                  │   │
│  │     分析: "用户想打开灯"                                      │   │
│  │     需要: 1) 先搜索设备 2) 然后执行命令                      │   │
│  │     工具选择: search_devices                                 │   │
│  │     参数生成: {"query": "客厅 灯", "limit": 5}               │   │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                            │                                         │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │  返回 tool_use 响应:                                         │   │
│  │  {                                                           │   │
│  │    "stop_reason": "tool_use",                                │   │
│  │    "content": [{                                             │   │
│  │      "type": "tool_use",                                     │   │
│  │      "id": "toolu_01ABC",                                    │   │
│  │      "name": "search_devices",                               │   │
│  │      "input": {                                              │   │
│  │        "query": "客厅 灯",  ← Claude 生成的参数              │   │
│  │        "limit": 5                                            │   │
│  │      }                                                        │   │
│  │    }]                                                         │   │
│  │  }                                                           │   │
│  └────────────────────────┬─────────────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      SmartThings Agent                               │
│                    (src/agent/client.py)                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  4. 处理 tool_use 响应                                       │    │
│  │     tool_uses = extract_tool_uses(response)                 │    │
│  │                                                              │    │
│  │     for tool_use in tool_uses:                              │    │
│  │       tool_name = tool_use.name      # "search_devices"     │    │
│  │       parameters = tool_use.input    # {"query": "客厅 灯"}  │    │
│  │                                                              │    │
│  │       # 调用 MCP executor                                    │    │
│  │       result = mcp_executor(tool_name, parameters) ──────┐  │    │
│  └──────────────────────────────────────────────────────────┼──┘    │
└─────────────────────────────────────────────────────────────┼────────┘
                                                              │
                                                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       MCP Executor                                   │
│                   (用户提供的函数)                                    │
│                                                                      │
│  def mcp_executor(tool_name: str, parameters: dict):                │
│      """                                                             │
│      参数已由 Claude 生成，直接传递给 MCP server                     │
│      """                                                             │
│      if tool_name == "search_devices":                              │
│          return search_devices(**parameters)  ────────────────┐     │
│                                                                │     │
│      elif tool_name == "execute_commands":                    │     │
│          return execute_commands(**parameters)                │     │
└───────────────────────────────────────────────────────────────┼─────┘
                                                                │
                                                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        MCP Server                                    │
│                      (src/server.py)                                 │
│                                                                      │
│  @mcp.tool(description="...")                                       │
│  def search_devices(query: str, limit: int = 5) -> List[dict]:     │
│      """                                                             │
│      参数直接接收:                                                   │
│      - query = "客厅 灯"   ← 从 Claude 生成的参数                    │
│      - limit = 5                                                     │
│      """                                                             │
│      logger.info(f"Searching: {query}, limit: {limit}")            │
│      return location.search_devices(query, limit)  ──────────┐     │
│                                                                │     │
└────────────────────────────────────────────────────────────────┼────┘
                                                                 │
                                                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    SmartThings API                                   │
│                     (api.Location)                                   │
│                                                                      │
│  def search_devices(self, query: str, limit: int):                 │
│      # 实际的设备搜索逻辑                                            │
│      devices = self._semantic_search(query)                         │
│      return devices[:limit]                                         │
│                                                                      │
│  返回结果: [                                                         │
│    {                                                                 │
│      "id": "abc123",                                                │
│      "fullId": "uuid-abc123",                                       │
│      "name": "客厅吸顶灯",                                           │
│      "room": "客厅",                                                 │
│      "type": "switch",                                               │
│      "capabilities": ["switch", "switchLevel"]                      │
│    }                                                                 │
│  ]                                                                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
        结果逐层返回               │
                                 ▼
                    ┌────────────────────────┐
                    │   MCP Server           │
                    │   返回结果给 executor   │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   MCP Executor         │
                    │   返回结果给 Agent      │
                    └────────────┬───────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      SmartThings Agent                               │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  5. 收集工具结果                                             │    │
│  │     tool_results.append({                                   │    │
│  │       "type": "tool_result",                                │    │
│  │       "tool_use_id": "toolu_01ABC",                         │    │
│  │       "content": json.dumps([{                              │    │
│  │         "id": "abc123",                                      │    │
│  │         "name": "客厅吸顶灯",                                 │    │
│  │         ...                                                  │    │
│  │       }])                                                    │    │
│  │     })                                                       │    │
│  └────────────────────────────────────────────────────────────┘    │
│                            │                                         │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │  6. 将工具结果添加到对话历史                                 │   │
│  │     messages.append({"role": "assistant", "content": ...})  │   │
│  │     messages.append({"role": "user", "content": tool_results})│  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                            │                                         │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │  7. 继续调用 Claude API (获取最终响应)                      │   │
│  │     final_response = self._call_claude_api()                │   │
│  └────────────────────────┬─────────────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Claude API                                    │
│                                                                      │
│  接收对话历史:                                                       │
│  1. User: "打开客厅的灯"                                             │
│  2. Assistant: [tool_use: search_devices]                           │
│  3. User: [tool_result: 找到客厅吸顶灯]                             │
│                                                                      │
│  继续推理:                                                           │
│  - 已找到设备: 客厅吸顶灯 (id: abc123)                              │
│  - 需要执行命令: 打开 (switch.on)                                   │
│  - 使用工具: execute_commands                                       │
│                                                                      │
│  返回第二个 tool_use:                                                │
│  {                                                                   │
│    "stop_reason": "tool_use",                                       │
│    "content": [{                                                     │
│      "type": "tool_use",                                             │
│      "name": "execute_commands",                                     │
│      "input": {                                                      │
│        "device_id": "uuid-abc123",                                  │
│        "commands": [{                                                │
│          "component": "main",                                        │
│          "capability": "switch",                                     │
│          "command": "on"                                             │
│        }]                                                            │
│      }                                                               │
│    }]                                                                │
│  }                                                                   │
└────────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
             (重复步骤 4-7，执行 execute_commands)
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Claude API                                    │
│                   (第三次调用，返回最终文本)                         │
│                                                                      │
│  接收对话历史:                                                       │
│  1. User: "打开客厅的灯"                                             │
│  2. Assistant: [tool_use: search_devices]                           │
│  3. User: [tool_result: 找到客厅吸顶灯]                             │
│  4. Assistant: [tool_use: execute_commands]                         │
│  5. User: [tool_result: {"status": "ACCEPTED"}]                    │
│                                                                      │
│  最终响应:                                                           │
│  {                                                                   │
│    "stop_reason": "end_turn",                                       │
│    "content": [{                                                     │
│      "type": "text",                                                 │
│      "text": "已成功打开客厅吸顶灯"                                  │
│    }]                                                                │
│  }                                                                   │
└────────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      SmartThings Agent                               │
│                                                                      │
│  返回文本响应给用户: "已成功打开客厅吸顶灯"                           │
└────────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          用户应用层                                   │
│                                                                      │
│  print(response)  # "已成功打开客厅吸顶灯"                           │
└──────────────────────────────────────────────────────────────────────┘
```

## 参数生成的关键点

### Claude 如何生成参数？

```
┌─────────────────────────────────────────────────────────────┐
│                   Claude AI 参数生成过程                    │
└─────────────────────────────────────────────────────────────┘

输入:
  1. 用户消息: "打开客厅的灯"
  2. 工具定义 (Tool Schema):
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
             "default": 5
           }
         },
         "required": ["query"]
       }
     }
  3. System Prompt:
     "When user mentions a device location and type, use search_devices
      with a query combining both (e.g., '客厅 灯')..."

推理过程:
  ┌──────────────────────────────────────┐
  │ 1. 意图识别                           │
  │    "打开" → 控制设备                  │
  │    "客厅的灯" → 需要找到设备          │
  └──────────────┬───────────────────────┘
                 │
  ┌──────────────▼───────────────────────┐
  │ 2. 工具选择                           │
  │    需要先找到设备 → search_devices    │
  └──────────────┬───────────────────────┘
                 │
  ┌──────────────▼───────────────────────┐
  │ 3. 参数提取                           │
  │    从 "客厅的灯" 提取:                │
  │    - 房间: "客厅"                     │
  │    - 设备类型: "灯"                   │
  └──────────────┬───────────────────────┘
                 │
  ┌──────────────▼───────────────────────┐
  │ 4. 参数格式化                         │
  │    根据 input_schema:                 │
  │    query (string, required)           │
  │    limit (integer, default=5)         │
  └──────────────┬───────────────────────┘
                 │
  ┌──────────────▼───────────────────────┐
  │ 5. 生成参数                           │
  │    {                                  │
  │      "query": "客厅 灯",              │
  │      "limit": 5                       │
  │    }                                  │
  └───────────────────────────────────────┘

输出:
  tool_use 对象，包含工具名和生成的参数
```

## 工具定义到参数生成的映射

### 示例 1: search_devices

```python
# MCP Server 定义
@mcp.tool(description="Search devices by natural language query...")
def search_devices(query: str, limit: int = 5) -> List[dict]:
    pass

# FastMCP 自动生成的 Tool Schema
{
  "name": "search_devices",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},      # ← 从 query: str
      "limit": {"type": "integer"}      # ← 从 limit: int = 5
    },
    "required": ["query"]               # ← 没有默认值 = required
  }
}

# Claude 看到用户输入 "打开客厅的灯"
# 生成的参数:
{
  "query": "客厅 灯",    # ← 智能提取关键词
  "limit": 5             # ← 使用默认值
}
```

### 示例 2: execute_commands

```python
# MCP Server 定义
@mcp.tool(description="Execute commands on a device...")
def execute_commands(
    device_id: str,
    commands: List[dict]
) -> dict:
    pass

# Tool Schema
{
  "name": "execute_commands",
  "input_schema": {
    "type": "object",
    "properties": {
      "device_id": {"type": "string"},
      "commands": {
        "type": "array",
        "items": {"type": "object"}
      }
    },
    "required": ["device_id", "commands"]
  }
}

# Claude 在得到 search_devices 结果后
# 已知设备 ID: "uuid-abc123"
# 用户请求: "打开"
# 生成的参数:
{
  "device_id": "uuid-abc123",  # ← 从工具结果获取
  "commands": [{                # ← 根据 "打开" 生成
    "component": "main",
    "capability": "switch",
    "command": "on"
  }]
}
```

### 示例 3: interpret_command (带复杂参数)

```python
# MCP Server 定义
@mcp.tool(description="Interpret ambiguous natural language commands...")
def interpret_command(
    user_input: str,
    device_capabilities: List[str],
    current_state: Optional[dict] = None
) -> dict:
    pass

# Tool Schema
{
  "name": "interpret_command",
  "input_schema": {
    "type": "object",
    "properties": {
      "user_input": {"type": "string"},
      "device_capabilities": {
        "type": "array",
        "items": {"type": "string"}
      },
      "current_state": {
        "type": "object",
        "nullable": true     # ← Optional[dict]
      }
    },
    "required": ["user_input", "device_capabilities"]
  }
}

# Claude 看到用户输入 "让灯光柔和一些"
# 从 search_devices 结果知道设备有 ["switch", "switchLevel"]
# 生成的参数:
{
  "user_input": "柔和一些",
  "device_capabilities": ["switch", "switchLevel"],
  "current_state": null    # ← Optional 参数可以为 null
}
```

## 参数传递中的数据转换

```
Python Type Hints
       ↓
FastMCP 自动转换
       ↓
JSON Schema
       ↓
发送到 Claude API
       ↓
Claude 生成参数 (JSON)
       ↓
Agent 接收 (Python dict)
       ↓
MCP Executor 传递
       ↓
MCP Server 接收
       ↓
Python 类型检查
       ↓
执行函数
```

### 类型映射表

| Python Type | JSON Schema Type | 示例值 |
|-------------|------------------|--------|
| `str` | `"string"` | `"客厅 灯"` |
| `int` | `"integer"` | `5` |
| `float` | `"number"` | `24.5` |
| `bool` | `"boolean"` | `true` |
| `List[str]` | `{"type": "array", "items": {"type": "string"}}` | `["switch", "lock"]` |
| `dict` / `Dict` | `"object"` | `{"key": "value"}` |
| `Optional[str]` | `{"type": "string", "nullable": true}` | `"value"` or `null` |
| `Literal["on", "off"]` | `{"type": "string", "enum": ["on", "off"]}` | `"on"` |

## 总结

参数传递的本质：

1. **工具作者** (MCP Server): 定义参数类型和约束
2. **Claude AI**: 从自然语言生成符合约束的参数值
3. **MCP Executor**: 简单地传递参数（不需要修改）
4. **MCP Server**: 接收并执行

关键优势：
- ✅ 无需编写参数解析逻辑
- ✅ Claude 处理自然语言理解
- ✅ 类型安全自动保证
- ✅ 易于扩展新工具
