import time
from agents import AgentHooks

class AgentLifecycleHooks(AgentHooks):
    """
    全生命周期监控钩子：
    1) 记录 Agent 启动、工具调用、错误和结束事件并立即打印；
    2) 在 on_start 时裁剪上下文，仅保留最近 N 轮对话。

    参数说明：
    - max_chars: 每条日志内容最大字符数（默认50000），超出部分截断并添加省略号
    - max_turns: 裁剪对话上下文时，最多保留最近多少轮（默认10轮）

    使用方式：
    ```python
    from agent_lifecycle_hooks import AgentLifecycleHooks
    hooks = AgentLifecycleHooks(max_chars=50000, max_turns=10)

    my_agent = Agent(
        name="MyAgent",
        instructions="...",
        tools=[...],
        hooks=[hooks],
        model=... ,
        model_settings=...,
    )

    result = await Runner.run(my_agent, input=[{"role":"user","content":"..."}])
    ```
    """
    def __init__(self, max_chars: int = 50000, max_turns: int = 10):
        self.max_chars = max_chars
        self.max_turns = max_turns

    def _truncate(self, text: str) -> str:
        return text if len(text) <= self.max_chars else text[: self.max_chars] + "…"

    async def on_start(self, context, agent):
        # 裁剪上下文
        msgs = context.messages
        max_msgs = self.max_turns * 2  # 一轮包含用户和助手两条消息
        if len(msgs) > max_msgs:
            keep = msgs[-max_msgs:]
            context.replace_messages(0, len(msgs), keep)
            print(f"[{agent.name}] 上下文超过 {self.max_turns} 轮，已裁剪至最近 {self.max_turns} 轮。")
        # 打印启动日志
        ts = time.time()
        print(f"[{agent.name}] start @ {ts}")

    async def on_tool_start(self, context, tool, tool_input):
        ts = time.time()
        inp = self._truncate(str(tool_input))
        print(f"[{tool.name}] tool_start @ {ts}, input={inp}")

    async def on_tool_end(self, context, tool, tool_output):
        ts = time.time()
        out = self._truncate(str(tool_output))
        print(f"[{tool.name}] tool_end   @ {ts}, output={out}")

    async def on_error(self, context, agent, error):
        ts = time.time()
        err = self._truncate(str(error))
        print(f"[{agent.name}] error      @ {ts}, error={err}")

    async def on_end(self, context, agent, output):
        ts = time.time()
        out = self._truncate(str(output))
        print(f"[{agent.name}] end        @ {ts}, output={out}")
