import asyncio
from agents import Agent, ModelSettings, function_tool, AgentHooks
from agents.mcp import MCPServerStdio
from openai import AsyncOpenAI
import os

from model_provider import model_provider, MODEL_NAME, client  

async def create_dispatcher_agent():
    agent = Agent(
        name="AI Assistant",
        instructions="你是一个智能助手",
        model=model_provider.get_model(MODEL_NAME),
        model_settings=ModelSettings(temperature=0.3, top_p=0.9),
    )
    return agent
