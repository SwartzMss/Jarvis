import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import ModelProvider
from agents import Model 
from agents import OpenAIChatCompletionsModel
from agents import set_tracing_disabled

load_dotenv()

API_KEY   = os.getenv("API_KEY")
BASE_URL  = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")

if not API_KEY:
    raise ValueError("API_KEY 未在环境变量中设置")
if not BASE_URL:
    raise ValueError("BASE_URL 未在环境变量中设置")


client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

set_tracing_disabled(disabled=True)

class DeepSeekModelProvider(ModelProvider):
    def get_model(self, model_name: str) -> Model:
        return OpenAIChatCompletionsModel(
            model=model_name or MODEL_NAME,
            openai_client=client,
        )


model_provider = DeepSeekModelProvider()
