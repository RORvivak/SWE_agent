import shutil
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_claude() -> str:
    if path := shutil.which("claude"):
        return path
    # nvm installs node tools here but doesn't add them to non-login shells
    fallbacks = [
        Path.home() / ".nvm/versions/node/v20.20.2/bin/claude",
        Path.home() / ".nvm/versions/node/v22.22.2/bin/claude",
        Path("/usr/local/bin/claude"),
    ]
    for p in fallbacks:
        if p.exists():
            return str(p)
    raise FileNotFoundError(
        "claude CLI not found. Install it or set CLAUDE_BIN in .env"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    claude_bin: str = ""  # override via .env if needed

    # Notion
    notion_api_key: str
    notion_database_id: str = "6414b49db9644262a2f6c4ab2dd0e298"

    # Claude (only needed if fix.py RETRY path is used)
    anthropic_api_key: str = ""

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
if not settings.claude_bin:
    settings.claude_bin = _find_claude()
