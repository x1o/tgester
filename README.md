# Telegram News Digester

## Content

-   80% authentic human code
-   20% synthetic LLM hallucinations

## Features

-   Fetches unread messages from the specified Telegram channels (1 day window)
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

### Deployment

Examine and run `scripts/deploy.sh`.

## License

WTFPL