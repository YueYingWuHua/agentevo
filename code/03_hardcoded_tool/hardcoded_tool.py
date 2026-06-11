"""
硬编码工具调用演示
================
演示在 Function Calling API 出现之前，开发者如何通过正则解析 LLM 输出
来实现"工具调用"。这是最早的 Tool Use 方式。

运行方式：python hardcoded_tool.py

API 模式：
  设置环境变量 OPENAI_API_KEY 后，LLM 输出由真实 API 生成
  未设置时使用内置的规则模拟
"""

import json
import os
import re
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat as llm_chat, is_available as llm_available


# ── 真实工具函数 ─────────────────────────────────────────────
def get_weather(city: str) -> str:
    """获取天气（模拟）"""
    weather_data = {
        "北京": "晴天，25°C，湿度45%",
        "上海": "多云，28°C，湿度60%",
        "深圳": "阵雨，30°C，湿度80%",
    }
    return weather_data.get(city, f"未找到 {city} 的天气数据")


def calculate(expression: str) -> str:
    """安全地计算数学表达式"""
    try:
        # 只允许数字和基本运算符，防止代码注入
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return f"表达式包含不允许的字符: {expression}"
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"


def search_database(query: str) -> str:
    """模拟数据库查询"""
    fake_db = {
        "用户": "找到 156 条用户记录",
        "订单": "找到 23 条订单记录",
        "产品": "找到 89 条产品记录",
    }
    for key, value in fake_db.items():
        if key in query:
            return value
    return f"在数据库中未找到与 '{query}' 相关的结果"


# ── 硬编码工具调用的 Prompt ──────────────────────────────────
TOOL_SYSTEM_PROMPT = """你是一个AI助手，可以使用以下工具：

可用工具：
- get_weather(city: str)  — 查询指定城市的天气
- calculate(expression: str) — 计算数学表达式
- search_database(query: str) — 搜索数据库

当你需要调用工具时，请严格使用以下格式：
<TOOL_CALL>
{"tool": "工具名", "args": {"参数名": "参数值"}}
</TOOL_CALL>

如果不需要工具，请直接回复。"""


# ── 调用 LLM 获取工具调用意图 ──────────────────────────────
def call_llm_for_tool(user_message: str) -> str:
    """
    让 LLM 输出带工具调用标记的文本。
    优先使用真实 API，不可用时回退到规则模拟。
    """
    # ── 尝试真实 API ──
    if llm_available():
        messages = [
            {"role": "system", "content": TOOL_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        result = llm_chat(messages, temperature=0.3)
        if result:
            print("  🌐 [真实LLM决策]")
            return result

    # ── 回退：规则模拟 ──
    print("  💻 [规则模拟]")
    return _simulate_llm(user_message)


def _simulate_llm(user_message: str) -> str:
    """模拟 LLM 的输出，包含工具调用标记（规则驱动，仅作回退）"""
    if "天气" in user_message:
        city = "北京"
        if "上海" in user_message:
            city = "上海"
        elif "深圳" in user_message:
            city = "深圳"
        return f"""好的，让我查询一下天气。

<TOOL_CALL>
{{"tool": "get_weather", "args": {{"city": "{city}"}}}}
</TOOL_CALL>"""

    elif any(c.isdigit() for c in user_message) and any(op in user_message for op in ["+", "-", "*", "/", "算", "计算"]):
        expr_match = re.search(r'[\d\+\-\*\/\(\)\.\s]+', user_message)
        expr = expr_match.group().strip() if expr_match else "1+1"
        return f"""让我计算一下。

<TOOL_CALL>
{{"tool": "calculate", "args": {{"expression": "{expr}"}}}}
</TOOL_CALL>"""

    elif "搜索" in user_message or "查" in user_message or "找" in user_message:
        return f"""我来搜索一下数据库。

<TOOL_CALL>
{{"tool": "search_database", "args": {{"query": "{user_message}"}}}}
</TOOL_CALL>"""

    else:
        return "你好！我可以帮你查询天气、计算数学表达式或搜索数据库。请问需要什么帮助？"


# ── 硬编码解析核心：正则提取工具调用 ─────────────────────────
def parse_tool_call(llm_output: str) -> dict | None:
    """
    用正则表达式从 LLM 输出中提取工具调用。
    这是硬编码工具调用最脆弱的部分！
    """
    pattern = r"<TOOL_CALL>\s*(.*?)\s*</TOOL_CALL>"
    match = re.search(pattern, llm_output, re.DOTALL)

    if not match:
        return None

    try:
        tool_call = json.loads(match.group(1))
        return tool_call
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 解析失败: {e}")
        print(f"  原始内容: {match.group(1)}")
        return None


def execute_tool(tool_name: str, args: dict) -> str:
    """执行工具并返回结果"""
    tools = {
        "get_weather": get_weather,
        "calculate": calculate,
        "search_database": search_database,
    }

    func = tools.get(tool_name)
    if not func:
        return f"❌ 未知工具: {tool_name}"

    try:
        return func(**args)
    except TypeError as e:
        return f"❌ 参数错误: {e}"


# ── 完整的硬编码工具调用流程 ─────────────────────────────────
def hardcoded_tool_agent(user_message: str) -> str:
    """
    完整的工具调用流程：
    1. 将工具描述 + 用户消息发送给 LLM
    2. 解析 LLM 输出中的工具调用标记
    3. 执行工具
    4. 将结果返回给用户（如有需要，可继续下一轮对话）
    """
    print(f"\n  👤 用户: {user_message}")

    # Step 1: 调用 LLM（真实API优先，模拟回退）
    llm_output = call_llm_for_tool(user_message)
    print(f"  🤖 LLM 输出: {llm_output[:100]}...")

    # Step 2: 尝试解析工具调用
    tool_call = parse_tool_call(llm_output)

    if tool_call is None:
        print(f"  💬 纯文本回复（无工具调用）")
        return llm_output

    # Step 3: 执行工具
    tool_name = tool_call["tool"]
    tool_args = tool_call["args"]
    print(f"  🔧 解析到工具调用: {tool_name}({tool_args})")

    tool_result = execute_tool(tool_name, tool_args)
    print(f"  📊 工具结果: {tool_result}")

    return f"{llm_output}\n\n工具执行结果: {tool_result}"


# ── 演示硬编码工具调用的脆弱性 ───────────────────────────────
def demo_fragility():
    """展示硬编码解析的脆弱性：LLM 输出格式稍有偏差就解析失败"""
    print("\n" + "=" * 60)
    print("📌 演示硬编码解析的脆弱性")
    print("=" * 60)

    # 多种可能的 LLM 输出格式（JSON 有多难解析）
    tricky_outputs = [
        # 格式正确
        '我需要查询天气\n<TOOL_CALL>\n{"tool": "get_weather", "args": {"city": "北京"}}\n</TOOL_CALL>',
        # 多了一个逗号（trailing comma）
        '我需要查询天气\n<TOOL_CALL>\n{"tool": "get_weather", "args": {"city": "北京",}}\n</TOOL_CALL>',
        # 用了单引号
        "<TOOL_CALL>\n{'tool': 'get_weather', 'args': {'city': '北京'}}\n</TOOL_CALL>",
        # 标签拼写错误
        '<TOOLCAL>\n{"tool": "get_weather", "args": {"city": "北京"}}\n</TOOLCAL>',
    ]

    for i, output in enumerate(tricky_outputs, 1):
        print(f"\n  测试 {i}: {output[:60]}...")
        result = parse_tool_call(output)
        if result:
            print(f"  ✅ 解析成功: {result}")
        else:
            print(f"  ❌ 解析失败")

    print("\n  💡 这就是 Function Calling API 要解决的核心问题——")
    print("     LLM 输出格式不稳定，正则解析脆弱得不堪一击。")


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，LLM 决策由真实 API 驱动\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，LLM 输出使用规则模拟")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    print("=" * 60)
    print("📌 硬编码工具调用演示")
    print("=" * 60)
    print(f"\n  System Prompt:\n{TOOL_SYSTEM_PROMPT}")

    # 正常流程演示
    hardcoded_tool_agent("北京今天天气怎么样？")
    print()
    hardcoded_tool_agent("帮我算一下 (15 + 8) * 3 - 12")
    print()
    hardcoded_tool_agent("搜索一下用户数据")

    # 脆弱性演示
    demo_fragility()

    print("\n" + "=" * 60)
    print("""
  💡 硬编码工具调用总结:
  ┌────────────────────────────────────────────────────────┐
  │ 优点: 简单直接，不需要特殊 API 支持                   │
  │                                                        │
  │ 缺点:                                                  │
  │   1. 解析脆弱——LLM输出稍有偏差就失败                   │
  │   2. 难以扩展——每加一个工具都要改Prompt和解析逻辑       │
  │   3. 无类型安全——参数全靠字符串传递                     │
  │   4. 浪费Token——工具描述占大量上下文                    │
  │                                                        │
  │ → 因此演化出了 Function Calling                        │
  └────────────────────────────────────────────────────────┘
    """)
