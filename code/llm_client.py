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
