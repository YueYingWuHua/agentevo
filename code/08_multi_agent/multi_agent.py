"""
Multi-Agent 协作演示
==================
演示多个 Agent 协作完成复杂任务的模式：

1. Sequential：Agent A → Agent B → Agent C
2. Hierarchical：Master Agent 调度多个 Worker Agent
3. Debate：多个 Agent 讨论并达成共识

运行方式：python multi_agent.py

API 模式：
  设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM 驱动模式
  未设置时使用内置的模拟逻辑
"""

import json
import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat as llm_chat, is_available as llm_available


# ── 基础工具 ─────────────────────────────────────────────────

def search(query: str) -> str:
    """搜索"""
    return f"关于 '{query}' 的搜索结果: Python 3.13 性能提升显著，FastAPI 是流行的异步框架。"


def read_file(path: str) -> str:
    """读文件"""
    return f"// {path}\nconst app = express();\napp.get('/api', (req, res) => res.json({{data: []}}));"


def run_tests(path: str) -> str:
    """运行测试"""
    return f"测试 {path}: 10 passed, 0 failed"


def lint_code(path: str) -> str:
    """代码检查"""
    return f"Lint {path}: 2 warnings — 缺少类型注解，函数过长"


# ── 基础 Agent ───────────────────────────────────────────────

class BaseAgent:
    """所有 Agent 的基类"""

    def __init__(self, name: str, role: str, tools: dict = None):
        self.name = name
        self.role = role
        self.tools = tools or {}

    def think_and_act(self, input_data: str, context: dict = None) -> dict:
        """Agent 的核心方法：接收输入，返回输出"""
        raise NotImplementedError


# ── 具体 Agent 定义 ─────────────────────────────────────────

class CoderAgent(BaseAgent):
    """编码 Agent"""

    def __init__(self):
        super().__init__(
            name="Coder",
            role="代码编写",
            tools={"search": search, "read_file": read_file},
        )

    def think_and_act(self, input_data: str, context: dict = None) -> dict:
        print(f"    🧑‍💻 [{self.name}] 开始编写: {input_data}")
        # 搜索最佳实践
        search_result = self.tools["search"]("Python best practices")
        print(f"    🧑‍💻 [{self.name}] 搜索最佳实践: {search_result[:50]}...")

        # 生成代码
        code = f"def solution(input):\n    # 处理: {input_data}\n    return processed_result"
        print(f"    🧑‍💻 [{self.name}] 生成代码完成")

        return {
            "agent": self.name,
            "output": code,
            "metadata": {"lines": 3, "language": "Python"},
        }


class ReviewerAgent(BaseAgent):
    """代码审查 Agent"""

    def __init__(self):
        super().__init__(
            name="Reviewer",
            role="代码审查",
            tools={"lint_code": lint_code},
        )

    def think_and_act(self, input_data: str, context: dict = None) -> dict:
        print(f"    🔍 [{self.name}] 开始审查代码...")

        # 运行 Lint
        lint_result = self.tools["lint_code"]("submission.py")
        print(f"    🔍 [{self.name}] {lint_result}")

        # 判断是否通过
        approved = "0 errors" in lint_result or "2 warnings" in lint_result

        return {
            "agent": self.name,
            "output": "APPROVED" if approved else "REJECTED",
            "metadata": {"issues": lint_result, "approved": approved},
        }


class TesterAgent(BaseAgent):
    """测试 Agent"""

    def __init__(self):
        super().__init__(
            name="Tester",
            role="测试执行",
            tools={"run_tests": run_tests},
        )

    def think_and_act(self, input_data: str, context: dict = None) -> dict:
        print(f"    🧪 [{self.name}] 开始测试...")
        test_result = self.tools["run_tests"]("all_tests")
        print(f"    🧪 [{self.name}] {test_result}")

        return {
            "agent": self.name,
            "output": test_result,
            "metadata": {"passed": 10, "failed": 0},
        }


class AnalystAgent(BaseAgent):
    """分析 Agent"""

    def __init__(self):
        super().__init__(
            name="Analyst",
            role="需求分析",
            tools={"search": search},
        )

    def think_and_act(self, input_data: str, context: dict = None) -> dict:
        print(f"    📊 [{self.name}] 分析需求: {input_data}")
        search_result = self.tools["search"](input_data)
        analysis = {
            "requirement": input_data,
            "feasibility": "high",
            "estimated_effort": "medium",
            "dependencies": ["Python 3.10+", "FastAPI"],
            "research": search_result[:100],
        }
        print(f"    📊 [{self.name}] 分析完成: 可行性={analysis['feasibility']}")
        return {"agent": self.name, "output": analysis}


# ── 协作模式1: Sequential ───────────────────────────────────

def demo_sequential():
    """
    Sequential 协作：
    Agent A → Agent B → Agent C
    前一个的输出是后一个的输入，形成流水线。
    """
    print("\n" + "=" * 60)
    print("📌 模式1: Sequential（顺序协作）")
    print("    Coder → Reviewer → Tester")
    print("=" * 60)

    task = "实现一个用户认证API"

    # 1. Coder 写代码
    coder = CoderAgent()
    code_result = coder.think_and_act(task)

    # 2. Reviewer 审查
    reviewer = ReviewerAgent()
    review_result = reviewer.think_and_act(code_result["output"])

    # 3. Tester 测试（仅在审查通过后）
    if review_result["metadata"]["approved"]:
        print(f"    ✅ 审查通过，进入测试阶段")
        tester = TesterAgent()
        test_result = tester.think_and_act(code_result["output"])
    else:
        print(f"    ❌ 审查不通过，返回修改")

    print(f"\n  📊 Sequential 流水线结果:")
    print(f"     Coder → {code_result['metadata']['lines']}行代码")
    print(f"     Reviewer → {review_result['output']}")
    print(f"     Tester → 10 passed, 0 failed")


# ── 协作模式2: Hierarchical ────────────────────────────────

class MasterAgent:
    """
    Master Agent：任务调度中心。

    接收复杂任务，分配给合适的 Worker Agent，汇总结果。
    """

    def __init__(self):
        self.workers = {
            "analyst": AnalystAgent(),
            "coder": CoderAgent(),
            "reviewer": ReviewerAgent(),
            "tester": TesterAgent(),
        }

    def dispatch(self, task: str) -> dict:
        """根据任务类型分派给合适的 Agent（真实LLM优先）"""
        print(f"\n  👑 [Master] 收到任务: {task}")
        print(f"  👑 [Master] 分析任务类型...")

        # ── 尝试用真实 LLM 分析并分派 ──
        routing = self._llm_classify_task(task) if llm_available() else None
        if routing:
            print(f"  🌐 [Master LLM] 任务分类: {routing}")

        results = {}

        # 判断任务类型并分派
        if "分析" in task or "调研" in task or (routing and "analyst" in routing):
            print(f"  👑 [Master] 分派给 Analyst")
            results["analysis"] = self.workers["analyst"].think_and_act(task)

        if "代码" in task or "实现" in task or "写" in task or (routing and "coder" in routing):
            print(f"  👑 [Master] 分派给 Coder")
            results["code"] = self.workers["coder"].think_and_act(task)

            if "code" in results:
                print(f"  👑 [Master] 自动触发 Review")
                results["review"] = self.workers["reviewer"].think_and_act(
                    results["code"]["output"]
                )

                if results["review"]["metadata"]["approved"]:
                    print(f"  👑 [Master] 自动触发 Test")
                    results["test"] = self.workers["tester"].think_and_act(
                        results["code"]["output"]
                    )

        elif "审查" in task or "review" in task.lower() or (routing and "reviewer" in routing):
            print(f"  👑 [Master] 分派给 Reviewer")
            results["review"] = self.workers["reviewer"].think_and_act(task)

        elif "测试" in task or "test" in task.lower() or (routing and "tester" in routing):
            print(f"  👑 [Master] 分派给 Tester")
            results["test"] = self.workers["tester"].think_and_act(task)

        # 汇总结果
        print(f"\n  👑 [Master] 汇总结果:")
        summary = {"task": task, "results": {}, "status": "success"}
        for key, result in results.items():
            summary["results"][key] = {
                "agent": result["agent"],
                "output": str(result["output"])[:100],
            }
            print(f"    - {result['agent']}: {str(result['output'])[:80]}...")

        return summary

    def _llm_classify_task(self, task: str) -> list[str] | None:
        """用真实 LLM 对任务进行分类，决定派发给哪些 Agent"""
        prompt = f"""分析以下任务，决定需要哪些 Agent 参与。

可用 Agent: analyst（需求分析）, coder（编码）, reviewer（代码审查）, tester（测试）

任务: {task}

请仅输出涉及的一个或多个 Agent 名称，用逗号分隔，如: "analyst,coder"
不要输出其他内容。"""

        result = llm_chat([{"role": "user", "content": prompt}], temperature=0.3)
        if result:
            print(f"  🌐 [LLM分类] 原始输出: {result.strip()}")
            # 解析输出
            agents = []
            for name in ["analyst", "coder", "reviewer", "tester"]:
                if name in result.lower():
                    agents.append(name)
            return agents if agents else None
        return None


def demo_hierarchical():
    """Hierarchical 协作：Master Agent 调度 Worker Agent"""
    print("\n" + "=" * 60)
    print("📌 模式2: Hierarchical（层级协作）")
    print("    Master → [Analyst, Coder, Reviewer, Tester]")
    print("=" * 60)

    master = MasterAgent()
    result = master.dispatch("分析和实现一个用户认证API的代码")

    print(f"\n  📊 Hierarchical 结果:")
    print(f"     任务状态: {result['status']}")
    print(f"     涉及Agent: {list(result['results'].keys())}")


# ── 协作模式3: Debate ────────────────────────────────────────

def demo_debate():
    """
    Debate 协作：
    多个 Agent 对同一问题给出不同角度的分析，
    综合多视角做出决策。
    """
    print("\n" + "=" * 60)
    print("📌 模式3: Debate（多角度讨论）")
    print("=" * 60)

    question = "应该用 SQLAlchemy 还是 raw SQL 来构建这个API？"
    print(f"\n  讨论议题: {question}")

    # 多个 Agent 各自提供观点（模拟）
    perspectives = {
        "Architect": {
            "view": "SQLAlchemy",
            "reasoning": "ORM 提供更好的抽象层，便于数据库迁移和代码维护。团队有 SQLAlchemy 经验。",
            "risk": "中等：学习曲线较陡，但生态成熟",
        },
        "SecurityExpert": {
            "view": "SQLAlchemy",
            "reasoning": "ORM 自动参数化查询，避免 SQL 注入。raw SQL 更容易出现安全问题。",
            "risk": "低：SQLAlchemy 的安全性已被广泛验证",
        },
        "PerformanceEngineer": {
            "view": "Raw SQL（部分）",
            "reasoning": "复杂查询场景下 raw SQL 性能更好。建议主要用 ORM，复杂查询使用 raw SQL。",
            "risk": "低：只要做好参数化，raw SQL 也可以安全",
        },
    }

    for role, opinion in perspectives.items():
        print(f"\n  🎯 {role}:")
        print(f"     推荐: {opinion['view']}")
        print(f"     理由: {opinion['reasoning']}")
        print(f"     风险: {opinion['risk']}")

    # 综合观点
    print(f"\n  📊 综合结论:")
    print(f"     主方案: SQLAlchemy ORM（3票支持）")
    print(f"     补充: 复杂查询场景允许使用 raw SQL（参数化）")


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║        Multi-Agent 协作演示                          ║
    ║                                                      ║
    ║  1. Sequential:   Coder → Reviewer → Tester        ║
    ║  2. Hierarchical: Master → Workers                  ║
    ║  3. Debate:       多视角讨论                         ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，Multi-Agent 协作由真实 LLM 驱动\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用内置模拟逻辑")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    demo_sequential()
    demo_hierarchical()
    demo_debate()

    print("\n" + "=" * 60)
    print("""
  💡 Multi-Agent 总结:
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  Sequential:   流水线模式，每个Agent专注一个环节       │
  │                适合：CI/CD、代码审查流程                │
  │                                                        │
  │  Hierarchical: 主从模式，Master 调度 Worker            │
  │                适合：复杂项目管理、多步骤任务           │
  │                                                        │
  │  Debate:       讨论模式，多视角分析                     │
  │                适合：架构决策、风险评估                 │
  │                                                        │
  │  Parallel:     并行模式，同时处理独立子任务             │
  │                适合：大数据分析、批量处理               │
  └────────────────────────────────────────────────────────┘
    """)
