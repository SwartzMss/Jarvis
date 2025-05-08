import time
from datetime import datetime
from agents import AgentHooks, RunContextWrapper, Agent,Tool
from typing import Any, TypeVar, Generic

TContext = TypeVar('TContext')

class AgentLifecycleHooks(Generic[TContext]):
    def __init__(self, max_chars: int = 50000, max_turns: int = 10):
        self.max_chars = max_chars
        self.max_turns = max_turns

    def _get_time_str(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    async def on_start(self, context: RunContextWrapper, agent: Agent) -> None:
        # 打印启动日志
        print(f"[{agent.name}] 开始运行 @ {self._get_time_str()}")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> bool:
        """工具开始执行时的钩子"""
        # 打印工具名
        print(f"[{agent.name}] 开始执行 {tool.name} @ {self._get_time_str()}")
        return True

    async def on_tool_end(
        self, context: RunContextWrapper, agent: Agent, tool: Tool, tool_output: str
    ) -> bool:
        """工具执行结束时的钩子"""
        print(f"[{agent.name}] 执行 {tool.name} 结束 @ {self._get_time_str()}, 输出: {tool_output}")
        return True

    async def on_handoff(
        self,
        context: RunContextWrapper[TContext],
        agent: Agent[TContext],
        source: Agent[TContext],
    ) -> None:
        """处理消息转交时的钩子
        
        参数：
            context: 运行上下文
            agent: 目标 Agent
            source: 源 Agent
        """
        print(f"[{source.name}] 将任务交给 {agent.name} @ {self._get_time_str()}")
        
        # 从上下文中获取会话实例并切换 agent
        try:
            if session := context.context:             
                await session.handoff_to(agent)     
        except Exception as e:
            print(f"切换 agent 时出错: {str(e)}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        print(f"[{agent.name}] 运行结束 @ {self._get_time_str()}, 输出: {output}")

# 默认实例
default_hooks = AgentLifecycleHooks()

"""
使用方式：
```python
from agent_lifecycle_hooks import default_hooks

my_agent = Agent(
    name="MyAgent",
    instructions="...",
    tools=[...],
    hooks=[default_hooks],  # 直接使用默认实例
    model=...,
    model_settings=...,
)

result = await Runner.run(my_agent, input=[{"role":"user","content":"..."}])
```

如果需要自定义参数，也可以创建新的实例：
```python
from agent_lifecycle_hooks import AgentLifecycleHooks

custom_hooks = AgentLifecycleHooks(max_chars=100000, max_turns=20)
```
"""
