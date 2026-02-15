from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = Field(default='Cypher Multi-Agent Backend', alias='APP_NAME')
    api_v1_prefix: str = Field(default='/api/v1', alias='API_V1_PREFIX')

    hardcoded_username: str = Field(default='demo_user', alias='HARDCODED_USERNAME')
    hardcoded_api_key: str = Field(default='demo-key-123', alias='HARDCODED_API_KEY')

    bge_model_name: str = Field(default='BAAI/bge-base-en-v1.5', alias='BGE_MODEL_NAME')
    faiss_index_path: str = Field(default='data/agent1.index', alias='FAISS_INDEX_PATH')
    faiss_metadata_path: str = Field(default='data/agent1_metadata.json', alias='FAISS_METADATA_PATH')

    knowledge_base_path: str = Field(default='knowledge_base.json', alias='KNOWLEDGE_BASE_PATH')
    agent3_store_path: str = Field(default='data/agent3_scores.json', alias='AGENT3_STORE_PATH')
    groq_api_key: str = Field(default='', alias='GROQ_API_KEY')
    groq_base_url: str = Field(default='https://api.groq.com/openai/v1', alias='GROQ_BASE_URL')
    groq_model: str = Field(default='llama-3.1-8b-instant', alias='GROQ_MODEL')
    groq_timeout_seconds: int = Field(default=60, alias='GROQ_TIMEOUT_SECONDS')
    groq_max_retries: int = Field(default=4, alias='GROQ_MAX_RETRIES')
    groq_requests_per_minute: int = Field(default=20, alias='GROQ_REQUESTS_PER_MINUTE')
    agent2_max_loops: int = Field(default=6, alias='AGENT2_MAX_LOOPS')

    chunk_size: int = Field(default=800, alias='CHUNK_SIZE')
    chunk_overlap: int = Field(default=120, alias='CHUNK_OVERLAP')


@lru_cache
def get_settings() -> Settings:
    return Settings()
