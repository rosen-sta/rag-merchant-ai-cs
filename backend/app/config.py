from functools import lru_cache
import logging
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    chat_model: str = Field(default="deepseek-v4-flash", alias="CHAT_MODEL")
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-small-zh-v1.5", alias="EMBEDDING_MODEL")
    chroma_db_path: str = Field(default="./data/chroma", alias="CHROMA_DB_PATH")
    sqlite_db_path: str = Field(default="./data/app.db", alias="SQLITE_DB_PATH")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    @property
    def sqlite_path(self) -> Path:
        return self.resolve_path(self.sqlite_db_path)

    @property
    def chroma_path(self) -> Path:
        return self.resolve_path(self.chroma_db_path)

    @property
    def use_local_embedding(self) -> bool:
        return self.embedding_provider.lower().strip() == "local"

    @property
    def has_deepseek_chat(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_base_url and self.chat_model)

    def warn_if_incomplete(self) -> None:
        if not self.deepseek_api_key:
            logger.warning(
                "DEEPSEEK_API_KEY 未配置：后端会启动，但 /api/chat 将使用本地检索摘要兜底，"
                "不会调用 DeepSeek。请在 .env 中填写 DEEPSEEK_API_KEY。"
            )
        if not self.use_local_embedding:
            logger.warning("当前 MVP 只支持本地 embedding，已忽略非 local 的 EMBEDDING_PROVIDER 配置。")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "uploads").mkdir(parents=True, exist_ok=True)
    return settings
