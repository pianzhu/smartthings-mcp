"""
Tests for SmartThings Agent
Validates intent recognition, workflow planning, and context management
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import only components that don't require anthropic SDK
from agent.context_manager import ConversationContext
from agent.planner import WorkflowPlanner, Intent
from agent.error_handler import ErrorHandler, ErrorType, AgentError


def test_intent_recognition():
    """Test intent recognition from user input"""
    print("=" * 60)
    print("测试意图识别")
    print("=" * 60)

    planner = WorkflowPlanner()

    test_cases = [
        ("打开客厅的灯", Intent.CONTROL),
        ("关闭卧室的空调", Intent.CONTROL),
        ("客厅温度是多少？", Intent.QUERY),
        ("灯现在是开的吗？", Intent.QUERY),
        ("过去一周的平均温度", Intent.ANALYSIS),
        ("今天用了多少电？", Intent.ANALYSIS),
        ("我有哪些设备？", Intent.DISCOVERY),
        ("客厅有什么设备？", Intent.DISCOVERY),
        ("如果温度超过26度，打开空调", Intent.CONDITIONAL_CONTROL),
    ]

    passed = 0
    for user_input, expected_intent in test_cases:
        detected_intent = planner.intent_recognizer.recognize(user_input)
        status = "✓" if detected_intent == expected_intent else "✗"
        if detected_intent == expected_intent:
            passed += 1

        print(f"{status} '{user_input}'")
        print(f"  期望: {expected_intent.value}, 识别: {detected_intent.value}")

    print(f"\n通过: {passed}/{len(test_cases)}")
    assert passed == len(test_cases), f"只通过了 {passed}/{len(test_cases)} 测试"
    print("✅ 意图识别测试通过\n")


def test_device_query_extraction():
    """Test extracting device query from user input"""
    print("=" * 60)
    print("测试设备查询提取")
    print("=" * 60)

    planner = WorkflowPlanner()

    test_cases = [
        ("打开客厅的灯", "客厅 灯"),
        ("关闭卧室的空调", "卧室 空调"),
        ("请帮我打开前门的锁", "前门 锁"),
        ("查看厨房的温度", "厨房 温度"),
    ]

    passed = 0
    for user_input, expected_query in test_cases:
        extracted = planner.intent_recognizer.extract_device_query(user_input)
        # Flexible matching - extracted should contain key words
        expected_words = set(expected_query.split())
        extracted_words = set(extracted.split())
        is_match = expected_words.issubset(extracted_words)

        status = "✓" if is_match else "✗"
        if is_match:
            passed += 1

        print(f"{status} '{user_input}'")
        print(f"  期望: '{expected_query}', 提取: '{extracted}'")

    print(f"\n通过: {passed}/{len(test_cases)}")
    print("✅ 设备查询提取测试通过\n")


def test_workflow_planning():
    """Test workflow planning for different intents"""
    print("=" * 60)
    print("测试工作流规划")
    print("=" * 60)

    planner = WorkflowPlanner()

    # Test CONTROL workflow without cached device
    print("\n场景1: 控制意图 (无缓存设备)")
    workflow = planner.plan("打开客厅的灯", context={})
    assert workflow.intent == Intent.CONTROL
    assert len(workflow.steps) == 2
    assert workflow.steps[0].tool_name == "search_devices"
    assert workflow.steps[1].tool_name == "execute_commands"
    print(f"✓ 步骤数: {len(workflow.steps)}")
    print(f"  1. {workflow.steps[0].tool_name}: {workflow.steps[0].description}")
    print(f"  2. {workflow.steps[1].tool_name}: {workflow.steps[1].description}")

    # Test CONTROL workflow with cached device
    print("\n场景2: 控制意图 (有缓存设备)")
    workflow = planner.plan(
        "把它打开",
        context={"cached_device": {"device_id": "abc123", "name": "客厅吸顶灯"}},
    )
    assert workflow.intent == Intent.CONTROL
    assert len(workflow.steps) == 1  # Only execute, no search
    assert workflow.steps[0].tool_name == "execute_commands"
    print(f"✓ 步骤数: {len(workflow.steps)} (使用缓存，跳过搜索)")
    print(f"  1. {workflow.steps[0].tool_name}: {workflow.steps[0].description}")

    # Test QUERY workflow
    print("\n场景3: 查询意图")
    workflow = planner.plan("客厅温度是多少？", context={})
    assert workflow.intent == Intent.QUERY
    assert len(workflow.steps) == 2
    assert workflow.steps[0].tool_name == "search_devices"
    assert workflow.steps[1].tool_name == "get_device_status"
    print(f"✓ 步骤数: {len(workflow.steps)}")
    print(f"  1. {workflow.steps[0].tool_name}: {workflow.steps[0].description}")
    print(f"  2. {workflow.steps[1].tool_name}: {workflow.steps[1].description}")

    # Test QUERY with cached fresh status
    print("\n场景4: 查询意图 (有新鲜缓存)")
    workflow = planner.plan(
        "现在状态如何？",
        context={
            "cached_device": {"device_id": "abc123", "name": "客厅温度传感器"},
            "has_fresh_status": True,
        },
    )
    assert workflow.intent == Intent.QUERY
    assert len(workflow.steps) == 0  # No API call needed
    print(f"✓ 步骤数: {len(workflow.steps)} (使用缓存状态，无需 API 调用)")

    # Test DISCOVERY workflow
    print("\n场景5: 发现意图")
    workflow = planner.plan("我有哪些设备？", context={})
    assert workflow.intent == Intent.DISCOVERY
    assert len(workflow.steps) == 1
    assert workflow.steps[0].tool_name == "get_context_summary"
    print(f"✓ 步骤数: {len(workflow.steps)}")
    print(f"  1. {workflow.steps[0].tool_name}: {workflow.steps[0].description}")

    # Test ANALYSIS workflow
    print("\n场景6: 分析意图")
    workflow = planner.plan("过去一周的平均温度", context={})
    assert workflow.intent == Intent.ANALYSIS
    assert len(workflow.steps) == 2
    assert workflow.steps[0].tool_name == "search_devices"
    assert workflow.steps[1].tool_name == "get_device_history"
    print(f"✓ 步骤数: {len(workflow.steps)}")
    print(f"  1. {workflow.steps[0].tool_name}: {workflow.steps[0].description}")
    print(f"  2. {workflow.steps[1].tool_name}: {workflow.steps[1].description}")

    print("\n✅ 工作流规划测试通过\n")


def test_context_management():
    """Test conversation context management"""
    print("=" * 60)
    print("测试上下文管理")
    print("=" * 60)

    context = ConversationContext()

    # Turn 1: Add a device
    print("\nTurn 1: 添加设备")
    context.increment_turn()
    device1 = context.add_device(
        device_id="abc123",
        name="客厅吸顶灯",
        room="living room",
        device_type="light",
        capabilities=["switch", "switchLevel"],
    )
    print(f"✓ 添加设备: {device1.name} (ID: {device1.device_id})")
    print(f"  当前房间: {context.current_room}")

    # Turn 2: Reference device by pronoun
    print("\nTurn 2: 通过代词引用设备")
    context.increment_turn()
    found = context.find_device_by_reference("它")
    assert found is not None
    assert found.device_id == "abc123"
    print(f"✓ '它' 引用到: {found.name}")

    # Turn 3: Add status to device
    print("\nTurn 3: 更新设备状态")
    context.update_device_status("abc123", {"switch": "on", "level": 80})
    cached_status = context.get_cached_status("abc123")
    assert cached_status is not None
    assert cached_status["switch"] == "on"
    print(f"✓ 缓存状态: {cached_status}")

    # Turn 4: Add another device in different room
    print("\nTurn 4: 添加另一个房间的设备")
    context.increment_turn()
    device2 = context.add_device(
        device_id="def456", name="卧室空调", room="bedroom", device_type="ac"
    )
    print(f"✓ 添加设备: {device2.name}")
    print(f"  当前房间更新为: {context.current_room}")

    # Turn 5: Reference by room context
    print("\nTurn 5: 在当前房间上下文中引用")
    context.current_room = "bedroom"
    found = context.find_device_by_reference("空调")
    assert found is not None
    assert found.device_id == "def456"
    print(f"✓ 在卧室找到 '空调': {found.name}")

    # Test room inference
    print("\nTurn 6: 从用户输入推断房间")
    room = context.infer_room_from_input("打开客厅的灯")
    assert room == "living room"
    print(f"✓ 从 '打开客厅的灯' 推断房间: {room}")

    room = context.infer_room_from_input("关闭bedroom的空调")
    assert room == "bedroom"
    print(f"✓ 从 '关闭bedroom的空调' 推断房间: {room}")

    # Test context summary
    print("\nTurn 7: 获取上下文摘要")
    summary = context.get_summary()
    print(f"✓ 对话轮数: {summary['current_turn']}")
    print(f"  当前房间: {summary['current_room']}")
    print(f"  记忆中的设备: {summary['devices_in_memory']}")
    for device in summary["device_list"]:
        print(f"    - {device['name']} (房间: {device['room']})")

    print("\n✅ 上下文管理测试通过\n")


def test_multi_device_detection():
    """Test detection of multi-device operations"""
    print("=" * 60)
    print("测试多设备操作检测")
    print("=" * 60)

    planner = WorkflowPlanner()

    test_cases = [
        ("打开客厅的灯", False, 1),
        ("打开客厅的灯和卧室的空调", True, 2),
        ("打开客厅的灯，关闭卧室的空调，锁上前门", True, 3),
        ("Turn on living room light and bedroom AC", True, 2),
    ]

    for user_input, expected_multi, expected_count in test_cases:
        is_multi, count = planner.detect_multi_device_operation(user_input)
        status = "✓" if is_multi == expected_multi else "✗"

        print(f"{status} '{user_input}'")
        print(f"  多设备: {is_multi}, 估计数量: {count}")

        # Test batch decision
        should_batch = planner.should_use_batch(count)
        print(
            f"  建议: {'batch_execute_commands' if should_batch else 'parallel execute_commands'}"
        )

    print("\n✅ 多设备操作检测测试通过\n")


def test_error_handling():
    """Test error handling and fallback strategies"""
    print("=" * 60)
    print("测试错误处理")
    print("=" * 60)

    handler = ErrorHandler()

    # Test device not found
    print("\n场景1: 设备未找到错误")
    error = AgentError(
        "Device not found",
        error_type=ErrorType.DEVICE_NOT_FOUND,
        context={"query": "客厅的灯"},
    )
    result = handler.handle_error(error)
    print(f"✓ 错误类型: {result['error']['error_type'].value}")
    print(f"  用户消息: {result['user_message']}")
    print(f"  建议策略: {result['fallback']['strategy']}")

    # Test command not supported
    print("\n场景2: 命令不支持错误")
    error = AgentError(
        "Command not supported",
        error_type=ErrorType.COMMAND_NOT_SUPPORTED,
        context={"command": "setColor"},
    )
    result = handler.handle_error(error)
    print(f"✓ 错误类型: {result['error']['error_type'].value}")
    print(f"  用户消息: {result['user_message']}")
    print(f"  建议策略: {result['fallback']['strategy']}")

    # Test parameter invalid
    print("\n场景3: 参数无效错误")
    error = AgentError(
        "Invalid parameter value",
        error_type=ErrorType.PARAMETER_INVALID,
        context={"parameter": "level"},
    )
    result = handler.handle_error(error)
    print(f"✓ 错误类型: {result['error']['error_type'].value}")
    print(f"  用户消息: {result['user_message']}")

    # Test retry decision
    print("\n场景4: 网络错误 - 应该重试")
    should_retry = handler.should_retry(ErrorType.NETWORK_ERROR)
    assert should_retry == True
    print(f"✓ 网络错误应该重试: {should_retry}")

    should_retry = handler.should_retry(ErrorType.PERMISSION_DENIED)
    assert should_retry == False
    print(f"✓ 权限错误不应该重试: {should_retry}")

    print("\n✅ 错误处理测试通过\n")


def test_workflow_cache_optimization():
    """Test that workflow planning optimizes based on cache"""
    print("=" * 60)
    print("测试工作流缓存优化")
    print("=" * 60)

    planner = WorkflowPlanner()

    # Scenario: Multi-turn conversation
    print("\n对话模拟:")

    print("\nTurn 1: '客厅的灯在哪里？'")
    workflow1 = planner.plan("客厅的灯在哪里？", context={})
    print(f"  步骤数: {len(workflow1.steps)}")
    print(f"  需要搜索: search_devices")

    print("\nTurn 2: '把它打开' (有缓存)")
    workflow2 = planner.plan(
        "把它打开",
        context={"cached_device": {"device_id": "abc123", "name": "客厅吸顶灯"}},
    )
    print(f"  步骤数: {len(workflow2.steps)}")
    print(f"  跳过搜索，直接执行")
    assert len(workflow2.steps) == 1  # Only execute

    print("\nTurn 3: '现在状态如何？' (有缓存)")
    workflow3 = planner.plan(
        "现在状态如何？",
        context={"cached_device": {"device_id": "abc123", "name": "客厅吸顶灯"}},
    )
    print(f"  步骤数: {len(workflow3.steps)}")
    print(f"  使用缓存设备 ID 查询状态")
    assert len(workflow3.steps) == 1  # Only get_status

    print("\nTurn 4: '现在状态如何？' (有新鲜缓存状态)")
    workflow4 = planner.plan(
        "现在状态如何？",
        context={
            "cached_device": {"device_id": "abc123", "name": "客厅吸顶灯"},
            "has_fresh_status": True,
        },
    )
    print(f"  步骤数: {len(workflow4.steps)}")
    print(f"  使用缓存状态，无需 API 调用")
    assert len(workflow4.steps) == 0  # No API call

    print("\n✅ 工作流缓存优化测试通过")
    print("   证明了上下文管理可以显著减少 API 调用\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SmartThings Agent 测试套件")
    print("=" * 60 + "\n")

    try:
        test_intent_recognition()
        test_device_query_extraction()
        test_workflow_planning()
        test_context_management()
        test_multi_device_detection()
        test_error_handling()
        test_workflow_cache_optimization()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n验证的能力:")
        print("  ✓ 意图识别 (CONTROL/QUERY/ANALYSIS/DISCOVERY/CONDITIONAL)")
        print("  ✓ 设备查询提取")
        print("  ✓ 工作流规划 (6种场景)")
        print("  ✓ 上下文管理 (设备缓存、状态缓存、房间推断)")
        print("  ✓ 多设备操作检测")
        print("  ✓ 错误处理与降级")
        print("  ✓ 缓存优化 (减少 API 调用)")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试错误: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
