import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class TelethonConfig(BaseModel):
    device_model: str
    system_version: str
    app_version: str
    session: str

    # secrets
    api_id: int | None = None
    api_hash: str | None = None


class TelegramConfig(BaseModel):
    channels: list[str] = Field(..., min_length=1)
    timezone: str
    # Optional per-channel descriptions ({'@handle': 'what it covers'}); given to
    # the model so it can group and attribute stories by source.
    descriptions: dict[str, str] = {}

    @field_validator('channels')
    @classmethod
    def validate_channels(cls, v):
        for channel in v:
            if not channel.startswith('@'):
                raise ValueError(f"Channel {channel} must start with @")
        return v


class AgentConfig(BaseModel):
    model: str
    max_tokens: int = 32000  # max output length of the digest (Sonnet 4.6 allows up to 64000)
    thinking: bool = False    # enable adaptive thinking (needs a model/SDK that supports it)

    # secret
    api_key: str | None = None


class PublishingConfig(BaseModel):
    author_name: str
    summary_channel: str
    domain: str = 'telegra.ph'  # Telegraph API domain; use 'graph.org' if telegra.ph is blocked

    # secret
    access_token: str | None = None


class Config(BaseModel):
    telethon: TelethonConfig
    telegram: TelegramConfig
    agent: AgentConfig
    publishing: PublishingConfig

    @classmethod
    def load(cls, config_path: Path, env_path: Path | None = None):
        if env_path is not None and env_path.exists():
            load_dotenv(env_path)

        with Path.open(config_path) as f:
            config_data = yaml.safe_load(f)

        # Inject secrets into the appropriate nested configs
        if 'telethon' not in config_data:
            config_data['telethon'] = {}
        config_data['telethon']['api_id'] = int(os.getenv('TELEGRAM_API_ID', '0'))
        config_data['telethon']['api_hash'] = os.getenv('TELEGRAM_API_HASH')

        # Resolve a relative session path against the config file's directory, so
        # the CLI works from any working directory. In deployment the config and
        # session live in the same dir, so this is a no-op there.
        session = config_data['telethon'].get('session')
        if session and not Path(session).is_absolute():
            config_data['telethon']['session'] = str((Path(config_path).parent / session).resolve())

        if 'agent' not in config_data:
            config_data['agent'] = {}
        config_data['agent']['api_key'] = os.getenv('ANTHROPIC_API_KEY')

        if 'publishing' not in config_data:
            config_data['publishing'] = {}
        config_data['publishing']['access_token'] = os.getenv('TELEGRAPH_ACCESS_TOKEN')

        return cls(**config_data)

    def validate_secrets(self):
        """Ensure all required secrets are present."""
        errors = []

        if not self.telethon.api_id or not self.telethon.api_hash:
            errors.append("Telethon credentials not found in environment")

        if not self.agent.api_key:
            errors.append("Anthropic API key not found in environment")

        if not self.publishing.access_token:
            errors.append("Telegraph token not found in environment")

        if errors:
            raise ValueError("; ".join(errors))
