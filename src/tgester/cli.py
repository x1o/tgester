import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from telethon import TelegramClient

from tgester import Config, NewsSummaryAgent, publish_summary

app = typer.Typer(no_args_is_help=True)

def setup_logging(debug: bool = False):
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


@app.command()
def summarise(
        config: Annotated[Path, typer.Option(
            "--config", "-c",
            help="Path to YAML configuration file"
        )] = Path("config.yaml"),
        env_file: Annotated[Path, typer.Option(
            "--env", "-e",
            help="Path to .env file"
        )] = Path(".env"),
        target_date: Annotated[str | None, typer.Option(
            "--date",
            help="Date to summarise (YYYY-MM-DD); defaults to yesterday in the configured timezone"
        )] = None,
        # channels: Annotated[str | None, typer.Option(
        #     "--channels",
        #     help="Override channels (comma-separated)"
        # )] = None,
        debug: Annotated[bool, typer.Option(
            "--debug", "-d",
            help="Enable debug logging"
        )] = False
    ):
    """Generate and post daily news summary."""
    logger = setup_logging(debug)

    try:
        # Load and validate configuration
        logger.info(f"Loading config from {config}")
        cfg = Config.load(config, env_file)
        cfg.validate_secrets()

        # # Override channels if specified
        # if channels:
        #     cfg.telegram.channels = [c.strip() for c in channels.split(',')]
        #     logger.info(f"Overriding channels: {cfg.telegram.channels}")

        tz = ZoneInfo(cfg.telegram.timezone)
        if target_date is not None:
            summary_date = date.fromisoformat(target_date)
        else:
            summary_date = (datetime.now(tz) - timedelta(days=1)).date()
        logger.info(f"Summarising news for {summary_date.isoformat()} ({cfg.telegram.timezone})")

        logger.info("Starting news summary generation")
        asyncio.run(_run_summary(cfg, summary_date, logger))
        logger.info("Summary completed successfully")

    except Exception:
        logger.exception("Failed")
        raise typer.Exit(code=1) from None


async def _run_summary(cfg: Config, summary_date: date, logger):
    """Run the actual summary generation."""
    session_path = Path(cfg.telethon.session)
    session_path.parent.mkdir(exist_ok=True)

    client = TelegramClient(**dict(cfg.telethon))
    agent = NewsSummaryAgent(
        client,
        model_id=cfg.agent.model,
        target_tz=cfg.telegram.timezone
    )

    logger.info(f"Processing {len(cfg.telegram.channels)} channels")

    summary = await agent.create_daily_summary(
        cfg.telegram.channels,
        summary_date
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

    # Post to summary channel
    async with client:
        await client.send_message(
            cfg.publishing.summary_channel,
            telegraph_response['url']
        )
        logger.info(f"Posted to {cfg.publishing.summary_channel}")


if __name__ == "__main__":
    app()
