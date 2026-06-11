# 代码示例说明

本目录包含「从Chat到Multi-Agent」技术分享的所有 Python 代码示例。

## 环境要求

- Python 3.10+
- `pip install -r requirements.txt`

## 运行模式

所有 Demo 支持两种运行模式，**自动切换**：

| 模式 | 触发条件 | 说明 |
|------|---------|------|
| 🌐 **真实 LLM 模式** | 配置了 API Key | 调用真实 API（OpenAI / DeepSeek / 其他兼容接口） |
| 💻 **模拟模式（默认）** | 未配置 API Key | 内置规则模拟，零依赖可直接运行 |

## 快速配置（推荐：api_config.json）

### 方式一：配置文件（最简单）

```bash
# 1. 复制示例文件
cp api_config.json.example api_config.json

# 2. 编辑 api_config.json，填入你的 API Key
# DeepSeek 用户只需改两行：
{
    "api_key": "sk-your-deepseek-key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
}

# 3. 直接运行
python 00_agent_loop/agent_loop_demo.py
```

### 方式二：环境变量

```bash
# Linux / macOS
export OPENAI_API_KEY=sk-your-key-here
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # DeepSeek 等非 OpenAI 必须设置
export OPENAI_MODEL=deepseek-chat

# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-key-here"
$env:OPENAI_BASE_URL="https://api.deepseek.com/v1"
$env:OPENAI_MODEL="deepseek-chat"
```

### 各平台 Base URL 参考

| 平台 | base_url |
|------|----------|
| DeepSeek | `https://api.deepseek.com/v1` |
| OpenAI | `https://api.openai.com/v1` |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| Moonshot | `https://api.moonshot.cn/v1` |
| 本地 Ollama | `http://localhost:11434/v1` |

### 配置优先级

```
环境变量 OPENAI_API_KEY    >   api_config.json   >   默认值（模拟模式）
环境变量 DEEPSEEK_API_KEY  >   api_config.json   >   默认值（模拟模式）
```

## 目录结构

| 文件夹 | 内容 | 运行方式 |
|--------|------|----------|
| `00_agent_loop/` | Agent Loop 核心概念 | `python agent_loop_demo.py` |
| `01_prompt_chat/` | 纯 LLM 对话 | `python simple_chat.py` |
| `02_chain_of_thought/` | CoT 思维链 | `python cot_demo.py` |
| `03_hardcoded_tool/` | 硬编码工具调用 | `python hardcoded_tool.py` |
| `04_react_loop/` | ReAct Agent | `python react_agent.py` |
| `05_mcp_demo/` | MCP 协议（Server+Client） | `python mcp_server.py` / `python mcp_client.py` |
| `06_skill_demo/` | Skill 模式 | `python skill_agent.py` |
| `07_plan_execute/` | Plan-and-Execute | `python plan_execute_agent.py` |
| `08_multi_agent/` | Multi-Agent + Computer Use | `python multi_agent.py` / `python computer_use_demo.py` |

## 共享模块

| 文件 | 说明 |
|------|------|
| `config.py` | 统一配置（环境变量 + api_config.json） |
| `llm_client.py` | LLM 调用接口（`chat` / `chat_structured` / `is_available`） |
| `api_config.json.example` | 配置文件模板，复制为 api_config.json 即可使用 |

## 学习建议

1. 先从 `00_agent_loop` 开始，理解 Agent 的核心循环机制
2. 按编号顺序阅读，每个阶段解决前一个阶段的问题
3. 重点对比：
   - `03_hardcoded_tool` vs `06_skill_demo`（工具管理方式演进）
   - `04_react_loop` vs `07_plan_execute`（执行策略演进）
   - `05_mcp_demo` 的 Server-Client 架构（协议标准化）
4. 配置 API Key 后对比同一 Demo 的真实 LLM 输出和模拟输出差异
