"""
ReAct Agent 实现
===============
完整实现一个 ReAct（Reasoning + Acting）Agent。

核心范式：Thought → Action → Observation → Thought → Action → ...
每一轮：
  1. Thought:  LLM 分析当前状态，推理下一步做什么
  2. Action:   调用工具
  3. Observation: 获取工具结果，成为下一轮 Thought 的输入

支持人工参与模式：当需要真实环境反馈时，可暂停等待人工输入 Observation。

运行方式：python react_agent.py

API 模式：
  设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM 驱动模式
  未设置时使用内置的模拟推理逻辑
"""

import json
import os
import re
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat_structured, is_available as llm_available

# ── 工具集 ───────────────────────────────────────────────────
def search(query: str) -> str:
    """搜索工具（模拟）"""
    fake_knowledge = {
        "python": "Python 3.13 于 2024年10月发布，主要新特性包括改进的类型系统和新AST。",
        "react": "React 19 引入了 Server Components 和新的 Hooks API。",
        "agent": "LLM Agent 正在快速发展，Multimodal Agent 是2025年的趋势之一。",
    }
    for key, value in fake_knowledge.items():
        if key.lower() in query.lower():
            return value
    return f"搜索 '{query}'：未找到相关信息，建议缩小搜索范围。"


def read_file(path: str) -> str:
    """读取文件工具（模拟）"""
    fake_files = {
        "/project/main.py": "from models import Model\n\ndef main():\n    model = Model()\n    model.train()\n    print('Training complete')",
        "/project/models.py": "class Model:\n    def __init__(self):\n        self.layers = []\n    def train(self):\n        print('Training...')",
        "/project/config.json": '{"learning_rate": 0.001, "batch_size": 32, "epochs": 10}',
    }
    if path in fake_files:
        return f"文件 {path}:\n```\n{fake_files[path]}\n```"
    return f"错误：文件 {path} 未找到。"


def write_file(path: str, content: str) -> str:
    """写入文件工具（模拟）"""
    print(f"    💾 [模拟写入] {path}: {content[:50]}...")
    return f"文件 {path} 写入成功。"


def calculate(expression: str) -> str:
    """计算工具"""
    try:
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return f"表达式包含不允许的字符"
        return f"计算 {expression} = {eval(expression)}"
    except Exception as e:
        return f"计算错误: {e}"


# ── ReAct Prompt ─────────────────────────────────────────────
REACT_SYSTEM_PROMPT = """你是一个ReAct Agent。你必须严格遵循以下格式：

可用工具：
- search(query: str) → 搜索信息
- read_file(path: str) → 读取文件内容
- write_file(path: str, content: str) → 写入文件
- calculate(expression: str) → 计算数学表达式

输出格式（每次只能选择一个工具或给出最终答案）：

对于需要调用工具的步骤：
Thought: <你的推理过程>
Action: <工具名>
Action Input: <JSON格式的参数>

对于最终答案：
Thought: <推理过程>
Final Answer: <最终回答>

重要规则：
1. 每次只能输出一个 Thought + Action 或 Thought + Final Answer
2. Action Input 必须是有效的 JSON
3. 如果工具返回错误，请思考替代方案
4. 当你有足够信息回答用户时，使用 Final Answer"""


# ── ReAct LLM 推理（真实API优先，模拟回退） ──────────────

REACT_STRUCTURED_PROMPT = """你是一个 ReAct Agent。你必须严格输出 JSON 格式的决策。

可用工具：
- search(query: str) → 搜索信息
- read_file(path: str) → 读取文件内容
- write_file(path: str, content: str) → 写入文件
- calculate(expression: str) → 计算数学表达式

输出格式：
{
    "type": "action 或 final",
    "thought": "你的推理过程（中文）",
    "action": "工具名（type=action时必填，type=final时填null）",
    "action_input": "参数值（type=action时必填，type=final时填null）",
    "final_answer": "最终答案（仅type=final时填写）"
}

规则：
1. 每次只选一个工具或给出最终答案
2. 如果工具返回错误，思考替代方案
3. 当有足够信息回答时，type=final"""


def react_llm_think(messages: list[dict], task: str, step: int,
                    last_observation: str) -> dict:
    """
    ReAct 的核心：让 LLM 根据当前观察做出推理。
    优先调用真实 LLM API，不可用时回退到规则模拟。
    """
    # ── 尝试真实 API ──
    if llm_available():
        structured_messages = [
            {"role": "system", "content": REACT_STRUCTURED_PROMPT},
            {"role": "user", "content": f"任务: {task}"},
        ]
        # 添加历史
        for h in messages:
            if h["role"] != "system":
                structured_messages.append(h)
        if last_observation:
            structured_messages.append({"role": "user", "content": f"上一步 Observation: {last_observation}\n请决定下一步（step {step}）。输出 JSON。"})
        else:
            structured_messages.append({"role": "user", "content": f"请开始第一步（step {step}）。输出 JSON。"})

        result = chat_structured(structured_messages, temperature=0.3)
        if result:
            print("  🌐 [真实LLM ReAct决策]")
            return {
                "thought": result.get("thought", ""),
                "type": result.get("type", "final"),
                "action": result.get("action"),
                "action_input": result.get("action_input"),
                "final_answer": result.get("final_answer"),
            }

    # ── 回退：规则模拟 ──
    print("  💻 [规则模拟ReAct]")
    return _mock_react_think(messages, task, step, last_observation)


def _mock_react_think(messages: list[dict], task: str, step: int,
                      last_observation: str) -> dict:
    """
    模拟 ReAct 推理（规则驱动）。
    仅在真实 API 不可用时作为回退方案。
    """
    if "搜索" in task and "文件" in task and step == 1:
        return {
            "thought": "用户需要我先搜索信息，然后再读文件。先搜索关于这个主题的最新信息。",
            "type": "action",
            "action": "search",
            "action_input": task.split("搜索")[-1].strip().strip("'").strip('"') or "Python Agent",
        }
    elif "搜索" in task and step == 2 and last_observation:
        return {
            "thought": "搜索完成，但我还需要读取项目的配置和代码文件来确认。",
            "type": "action",
            "action": "read_file",
            "action_input": "/project/config.json",
        }
    elif "搜索" in task and step == 3 and last_observation:
        return {
            "thought": "已经获取了配置信息和搜索结果，现在有足够的信息来回答用户了。让我总结一下。",
            "type": "final",
            "action": None,
            "final_answer": f"基于多步分析的结果，结论：任务已通过搜索和文件分析完成。",
        }
    elif "计算" in task or any(op in task for op in ["+", "-", "*", "/"]):
        expr_match = re.search(r'[\d\+\-\*\/\(\)\.\s]+', task)
        expr = expr_match.group().strip() if expr_match else "1+1"
        if step == 1:
            return {
                "thought": f"需要计算表达式: {expr}。使用 calculate 工具。",
                "type": "action",
                "action": "calculate",
                "action_input": expr,
            }
        elif step == 2:
            return {
                "thought": f"计算完成，结果是 {last_observation}。直接告诉用户。",
                "type": "final",
                "action": None,
                "final_answer": f"计算结果: {last_observation}",
            }
    else:
        return {
            "thought": "这是一个简单问题，我可以直接回答。",
            "type": "final",
            "action": None,
            "final_answer": f"关于「{task}」的处理已完成。",
        }


# ── ReAct Agent 主循环 ──────────────────────────────────────
class ReActAgent:
    def __init__(self, human_in_loop: bool = False):
        self.human_in_loop = human_in_loop  # 是否需要人工参与观察
        self.tools = {
            "search": search,
            "read_file": read_file,
            "write_file": write_file,
            "calculate": calculate,
        }
        self.history: list[dict] = []

    def run(self, task: str, max_steps: int = 10) -> str:
        print("=" * 60)
        print(f"🤖 ReAct Agent 启动")
        print(f"📋 任务: {task}")
        print("=" * 60)

        observation = ""
        messages = [{"role": "system", "content": REACT_SYSTEM_PROMPT}]

        for step in range(1, max_steps + 1):
            print(f"\n{'─' * 40}")
            print(f"📍 Step {step}")

            # ── Thought ──
            llm_response = react_llm_think(messages, task, step, observation)
            thought = llm_response["thought"]
            print(f"  💭 Thought: {thought}")

            # ── 检查是否为最终答案 ──
            if llm_response["type"] == "final":
                final_answer = llm_response["final_answer"]
                print(f"  ✅ Final Answer: {final_answer}")
                self._print_summary(final_answer, step)
                return final_answer

            # ── Action ──
            action = llm_response["action"]
            action_input = llm_response["action_input"]
            print(f"  🔧 Action: {action}({action_input})")

            # ── Execute ──
            tool = self.tools.get(action)
            if not tool:
                observation = f"错误：未知工具 '{action}'。可用工具：{list(self.tools.keys())}"
            else:
                observation = tool(action_input)

            # ── Observation（可选人工参与） ──
            if self.human_in_loop:
                print(f"  🤖 工具返回: {observation}")
                human_feedback = input(f"  👤 请输入补充观察（直接回车跳过）: ").strip()
                if human_feedback:
                    observation = f"{observation}\n[人工反馈] {human_feedback}"

            print(f"  👁️  Observation: {observation}")

            # ── 记录到历史 ──
            step_record = {
                "step": step,
                "thought": thought,
                "action": action,
                "action_input": str(action_input),
                "observation": observation,
            }
            self.history.append(step_record)
            messages.append({"role": "assistant", "content": f"Thought: {thought}\nAction: {action}({action_input})"})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        print(f"\n⚠️ 达到最大步数 {max_steps}，强制终止")
        return "任务未完成"

    def _print_summary(self, result: str, steps: int):
        print(f"\n{'=' * 60}")
        print(f"📊 执行总结")
        print(f"{'=' * 60}")
        print(f"  总步数: {steps}")
        print(f"  工具调用: {[h['action'] for h in self.history]}")
        print(f"  结果: {result[:200]}")

    def export_trace(self) -> str:
        """导出完整的 ReAct 执行轨迹"""
        return json.dumps(self.history, ensure_ascii=False, indent=2)


# ── 演示 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║          ReAct Agent 演示                            ║
    ║                                                      ║
    ║  模式: Thought → Action → Observation → Thought → ...║
    ║                                                      ║
    ║  可用工具: search, read_file, write_file, calculate  ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，使用真实 LLM 驱动 ReAct 决策\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用内置规则模拟 ReAct 决策")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    # ── 演示1：多步搜索和分析任务 ──
    print("\n📌 演示1：多步搜索和分析")
    agent = ReActAgent(human_in_loop=False)
    agent.run("搜索 Python Agent 的最新发展，然后分析项目配置文件")
    print(f"\n  📋 完整执行轨迹:\n{agent.export_trace()}")

    # ── 演示2：计算任务（简单单步） ──
    print("\n\n📌 演示2：简单计算任务")
    agent2 = ReActAgent(human_in_loop=False)
    agent2.run("(15 + 8) * 3 - 12 等于多少？")

    # ── 演示3：人工参与模式 ──
    print("\n\n📌 演示3：人工参与模式（Human-in-the-Loop）")
    print("  在这个模式中，你可以在每个 Observation 之后补充反馈。")
    choice = input("  是否启用人工参与模式？(y/n): ").strip().lower()
    if choice == "y":
        agent3 = ReActAgent(human_in_loop=True)
        agent3.run("搜索最新的AI新闻")

    print("\n" + "=" * 60)
    print("""
  💡 ReAct 核心总结:
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  Thought → Action → Observation → Thought → ...       │
  │                                                        │
  │  1. 每个 Thought 基于最新的 Observation               │
  │  2. Agent 能根据结果调整策略                           │
  │  3. 工具执行失败可以重试或换方案                        │
  │  4. Agent 自主判断何时任务完成                         │
  │                                                        │
  │  局限：缺乏全局规划，可能"走一步看一步"偏离目标          │
  │  → 因此需要 Plan-and-Execute                           │
  └────────────────────────────────────────────────────────┘
    """)
