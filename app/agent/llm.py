from langchain.chat_models import init_chat_model
from app.conf.app_config import app_config

llm = init_chat_model(
    model=app_config.llm.model_name,
    base_url="https://api.deepseek.com",
    API_KEY=app_config.llm.api_key,
    temperature=0
)