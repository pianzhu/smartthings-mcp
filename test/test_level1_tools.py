"""
Level 1: 单工具基础测试

根据 solution/03-test-cases.md 实现单工具验证测试
"""

from framework import (
    TestFramework, TestCase, TestPriority, TestCategory, ToolCall,
    MockMCPServer, MockDevice,
    assert_tool_call_count, assert_device_found, assert_command_success,
    assert_device_count, assert_all_devices_in_room, assert_no_errors,
    assert_result_contains, combine_assertions
)


def create_level1_tests() -> TestFramework:
    """创建 Level 1 测试套件"""
    framework = TestFramework()
    mock_server = MockMCPServer()
    framework.set_mock_server(mock_server)

    # ==================== 1.1 search_devices 测试 ====================

    # TC-101: 基础搜索 - 房间 + 设备类型
    framework.register_test(TestCase(
        test_id="TC-101",
        name="Search devices by room and type",
        priority=TestPriority.P0,
        category=TestCategory.UNIT,
        description="测试基础的房间+设备类型搜索功能",
        scenario="客厅 灯",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "def456", "fullId": "def456-full", "name": "客厅台灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "ghi789", "fullId": "ghi789-full", "name": "卧室台灯", "room": "卧室", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices"],
        expected_results={"device_count": 2},
        assertions=[
            assert_tool_call_count(1),
            assert_device_count(2),
            assert_device_found("客厅吸顶灯"),
            assert_device_found("客厅台灯"),
            assert_all_devices_in_room("客厅")
        ],
        max_tokens=500
    ))

    # TC-102: 模糊匹配
    framework.register_test(TestCase(
        test_id="TC-102",
        name="Fuzzy matching for device names",
        priority=TestPriority.P0,
        category=TestCategory.UNIT,
        description="测试模糊匹配功能（TV → 电视）",
        scenario="客厅 TV",
        mock_data={
            "devices": [
                {"id": "tv001", "fullId": "tv001-full", "name": "客厅电视", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "tv002", "fullId": "tv002-full", "name": "客厅 Television", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "light001", "fullId": "light001-full", "name": "客厅灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices"],
        expected_results={},
        assertions=[
            assert_tool_call_count(1),
            lambda result: len(result.tool_calls[0].result) > 0  # 至少找到一个设备
        ],
        max_tokens=500
    ))

    # TC-103: 空结果处理
    framework.register_test(TestCase(
        test_id="TC-103",
        name="Handle no matching devices",
        priority=TestPriority.P1,
        category=TestCategory.UNIT,
        description="测试无匹配设备时的处理",
        scenario="火星 灯",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["search_devices"],
        expected_results={},
        assertions=[
            assert_tool_call_count(1),
            assert_device_count(0),
            assert_no_errors()  # 不应抛出异常
        ],
        max_tokens=500
    ))

    # ==================== 1.2 get_device_commands 测试 ====================

    # TC-111: 获取开关设备命令
    framework.register_test(TestCase(
        test_id="TC-111",
        name="Get commands for switch capability",
        priority=TestPriority.P0,
        category=TestCategory.UNIT,
        description="测试获取开关设备的命令列表",
        scenario="获取 switch 能力的命令",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["get_device_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(1),
            assert_result_contains("get_device_commands", "capability", "switch"),
            lambda result: "on" in result.tool_calls[0].result.get("commands", []),
            lambda result: "off" in result.tool_calls[0].result.get("commands", [])
        ],
        max_tokens=500
    ))

    # TC-112: 不支持的能力
    framework.register_test(TestCase(
        test_id="TC-112",
        name="Handle unsupported capability",
        priority=TestPriority.P1,
        category=TestCategory.UNIT,
        description="测试查询设备不支持的能力时的错误处理",
        scenario="查询不支持的 thermostat 能力",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["get_device_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(1),
            lambda result: "error" in result.tool_calls[0].result or result.tool_calls[0].result.get("commands", []) == []
        ],
        max_tokens=500
    ))

    # ==================== 1.3 batch_execute_commands 测试 ====================

    # TC-121: 批量执行成功
    framework.register_test(TestCase(
        test_id="TC-121",
        name="Batch execute commands on multiple devices",
        priority=TestPriority.P0,
        category=TestCategory.UNIT,
        description="测试批量执行命令功能",
        scenario="批量关闭多个设备",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]},
                {"id": "def456", "fullId": "def456-full", "name": "客厅台灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["batch_execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(1),
            assert_result_contains("batch_execute_commands", "total", 2),
            assert_result_contains("batch_execute_commands", "success", 2),
            lambda result: all(r.get("status") == "ACCEPTED" for r in result.tool_calls[0].result.get("results", []))
        ],
        max_tokens=800
    ))

    # TC-122: 部分失败处理
    framework.register_test(TestCase(
        test_id="TC-122",
        name="Handle partial failures in batch execution",
        priority=TestPriority.P1,
        category=TestCategory.UNIT,
        description="测试批量执行中部分设备失败的情况",
        scenario="批量执行，其中一个设备 ID 无效",
        mock_data={
            "devices": [
                {"id": "abc123", "fullId": "abc123-full", "name": "客厅吸顶灯", "room": "客厅", "type": "switch", "capabilities": ["switch"]}
            ]
        },
        expected_tool_calls=["batch_execute_commands"],
        expected_results={},
        assertions=[
            assert_tool_call_count(1),
            assert_result_contains("batch_execute_commands", "total", 2),
            lambda result: result.tool_calls[0].result.get("success", 0) < 2,  # 不是全部成功
            lambda result: any(r.get("status") == "FAILED" for r in result.tool_calls[0].result.get("results", []))
        ],
        max_tokens=800
    ))

    return framework


# ==================== 测试执行器 ====================

class Level1TestRunner(TestFramework):
    """Level 1 测试运行器

    继承 TestFramework 并实现实际的测试场景执行
    """

    def _execute_scenario(self, test_case: TestCase, tool_calls: list):
        """执行测试场景"""
        if not self.mock_server:
            raise RuntimeError("Mock server not set")

        # 根据测试场景执行不同的工具调用
        if "search_devices" in test_case.expected_tool_calls:
            result = self.mock_server.search_devices(test_case.scenario)
            tool_calls.append(ToolCall(
                tool_name="search_devices",
                parameters={"query": test_case.scenario},
                result=result,
                timestamp=0,
                token_count=100  # Mock token count
            ))

        if "get_device_commands" in test_case.expected_tool_calls:
            # 从 mock_data 获取设备 ID
            device_id = test_case.mock_data.get("devices", [{}])[0].get("id", "abc123")

            # 从 scenario 提取 capability（简化处理）
            capability = "switch"
            if "thermostat" in test_case.scenario:
                capability = "thermostat"

            result = self.mock_server.get_device_commands(device_id, capability)
            tool_calls.append(ToolCall(
                tool_name="get_device_commands",
                parameters={"device_id": device_id, "capability": capability},
                result=result,
                timestamp=0,
                token_count=80
            ))

        if "batch_execute_commands" in test_case.expected_tool_calls:
            # 构造批量执行的操作
            operations = []

            # TC-121: 正常的两个设备
            if test_case.test_id == "TC-121":
                operations = [
                    {"device_id": "abc123", "commands": [{"component": "main", "capability": "switch", "command": "off"}]},
                    {"device_id": "def456", "commands": [{"component": "main", "capability": "switch", "command": "off"}]}
                ]
            # TC-122: 一个有效，一个无效
            elif test_case.test_id == "TC-122":
                operations = [
                    {"device_id": "abc123", "commands": [{"component": "main", "capability": "switch", "command": "off"}]},
                    {"device_id": "invalid_id", "commands": [{"component": "main", "capability": "switch", "command": "off"}]}
                ]

            result = self.mock_server.batch_execute_commands(operations)
            tool_calls.append(ToolCall(
                tool_name="batch_execute_commands",
                parameters={"operations": operations},
                result=result,
                timestamp=0,
                token_count=200
            ))


if __name__ == "__main__":
    # 创建并运行测试
    framework = create_level1_tests()

    # 将测试用例转移到 Level1TestRunner
    runner = Level1TestRunner()
    runner.set_mock_server(framework.mock_server)
    runner.test_cases = framework.test_cases

    # 运行所有 Level 1 测试
    print("="*60)
    print("LEVEL 1: 单工具基础测试")
    print("="*60)

    results = runner.run_all(category=TestCategory.UNIT)

    # 生成报告
    print(runner.generate_report())
