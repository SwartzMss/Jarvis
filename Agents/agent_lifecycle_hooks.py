import time
from agents import AgentHooks, HandoffError

class AgentLifecycleHooks(AgentHooks):
    def __init__(self):
        self.logs = []
    
    async def on_start(self, context, agent):
        ts = time.time()
        self.logs.append((agent.name, "start", ts))
        print(f"[{agent.name}] 开始执行，时间戳：{ts}")
    
    async def on_tool_start(self, context, tool, tool_input):
        ts = time.time()
        self.logs.append((tool.name, "tool_start", ts, tool_input))
        print(f"[{tool.name}] 工具调用开始，时间戳：{ts}，入参：{tool_input}")
    
    async def on_tool_end(self, context, tool, tool_output):
        ts = time.time()
        self.logs.append((tool.name, "tool_end", ts, tool_output))
        print(f"[{tool.name}] 工具调用结束，时间戳：{ts}，返回：{tool_output}")
    
    async def on_error(self, context, agent, error):
        ts = time.time()
        self.logs.append((agent.name, "error", ts, str(error)))
        print(f"[{agent.name}] 执行出错，时间戳：{ts}，错误：{error}")
    
    async def on_end(self, context, agent, output):
        ts = time.time()
        self.logs.append((agent.name, "end", ts, output))
        print(f"[{agent.name}] 完成执行，时间戳：{ts}，输出预览：{str(output)[:200]}")
