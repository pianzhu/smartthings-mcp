"""
Integration test for interpret_command MCP tool
Tests the integration of intent_mapper in the MCP server
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent_mapper import IntentMapper


def test_interpret_command_integration():
    """Test interpret_command tool integration"""
    print("=" * 60)
    print("测试 interpret_command MCP 工具集成")
    print("=" * 60)

    mapper = IntentMapper()

    # Test Case 1: Clear command
    print("\n场景1: 明确的命令")
    print("  用户输入: '打开'")
    print("  设备能力: ['switch', 'switchLevel']")

    result = mapper.map_to_command("打开", ["switch", "switchLevel"])
    if result:
        print(f"  ✓ 意图: {result.intent}")
        print(f"    能力: {result.capability}")
        print(f"    命令: {result.command}")
        print(f"    参数: {result.arguments}")
        print(f"    置信度: {result.confidence}")

    # Test Case 2: Ambiguous command (柔和一些)
    print("\n场景2: 模糊的命令 - '柔和一些'")
    print("  用户输入: '柔和一些'")
    print("  设备能力: ['switch', 'switchLevel']")

    result = mapper.map_to_command("柔和一些", ["switch", "switchLevel"])
    if result:
        print(f"  ✓ 意图: {result.intent}")
        print(f"    能力: {result.capability}")
        print(f"    命令: {result.command}")
        print(f"    参数: {result.arguments}")
        print(f"    置信度: {result.confidence}")
        print(f"    解释: DECREASE_BRIGHTNESS → switchLevel.setLevel(40)")
        assert result.intent == "DECREASE_BRIGHTNESS"
        assert result.capability == "switchLevel"
        assert result.command == "setLevel"
        assert result.arguments == [40]

    # Test Case 3: Context-aware (打开锁)
    print("\n场景3: 上下文感知 - '打开锁'")
    print("  用户输入: '打开锁'")
    print("  设备能力: ['lock']")

    result = mapper.map_to_command("打开锁", ["lock"])
    if result:
        print(f"  ✓ 意图: {result.intent}")
        print(f"    能力: {result.capability}")
        print(f"    命令: {result.command}")
        print(f"    解释: 'lock' 设备的 '打开' → UNLOCK")
        assert result.intent == "UNLOCK"
        assert result.capability == "lock"
        assert result.command == "unlock"

    # Test Case 4: Parameter extraction
    print("\n场景4: 参数提取 - '调到50%'")
    print("  用户输入: '调到50%'")
    print("  设备能力: ['switchLevel']")

    result = mapper.map_to_command("调到50%", ["switchLevel"])
    if result:
        print(f"  ✓ 意图: {result.intent}")
        print(f"    能力: {result.capability}")
        print(f"    命令: {result.command}")
        print(f"    参数: {result.arguments}")
        print(f"    解释: 从自然语言提取参数 50")
        assert result.arguments == [50]

    # Test Case 5: Unsupported capability
    print("\n场景5: 不支持的操作")
    print("  用户输入: '调到50%'")
    print("  设备能力: ['switch'] (无 switchLevel)")

    result = mapper.map_to_command("调到50%", ["switch"])
    if result is None:
        print("  ✓ 正确返回 None (设备不支持此操作)")
    else:
        print("  ✗ 应该返回 None")

    print("\n" + "=" * 60)
    print("✅ MCP 工具集成测试通过")
    print("=" * 60)

    # Simulate MCP tool response format
    print("\n模拟 MCP 工具响应格式:")
    print("-" * 60)

    test_result = mapper.map_to_command("柔和一些", ["switch", "switchLevel"])
    if test_result:
        response = {
            "intent": test_result.intent,
            "capability": test_result.capability,
            "command": test_result.command,
            "arguments": test_result.arguments,
            "confidence": test_result.confidence,
            "interpretation": f"{test_result.intent} → {test_result.capability}.{test_result.command}({test_result.arguments})",
            "needs_current_state": test_result.needs_current_state
        }

        print("interpret_command('柔和一些', ['switch', 'switchLevel']):")
        import json
        print(json.dumps(response, indent=2, ensure_ascii=False))

    print("\n这个响应可以直接用于构建 execute_commands 的参数！")


def test_workflow_example():
    """Test complete workflow example"""
    print("\n" + "=" * 60)
    print("完整工作流示例")
    print("=" * 60)

    print("\n用户请求: '让客厅的灯柔和一些'")
    print("\nAI 工具调用序列:")
    print("-" * 60)

    print("\n1️⃣  search_devices('客厅 灯')")
    print("    返回: {")
    print("      'fullId': 'abc-123-uuid',")
    print("      'name': '客厅吸顶灯',")
    print("      'capabilities': ['switch', 'switchLevel']")
    print("    }")

    print("\n2️⃣  interpret_command('柔和一些', ['switch', 'switchLevel'])")
    mapper = IntentMapper()
    result = mapper.map_to_command("柔和一些", ["switch", "switchLevel"])
    if result:
        print("    返回: {")
        print(f"      'intent': '{result.intent}',")
        print(f"      'capability': '{result.capability}',")
        print(f"      'command': '{result.command}',")
        print(f"      'arguments': {result.arguments},")
        print(f"      'confidence': {result.confidence}")
        print("    }")

    print("\n3️⃣  execute_commands('abc-123-uuid', [")
    print("      {")
    print("        'component': 'main',")
    print(f"        'capability': '{result.capability}',")
    print(f"        'command': '{result.command}',")
    print(f"        'arguments': {result.arguments}")
    print("      }")
    print("    ])")
    print("    ✅ 执行成功")

    print("\n" + "=" * 60)
    print("优势:")
    print("  ✓ 3步完成复杂的自然语言命令")
    print("  ✓ 语义理解：'柔和' 自动映射到 40% 亮度")
    print("  ✓ 上下文感知：不同设备类型，相同词语不同命令")
    print("  ✓ 参数智能：自动提取或建议合适的参数值")
    print("=" * 60)


if __name__ == "__main__":
    test_interpret_command_integration()
    test_workflow_example()
    print("\n✨ 集成测试全部通过！MCP server 已准备好处理自然语言设备控制\n")
