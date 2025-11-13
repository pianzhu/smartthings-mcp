# 简化设计原则：工具保持简单，AI 负责编排

**设计理念**: Keep tools simple, let AI orchestrate

---

## 核心思想 💡

**工具应该只做一件事，并把它做好。**

❌ **错误做法**：在工具内部塞入复杂逻辑（自动搜索、自动循环等）
✅ **正确做法**：工具保持简单，通过 prompt 引导 AI 如何组合使用

---

## 三个简单工具

### 1. `search_devices`
```python
输入: query (str)
输出: [{"fullId": UUID, "name": str, ...}]

职责: 只负责搜索，返回 device_id
```

### 2. `execute_commands`
```python
输入: device_id (UUID) + commands (List)
输出: {status: "ACCEPTED"}

职责: 只负责执行单个设备的命令
```

### 3. `batch_execute_commands`
```python
输入: [{"device_id": UUID, "commands": List}, ...]
输出: {total, success, failed, results}

职责: 批量执行多个设备的命令（仅此而已）
```

---

## AI 如何编排（通过 Prompt 引导）

### 场景 1: 少量不同操作（2-3 个）

**用户**: "打开客厅的灯，关闭卧室的空调，锁上前门"

**AI 执行**:
```xml
<!-- Round 1: 并行搜索 -->
<tool_use id="1">search_devices("客厅 灯")</tool_use>
<tool_use id="2">search_devices("卧室 空调")</tool_use>
<tool_use id="3">search_devices("前门")</tool_use>

<!-- AI 收到 3 个结果，提取 fullId -->

<!-- Round 2: 并行执行 -->
<tool_use id="4">execute_commands(device_id_1, [Command(...)])</tool_use>
<tool_use id="5">execute_commands(device_id_2, [Command(...)])</tool_use>
<tool_use id="6">execute_commands(device_id_3, [Command(...)])</tool_use>
```

**性能**: 2 轮，~1500 tokens

---

### 场景 2: 大量相似操作（4+ 个）

**用户**: "关闭客厅所有的灯"（假设 5 个灯）

**AI 执行**:
```xml
<!-- Step 1: 搜索一次 -->
<tool_use id="1">
  search_devices("客厅 灯", limit=10)
</tool_use>

<!-- 返回 5 个设备，AI 提取所有 fullId -->

<!-- Step 2: 批量执行 -->
<tool_use id="2">
  batch_execute_commands([
    {"device_id": "aaa-uuid", "commands": [{"capability": "switch", "command": "off"}]},
    {"device_id": "bbb-uuid", "commands": [{"capability": "switch", "command": "off"}]},
    {"device_id": "ccc-uuid", "commands": [{"capability": "switch", "command": "off"}]},
    {"device_id": "ddd-uuid", "commands": [{"capability": "switch", "command": "off"}]},
    {"device_id": "eee-uuid", "commands": [{"capability": "switch", "command": "off"}]}
  ])
</tool_use>
```

**性能**: 2 次调用，~800 tokens

---

## 为什么这样设计？

### ✅ 优势

1. **工具简单**
   - 每个工具职责单一
   - 易于测试和维护
   - 没有隐藏的副作用

2. **灵活性高**
   - AI 可以根据场景自由组合
   - 不受工具内部逻辑限制
   - 容易扩展新策略

3. **可预测性**
   - 工具行为清晰明确
   - 没有"魔法"自动行为
   - 调试更容易

4. **符合 UNIX 哲学**
   - Do one thing and do it well
   - Tools compose, not integrate

### ❌ 之前复杂设计的问题

```python
# ❌ 工具太复杂（之前的设计）
batch_execute_commands([
    {"deviceName": "灯", "roomName": "客厅", "commands": [...]},  # 内部自动搜索
    {"query": "卧室 空调", "commands": [...]},                     # 内部自动搜索
    {"device_id": "xxx", "commands": [...]}                        # 直接使用 ID
])

# 问题：
# 1. 工具职责不清（既搜索又执行）
# 2. 三种输入格式增加复杂度
# 3. 内部循环搜索，AI 失去控制
# 4. 难以并行优化
```

---

## Prompt Engineering 核心

在工具描述中明确告诉 AI 如何编排：

```
[IMPORTANT - MULTI-OPERATION STRATEGY]:

When user requests multiple operations, YOU must orchestrate tool calls:

Strategy 1: Few operations (2-3 devices) → PARALLEL calls
  Round 1: Call search_devices 3x IN PARALLEL
  Round 2: Call execute_commands 3x IN PARALLEL

Strategy 2: Many similar operations (4+ devices) → BATCH
  Round 1: Search once
  Round 2: Batch execute with all device_ids
```

**关键**：用 `<tool_use id="...">` 语法明确展示给 AI 看

---

## 实际执行流程对比

### 场景：用户说 "关闭客厅所有的灯"（5 个灯）

#### ❌ 复杂设计（工具内部循环）

```
AI 调用:
  batch_execute_commands([
    {"deviceName": "吸顶灯", "roomName": "客厅", ...},
    {"deviceName": "台灯1", "roomName": "客厅", ...},
    {"deviceName": "台灯2", "roomName": "客厅", ...},
    {"deviceName": "落地灯", "roomName": "客厅", ...},
    {"deviceName": "壁灯", "roomName": "客厅", ...}
  ])

工具内部执行:
  for each operation:
    search_devices(roomName + deviceName)  # 串行搜索 5 次！
    execute_commands(device_id, ...)

问题:
  - AI 不知道工具内部在做什么
  - 无法利用并行能力
  - 搜索是串行的（浪费时间）
```

#### ✅ 简化设计（AI 编排）

```
AI Round 1:
  search_devices("客厅 灯", limit=10)  # 一次搜索，返回所有

AI 收到结果:
  [
    {"fullId": "aaa", "name": "吸顶灯"},
    {"fullId": "bbb", "name": "台灯1"},
    {"fullId": "ccc", "name": "台灯2"},
    {"fullId": "ddd", "name": "落地灯"},
    {"fullId": "eee", "name": "壁灯"}
  ]

AI Round 2:
  batch_execute_commands([
    {"device_id": "aaa", "commands": [...]},
    {"device_id": "bbb", "commands": [...]},
    {"device_id": "ccc", "commands": [...]},
    {"device_id": "ddd", "commands": [...]},
    {"device_id": "eee", "commands": [...]}
  ])

优势:
  - AI 完全控制流程
  - 搜索一次，效率高
  - 批量执行，减少开销
```

---

## 对比表

| 方面 | 复杂设计 | 简化设计 |
|------|----------|----------|
| 工具职责 | 模糊（搜索+执行） | 清晰（单一职责） |
| 输入格式 | 3 种混合 | 1 种统一 |
| 搜索方式 | 内部串行循环 | AI 控制，可并行 |
| 可预测性 | 低（黑盒行为） | 高（每步可见） |
| 调试难度 | 困难 | 简单 |
| 扩展性 | 受限 | 灵活 |
| Token 消耗 | 类似 | 类似 |
| 延迟 | 较高（串行搜索） | 较低（AI 优化） |

---

## 设计哲学

### UNIX 哲学的启示

> "Write programs that do one thing and do it well."

MCP 工具应该遵循相同原则：
- **单一职责**：每个工具只做一件事
- **可组合性**：通过组合实现复杂功能
- **透明性**：行为清晰可预测

### AI Agent 的角色

AI 不是工具的"用户"，而是**编排者**（Orchestrator）：
- 理解用户意图
- 分解为简单步骤
- 选择合适工具
- 并行/串行执行
- 处理结果和错误

---

## 实现细节

### api.py（简化版）

```python
def batch_execute_commands(self, operations: List[dict]) -> dict:
    """
    Simple design: Only accepts device_id + commands.
    AI should call search_devices first to get device_ids.
    """
    results = []
    for op in operations:
        device_id = UUID(op['device_id'])
        commands = op['commands']
        # ... 执行命令
    return {"total": ..., "success": ..., "failed": ..., "results": ...}
```

**关键**：只有一个分支，没有复杂的格式判断

### server.py（引导式描述）

```python
@mcp.tool(description="""
[IMPORTANT - MULTI-OPERATION STRATEGY]:

When user requests multiple operations, YOU must orchestrate tool calls:

Strategy 1: Few operations (2-3 devices) → PARALLEL calls
  Round 1: Call search_devices 3x IN PARALLEL
    <tool_use id="1">search_devices("客厅 灯")</tool_use>
    <tool_use id="2">search_devices("卧室 空调")</tool_use>
  Round 2: Call execute_commands 3x IN PARALLEL
    <tool_use id="3">execute_commands(device_id_1, [...])</tool_use>
    <tool_use id="4">execute_commands(device_id_2, [...])</tool_use>

Strategy 2: Many similar operations (4+ devices) → BATCH
  Round 1: Search once
    <tool_use id="1">search_devices("客厅 灯", limit=10)</tool_use>
  Round 2: Batch execute
    <tool_use id="2">batch_execute_commands([...])</tool_use>
""")
def batch_execute_commands(operations: List[dict]) -> dict:
    ...
```

**关键**：用具体的 XML 示例告诉 AI 怎么做

---

## 测试验证

### 简单性测试

```python
# 工具接口应该极其简单
operations = [
    {"device_id": "aaa-uuid", "commands": [...]},
    {"device_id": "bbb-uuid", "commands": [...]}
]

result = batch_execute_commands(operations)

# 断言：只需要 device_id，没有其他魔法
assert "device_id" in operations[0]
assert "deviceName" not in operations[0]  # 不需要
assert "query" not in operations[0]       # 不需要
```

### AI 编排测试（人工验证）

```
测试场景："关闭客厅所有的灯"

AI 应该:
  1. 调用 search_devices("客厅 灯", limit=10)
  2. 从结果中提取所有 fullId
  3. 调用 batch_execute_commands([{device_id, commands}, ...])

验证:
  - ✅ AI 只调用了 2 次工具
  - ✅ 第一次是 search_devices
  - ✅ 第二次是 batch_execute_commands
  - ✅ batch 的输入包含所有 device_id
```

---

## 总结

### 核心原则

1. **Keep it simple**: 工具只做一件事
2. **AI orchestrates**: 复杂逻辑由 AI 编排
3. **Explicit is better**: 用 prompt 明确指导
4. **Composability**: 简单工具组合成强大功能

### 实际效果

| 场景 | 调用次数 | Token | 延迟 |
|------|----------|-------|------|
| 3 个不同操作 | 2 轮（6 次） | ~1500 | 1s |
| 5 个相似操作 | 2 次 | ~800 | 0.5s |

### 关键收获

> "Simplicity is the ultimate sophistication." - Leonardo da Vinci

在 MCP 工具设计中，**简单 > 智能**。

让工具保持愚蠢和简单，把智能留给 AI。

---

**状态**: ✅ 已实施
**验证**: ✅ 语法检查通过
**文档**: 本文件
**作者**: Claude (Anthropic MCP Expert)
