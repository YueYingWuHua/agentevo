"""
Chain of Thought（思维链）演示
=======================
演示 Zero-shot CoT 和 Few-shot CoT 的实现原理。
展示如何通过 Prompt 引导 LLM "一步步思考"，从而提高复杂推理任务的准确率。

运行方式：python cot_demo.py
"""

import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat as llm_chat, is_available as llm_available


# ── 模拟 CoT 回复 ───────────────────────────────────────────
def simulate_cot(messages: list[dict]) -> str:
    """模拟 CoT 模式下的回复，展示思维链的不同效果"""
    last_msg = messages[-1]["content"]

    if "Let's think step by step" in last_msg or "一步步" in last_msg or "步骤" in last_msg:
        # Zero-shot CoT 风格的回复
        return """让我一步步分析：

**第1步**：初始3人，每人2个苹果 → 3 × 2 = 6个苹果
**第2步**：后来2人，每人3个苹果 → 2 × 3 = 6个苹果
**第3步**：总数 = 6 + 6 = 12个苹果

答案是 **12个苹果**。"""

    elif "请直接回答" in last_msg or "不要推理" in last_msg:
        # 直接回答（可能出错）
        return "12个"

    else:
        # 标准 CoT Few-shot 风格的回复
        return """我来分析一下：

已知信息：
- 房间初始有3个人
- 每人有2个苹果
- 后来又进来2个人
- 这2人每人有3个苹果

计算过程：
- 初始苹果数：3人 × 2个/人 = 6个
- 新增苹果数：2人 × 3个/人 = 6个
- 总苹果数：6个 + 6个 = 12个

答案是12个苹果。"""


def chat(messages: list[dict]) -> str:
    """统一的对话接口：真实API优先，不可用时回退模拟"""
    result = llm_chat(messages)
    if result is not None:
        print("  🌐 [真实LLM]")
        return result
    print("  💻 [模拟CoT]")
    return simulate_cot(messages)


# ── 演示1：无 CoT（直接回答） ───────────────────────────────
def demo_no_cot():
    """直接让 LLM 回答，不引导推理过程"""
    print("\n" + "=" * 60)
    print("📌 演示1：无 CoT——直接回答")
    print("=" * 60)

    question = "一个房间里有3个人，每人有2个苹果，后来进来了2个人，每人带了3个苹果，现在房间里一共有多少个苹果？"

    messages = [{"role": "user", "content": f"请直接回答，不要推理过程：{question}"}]
    print(f"\n  👤 Prompt: {messages[0]['content']}")
    response = chat(messages)
    print(f"\n  🤖 Response:\n{response}")
    print("\n  ⚠️ 直接回答可能正确，但在更复杂的问题上容易出错，且缺乏验证手段。")


# ── 演示2：Zero-shot CoT ────────────────────────────────────
def demo_zero_shot_cot():
    """Zero-shot CoT：在 Prompt 末尾加上 "Let's think step by step" """
    print("\n" + "=" * 60)
    print("📌 演示2：Zero-shot CoT")
    print("=" * 60)

    question = "一个房间里有3个人，每人有2个苹果，后来进来了2个人，每人带了3个苹果，现在房间里一共有多少个苹果？"

    # 关键：在结尾加上引导语
    cot_prompt = f"{question}\n\nLet's think step by step.（请一步步思考）"
    messages = [{"role": "user", "content": cot_prompt}]

    print(f"\n  👤 Prompt: {question}")
    print(f"  🔑 加上 Magic Words: \"Let's think step by step.\"")
    response = chat(messages)
    print(f"\n  🤖 Response:\n{response}")
    print("\n  ✅ 通过引导 LLM 展示推理步骤，显著提高准确率，且推理过程可审查。")


# ── 演示3：Few-shot CoT ─────────────────────────────────────
def demo_few_shot_cot():
    """Few-shot CoT：在 Prompt 中给出带推理过程的示例"""
    print("\n" + "=" * 60)
    print("📌 演示3：Few-shot CoT")
    print("=" * 60)

    question = "一个房间里有3个人，每人有2个苹果，后来进来了2个人，每人带了3个苹果，现在房间里一共有多少个苹果？"

    # Few-shot 示例包含完整的推理过程
    few_shot_prompt = f"""请按以下示例的格式回答问题。

示例问题：小明有5个苹果，吃了2个，妈妈又给了3个，现在有几个苹果？
示例推理：
  第1步：初始苹果数 = 5个
  第2步：吃掉2个，剩余 = 5 - 2 = 3个
  第3步：妈妈给了3个，现在 = 3 + 3 = 6个
示例答案：6个苹果

现在请回答：{question}"""

    messages = [{"role": "user", "content": few_shot_prompt}]
    print(f"\n  👤 Prompt:\n{few_shot_prompt}")
    print(f"\n  💡 Few-shot 的关键：通过示例教会 LLM 推理格式")
    response = chat(messages)
    print(f"\n  🤖 Response:\n{response}")


# ── 演示4：复杂任务中的 CoT 价值 ────────────────────────────
def demo_cot_value():
    """展示 CoT 在多步推理中的价值"""
    print("\n" + "=" * 60)
    print("📌 演示4：CoT 在代码生成中的价值")
    print("=" * 60)

    task = "写一个函数，接受一个字符串列表，返回其中最长的那个字符串。如果有多个相同长度的，返回第一个出现的。"

    # 无 CoT
    no_cot = [{"role": "user", "content": f"写一个Python函数：{task}"}]

    # 带 CoT
    with_cot = [{"role": "user", "content": f"""写一个Python函数：{task}

请按以下步骤思考：
1. 首先分析输入和输出
2. 设计算法步骤
3. 考虑边界情况（空列表、多个相同长度）
4. 写出最终代码""" }]

    print(f"\n  📝 任务: {task}")
    print(f"\n  ❌ 无 CoT Prompt: 直接要求写函数")
    response_no_cot = chat(no_cot)
    print(f"  🤖 回复:\n{response_no_cot[:200]}...")

    print(f"\n  ✅ 有 CoT Prompt: 要求按步骤分析")
    response_cot = chat(with_cot)
    print(f"  🤖 回复:\n{response_cot[:300]}...")


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    if llm_available():
        print("🌐 使用真实 LLM API 演示 CoT\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用模拟模式演示 CoT 原理")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    demo_no_cot()
    demo_zero_shot_cot()
    demo_few_shot_cot()
    demo_cot_value()

    print("\n" + "=" * 60)
    print("""
  💡 CoT 核心总结:
  ┌────────────────────────────────────────────────────────┐
  │ Chain of Thought 是 Agent Think 环节的基础            │
  │                                                        │
  │ - Zero-shot CoT: 加 "Let's think step by step"        │
  │ - Few-shot CoT:  给出带推理过程的示例                  │
  │ - 价值: 提高复杂推理准确率 + 推理过程可审查            │
  │                                                        │
  │ 在 Agent 中，CoT 的输出就是 Thought（思考），          │
  │ 而 ReAct 在 CoT 的 Thinking 基础上增加了 Acting。       │
  └────────────────────────────────────────────────────────┘
    """)
