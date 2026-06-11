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
