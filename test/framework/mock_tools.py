"""
Mock MCP Server 和设备

提供测试用的 Mock 对象
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class MockDevice:
    """Mock 设备"""
    id: str
    fullId: str
    name: str
    room: Optional[str] = None
    type: str = "switch"
    capabilities: List[str] = field(default_factory=lambda: ["switch"])
    status: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "fullId": self.fullId,
            "name": self.name,
            "room": self.room,
            "type": self.type,
            "capabilities": self.capabilities
        }


class MockMCPServer:
    """Mock MCP Server

    模拟 MCP server 的行为，用于测试
    """

    def __init__(self):
        self.devices: List[MockDevice] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.capabilities_map: Dict[str, Dict[str, Any]] = {
            "switch": {
                "commands": ["on", "off"],
                "attributes": {
                    "switch": {"type": "string", "values": ["on", "off"]}
                }
            },
            "switchLevel": {
                "commands": ["setLevel"],
                "attributes": {
                    "level": {"type": "number", "min": 0, "max": 100}
                }
            },
            "lock": {
                "commands": ["lock", "unlock"],
                "attributes": {
                    "lock": {"type": "string", "values": ["locked", "unlocked"]}
                }
            },
            "thermostat": {
                "commands": ["setHeatingSetpoint", "setCoolingSetpoint", "setThermostatMode"],
                "attributes": {
                    "temperature": {"type": "number"},
                    "heatingSetpoint": {"type": "number"},
                    "coolingSetpoint": {"type": "number"}
                }
            }
        }

    def setup_mock_data(self, mock_data: Dict[str, Any]):
        """设置 Mock 数据"""
        self.devices = []
        if "devices" in mock_data:
            for device_data in mock_data["devices"]:
                device = MockDevice(**device_data)
                self.devices.append(device)

    def reset(self):
        """重置状态"""
        self.devices = []
        self.tool_calls = []

    def search_devices(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """模拟 search_devices 工具"""
        self.tool_calls.append({
            "tool": "search_devices",
            "parameters": {"query": query, "limit": limit}
        })

        # 简单的匹配逻辑
        query_parts = query.lower().split()
        results = []

        for device in self.devices:
            score = 0
            device_text = f"{device.name} {device.room or ''} {device.type}".lower()

            for part in query_parts:
                if part in device_text:
                    score += 1

            if score > 0:
                results.append((score, device))

        # 按相关性排序
        results.sort(key=lambda x: x[0], reverse=True)

        # 返回前 N 个结果
        return [device.to_dict() for score, device in results[:limit]]

    def get_device_commands(self, device_id: str, capability: str) -> Dict[str, Any]:
        """模拟 get_device_commands 工具"""
        self.tool_calls.append({
            "tool": "get_device_commands",
            "parameters": {"device_id": device_id, "capability": capability}
        })

        # 查找设备
        device = next((d for d in self.devices if d.id == device_id or d.fullId == device_id), None)

        if not device:
            return {"error": "Device not found"}

        if capability not in device.capabilities:
            return {
                "error": f"Capability '{capability}' not supported",
                "message": f"Device does not support '{capability}'",
                "commands": []
            }

        # 返回能力信息
        capability_info = self.capabilities_map.get(capability, {})
        return {
            "capability": capability,
            "commands": capability_info.get("commands", []),
            "attributes": capability_info.get("attributes", {})
        }

    def execute_commands(self, device_id: str, commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """模拟 execute_commands 工具"""
        self.tool_calls.append({
            "tool": "execute_commands",
            "parameters": {"device_id": device_id, "commands": commands}
        })

        # 查找设备
        device = next((d for d in self.devices if d.id == device_id or d.fullId == device_id), None)

        if not device:
            return {"status": "FAILED", "error": "Device not found"}

        # 验证命令
        for cmd in commands:
            capability = cmd.get("capability")
            command = cmd.get("command")

            if capability not in device.capabilities:
                return {
                    "status": "FAILED",
                    "error": f"Device does not support capability '{capability}'"
                }

            capability_info = self.capabilities_map.get(capability, {})
            if command not in capability_info.get("commands", []):
                return {
                    "status": "FAILED",
                    "error": f"Command '{command}' not supported for capability '{capability}'"
                }

        # 执行成功
        return {
            "status": "ACCEPTED",
            "device_id": device_id,
            "commands_executed": len(commands)
        }

    def batch_execute_commands(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """模拟 batch_execute_commands 工具"""
        self.tool_calls.append({
            "tool": "batch_execute_commands",
            "parameters": {"operations": operations}
        })

        results = []
        success_count = 0

        for operation in operations:
            device_id = operation.get("device_id")
            commands = operation.get("commands", [])

            result = self.execute_commands(device_id, commands)

            if result.get("status") == "ACCEPTED":
                success_count += 1

            results.append({
                "device_id": device_id,
                "status": result.get("status"),
                "error": result.get("error")
            })

        return {
            "total": len(operations),
            "success": success_count,
            "results": results
        }

    def get_tool_call_count(self, tool_name: Optional[str] = None) -> int:
        """获取工具调用次数"""
        if tool_name is None:
            return len(self.tool_calls)
        return sum(1 for call in self.tool_calls if call["tool"] == tool_name)

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """获取所有工具调用记录"""
        return self.tool_calls

    def get_tool_call_sequence(self) -> List[str]:
        """获取工具调用顺序"""
        return [call["tool"] for call in self.tool_calls]
