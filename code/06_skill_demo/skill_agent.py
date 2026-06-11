"""
Skill 模式演示
============
演示 Skill 模式：将 Prompt Template + Tools + Domain Knowledge + Workflow
打包为一个可复用的"技能"单元。

对比硬编码工具调用，从维护成本、复用性、上下文占用等多个角度展示 Skill 的优势。

运行方式：python skill_agent.py

API 模式：
  设置 OPENAI_API_KEY 后，Skill 的 Agent 决策可用真实 LLM 驱动
  未设置时使用内置模拟逻辑
"""

import json
import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import is_available as llm_available


# ── 基础工具 ─────────────────────────────────────────────────

def read_file(path: str) -> str:
    """读取文件"""
    fake_files = {
        "/src/api.py": """
from flask import Flask, request
app = Flask(__name__)

@app.route('/user/<id>')
def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return db.execute(query)
""",
        "/src/utils.py": """
def validate_email(email):
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[.][a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
""",
    }
    return fake_files.get(path, f"文件不存在: {path}")


def run_linter(path: str) -> str:
    """运行代码检查（模拟）"""
    issues = {
        "/src/api.py": [
            {"line": 5, "severity": "high", "message": "SQL注入漏洞：直接拼接用户输入到SQL语句"},
            {"line": 7, "severity": "medium", "message": "缺少身份验证中间件"},
        ],
        "/src/utils.py": [
            {"line": 2, "severity": "low", "message": "缺少函数文档字符串"},
        ],
    }
    result = issues.get(path, [])
    if not result:
        return "未发现问题"
    return json.dumps(result, ensure_ascii=False)


def execute_tests(pattern: str) -> str:
    """运行测试"""
    return f"测试 '{pattern}': 3 passed, 1 failed — test_login 未处理空密码"


# ── Skill 定义 ───────────────────────────────────────────────

class Skill:
    """
    Skill 将以下内容打包为一个整体：
    - Prompt Template: 告诉 LLM 如何执行这个技能
    - Tools: 该技能所需的工具
    - Domain Knowledge: 领域知识（如编码规范、常见漏洞模式）
    - Workflow: 执行流程
    """

    def __init__(self, name: str, description: str,
                 prompt_template: str, tools: dict,
                 domain_knowledge: str = "", workflow: list[str] = None):
        self.name = name
        self.description = description
        self.prompt_template = prompt_template
        self.tools = tools
        self.domain_knowledge = domain_knowledge
        self.workflow = workflow or []

    def get_schema(self) -> dict:
        """返回 Skill 的 Schema（供 Agent 发现）"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": list(self.tools.keys()),
            "workflow": self.workflow,
        }

    def get_system_prompt(self, task_context: dict = None) -> str:
        """生成该 Skill 的 System Prompt（包含领域知识）"""
        context_str = json.dumps(task_context, ensure_ascii=False) if task_context else ""
        return self.prompt_template.format(
            domain_knowledge=self.domain_knowledge,
            context=context_str,
        )


# ── 定义几个 Skill ──────────────────────────────────────────

# Skill 1: 代码审查
CODE_REVIEW_SKILL = Skill(
    name="CodeReview",
    description="对代码进行安全审查和质量检查",
    tools={"read_file": read_file, "run_linter": run_linter},
    domain_knowledge="""
常见安全漏洞：
- SQL注入：禁止字符串拼接SQL，必须使用参数化查询
- XSS：用户输入必须转义
- 敏感信息泄露：禁止在日志中打印密码、Token
- 认证缺失：API接口必须有身份验证

编码规范：
- 函数必须有文档字符串
- 变量命名采用 snake_case
""",
    workflow=["读取文件", "静态分析", "报告问题"],
    prompt_template="""你是一个代码审查专家。

你需要检查以下代码的安全性和质量。

{domain_knowledge}

请按照以下流程执行：
1. 读取需要审查的文件
2. 运行静态分析工具
3. 提供审查报告，包含：
   - 安全问题（按严重程度排序）
   - 代码质量问题
   - 改进建议

审查上下文: {context}
""",
)

# Skill 2: 测试运行
TEST_SKILL = Skill(
    name="TestRunner",
    description="运行测试并分析失败原因",
    tools={"execute_tests": execute_tests, "read_file": read_file},
    domain_knowledge="""
常见测试失败原因：
- 空值/边界值未处理
- Mock对象未正确配置
- 异步操作超时
- 环境依赖缺失
""",
    workflow=["运行测试", "分析失败", "定位问题", "提供修复建议"],
    prompt_template="""你是一个测试分析专家。

{domain_knowledge}

当测试失败时，你需要：
1. 运行测试
2. 分析每个失败的测试用例
3. 读取相关源代码定位问题
4. 提供具体的修复建议

测试上下文: {context}
""",
)


# ── Skill Manager ────────────────────────────────────────────

class SkillManager:
    """
    Skill 管理器：
    - 注册和管理 Skill
    - 按需加载 Skill（渐进式披露）
    - Agent 通过 Manager 发现和调用 Skill
    """

    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册一个 Skill"""
        self.skills[skill.name] = skill

    def list_skills(self) -> list[dict]:
        """列出所有可用 Skill（仅摘要，不加载完整内容）"""
        return [skill.get_schema() for skill in self.skills.values()]

    def activate(self, skill_name: str) -> Skill | None:
        """激活一个 Skill，获取其完整内容"""
        return self.skills.get(skill_name)

    def get_skill_prompt_size(self, skill_name: str) -> int:
        """估算 Skill 的 Prompt 占用 Token 数（用于对比）"""
        skill = self.skills.get(skill_name)
        if not skill:
            return 0
        prompt = skill.get_system_prompt()
        return len(prompt)  # 粗略估算（实际 Token 数约为字符数/4）


# ── 硬编码方式（用于对比） ──────────────────────────────────

class HardcodedAgent:
    """
    传统硬编码方式：所有工具的 Schema 和知识都硬编码在 Agent 中。
    """

    def __init__(self):
        # 所有工具 Schema 直接写死在代码中
        self.system_prompt = """你是一个全能助手，可以进行代码审查和测试分析。

可用工具：
1. read_file(path: str) — 读取文件
2. run_linter(path: str) — 运行代码检查
3. execute_tests(pattern: str) — 运行测试

代码审查规范：
- 检查SQL注入漏洞（禁止字符串拼接SQL，必须参数化查询）
- 检查XSS漏洞（用户输入必须转义）
- 检查敏感信息泄露（禁止日志打印密码、Token）
- 检查认证缺失（API接口必须有身份验证）
- 函数必须有文档字符串
- 变量命名采用 snake_case

测试分析规则：
- 检查空值/边界值处理
- 检查Mock对象配置
- 检查异步操作超时
- 检查环境依赖

请根据用户需求使用合适的工具。"""
        self.tools = {
            "read_file": read_file,
            "run_linter": run_linter,
            "execute_tests": execute_tests,
        }


# ── 对比演示 ─────────────────────────────────────────────────

def demo_comparison():
    """对比 Skill 模式和硬编码模式"""
    print("=" * 60)
    print("📌 Skill 模式 vs 硬编码模式 对比")
    print("=" * 60)

    # ── 硬编码方式 ──
    print("\n❌ 硬编码方式:")
    agent = HardcodedAgent()
    print(f"  System Prompt 大小: {len(agent.system_prompt)} 字符")
    print(f"  包含内容: 所有工具的 Schema + 所有领域知识")

    # ── Skill 方式 ──
    print("\n✅ Skill 方式:")
    manager = SkillManager()
    manager.register(CODE_REVIEW_SKILL)
    manager.register(TEST_SKILL)

    print(f"  初始加载（技能摘要）:")
    for skill_info in manager.list_skills():
        print(f"    📦 {skill_info['name']}: {skill_info['description']}")

    # 按需加载
    review_skill = manager.activate("CodeReview")
    review_prompt = review_skill.get_system_prompt({"file": "/src/api.py"})
    print(f"\n  激活 CodeReview Skill 后:")
    print(f"  Prompt 大小: {len(review_prompt)} 字符（仅加载需要的 Skill）")
    print(f"  知识域: 仅包含代码安全审查知识")

    test_skill = manager.activate("TestRunner")
    test_prompt = test_skill.get_system_prompt({"scope": "all tests"})
    print(f"\n  激活 TestRunner Skill 后:")
    print(f"  Prompt 大小: {len(test_prompt)} 字符")
    print(f"  知识域: 仅包含测试分析知识")


def demo_skill_execution():
    """演示 Skill 的执行"""
    print("\n" + "=" * 60)
    print("📌 Skill 执行演示")
    print("=" * 60)

    manager = SkillManager()
    manager.register(CODE_REVIEW_SKILL)
    manager.register(TEST_SKILL)

    # 用户：代码审查任务
    print("\n👤 用户: 审查 /src/api.py 的代码")

    # Agent 选择激活 CodeReview Skill
    print("\n💭 Agent: 这是一个代码审查任务，激活 CodeReview Skill")
    skill = manager.activate("CodeReview")

    print(f"\n📋 Skill: {skill.name}")
    print(f"📝 System Prompt:\n{skill.get_system_prompt({'file': '/src/api.py'})}")

    # 执行 Workflow
    print("\n🔧 执行 Workflow:")
    for step in skill.workflow:
        print(f"  → {step}")
        if step == "读取文件":
            result = skill.tools["read_file"]("/src/api.py")
            print(f"    读取 /src/api.py 成功")
        elif step == "静态分析":
            result = skill.tools["run_linter"]("/src/api.py")
            print(f"    发现 {len(json.loads(result))} 个问题:")
            for issue in json.loads(result):
                print(f"      ⚠️ [{issue['severity']}] {issue['message']}")
        elif step == "报告问题":
            print(f"    生成审查报告: 1个高危(SQL注入), 1个中危(缺少认证)")

    print(f"\n✅ Skill '{skill.name}' 执行完成")


def demo_reusability():
    """演示 Skill 的复用性"""
    print("\n" + "=" * 60)
    print("📌 Skill 复用性演示")
    print("=" * 60)

    manager = SkillManager()
    manager.register(CODE_REVIEW_SKILL)
    manager.register(TEST_SKILL)

    print("""
  场景：三个不同的 Agent 都需要代码审查能力

  ❌ 硬编码方式:
    Agent A: 复制审查代码 + 审查知识 → 200行
    Agent B: 复制审查代码 + 审查知识 → 200行
    Agent C: 复制审查代码 + 审查知识 → 200行
    总计: 600行代码，3处维护点
    修改审查规则 → 需要改3个地方

  ✅ Skill 方式:
    Agent A ─┐
    Agent B ─┼─→ CodeReview Skill（单一定义，集中维护）
    Agent C ─┘
    总计: 1个Skill定义，3个Agent共享
    修改审查规则 → 只需改Skill定义
    """)


# ── Token 占用对比 ─────────────────────────────────────────

def demo_token_comparison():
    """演示上下文占用的对比"""
    print("\n" + "=" * 60)
    print("📌 上下文 Token 占用对比")
    print("=" * 60)

    manager = SkillManager()
    manager.register(CODE_REVIEW_SKILL)
    manager.register(TEST_SKILL)

    hardcoded_agent = HardcodedAgent()

    # 硬编码：一次性加载所有工具和知识
    hardcoded_size = len(hardcoded_agent.system_prompt)

    # Skill：摘要 + 按需加载
    list_size = sum(len(json.dumps(s, ensure_ascii=False)) for s in manager.list_skills())
    code_review_size = manager.get_skill_prompt_size("CodeReview")
    test_size = manager.get_skill_prompt_size("TestRunner")

    print(f"""
  场景：Agent 有 2 个功能模块（CodeReview + TestRunner）

  ❌ 硬编码（全部加载）: {hardcoded_size} 字符
     所有工具Schema + 所有领域知识一直在上下文中

  ✅ Skill 模式:
     初始（仅摘要）: ~{list_size} 字符
     按需加载 CodeReview: ~{code_review_size} 字符
     按需加载 TestRunner: ~{test_size} 字符

  节省: 初始阶段节省 ~{hardcoded_size - list_size} 字符的上下文空间
        不相关的 Skill 不会占用上下文
  """)


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║          Skill 模式演示                              ║
    ║                                                      ║
    ║  Skill = Prompt Template + Tools +                   ║
    ║          Domain Knowledge + Workflow                 ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY（Skill Agent 选择可用真实 LLM 驱动）\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用内置模拟逻辑")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    demo_comparison()
    demo_skill_execution()
    demo_reusability()
    demo_token_comparison()

    print("\n" + "=" * 60)
    print("""
  💡 Skill 模式总结:
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  1. 内聚性: Prompt + Tool + Knowledge + Workflow     │
  │     打包为一个整体                                     │
  │                                                        │
  │  2. 复用性: 一个Skill定义，多个Agent共享               │
  │                                                        │
  │  3. 上下文效率: 按需加载，不相关Skill不占Token          │
  │                                                        │
  │  4. 可维护性: 修改集中在Skill定义，不影响Agent         │
  │                                                        │
  │  5. 可演进性: Skill可独立版本化、独立测试               │
  └────────────────────────────────────────────────────────┘
    """)
