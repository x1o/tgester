# Telegram News Digester

## Content

-   80% authentic human code
-   20% synthetic LLM hallucinations

## Features

-   Fetches all messages posted on a given date (defaults to *yesterday*) from the specified Telegram channels
-   Works even when the account is not a member of the channels (public channels are scraped by `@username`)
-   Creates analytical summaries grouping news by topics across all sources
-   Publishes to Telegra.ph and posts the link to a designated channel

## Configuration and Installation

### Telegram App setup

Create a new Telegram application to get API credentials:

-   Go to <https://my.telegram.org/apps>

-   Create application and save `api_id` and `api_hash`

-   See [Telethon docs](https://docs.telethon.dev/en/stable/basic/signing-in.html) for details

**Important**: The `device_model`, `system_version`, and `app_version` fields in config are mandatory. Telegram actually *bans* accounts if these are mis-specified or suspicious.

### Configuration

Copy and edit configuration files:

``` bash
# Channel lists, timezone, etc
cp inst/config.example.yaml config.yaml
# Credentials
cp inst/example.env .env
```

Sign in once and save the session file.

## Usage

``` bash
# Generate the digest for yesterday and post it to the summary channel
tgester summarise -c config.yaml -e .env

# Pick a date and/or override the channels; --dry-run publishes to Telegra.ph
# but skips the channel post and just prints the URL (handy for testing)
tgester summarise -c config.yaml -e .env \
    --date 2026-06-19 --channels @nplusone,@bbbreaking --dry-run

# Print the messages a date would pull, without the LLM or publishing (debug)
tgester fetch -c config.yaml -e .env --channels @nplusone --date 2026-06-19

# List the Claude models your API key can access (newest first)
tgester models -e .env
```

A relative `session` path in the config is resolved against the config file's
directory, so the commands work from any working directory.

### Deployment

Examine and run `scripts/deploy.sh`.

## License

WTFPL