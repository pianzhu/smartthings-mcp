# 大模型工具规划策略与架构设计

## 核心挑战

大模型在使用工具时面临的主要问题：

1. **工具选择困难** - 多个工具可能完成相同任务，如何选择最优路径？
2. **顺序规划** - 复杂任务需要多步骤，如何规划执行顺序？
3. **上下文爆炸** - 每次工具调用都会增加上下文，如何控制？
4. **错误恢复** - 工具调用失败时如何优雅处理？

---

## 系统架构设计

### 三层架构模型

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Context Layer (Cached)                       │
│  ┌────────────────────────────────────────────────┐    │
│  │ - System Prompt (工作原则、禁止行为)           │    │
│  │ - Static Context (房间列表、能力类型)          │    │
│  │ - Tool Descriptions (工具使用指南)             │    │
│  └────────────────────────────────────────────────┘    │
│  Token: ~2000 | Cache Hit Rate: 95%                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Planning Layer (Dynamic)                     │
│  ┌────────────────────────────────────────────────┐    │
│  │ 1. Intent Recognition (意图识别)               │    │
│  │    - 控制 / 查询 / 分析                        │    │
│  │                                                 │    │
│  │ 2. Device Location (设备定位)                  │    │
│  │    - search_devices(query)                     │    │
│  │    - 或使用缓存的 device_id                    │    │
│  │                                                 │    │
│  │ 3. Task Decomposition (任务分解)               │    │
│  │    - 单步 vs 多步                              │    │
│  │    - 串行 vs 并行                              │    │
│  └────────────────────────────────────────────────┘    │
│  Token: ~500-1000                                       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Execution Layer (Transient)                  │
│  ┌────────────────────────────────────────────────┐    │
│  │ 1. Pre-Execution (执行前验证)                  │    │
│  │    - get_device_commands (可选)                │    │
│  │    - get_device_status (条件控制时)            │    │
│  │                                                 │    │
│  │ 2. Execution (执行)                             │    │
│  │    - execute_commands / batch_execute          │    │
│  │                                                 │    │
│  │ 3. Post-Execution (执行后确认)                 │    │
│  │    - 验证结果                                   │    │
│  │    - 简化返回信息                               │    │
│  └────────────────────────────────────────────────┘    │
│  Token: ~500-1500 | Discarded after confirmation       │
└─────────────────────────────────────────────────────────┘
```

---

## Prompt Engineering 策略

### 1. 系统提示词设计

在 `src/server.py` 中添加：

```python
AGENT_SYSTEM_PROMPT = """
You are a smart home assistant with access to SmartThings devices.

🎯 CORE PRINCIPLES:

1. MINIMAL INFORMATION PRINCIPLE
   - NEVER call get_devices() without filters
   - ALWAYS use search_devices(query) to locate devices
   - ONLY query status when necessary

2. EFFICIENT WORKFLOW
   - Simple control: search_devices → execute_commands
   - Conditional control: search_devices → get_device_status → (conditional) execute_commands
   - Data analysis: search_devices → get_device_history

3. CONTEXT MANAGEMENT
   - Remember device IDs mentioned in conversation
   - Reuse IDs instead of re-searching
   - Clear detailed status after task completion

4. ERROR PREVENTION
   - Use get_device_commands before executing unknown commands
   - Validate parameters before execution
   - Provide clear error messages to users

❌ PROHIBITED BEHAVIORS:

- Do NOT guess command parameters
- Do NOT repeatedly query the same device status
- Do NOT return complete device lists to users
- Do NOT use get_devices() for exploration (use get_context_summary instead)

📋 TOOL SELECTION GUIDE:

Starting a conversation?
  → get_context_summary()

User mentions a device/room?
  → search_devices(query)

Need to control a device?
  → Already have device_id? → execute_commands()
  → Don't know device_id? → search_devices() → execute_commands()

Need historical data?
  → search_devices() → get_device_history()

Uncertain about commands?
  → get_device_commands(device_id, capability)

🔄 MULTI-TURN OPTIMIZATION:

Turn 1: User: "客厅的灯在哪？"
  → search_devices("客厅 灯") → Return device info
  → REMEMBER: device_id = "abc123"

Turn 2: User: "把它打开"
  → USE CACHED: device_id = "abc123"
  → execute_commands(device_id, ...)
  → DO NOT re-search

Turn 3: User: "现在状态如何？"
  → USE CACHED: device_id = "abc123"
  → get_device_status(device_id)
"""

# 在 FastMCP 初始化时注入
mcp = FastMCP("SmartThings", port=8001)
# 如果 FastMCP 支持系统提示，添加：
# mcp.set_system_prompt(AGENT_SYSTEM_PROMPT)
```

### 2. 工具描述增强

每个工具的 `description` 必须包含：

```python
@mcp.tool(description="""
[FUNCTION]: Clear one-line description

[WHEN TO USE]:
- Scenario 1
- Scenario 2

[DO NOT USE]:
- Anti-pattern 1
- Anti-pattern 2

[EXAMPLE]:
Input: "Turn on living room light"
Flow: search_devices("living room light") → execute_commands(...)

[OUTPUT FORMAT]:
Brief description of return value structure
""")
def tool_name(...):
    pass
```

**实际示例**：

```python
@mcp.tool(description="""
[FUNCTION]: Search devices by natural language query

[WHEN TO USE]:
- User mentions room + device type (e.g., "客厅的灯", "卧室空调")
- First time encountering a device in conversation
- Need to find device without knowing ID

[DO NOT USE]:
- When device_id is already known from previous turns
- For "list all devices" requests (use get_context_summary instead)
- When user asks for statistics (use get_context_summary)

[EXAMPLE]:
User: "打开客厅的灯"
Step 1: search_devices("客厅 灯") → Returns device_id
Step 2: execute_commands(device_id, [Command("main", "switch", "on")])

[OUTPUT FORMAT]:
List of {id, name, room, type, fullId}
Maximum 5 results, sorted by relevance
""")
def search_devices(query: str, limit: int = 5) -> List[dict]:
    pass
```

---

## 决策树设计

### 用户意图分类

```python
# 伪代码：AI 内部决策逻辑
def classify_intent(user_input: str) -> Intent:
    """
    CONTROL: "打开客厅的灯", "关闭空调"
    QUERY: "客厅的温度是多少？", "灯现在是开的吗？"
    ANALYSIS: "过去一周的平均温度", "今天用了多少电？"
    DISCOVERY: "我有哪些设备？", "客厅有什么？"
    """
    pass

def plan_workflow(intent: Intent, user_input: str) -> List[ToolCall]:
    if intent == Intent.CONTROL:
        return plan_control(user_input)
    elif intent == Intent.QUERY:
        return plan_query(user_input)
    elif intent == Intent.ANALYSIS:
        return plan_analysis(user_input)
    elif intent == Intent.DISCOVERY:
        return plan_discovery(user_input)
```

### 控制意图工作流

```python
def plan_control(user_input: str) -> List[ToolCall]:
    """
    Example: "如果客厅温度超过 26 度，打开空调"
    """
    # 1. 解析条件
    has_condition = detect_condition(user_input)  # "如果...那么..."

    if has_condition:
        # 条件控制流程
        return [
            ToolCall("search_devices", query="客厅 温度"),
            ToolCall("get_device_status", device_id="<from_step1>"),
            # [AI 内部评估条件]
            ToolCall("search_devices", query="客厅 空调"),
            ToolCall("execute_commands", device_id="<from_step3>", commands=[...])
        ]
    else:
        # 简单控制流程
        return [
            ToolCall("search_devices", query="<extracted_query>"),
            ToolCall("execute_commands", device_id="<from_step1>", commands=[...])
        ]
```

### 查询意图工作流

```python
def plan_query(user_input: str) -> List[ToolCall]:
    """
    Example: "客厅的灯现在是开的吗？"
    """
    # 检查是否有缓存的 device_id
    device_id = check_conversation_history(user_input)

    if device_id:
        return [
            ToolCall("get_device_status", device_id=device_id)
        ]
    else:
        return [
            ToolCall("search_devices", query="<extracted_query>"),
            ToolCall("get_device_status", device_id="<from_step1>")
        ]
```

---

## 上下文感知规划

### Short-Term Memory（短期记忆）

AI 应在对话中维护：

```python
# 概念模型（AI 内部状态）
conversation_context = {
    "mentioned_devices": {
        "living_room_light": {
            "device_id": "abc123...",
            "last_mentioned_turn": 2,
            "last_status": {"switch": "on"}
        }
    },
    "current_room": "living_room",  # 推断的当前上下文
    "pending_actions": []
}
```

**使用示例**：

```
Turn 1:
User: "客厅的灯在哪里？"
AI: search_devices("客厅 灯")
    → Store: mentioned_devices["living_room_light"] = {device_id: "abc123"}
Response: "找到客厅吸顶灯 (ID: abc123)"

Turn 2:
User: "把它打开"
AI: Resolve "它" → living_room_light (device_id: abc123)
    → execute_commands(abc123, [Command("main", "switch", "on")])
    → NO need to search again!
Response: "已打开客厅吸顶灯"

Turn 3:
User: "现在状态如何？"
AI: Resolve context → living_room_light
    → get_device_status(abc123)
Response: "客厅吸顶灯当前状态：开启"
```

### Long-Term Memory（长期记忆）

跨对话 session 的优化（可选）：

```python
# 如果 MCP 支持持久化状态
persistent_context = {
    "user_preferences": {
        "default_room": "living_room",
        "common_devices": ["living_room_light", "bedroom_ac"]
    },
    "frequent_commands": [
        {"device": "living_room_light", "command": "on", "count": 15},
        {"device": "bedroom_ac", "command": "setTemperature", "count": 8}
    ]
}
```

---

## 并行与串行执行策略

### 并行执行场景

```python
# User: "告诉我客厅的温度和湿度"

# ✅ 正确：并行查询
parallel_calls = [
    ToolCall("search_devices", query="客厅 温度"),  # Call 1
    ToolCall("search_devices", query="客厅 湿度")   # Call 2
]
# 然后并行获取状态
parallel_status = [
    ToolCall("get_device_status", device_id="temp_sensor_id"),
    ToolCall("get_device_status", device_id="humidity_sensor_id")
]

# ❌ 错误：串行执行（浪费时间）
sequential_calls = [
    ToolCall("search_devices", query="客厅 温度"),
    # 等待...
    ToolCall("get_device_status", device_id="..."),
    # 等待...
    ToolCall("search_devices", query="客厅 湿度"),
    # 等待...
    ToolCall("get_device_status", device_id="...")
]
```

### 串行执行场景

```python
# User: "如果客厅温度超过 26 度，打开空调"

# ✅ 必须串行：因为有依赖关系
sequential_calls = [
    ToolCall("search_devices", query="客厅 温度"),
    ToolCall("get_device_status", device_id="<from_step1>"),
    # AI 评估条件：temperature > 26?
    # 如果为真，继续：
    ToolCall("search_devices", query="客厅 空调"),
    ToolCall("execute_commands", device_id="<from_step3>", commands=[...])
]
```

---

## 错误处理与恢复

### 优雅降级策略

```python
# Workflow with error handling
def execute_with_fallback(primary_plan, fallback_plan):
    try:
        result = execute(primary_plan)
        return result
    except DeviceNotFoundError:
        # Fallback: 扩大搜索范围
        return execute(fallback_plan)
    except CommandNotSupportedError:
        # Fallback: 查询支持的命令
        commands = get_device_commands(device_id, capability)
        return retry_with_valid_command(commands)
    except Exception as e:
        return user_friendly_error(e)
```

**实际示例**：

```
User: "打开客厅的电视"
AI: search_devices("客厅 电视")
    → Result: [] (没找到)

Fallback:
AI: search_devices("电视")  # 去掉房间限制
    → Result: [{"name": "主卧电视", ...}, {"name": "客厅 TV", ...}]
    → 向用户确认："没找到'客厅的电视'，但找到了'客厅 TV'，是这个吗？"
```

---

## 性能优化技巧

### 1. 工具调用批处理

```python
# ❌ 低效：多次单独调用
for device_id in device_ids:
    execute_commands(device_id, [Command("main", "switch", "off")])

# ✅ 高效：批量调用
batch_execute_commands([
    {"device_id": id1, "commands": [Command("main", "switch", "off")]},
    {"device_id": id2, "commands": [Command("main", "switch", "off")]},
    ...
])
```

### 2. 结果缓存

```python
# 在 AI 的对话上下文中缓存
cache = {
    "device_status": {
        "abc123": {
            "value": {"switch": "on"},
            "timestamp": "2025-11-12T10:30:00",
            "ttl": 300  # 5 分钟有效
        }
    }
}

# 查询时先检查缓存
if cache["device_status"].get(device_id) and not expired:
    return cache["device_status"][device_id]
else:
    result = get_device_status(device_id)
    cache["device_status"][device_id] = result
    return result
```

### 3. 预测性加载

```python
# User: "客厅的灯在哪里？"
AI: search_devices("客厅 灯")
    → Result: device_id = "abc123"

# AI 预测：用户可能接下来会控制这个灯
# 可选：预加载命令信息
preload_cache = get_device_commands(device_id, "switch")
# 这样下一轮对话可以立即执行，无需再查询
```

---

## 实施检查清单

在实现 Agent 时，确保：

- [ ] System Prompt 包含所有工作原则
- [ ] 每个工具有完整的使用指南（WHEN TO USE / DO NOT USE）
- [ ] 实现意图识别逻辑
- [ ] 实现设备 ID 缓存机制
- [ ] 支持并行工具调用（独立操作）
- [ ] 实现错误处理和优雅降级
- [ ] 添加 token 消耗监控
- [ ] 编写决策树单元测试

---

## 下一步

👉 阅读 [03-test-cases.md](03-test-cases.md) 了解如何验证 Agent 的规划能力
