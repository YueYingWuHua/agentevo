"""
MCP Client 演示
==============
实现一个简化版 MCP Client，通过 stdio 或直接调用方式与 MCP Server 通信。
演示 Agent（Client）如何动态发现和调用 Server 提供的工具。

运行方式：
  1. 先在一个终端启动 Server: python mcp_server.py --mode demo
  2. 直接运行此 Client 演示: python mcp_client.py

或者 Client 通过 subprocess 自动启动 Server（本文件默认模式）。
"""

import json
import subprocess
import sys
from typing import Any


class MCPClient:
    """
    MCP Client — Agent 端使用。

    核心功能：
    1. 连接 MCP Server
    2. 获取可用工具列表（动态发现）
    3. 调用工具
    4. 无需硬编码任何工具信息
    """

    def __init__(self):
        self.tools: list[dict] = []
        self.server_name = ""
        self.server_version = ""

    def connect_direct(self, server) -> None:
        """直接连接到 MCP Server 对象（演示模式）"""
        self._server = server
        self._discover()

    def connect_stdio(self, server_script: str) -> None:
        """通过 stdio 启动并连接 MCP Server 进程"""
        self._process = subprocess.Popen(
            [sys.executable, server_script, "--mode", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._discover_via_stdio()

    def _send_request(self, method: str, params: dict = None) -> dict:
        """发送 JSON-RPC 请求（直接模式）"""
        if hasattr(self, "_server"):
            return self._server.handle_request({
                "method": method,
                "params": params or {},
                "id": 1,
            })
        else:
            return self._send_stdio(method, params or {})

    def _send_stdio(self, method: str, params: dict) -> dict:
        """通过 stdio 发送请求"""
        request = json.dumps({"method": method, "params": params, "id": 1})
        self._process.stdin.write(request + "\n")
        self._process.stdin.flush()
        response_line = self._process.stdout.readline()
        return json.loads(response_line)

    def _discover(self) -> None:
        """动态发现 Server 提供的工具（MCP 的核心优势）"""
        # 初始化
        init_resp = self._send_request("initialize")
        result = init_resp.get("result", {})
        self.server_name = result.get("serverInfo", {}).get("name", "unknown")
        self.server_version = result.get("serverInfo", {}).get("version", "0")

        # 获取工具列表
        tools_resp = self._send_request("tools/list")
        self.tools = tools_resp.get("result", {}).get("tools", [])

    def _discover_via_stdio(self) -> None:
        """通过 stdio 发现工具"""
        init_resp = self._send_stdio("initialize", {})
        result = init_resp.get("result", {})
        self.server_name = result.get("serverInfo", {}).get("name", "unknown")
        self.server_version = result.get("serverInfo", {}).get("version", "0")

        tools_resp = self._send_stdio("tools/list", {})
        self.tools = tools_resp.get("result", {}).get("tools", [])

    def list_tools(self) -> list[dict]:
        """返回可用工具列表"""
        return self.tools

    def call_tool(self, name: str, arguments: dict) -> str:
        """调用指定工具"""
        resp = self._send_request("tools/call", {"name": name, "arguments": arguments})
        result = resp.get("result", {})
        if "error" in result:
            return f"❌ {result['error']}"
        content = result.get("content", [])
        if content:
            return content[0].get("text", str(content))
        return str(result)


# ── 演示：Agent 使用 MCP Client ─────────────────────────────

def simulate_agent_with_mcp(client: MCPClient, task: str):
    """
    模拟一个 Agent 通过 MCP Client 自主完成任务的过程。

    这个流程体现了 MCP 的核心价值：
    1. Agent 不需要硬编码工具 → 通过 tools/list 动态发现
    2. Agent 不需要知道工具实现 → 通过 tools/call 统一调用
    3. 工具扩展不影响 Agent 代码 → Server 端增加工具，Client 自动感知
    """
    print(f"\n{'=' * 60}")
    print(f"🤖 Agent 收到任务: {task}")
    print(f"{'=' * 60}")

    # Step 1: 动态获取可用工具
    tools = client.list_tools()
    print(f"\n📋 动态发现工具（无需在 Agent 代码中硬编码）:")
    for tool in tools:
        print(f"  🔧 {tool['name']}: {tool.get('description', 'N/A')}")

    # Step 2: Agent 根据任务选择合适的工具
    print(f"\n💭 Agent 思考: 需要列出文件、搜索代码、查询数据库...")

    # 列出文件
    print(f"\n  🔧 调用: list_files({'.'})")
    result = client.call_tool("list_files", {"path": "."})
    print(f"  结果: {result[:200]}")

    # 搜索文件
    print(f"\n  🔧 调用: search_files({'*.py'})")
    result = client.call_tool("search_files", {"pattern": "*.py", "path": "."})
    print(f"  结果: {result[:200]}")

    # 查询数据库
    print(f"\n  🔧 调用: query_db({'SELECT * FROM users'})")
    result = client.call_tool("query_db", {"sql": "SELECT * FROM users"})
    print(f"  结果: {result[:200]}")

    print(f"\n✅ Agent 完成任务: 所有工具调用均通过 MCP 协议完成")


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║          MCP Client 演示                             ║
    ║                                                      ║
    ║  演示 Agent 如何通过 MCP 协议:                        ║
    ║  1. 动态发现工具（tools/list）                       ║
    ║  2. 统一调用工具（tools/call）                       ║
    ║  3. 无需在 Agent 代码中硬编码工具信息                 ║
    ╚══════════════════════════════════════════════════════╝
    """)

    # 创建 Server 和 Client（直接模式，不需要 subprocess）
    from mcp_server import MCPServer

    server = MCPServer()
    client = MCPClient()
    client.connect_direct(server)

    print(f"\n✅ 已连接 MCP Server: {client.server_name} v{client.server_version}")

    # 演示1：查看工具列表
    tools = client.list_tools()
    print(f"\n📋 可用工具 ({len(tools)} 个):")
    for tool in tools:
        params_desc = json.dumps(tool.get("parameters", {}).get("properties", {}).keys(), default=str)
        print(f"  🔧 {tool['name']} — {tool.get('description', '')}")

    # 演示2：Agent 使用 MCP Client 完成任务
    simulate_agent_with_mcp(client, "分析当前项目结构，查看数据库中的用户信息")

    # 演示3：对比——如果不用 MCP，Agent 需要怎么做
    print("\n" + "=" * 60)
    print("📌 对比：不用 MCP 时的问题")
    print("=" * 60)
    print("""
  ❌ 传统方式（不用 MCP）:
    1. Agent 代码中硬编码工具列表
    2. 每个工具需要单独定义 Schema
    3. 新增工具 → 修改 Agent 代码
    4. 工具实现和 Agent 紧耦合
    5. 无法复用其他服务的工具

  ✅ 使用 MCP:
    1. Agent 通过 tools/list 自动发现
    2. Schema 由 Server 提供，格式统一
    3. 新增工具 → 只需更新 Server
    4. Agent 和工具松耦合
    5. 任何实现 MCP 的工具服务都可接入
    """)
