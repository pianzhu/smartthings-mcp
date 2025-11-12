# 测试驱动开发用例设计

## 测试策略概览

采用分层测试策略：

```
┌──────────────────────────────────────────┐
│  Level 3: Integration Tests             │  ← 端到端场景（10-20 个）
│  (End-to-End Scenarios)                 │
├──────────────────────────────────────────┤
│  Level 2: Workflow Tests                │  ← 多工具组合（20-30 个）
│  (Multi-Tool Interactions)              │
├──────────────────────────────────────────┤
│  Level 1: Unit Tests                    │  ← 单工具验证（50+ 个）
│  (Single Tool Validation)               │
└──────────────────────────────────────────┘
```

---

## Level 1: 单工具基础测试

### 1.1 `search_devices` 测试

#### TC-101: 基础搜索 - 房间 + 设备类型
```yaml
Test ID: TC-101
Name: Search devices by room and type
Priority: P0

Input:
  query: "客厅 灯"
  limit: 5

Expected Behavior:
  1. 返回客厅中的灯设备
  2. 结果按相关性排序
  3. 最多返回 5 个设备
  4. 每个设备包含: id, name, room, type, fullId

Assertions:
  - result.length <= 5
  - all(device.room == "客厅" for device in result)
  - all("灯" in device.name or device.type == "switch" for device in result)
  - token_count < 500

Mock Data:
  devices:
    - {id: "abc123", name: "客厅吸顶灯", room: "客厅", type: "switch"}
    - {id: "def456", name: "客厅台灯", room: "客厅", type: "switch"}
    - {id: "ghi789", name: "卧室台灯", room: "卧室", type: "switch"}  # 不应返回

Expected Output:
  - {id: "abc123", name: "客厅吸顶灯", room: "客厅", type: "switch", fullId: "abc123..."}
  - {id: "def456", name: "客厅台灯", room: "客厅", type: "switch", fullId: "def456..."}
```

#### TC-102: 模糊匹配
```yaml
Test ID: TC-102
Name: Fuzzy matching for device names
Priority: P0

Input:
  query: "客厅 TV"  # 注意：设备名称可能是 "客厅电视" 或 "客厅 television"

Expected Behavior:
  - 支持模糊匹配（TV → 电视, television）
  - 支持拼音（keying → 客厅）（可选）

Assertions:
  - result.length > 0
  - any("电视" in device.name or "TV" in device.name for device in result)
```

#### TC-103: 空结果处理
```yaml
Test ID: TC-103
Name: Handle no matching devices
Priority: P1

Input:
  query: "火星 灯"

Expected Behavior:
  - 返回空列表
  - 不应抛出异常

Assertions:
  - result == []
  - no_exception_raised()
```

---

### 1.2 `get_device_commands` 测试

#### TC-111: 获取开关设备命令
```yaml
Test ID: TC-111
Name: Get commands for switch capability
Priority: P0

Input:
  device_id: "abc123"
  capability: "switch"

Expected Output:
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

Assertions:
  - "on" in result.commands
  - "off" in result.commands
  - result.capability == "switch"
```

#### TC-112: 不支持的能力
```yaml
Test ID: TC-112
Name: Handle unsupported capability
Priority: P1

Input:
  device_id: "abc123"  # 只支持 "switch"
  capability: "thermostat"

Expected Behavior:
  - 返回错误或空命令列表
  - 提供清晰的错误信息

Assertions:
  - result.error or result.commands == []
  - "not supported" in result.message.lower()
```

---

### 1.3 `batch_execute_commands` 测试

#### TC-121: 批量执行成功
```yaml
Test ID: TC-121
Name: Batch execute commands on multiple devices
Priority: P0

Input:
  operations:
    - device_id: "abc123"
      commands: [{component: "main", capability: "switch", command: "off"}]
    - device_id: "def456"
      commands: [{component: "main", capability: "switch", command: "off"}]

Expected Output:
  {
    "total": 2,
    "success": 2,
    "results": [
      {device_id: "abc123", status: "ACCEPTED"},
      {device_id: "def456", status: "ACCEPTED"}
    ]
  }

Assertions:
  - result.total == 2
  - result.success == 2
  - all(r.status == "ACCEPTED" for r in result.results)
```

#### TC-122: 部分失败处理
```yaml
Test ID: TC-122
Name: Handle partial failures in batch execution
Priority: P1

Input:
  operations:
    - device_id: "abc123"
      commands: [{component: "main", capability: "switch", command: "off"}]
    - device_id: "invalid_id"
      commands: [{component: "main", capability: "switch", command: "off"}]

Expected Output:
  {
    "total": 2,
    "success": 1,
    "results": [
      {device_id: "abc123", status: "ACCEPTED"},
      {device_id: "invalid_id", status: "FAILED", error: "Device not found"}
    ]
  }

Assertions:
  - result.success == 1
  - result.results[1].status == "FAILED"
```

---

## Level 2: 多工具组合测试

### 2.1 简单控制流程

#### TC-201: 单设备简单控制
```yaml
Test ID: TC-201
Name: Simple device control workflow
Priority: P0
Category: Control Flow

Scenario: "打开客厅的灯"

Expected Workflow:
  Step 1: search_devices("客厅 灯")
    → Returns: [{id: "abc123", name: "客厅吸顶灯", ...}]

  Step 2: execute_commands(
      device_id="abc123",
      commands=[{component: "main", capability: "switch", command: "on"}]
    )
    → Returns: {status: "ACCEPTED"}

Assertions:
  - total_tool_calls == 2
  - tools_called == ["search_devices", "execute_commands"]
  - total_tokens < 1000
  - execution_time < 2s

Success Criteria:
  ✓ 正确定位设备
  ✓ 正确执行命令
  ✓ 无多余工具调用
  ✓ Token 消耗在预期范围内
```

#### TC-202: 设备状态查询
```yaml
Test ID: TC-202
Name: Device status query workflow
Priority: P0
Category: Query Flow

Scenario: "客厅现在的温度是多少？"

Expected Workflow:
  Step 1: search_devices("客厅 温度")
    → Returns: [{id: "temp123", name: "客厅温度传感器", ...}]

  Step 2: get_device_status(device_id="temp123")
    → Returns: {
        "main": {
          "temperatureMeasurement": {
            "temperature": {value: 24.5, unit: "C"}
          }
        }
      }

Assertions:
  - total_tool_calls == 2
  - final_response contains "24.5"
  - final_response contains "度" or "C"
  - total_tokens < 1200

Success Criteria:
  ✓ 正确提取温度值
  ✓ 返回用户友好的信息
```

---

### 2.2 条件控制流程

#### TC-211: 条件判断 - 温度控制
```yaml
Test ID: TC-211
Name: Conditional control based on temperature
Priority: P0
Category: Conditional Flow

Scenario: "如果客厅温度超过 26 度，打开空调"

Expected Workflow:
  Step 1: search_devices("客厅 温度")
    → Returns: [{id: "temp123", ...}]

  Step 2: get_device_status(device_id="temp123")
    → Returns: {temperature: {value: 27, unit: "C"}}  # > 26

  Step 3: [AI evaluates condition: 27 > 26 → True]

  Step 4: search_devices("客厅 空调")
    → Returns: [{id: "ac123", ...}]

  Step 5: execute_commands(
      device_id="ac123",
      commands=[{component: "main", capability: "switch", command: "on"}]
    )

Assertions:
  - total_tool_calls == 4
  - condition_evaluated_correctly == True
  - ac_turned_on == True

Test Variant (Condition False):
  If temperature = 25 (< 26):
    - total_tool_calls == 2 (只执行 Step 1-2)
    - ac_not_called == True
    - final_response contains "温度未超过 26 度"
```

#### TC-212: 条件判断 - 存在性检查
```yaml
Test ID: TC-212
Name: Conditional control with existence check
Priority: P1
Category: Conditional Flow

Scenario: "如果有人在家，打开客厅的灯"

Expected Workflow:
  Step 1: search_devices("存在传感器" or "presence")
    → Returns: [{id: "presence123", ...}]

  Step 2: get_device_status(device_id="presence123")
    → Returns: {presence: {value: "present"}}

  Step 3: [AI evaluates: presence == "present" → True]

  Step 4: search_devices("客厅 灯")
  Step 5: execute_commands(...)

Assertions:
  - condition_logic_correct == True
  - lights_only_turned_on_when_present == True
```

---

### 2.3 批量控制流程

#### TC-221: 批量设备控制
```yaml
Test ID: TC-221
Name: Batch control multiple devices
Priority: P0
Category: Batch Flow

Scenario: "关闭客厅所有的灯"

Expected Workflow:
  Step 1: search_devices("客厅 灯")
    → Returns: [
        {id: "light1", name: "客厅吸顶灯"},
        {id: "light2", name: "客厅台灯"},
        {id: "light3", name: "客厅氛围灯"}
      ]

  Step 2: batch_execute_commands([
      {device_id: "light1", commands: [{..., command: "off"}]},
      {device_id: "light2", commands: [{..., command: "off"}]},
      {device_id: "light3", commands: [{..., command: "off"}]}
    ])

Alternative (if batch not available):
  Step 2a: execute_commands(device_id="light1", ...)
  Step 2b: execute_commands(device_id="light2", ...)
  Step 2c: execute_commands(device_id="light3", ...)

Assertions:
  - all_lights_turned_off == True
  - token_count < 2000
  - prefer_batch_over_individual == True (if batch_execute available)

Success Criteria:
  ✓ 识别所有目标设备
  ✓ 使用批量执行（如果可用）
  ✓ 所有设备执行成功
```

---

### 2.4 历史数据分析流程

#### TC-231: 历史数据查询
```yaml
Test ID: TC-231
Name: Historical data analysis workflow
Priority: P0
Category: Analysis Flow

Scenario: "过去一周卧室的平均温度是多少？"

Expected Workflow:
  Step 1: search_devices("卧室 温度")
    → Returns: [{id: "temp456", ...}]

  Step 2: get_device_history(
      device_id="temp456",
      attribute="temperature",
      delta_start="P7D",  # 7 days
      delta_end=None,     # now
      granularity="daily",
      aggregate="avg"
    )
    → Returns: [
        {time: "2025-11-05", value: 22.3},
        {time: "2025-11-06", value: 23.1},
        ...
      ]

  Step 3: [AI calculates overall average from daily averages]

Assertions:
  - total_tool_calls == 2
  - correct_time_format == "P7D"
  - correct_granularity == "daily"
  - correct_aggregate == "avg"
  - final_response contains calculated average

Success Criteria:
  ✓ 正确使用 ISO8601 duration
  ✓ 选择合适的粒度和聚合方式
  ✓ 准确计算并展示结果
```

---

## Level 3: 端到端集成测试

### 3.1 多轮对话上下文管理

#### TC-301: 上下文连续性测试
```yaml
Test ID: TC-301
Name: Multi-turn context retention
Priority: P0
Category: Context Management

Scenario:
  Turn 1: "客厅的灯在哪里？"
  Turn 2: "把它打开"
  Turn 3: "现在状态如何？"
  Turn 4: "调到 50% 亮度"

Expected Workflow:
  Turn 1:
    - search_devices("客厅 灯") → device_id = "abc123"
    - AI stores: context.device_id = "abc123"

  Turn 2:
    - AI resolves "它" → device_id = "abc123" (FROM CONTEXT)
    - execute_commands(device_id="abc123", ...)
    - NO search_devices call!

  Turn 3:
    - AI resolves context → device_id = "abc123"
    - get_device_status(device_id="abc123")
    - NO search_devices call!

  Turn 4:
    - AI resolves context → device_id = "abc123"
    - execute_commands(device_id="abc123", commands=[{
        capability: "switchLevel",
        command: "setLevel",
        arguments: [50]
      }])

Assertions:
  - turn1_tool_calls == 1  # search only
  - turn2_tool_calls == 1  # execute only
  - turn3_tool_calls == 1  # status only
  - turn4_tool_calls == 1  # execute only
  - total_search_calls == 1  # 只在 Turn 1 搜索
  - total_tokens_all_turns < 3000

Success Criteria:
  ✓ 正确维护设备上下文
  ✓ 避免重复搜索
  ✓ 正确解析代词（它、这个、那个）
  ✓ Token 消耗符合预期
```

#### TC-302: 上下文切换测试
```yaml
Test ID: TC-302
Name: Context switching between devices
Priority: P1
Category: Context Management

Scenario:
  Turn 1: "打开客厅的灯"
  Turn 2: "打开卧室的空调"
  Turn 3: "把客厅的灯关掉"
  Turn 4: "空调调到 24 度"

Expected Workflow:
  Turn 1:
    - search_devices("客厅 灯") → living_room_light
    - execute_commands(living_room_light, "on")
    - context.current_device = living_room_light

  Turn 2:
    - search_devices("卧室 空调") → bedroom_ac
    - execute_commands(bedroom_ac, "on")
    - context.current_device = bedroom_ac

  Turn 3:
    - AI recognizes "客厅的灯" (not current device)
    - Uses cached living_room_light from Turn 1
    - execute_commands(living_room_light, "off")

  Turn 4:
    - AI resolves "空调" → bedroom_ac (current context)
    - execute_commands(bedroom_ac, setTemperature: 24)

Assertions:
  - context_switching_correct == True
  - no_redundant_searches == True
  - total_search_calls == 2  # 只在 Turn 1 和 Turn 2
```

---

### 3.2 复杂场景测试

#### TC-311: 多步骤场景
```yaml
Test ID: TC-311
Name: Complex multi-step scenario
Priority: P0
Category: Complex Flow

Scenario: "关闭所有灯，然后打开客厅的电视，把空调调到 24 度"

Expected Workflow:
  Task 1: 关闭所有灯
    - search_devices("灯")
    - batch_execute_commands([{..., command: "off"}, ...])

  Task 2: 打开客厅的电视
    - search_devices("客厅 电视")
    - execute_commands(..., command: "on")

  Task 3: 空调调到 24 度
    - search_devices("空调")
    - execute_commands(..., command: "setTemperature", arguments: [24])

Assertions:
  - task_decomposition_correct == True
  - tasks_executed_in_order == True
  - total_tool_calls <= 6  # 3 searches + 3 executions
  - all_tasks_completed == True

Success Criteria:
  ✓ 正确分解任务
  ✓ 按顺序执行
  ✓ 所有任务成功完成
```

#### TC-312: 异常恢复场景
```yaml
Test ID: TC-312
Name: Error recovery and graceful degradation
Priority: P1
Category: Error Handling

Scenario: "打开客厅的洗衣机"（假设不存在）

Expected Workflow:
  Step 1: search_devices("客厅 洗衣机")
    → Returns: []

  Step 2: [AI recognizes error]

  Fallback Option A: 扩大搜索范围
    - search_devices("洗衣机")
    → Returns: [{id: "washer123", room: "阳台", ...}]
    → AI: "没找到客厅的洗衣机，但在阳台找到洗衣机，是这个吗？"

  Fallback Option B: 提示用户
    → AI: "抱歉，没有找到客厅的洗衣机。您可以使用以下命令查看所有设备..."

Assertions:
  - error_handled_gracefully == True
  - no_exception_thrown == True
  - user_receives_helpful_message == True
```

---

### 3.3 性能压力测试

#### TC-321: 大规模设备环境
```yaml
Test ID: TC-321
Name: Performance test with large device set
Priority: P1
Category: Performance

Setup:
  - 模拟 100+ 设备的家庭环境
  - 10 个房间
  - 多种设备类型

Scenario: "打开主卧的床头灯"

Constraints:
  - MUST NOT call get_devices() without filters
  - MUST use search_devices for targeting

Assertions:
  - total_tokens < 1500
  - execution_time < 2s
  - memory_usage < 100MB
  - search_efficiency > 95%  # 正确设备在前 5 个结果中

Success Criteria:
  ✓ 即使有 100+ 设备，仍能高效定位
  ✓ Token 消耗不随设备数量线性增长
```

#### TC-322: 连续对话压力测试
```yaml
Test ID: TC-322
Name: Extended conversation stress test
Priority: P1
Category: Performance

Scenario: 连续 10 轮对话

Turn 1-10: 各种控制、查询、分析任务

Assertions:
  - total_tokens_all_turns < 10000
  - avg_tokens_per_turn < 1000
  - context_cleanup_working == True  # 老旧信息被清理
  - cache_hit_rate > 80%  # Prompt cache 命中率

Success Criteria:
  ✓ 长对话不导致上下文爆炸
  ✓ 缓存有效利用
  ✓ 响应时间稳定
```

---

## 测试实施指南

### 测试优先级

**Week 1（必须完成）:**
- ✅ TC-101, TC-102, TC-103 (search_devices)
- ✅ TC-201, TC-202 (简单流程)
- ✅ TC-301 (多轮对话)

**Week 2（建议完成）:**
- ✅ TC-111, TC-112 (get_device_commands)
- ✅ TC-211, TC-212 (条件控制)
- ✅ TC-221 (批量控制)
- ✅ TC-231 (历史数据)

**Week 3（增强）:**
- ✅ TC-311, TC-312 (复杂场景)
- ✅ TC-321, TC-322 (性能测试)

### 测试框架示例

```python
# test/test_agent_integration.py

import pytest
from unittest.mock import Mock, patch
from src.api import Location
from src.server import mcp

class TestSimpleControlFlow:
    def test_tc_201_simple_device_control(self):
        """TC-201: 单设备简单控制"""
        # Arrange
        mock_location = Mock(spec=Location)
        mock_location.search_devices.return_value = [
            {"id": "abc123", "name": "客厅吸顶灯", "room": "客厅", "type": "switch"}
        ]
        mock_location.device_commands.return_value = {"status": "ACCEPTED"}

        # Act
        with patch('src.server.location', mock_location):
            # 模拟 AI 调用
            devices = mcp.call_tool("search_devices", query="客厅 灯")
            result = mcp.call_tool("execute_commands",
                device_id="abc123",
                commands=[{"component": "main", "capability": "switch", "command": "on"}]
            )

        # Assert
        assert len(devices) == 1
        assert devices[0]["name"] == "客厅吸顶灯"
        assert result["status"] == "ACCEPTED"
        assert mock_location.search_devices.call_count == 1
        assert mock_location.device_commands.call_count == 1
```

### 自动化测试脚本

```bash
# scripts/run_tests.sh

#!/bin/bash

echo "Running Level 1 Tests..."
pytest test/test_tools.py -v

echo "Running Level 2 Tests..."
pytest test/test_workflows.py -v

echo "Running Level 3 Tests..."
pytest test/test_integration.py -v

echo "Running Performance Tests..."
pytest test/test_performance.py -v --benchmark-only

echo "Generating Coverage Report..."
pytest --cov=src --cov-report=html

echo "Token Usage Analysis..."
python scripts/analyze_token_usage.py
```

---

## 成功指标

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 工具调用准确率 | > 95% | Level 2 测试 |
| 上下文复用率 | > 80% | TC-301, TC-302 |
| Token 效率 | < 2000/轮 | 所有测试 |
| 错误恢复率 | 100% | TC-312 |
| 性能稳定性 | < 2s 响应 | TC-321, TC-322 |

---

## 下一步

👉 阅读 [04-context-management.md](04-context-management.md) 了解如何优化上下文消耗
