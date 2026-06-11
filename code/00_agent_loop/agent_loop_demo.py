"""
Agent Loop 核心概念演示
=======================
演示 Agent 最核心的执行循环：观察(Observe) → 思考(Think) → 行动(Act) → 观察(Observe)

运行方式：python agent_loop_demo.py

API 模式：
  设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM 驱动模式
  未设置时使用内置的模拟推理逻辑
"""

import json
import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat_structured, is_available as llm_available


# ── 模拟工具集 ─────────────────────────────────────────────
def search_files(query: str) -> str:
    """模拟文件搜索工具"""
    fake_files = {
        "config": ["config.yaml", "config.json", ".env.example"],
        "test": ["test_main.py", "test_utils.py", "conftest.py"],
        "model": ["model.py", "model_v2.py", "model_legacy.py"],
    }
    results = fake_files.get(query.lower(), [])
    return f"找到 {len(results)} 个文件: {results}" if results else f"未找到与 '{query}' 相关的文件"


def read_file(path: str) -> str:
    """模拟文件读取工具"""
    fake_contents = {
        "config.yaml": "server: {port: 8080, debug: true}",
        "test_main.py": "def test_login(): ...\ndef test_logout(): ...",
        "model.py": "class Model(nn.Module):\n    def __init__(self): ...",
    }
    return fake_contents.get(path, f"[错误] 文件 {path} 不存在")


def run_tests(pattern: str) -> str:
    """模拟测试运行工具"""
    return f"运行测试 '{pattern}': 5 passed, 2 failed, 0 error"


# 工具注册表
TOOLS = {
    "search_files": search_files,
    "read_file": read_file,
    "run_tests": run_tests,
}

# ── 真实 LLM 推理 Prompt ──────────────────────────────────

AGENT_LOOP_SYSTEM_PROMPT = """你是一个 Agent，你需要根据任务和环境反馈，决定下一步行动。

可用工具：
- search_files(query: str) — 搜索文件，返回匹配的文件列表
- read_file(path: str) — 读取文件内容
- run_tests(pattern: str) — 运行测试

你必须输出 JSON 格式的决策：
{
    "thought": "你的推理过程（用中文）",
    "action": "工具名",         // 如果不需操作，设为 null
    "action_input": "参数值",   // 如果不需操作，设为 null
    "final_answer": "最终答案"  // 仅在任务可以完成时填写，否则为 null
}

规则：
1. 每次只选择一个工具
2. 根据 Observation 调整下一步
3. 当有足够信息时，设置 action=null 并填写 final_answer"""


def _build_agent_messages(task: str, observation: str, history: list[dict]) -> list[dict]:
    """构建发送给 LLM 的消息列表"""
    messages = [{"role": "system", "content": AGENT_LOOP_SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": f"任务: {task}"})

    for h in history:
        messages.append({"role": "assistant", "content": f"Thought: {h['thought']}\nAction: {h['action']}({h['action_input']})"})
        messages.append({"role": "user", "content": f"Observation: {h['observation']}"})

    if observation:
        messages.append({"role": "user", "content": f"上一步 Observation: {observation}\n请决定下一步。"})
    else:
        messages.append({"role": "user", "content": "请开始第一步。"})

    return messages


def llm_think(task: str, observation: str, history: list[dict]) -> dict:
    """
    Agent 的思考环节。
    优先调用真实 LLM API，不可用时回退到模拟规则。
    """
    # ── 尝试真实 API ──
    if llm_available():
        messages = _build_agent_messages(task, observation, history)
        result = chat_structured(messages, temperature=0.3)
        if result:
            print("  🌐 [真实LLM决策]")
            return {
                "thought": result.get("thought", ""),
                "action": result.get("action"),
                "action_input": result.get("action_input"),
                "final_answer": result.get("final_answer"),
            }

    # ── 回退：模拟规则 ──
    print("  💻 [模拟规则决策]")
    return _mock_llm_think(task, observation, history)


def _mock_llm_think(task: str, observation: str, history: list[dict]) -> dict:
    """
    模拟 LLM 的"思考"过程（规则驱动）。
    仅在真实 API 不可用时作为回退方案。
    """
    step_count = len(history)

    if step_count == 0 and "测试" in task:
        return {
            "thought": "要运行测试，我需要先找到所有测试文件。让我搜索一下。",
            "action": "search_files",
            "action_input": "test",
        }
    if step_count == 0 and "模型" in task:
        return {
            "thought": "需要先找到模型相关的文件。",
            "action": "search_files",
            "action_input": "model",
        }

    if step_count == 1 and observation and "test_main" in observation:
        return {
            "thought": "找到了测试文件，让我读取 test_main.py 看看具体内容。",
            "action": "read_file",
            "action_input": "test_main.py",
        }
    if step_count == 1 and observation and "model" in observation:
        return {
            "thought": "找到了模型文件，让我读取 model.py。",
            "action": "read_file",
            "action_input": "model.py",
        }

    if step_count == 2 and "test" in str(history[-1].get("observation", "")):
        return {
            "thought": "已经了解了测试内容，现在运行这些测试看看结果。",
            "action": "run_tests",
            "action_input": "test_*.py",
        }

    return {
        "thought": "所有操作已完成，我已获取了足够的信息来回答用户的问题。",
        "action": None,
        "action_input": None,
        "final_answer": f"任务 '{task}' 已完成。经过 {step_count + 1} 步操作，已搜索文件、读取内容并运行了测试。"
    }


# ── Agent Loop 核心 ─────────────────────────────────────────
def agent_loop(task: str, max_steps: int = 10) -> str:
    """
    Agent 的核心执行循环。

    每一轮循环包含三个阶段：
    1. Think  (思考)：根据任务和当前观察，决定下一步做什么
    2. Act    (行动)：执行选择的工具
    3. Observe(观察)：获取工具执行的结果，成为下一轮思考的输入
    """
    history: list[dict] = []
    observation = ""

    print("=" * 60)
    print(f"🤖 Agent 启动，任务: {task}")
    print("=" * 60)

    for step in range(1, max_steps + 1):
        print(f"\n{'─' * 40}")
        print(f"📍 Step {step}")

        # ── 1. Think：让 LLM 推理下一步（真实API优先，模拟回退）──
        llm_response = llm_think(task, observation, history)
        thought = llm_response["thought"]
        action = llm_response["action"]
        action_input = llm_response["action_input"]

        print(f"  💭 Thought: {thought}")

        # ── 2. 判断是否终止 ──
        if action is None:
            print(f"  ✅ Agent 判定任务完成")
            print(f"\n📋 最终结果: {llm_response.get('final_answer', '任务完成')}")
            return llm_response.get("final_answer", "任务完成")

        # ── 3. Act：执行工具 ──
        print(f"  🔧 Action: {action}({action_input})")
        tool_func = TOOLS.get(action)
        if not tool_func:
            observation = f"[错误] 未知工具: {action}"
        else:
            observation = tool_func(action_input)

        # ── 4. Observe：记录观察结果 ──
        print(f"  👁️  Observation: {observation}")

        # ── 5. 记录本轮历史 ──
        history.append({
            "step": step,
            "thought": thought,
            "action": action,
            "action_input": action_input,
            "observation": observation,
        })

    print(f"\n⚠️ 达到最大步数 {max_steps}，Agent 强制终止")
    return "任务未完成：达到最大步数限制"


# ── 运行演示 ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║        Agent Loop 核心概念演示                       ║
    ║                                                      ║
    ║  循环结构:                                           ║
    ║    ┌──────────┐    ┌──────────┐    ┌──────────┐     ║
    ║    │ Observe  │───→│  Think   │───→│   Act    │     ║
    ║    │  (观察)  │    │  (思考)  │    │  (行动)  │     ║
    ║    └──────────┘    └──────────┘    └──────────┘     ║
    ║         ↑                               │            ║
    ║         └───────────────────────────────┘            ║
    ║                                                      ║
    ║  关键洞察：                                          ║
    ║  - 每次行动的结果反馈给下一次思考                     ║
    ║  - Agent 自主决定何时终止                             ║
    ║  - 出现错误时，Agent 可观察错误并调整策略             ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，使用真实 LLM 驱动 Agent Loop\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用内置模拟规则演示 Agent Loop")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    # 测试任务1：运行测试
    agent_loop("帮我运行所有测试文件")

    print("\n" + "=" * 60 + "\n")

    # 测试任务2：检查模型文件
    agent_loop("帮我检查代码中的模型实现")
