"""
Plan-and-Execute Agent 实现
==========================
展示 Planner + Executor 两阶段架构：

1. Planner（规划器）：将复杂任务分解为有序的子任务列表
2. Executor（执行器）：使用 ReAct Loop 逐步执行每个子任务
3. 动态重规划：Executor 的结果可能触发 Planner 调整计划

运行方式：python plan_execute_agent.py

API 模式：
  设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM 驱动规划
  未设置时使用内置的模拟逻辑
"""

import json
import os
import sys
from typing import Any

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import chat_structured, is_available as llm_available


# ── 工具集 ───────────────────────────────────────────────────

def search(query: str) -> str:
    """搜索工具（模拟）"""
    knowledge = {
        "python": "Python 3.13 是该语言的最新主要版本。",
        "fastapi": "FastAPI 是一个现代Python Web框架，支持异步处理。",
        "docker": "Docker 用于容器化应用，Dockerfile 定义构建步骤。",
    }
    for key, value in knowledge.items():
        if key.lower() in query.lower():
            return value
    return f"关于 '{query}' 的搜索结果：需要更多上下文才能给出准确回答。"


def read_file(path: str) -> str:
    """读取文件"""
    files = {
        "/app/main.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'hello': 'world'}\n\n@app.get('/items/{id}')\ndef get_item(id: int):\n    return {'id': id}",
        "/app/requirements.txt": "fastapi==0.100.0\nuvicorn==0.23.0\nsqlalchemy==2.0.0",
        "/app/Dockerfile": "FROM python:3.11\nCOPY . /app\nRUN pip install -r requirements.txt\nCMD uvicorn main:app --host 0.0.0.0",
        "/app/test_main.py": "def test_root():\n    assert True\ndef test_items():\n    assert True  # TODO: add real tests",
    }
    return files.get(path, f"文件不存在: {path}")


def write_file(path: str, content: str) -> str:
    """写入文件（模拟）"""
    return f"文件 {path} 已写入，大小 {len(content)} 字节"


def run_command(cmd: str) -> str:
    """运行命令（模拟）"""
    commands = {
        "docker build .": "Successfully built image: myapp:latest",
        "pytest": "test_main.py::test_root PASSED\ntest_main.py::test_items PASSED\n2 passed in 0.15s",
        "pip install -r requirements.txt": "Successfully installed fastapi uvicorn sqlalchemy",
    }
    return commands.get(cmd, f"命令执行结果: {cmd} → OK")


# ── Planner ──────────────────────────────────────────────────

class Planner:
    """
    Planner：将用户任务分解为有序的子任务列表。

    不需要执行任何操作，只需要规划和分解。
    """

    def create_plan(self, task: str, context: dict = None) -> dict:
        """
        根据任务生成执行计划。
        优先调用真实 LLM API 进行任务分解，不可用时回退到规则模拟。
        """
        # ── 尝试真实 API ──
        if llm_available():
            result = self._llm_create_plan(task)
            if result:
                print("  🌐 [真实LLM规划]")
                return result

        # ── 回退：规则模拟 ──
        print("  💻 [规则模拟规划]")
        return self._mock_create_plan(task)

    def _llm_create_plan(self, task: str) -> dict | None:
        """使用真实 LLM 进行任务规划"""
        prompt = f"""将以下任务分解为有序的子任务列表。每个子任务需要包含：
- id: 序号
- title: 简短标题
- description: 详细描述
- tools_needed: 需要的工具列表
- expected_output: 预期输出

可用工具: search, read_file, write_file, run_command

任务: {task}

请输出 JSON 格式: {{"task": "...", "subtasks": [...]}}"""

        result = chat_structured([
            {"role": "user", "content": prompt}
        ], temperature=0.3)
        if result and "subtasks" in result:
            return result
        return None

    def _mock_create_plan(self, task: str) -> dict:
        """规则模拟的任务规划（仅作回退）"""
        if "部署" in task or "deploy" in task.lower():
            plan = {
                "task": task,
                "subtasks": [
                    {
                        "id": 1,
                        "title": "读取项目文件",
                        "description": "读取 main.py, requirements.txt, Dockerfile 了解项目结构",
                        "tools_needed": ["read_file"],
                        "expected_output": "项目结构信息",
                    },
                    {
                        "id": 2,
                        "title": "检查依赖",
                        "description": "确认 requirements.txt 中的依赖是否完整",
                        "tools_needed": ["read_file", "search"],
                        "expected_output": "依赖清单",
                    },
                    {
                        "id": 3,
                        "title": "构建Docker镜像",
                        "description": "使用 Dockerfile 构建镜像",
                        "tools_needed": ["run_command"],
                        "expected_output": "构建成功或失败信息",
                    },
                    {
                        "id": 4,
                        "title": "运行测试",
                        "description": "执行测试确保构建质量",
                        "tools_needed": ["run_command"],
                        "expected_output": "测试结果",
                    },
                ],
            }
        elif "搜索" in task and "测试" in task:
            plan = {
                "task": task,
                "subtasks": [
                    {
                        "id": 1,
                        "title": "搜索相关技术信息",
                        "description": "搜索任务涉及的技术点",
                        "tools_needed": ["search"],
                        "expected_output": "技术信息",
                    },
                    {
                        "id": 2,
                        "title": "读取现有测试文件",
                        "description": "了解现有测试覆盖情况",
                        "tools_needed": ["read_file"],
                        "expected_output": "测试文件内容",
                    },
                    {
                        "id": 3,
                        "title": "运行测试",
                        "description": "执行测试并分析结果",
                        "tools_needed": ["run_command"],
                        "expected_output": "测试执行结果",
                    },
                ],
            }
        else:
            plan = {
                "task": task,
                "subtasks": [
                    {
                        "id": 1,
                        "title": "分析任务需求",
                        "description": f"理解用户需求: {task}",
                        "tools_needed": ["search"],
                        "expected_output": "任务分析结果",
                    },
                    {
                        "id": 2,
                        "title": "执行操作",
                        "description": "根据分析结果执行相应操作",
                        "tools_needed": ["read_file", "run_command"],
                        "expected_output": "操作结果",
                    },
                    {
                        "id": 3,
                        "title": "总结结果",
                        "description": "汇总步骤1和步骤2的结果，给出最终答案",
                        "tools_needed": [],
                        "expected_output": "最终答案",
                    },
                ],
            }
        return plan

    def revise_plan(self, original_plan: dict, step_result: dict, step_id: int) -> dict:
        """
        动态重规划：当某步骤的执行结果不理想时，调整后续计划。

        这是 Plan-and-Execute 相对于纯 ReAct 的关键优势：
        - 纯 ReAct 发现问题时会"硬着头皮继续"
        - Plan-and-Execute 可以调整整个后续计划
        """
        subtasks = original_plan.get("subtasks", [])

        # 如果某步骤失败，插入一个修复步骤
        if step_result.get("status") == "failed":
            original_plan["revised"] = True
            fix_step = {
                "id": step_id + 0.5,
                "title": f"修复步骤{step_id}的问题",
                "description": f"上一步失败: {step_result.get('error', '未知错误')}，尝试修复",
                "tools_needed": ["search", "read_file"],
                "expected_output": "修复方案",
            }
            subtasks.insert(step_id, fix_step)

        return original_plan


# ── Executor（基于 ReAct Loop） ──────────────────────────────

class Executor:
    """
    Executor：使用 ReAct Loop 逐步执行 Planner 的子任务。

    每个子任务的执行本身是一个小型的 ReAct 循环：
    Thought → Action → Observation → ... → 子任务完成
    """

    def __init__(self):
        self.tools = {
            "search": search,
            "read_file": read_file,
            "write_file": write_file,
            "run_command": run_command,
        }

    def execute_subtask(self, subtask: dict, max_steps: int = 5) -> dict:
        """执行单个子任务（使用微型 ReAct Loop）"""
        print(f"\n  {'─' * 30}")
        print(f"  📋 执行子任务 {subtask['id']}: {subtask['title']}")

        steps_taken = []
        observation = ""

        for step in range(1, max_steps + 1):
            # ── Thought ──
            thought = self._decide_action_api_first(subtask, observation, step)
            print(f"    💭 Step {step}: {thought['reasoning']}")

            # ── 检查是否完成 ──
            if thought.get("complete"):
                break

            # ── Action ──
            action_name = thought["action"]
            action_input = thought["action_input"]
            print(f"    🔧 {action_name}({action_input})")

            # ── Observe ──
            tool = self.tools.get(action_name)
            if tool:
                observation = tool(action_input)
            else:
                observation = f"未知工具: {action_name}"

            print(f"    👁️  {observation[:100]}")
            steps_taken.append({
                "step": step,
                "thought": thought["reasoning"],
                "action": action_name,
                "action_input": str(action_input),
                "observation": observation,
            })

        return {
            "subtask_id": subtask["id"],
            "title": subtask["title"],
            "status": "completed" if len(steps_taken) > 0 else "no_action",
            "steps": steps_taken,
            "result": observation or "子任务完成",
        }

    def _decide_action_api_first(self, subtask: dict, last_obs: str, step: int) -> dict:
        """API优先的执行决策"""
        if llm_available():
            result = self._llm_decide_action(subtask, last_obs, step)
            if result:
                return result
        return self._mock_decide_action(subtask, last_obs, step)

    def _llm_decide_action(self, subtask: dict, last_obs: str, step: int) -> dict | None:
        """使用真实 LLM 决定下一步行动"""
        prompt = f"""你是执行器。根据当前子任务决定下一步行动。

子任务: {subtask.get('title', '')} — {subtask.get('description', '')}
可用工具: {subtask.get('tools_needed', [])}
当前步骤: {step}
上次观察: {last_obs or '无'}

输出 JSON: {{"reasoning": "...", "action": "工具名", "action_input": "参数", "complete": false}}"""

        result = chat_structured([{"role": "user", "content": prompt}], temperature=0.3)
        if result:
            return result
        return None

    def _mock_decide_action(self, subtask: dict, last_obs: str, step: int) -> dict:
        """根据子任务决定下一步行动（规则驱动，仅作回退）"""
        title = subtask.get("title", "")
        tools = subtask.get("tools_needed", [])

        if "读取" in title or "read" in title.lower():
            if step == 1:
                return {
                    "reasoning": "需要先了解项目结构，读取主要文件",
                    "action": "read_file",
                    "action_input": "/app/main.py",
                }
            elif step == 2:
                return {
                    "reasoning": "还需要检查依赖文件和部署配置",
                    "action": "read_file",
                    "action_input": "/app/requirements.txt",
                }
            else:
                return {
                    "reasoning": "还需要检查 Dockerfile",
                    "action": "read_file",
                    "action_input": "/app/Dockerfile",
                }

        elif "构建" in title or "build" in title.lower():
            return {
                "reasoning": "使用 Docker 构建镜像",
                "action": "run_command",
                "action_input": "docker build .",
            }

        elif "测试" in title or "test" in title.lower():
            if step == 1 and "read_file" in tools:
                return {
                    "reasoning": "先看看测试文件有什么测试",
                    "action": "read_file",
                    "action_input": "/app/test_main.py",
                }
            elif step <= 2:
                return {
                    "reasoning": "运行测试",
                    "action": "run_command",
                    "action_input": "pytest",
                }
            else:
                return {"reasoning": "测试执行完成", "complete": True}

        elif "搜索" in title or "search" in title.lower():
            return {
                "reasoning": "搜索任务相关的技术信息",
                "action": "search",
                "action_input": "python fastapi docker",
            }

        # 默认完成
        return {"reasoning": "任务步骤已执行", "complete": True}


# ── Plan-and-Execute Agent ───────────────────────────────────

class PlanAndExecuteAgent:
    """
    Plan-and-Execute Agent：
    - Planner 负责"想清楚"
    - Executor 负责"做到位"
    - 两者协作完成复杂任务
    """

    def __init__(self):
        self.planner = Planner()
        self.executor = Executor()

    def run(self, task: str, allow_replan: bool = True) -> str:
        print("=" * 60)
        print(f"🤖 Plan-and-Execute Agent 启动")
        print(f"📋 任务: {task}")
        print("=" * 60)

        # ── Phase 1: Plan ──
        print(f"\n📐 Phase 1: Planning（规划）")
        plan = self.planner.create_plan(task)
        print(f"  任务分解为 {len(plan['subtasks'])} 个子任务:")
        for st in plan["subtasks"]:
            print(f"    {st['id']}. {st['title']} → 需要工具: {st['tools_needed']}")

        # ── Phase 2: Execute ──
        print(f"\n⚙️  Phase 2: Execution（执行）")
        all_results = []

        for subtask in plan["subtasks"]:
            result = self.executor.execute_subtask(subtask)

            # ── 检查是否需要重规划 ──
            if result["status"] == "failed" and allow_replan:
                print(f"\n  🔄 子任务 {subtask['id']} 失败，触发重规划...")
                plan = self.planner.revise_plan(plan, result, subtask["id"])
                if plan.get("revised"):
                    print(f"  📐 计划已更新：插入修复步骤")

            all_results.append(result)

        # ── Phase 3: Summary ──
        print(f"\n{'=' * 60}")
        print(f"📊 执行总结")
        print(f"{'=' * 60}")
        total_steps = sum(len(r["steps"]) for r in all_results)
        print(f"  总子任务: {len(all_results)}")
        print(f"  总执行步数: {total_steps}")
        for r in all_results:
            status_icon = "✅" if r["status"] == "completed" else "❌"
            print(f"  {status_icon} 子任务 {r['subtask_id']}: {r['title']} — {r['status']}")

        return f"任务 '{task}' 完成，共 {len(all_results)} 个子任务，{total_steps} 步操作"


# ── 对比：纯 ReAct 执行相同任务 ─────────────────────────────

def demo_react_vs_plan_execute():
    """展示 Plan-and-Execute 相比纯 ReAct 的优势"""
    print("\n" + "=" * 60)
    print("📌 Plan-and-Execute vs 纯 ReAct 对比")
    print("=" * 60)

    print("""
  场景：部署一个 FastAPI 应用到 Docker

  ❌ 纯 ReAct:
    Step 1: "我需要先看看有什么文件" → list_files
    Step 2: "有 main.py 和 Dockerfile" → read_file main.py
    Step 3: "这是个 FastAPI 应用" → read_file requirements.txt
    Step 4: "需要 fastapi 和 uvicorn" → read_file Dockerfile
    Step 5: "有 Dockerfile，直接构建" → docker build
    Step 6: "构建成功，接下来..." → ???

    问题：ReAct 可能在第6步不知道要做什么（没有看到全貌）

  ✅ Plan-and-Execute:
    Plan: 1.读取文件 → 2.检查依赖 → 3.构建Docker → 4.运行测试
    (在开始执行前就已经规划好了全部4个步骤)

    优势：每步都知道自己在整体计划中的位置，不会迷失方向
    """)


# ── 主入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║     Plan-and-Execute Agent 演示                      ║
    ║                                                      ║
    ║  架构: Planner（规划器） + Executor（执行器）        ║
    ║                                                      ║
    ║  流程:                                               ║
    ║  用户任务 → Planner 分解 → Executor 逐步执行         ║
    ║     ↑                                    │           ║
    ║     └────── 动态重规划（可选）←───────────┘           ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if llm_available():
        print("🌐 检测到 OPENAI_API_KEY，Planner 和 Executor 由真实 LLM 驱动\n")
    else:
        print("💻 未设置 OPENAI_API_KEY，使用内置规则模拟")
        print("   设置方式: export OPENAI_API_KEY=sk-xxx\n")

    # 演示1：部署任务
    agent = PlanAndExecuteAgent()
    agent.run("部署 FastAPI 应用到 Docker")

    # 演示2：对比
    demo_react_vs_plan_execute()

    # 演示3：第二个任务
    print("\n\n")
    agent2 = PlanAndExecuteAgent()
    agent2.run("搜索最新Python版本信息并运行项目测试")

    print("\n" + "=" * 60)
    print("""
  💡 Plan-and-Execute 总结:
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  1. 全局规划: 执行前先分解任务，避免"走一步看一步"     │
  │                                                        │
  │  2. 可审查: 计划可被人类审查和调整                     │
  │                                                        │
  │  3. 可重规划: 某步失败可重新规划后续步骤               │
  │                                                        │
  │  4. 与 ReAct 互补: Planner 做规划，Executor 用        │
  │     ReAct Loop 执行每个子步骤                           │
  │                                                        │
  │  现代 Agent = Plan-and-Execute + ReAct + Tool Use      │
  └────────────────────────────────────────────────────────┘
    """)
