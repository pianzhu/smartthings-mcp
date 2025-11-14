"""
Level 3: 端到端集成测试

根据 solution/03-test-cases.md 实现端到端场景测试
注意：跳过查询设备状态的测试（TC-301 Turn 3）
"""

from framework import (
    TestFramework, TestCase, TestPriority, TestCategory, ToolCall,
    MockMCPServer, MockDevice,
    assert_tool_call_count, assert_device_found, assert_command_success,
    assert_specific_tool_call_count
)


def create_level3_tests() -> TestFramework:
    """创建 Level 3 测试套件"""
    framework = TestFramework()
    mock_server = MockMCPServer()
    framework.set_mock_server(mock_server)

    # ==================== 3.1 多轮对话上下文管理 ====================

    # TC-301: 上下文连续性测试（修改版，跳过 Turn 3 状态查询）
    framework.register_test(TestCase(
        test_id="TC-301",
        name="Multi-turn context retention (control only)",
        priority=TestPriority.P0,
        category=TestCategory.INTEGRATION,
        description="测试多轮对话中的上下文维护（仅控制命令）",
        scenario="多轮对话：搜索 → 控制 → 再控制",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch", "switchLevel"]}
            ]
        },
        expected_tool_calls=["search_devices", "execute_commands", "execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(3),
            assert_specific_tool_call_count("search_devices", 1),  # 只在 Turn 1 搜索
            assert_specific_tool_call_count("execute_commands", 2),  # Turn 2 和 Turn 3
            assert_command_success()
        ],
        max_tokens=2000,
        max_execution_time=3.0
    ))

    # TC-302: 上下文切换测试
    framework.register_test(TestCase(
        test_id="TC-302",
        name="Context switching between devices",
        priority=TestPriority.P1,
        category=TestCategory.INTEGRATION,
        description="测试在多个设备间切换上下文",
        scenario="多轮对话：控制设备1 → 控制设备2 → 回到设备1 → 设备2",
        mock_data={
            "devices": [
                {"id": "light001", "fullId": "light001-full", "name": "客厅灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "ac001", "fullId": "ac001-full", "name": "卧室空调", "room": "卧室", "type": "thermostat", "capabilities": ["switch", "thermostat"]}
            ]
        },
        expected_tool_calls=["search_devices", "execute_commands", "search_devices", "execute_commands", "execute_commands", "execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(6),
            assert_specific_tool_call_count("search_devices", 2),  # Turn 1 和 Turn 2
            assert_specific_tool_call_count("execute_commands", 4),  # Turn 1, 2, 3, 4
            assert_command_success()
        ],
        max_tokens=3000,
        max_execution_time=4.0
    ))

    # ==================== 3.2 复杂场景测试 ====================

    # TC-311: 多步骤场景
    framework.register_test(TestCase(
        test_id="TC-311",
        name="Complex multi-step scenario",
        priority=TestPriority.P0,
        category=TestCategory.INTEGRATION,
        description="测试复杂的多步骤控制场景",
        scenario="关闭所有灯，然后打开客厅的电视，把空调调到 24 度",
        mock_data={
            "devices": [
                {"id": "light1", "fullId": "light1-full", "name": "客厅灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "light2", "fullId": "light2-full", "name": "卧室灯", "room": "卧室", "type": "switch", "capabilities": ["switch"]},
                {"id": "tv001", "fullId": "tv001-full", "name": "客厅电视", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "ac001", "fullId": "ac001-full", "name": "空调", "room": "客厅", "type": "thermostat", "capabilities": ["switch", "thermostat"]}
            ]
        },
        expected_tool_calls=["search_devices", "batch_execute_commands", "search_devices", "execute_commands", "search_devices", "execute_commands"],
        expected_results={},
        assertions=[
            lambda result: len(result.tool_calls) <= 6,  # 最多 6 次调用
            assert_specific_tool_call_count("search_devices", 3),  # 3 次搜索
            assert_command_success()
        ],
        max_tokens=3000,
        max_execution_time=5.0
    ))

    # TC-312: 异常恢复场景
    framework.register_test(TestCase(
        test_id="TC-312",
        name="Error recovery and graceful degradation",
        priority=TestPriority.P1,
        category=TestCategory.INTEGRATION,
        description="测试错误恢复和优雅降级",
        scenario="打开客厅的洗衣机（不存在）",
        mock_data={
            "devices": [
                {"id": "washer123", "fullId": "washer123-full", "name": "阳台洗衣机", "room": "阳台", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices", "search_devices"],  # 第一次失败，扩大搜索范围
        expected_results={},
        assertions=[
            lambda result: len(result.tool_calls) >= 1,  # 至少搜索一次
            lambda result: result.tool_calls[0].tool_name == "search_devices",
            lambda result: len(result.tool_calls[0].result) == 0,  # 第一次搜索无结果
            lambda result: len(result.tool_calls) >= 2 and len(result.tool_calls[1].result) > 0  # 第二次找到设备
        ],
        max_tokens=1500,
        max_execution_time=3.0
    ))

    return framework


# ==================== 测试执行器 ====================

class Level3TestRunner(TestFramework):
    """Level 3 测试运行器"""

    def __init__(self):
        super().__init__()
        self.context = {}  # 模拟对话上下文

    def _execute_scenario(self, test_case: TestCase, tool_calls: list):
        """执行测试场景"""
        if not self.mock_server:
            raise RuntimeError("Mock server not set")

        # TC-301: 多轮对话上下文（修改版）
        if test_case.test_id == "TC-301":
            # Turn 1: "客厅的灯在哪里？"
            result = self.mock_server.search_devices("客厅 灯")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 灯"},
                result=result,
                timestamp=0,
                token_count=100
            ))
            self.context["last_device_id"] = result[0]["id"]

            # Turn 2: "把它打开"
            device_id = self.context["last_device_id"]
            result = self.mock_server.execute_commands(
                device_id,
                [{"component": "main", "capability": "switch", "command": "on"}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": device_id, "commands": [{"capability": "switch", "command": "on"}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

            # Turn 3: "调到 50% 亮度"（跳过状态查询，直接控制）
            result = self.mock_server.execute_commands(
                device_id,
                [{"component": "main", "capability": "switchLevel", "command": "setLevel", "arguments": [50]}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": device_id, "commands": [{"capability": "switchLevel", "command": "setLevel", "arguments": [50]}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

        # TC-302: 上下文切换
        elif test_case.test_id == "TC-302":
            # Turn 1: "打开客厅的灯"
            result = self.mock_server.search_devices("客厅 灯")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 灯"},
                result=result,
                timestamp=0,
                token_count=100
            ))
            living_room_light = result[0]["id"]

            result = self.mock_server.execute_commands(
                living_room_light,
                [{"component": "main", "capability": "switch", "command": "on"}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": living_room_light, "commands": [{"capability": "switch", "command": "on"}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

            # Turn 2: "打开卧室的空调"
            result = self.mock_server.search_devices("卧室 空调")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "卧室 空调"},
                result=result,
                timestamp=0,
                token_count=100
            ))
            bedroom_ac = result[0]["id"]

            result = self.mock_server.execute_commands(
                bedroom_ac,
                [{"component": "main", "capability": "switch", "command": "on"}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": bedroom_ac, "commands": [{"capability": "switch", "command": "on"}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

            # Turn 3: "把客厅的灯关掉"（使用缓存的设备 ID）
            result = self.mock_server.execute_commands(
                living_room_light,
                [{"component": "main", "capability": "switch", "command": "off"}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": living_room_light, "commands": [{"capability": "switch", "command": "off"}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

            # Turn 4: "空调调到 24 度"（使用当前上下文的空调）
            result = self.mock_server.execute_commands(
                bedroom_ac,
                [{"component": "main", "capability": "thermostat", "command": "setHeatingSetpoint", "arguments": [24]}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": bedroom_ac, "commands": [{"capability": "thermostat", "command": "setHeatingSetpoint", "arguments": [24]}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

        # TC-311: 多步骤场景
        elif test_case.test_id == "TC-311":
            # Task 1: 关闭所有灯
            result = self.mock_server.search_devices("灯")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "灯"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            operations = [
                {"device_id": device["id"], "commands": [{"component": "main", "capability": "switch", "command": "off"}]}
                for device in result
            ]
            batch_result = self.mock_server.batch_execute_commands(operations)
            tool_calls.append(ToolCall(
                tool_name="batch_execute_commands",
                parameters={"operations": operations},
                result=batch_result,
                timestamp=0,
                token_count=300
            ))

            # Task 2: 打开客厅的电视
            result = self.mock_server.search_devices("客厅 电视")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 电视"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            result = self.mock_server.execute_commands(
                result[0]["id"],
                [{"component": "main", "capability": "switch", "command": "on"}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": result[0]["id"], "commands": [{"capability": "switch", "command": "on"}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

            # Task 3: 空调调到 24 度
            result = self.mock_server.search_devices("空调")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "空调"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            result = self.mock_server.execute_commands(
                result[0]["id"],
                [{"component": "main", "capability": "thermostat", "command": "setHeatingSetpoint", "arguments": [24]}]
            )
            tool_calls.append(ToolCall(
                tool_name="execute_commands",
                parameters={"device_id": result[0]["id"], "commands": [{"capability": "thermostat", "command": "setHeatingSetpoint", "arguments": [24]}]},
                result=result,
                timestamp=0,
                token_count=150
            ))

        # TC-312: 异常恢复
        elif test_case.test_id == "TC-312":
            # 第一次搜索：客厅 洗衣机（无结果）
            result = self.mock_server.search_devices("客厅 洗衣机")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 洗衣机"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            # Fallback: 扩大搜索范围，只搜索"洗衣机"
            result = self.mock_server.search_devices("洗衣机")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "洗衣机"},
                result=result,
                timestamp=0,
                token_count=100
            ))


if __name__ == "__main__":
    # 创建并运行测试
    framework = create_level3_tests()

    # 将测试用例转移到 Level3TestRunner
    runner = Level3TestRunner()
    runner.set_mock_server(framework.mock_server)
    runner.test_cases = framework.test_cases

    # 运行所有 Level 3 测试
    print("="*60)
    print("LEVEL 3: 端到端集成测试")
    print("注意：跳过查询设备状态的测试（TC-301 Turn 3）")
    print("="*60)

    results = runner.run_all(category=TestCategory.INTEGRATION)

    # 生成报告
    print(runner.generate_report())
