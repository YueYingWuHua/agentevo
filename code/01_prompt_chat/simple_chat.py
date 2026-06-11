"""
纯 LLM 对话演示（ChatBox 时代）
=======================
演示最基础的 LLM 对话模式：单轮对话 + 多轮对话（Context 传递）

运行方式：
  python simple_chat.py

API 模式：
  设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM 驱动模式
  未设置时使用内置的模拟对话逻辑
"""

import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat as llm_chat, is_available as llm_available


# ── 模拟对话（无 API Key 时使用） ───────────────────────────
def simulate_chat(messages: list[dict]) -> str:
    """模拟 LLM 回复，用于演示对话流程"""
    last_user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break

    history_count = len([m for m in messages if m["role"] == "assistant"])

    if "快速排序" in last_user_msg and "类型注解" in last_user_msg and history_count > 0:
        return """好的，给快速排序加上类型注解：

```python
from typing import List, TypeVar

T = TypeVar('T')

def quicksort(arr: List[T]) -> List[T]:
    if len(arr) <= 1:
        return arr
    pivot: T = arr[len(arr) // 2]
    left: List[T] = [x for x in arr if x < pivot]
    middle: List[T] = [x for x in arr if x == pivot]
    right: List[T] = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
```"""
    elif "快速排序" in last_user_msg:
        return """好的，这是一个快速排序的Python实现：

```python
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
```"""
    else:
        return f"[模拟回复] 收到你的问题：「{last_user_msg[:50]}...」，这是模拟的回复内容。"


def chat(messages: list[dict]) -> str:
    """统一的对话接口：真实API优先，不可用时回退模拟"""
    result = llm_chat(messages)
    if result is not None:
        print("  🌐 [真实LLM]")
        return result
    print("  💻 [模拟回复]")
    return simulate_chat(messages)


# ── 演示1：单轮对话 ─────────────────────────────────────────
def demo_single_turn():
    """单轮对话：一问一答，没有上下文记忆"""
    print("\n" + "=" * 60)
    print("📌 演示1：单轮对话（一问一答，无状态）")
    print("=" * 60)

    messages = [
        {"role": "user", "content": "用Python写一个快速排序算法"}
    ]
    print(f"\n  👤 User: {messages[0]['content']}")
    response = chat(messages)
    print(f"\n  🤖 Assistant:\n{response}")


# ── 演示2：多轮对话 ─────────────────────────────────────────
def demo_multi_turn():
    """多轮对话：将历史对话作为 Context 传入，LLM 能"记住"上文"""
    print("\n" + "=" * 60)
    print("📌 演示2：多轮对话（带上下文记忆）")
    print("=" * 60)

    messages = [
        {"role": "user", "content": "用Python写一个快速排序算法"}
    ]
    print(f"\n  👤 User: {messages[0]['content']}")
    response = chat(messages)
    print(f"\n  🤖 Assistant:\n{response}")

    # 第二轮：将历史对话和新的用户消息一起传入
    messages.append({"role": "assistant", "content": response})
    messages.append({"role": "user", "content": "能加上类型注解吗？"})

    print(f"\n  👤 User: {messages[-1]['content']}")
    print("  (此时 messages 包含第1轮的完整对话历史)")
    response = chat(messages)
    print(f"\n  🤖 Assistant:\n{response}")

    print("\n  💡 关键：第2轮回复中包含了类型注解，说明 LLM '记住'了第1轮的代码内容")
    print("  这是因为第1轮的完整对话作为 Context 传入了第2轮的请求中。")


# ── 演示3：纯 Chat 的局限 ───────────────────────────────────
def demo_limitation():
    """展示纯 Chat 模式无法做到的事情"""
    print("\n" + "=" * 60)
    print("📌 演示3：纯 Chat 的局限性")
    print("=" * 60)

    limitations = [
        "读取文件内容 → LLM 无法访问文件系统",
        "查询数据库 → LLM 无法连接数据库",
        "发送邮件 → LLM 无法调用邮件服务",
        "运行代码并获取输出 → LLM 无法执行代码",
        "获取实时数据（如天气、股价）→ LLM 的知识有截止日期",
    ]
    for item in limitations:
        print(f"  ❌ {item}")

    print("\n  💡 这正是 Tool Use / Agent 需要解决的问题。")


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，使用真实 LLM 调用\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用模拟模式演示对话流程")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    demo_single_turn()
    demo_multi_turn()
    demo_limitation()
