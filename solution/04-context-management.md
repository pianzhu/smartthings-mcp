# 上下文管理与优化方案

## 问题背景

智能家居 Agent 面临的核心挑战：

```
问题现象：
┌─────────────────────────────────────────────┐
│  Turn 1: get_devices() → 5000 tokens       │
│  Turn 2: User response → 6500 tokens       │
│  Turn 3: More queries → 9000 tokens        │
│  Turn 4: ❌ Context overflow (>10k)        │
└─────────────────────────────────────────────┘

预期目标：
┌─────────────────────────────────────────────┐
│  Turn 1: Optimized → 500 tokens            │
│  Turn 2: Cached → 800 tokens               │
│  Turn 3: Reuse → 1000 tokens               │
│  Turn 10: ✅ Stable < 2000 tokens/turn     │
└─────────────────────────────────────────────┘
```

---

## 策略 1: Prompt Caching（最关键）

### 1.1 原理

Claude 支持缓存静态上下文，避免重复计费：

```python
# 未优化：每次对话都计算完整 prompt
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},  # 2000 tokens
    {"role": "user", "content": "打开客厅的灯"},      # 20 tokens
]
# 总消耗：2020 tokens/turn

# 优化后：缓存系统提示
messages = [
    {"role": "system", "content": SYSTEM_PROMPT, "cache": True},  # 首次 2000，后续 ~100
    {"role": "user", "content": "打开客厅的灯"},                    # 20 tokens
]
# 首次：2020 tokens
# 后续：120 tokens/turn（节省 94%）
```

### 1.2 实施方案

**在 `src/server.py` 中构建可缓存内容：**

```python
# src/server.py

# 静态内容（可缓存）
CACHEABLE_SYSTEM_CONTEXT = f"""
You are a smart home assistant for SmartThings.

# WORK PRINCIPLES
{AGENT_SYSTEM_PROMPT}

# AVAILABLE ROOMS (Static - Updated daily)
{json.dumps(location.rooms, indent=2)}

# SUPPORTED CAPABILITIES (Static - Reference only)
{json.dumps(list(Capability.__args__), indent=2)}

# CONNECTION TYPES
{json.dumps(list(ConnectionType.__args__), indent=2)}

# DEVICE CATEGORIES
{json.dumps(list(ComponentCategory.__args__), indent=2)}
"""

# 在 FastMCP 中启用缓存（如果支持）
# 注意：具体实现取决于 MCP 框架的缓存 API
mcp = FastMCP("SmartThings", port=8001)

# 伪代码：配置缓存策略
mcp.configure_prompt_cache(
    system_prompt=CACHEABLE_SYSTEM_CONTEXT,
    cache_ttl=3600,  # 1 小时
    cache_key="smartthings_static_v1"
)
```

### 1.3 收益分析

| 对话轮次 | 未优化 | 优化后 | 节省 |
|---------|--------|--------|------|
| Turn 1  | 2000   | 2000   | 0%   |
| Turn 2  | 2000   | 100    | 95%  |
| Turn 3  | 2000   | 100    | 95%  |
| Turn 10 | 2000   | 100    | 95%  |
| **总计（10 轮）** | **20000** | **2900** | **86%** |

---

## 策略 2: 渐进式信息加载

### 2.1 反模式（避免）

```python
# ❌ 错误方式：一次性加载所有设备
@mcp.tool()
def initialize_conversation():
    all_devices = location.get_devices()  # 💀 5000+ tokens
    return all_devices

# AI 调用
User: "你好"
AI: initialize_conversation()
    → Result: 50 个设备的完整信息（5000 tokens）
    → ❌ 浪费，用户可能只需要 1 个设备
```

### 2.2 正确方式：按需加载

```python
# ✅ 正确方式：分层加载

# Level 0: 概览（50 tokens）
@mcp.tool()
def get_context_summary() -> dict:
    return {
        "total_devices": 22,
        "rooms": {"客厅": 8, "卧室": 5, ...},
        "device_types": {"switch": 10, "sensor": 8, ...}
    }

# Level 1: 搜索（500 tokens）
@mcp.tool()
def search_devices(query: str, limit: int = 5) -> List[dict]:
    # 只返回匹配的设备，超压缩格式
    return [{"id": "abc123", "name": "客厅灯", ...}]

# Level 2: 详细信息（按需，仅在需要时调用）
@mcp.tool()
def get_device_status(device_id: UUID) -> dict:
    return location.device_status(device_id)
```

### 2.3 加载决策树

```python
def decide_what_to_load(user_intent):
    if user_intent == "greeting" or user_intent == "general_question":
        return ["get_context_summary"]  # 50 tokens

    elif user_intent == "device_control":
        return ["search_devices"]  # 500 tokens

    elif user_intent == "status_query":
        return ["search_devices", "get_device_status"]  # 800 tokens

    elif user_intent == "analysis":
        return ["search_devices", "get_device_history"]  # 1000 tokens

    # 永远不要返回 get_devices() 无参数版本
```

---

## 策略 3: 智能状态压缩

### 3.1 返回值压缩

**当前实现（`src/api.py:243-289`）：**

```python
# 已经做了很好的压缩
def get_devices_short(...) -> List[dict]:
    # 过滤了不必要的字段
    filtered_device = {
        'deviceId': device.device_id,
        'label': device.label,
        'manufacturerName': device.manufacturer_name,
        # ... 只保留必要字段
    }
```

**进一步优化建议：**

```python
# src/api.py

def get_devices_ultra_short(
    self,
    capability: Set[Capability] | None = None,
    room_id: UUID | None = None,
) -> List[dict]:
    """超压缩版本，用于设备搜索"""
    devices = self.get_devices(
        capability=capability,
        room_id=room_id,
        include_status=False  # ✅ 关键：不包含状态
    )

    return [
        {
            'id': str(d.device_id)[:8],  # 短 ID（前 8 位，用于显示）
            'fullId': str(d.device_id),  # 完整 ID（用于执行）
            'name': d.label,
            'room': self.rooms.get(d.room_id, 'unknown') if d.room_id else None,
            'type': d.components[0].capabilities[0].id if d.components else 'unknown'
        }
        for d in devices[:5]  # ✅ 限制结果数量
    ]
```

### 3.2 状态缓存机制

```python
# src/api.py

class Location:
    def __init__(self, auth: str, location_id: UUID | None = None):
        # ... 现有代码 ...
        self._status_cache = {}  # 新增：状态缓存
        self._cache_ttl = 300    # 5 分钟

    def device_status(self, device_id: UUID) -> dict:
        # 检查缓存
        cache_key = str(device_id)
        if cache_key in self._status_cache:
            cached = self._status_cache[cache_key]
            if time.time() - cached['timestamp'] < self._cache_ttl:
                logger.info(f"Cache hit for device {device_id}")
                return cached['data']

        # 缓存未命中，查询 API
        device_id = self.validate_device_id(device_id)
        status = self._device_status(device_id)

        # 更新缓存
        self._status_cache[cache_key] = {
            'data': status.components,
            'timestamp': time.time()
        }

        return status.components
```

---

## 策略 4: 工具结果过滤

### 4.1 智能摘要返回

```python
# src/server.py

@mcp.tool(description="...")
def get_device_status(device_id: UUID) -> dict:
    """添加智能过滤，只返回有用的信息"""
    full_status = location.device_status(device_id)

    # 过滤：移除 supported* 和其他元数据
    filtered_status = {}
    for component, capabilities in full_status.items():
        filtered_status[component] = {}
        for cap_name, attributes in capabilities.items():
            filtered_status[component][cap_name] = {}
            for attr_name, attr_value in attributes.items():
                # 跳过元数据
                if attr_name.startswith('supported') or attr_name == 'numberOfButtons':
                    continue
                filtered_status[component][cap_name][attr_name] = attr_value

    return filtered_status
```

### 4.2 返回值摘要注解

```python
# 在工具描述中添加
@mcp.tool(
    description="""
    ...
    [RETURN OPTIMIZATION]:
    - Only essential attributes are returned
    - Metadata fields are filtered out
    - Use this to minimize token usage
    """,
    # 新增：返回值摘要策略
    result_summary_hint="Only return changed attributes if called multiple times for same device"
)
def get_device_status(device_id: UUID) -> dict:
    pass
```

---

## 策略 5: 滑动窗口对话管理

### 5.1 上下文生命周期

```python
# 伪代码：AI 内部状态管理

class ConversationContext:
    def __init__(self):
        self.short_term = {}  # 最近 3 轮
        self.long_term = {}   # 整个 session
        self.turn_count = 0

    def add_device(self, device_id: str, device_info: dict):
        """添加设备到上下文"""
        self.short_term[device_id] = {
            'info': device_info,
            'turn': self.turn_count,
            'last_accessed': self.turn_count
        }

    def get_device(self, device_id: str) -> dict | None:
        """获取设备信息"""
        if device_id in self.short_term:
            self.short_term[device_id]['last_accessed'] = self.turn_count
            return self.short_term[device_id]['info']
        return None

    def cleanup_old_entries(self):
        """清理超过 3 轮未使用的条目"""
        self.turn_count += 1
        to_remove = []
        for device_id, data in self.short_term.items():
            if self.turn_count - data['last_accessed'] > 3:
                to_remove.append(device_id)

        for device_id in to_remove:
            del self.short_term[device_id]
            logger.info(f"Cleaned up old context for device {device_id}")
```

### 5.2 使用示例

```
Turn 1: User: "客厅的灯在哪里？"
  AI: search_devices("客厅 灯")
  Context: {
    "light_abc123": {info: {...}, turn: 1, last_accessed: 1}
  }
  Token: 500

Turn 2: User: "把它打开"
  AI: Resolve "它" → light_abc123 (from context)
  Context: {
    "light_abc123": {info: {...}, turn: 1, last_accessed: 2}  # updated
  }
  Token: 200

Turn 5: User: "打开卧室的空调"  # 3 轮后
  AI: Cleanup triggered
  Context: {
    # light_abc123 removed (not accessed in 3 turns)
    "ac_def456": {info: {...}, turn: 5, last_accessed: 5}
  }
  Token: 600
```

---

## 策略 6: 批量操作优化

### 6.1 批量查询压缩

```python
# ❌ 低效方式
devices = []
for room in ["客厅", "卧室", "厨房"]:
    devices.extend(search_devices(f"{room} 灯"))
# 3 次工具调用，3000+ tokens

# ✅ 高效方式
devices = search_devices("灯")  # 一次调用
devices = [d for d in devices if d['room'] in ["客厅", "卧室", "厨房"]]
# 1 次工具调用，1000 tokens
```

### 6.2 批量执行合并

```python
# 实现 batch_execute_commands
@mcp.tool(description="Execute commands on multiple devices")
def batch_execute_commands(operations: List[dict]) -> dict:
    """
    operations: [
        {"device_id": UUID, "commands": [Command, ...]},
        ...
    ]
    """
    results = []
    for op in operations:
        try:
            result = location.device_commands(op['device_id'], op['commands'])
            results.append({
                'device_id': str(op['device_id']),
                'status': 'success',
                'details': result
            })
        except Exception as e:
            results.append({
                'device_id': str(op['device_id']),
                'status': 'failed',
                'error': str(e)
            })

    # 返回摘要（而非完整详情）
    return {
        'total': len(operations),
        'success': sum(1 for r in results if r['status'] == 'success'),
        'failed': sum(1 for r in results if r['status'] == 'failed'),
        'details': results  # 可选：AI 可以忽略此字段
    }
```

---

## 策略 7: Token 使用监控

### 7.1 实时监控

```python
# src/monitoring.py

from dataclasses import dataclass
from typing import List
import logging

logger = logging.getLogger(__name__)

@dataclass
class ToolCallMetrics:
    tool_name: str
    input_tokens: int
    output_tokens: int
    execution_time: float
    timestamp: float

class TokenMonitor:
    def __init__(self):
        self.calls: List[ToolCallMetrics] = []

    def record_call(self, tool_name: str, input_tokens: int,
                    output_tokens: int, execution_time: float):
        metric = ToolCallMetrics(
            tool_name=tool_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            execution_time=execution_time,
            timestamp=time.time()
        )
        self.calls.append(metric)

        # 实时警告
        if output_tokens > 2000:
            logger.warning(f"High token output from {tool_name}: {output_tokens} tokens")

    def get_summary(self) -> dict:
        return {
            'total_calls': len(self.calls),
            'total_input_tokens': sum(c.input_tokens for c in self.calls),
            'total_output_tokens': sum(c.output_tokens for c in self.calls),
            'avg_execution_time': sum(c.execution_time for c in self.calls) / len(self.calls),
            'top_token_consumers': sorted(
                [(c.tool_name, c.output_tokens) for c in self.calls],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }

# 在 server.py 中集成
monitor = TokenMonitor()

# 装饰器：自动监控工具调用
def monitored_tool(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        # 估算 token（粗略）
        import sys
        output_tokens = sys.getsizeof(str(result)) // 4  # 4 bytes ≈ 1 token

        monitor.record_call(
            tool_name=func.__name__,
            input_tokens=0,  # 需要从 MCP 框架获取
            output_tokens=output_tokens,
            execution_time=end_time - start_time
        )

        return result
    return wrapper
```

### 7.2 使用示例

```python
# 在每个工具上应用监控
@mcp.tool(...)
@monitored_tool
def search_devices(query: str, limit: int = 5) -> List[dict]:
    pass

# 在对话结束时输出摘要
@mcp.tool(description="Get token usage summary for this conversation")
def get_usage_summary() -> dict:
    return monitor.get_summary()
```

---

## 策略 8: 预测性优化

### 8.1 智能预加载

```python
# 基于用户意图预测下一步需要的信息

def predict_next_action(current_action: str, user_query: str) -> str | None:
    """预测用户下一步可能的操作"""

    if current_action == "search_devices":
        # 用户搜索了设备，可能接下来会：
        # 1. 查询状态
        # 2. 执行控制
        if "哪里" in user_query or "是什么" in user_query:
            return "get_device_status"  # 预测：用户想了解详情
        else:
            return "execute_commands"  # 预测：用户想控制

    elif current_action == "get_device_status":
        # 用户查询了状态，可能接下来会：
        # 1. 执行控制（基于状态）
        # 2. 查询历史数据
        return "execute_commands"

    return None

# 使用预测进行缓存预热（可选）
def preheat_cache(device_id: UUID, predicted_action: str):
    if predicted_action == "get_device_commands":
        # 提前获取设备命令信息
        _ = get_device_commands(device_id, "switch")
    # 不发送给 AI，仅缓存
```

### 8.2 频率分析

```python
class FrequencyAnalyzer:
    def __init__(self):
        self.device_access_count = {}
        self.command_patterns = []

    def record_access(self, device_id: str):
        self.device_access_count[device_id] = \
            self.device_access_count.get(device_id, 0) + 1

    def get_frequent_devices(self, top_n: int = 5) -> List[str]:
        """返回最常访问的设备"""
        return sorted(
            self.device_access_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

    def suggest_preload(self) -> List[str]:
        """建议预加载的设备"""
        frequent = self.get_frequent_devices(3)
        return [device_id for device_id, _ in frequent]

# 在系统启动时预加载常用设备信息
analyzer = FrequencyAnalyzer()
# ... 记录使用情况 ...
# 在新对话开始时
preload_devices = analyzer.suggest_preload()
for device_id in preload_devices:
    # 预热缓存
    _ = location.device_status(UUID(device_id))
```

---

## 实施优先级

### Phase 1: 立即实施（Week 1）

1. ✅ **Prompt Caching**
   - 分离静态/动态内容
   - 配置缓存策略
   - 预期收益：**80-90% token 节省**

2. ✅ **渐进式加载**
   - 实现 `get_context_summary`
   - 实现 `search_devices`
   - 预期收益：**70% 首次查询优化**

3. ✅ **状态压缩**
   - 过滤不必要的返回字段
   - 预期收益：**30-40% 返回值优化**

### Phase 2: 优化增强（Week 2）

4. ✅ **状态缓存**
   - 实现设备状态缓存
   - TTL 设置为 5 分钟
   - 预期收益：**减少 50% 重复查询**

5. ✅ **批量操作**
   - 实现 `batch_execute_commands`
   - 预期收益：**多设备操作提速 60%**

6. ✅ **Token 监控**
   - 添加实时监控
   - 预期收益：**可见性提升，发现瓶颈**

### Phase 3: 高级优化（Week 3+）

7. ✅ **滑动窗口管理**
   - 实现上下文清理
   - 预期收益：**长对话稳定性**

8. ✅ **预测性优化**
   - 智能预加载
   - 预期收益：**响应速度提升 20%**

---

## 性能目标

| 指标 | 优化前 | 优化后 | 改进 |
|------|--------|--------|------|
| 首轮 Token | 8000 | 2000 | **75%** ⬇️ |
| 第 2 轮 Token | 12000 | 800 | **93%** ⬇️ |
| 第 3 轮 Token | 18000 | 1000 | **94%** ⬇️ |
| 10 轮累计 | 80000+ | 10000 | **87%** ⬇️ |
| Cache 命中率 | 0% | 85%+ | - |
| 平均响应时间 | 3s | 1.5s | **50%** ⬇️ |

---

## 监控仪表板

```python
# 实时监控输出示例
@mcp.tool(description="Get performance metrics")
def get_performance_metrics() -> dict:
    return {
        "current_session": {
            "turn_count": 5,
            "total_tokens": 3200,
            "avg_tokens_per_turn": 640,
            "cache_hit_rate": 0.87
        },
        "tool_usage": {
            "search_devices": {"calls": 2, "avg_tokens": 450},
            "execute_commands": {"calls": 3, "avg_tokens": 200},
            "get_device_status": {"calls": 1, "avg_tokens": 300}
        },
        "optimization_status": {
            "prompt_caching": "✅ Active",
            "state_caching": "✅ Active (3 devices cached)",
            "context_cleanup": "✅ Active (2 old entries removed)"
        }
    }
```

---

## 最佳实践总结

### DO ✅

1. **始终使用 Prompt Caching** - 最高 ROI
2. **按需加载信息** - 避免一次性加载
3. **压缩返回值** - 过滤无用字段
4. **缓存状态** - 避免重复查询
5. **监控 Token 使用** - 持续优化

### DON'T ❌

1. **不要** 在对话开始时加载所有设备
2. **不要** 重复查询相同的设备状态
3. **不要** 返回完整的未过滤数据
4. **不要** 忽略上下文管理
5. **不要** 在没有监控的情况下上线

---

## 下一步行动

1. ✅ 实施 Prompt Caching（最高优先级）
2. ✅ 添加 `get_context_summary` 和 `search_devices` 工具
3. ✅ 配置 Token 监控
4. ✅ 运行性能基准测试
5. ✅ 根据监控数据调优

---

**恭喜！** 你已经完成了所有设计文档的阅读。现在可以开始实施了！

👉 回到 [README.md](README.md) 查看实施路线图
