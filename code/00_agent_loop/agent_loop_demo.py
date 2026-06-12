"""
Agent Loop 核心概念演示
=======================
演示 Agent 最核心的执行循环：观察(Observe) → 思考(Think) → 行动(Act) → 观察(Observe)

运行方式：
  python agent_loop_demo.py                      # 默认：Prompt JSON 模式
  python agent_loop_demo.py --mode native-fc     # 原生 Function Calling 模式
  python agent_loop_demo.py --mode compare       # 两种模式对比

API 模式：
  设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM 驱动模式
  未设置时使用内置的模拟推理逻辑

两种工具调用方式对比：
┌──────────────────────┬──────────────────────────────┐
│  Prompt 强制 JSON     │  原生 Function Calling       │
│  (chat_structured)    │  (chat_with_tools)           │
├──────────────────────┼──────────────────────────────┤
│ 约束层级: Prompt 级    │ 约束层级: 模型训练级          │
│ 依赖模型"记住" JSON   │ API 的 tools 参数传递 Schema │
│ 格式要求               │ LLM 自动判断是否调工具        │
├──────────────────────┼──────────────────────────────┤
│ 问题: 上下文越长，     │ 不受上下文长度影响            │
│ 模型越容易忘记 JSON   │ token 生成不需手动维护        │
│ 格式要求 → 注意力漂移  │ JSON 括号/引号配对            │
└──────────────────────┴──────────────────────────────┘
"""

import argparse
import json
import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat_structured, chat_with_tools, is_available as llm_available


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


TOOLS = {
    "search_files": search_files,
    "read_file": read_file,
    "run_tests": run_tests,
}

# ── 原生 Function Calling 的工具 Schema ──────────────────
# 这是传给 API tools 参数的结构，LLM 不需要"记住"它
NATIVE_FC_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "搜索文件，返回匹配的文件列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "运行测试",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "测试匹配模式，如 test_*.py"}
                },
                "required": ["pattern"],
            },
        },
    },
]

# ── Prompt 强制 JSON 模式（当前 Demo 的方案） ──────────────
# 约束方式：在 System Prompt 中要求 LLM 输出 JSON。
# 问题：约束是 Prompt 级的，每轮都需要模型"记住"格式指令。
#       上下文越长 → 注意力越分散 → 越容易忘记 JSON 格式 → 输出不可解析。

AGENT_LOOP_JSON_PROMPT = """你是一个 Agent，你需要根据任务和环境反馈，决定下一步行动。

可用工具：
- search_files(query: str) — 搜索文件
- read_file(path: str) — 读取文件内容
- run_tests(pattern: str) — 运行测试

你必须输出 JSON 格式的决策：
{
    "thought": "你的推理过程（用中文）",
    "action": "工具名",
    "action_input": "参数值",
    "final_answer": null
}

如果不需要继续操作（任务完成），设置 action=null 并填写 final_answer。"""


# ── 原生 Function Calling 模式的 System Prompt ─────────────
# 约束方式：工具 Schema 由 API 的 tools 参数传递，模型训练时就支持此机制。
# 优势：不依赖 Prompt 维持格式约束，模型用自然语言输出 reasoning，
#       API 在模型"想调工具"时通过 tool_calls 字段返回结构化调用。

AGENT_LOOP_FC_PROMPT = """你是一个 Agent，你需要根据任务和环境反馈，决定下一步行动。

你可以使用工具来完成以下操作：
- 搜索文件 (search_files)
- 读取文件内容 (read_file)
- 运行测试 (run_tests)

请用中文自然语言描述你的推理过程。如果不需要继续操作，给出最终结论。"""


# ── 消息构建 ─────────────────────────────────────────────────
def _build_messages(task: str, observation: str, history: list[dict],
                    system_prompt: str = AGENT_LOOP_JSON_PROMPT) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": f"任务: {task}"})

    for h in history:
        messages.append({"role": "assistant",
            "content": f"Thought: {h['thought']}\nAction: {h['action']}({h.get('action_input', '')})"})
        messages.append({"role": "user", "content": f"Observation: {h['observation']}"})

    if observation:
        messages.append({"role": "user", "content": f"上一步 Observation: {observation}\n请决定下一步。"})
    else:
        messages.append({"role": "user", "content": "请开始第一步。"})

    return messages


# ══════════════════════════════════════════════════════════════
# 模式一：Prompt 强制 JSON
# ══════════════════════════════════════════════════════════════

def llm_think_prompt_json(task: str, observation: str, history: list[dict]) -> dict:
    """
    通过 Prompt 要求 LLM 输出 JSON 格式的决策。

    【注意力漂移：不是 Bug，是机制决定的概率性缺陷】

    原理（概念类比，非精确测量）：
      上下文中的每轮 Thought/Action/Observation 都在稀释 System Prompt 的权重。
      「注意力稀释」是 LLM 的内部机制，作为 Client 我们无法观测具体的权重值。
      以下是一个形象化的类比，帮助你理解稀释的渐变过程：
        Step 1-3: System Prompt 在总输入中占比高 → 大概率遵守 JSON 格式
        Step 4-5: Observation 累积，Prompt 占比下降 → 临界区，有时遵守有时不遵守
        Step 6+:  Prompt 被淹没在历史消息中 → 几乎必定违背 JSON 格式

    为什么漂移点不稳定复现（这比稳定失败更糟糕）：
      1. 采样随机性：即使 temperature=0.3，模型在每个 token 位置做概率采样，
         不同运行选到不同 token 路径，导致漂移发生在不同步数。
      2. 注意力稀释是渐变而非开关：Step 4-5 处于「临界区」——
         System Prompt 权重从主导变为边缘，过渡不是精确的二进制切换。
      3. 任务内容影响：Observation 内容越长，System Prompt 被稀释越快。
         同样 4 步：Observation 短的能撑住，长的提前漂移。

    实际影响：
      - 开发时跑 3 步通过测试 → 以为没问题
      - 生产环境跑 6 步任务 → 第 4 步随机崩溃
      - 无法稳定复现 → 无法调试 → 间歇性故障

    结论：Prompt JSON 仅适合 ≤3 步的原型验证，生产环境必须用原生 FC。
    """
    if llm_available():
        messages = _build_messages(task, observation, history, AGENT_LOOP_JSON_PROMPT)
        result = chat_structured(messages, temperature=0.3)
        if result:
            print("  🌐 [Prompt JSON]")
            return {
                "thought": result.get("thought", ""),
                "action": result.get("action"),
                "action_input": result.get("action_input"),
                "final_answer": result.get("final_answer"),
            }
    # 回退
    print("  💻 [模拟规则回退]")
    return _mock_llm_think(task, observation, history)


# ══════════════════════════════════════════════════════════════
# 模式二：原生 Function Calling
# ══════════════════════════════════════════════════════════════

def llm_think_native_fc(task: str, observation: str, history: list[dict]) -> dict:
    """
    使用 API 原生 tools 参数进行决策，不依赖 Prompt 维持 JSON 格式。

    【为什么不受注意力漂移影响】
    1. 工具 Schema 由 API 的 tools 参数传递 → 模型训练时就支持此机制，
       不是靠 Prompt 里的文字约束。
    2. 模型的 reasoning（思考）输出为自然语言 → 不需要手动维护 JSON
       的大括号配对和引号转义，token 生成稳定性显著更高。
    3. 模型决定调工具时，API 返回 tool_calls 字段 → 结构化程度由
       API 保证，不依赖模型"记住"输出格式。
    4. 模型决定不调工具时，content 为自然语言 → 直接作为 final_answer，
       不需要解析 JSON。
    """
    if llm_available():
        messages = _build_messages(task, observation, history, AGENT_LOOP_FC_PROMPT)
        content, tool_call = chat_with_tools(messages, tools=NATIVE_FC_TOOLS_SCHEMA, temperature=0.3)

        if tool_call:
            # 模型决定调用工具 → tool_calls 由 API 保证结构正确
            print("  🌐 [原生 FC → 工具调用]")
            return {
                "thought": content or f"调用工具 {tool_call['name']}",
                "action": tool_call["name"],
                "action_input": tool_call["arguments"],
                "final_answer": None,
            }
        elif content:
            # 模型以自然语言结束 → 无需 JSON 解析
            print("  🌐 [原生 FC → 任务完成]")
            return {
                "thought": content,
                "action": None,
                "action_input": None,
                "final_answer": content,
            }

    # 回退
    print("  💻 [模拟规则回退]")
    return _mock_llm_think(task, observation, history)


# ── 模拟回退 ─────────────────────────────────────────────────
def _mock_llm_think(task: str, observation: str, history: list[dict]) -> dict:
    step_count = len(history)

    if step_count == 0 and "测试" in task:
        return {"thought": "要运行测试，我需要先找到所有测试文件。", "action": "search_files",
                "action_input": "test", "final_answer": None}
    if step_count == 0 and "模型" in task:
        return {"thought": "需要先找到模型相关的文件。", "action": "search_files",
                "action_input": "model", "final_answer": None}
    if step_count == 1 and observation and "test_main" in observation:
        return {"thought": "找到了测试文件，读取 test_main.py。", "action": "read_file",
                "action_input": "test_main.py", "final_answer": None}
    if step_count == 1 and observation and "model" in observation:
        return {"thought": "找到了模型文件，读取 model.py。", "action": "read_file",
                "action_input": "model.py", "final_answer": None}
    if step_count == 2 and "test" in str(history[-1].get("observation", "")):
        return {"thought": "已经了解测试内容，运行测试。", "action": "run_tests",
                "action_input": "test_*.py", "final_answer": None}
    return {"thought": "所有操作已完成。", "action": None, "action_input": None,
            "final_answer": f"任务 '{task}' 已完成，共 {step_count + 1} 步。"}


# ── Agent Loop ────────────────────────────────────────────────
def agent_loop(task: str, max_steps: int = 10,
               use_native_fc: bool = False) -> str:
    history: list[dict] = []
    observation = ""

    mode_label = "原生 Function Calling" if use_native_fc else "Prompt 强制 JSON"
    think_fn = llm_think_native_fc if use_native_fc else llm_think_prompt_json

    print("=" * 60)
    print(f"🤖 Agent 启动，任务: {task}")
    print(f"   模式: {mode_label}")
    print("=" * 60)

    if not use_native_fc and llm_available():
        print("\n  ⚠️  当前使用「Prompt 强制 JSON」模式。")
        print("  Step 较多时可能出现注意力漂移（JSON 格式丢失）。")
        print("  运行 python agent_loop_demo.py --mode compare 查看对比。\n")

    for step in range(1, max_steps + 1):
        print(f"\n{'─' * 40}")
        print(f"📍 Step {step}")

        llm_response = think_fn(task, observation, history)
        thought = llm_response["thought"]
        action = llm_response["action"]
        action_input = llm_response["action_input"]

        print(f"  💭 Thought: {thought}")

        if action is None:
            print(f"  ✅ Agent 判定任务完成")
            print(f"\n📋 最终结果: {llm_response.get('final_answer', '任务完成')}")
            return llm_response.get("final_answer", "任务完成")

        action_str = action_input if isinstance(action_input, str) else json.dumps(action_input, ensure_ascii=False)
        print(f"  🔧 Action: {action}({action_str})")
        tool_func = TOOLS.get(action)
        if not tool_func:
            observation = f"[错误] 未知工具: {action}"
        elif isinstance(action_input, dict):
            observation = tool_func(**action_input)   # dict → 展开为关键字参数
        else:
            observation = tool_func(action_input)     # str → 直接传参

        print(f"  👁️  Observation: {observation}")

        history.append({
            "step": step, "thought": thought,
            "action": action, "action_input": str(action_input),
            "observation": observation,
        })

    print(f"\n⚠️ 达到最大步数 {max_steps}，Agent 强制终止")
    return "任务未完成"


# ── 运行演示 ─────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agent Loop Demo — 对比 Prompt JSON 与原生 Function Calling",
    )
    parser.add_argument("--mode", choices=["prompt-json", "native-fc", "compare"],
                        default="prompt-json",
                        help="工具调用模式：prompt-json（默认）/ native-fc / compare（对比）")
    parser.add_argument("--task", type=str, default=None,
                        help="自定义任务")
    args = parser.parse_args()

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
    ╚══════════════════════════════════════════════════════╝
    """)

    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，使用真实 LLM 驱动\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用内置模拟规则")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    if args.mode == "compare" and llm_available():
        # ══════════════════════════════════════════════════════
        # 对比模式：同一任务分别用两种方案执行
        # ══════════════════════════════════════════════════════
        task = args.task or "帮我检查代码中的模型实现"

        print("=" * 65)
        print("📊 对比：Prompt 强制 JSON  vs  原生 Function Calling")
        print("=" * 65)
        print("""
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  两种方案的核心区别在「工具调用格式由谁保证」:            │
  │                                                         │
  │  Prompt JSON: 约束在 Prompt 文字里                       │
  │    → 模型每轮需要"记住"输出 JSON                        │
  │    → 上下文越长，指令权重越被稀释                        │
  │    → Step 4-5 常见 JSON 格式漂移                        │
  │                                                         │
  │  原生 FC:     约束在 API 的 tools 参数里                 │
  │    → 模型训练级支持，不依赖 Prompt 记忆                  │
  │    → 自然语言思考 + API 保证 tool_calls 结构             │
  │    → 不受上下文长度影响                                  │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
  """)

        print("\n  ── 📦 方案一: Prompt 强制 JSON ──")
        print("  (预期：前几步正常，Step 4+ 可能出现 JSON 格式漂移)\n")
        agent_loop(task, max_steps=8, use_native_fc=False)

        print("\n\n  ── 🌐 方案二: 原生 Function Calling ──")
        print("  (预期：全程稳定，不受上下文长度影响)\n")
        agent_loop(task, max_steps=8, use_native_fc=True)

        print("\n" + "=" * 65)
        print("📊 对比总结")
        print("=" * 65)
        print("""
  Prompt 强制 JSON:
    优势: 实现简单，不依赖特定 API 参数，任何模型都能用
    劣势: 上下文 > 4 轮后注意力漂移，JSON 格式解析失败率高

  原生 Function Calling:
    优势: 格式由 API 保证，不受上下文长度影响，token 生成更稳定
    劣势: 需要模型/API 支持 tools 参数

  结论: 生产环境的 Agent 应使用原生 Function Calling。
        Prompt JSON 仅适合短上下文原型验证。
  """)

    else:
        use_fc = args.mode == "native-fc"
        task = args.task or "帮我检查代码中的模型实现"
        agent_loop(task, use_native_fc=use_fc)
