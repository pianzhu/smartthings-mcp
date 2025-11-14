"""
Level 2: 多工具组合测试

根据 solution/03-test-cases.md 实现多工具交互测试
注意：跳过所有查询设备状态的测试（TC-202, TC-211, TC-212, TC-231）
"""

from framework import (
    TestFramework, TestCase, TestPriority, TestCategory, ToolCall,
    MockMCPServer, MockDevice,
    assert_tool_call_count, assert_device_found, assert_command_success,
    assert_specific_tool_call_count, combine_assertions
)


def create_level2_tests() -> TestFramework:
    """创建 Level 2 测试套件"""
    framework = TestFramework()
    mock_server = MockMCPServer()
    framework.set_mock_server(mock_server)

    # ==================== 2.1 简单控制流程 ====================

    # TC-201: 单设备简单控制
    framework.register_test(TestCase(
        test_id="TC-201",
        name="Simple device control workflow",
        priority=TestPriority.P0,
        category=TestCategory.WORKFLOW,
        description="测试单设备简单控制流程",
        scenario="打开客厅的灯",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices", "execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(2),
            assert_specific_tool_call_count("search_devices", 1),
            assert_specific_tool_call_count("execute_commands", 1),
            assert_device_found("客厅吸顶灯"),
            assert_command_success()
        ],
        max_tokens=1000,
        max_execution_time=2.0
    ))

    # 注意：TC-202 (设备状态查询) 被跳过，因为用户要求不测试查询设备状态

    # ==================== 2.3 批量控制流程 ====================

    # TC-221: 批量设备控制
    framework.register_test(TestCase(
        test_id="TC-221",
        name="Batch control multiple devices",
        priority=TestPriority.P0,
        category=TestCategory.WORKFLOW,
        description="测试批量控制多个设备的流程",
        scenario="关闭客厅所有的灯",
        mock_data={
            "devices": [
                {"id": "light1", "fullId": "light1-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "light2", "fullId": "light2-full", "name": "客厅台灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "light3", "fullId": "light3-full", "name": "客厅氛围灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices", "batch_execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(2),
            assert_specific_tool_call_count("search_devices", 1),
            assert_specific_tool_call_count("batch_execute_commands", 1),
            lambda result: len([call for call in result.tool_calls if call.tool_name == "search_devices"][0].result) == 3,
            lambda result: [call for call in result.tool_calls if call.tool_name == "batch_execute_commands"][0].result.get("success") == 3
        ],
        max_tokens=2000,
        max_execution_time=3.0
    ))

    # TC-221-alt: 批量设备控制（使用并行 execute_commands）
    framework.register_test(TestCase(
        test_id="TC-221-alt",
        name="Batch control with parallel execute_commands",
        priority=TestPriority.P1,
        category=TestCategory.WORKFLOW,
        description="测试使用并行 execute_commands 控制多个设备",
        scenario="关闭客厅所有的灯（并行执行）",
        mock_data={
            "devices": [
                {"id": "light1", "fullId": "light1-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "light2", "fullId": "light2-full", "name": "客厅台灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "light3", "fullId": "light3-full", "name": "客厅氛围灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices", "execute_commands", "execute_commands", "execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(4),
            assert_specific_tool_call_count("search_devices", 1),
            assert_specific_tool_call_count("execute_commands", 3),
            assert_command_success()
        ],
        max_tokens=2000,
        max_execution_time=3.0
    ))

    return framework


# ==================== 测试执行器 ====================

class Level2TestRunner(TestFramework):
    """Level 2 测试运行器"""

    def _execute_scenario(self, test_case: TestCase, tool_calls: list):
        """执行测试场景"""
        if not self.mock_server:
            raise RuntimeError("Mock server not set")

        # TC-201: 单设备简单控制
        if test_case.test_id == "TC-201":
            # Step 1: search_devices
            result = self.mock_server.search_devices("客厅 灯")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 灯"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            # Step 2: execute_commands
            device_id = result[0]["id"]
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

        # TC-221: 批量设备控制（使用 batch_execute_commands）
        elif test_case.test_id == "TC-221":
            # Step 1: search_devices
            result = self.mock_server.search_devices("客厅 灯")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 灯"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            # Step 2: batch_execute_commands
            operations = [
                {"device_id": device["id"], "commands": [{"component": "main", "capability": "switch", "command": "off"}]}
                for device in result
            ]
            result = self.mock_server.batch_execute_commands(operations)
            tool_calls.append(ToolCall(
                tool_name="batch_execute_commands",
                parameters={"operations": operations},
                result=result,
                timestamp=0,
                token_count=300
            ))

        # TC-221-alt: 批量设备控制（使用并行 execute_commands）
        elif test_case.test_id == "TC-221-alt":
            # Step 1: search_devices
            result = self.mock_server.search_devices("客厅 灯")
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": "客厅 灯"},
                result=result,
                timestamp=0,
                token_count=100
            ))

            # Step 2-4: 并行 execute_commands
            for device in result:
                exec_result = self.mock_server.execute_commands(
                    device["id"],
                    [{"component": "main", "capability": "switch", "command": "off"}]
                )
                tool_calls.append(ToolCall(
                    tool_name="execute_commands",
                    parameters={"device_id": device["id"], "commands": [{"capability": "switch", "command": "off"}]},
                    result=exec_result,
                    timestamp=0,
                    token_count=150
                ))


if __name__ == "__main__":
    # 创建并运行测试
    framework = create_level2_tests()

    # 将测试用例转移到 Level2TestRunner
    runner = Level2TestRunner()
    runner.set_mock_server(framework.mock_server)
    runner.test_cases = framework.test_cases

    # 运行所有 Level 2 测试
    print("="*60)
    print("LEVEL 2: 多工具组合测试")
    print("注意：跳过查询设备状态的测试（TC-202, TC-211, TC-212, TC-231）")
    print("="*60)

    results = runner.run_all(category=TestCategory.WORKFLOW)

    # 生成报告
    print(runner.generate_report())
