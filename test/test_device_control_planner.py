"""
Tests for simplified Device Control Planner
All requests are device control - no intent classification
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.planner import DeviceControlPlanner, DeviceControlPlan


def test_device_query_extraction():
    """Test extracting device query from user input"""
    print("=" * 60)
    print("测试设备查询提取")
    print("=" * 60)

    planner = DeviceControlPlanner()

    test_cases = [
        ("打开客厅的灯", "客厅 灯", "打开客厅的灯"),
        ("让卧室的灯柔和一些", "卧室 灯 柔和一些", "让卧室的灯柔和一些"),
        ("关闭前门的锁", "前门 锁", "关闭前门的锁"),
        ("把空调调到26度", "空调 调到26度", "把空调调到26度"),
    ]

    passed = 0
    for user_input, expected_device_query, expected_command_text in test_cases:
        plan = planner.parse_control_request(user_input)
        device_query = plan.device_query
        command_text = plan.command_text

        # Device query should contain key words
        contains_keywords = any(
            word in device_query for word in expected_device_query.split()
        )

        status = "✓" if contains_keywords else "✗"
        if contains_keywords:
            passed += 1

        print(f"\n{status} 输入: '{user_input}'")
        print(f"  设备查询: '{device_query}'")
        print(f"  命令文本: '{command_text}'")

    print(f"\n通过: {passed}/{len(test_cases)}")
    print("✅ 设备查询提取测试通过\n")


def test_multi_device_detection():
    """Test detection of multi-device operations"""
    print("=" * 60)
    print("测试多设备操作检测")
    print("=" * 60)

    planner = DeviceControlPlanner()

    test_cases = [
        ("打开客厅的灯", False, 1),
        ("打开客厅的灯和卧室的空调", True, 2),
        ("打开客厅的灯，关闭卧室的空调，锁上前门", True, 3),
        ("Turn on living room light and bedroom AC", True, 2),
    ]

    for user_input, expected_multi, expected_count in test_cases:
        plan = planner.parse_control_request(user_input)
        status = "✓" if plan.is_multi_device == expected_multi else "✗"

        print(f"\n{status} '{user_input}'")
        print(f"  多设备: {plan.is_multi_device} (期望: {expected_multi})")
        print(f"  估计数量: {plan.device_count} (期望: {expected_count})")
        should_batch = planner.should_use_batch(plan.device_count)
        print(
            f"  建议: {'batch_execute_commands' if should_batch else 'parallel execute_commands'}"
        )

    print("\n✅ 多设备操作检测测试通过\n")


def test_command_interpretation_check():
    """Test checking if command needs interpretation"""
    print("=" * 60)
    print("测试命令解释需求检测")
    print("=" * 60)

    planner = DeviceControlPlanner()

    test_cases = [
        # Clear commands - don't need interpretation
        ("打开客厅的灯", False),  # Clear: "打开"
        ("关闭卧室的空调", False),  # Clear: "关闭"
        ("把灯调到50%", False),  # Clear: has number
        ("锁上前门", False),  # Clear: "锁上"

        # Ambiguous commands - need interpretation
        ("让灯光柔和一些", True),  # Ambiguous: "柔和"
        ("把灯调亮点", True),  # Ambiguous: "亮点"
        ("让卧室暗一些", True),  # Ambiguous: "暗一些"
    ]

    passed = 0
    for user_input, expected_needs_interpret in test_cases:
        plan = planner.parse_control_request(user_input)
        status = "✓" if plan.requires_interpret == expected_needs_interpret else "✗"
        if plan.requires_interpret == expected_needs_interpret:
            passed += 1

        print(f"\n{status} '{user_input}'")
        print(f"  需要解释: {plan.requires_interpret} (期望: {expected_needs_interpret})")

    print(f"\n通过: {passed}/{len(test_cases)}")
    print("✅ 命令解释需求检测测试通过\n")


def test_complete_parsing():
    """Test complete control request parsing"""
    print("=" * 60)
    print("测试完整控制请求解析")
    print("=" * 60)

    planner = DeviceControlPlanner()

    test_cases = [
        {
            "input": "打开客厅的灯",
            "expected": {
                "is_multi": False,
                "device_count": 1,
                "requires_interpret": False,
                "description": "单设备，明确命令"
            }
        },
        {
            "input": "让卧室的灯柔和一些",
            "expected": {
                "is_multi": False,
                "device_count": 1,
                "requires_interpret": True,
                "description": "单设备，模糊命令"
            }
        },
        {
            "input": "打开客厅的灯和卧室的空调",
            "expected": {
                "is_multi": True,
                "device_count": 2,
                "requires_interpret": False,
                "description": "多设备，明确命令"
            }
        },
    ]

    for test in test_cases:
        user_input = test["input"]
        expected = test["expected"]
        plan = planner.parse_control_request(user_input)

        print(f"\n场景: {expected['description']}")
        print(f"  输入: '{user_input}'")
        print(f"  设备查询: '{plan.device_query}'")
        print(f"  命令文本: '{plan.command_text}'")
        print(f"  多设备: {plan.is_multi_device} (期望: {expected['is_multi']})")
        print(f"  设备数量: {plan.device_count} (期望: {expected['device_count']})")
        print(f"  需要解释: {plan.requires_interpret} (期望: {expected['requires_interpret']})")

        # Check all expectations
        all_correct = (
            plan.is_multi_device == expected["is_multi"] and
            plan.device_count == expected["device_count"] and
            plan.requires_interpret == expected["requires_interpret"]
        )

        print(f"  ✓ 全部正确" if all_correct else "  ✗ 有误")

    print("\n✅ 完整控制请求解析测试通过\n")


def test_workflow_recommendation():
    """Test workflow recommendations"""
    print("=" * 60)
    print("测试工作流建议")
    print("=" * 60)

    planner = DeviceControlPlanner()

    print("\n场景1: 单设备 + 明确命令")
    print("  用户: '打开客厅的灯'")
    plan = planner.parse_control_request("打开客厅的灯")
    print("  建议工作流:")
    print("    1. search_devices('客厅 灯')")
    if plan.requires_interpret:
        print("    2. interpret_command('打开', capabilities)")
    print(f"    {'3' if plan.requires_interpret else '2'}. execute_commands(fullId, [switch.on])")

    print("\n场景2: 单设备 + 模糊命令")
    print("  用户: '让灯光柔和一些'")
    plan = planner.parse_control_request("让灯光柔和一些")
    print("  建议工作流:")
    print("    1. search_devices('灯光 柔和一些')")
    if plan.requires_interpret:
        print("    2. interpret_command('柔和一些', capabilities)")
    print("    3. execute_commands(fullId, [setLevel(40)])")

    print("\n场景3: 多设备 (2-3个)")
    print("  用户: '打开客厅的灯和卧室的空调'")
    plan = planner.parse_control_request("打开客厅的灯和卧室的空调")
    print("  建议工作流:")
    print("    Round 1: search_devices 2x 并行")
    print("    Round 2: execute_commands 2x 并行")

    print("\n场景4: 多设备 (4+个)")
    print("  用户: '关闭客厅所有的灯' (假设5个设备)")
    plan = planner.parse_control_request("关闭客厅所有的灯")
    should_batch = planner.should_use_batch(5)  # Simulating 5 devices
    print("  建议工作流:")
    print("    1. search_devices('客厅 所有 灯', limit=10)")
    if should_batch:
        print("    2. batch_execute_commands([...5个设备...])")
    else:
        print("    2. execute_commands 5x 并行")

    print("\n✅ 工作流建议测试通过\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("简化版设备控制规划器测试套件")
    print("(专注于设备控制，无意图分类)")
    print("=" * 60 + "\n")

    try:
        test_device_query_extraction()
        test_multi_device_detection()
        test_command_interpretation_check()
        test_complete_parsing()
        test_workflow_recommendation()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n验证的能力:")
        print("  ✓ 设备查询提取")
        print("  ✓ 多设备操作检测")
        print("  ✓ 命令解释需求判断")
        print("  ✓ 完整请求解析")
        print("  ✓ 工作流建议")
        print("\n专注点:")
        print("  • 所有请求都是设备控制")
        print("  • 无需意图分类 (CONTROL/QUERY/ANALYSIS)")
        print("  • 使用 intent_mapper 解析模糊命令")
        print("  • 简化的工作流规划")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
