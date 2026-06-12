"""
统一 LLM 客户端
==============
为所有Demo提供统一的LLM调用接口。

核心设计：
- 当 config.use_real_api=True 时，调用真实 OpenAI 兼容 API
- 否则返回 None，由各 Demo 使用原有的模拟逻辑

使用方式：
    from llm_client import chat, chat_structured
    response = chat(messages)           # 普通对话
    response = chat_structured(messages) # 要求返回JSON

═══ API 格式小知识 ════════════════════════════════════════════

【事实标准：OpenAI Chat Completions 协议】
  目前几乎所有 LLM 厂商的 API 都"兼容 OpenAI 接口"。
  这不是任何官方标准（没有 RFC、ISO、W3C），而是市场形成的
  事实标准（de facto standard）：OpenAI 先定义了这套格式，
  DeepSeek/智谱/阿里百炼/Moonshot/本地 Ollama 都主动兼容。
  开发者只需改 base_url 就能切换厂商。

【请求格式】 POST {base_url}/chat/completions
{
  "model": "deepseek-v4-flash",           // 模型名称，各厂商不同
  "messages": [                       // 对话历史，必填
    {"role": "system", "content": "你是一只猫娘"},   // system: 系统指令
    {"role": "user",   "content": "你好"},       // user: 用户消息
    {"role": "assistant", "content": "你好！"},  // assistant: 模型回复
    {"role": "tool",   "content": "...",         // tool: 工具执行结果
                       "tool_call_id": "xxx"}
  ],
  "temperature": 0.7,                 // 采样温度 0-2，越高越随机
  "max_tokens": 2048,                 // 最大输出 token 数
  "stream": false,                    // 是否流式返回
  "tools": [...],                     // 工具 Schema（Function Calling）
  "tool_choice": "auto"               // 工具选择策略
}

【响应格式】 JSON
{
  "id": "chatcmpl-xxx",               // 本次请求的唯一 ID
  "object": "chat.completion",        // 固定值，标识响应类型
  "created": 1710000000,              // Unix 时间戳
  "model": "deepseek-chat",           // 实际使用的模型名

  "choices": [                        // 候选回复列表（通常取第一个）
    {
      "index": 0,                     // 候选序号
      "message": {                    // 模型回复
        "role": "assistant",          // 固定为 "assistant"
        "content": "回复文本",         // 自然语言回复（可能为 null）
        "tool_calls": [               // 工具调用（模型决定调工具时出现）
          {
            "id": "call_xxx",         // 本次调用的唯一 ID
            "type": "function",       // 固定为 "function"
            "function": {
              "name": "search",       // 工具名
              "arguments": "{\"q\":\"x\"}"  // 参数，JSON 字符串
            }
          }
        ]
      },
      "finish_reason": "stop"         // 结束原因：
    }                                 //   "stop"        — 自然结束
  ],                                  //   "tool_calls"  — 需要调工具
                                      //   "length"      — 达到 max_tokens
  "usage": {                          //   "content_filter" — 内容过滤
    "prompt_tokens": 150,             // 输入消耗的 token 数
    "completion_tokens": 80,          // 输出消耗的 token 数
    "total_tokens": 230               // 总计 token 数
  }
}

【Stream 模式响应】 SSE (Server-Sent Events)
  每行格式: data: {JSON}\n\n
  data: {"choices":[{"delta":{"content":"你"}}]}
  data: {"choices":[{"delta":{"content":"好"}}]}
  data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
  data: [DONE]                        ← 流结束标记
  -----------------------------------------------------------------
  关键区别: 非 stream 返回整个 message，stream 返回增量 delta。
  tool_calls 在 stream 模式下按 index 分片传输，需客户端拼装。

【实际验证方式】
  如需查看原始响应，可在 llm_client.py 的 chat() 函数中临时
  取消注释调试打印: print(resp.text)

════════════════════════════════════════════════════════════════
"""

import json
import sys
import os

# 将父目录加入路径，以便各子目录的 Demo 可以导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config


def chat(
    messages: list[dict],
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
) -> str | None:
    """
    发送对话请求。

    Args:
        messages: OpenAI 格式的消息列表 [{"role": "...", "content": "..."}]
        model: 模型名，默认使用 config 中的配置
        temperature: 温度参数
        max_tokens: 最大输出 token 数

    Returns:
        LLM 的回复文本，如果未配置 API Key 则返回 None
    """
    if not config.use_real_api:
        return None

    import requests

    model = model or config.openai_model
    temperature = temperature if temperature is not None else config.temperature
    max_tokens = max_tokens or config.max_tokens

    try:
        resp = requests.post(
            f"{config.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=config.timeout,
        )
        resp.raise_for_status()
        print("resp => " + resp.text + "\n\n\n\n")
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ⚠️ LLM API 调用失败: {e}")
        print(f"  💡 回退到模拟模式")
        return None


def chat_structured(
    messages: list[dict],
    model: str = None,
    temperature: float = None,
) -> dict | None:
    """
    发送对话请求，并要求 LLM 返回 JSON 结构。

    通过 Prompt 引导 + JSON 解析来实现结构化输出。
    如果 LLM 返回的不是有效 JSON，尝试从文本中提取 JSON 块。

    Returns:
        解析后的 dict，如果未配置 API Key 或解析失败则返回 None
    """
    if not config.use_real_api:
        return None

    # 在 System Prompt 中强调 JSON 输出
    structured_messages = messages.copy()
    json_hint = "\n\n重要：请严格输出有效的 JSON 格式，不要包含 markdown 代码块标记或其他文本。"
    if structured_messages and structured_messages[0]["role"] == "system":
        structured_messages[0]["content"] += json_hint
    else:
        structured_messages.insert(0, {"role": "system", "content": f"你必须输出有效的 JSON。{json_hint}"})

    raw = chat(structured_messages, model=model, temperature=temperature if temperature is not None else 0.3)
    print("raw => " + raw + "\n\n\n\n")
    if raw is None:
        return None
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取 JSON
    import re
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 { 到最后一个 } 之间的内容
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass

    print(f"  ⚠️ 无法解析 LLM 返回的 JSON，回退到模拟模式")
    return None


def is_available() -> bool:
    """检查真实 API 是否可用"""
    return config.use_real_api


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
) -> tuple[str | None, dict | None]:
    """
    使用 API 原生 tools 参数进行对话（即 Function Calling）。

    与 chat_structured() 的关键区别：
      - chat_structured(): 在 Prompt 中要求 LLM 输出 JSON → 依赖注意力维持
      - chat_with_tools(): 将工具 Schema 传给 API 的 tools 参数 → 模型训练级支持

    Args:
        messages: 消息列表
        tools: 工具 Schema 列表，OpenAI 格式 [{"type":"function","function":{...}}]
        model/temperature/max_tokens: 同 chat()

    Returns:
        (content_text, tool_call_or_None)
          - content_text: LLM 的自然语言回复（可能为 None 如果只调了工具）
          - tool_call: {"name": "...", "arguments": {...}} 或 None
    """
    if not config.use_real_api:
        return None, None

    import requests

    model = model or config.openai_model
    temperature = temperature if temperature is not None else config.temperature
    max_tokens = max_tokens or config.max_tokens

    try:
        resp = requests.post(
            f"{config.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools,
                "tool_choice": "auto",
            },
            timeout=config.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        print("resp => " + resp.text + "\n\n\n\n")
        choice = data["choices"][0]
        message = choice.get("message", {})

        content = message.get("content")  # 自然语言文本
        tool_calls = message.get("tool_calls")  # 工具调用（原生 FC）

        if tool_calls:
            tc = tool_calls[0]
            func = tc.get("function", {})
            parsed = {
                "name": func.get("name", ""),
                "arguments": json.loads(func.get("arguments", "{}")),
            }
            return content, parsed

        return content, None

    except Exception as e:
        print(f"  ⚠️ LLM tools 调用失败: {e}")
        return None, None


def chat_stream(
    messages: list[dict],
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
):
    """
    流式调用 LLM API。

    工作方式：
      for token in chat_stream(messages):
          print(token, end="", flush=True)     # 逐 token 打印
      text, tool_calls = yield from ... 的返回值

    实际实现：Generator 逐 token yield，流结束后通过 return 返回完整结果。

    用法：
      gen = chat_stream(messages)
      for token in gen:
          print(token, end="", flush=True)
      full_text, tool_calls = gen.value  # 流结束后的返回值

    Returns (via Generator return):
      (accumulated_text, tool_calls_or_None)
        - accumulated_text: 完整累积文本
        - tool_calls: 如果 LLM 决定调工具，返回解析后的工具调用，否则为 None
                      格式: {"name": "函数名", "arguments": "JSON参数字符串"}
    """
    if not config.use_real_api:
        return _simulate_stream(messages)

    yield from _real_stream(messages, model, temperature, max_tokens)


def _real_stream(messages, model, temperature, max_tokens):
    """真实 API 的流式调用"""
    import requests

    model = model or config.openai_model
    temperature = temperature if temperature is not None else config.temperature
    max_tokens = max_tokens or config.max_tokens

    try:
        resp = requests.post(
            f"{config.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            },
            timeout=config.timeout,
            stream=True,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  ⚠️ LLM 流式调用失败: {e}")
        yield " [流式调用失败]"
        return " [流式调用失败]", None

    accumulated_text = ""
    # tool_calls 拼装状态：按 index 分片合并
    tool_call_chunks: dict[int, dict] = {}

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]  # 去掉 "data: " 前缀
        if data_str == "[DONE]":
            break

        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        delta = chunk.get("choices", [{}])[0].get("delta", {})
        finish_reason = chunk.get("choices", [{}])[0].get("finish_reason")

        # ── 处理纯文本内容 ──
        content = delta.get("content", "")
        if content:
            accumulated_text += content
            yield content

        # ── 处理 tool_calls 分片 ──
        tc_list = delta.get("tool_calls")
        if tc_list:
            for tc in tc_list:
                idx = tc.get("index", 0)
                if idx not in tool_call_chunks:
                    tool_call_chunks[idx] = {"name": "", "arguments": ""}

                if tc.get("function", {}).get("name"):
                    tool_call_chunks[idx]["name"] += tc["function"]["name"]
                if tc.get("function", {}).get("arguments"):
                    tool_call_chunks[idx]["arguments"] += tc["function"]["arguments"]

        # ── 流结束，拼装结果 ──
        if finish_reason:
            if tool_call_chunks and finish_reason in ("tool_calls", "stop"):
                tc = tool_call_chunks[0]
                parsed_tc = {
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                }
                return accumulated_text, parsed_tc

    return accumulated_text, None


def _simulate_stream(messages):
    """
    模拟流式输出（无 API Key 时的回退方案）。
    从最后一条 user 消息生成一段模拟回复，逐字输出。
    """
    import time
    import random

    # 找最后一条 user 消息
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"]
            break

    if "任务:" in last_user or "请决定" in last_user or "请开始" in last_user:
        simulated = "我需要使用工具来完成这个任务。\n<ACTION>search</ACTION>\n<ARGS>{\"query\":\"test\"}</ARGS>"
    else:
        simulated = "这是一个模拟的流式回复，展示了逐字输出的效果。当配置真实的 API Key 后，这里将由 LLM 实时生成。"

    accumulated = ""
    for char in simulated:
        accumulated += char
        yield char
        time.sleep(random.uniform(0.015, 0.04))

    # 检测模拟文本中的 Action 标签
    import re
    action_match = re.search(r'<ACTION>(.*?)</ACTION>', accumulated)
    args_match = re.search(r'<ARGS>(.*?)</ARGS>', accumulated)
    if action_match:
        tool_calls = {
            "name": action_match.group(1).strip(),
            "arguments": args_match.group(1).strip() if args_match else "{}",
        }
        return accumulated, tool_calls
    return accumulated, None
