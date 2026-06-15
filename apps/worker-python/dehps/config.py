from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


WORKER_DIR = Path(__file__).resolve().parents[1]


def _find_root_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docker-compose.yaml").exists():
            return parent
    return WORKER_DIR


ROOT_DIR = _find_root_dir()
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    db_host: str = Field("localhost", alias="DB_HOST")
    db_port: int = Field(54329, alias="DB_PORT")
    db_name: str = Field("dehps", alias="DB_NAME")
    db_user: str = Field("dehps", alias="DB_USER")
    db_password: str = Field("dehps_password", alias="DB_PASSWORD")
    ssq_sync_source: str = Field("zhcw", alias="SSQ_SYNC_SOURCE")
    ssq_csv_path: str | None = Field(None, alias="SSQ_CSV_PATH")
    ssq_crawler_user_agent: str = Field("ArkDEHPS/0.1", alias="SSQ_CRAWLER_USER_AGENT")
    ssq_crawler_timeout_seconds: int = Field(15, alias="SSQ_CRAWLER_TIMEOUT_SECONDS")
    ssq_crawler_max_retries: int = Field(2, alias="SSQ_CRAWLER_MAX_RETRIES")
    dehps_auto_git: bool = Field(False, alias="DEHPS_AUTO_GIT")
    dehps_git_remote: str = Field("origin", alias="DEHPS_GIT_REMOTE")
    dehps_git_branch: str = Field("main", alias="DEHPS_GIT_BRANCH")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def get_settings() -> Settings:
    return Settings()
