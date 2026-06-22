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
    # Each entry is either '@handle' or a single-key mapping {'@handle': 'description'}.
    # Descriptions, where present, are given to the model for grouping/attribution.
    channels: list[str | dict[str, str | None]] = Field(..., min_length=1)
    timezone: str

    @field_validator('channels')
    @classmethod
    def validate_channels(cls, v):
        for entry in v:
            if isinstance(entry, dict):
                if len(entry) != 1:
                    raise ValueError(
                        f"Channel entry {entry} must be a single '@handle: description' mapping"
                    )
                name = next(iter(entry))
            else:
                name = entry
            if not isinstance(name, str) or not name.startswith('@'):
                raise ValueError(f"Channel {name!r} must start with @")
        return v

    @property
    def channel_names(self) -> list[str]:
        return [next(iter(c)) if isinstance(c, dict) else c for c in self.channels]

    @property
    def descriptions(self) -> dict[str, str]:
        result = {}
        for c in self.channels:
            if isinstance(c, dict):
                name, desc = next(iter(c.items()))
                if desc:
                    result[name] = desc
        return result


class AgentConfig(BaseModel):
    model: str
    max_tokens: int = 32000  # max output length of the digest (Opus 4.8 allows up to 128000)
    thinking: bool = True     # adaptive thinking (needs a model/SDK that supports it; default model does)

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
