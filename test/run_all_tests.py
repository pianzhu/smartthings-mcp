#!/usr/bin/env python3
"""
统一测试运行器

运行所有三个级别的测试并生成综合报告
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# 添加 test 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from test_level1_tools import create_level1_tests, Level1TestRunner
from test_level2_workflows import create_level2_tests, Level2TestRunner
from test_level3_integration import create_level3_tests, Level3TestRunner


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("SmartThings MCP 测试套件")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    all_results = {
        "level1": {"name": "Level 1: 单工具基础测试", "results": []},
        "level2": {"name": "Level 2: 多工具组合测试", "results": []},
        "level3": {"name": "Level 3: 端到端集成测试", "results": []}
    }

    # ==================== Level 1 ====================
    print("\n" + "-"*70)
    print("LEVEL 1: 单工具基础测试")
    print("-"*70)

    framework1 = create_level1_tests()
    runner1 = Level1TestRunner()
    runner1.set_mock_server(framework1.mock_server)
    runner1.test_cases = framework1.test_cases

    results1 = runner1.run_all()
    all_results["level1"]["results"] = results1

    # ==================== Level 2 ====================
    print("\n" + "-"*70)
    print("LEVEL 2: 多工具组合测试")
    print("注意：跳过查询设备状态的测试（TC-202, TC-211, TC-212, TC-231）")
    print("-"*70)

    framework2 = create_level2_tests()
    runner2 = Level2TestRunner()
    runner2.set_mock_server(framework2.mock_server)
    runner2.test_cases = framework2.test_cases

    results2 = runner2.run_all()
    all_results["level2"]["results"] = results2

    # ==================== Level 3 ====================
    print("\n" + "-"*70)
    print("LEVEL 3: 端到端集成测试")
    print("注意：跳过查询设备状态的测试（TC-301 Turn 3）")
    print("-"*70)

    framework3 = create_level3_tests()
    runner3 = Level3TestRunner()
    runner3.set_mock_server(framework3.mock_server)
    runner3.test_cases = framework3.test_cases

    results3 = runner3.run_all()
    all_results["level3"]["results"] = results3

    # ==================== 生成综合报告 ====================
    print("\n" + "="*70)
    print("综合测试报告")
    print("="*70)

    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_time = 0
    total_tokens = 0

    for level_key, level_data in all_results.items():
        level_results = level_data["results"]
        level_tests = len(level_results)
        level_passed = sum(1 for r in level_results if r.passed)
        level_failed = level_tests - level_passed
        level_time = sum(r.execution_time for r in level_results)
        level_tokens = sum(r.total_tokens for r in level_results)

        total_tests += level_tests
        total_passed += level_passed
        total_failed += level_failed
        total_time += level_time
        total_tokens += level_tokens

        print(f"\n{level_data['name']}:")
        print(f"  Tests: {level_tests} | ✅ Passed: {level_passed} | ❌ Failed: {level_failed}")
        print(f"  Time: {level_time:.2f}s | Tokens: {level_tokens}")
        if level_tests > 0:
            print(f"  Pass Rate: {level_passed/level_tests*100:.1f}%")

    print(f"\n{'-'*70}")
    print(f"总计:")
    print(f"  总测试数: {total_tests}")
    print(f"  ✅ 通过: {total_passed} ({total_passed/total_tests*100:.1f}%)")
    print(f"  ❌ 失败: {total_failed} ({total_failed/total_tests*100:.1f}%)")
    print(f"  总时间: {total_time:.2f}s")
    print(f"  总 Token: {total_tokens}")
    print(f"  平均 Token/测试: {total_tokens/total_tests:.1f}")

    # ==================== 失败详情 ====================
    if total_failed > 0:
        print(f"\n{'='*70}")
        print("失败测试详情:")
        print(f"{'='*70}")

        for level_key, level_data in all_results.items():
            failed_tests = [r for r in level_data["results"] if not r.passed]
            if failed_tests:
                print(f"\n{level_data['name']}:")
                for result in failed_tests:
                    print(f"\n  ❌ {result.test_id}: {result.name}")
                    if result.error_message:
                        print(f"     Error: {result.error_message}")
                    print(f"     Tool Calls: {len(result.tool_calls)}")
                    print(f"     Tokens: {result.total_tokens}")
                    print(f"     Time: {result.execution_time:.3f}s")

    # ==================== 导出 JSON 报告 ====================
    report_file = Path(__file__).parent / "test_report.json"
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "total_time": total_time,
            "total_tokens": total_tokens
        },
        "levels": {}
    }

    for level_key, level_data in all_results.items():
        report_data["levels"][level_key] = {
            "name": level_data["name"],
            "tests": [
                {
                    "test_id": r.test_id,
                    "name": r.name,
                    "passed": r.passed,
                    "execution_time": r.execution_time,
                    "total_tokens": r.total_tokens,
                    "error_message": r.error_message,
                    "tool_calls": len(r.tool_calls)
                }
                for r in level_data["results"]
            ]
        }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print(f"详细报告已导出到: {report_file}")
    print(f"{'='*70}\n")

    # 返回状态码（如果有失败的测试，返回 1）
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
