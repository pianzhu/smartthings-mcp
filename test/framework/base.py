"""
测试框架基础类

提供测试用例定义、执行和验证的基础设施
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import time


class TestPriority(Enum):
    """测试优先级"""
    P0 = "P0"  # 关键功能，必须通过
    P1 = "P1"  # 重要功能，建议通过
    P2 = "P2"  # 增强功能，可选


class TestCategory(Enum):
    """测试类别"""
    UNIT = "Unit"  # Level 1: 单工具测试
    WORKFLOW = "Workflow"  # Level 2: 多工具组合
    INTEGRATION = "Integration"  # Level 3: 端到端测试
    PERFORMANCE = "Performance"  # 性能测试


@dataclass
class ToolCall:
    """工具调用记录"""
    tool_name: str
    parameters: Dict[str, Any]
    result: Any
    timestamp: float
    token_count: int = 0


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    name: str
    passed: bool
    execution_time: float
    tool_calls: List[ToolCall]
    total_tokens: int
    error_message: Optional[str] = None
    assertions: Dict[str, bool] = field(default_factory=dict)

    def summary(self) -> str:
        """生成测试结果摘要"""
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | {self.test_id} | {self.name} | {self.execution_time:.3f}s | {self.total_tokens} tokens"


@dataclass
class TestCase:
    """测试用例定义"""
    test_id: str
    name: str
    priority: TestPriority
    category: TestCategory
    description: str

    # 输入
    scenario: str  # 场景描述（如用户输入）
    mock_data: Dict[str, Any]  # Mock 数据

    # 预期行为
    expected_tool_calls: List[str]  # 预期的工具调用顺序
    expected_results: Dict[str, Any]  # 预期的结果

    # 断言
    assertions: List[Callable[[TestResult], bool]]  # 自定义断言函数

    # 约束
    max_tokens: int = 2000
    max_execution_time: float = 5.0

    def __repr__(self):
        return f"TestCase({self.test_id}: {self.name})"


class TestFramework:
    """测试框架主类"""

    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
        self.mock_server = None

    def register_test(self, test_case: TestCase):
        """注册测试用例"""
        self.test_cases.append(test_case)

    def set_mock_server(self, mock_server):
        """设置 Mock MCP Server"""
        self.mock_server = mock_server

    def run_test(self, test_case: TestCase) -> TestResult:
        """运行单个测试用例"""
        start_time = time.time()
        tool_calls: List[ToolCall] = []
        total_tokens = 0
        passed = True
        error_message = None
        assertion_results = {}

        try:
            # 设置 Mock 数据
            if self.mock_server:
                self.mock_server.setup_mock_data(test_case.mock_data)

            # 执行测试场景
            # 这里会记录所有工具调用
            self._execute_scenario(test_case, tool_calls)

            # 计算 token 总数
            total_tokens = sum(call.token_count for call in tool_calls)

            # 创建临时结果用于断言
            temp_result = TestResult(
                test_id=test_case.test_id,
                name=test_case.name,
                passed=True,
                execution_time=time.time() - start_time,
                tool_calls=tool_calls,
                total_tokens=total_tokens
            )

            # 运行断言
            for i, assertion in enumerate(test_case.assertions):
                assertion_name = f"assertion_{i}"
                try:
                    result = assertion(temp_result)
                    assertion_results[assertion_name] = result
                    if not result:
                        passed = False
                except Exception as e:
                    assertion_results[assertion_name] = False
                    passed = False
                    error_message = f"Assertion {i} failed: {str(e)}"

            # 检查约束
            if total_tokens > test_case.max_tokens:
                passed = False
                error_message = f"Token limit exceeded: {total_tokens} > {test_case.max_tokens}"

            execution_time = time.time() - start_time
            if execution_time > test_case.max_execution_time:
                passed = False
                error_message = f"Time limit exceeded: {execution_time:.2f}s > {test_case.max_execution_time}s"

        except Exception as e:
            passed = False
            error_message = str(e)
            execution_time = time.time() - start_time

        return TestResult(
            test_id=test_case.test_id,
            name=test_case.name,
            passed=passed,
            execution_time=time.time() - start_time,
            tool_calls=tool_calls,
            total_tokens=total_tokens,
            error_message=error_message,
            assertions=assertion_results
        )

    def _execute_scenario(self, test_case: TestCase, tool_calls: List[ToolCall]):
        """执行测试场景（需要子类实现具体逻辑）"""
        # 这个方法由具体的测试实现覆盖
        # 在实际使用中，会通过 mock_server 来模拟工具调用
        pass

    def run_all(self, priority: Optional[TestPriority] = None,
                category: Optional[TestCategory] = None) -> List[TestResult]:
        """运行所有测试用例（可按优先级和类别筛选）"""
        tests_to_run = self.test_cases

        if priority:
            tests_to_run = [t for t in tests_to_run if t.priority == priority]

        if category:
            tests_to_run = [t for t in tests_to_run if t.category == category]

        print(f"\n{'='*60}")
        print(f"Running {len(tests_to_run)} test(s)...")
        print(f"{'='*60}\n")

        results = []
        for test_case in tests_to_run:
            print(f"Running {test_case.test_id}: {test_case.name}...")
            result = self.run_test(test_case)
            results.append(result)
            print(f"  {result.summary()}\n")

        self.results.extend(results)
        return results

    def generate_report(self) -> str:
        """生成测试报告"""
        if not self.results:
            return "No tests have been run yet."

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        total_time = sum(r.execution_time for r in self.results)
        total_tokens = sum(r.total_tokens for r in self.results)

        report = []
        report.append("\n" + "="*60)
        report.append("TEST REPORT")
        report.append("="*60)
        report.append(f"\nTotal Tests: {total}")
        report.append(f"✅ Passed: {passed} ({passed/total*100:.1f}%)")
        report.append(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
        report.append(f"\nTotal Time: {total_time:.2f}s")
        report.append(f"Total Tokens: {total_tokens}")
        report.append(f"Avg Tokens/Test: {total_tokens/total:.1f}")

        if failed > 0:
            report.append("\n" + "-"*60)
            report.append("FAILED TESTS:")
            report.append("-"*60)
            for result in self.results:
                if not result.passed:
                    report.append(f"\n{result.test_id}: {result.name}")
                    if result.error_message:
                        report.append(f"  Error: {result.error_message}")
                    report.append(f"  Tool Calls: {len(result.tool_calls)}")
                    report.append(f"  Tokens: {result.total_tokens}")

        report.append("\n" + "="*60 + "\n")

        return "\n".join(report)
