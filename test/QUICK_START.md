# 快速入门指南

## 5 分钟快速上手

### 1. 运行所有测试

```bash
cd /home/user/smartthings-mcp/test
python run_all_tests.py
```

### 2. 查看测试结果

测试运行后会显示：

```
======================================================================
综合测试报告
======================================================================

Level 1: 单工具基础测试:
  Tests: 7 | ✅ Passed: 5 | ❌ Failed: 2
  Time: 0.00s | Tokens: 860
  Pass Rate: 71.4%

Level 2: 多工具组合测试:
  Tests: 3 | ✅ Passed: 3 | ❌ Failed: 0
  Time: 0.00s | Tokens: 1200
  Pass Rate: 100.0%

Level 3: 端到端集成测试:
  Tests: 4 | ✅ Passed: 2 | ❌ Failed: 2
  Time: 0.00s | Tokens: 1400
  Pass Rate: 50.0%

----------------------------------------------------------------------
总计:
  总测试数: 14
  ✅ 通过: 10 (71.4%)
  ❌ 失败: 4 (28.6%)
  总时间: 0.00s
  总 Token: 3460
  平均 Token/测试: 247.1
```

### 3. 查看详细报告

```bash
cat test_report.json | python -m json.tool
```

## 添加新测试用例（简单示例）

### 步骤 1: 在 test_level1_tools.py 中添加测试

```python
# 在 create_level1_tests() 函数中添加
framework.register_test(TestCase(
    test_id="TC-104",
    name="Search by device type only",
    priority=TestPriority.P1,
    category=TestCategory.UNIT,
    description="仅按设备类型搜索",
    scenario="空调",
    mock_data={
        "devices": [
            {"id": "ac1", "fullId": "ac1-full", "name": "客厅空调", "room": "客厅", "type": "thermostat", "capabilities": ["thermostat"]},
            {"id": "ac2", "fullId": "ac2-full", "name": "卧室空调", "room": "卧室", "type": "thermostat", "capabilities": ["thermostat"]}
        ]
    },
    expected_tool_calls=["search_devices"],
    expected_results={},
    assertions=[
        assert_tool_call_count(1),
        lambda result: len(result.tool_calls[0].result) >= 2
    ],
    max_tokens=500
))
```

### 步骤 2: 在 Level1TestRunner 的 _execute_scenario 中添加处理逻辑

```python
def _execute_scenario(self, test_case: TestCase, tool_calls: list):
    if not self.mock_server:
        raise RuntimeError("Mock server not set")

    if "search_devices" in test_case.expected_tool_calls:
        result = self.mock_server.search_devices(test_case.scenario)
        tool_calls.append(ToolCall(
            tool_name="search_devices",
            parameters={"query": test_case.scenario},
            result=result,
            timestamp=0,
            token_count=100
        ))

    # ... 其他工具的处理逻辑
```

### 步骤 3: 运行测试

```bash
python test_level1_tools.py
```

## 测试框架核心概念

### 1. 测试优先级

- **P0**: 关键功能，必须通过
- **P1**: 重要功能，建议通过
- **P2**: 增强功能，可选

### 2. 测试类别

- **UNIT**: Level 1 - 单工具测试
- **WORKFLOW**: Level 2 - 多工具组合
- **INTEGRATION**: Level 3 - 端到端测试

### 3. 断言函数

最常用的断言：

```python
# 工具调用
assert_tool_call_count(2)                        # 总共调用2次
assert_specific_tool_call_count("search_devices", 1)  # search_devices 调用1次

# 设备搜索
assert_device_found("客厅灯")                    # 找到特定设备
assert_device_count(3)                           # 找到3个设备

# 命令执行
assert_command_success()                         # 命令执行成功

# 性能
assert_max_tokens(1000)                          # Token 限制
```

## 当前测试覆盖

### ✅ 已实现的测试（14个）

**Level 1** (7个):
- TC-101: 基础搜索
- TC-102: 模糊匹配
- TC-103: 空结果处理
- TC-111: 获取设备命令
- TC-112: 不支持的能力
- TC-121: 批量执行成功
- TC-122: 部分失败处理

**Level 2** (3个):
- TC-201: 单设备简单控制
- TC-221: 批量设备控制（batch）
- TC-221-alt: 批量设备控制（并行）

**Level 3** (4个):
- TC-301: 多轮对话上下文
- TC-302: 上下文切换
- TC-311: 复杂多步骤场景
- TC-312: 异常恢复

### ❌ 跳过的测试（根据需求）

所有涉及查询设备状态的测试：
- TC-202: 设备状态查询
- TC-211: 条件判断 - 温度控制
- TC-212: 条件判断 - 存在性检查
- TC-231: 历史数据查询
- TC-321: 性能测试（大规模设备）
- TC-322: 连续对话压力测试

## 下一步

1. 查看 [README.md](README.md) 了解完整文档
2. 查看 [solution/03-test-cases.md](../solution/03-test-cases.md) 了解测试规范
3. 根据需要添加更多测试用例
4. 集成到 CI/CD 流程

## 常见问题

### Q: 如何只运行 P0 优先级的测试？

修改 `run_all_tests.py` 中的调用：

```python
results = runner.run_all(priority=TestPriority.P0)
```

### Q: 如何添加新的设备能力？

编辑 `framework/mock_tools.py`，在 `MockMCPServer.__init__` 的 `capabilities_map` 中添加：

```python
self.capabilities_map["your_capability"] = {
    "commands": ["command1", "command2"],
    "attributes": {...}
}
```

### Q: 测试失败但没有详细错误信息？

在 `framework/base.py` 中的 `run_test` 方法添加 try-except 来捕获更详细的错误信息。

## 支持

查看 [README.md](README.md) 获取完整文档和详细说明。
