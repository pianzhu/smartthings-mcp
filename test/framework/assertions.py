"""
测试断言辅助函数

提供常用的断言函数，简化测试用例编写
"""

from typing import List, Callable
from .base import TestResult


def assert_tool_calls(expected_sequence: List[str]) -> Callable[[TestResult], bool]:
    """断言工具调用顺序"""
    def assertion(result: TestResult) -> bool:
        actual_sequence = [call.tool_name for call in result.tool_calls]
        return actual_sequence == expected_sequence
    return assertion


def assert_tool_call_count(expected_count: int) -> Callable[[TestResult], bool]:
    """断言工具调用总次数"""
    def assertion(result: TestResult) -> bool:
        return len(result.tool_calls) == expected_count
    return assertion


def assert_specific_tool_call_count(tool_name: str, expected_count: int) -> Callable[[TestResult], bool]:
    """断言特定工具的调用次数"""
    def assertion(result: TestResult) -> bool:
        actual_count = sum(1 for call in result.tool_calls if call.tool_name == tool_name)
        return actual_count == expected_count
    return assertion


def assert_device_found(device_name: str) -> Callable[[TestResult], bool]:
    """断言找到了指定设备"""
    def assertion(result: TestResult) -> bool:
        # 查找 search_devices 调用的结果
        for call in result.tool_calls:
            if call.tool_name == "search_devices":
                devices = call.result or []
                return any(device_name in device.get("name", "") for device in devices)
        return False
    return assertion


def assert_command_success() -> Callable[[TestResult], bool]:
    """断言命令执行成功"""
    def assertion(result: TestResult) -> bool:
        # 查找 execute_commands 调用的结果
        for call in result.tool_calls:
            if call.tool_name == "execute_commands":
                status = call.result.get("status")
                if status != "ACCEPTED":
                    return False
        return True
    return assertion


def assert_max_tokens(max_tokens: int) -> Callable[[TestResult], bool]:
    """断言 token 消耗不超过限制"""
    def assertion(result: TestResult) -> bool:
        return result.total_tokens <= max_tokens
    return assertion


def assert_execution_time(max_seconds: float) -> Callable[[TestResult], bool]:
    """断言执行时间不超过限制"""
    def assertion(result: TestResult) -> bool:
        return result.execution_time <= max_seconds
    return assertion


def assert_no_errors() -> Callable[[TestResult], bool]:
    """断言没有错误"""
    def assertion(result: TestResult) -> bool:
        # 检查所有工具调用结果中是否有错误
        for call in result.tool_calls:
            if isinstance(call.result, dict) and "error" in call.result:
                return False
        return True
    return assertion


def assert_result_contains(tool_name: str, key: str, expected_value) -> Callable[[TestResult], bool]:
    """断言工具调用结果包含特定值"""
    def assertion(result: TestResult) -> bool:
        for call in result.tool_calls:
            if call.tool_name == tool_name:
                if isinstance(call.result, dict):
                    return call.result.get(key) == expected_value
        return False
    return assertion


def assert_device_count(expected_count: int) -> Callable[[TestResult], bool]:
    """断言找到的设备数量"""
    def assertion(result: TestResult) -> bool:
        for call in result.tool_calls:
            if call.tool_name == "search_devices":
                devices = call.result or []
                return len(devices) == expected_count
        return False
    return assertion


def assert_all_devices_in_room(room_name: str) -> Callable[[TestResult], bool]:
    """断言所有找到的设备都在指定房间"""
    def assertion(result: TestResult) -> bool:
        for call in result.tool_calls:
            if call.tool_name == "search_devices":
                devices = call.result or []
                return all(device.get("room") == room_name for device in devices)
        return False
    return assertion


def combine_assertions(*assertions: Callable[[TestResult], bool]) -> Callable[[TestResult], bool]:
    """组合多个断言"""
    def combined(result: TestResult) -> bool:
        return all(assertion(result) for assertion in assertions)
    return combined
