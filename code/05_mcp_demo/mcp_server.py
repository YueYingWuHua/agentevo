"""
MCP Server 演示（本地）
====================
实现一个简化的 MCP Server，遵循 MCP 协议的 JSON-RPC 通信模式。
提供文件系统操作和数据库查询工具。

通信方式: stdio（标准输入输出）
协议: JSON-RPC 2.0 简化版

运行方式：python mcp_server.py
"""

import json
import sys
import os
from typing import Any

# ── 工具实现 ─────────────────────────────────────────────────

def tool_list_files(path: str = ".") -> str:
    """列出目录中的文件"""
    try:
        files = os.listdir(path)
        return json.dumps({"files": files, "count": len(files), "path": path})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_read_file(filepath: str) -> str:
    """读取文件内容"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return json.dumps({"content": content, "filepath": filepath, "size": len(content)})
    except FileNotFoundError:
        return json.dumps({"error": f"文件不存在: {filepath}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_search_files(pattern: str, path: str = ".") -> str:
    """在文件中搜索指定模式"""
    import fnmatch
    results = []
    try:
        for root, dirs, files in os.walk(path):
            for filename in fnmatch.filter(files, pattern):
                results.append(os.path.join(root, filename))
        return json.dumps({"matches": results, "count": len(results), "pattern": pattern})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_query_db(sql: str) -> str:
    """模拟数据库查询"""
    # 模拟一个简单的"数据库"
    fake_tables = {
        "users": [
            {"id": 1, "name": "Alice", "role": "admin"},
            {"id": 2, "name": "Bob", "role": "developer"},
            {"id": 3, "name": "Charlie", "role": "developer"},
        ],
        "projects": [
            {"id": 1, "name": "Project A", "owner": "Alice"},
            {"id": 2, "name": "Project B", "owner": "Bob"},
        ],
    }

    sql_lower = sql.lower()
    if "select" in sql_lower and "users" in sql_lower:
        return json.dumps({"data": fake_tables["users"], "sql": sql})
    elif "select" in sql_lower and "projects" in sql_lower:
        return json.dumps({"data": fake_tables["projects"], "sql": sql})
    else:
        return json.dumps({"error": f"不支持的查询: {sql}", "available_tables": list(fake_tables.keys())})


# ── MCP Server 核心 ─────────────────────────────────────────

class MCPServer:
    """
    简化版 MCP Server，遵循 MCP 协议的核心设计：

    MCP 协议的核心方法：
    - tools/list:   返回可用工具列表及其 Schema
    - tools/call:   调用指定工具
    - resources/list: 返回可用资源列表
    - resources/read: 读取指定资源
    """

    def __init__(self, name: str = "local-mcp-server", version: str = "1.0.0"):
        self.name = name
        self.version = version

        # 工具注册表
        self.tools: dict[str, dict] = {
            "list_files": {
                "function": tool_list_files,
                "schema": {
                    "name": "list_files",
                    "description": "列出指定目录中的文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "目录路径",
                                "default": ".",
                            }
                        },
                    },
                },
            },
            "read_file": {
                "function": tool_read_file,
                "schema": {
                    "name": "read_file",
                    "description": "读取文件内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "文件路径",
                            }
                        },
                        "required": ["filepath"],
                    },
                },
            },
            "search_files": {
                "function": tool_search_files,
                "schema": {
                    "name": "search_files",
                    "description": "搜索匹配模式的文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "文件匹配模式，如 *.py",
                            },
                            "path": {"type": "string", "description": "搜索根目录", "default": "."},
                        },
                        "required": ["pattern"],
                    },
                },
            },
            "query_db": {
                "function": tool_query_db,
                "schema": {
                    "name": "query_db",
                    "description": "执行数据库查询",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "SQL 查询语句",
                            }
                        },
                        "required": ["sql"],
                    },
                },
            },
        }

    def handle_request(self, request: dict) -> dict:
        """处理 JSON-RPC 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "tools/list":
            result = self._list_tools()
        elif method == "tools/call":
            result = self._call_tool(params.get("name", ""), params.get("arguments", {}))
        elif method == "resources/list":
            result = self._list_resources()
        elif method == "resources/read":
            result = self._read_resource(params.get("uri", ""))
        elif method == "initialize":
            result = self._initialize()
        else:
            result = {"error": f"未知方法: {method}"}

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _initialize(self) -> dict:
        return {
            "serverInfo": {"name": self.name, "version": self.version},
            "capabilities": {"tools": {}, "resources": {}},
        }

    def _list_tools(self) -> dict:
        """返回所有工具的 Schema（MCP 协议的核心能力之一：工具发现）"""
        return {
            "tools": [
                tool["schema"] for tool in self.tools.values()
            ]
        }

    def _call_tool(self, name: str, arguments: dict) -> dict:
        """调用指定工具"""
        tool = self.tools.get(name)
        if not tool:
            return {"error": f"工具不存在: {name}"}

        try:
            result = tool["function"](**arguments)
            return {"content": [{"type": "text", "text": result}]}
        except TypeError as e:
            return {"error": f"参数错误: {e}"}
        except Exception as e:
            return {"error": f"执行错误: {e}"}

    def _list_resources(self) -> dict:
        """列出可用资源"""
        return {
            "resources": [
                {"uri": "file:///project/readme.md", "name": "项目说明"},
                {"uri": "db://users", "name": "用户表"},
            ]
        }

    def _read_resource(self, uri: str) -> dict:
        """读取指定资源"""
        resources = {
            "file:///project/readme.md": "# 项目说明\n这是一个演示项目。",
            "db://users": json.dumps({"table": "users", "rows": 3}),
        }
        content = resources.get(uri, f"资源不存在: {uri}")
        return {"contents": [{"uri": uri, "text": content}]}

    def run_stdio(self):
        """
        通过 stdio 运行 Server（标准 MCP 通信方式）。
        从 stdin 读取 JSON-RPC 请求，处理后写入 stdout。
        """
        print(f"MCP Server '{self.name}' v{self.version} 已启动 (stdio模式)", file=sys.stderr)
        print(f"可用工具: {list(self.tools.keys())}", file=sys.stderr)
        print("等待请求...", file=sys.stderr)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response, ensure_ascii=False), flush=True)
            except json.JSONDecodeError as e:
                error_resp = {"jsonrpc": "2.0", "id": None, "error": f"JSON解析错误: {e}"}
                print(json.dumps(error_resp, ensure_ascii=False), flush=True)


# ── 交互式演示模式 ───────────────────────────────────────────

def demo_interactive():
    """交互式演示 MCP Server，不依赖 stdio"""
    server = MCPServer()

    print("=" * 60)
    print(f"  MCP Server '{server.name}' v{server.version} — 交互式演示")
    print("=" * 60)

    # 1. 展示工具列表
    print("\n📋 工具列表（tools/list）:")
    response = server.handle_request({"method": "tools/list", "params": {}, "id": 1})
    for tool in response["result"]["tools"]:
        print(f"  🔧 {tool['name']}: {tool['description']}")

    # 2. 演示一些工具调用
    demos = [
        ("list_files", {"path": "."}),
        ("search_files", {"pattern": "*.py", "path": "."}),
        ("query_db", {"sql": "SELECT * FROM users"}),
        ("query_db", {"sql": "SELECT * FROM projects WHERE owner = 'Alice'"}),
    ]

    for i, (tool_name, args) in enumerate(demos, 1):
        print(f"\n📌 工具调用 {i}: {tool_name}({args})")
        response = server.handle_request({
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
            "id": i + 1,
        })
        result = response["result"]
        if "error" in result:
            print(f"  ❌ 错误: {result['error']}")
        else:
            content = result["content"][0]["text"]
            print(f"  ✅ 结果: {content[:200]}{'...' if len(content) > 200 else ''}")

    # 3. 演示资源
    print(f"\n📋 资源列表（resources/list）:")
    response = server.handle_request({"method": "resources/list", "params": {}, "id": 99})
    for res in response["result"]["resources"]:
        print(f"  📁 {res['uri']} — {res['name']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MCP Server 演示")
    parser.add_argument("--mode", choices=["demo", "stdio"], default="demo",
                        help="demo=交互式演示, stdio=标准输入输出模式")
    args = parser.parse_args()

    if args.mode == "stdio":
        # stdio 模式：真正的 MCP 通信方式
        server = MCPServer()
        server.run_stdio()
    else:
        # 交互式演示模式
        demo_interactive()

        print("\n" + "=" * 60)
        print("""
  💡 MCP Server 核心设计:
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  1. tools/list → 动态工具发现（Agent无需硬编码工具列表） │
  │  2. tools/call → 统一的工具调用接口                     │
  │  3. JSON-RPC 协议 → 跨语言、跨进程通信                  │
  │  4. 传输层无关 → stdio / HTTP / SSE 自由切换            │
  │                                                        │
  │  实际使用时，通过 stdio 或 HTTP 启动 Server，           │
  │  Agent（Client）通过标准协议连接并调用工具               │
  └────────────────────────────────────────────────────────┘
        """)
