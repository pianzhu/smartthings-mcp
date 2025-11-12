# 工具完整性评估与补充方案

## 现有工具概览

当前 SmartThings MCP Server 提供了 6 个核心工具：

| 工具 | 功能 | 特性 | 位置 |
|------|------|------|------|
| `get_rooms` | 获取房间列表 | 只读、幂等 | server.py:44 |
| `get_devices` | 获取设备列表（带过滤） | 只读、幂等 | server.py:66 |
| `get_device_status` | 获取设备状态 | 只读、幂等 | server.py:86 |
| `execute_commands` | 执行设备命令 | 破坏性、非幂等 | server.py:98 |
| `get_device_history` | 获取历史数据 | 只读、幂等 | server.py:116 |
| `get_hub_time` | 获取 Hub 时间 | 只读 | server.py:152 |

## 工具能力分析

### ✅ 足够应对的场景

1. **基础设备控制**
   - 单设备开关操作
   - 设备状态查询
   - 房间级别查询

2. **数据分析**
   - 历史数据趋势分析
   - 多种聚合方式（avg, sum, min, max）
   - 灵活的时间粒度

3. **设备发现**
   - 按能力（capability）过滤
   - 按房间过滤
   - 按设备类型过滤

### ❌ 存在的问题

1. **无法获取设备支持的命令**
   - AI 需要"猜测"设备支持哪些命令
   - 容易产生幻觉导致错误调用
   - 没有参数验证机制

2. **全量加载问题**
   - `get_devices()` 无参数调用会返回所有设备
   - 在大型家庭（50+ 设备）中消耗大量 token
   - 缺少智能搜索能力

3. **缺少上下文概览**
   - 首次对话需要加载完整设备列表
   - 无法快速了解家庭设备概况

4. **批量操作效率低**
   - 需要多次调用 `execute_commands`
   - 缺少事务性保证

---

## 必须补充的工具（P0）

### 1. `get_device_commands` - 获取设备支持的命令

**优先级**: 🔴 P0（必须）

**问题场景**:
```python
# 当前情况：AI 可能犯错
execute_commands(device_id, [
    Command("main", "switch", "toggle")  # ❌ 如果设备不支持 toggle 会失败
])
```

**实现方案**:

```python
@mcp.tool(
    description="""
    Get available commands and attributes for a device capability.
    Use this BEFORE calling execute_commands to avoid errors.
    """,
    annotations=ToolAnnotations(
        title="Get Device Commands",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def get_device_commands(
    device_id: UUID,
    capability: Capability
) -> dict:
    """
    Returns:
    {
        "capability": "switch",
        "commands": ["on", "off"],
        "attributes": {
            "switch": {
                "type": "string",
                "values": ["on", "off"]
            }
        }
    }
    """
    device = location.get_devices(include_status=False)
    # 从 device components 中提取 capability 信息
    # 或调用 SmartThings API 获取 capability schema
    pass
```

**实现位置**: `src/server.py` (新增) + `src/api.py` (辅助方法)

**收益**:
- ✅ 消除 AI 幻觉导致的命令错误
- ✅ 提供自我文档化能力
- ✅ 支持动态设备类型

---

### 2. `search_devices` - 智能设备搜索

**优先级**: 🔴 P0（必须）

**问题场景**:
```python
# 错误方式：用户说"打开客厅的灯"
all_devices = get_devices()  # 💀 返回 50 个设备，消耗 5000+ tokens

# 正确方式：
devices = search_devices("客厅 灯")  # ✅ 返回 2 个相关设备，500 tokens
```

**实现方案**:

```python
@mcp.tool(
    description="""
    Search devices by natural language query.

    WHEN TO USE:
    - User mentions room + device type (e.g., "客厅的灯", "卧室空调")
    - Need to find specific device without knowing ID
    - First time user mentions a device

    DO NOT USE:
    - When device_id is already known
    - For "list all devices" requests (use get_context_summary instead)
    """,
    annotations=ToolAnnotations(
        title="Search Devices",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def search_devices(
    query: str,
    limit: int = 5
) -> List[dict]:
    """
    Fuzzy search devices by label, room name, or capability.
    Returns minimal information to reduce token usage.

    Example queries:
    - "客厅的灯" → finds lights in living room
    - "温度传感器" → finds all temperature sensors
    - "卧室" → finds all devices in bedroom
    """
    # 实现模糊匹配逻辑
    # 1. 分词：提取房间名、设备类型关键词
    # 2. 匹配：房间 + 设备标签 + capability
    # 3. 排序：相关性评分
    # 4. 压缩：仅返回必要字段
    pass
```

**返回格式（超压缩）**:
```json
[
    {
        "id": "75c2fdb1",  // 短 ID（前 8 位）
        "name": "客厅吸顶灯",
        "room": "客厅",
        "type": "switch",
        "fullId": "75c2fdb1-ef20-419b-afc1-af6b34392ebb"  // 用于执行命令
    }
]
```

**实现位置**: `src/api.py` (新增 `Location.search_devices` 方法)

**算法伪代码**:
```python
def search_devices(self, query: str, limit: int = 5):
    # 1. 提取关键词
    keywords = extract_keywords(query)  # "客厅", "灯"

    # 2. 匹配房间
    room_matches = fuzzy_match_rooms(keywords)

    # 3. 匹配设备
    device_matches = []
    for device in self.get_devices(room_id=room_matches, include_status=False):
        score = calculate_relevance(device, keywords)
        if score > 0.3:
            device_matches.append((score, device))

    # 4. 排序和截断
    device_matches.sort(reverse=True)
    return [compress_device(d) for _, d in device_matches[:limit]]
```

**收益**:
- ✅ 减少 80% 的 token 消耗（首次查询）
- ✅ 提升用户体验（更快响应）
- ✅ 支持自然语言交互

---

## 强烈建议的工具（P1）

### 3. `get_context_summary` - 上下文摘要

**优先级**: 🟡 P1（强烈建议）

**实现方案**:

```python
@mcp.tool(
    description="""
    Get a high-level summary of the smart home setup.
    Use this at the START of a conversation to understand the environment.

    DO NOT use get_devices() for initial exploration.
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
    Returns ultra-compressed overview:
    {
        "rooms": {
            "living_room": {"device_count": 8, "types": ["switch", "sensor"]},
            "bedroom": {"device_count": 5, "types": ["switch", "lock"]}
        },
        "statistics": {
            "total_devices": 22,
            "by_type": {"switch": 10, "sensor": 8, "lock": 2, "other": 2}
        },
        "hub_time": "2025-11-12 10:30:00 UTC+8"
    }
    """
    pass
```

**实现位置**: `src/api.py` (新增方法)

**收益**:
- ✅ 首次对话节省 ~4000 tokens
- ✅ 帮助 AI 快速了解环境
- ✅ Token 消耗仅 ~50

---

### 4. `batch_execute_commands` - 批量命令执行

**优先级**: 🟡 P1（建议）

**实现方案**:

```python
@mcp.tool(
    description="""
    Execute commands on multiple devices in a single call.
    Use when user wants to control multiple devices at once.

    Example: "关闭所有灯", "打开客厅的所有设备"
    """,
    annotations=ToolAnnotations(
        title="Batch Execute Commands",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False
    )
)
def batch_execute_commands(
    operations: List[dict]  # [{"device_id": UUID, "commands": [Command, ...]}, ...]
) -> dict:
    """
    Execute commands on multiple devices.
    Returns aggregated results.
    """
    results = []
    for op in operations:
        result = location.device_commands(op['device_id'], op['commands'])
        results.append({
            'device_id': op['device_id'],
            'status': result
        })

    return {
        'total': len(operations),
        'success': sum(1 for r in results if r['status'].get('results', [{}])[0].get('status') == 'ACCEPTED'),
        'results': results
    }
```

**收益**:
- ✅ 减少多次工具调用
- ✅ 更好的用户体验（原子性）
- ✅ 降低延迟

---

## 可选的增强工具（P2）

### 5. `get_device_by_name` - 按名称获取设备

**优先级**: 🟢 P2（可选，可被 `search_devices` 替代）

### 6. `get_scene_list` - 获取场景列表

**优先级**: 🟢 P2（扩展功能）

### 7. `validate_command` - 命令验证

**优先级**: 🟢 P2（可被 `get_device_commands` 替代）

---

## 实施优先级总结

### 本周必须完成（P0）:
1. ✅ `search_devices` - 核心功能，最高 ROI
2. ✅ `get_device_commands` - 防止错误，提升可靠性

### 下周建议完成（P1）:
3. ✅ `get_context_summary` - 性能优化关键
4. ✅ `batch_execute_commands` - 用户体验提升

### 后续迭代（P2）:
5. 根据实际使用反馈决定是否需要

---

## 工具开发检查清单

每个新工具必须包含：

- [ ] 清晰的 description（包含 WHEN TO USE / DO NOT USE）
- [ ] 完整的 ToolAnnotations（readOnly, destructive, idempotent 标记）
- [ ] 参数验证和错误处理
- [ ] 返回格式压缩优化
- [ ] 单元测试（覆盖率 > 80%）
- [ ] 集成测试（至少 3 个真实场景）
- [ ] Token 消耗基准测试
- [ ] API 文档和示例

---

## 下一步

👉 阅读 [02-agent-planning.md](02-agent-planning.md) 了解如何让 AI 正确使用这些工具
