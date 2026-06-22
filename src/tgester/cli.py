import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from telethon import TelegramClient

from tgester import Config, NewsSummaryAgent, get_messages_for_date, publish_summary

app = typer.Typer(no_args_is_help=True)

# Reusable option annotations
ConfigOpt = Annotated[Path, typer.Option("--config", "-c", help="Path to YAML configuration file")]
EnvOpt = Annotated[Path, typer.Option("--env", "-e", help="Path to .env file")]
ChannelsOpt = Annotated[str | None, typer.Option(
    "--channels", help="Override config channels (comma-separated, e.g. @a,@b)"
)]
DateOpt = Annotated[str | None, typer.Option(
    "--date", help="Date to process (YYYY-MM-DD); defaults to yesterday in the configured timezone"
)]
DebugOpt = Annotated[bool, typer.Option("--debug", "-d", help="Enable debug logging")]


def setup_logging(debug: bool = False):
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def _resolve_date(target_date: str | None, tz: ZoneInfo) -> date:
    """Parse --date or default to yesterday in the target timezone."""
    if target_date is not None:
        return date.fromisoformat(target_date)
    return (datetime.now(tz) - timedelta(days=1)).date()


def _resolve_channels(channels: str | None, cfg: Config) -> list[str]:
    """Use --channels override if given, else the configured channel list."""
    if channels:
        return [c.strip() for c in channels.split(',')]
    return cfg.telegram.channels


@app.command()
def summarise(
        config: ConfigOpt = Path("config.yaml"),
        env_file: EnvOpt = Path(".env"),
        channels: ChannelsOpt = None,
        target_date: DateOpt = None,
        dry_run: Annotated[bool, typer.Option(
            "--dry-run",
            help="Publish to Telegraph but skip posting to the summary channel; print the URL"
        )] = False,
        debug: DebugOpt = False
    ):
    """Generate and post a daily news summary."""
    logger = setup_logging(debug)

    try:
        logger.info(f"Loading config from {config}")
        cfg = Config.load(config, env_file)
        cfg.validate_secrets()

        cfg.telegram.channels = _resolve_channels(channels, cfg)
        if channels:
            logger.info(f"Overriding channels: {cfg.telegram.channels}")

        summary_date = _resolve_date(target_date, ZoneInfo(cfg.telegram.timezone))
        logger.info(f"Summarising news for {summary_date.isoformat()} ({cfg.telegram.timezone})")

        logger.info("Starting news summary generation")
        asyncio.run(_run_summary(cfg, summary_date, dry_run, logger))
        logger.info("Summary completed successfully")

    except Exception:
        logger.exception("Failed")
        raise typer.Exit(code=1) from None


@app.command()
def fetch(
        config: ConfigOpt = Path("config.yaml"),
        env_file: EnvOpt = Path(".env"),
        channels: ChannelsOpt = None,
        target_date: DateOpt = None,
        debug: DebugOpt = False
    ):
    """Fetch and print messages for a date (no LLM, no publishing) — useful for debugging."""
    logger = setup_logging(debug)

    try:
        cfg = Config.load(config, env_file)
        if not cfg.telethon.api_id or not cfg.telethon.api_hash:
            raise ValueError("Telethon credentials not found in environment")

        chans = _resolve_channels(channels, cfg)
        summary_date = _resolve_date(target_date, ZoneInfo(cfg.telegram.timezone))
        logger.info(f"Fetching {len(chans)} channels for {summary_date.isoformat()} ({cfg.telegram.timezone})")

        asyncio.run(_run_fetch(cfg, chans, summary_date))

    except Exception:
        logger.exception("Failed")
        raise typer.Exit(code=1) from None


@app.command()
def models(
        env_file: EnvOpt = Path(".env"),
    ):
    """List Claude models available to your API key (newest first)."""
    import anthropic
    from dotenv import load_dotenv

    if env_file.exists():
        load_dotenv(env_file)

    try:
        client = anthropic.Anthropic()
        for m in client.models.list(limit=30):
            print(f"{m.id:28} {m.display_name}")
    except Exception as e:
        typer.echo(f"Failed to list models: {e}", err=True)
        raise typer.Exit(code=1) from None


async def _run_summary(cfg: Config, summary_date: date, dry_run: bool, logger):
    """Run the actual summary generation."""
    session_path = Path(cfg.telethon.session)
    session_path.parent.mkdir(exist_ok=True)

    client = TelegramClient(**dict(cfg.telethon))
    agent = NewsSummaryAgent(
        client,
        model_id=cfg.agent.model,
        target_tz=cfg.telegram.timezone,
        max_tokens=cfg.agent.max_tokens,
        thinking=cfg.agent.thinking
    )

    logger.info(f"Processing {len(cfg.telegram.channels)} channels")

    summary = await agent.create_daily_summary(
        cfg.telegram.channels,
        summary_date,
        cfg.telegram.descriptions
    )

    logger.info("Summary generated successfully")

    logger.info("Publishing to Telegraph")

    telegraph_response = publish_summary(
        summary.content,
        cfg.publishing.access_token,
        cfg.publishing.author_name,
        cfg.publishing.domain
    )

    logger.info(f"Published: {telegraph_response['url']}")

    if dry_run:
        logger.info("Dry run: skipping post to summary channel")
        print(telegraph_response['url'])
        return

    # Post to summary channel
    async with client:
        await client.send_message(
            cfg.publishing.summary_channel,
            telegraph_response['url']
        )
        logger.info(f"Posted to {cfg.publishing.summary_channel}")


async def _run_fetch(cfg: Config, channels: list[str], summary_date: date):
    """Fetch messages for the date and print them, grouped by channel."""
    session_path = Path(cfg.telethon.session)
    session_path.parent.mkdir(exist_ok=True)

    client = TelegramClient(**dict(cfg.telethon))
    messages = await get_messages_for_date(
        client, channels, summary_date, cfg.telegram.timezone
    )

    for channel, msgs in messages.items():
        print(f"\n=== {channel} ({len(msgs)} messages) ===")
        for m in msgs:
            oneline = ' '.join(m['text'].split())
            print(f"[{m['time']}] {oneline[:200]}")


if __name__ == "__main__":
    app()
