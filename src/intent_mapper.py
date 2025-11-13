"""
Intelligent Intent-to-Command Mapper for SmartThings
智能意图到命令的映射系统

核心设计：
1. 语义理解（而非简单字符串匹配）
2. 上下文感知（根据设备类型调整）
3. 参数智能提取
4. 强泛化能力
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CommandSuggestion:
    """命令建议结果"""
    capability: str
    command: str
    arguments: List
    confidence: float  # 0.0 - 1.0
    intent: str
    needs_current_state: bool = False


class IntentMapper:
    """智能意图映射器"""

    # 意图模式库（支持语义匹配，而非简单字符串）
    INTENT_PATTERNS = {
        "TURN_ON": {
            "keywords": ["打开", "开启", "turn on", "启动", "亮起", "开", "开灯", "点亮"],
            "semantic_variants": ["activate", "enable", "power on", "switch on"],
            "context_aware": {
                "switch": ["照亮", "点灯"],
                "windowShade": ["拉开", "升起", "打开窗帘"]
            },
            "fuzzy_patterns": [r'.*亮.*起', r'.*开.*灯']
        },

        "TURN_OFF": {
            "keywords": ["关闭", "关掉", "turn off", "关", "熄灭", "关灯"],
            "semantic_variants": ["deactivate", "disable", "power off", "switch off"],
            "context_aware": {
                "switch": ["熄灯", "灭灯", "不亮了"],
                "windowShade": ["关上", "降下", "关闭窗帘"]
            },
            "fuzzy_patterns": [r'.*关.*灯', r'.*熄.*']
        },

        "INCREASE_BRIGHTNESS": {
            "keywords": ["调亮", "调高", "增加亮度", "提高亮度", "更亮", "brighten", "亮一点"],
            "semantic_variants": ["increase brightness", "raise brightness", "brighter"],
            "context_aware": {
                "switchLevel": ["亮度高一些", "再亮些", "亮点"],
            },
            "parameter_patterns": [r'调亮.*?(\d+)%?', r'亮度.*?(\d+)%?'],
            "default_delta": 20,  # 默认增加20%
            "fuzzy_patterns": [r'.*[亮高].*[一些点]']
        },

        "DECREASE_BRIGHTNESS": {
            "keywords": ["调暗", "调低", "降低亮度", "减少亮度", "暗一点", "dim", "柔和"],
            "semantic_variants": ["decrease brightness", "lower brightness", "dimmer"],
            "context_aware": {
                "switchLevel": ["柔和一些", "暗一点", "暗些", "低一点"],
            },
            "parameter_patterns": [r'调暗.*?(\d+)%?', r'亮度.*?(\d+)%?'],
            "default_delta": -20,  # 默认降低20%
            "suggested_values": {
                "柔和": 40,    # "柔和的灯光" → 40%
                "微弱": 20,    # "微弱的光" → 20%
                "昏暗": 10,    # "昏暗一点" → 10%
            },
            "fuzzy_patterns": [r'.*[暗低].*[一些点]', r'.*柔和.*']
        },

        "SET_BRIGHTNESS": {
            "keywords": ["设置", "调到", "调节到", "set to", "亮度"],
            "parameter_patterns": [
                r'调[到至].*?(\d+)%',
                r'设置.*?(\d+)%',
                r'亮度.*?(\d+)%?',
                r'(\d+)%'
            ],
            "requires_parameter": True
        },

        "SET_TEMPERATURE": {
            "keywords": ["设置温度", "调到", "温度", "度"],
            "parameter_patterns": [
                r'调[到至].*?(\d+)\s*[度°]',
                r'设置.*?(\d+)\s*[度°]',
                r'(\d+)\s*[度°]'
            ],
            "requires_parameter": True,
            "valid_range": (16, 30)  # 合理温度范围
        },

        "LOCK": {
            "keywords": ["锁上", "锁门", "lock", "上锁"],
            "context_aware": {
                "lock": ["关闭", "关"]
            },
            "device_types": ["lock"]
        },

        "UNLOCK": {
            "keywords": ["解锁", "开锁", "unlock", "打开锁"],
            "context_aware": {
                "lock": ["打开", "开"]
            },
            "device_types": ["lock"]
        }
    }

    # 意图到命令的映射（第二层）
    INTENT_TO_COMMAND = {
        "TURN_ON": {
            "switch": {
                "capability": "switch",
                "command": "on",
                "arguments": []
            },
            "windowShade": {
                "capability": "windowShade",
                "command": "open",
                "arguments": []
            }
        },

        "TURN_OFF": {
            "switch": {
                "capability": "switch",
                "command": "off",
                "arguments": []
            },
            "windowShade": {
                "capability": "windowShade",
                "command": "close",
                "arguments": []
            }
        },

        "INCREASE_BRIGHTNESS": {
            "switchLevel": {
                "capability": "switchLevel",
                "command": "setLevel",
                "needs_current": True,  # 需要当前值
                "argument_builder": lambda current, delta: [min(100, current + delta)]
            }
        },

        "DECREASE_BRIGHTNESS": {
            "switchLevel": {
                "capability": "switchLevel",
                "command": "setLevel",
                "needs_current": False,  # 可以用建议值
                "argument_builder": lambda value: [value]
            }
        },

        "SET_BRIGHTNESS": {
            "switchLevel": {
                "capability": "switchLevel",
                "command": "setLevel",
                "argument_builder": lambda value: [value]
            },
            "windowShadeLevel": {
                "capability": "windowShadeLevel",
                "command": "setShadeLevel",
                "argument_builder": lambda value: [value]
            }
        },

        "SET_TEMPERATURE": {
            "thermostat": {
                "capability": "thermostat",
                "command": "setHeatingSetpoint",
                "argument_builder": lambda value: [value]
            }
        },

        "LOCK": {
            "lock": {
                "capability": "lock",
                "command": "lock",
                "arguments": []
            }
        },

        "UNLOCK": {
            "lock": {
                "capability": "lock",
                "command": "unlock",
                "arguments": []
            }
        }
    }

    def recognize_intent(self, user_input: str, device_capabilities: List[str]) -> Tuple[str, float, Optional[int]]:
        """
        识别用户意图（第一层：语义理解）

        Args:
            user_input: 用户输入的命令
            device_capabilities: 设备支持的能力列表

        Returns:
            (intent_name, confidence, extracted_parameter)
        """
        user_input_lower = user_input.lower()
        best_intent = None
        best_score = 0.0
        extracted_param = None

        for intent_name, pattern in self.INTENT_PATTERNS.items():
            score = 0.0
            param = None

            # 1. 关键词匹配（基础分 0.3）
            for keyword in pattern.get("keywords", []):
                if keyword.lower() in user_input_lower:
                    score += 0.3
                    break

            # 2. 上下文感知匹配（高权重 0.5）
            context_aware = pattern.get("context_aware", {})
            for cap in device_capabilities:
                if cap in context_aware:
                    for context_keyword in context_aware[cap]:
                        if context_keyword.lower() in user_input_lower:
                            score += 0.5
                            break

            # 3. 模糊模式匹配（中等权重 0.2）
            for fuzzy_pattern in pattern.get("fuzzy_patterns", []):
                if re.search(fuzzy_pattern, user_input_lower):
                    score += 0.2
                    break

            # 4. 参数提取
            for param_pattern in pattern.get("parameter_patterns", []):
                match = re.search(param_pattern, user_input)
                if match:
                    param = int(match.group(1))
                    score += 0.1  # 有参数额外加分
                    break

            # 5. 语义变体匹配（低权重 0.1）
            for variant in pattern.get("semantic_variants", []):
                if variant.lower() in user_input_lower:
                    score += 0.1
                    break

            # 更新最佳匹配
            if score > best_score:
                best_score = score
                best_intent = intent_name
                extracted_param = param

        return best_intent, best_score, extracted_param

    def map_to_command(
        self,
        user_input: str,
        device_capabilities: List[str],
        current_state: Optional[Dict] = None
    ) -> Optional[CommandSuggestion]:
        """
        将用户输入映射到具体命令（完整流程）

        Args:
            user_input: 用户输入
            device_capabilities: 设备能力列表
            current_state: 设备当前状态（可选）

        Returns:
            CommandSuggestion 或 None
        """
        # 第一层：识别意图
        intent, confidence, param = self.recognize_intent(user_input, device_capabilities)

        if not intent or confidence < 0.2:
            return None  # 置信度太低

        # 第二层：找到对应的命令映射
        command_map = self.INTENT_TO_COMMAND.get(intent, {})

        # 查找设备支持的能力
        matching_cap = None
        for cap in device_capabilities:
            if cap in command_map:
                matching_cap = cap
                break

        if not matching_cap:
            return None  # 设备不支持此操作

        cmd_template = command_map[matching_cap]

        # 第三层：构建命令参数
        arguments = []
        needs_current_state = False

        if "arguments" in cmd_template:
            # 固定参数
            arguments = cmd_template["arguments"]
        elif "argument_builder" in cmd_template:
            # 动态构建参数
            builder = cmd_template["argument_builder"]

            if cmd_template.get("needs_current"):
                # 需要当前状态
                needs_current_state = True
                if current_state:
                    current_value = self._extract_current_value(current_state, matching_cap)
                    delta = param or self.INTENT_PATTERNS[intent].get("default_delta", 0)
                    arguments = builder(current_value, delta)
                else:
                    # 没有当前状态，使用默认值
                    arguments = [50]  # 默认中间值
            else:
                # 不需要当前状态
                if param is not None:
                    # 用户提供了具体数值
                    arguments = builder(param)
                else:
                    # 使用建议值
                    suggested = self._get_suggested_value(user_input, intent)
                    arguments = builder(suggested)

        return CommandSuggestion(
            capability=cmd_template["capability"],
            command=cmd_template["command"],
            arguments=arguments,
            confidence=confidence,
            intent=intent,
            needs_current_state=needs_current_state
        )

    def _get_suggested_value(self, user_input: str, intent: str) -> int:
        """获取建议值（用于模糊命令）"""
        pattern = self.INTENT_PATTERNS.get(intent, {})
        suggested_values = pattern.get("suggested_values", {})

        # 检查是否包含特定关键词
        for keyword, value in suggested_values.items():
            if keyword in user_input:
                return value

        # 默认值
        if intent == "DECREASE_BRIGHTNESS":
            return 40  # 默认柔和亮度
        elif intent == "INCREASE_BRIGHTNESS":
            return 80  # 默认明亮

        return 50  # 通用默认值

    def _extract_current_value(self, state: Dict, capability: str) -> int:
        """从设备状态中提取当前值"""
        # 假设状态格式：{"main": {"switchLevel": {"level": {"value": 75}}}}
        try:
            for component in state.values():
                if capability in component:
                    cap_data = component[capability]
                    # 查找值字段
                    for attr_name, attr_value in cap_data.items():
                        if isinstance(attr_value, dict) and "value" in attr_value:
                            return int(attr_value["value"])
        except:
            pass

        return 50  # 默认中间值


# 全局单例
intent_mapper = IntentMapper()
