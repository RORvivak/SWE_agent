from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Notion
    notion_api_key: str
    notion_database_id: str = "6414b49db9644262a2f6c4ab2dd0e298"

    # Claude
    anthropic_api_key: str

    # Obsidian
    obsidian_vault_path: str
    obsidian_project_name: str  # subfolder inside vault e.g. "varzo-ai"

    # GitHub
    github_token: str
    github_repo: str  # owner/repo

    # Target repo
    repo_path: str

    # Validation flags
    skip_validation: bool = False
    retry: bool = False


settings = Settings()
