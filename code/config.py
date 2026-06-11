"""
共享配置模块
==========
所有Demo的统一配置入口。

配置读取优先级：
1. 环境变量（最高）
2. code/api_config.json 文件
3. 默认值

使用方式：
    from config import config
    if config.use_real_api:
        # 调用真实LLM
    else:
        # 使用模拟模式

快速配置 DeepSeek：
  1. 复制 api_config.json.example 为 api_config.json
  2. 填入你的 api_key
  3. 运行任意 Demo
"""

import json
import os


# api_config.json 的搜索路径
CONFIG_FILE_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.json"),
]


def _load_file_config() -> dict:
    """从 api_config.json 加载配置"""
    for path in CONFIG_FILE_PATHS:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
    return {}


class Config:
    """统一配置"""

    def __init__(self):
        # 加载文件配置（优先级低于环境变量）
        file_cfg = _load_file_config()

        # ── API 配置 ──
        # api_key: 环境变量 > api_config.json
        self.api_key = (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or file_cfg.get("api_key", "")
        )
        # 兼容旧变量名
        self.openai_api_key = self.api_key

        # base_url: 环境变量 > api_config.json > 默认
        self.base_url = (
            os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or file_cfg.get("base_url", "https://api.openai.com/v1")
        )
        self.openai_base_url = self.base_url

        # model: 环境变量 > api_config.json > 默认
        self.model = (
            os.environ.get("OPENAI_MODEL")
            or os.environ.get("DEEPSEEK_MODEL")
            or file_cfg.get("model", "gpt-3.5-turbo")
        )
        self.openai_model = self.model

        # 是否使用真实 API
        self.use_real_api = bool(self.api_key)

        # ── 通用参数 ──
        self.temperature = float(
            os.environ.get("LLM_TEMPERATURE")
            or file_cfg.get("temperature", 0.7)
        )
        self.max_tokens = int(
            os.environ.get("LLM_MAX_TOKENS")
            or file_cfg.get("max_tokens", 2048)
        )
        self.timeout = int(
            os.environ.get("LLM_TIMEOUT")
            or file_cfg.get("timeout", 60)
        )

    @property
    def source(self) -> str:
        """返回当前配置来源"""
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"):
            return "环境变量"
        if _load_file_config().get("api_key"):
            return "api_config.json"
        return "无（模拟模式）"


# 全局单例
config = Config()
