# SmartThings MCP 测试框架

这是一个完整的测试框架，用于测试 SmartThings MCP server 的功能。

## 测试架构

```
test/
├── framework/                    # 测试框架核心
│   ├── __init__.py              # 导出公共接口
│   ├── base.py                  # 基础测试类和测试结果
│   ├── mock_tools.py            # Mock MCP Server 和设备
│   └── assertions.py            # 断言辅助函数
├── test_level1_tools.py         # Level 1: 单工具基础测试
├── test_level2_workflows.py     # Level 2: 多工具组合测试
├── test_level3_integration.py   # Level 3: 端到端集成测试
├── run_all_tests.py             # 统一测试运行器
└── README.md                    # 本文档
```

## 测试策略

### Level 1: 单工具基础测试（6 个测试）
- TC-101: 基础搜索 - 房间 + 设备类型
- TC-102: 模糊匹配
- TC-103: 空结果处理
- TC-111: 获取开关设备命令
- TC-112: 不支持的能力
- TC-121: 批量执行成功
- TC-122: 部分失败处理

### Level 2: 多工具组合测试（3 个测试）
- TC-201: 单设备简单控制
- TC-221: 批量设备控制（batch_execute_commands）
- TC-221-alt: 批量设备控制（并行 execute_commands）

**注意**: 跳过查询设备状态的测试（TC-202, TC-211, TC-212, TC-231）

### Level 3: 端到端集成测试（4 个测试）
- TC-301: 多轮对话上下文（仅控制命令）
- TC-302: 上下文切换
- TC-311: 复杂多步骤场景
- TC-312: 异常恢复

**注意**: TC-301 修改为跳过 Turn 3 的状态查询

## 快速开始

### 运行所有测试

```bash
cd test
python run_all_tests.py
```

### 运行单个级别的测试

```bash
# Level 1
python test_level1_tools.py

# Level 2
python test_level2_workflows.py

# Level 3
python test_level3_integration.py
```

## 测试输出

测试运行后会生成：

1. **终端输出**: 详细的测试执行过程和结果
2. **test_report.json**: JSON 格式的详细报告

### 示例输出

```
======================================================================
SmartThings MCP 测试套件
运行时间: 2025-11-14 10:30:00
======================================================================

----------------------------------------------------------------------
LEVEL 1: 单工具基础测试
----------------------------------------------------------------------
Running TC-101: Search devices by room and type...
  ✅ PASS | TC-101 | Search devices by room and type | 0.001s | 100 tokens

...

======================================================================
综合测试报告
======================================================================

Level 1: 单工具基础测试:
  Tests: 7 | ✅ Passed: 7 | ❌ Failed: 0
  Time: 0.05s | Tokens: 600
  Pass Rate: 100.0%

Level 2: 多工具组合测试:
  Tests: 3 | ✅ Passed: 3 | ❌ Failed: 0
  Time: 0.03s | Tokens: 450
  Pass Rate: 100.0%

Level 3: 端到端集成测试:
  Tests: 4 | ✅ Passed: 4 | ❌ Failed: 0
  Time: 0.06s | Tokens: 800
  Pass Rate: 100.0%

----------------------------------------------------------------------
总计:
  总测试数: 14
  ✅ 通过: 14 (100.0%)
  ❌ 失败: 0 (0.0%)
  总时间: 0.14s
  总 Token: 1850
  平均 Token/测试: 132.1

======================================================================
详细报告已导出到: test/test_report.json
======================================================================
```

## 如何添加新的测试用例

### 步骤 1: 定义测试用例

```python
from framework import (
    TestCase, TestPriority, TestCategory,
    assert_tool_call_count, assert_device_found
)

# 创建测试用例
test_case = TestCase(
    test_id="TC-XXX",
    name="你的测试名称",
    priority=TestPriority.P0,  # P0 / P1 / P2
    category=TestCategory.UNIT,  # UNIT / WORKFLOW / INTEGRATION
    description="测试描述",
    scenario="用户输入场景",
    mock_data={
        "devices": [
            {
                "id": "device123",
                "fullId": "device123-full",
                "name": "设备名称",
                "room": "房间",
                "type": "switch",
                "capabilities": ["switch"]
            }
        ]
    },
    expected_tool_calls=["search_devices", "execute_commands"],
    expected_results={},
    assertions=[
        assert_tool_call_count(2),
        assert_device_found("设备名称")
    ],
    max_tokens=1000,
    max_execution_time=2.0
)

# 注册到框架
framework.register_test(test_case)
```

### 步骤 2: 实现测试执行逻辑

在对应的 TestRunner 类中实现 `_execute_scenario` 方法：

```python
def _execute_scenario(self, test_case: TestCase, tool_calls: list):
    if test_case.test_id == "TC-XXX":
        # Step 1: 搜索设备
        result = self.mock_server.search_devices("客厅 灯")
        tool_calls.append(ToolCall(
            tool_name="search_devices",
            parameters={"query": "客厅 灯"},
            result=result,
            timestamp=0,
            token_count=100
        ))

        # Step 2: 执行命令
        device_id = result[0]["id"]
        result = self.mock_server.execute_commands(
            device_id,
            [{"component": "main", "capability": "switch", "command": "on"}]
        )
        tool_calls.append(ToolCall(
            tool_name="execute_commands",
            parameters={"device_id": device_id, "commands": [...]},
            result=result,
            timestamp=0,
            token_count=150
        ))
```

### 步骤 3: 运行测试

```bash
python test_levelX_xxx.py
```

## 可用的断言函数

测试框架提供了丰富的断言函数：

```python
# 工具调用相关
assert_tool_call_count(expected_count)              # 总调用次数
assert_tool_calls(expected_sequence)                # 调用顺序
assert_specific_tool_call_count(tool_name, count)   # 特定工具调用次数

# 设备相关
assert_device_found(device_name)                    # 找到特定设备
assert_device_count(expected_count)                 # 设备数量
assert_all_devices_in_room(room_name)              # 所有设备在同一房间

# 命令执行相关
assert_command_success()                            # 命令执行成功
assert_result_contains(tool_name, key, value)      # 结果包含特定值

# 性能相关
assert_max_tokens(max_tokens)                       # Token 限制
assert_execution_time(max_seconds)                  # 执行时间限制

# 错误处理相关
assert_no_errors()                                  # 无错误

# 组合断言
combine_assertions(assertion1, assertion2, ...)     # 组合多个断言
```

## Mock MCP Server

Mock server 支持以下工具：

### 1. search_devices
```python
result = mock_server.search_devices(query="客厅 灯", limit=10)
# Returns: List[Dict] - 设备列表
```

### 2. get_device_commands
```python
result = mock_server.get_device_commands(device_id="abc123", capability="switch")
# Returns: Dict - 命令和属性信息
```

### 3. execute_commands
```python
result = mock_server.execute_commands(
    device_id="abc123",
    commands=[{"component": "main", "capability": "switch", "command": "on"}]
)
# Returns: Dict - 执行结果
```

### 4. batch_execute_commands
```python
result = mock_server.batch_execute_commands(
    operations=[
        {"device_id": "abc123", "commands": [...]},
        {"device_id": "def456", "commands": [...]}
    ]
)
# Returns: Dict - 批量执行结果
```

## 支持的设备能力

Mock server 预配置了以下能力：

- **switch**: on, off
- **switchLevel**: setLevel
- **lock**: lock, unlock
- **thermostat**: setHeatingSetpoint, setCoolingSetpoint, setThermostatMode

## 扩展测试框架

### 添加新的 Mock 能力

编辑 `framework/mock_tools.py`，在 `capabilities_map` 中添加：

```python
self.capabilities_map["新能力"] = {
    "commands": ["command1", "command2"],
    "attributes": {
        "attribute1": {"type": "string", "values": ["val1", "val2"]}
    }
}
```

### 添加自定义断言

在 `framework/assertions.py` 中添加新的断言函数：

```python
def assert_custom_condition() -> Callable[[TestResult], bool]:
    """你的自定义断言"""
    def assertion(result: TestResult) -> bool:
        # 实现你的断言逻辑
        return True
    return assertion
```

## 测试用例 ID 规范

- **TC-1XX**: Level 1 - 单工具测试
  - TC-10X: search_devices
  - TC-11X: get_device_commands
  - TC-12X: batch_execute_commands

- **TC-2XX**: Level 2 - 多工具组合
  - TC-20X: 简单控制流程
  - TC-22X: 批量控制流程

- **TC-3XX**: Level 3 - 端到端集成
  - TC-30X: 多轮对话
  - TC-31X: 复杂场景

## 注意事项

1. **不测试查询状态**: 根据需求，所有涉及 `get_device_status` 和 `get_device_history` 的测试都被跳过

2. **Token 计数**: 当前是 Mock 值，实际集成时需要从真实 API 获取

3. **执行时间**: Mock 测试执行很快，实际 API 调用会更慢

4. **Mock 数据**: 在 `mock_data` 中定义，确保符合实际 API 格式

## 参考文档

- [solution/03-test-cases.md](../solution/03-test-cases.md) - 完整测试用例规范
- [framework/base.py](framework/base.py) - 框架核心实现
- [framework/assertions.py](framework/assertions.py) - 所有可用断言

## 问题反馈

如果遇到问题或需要添加新功能，请检查：
1. Mock 数据是否正确配置
2. 断言函数是否符合预期
3. 测试执行逻辑是否正确实现
