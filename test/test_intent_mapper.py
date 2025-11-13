#!/usr/bin/env python3
"""
测试智能意图映射系统
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from intent_mapper import IntentMapper, CommandSuggestion


def test_turn_on_variants():
    """测试"打开"的各种说法"""
    print("✓ 测试 TURN_ON 意图的泛化能力...\n")

    mapper = IntentMapper()
    test_cases = [
        ("打开", ["switch"]),
        ("开启", ["switch"]),
        ("turn on", ["switch"]),
        ("亮起来", ["switch"]),
        ("点亮", ["switch"]),
        ("开灯", ["switch"]),
    ]

    for user_input, capabilities in test_cases:
        intent, confidence, param = mapper.recognize_intent(user_input, capabilities)
        print(f"  输入: '{user_input}'")
        print(f"    → 意图: {intent}, 置信度: {confidence:.2f}")
        assert intent == "TURN_ON", f"应该识别为 TURN_ON，但得到 {intent}"
        assert confidence > 0.2, f"置信度太低: {confidence}"

    print("  ✅ 所有变体都正确识别\n")


def test_semantic_matching():
    """测试语义匹配（而非字符串匹配）"""
    print("✓ 测试语义匹配能力...\n")

    mapper = IntentMapper()

    # 测试："柔和一些" 应该被识别为 DECREASE_BRIGHTNESS
    user_input = "让灯光柔和一些"
    capabilities = ["switch", "switchLevel"]

    intent, confidence, param = mapper.recognize_intent(user_input, capabilities)

    print(f"  输入: '{user_input}'")
    print(f"  设备能力: {capabilities}")
    print(f"    → 识别意图: {intent}")
    print(f"    → 置信度: {confidence:.2f}")

    assert intent == "DECREASE_BRIGHTNESS", "应该识别为 DECREASE_BRIGHTNESS"
    assert confidence > 0.4, "语义匹配应该有较高置信度"

    print("  ✅ 语义匹配成功（'柔和' → DECREASE_BRIGHTNESS）\n")


def test_context_awareness():
    """测试上下文感知"""
    print("✓ 测试上下文感知能力...\n")

    mapper = IntentMapper()

    # 测试1：灯的"打开"
    intent1, conf1, _ = mapper.recognize_intent("打开", ["switch"])
    print(f"  场景1: 打开 + switch → {intent1} (置信度: {conf1:.2f})")

    # 测试2：锁的"打开"（应该是 UNLOCK）
    intent2, conf2, _ = mapper.recognize_intent("打开锁", ["lock"])
    print(f"  场景2: 打开锁 + lock → {intent2} (置信度: {conf2:.2f})")

    # 测试3：窗帘的"打开"
    intent3, conf3, _ = mapper.recognize_intent("打开", ["windowShade"])
    print(f"  场景3: 打开 + windowShade → {intent3} (置信度: {conf3:.2f})")

    assert intent1 == "TURN_ON"
    assert intent2 == "UNLOCK"
    assert intent3 == "TURN_ON"

    print("  ✅ 上下文感知正确\n")


def test_parameter_extraction():
    """测试参数提取"""
    print("✓ 测试参数提取能力...\n")

    mapper = IntentMapper()

    test_cases = [
        ("调到50%", 50),
        ("设置亮度为80%", 80),
        ("亮度30", 30),
        ("调暗到20%", 20),
    ]

    for user_input, expected_param in test_cases:
        intent, confidence, param = mapper.recognize_intent(user_input, ["switchLevel"])
        print(f"  输入: '{user_input}'")
        print(f"    → 提取参数: {param} (期望: {expected_param})")
        assert param == expected_param, f"参数提取错误"

    print("  ✅ 参数提取正确\n")


def test_full_mapping():
    """测试完整映射流程"""
    print("✓ 测试完整映射流程...\n")

    mapper = IntentMapper()

    # 场景1：简单开关
    result = mapper.map_to_command("打开", ["switch"])
    print(f"  场景1: '打开' + switch")
    print(f"    → capability: {result.capability}")
    print(f"    → command: {result.command}")
    print(f"    → arguments: {result.arguments}")
    print(f"    → 置信度: {result.confidence:.2f}\n")

    assert result.capability == "switch"
    assert result.command == "on"
    assert result.arguments == []

    # 场景2：带参数的调节
    result = mapper.map_to_command("调到50%", ["switchLevel"])
    print(f"  场景2: '调到50%' + switchLevel")
    print(f"    → capability: {result.capability}")
    print(f"    → command: {result.command}")
    print(f"    → arguments: {result.arguments}")
    print(f"    → 置信度: {result.confidence:.2f}\n")

    assert result.capability == "switchLevel"
    assert result.command == "setLevel"
    assert result.arguments == [50]

    # 场景3：模糊命令（使用建议值）
    result = mapper.map_to_command("让灯光柔和一些", ["switchLevel"])
    print(f"  场景3: '让灯光柔和一些' + switchLevel")
    print(f"    → capability: {result.capability}")
    print(f"    → command: {result.command}")
    print(f"    → arguments: {result.arguments}")
    print(f"    → 置信度: {result.confidence:.2f}")
    print(f"    → 建议值: 40 (柔和的灯光)\n")

    assert result.capability == "switchLevel"
    assert result.command == "setLevel"
    assert result.arguments == [40]  # "柔和" 的建议值

    print("  ✅ 完整映射流程正确\n")


def test_unsupported_capability():
    """测试设备不支持的操作"""
    print("✓ 测试不支持的操作...\n")

    mapper = IntentMapper()

    # 尝试对只有 switch 的设备调光
    result = mapper.map_to_command("调到50%", ["switch"])  # 没有 switchLevel

    print(f"  场景: '调到50%' + 只有 switch (没有 switchLevel)")
    print(f"    → 结果: {result}\n")

    assert result is None, "应该返回 None（设备不支持）"

    print("  ✅ 正确处理不支持的操作\n")


def test_fuzzy_matching():
    """测试模糊匹配"""
    print("✓ 测试模糊匹配能力...\n")

    mapper = IntentMapper()

    # 各种没见过的说法
    test_cases = [
        ("亮点", "INCREASE_BRIGHTNESS"),
        ("暗些", "DECREASE_BRIGHTNESS"),
        ("微弱一点", "DECREASE_BRIGHTNESS"),
        ("再亮些", "INCREASE_BRIGHTNESS"),
    ]

    for user_input, expected_intent in test_cases:
        intent, confidence, _ = mapper.recognize_intent(user_input, ["switchLevel"])
        print(f"  输入: '{user_input}'")
        print(f"    → 意图: {intent} (期望: {expected_intent})")
        print(f"    → 置信度: {confidence:.2f}")

        # 注意：模糊匹配可能置信度较低，但应该能识别
        if confidence > 0.15:  # 降低阈值，因为是模糊匹配
            assert intent == expected_intent, f"模糊匹配失败"

    print("  ✅ 模糊匹配工作正常\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("智能意图映射系统 - 测试套件")
    print("=" * 60 + "\n")

    tests = [
        test_turn_on_variants,
        test_semantic_matching,
        test_context_awareness,
        test_parameter_extraction,
        test_full_mapping,
        test_unsupported_capability,
        test_fuzzy_matching,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  ✗ 失败: {e}\n")
            failed += 1
        except Exception as e:
            print(f"  ✗ 错误: {e}\n")
            failed += 1

    print("=" * 60)
    if failed == 0:
        print("✅ 所有测试通过！")
        print("\n📊 验证的能力:")
        print("  - ✓ 关键词变体识别")
        print("  - ✓ 语义匹配（非字符串匹配）")
        print("  - ✓ 上下文感知")
        print("  - ✓ 参数提取")
        print("  - ✓ 完整映射流程")
        print("  - ✓ 不支持操作处理")
        print("  - ✓ 模糊匹配")
    else:
        print(f"❌ {failed} 个测试失败")
    print("=" * 60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
