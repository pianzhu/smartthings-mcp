"""
测试框架模块

提供测试基础设施，包括：
- 基础测试类
- Mock 工具
- 测试数据定义
- 断言辅助函数
"""

from .base import (
    TestFramework, TestCase, TestResult,
    TestPriority, TestCategory, ToolCall
)
from .mock_tools import MockMCPServer, MockDevice
from .assertions import (
    assert_tool_calls, assert_device_found, assert_command_success,
    assert_tool_call_count, assert_specific_tool_call_count,
    assert_device_count, assert_all_devices_in_room, assert_no_errors,
    assert_result_contains, combine_assertions
)

__all__ = [
    # Base classes
    'TestFramework',
    'TestCase',
    'TestResult',
    'TestPriority',
    'TestCategory',
    'ToolCall',
    # Mock tools
    'MockMCPServer',
    'MockDevice',
    # Assertions
    'assert_tool_calls',
    'assert_device_found',
    'assert_command_success',
    'assert_tool_call_count',
    'assert_specific_tool_call_count',
    'assert_device_count',
    'assert_all_devices_in_room',
    'assert_no_errors',
    'assert_result_contains',
    'combine_assertions',
]
