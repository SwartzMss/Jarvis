import time
from collections import deque
from agents import AgentHooks

class AgentLifecycleHooks(AgentHooks):
    """
    全生命周期监控钩子：记录 Agent 启动、工具调用、错误和结束事件。
    - max_events: 最多保留最近多少条日志（默认10条）
    - max_chars: 每条日志内容最大字符数（默认50000），超出部分截断并添加省略号

    使用方式：
    ```python
    from agent_lifecycle_hooks import AgentLifecycleHooks
    hooks = AgentLifecycleHooks(max_events=10, max_chars=50000)

    # 在 Agent 构造时复用同一个 hooks 实例
    my_agent = Agent(
        name="MyAgent",
        instructions="...",
        tools=[...],
        hooks=[hooks],
        model=... ,
        model_settings=...,
    )

    # Runner.run 时，控制台会打印出完整的生命周期日志信息
    result = await Runner.run(my_agent, input=[{"role":"user","content":"..."}])
    ```
    """
    def __init__(self, max_events: int = 10, max_chars: int = 50000):
        # 用 deque 限长队列自动丢弃最早的事件
        self.logs: deque[tuple] = deque(maxlen=max_events)
        self.max_chars = max_chars

    def _truncate(self, text: str) -> str:
        # 如果文本长度超过 max_chars，则截断并添加省略号
        return text if len(text) <= self.max_chars else text[: self.max_chars] + "…"

    async def on_start(self, context, agent):
        ts = time.time()
        self.logs.append((agent.name, "start", ts))
        print(f"[{agent.name}] start @ {ts}")

    async def on_tool_start(self, context, tool, tool_input):
        ts = time.time()
        inp = self._truncate(str(tool_input))
        self.logs.append((tool.name, "tool_start", ts, inp))
        print(f"[{tool.name}] tool_start @ {ts}, input={inp}")

    async def on_tool_end(self, context, tool, tool_output):
        ts = time.time()
        out = self._truncate(str(tool_output))
        self.logs.append((tool.name, "tool_end", ts, out))
        print(f"[{tool.name}] tool_end   @ {ts}, output={out}")

    async def on_error(self, context, agent, error):
        ts = time.time()
        err = self._truncate(str(error))
        self.logs.append((agent.name, "error", ts, err))
        print(f"[{agent.name}] error      @ {ts}, error={err}")

    async def on_end(self, context, agent, output):
        ts = time.time()
        out = self._truncate(str(output))
        self.logs.append((agent.name, "end", ts, out))
        print(f"[{agent.name}] end        @ {ts}, output={out}")
